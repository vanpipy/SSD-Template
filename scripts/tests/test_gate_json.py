"""`ssdctl gate --json` 的输出契约。

背景:AGENTS.md §3.6 对外承诺 `gate [--json]`,但实现一直忽略 `--json`
(解析器声明了参数,`cmd_gate` 从不看它)。本文件把「JSON 模式与文本模式
描述**同一批门禁**」钉成断言,并守住「文本模式的骨架不漂移」。

要点:
- `--json` 的 stdout 是**纯 JSON**(能 `json.loads`),顶层键固定;
- `gates[]` 每项带 script / args / exit_code / stdout_bytes / soft_fail / output / stderr;
- `criteria[]` / `artifacts[]` 的形状固定(scope / target / passed / failures / warnings 等);
- 文本模式与 JSON 模式说的是同一批门禁:数量、顺序、脚本名、退出码一致
  —— 这正是「收集与打印分离」的定义,也是文本模式逐字不变的前提;
- 文本模式的**骨架**(小标题 + 门禁清单)与 golden 逐字相同;
- 文本模式里不含任何「每次跑都会变」的成分(时间戳 / 临时路径 / 计时),
  否则 golden 会自己漂移。

关于 golden 为什么是「骨架」而不是整份文本:
整份文本里嵌着仓内的**易变状态**(文件数、链接条数、制品数、制品路径)——
制品一变 golden 就红,那是噪声而不是回归。契约真正要守住的是
「门禁是哪几个、什么顺序、带什么参数、文本分成哪几段、末行怎么下结论」,
这些全在骨架里;整份文本的逐字节比对在改动当场用仓外 golden 做(见交付报告)。

性能:一次 gate 要跑 8 个门禁脚本(本机约 30 秒),所以这里把 gate 调用
做成**模块级缓存** —— 否则 11 个用例会跑 20 多次 gate,单测套件会被拖爆。
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest

from _support import REPO_ROOT, run_cli
from lib import commands

# 文本模式的门禁行:「✓ scripts/check-naming.sh  → exit 0」/「! scripts/sync-prd.sh --check → exit 1」
GATE_LINE = re.compile(r"^(?P<label>[✓!✗]) (?P<script>\S+) (?P<args>.*?)→ exit (?P<code>-?\d+)$")

TEXT_HEADERS = ("— 仓内门禁 —", "— 判据 —", "— 制品自洽性 —")

# golden:文本模式的稳定骨架(小标题 + 门禁清单 + 末行结论)
GOLDEN_SKELETON = """— 仓内门禁 —
scripts/check-line-endings.sh
scripts/check-naming.sh
scripts/check-md-schema.sh
scripts/check-traceability.sh
scripts/check-repo-baseline.sh
scripts/check-doc-links.py
scripts/sync-prd.sh --check
scripts/sync-test-index.sh --check
— 判据 —
— 制品自洽性 —
"""

# 「每次跑都会变」的成分:时间戳 / 临时目录 / 计时
VOLATILE_PATTERNS = [
    re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"),
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\s]*AppData[\\/]+Local[\\/]+Temp"),
    re.compile(r"\b(elapsed|duration|took \d)\b", re.IGNORECASE),
]

_RUN_CACHE: dict[tuple[str, ...], subprocess.CompletedProcess] = {}


def _run(*args: str) -> subprocess.CompletedProcess:
    """跑一次 CLI 并缓存结果(门禁本身要 30 秒,重复跑没有意义)。"""
    key = tuple(args)
    if key not in _RUN_CACHE:
        _RUN_CACHE[key] = run_cli(REPO_ROOT, *args)
    return _RUN_CACHE[key]


def _gate_json() -> dict:
    proc = _run("gate", "--json")
    assert proc.returncode == 0, f"gate --json 退出码 {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def _gate_text() -> str:
    proc = _run("gate")
    assert proc.returncode == 0, f"gate 退出码 {proc.returncode}: {proc.stderr}"
    return proc.stdout


def _gate_labels(text: str) -> list[str]:
    """文本模式里每个门禁的「脚本 + 参数」(顺序即执行顺序)。"""
    labels = []
    for line in text.splitlines():
        match = GATE_LINE.match(line)
        if match:
            labels.append(f"{match.group('script')} {match.group('args').strip()}".strip())
    return labels


def _conclusion(text: str) -> str:
    """末行结论(全绿 = 「✓ 全部门禁通过」;否则 = 「✗ 门禁未通过: N 项」)。"""
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


class GateJsonContract(unittest.TestCase):
    def test_json_stdout_is_pure_json(self):
        proc = _run("gate", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stripped = proc.stdout.strip()
        self.assertTrue(stripped.startswith("{"), "JSON 模式必须以 { 开头")
        self.assertTrue(stripped.endswith("}"), "JSON 模式必须以 } 结尾")
        json.loads(stripped)  # 解析失败即红
        for header in TEXT_HEADERS:
            self.assertNotIn(header, proc.stdout, f"JSON 模式不应混进文本小标题 {header!r}")

    def test_top_level_keys_are_exactly_the_contract(self):
        payload = _gate_json()
        self.assertEqual(
            set(payload),
            {"ok", "failures", "gates", "criteria", "artifacts"},
            "顶层键必须固定,多一个少一个都算破约",
        )
        self.assertIsInstance(payload["ok"], bool)
        self.assertIsInstance(payload["failures"], int)
        self.assertIsInstance(payload["gates"], list)
        self.assertIsInstance(payload["criteria"], list)
        self.assertIsInstance(payload["artifacts"], list)

    def test_gate_entries_have_required_fields(self):
        payload = _gate_json()
        self.assertGreaterEqual(len(payload["gates"]), 1)
        for gate in payload["gates"]:
            missing = {
                "script",
                "args",
                "exit_code",
                "stdout_bytes",
                "soft_fail",
                "output",
                "stderr",
            } - set(gate)
            self.assertFalse(missing, f"{gate.get('script')} 缺字段 {sorted(missing)}")
            self.assertIsInstance(gate["script"], str)
            self.assertIsInstance(gate["args"], list)
            self.assertIsInstance(gate["exit_code"], int)
            self.assertIsInstance(gate["stdout_bytes"], int)
            self.assertIsInstance(gate["soft_fail"], bool)
            self.assertIsInstance(gate["output"], str)
            self.assertIsInstance(gate["stderr"], str)
            self.assertEqual(
                gate["stdout_bytes"],
                len(gate["output"].encode("utf-8")),
                f"{gate['script']}: stdout_bytes 必须等于 stdout 原文的字节数",
            )

    def test_gate_list_matches_the_code_declaration(self):
        """JSON 里的门禁清单 = 代码里声明的那一份(顺序也一致)。"""
        payload = _gate_json()
        declared = [script for script, _args in commands.GATE_SCRIPTS]
        self.assertGreaterEqual(len(declared), 1, "解析不到 GATE_SCRIPTS 声明")
        self.assertEqual([gate["script"] for gate in payload["gates"]], declared)

    def test_ok_is_consistent_with_failures(self):
        payload = _gate_json()
        self.assertEqual(payload["ok"], payload["failures"] == 0, "ok 必须等于「零失败」")
        hard_failures = [
            gate
            for gate in payload["gates"]
            if gate["exit_code"] != 0 and not (gate["soft_fail"] and gate["exit_code"] != 0)
        ]
        if not hard_failures and not payload["artifacts"]:
            self.assertTrue(payload["ok"], "全部门禁退出码为 0 且没有制品问题 ⇒ ok 必须为 true")

    def test_criteria_and_artifacts_shapes(self):
        payload = _gate_json()
        for row in payload["criteria"]:
            missing = {"scope", "target", "passed", "failures", "warnings"} - set(row)
            self.assertFalse(missing, f"criteria 行缺字段 {sorted(missing)}")
            self.assertIn(row["scope"], {"artifact", "layer", "repo"}, row)
            self.assertIsInstance(row["target"], str)
            self.assertIsInstance(row["passed"], bool)
            self.assertIsInstance(row["failures"], list)
            self.assertIsInstance(row["warnings"], list)
        for row in payload["artifacts"]:
            missing = {"artifact", "problems"} - set(row)
            self.assertFalse(missing, f"artifacts 行缺字段 {sorted(missing)}")
            self.assertIsInstance(row["artifact"], str)
            self.assertIsInstance(row["problems"], list)

    def test_text_mode_describes_the_same_gates(self):
        """文本模式 = JSON 收集结果的投影:数量、顺序、脚本名、退出码必须一致。"""
        payload = _gate_json()
        text = _gate_text()
        lines = [line for line in text.splitlines() if GATE_LINE.match(line)]
        self.assertEqual(
            len(lines),
            len(payload["gates"]),
            "文本里的门禁行数必须等于 JSON 里的门禁数",
        )
        for line, gate in zip(lines, payload["gates"]):
            match = GATE_LINE.match(line)
            self.assertEqual(match.group("script"), gate["script"])
            self.assertEqual(match.group("args").strip(), " ".join(gate["args"]))
            self.assertEqual(int(match.group("code")), gate["exit_code"])

    def test_text_skeleton_matches_golden(self):
        """文本骨架 = golden(逐字)。门禁增删改名改参数都会让它红。"""
        text = _gate_text()
        self.assertEqual(
            _gate_labels(text),
            [
                line.strip()
                for line in GOLDEN_SKELETON.splitlines()
                if line.strip() and not line.startswith("— ")
            ],
            "文本模式的门禁清单与 golden 不一致",
        )

        headers = [line for line in text.splitlines() if line.startswith("— ")]
        self.assertEqual(
            headers,
            [line for line in GOLDEN_SKELETON.splitlines() if line.startswith("— ")],
            "文本模式的小标题与 golden 不一致",
        )

    def test_text_mode_has_no_volatile_tokens(self):
        """文本里不能出现「每次跑都不同」的东西 —— 否则 golden 会自己漂移。"""
        text = _gate_text()
        for pattern in VOLATILE_PATTERNS:
            match = pattern.search(text)
            self.assertIsNone(match, f"文本模式里出现了易变成分 {match.group(0) if match else ''!r}")

    def test_text_mode_conclusion_is_explicit(self):
        """末行必须明确下结论(全绿 / 有失败),不能默默结束。"""
        conclusion = _conclusion(_gate_text())
        self.assertTrue(
            conclusion.startswith("✓ 全部门禁通过") or conclusion.startswith("✗ 门禁未通过"),
            f"末行结论不明确: {conclusion!r}",
        )

    def test_text_mode_emits_no_json(self):
        text = _gate_text()
        self.assertFalse(text.lstrip().startswith("{"), "文本模式不应输出 JSON")
        self.assertNotIn('"ok":', text, "文本模式不应混进 JSON 字段")
        for header in TEXT_HEADERS:
            self.assertIn(header, text, f"文本模式应包含小标题 {header!r}")


if __name__ == "__main__":
    unittest.main()
