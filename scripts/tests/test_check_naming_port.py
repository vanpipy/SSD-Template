"""check-naming 门禁的 Python 端口 vs bash 原件 —— 等价性测试。

契约(需求集 `.swarm/requirements/phase-b-gate-python-port.md` R-1):

* 等价判据 = **归一化后逐字节相同 + 同退出码**,stdout 与 stderr 都要比;
* 归一化规则(对两侧同时施加,与 `.swarm/tools/diff_gate.py` 一致):
  - 门禁 basename:`check-*.sh` / `check-*.py` 一律 → `{GATE}`(其它门禁同理);
  - 调用前缀:`bash scripts/` 与 `python scripts/` → `{RUN} scripts/`;
  - 临时根路径:Windows 形态、JSON 转义后的 Windows 形态、POSIX 形态 → `{ROOT}`;
* 归一化之外的任何一个字节不同即判失败;
* 新实现必须用新身份(`check-naming.py`)—— 这是**唯一**允许的差异。

本文件同时承担两件事:

1. **差分**:现场重跑 bash 原件与 Python 端口,逐字节比较;
2. **corpus 契约**:仓内 golden(`fixtures/naming-corpus.json`)由 bash 原件采集,
   本测试验证端口输出与 golden 一致、golden 的 provenance(原件 SHA-1)未漂移、
   每条规则都有触发用例、标记确实出现在对应输出里、且变异自证(反例真的能红)。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PORT = REPO / "scripts" / "check-naming.py"
ORIGINAL = REPO / "scripts" / "check-naming.sh"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "naming-corpus.json"
BASH = r"C:\Program Files\Git\bin\bash.exe"

#: 归一化用的身份串(与 `.swarm/tools/diff_gate.py` 的 IDENT 保持一致)。
IDENT = [
    ("check-naming.sh", "{GATE}"),
    ("check-naming.py", "{GATE}"),
    ("check-md-schema.sh", "{GATE-md}"),
    ("check-md-schema.py", "{GATE-md}"),
    ("check-traceability.sh", "{GATE-tr}"),
    ("check-traceability.py", "{GATE-tr}"),
]


def canon(data: bytes, root: Path | None = None, posix_root: str = "") -> bytes:
    """R-1 的归一化:两侧同时施加,归一化之外必须逐字节相同。"""
    text = data.decode("utf-8", "replace")
    if root is not None:
        windows = str(root)
        for variant in (windows, windows.replace("\\", "\\\\")):
            if variant:
                text = text.replace(variant, "{ROOT}")
    if posix_root:
        text = text.replace(posix_root, "{ROOT}")
    text = text.replace("bash scripts/", "{RUN} scripts/").replace("python scripts/", "{RUN} scripts/")
    for old, new in IDENT:
        text = text.replace(old, new)
    return text.encode("utf-8")


def sha1_of(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _haystack(case: dict) -> bytes:
    """用例的 stdout + stderr(归一化后)—— 标记查找用的干草堆。"""
    return canon(case["expect_stdout"].encode("utf-8")) + canon(
        case.get("expect_stderr", "").encode("utf-8")
    )


def materialize(case: dict, root: Path) -> None:
    """把用例的文件树铺到临时仓根。"""
    for rel, content in case.get("files", {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")


def stage_gates(root: Path) -> None:
    """把两个门禁实现放进临时仓的 `scripts/`,以便**相对路径**调用。

    相对路径是刻意的:bash 原件的错误前缀是 `$0`,端口的是 `sys.argv[0]`;
    两侧都用 `scripts/<name>` 调用,前缀才落在同一形态上(归一化后 `{GATE}`)。
    """
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    for src in (ORIGINAL, PORT):
        if src.exists():
            shutil.copyfile(src, scripts / src.name)


def posix_root(root: Path) -> str:
    """问 bash 要临时根的 POSIX 形态(Git Bash 下是 `/c/Users/...`)。

    bash 不可用时返回空串:调用方只是少做一层归一化,不该因此报错。
    """
    if not os.path.exists(BASH):
        return ""
    try:
        proc = subprocess.run([BASH, "-c", f'cd "{root}" && pwd'], capture_output=True)
    except OSError:
        return ""
    return proc.stdout.decode("utf-8", "replace").strip()


def run_bash(root: Path, args: list[str]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run([BASH, "scripts/check-naming.sh", *args], cwd=str(root), capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def run_port(root: Path, args: list[str]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [sys.executable, "scripts/check-naming.py", *args], cwd=str(root), capture_output=True
    )
    return proc.returncode, proc.stdout, proc.stderr


#: 规则 → 输出里必须出现的标记(取自 bash 原件的真实措辞)。
#: 只覆盖措辞有辨识度的规则;其余规则靠「触发用例存在」+「退出码语义」保证。
RULE_MARKERS = {
    "cli-help": "退出码: 0=通过 1=存在违规 2=调用/环境错误",
    "cli-json": '"script":"{GATE}"',
    "cli-root-missing": "根目录不存在",
    "cli-target-missing": "TARGET 不存在",
    "cli-unknown-arg": "未知参数",
    "cli-two-targets": "只接受一个 TARGET",
    "cli-root-no-value": "--root 需要参数",
    "cli-stage": "本门禁与阶段无关",
    "cli-root-equals-form": "命名与层结构检查通过",
    "layer-not-enabled-note": "层未启用(目录不存在,跳过)",
    "layer-enabled-but-no-artifact-warn": "层已启用但没有任何制品",
    "layer-only-root-docs-warn": "层已启用但没有任何规格制品",
    "repo-empty-err": "本仓没有任何规格产物,门禁无从校验",
    "layer-root-extra-file-err": "层根目录不允许放规格文件",
    "material-root-md-warn": "素材区根目录出现 .md",
    "prd-depth-err": "形状错误: prd/ 下只允许",
    "prd-date-dir-err": "日期目录格式错误(期望 YYYY-MM-DD): prd/",
    "prd-topic-warn": "疑似 PRD 命名不合规",
    "td-depth-err": "形状错误: tech_design/ 下只允许",
    "td-dir-name-err": "Tech Design 目录名必须为",
    "plan-depth-err": "形状错误: plan/ 下只允许",
    "plan-dir-name-err": "Plan 目录名必须为",
    "plan-name-must-match-dir-err": "Plan 文件名必须等于目录 topic",
    "tc-depth-err": "形状错误: test_cases/ 下只允许",
    "tc-date-dir-err": "日期目录格式错误(期望 YYYY-MM-DD): test_cases/",
    "tc-topic-err": "测试用例文件名不合法",
    "tc-suffix-strip-ok": "命名与层结构检查通过",
    "material-depth-err": "形状错误: material/ 下只允许",
    "material-date-dir-err": "素材批次目录格式错误(期望 YYYY-MM-DD)",
    "target-single-file-ok": "单文件模式: 只检查",
    "target-single-file-depth-err": "形状错误: prd/ 下只允许",
    "target-single-file-topic-warn": "疑似 PRD 命名不合规",
    "target-single-file-skips-name-check": "单文件模式: 只检查 plan/2026-11-22-feature-a/other.md",
    "target-single-dir-mode": "单目录模式: 只检查",
    "target-bad-layer-dir": "无法识别的层目录",
    "target-bad-layer-file": "无法识别的层路径",
    "material-not-counted-as-artifact": "制品 0 个",
    "hidden-md-is-scanned": "prd/2026-11-22/.hidden.md",
}

#: 这些字符串**不得**出现在对应规则的触发用例输出里 —— 规则的证据是「缺席」而不是「出现」。
RULE_ABSENT_MARKERS = {
    "cli-double-dash": '"script"',
    "target-single-file-skips-name-check": "Plan 文件名必须等于目录 topic",
    "uppercase-suffix-ignored": "feature-a.MD",
}

#: 这些规则靠**输出顺序**证明(标记必须按序出现,顺序本身就是规则)。
RULE_MARKER_SEQUENCES = {
    "multi-file-sort-order": ["Apple.md", "Zebra.md", "mango_1.md"],
    "mixed-layers-order": [
        "形状错误: prd/",
        "Tech Design 目录名必须为",
        "Plan 目录名必须为",
        "日期目录格式错误(期望 YYYY-MM-DD): test_cases/",
        "素材区根目录出现 .md",
    ],
}

#: 这些错误措辞**不得**出现在退出码为 0 的用例输出里(防止「规则其实没生效」)。
ERROR_MARKERS = [
    "层根目录不允许放规格文件",
    "形状错误:",
    "日期目录格式错误",
    "素材批次目录格式错误",
    "Tech Design 目录名必须为",
    "Plan 目录名必须为",
    "Plan 文件名必须等于目录 topic",
    "测试用例文件名不合法",
    "本仓没有任何规格产物",
    "根目录不存在",
    "TARGET 不存在",
    "未知参数",
]


#: 需要「bash 解释器 + bash 原件」同时在场才能跑的用例。
#: 集成阶段(R-4)删除 bash 原件后,这些用例必须 **skip**,不能 fail/error;
#: 而只依赖仓内 corpus 的用例必须继续跑 —— 原件删除后 corpus 是唯一的行为真源。
NEEDS_ORIGINAL = "bash 原件已删除(R-4 集成阶段)或 bash 解释器不可用,无法现场重跑原件"


class CheckNamingPortTest(unittest.TestCase):
    """端口与 bash 原件的差分 + corpus 契约。"""

    maxDiff = None

    # ---------- 差分 ----------

    @unittest.skipUnless(
        os.path.exists(BASH) and ORIGINAL.exists(), NEEDS_ORIGINAL
    )
    def test_port_matches_bash_original_byte_for_byte(self) -> None:
        """R-1:每个用例的 (exit, stdout, stderr) 归一化后逐字节相同。

        需要 bash 原件在场:集成阶段(R-4)删除原件后本用例 skip,
        而不是 fail —— 届时仓内 corpus 是唯一的行为真源。
        """
        data = load_fixture()
        self.assertGreaterEqual(len(data["cases"]), 40)
        for case in data["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    materialize(case, root)
                    stage_gates(root)
                    rc_b, out_b, err_b = run_bash(root, case["args"])
                    rc_p, out_p, err_p = run_port(root, case["args"])
                    posix = posix_root(root)
                    self.assertEqual(rc_b, rc_p, "退出码不一致")
                    self.assertEqual(
                        canon(out_b, root, posix),
                        canon(out_p, root, posix),
                        "stdout 归一化后不一致",
                    )
                    self.assertEqual(
                        canon(err_b, root, posix),
                        canon(err_p, root, posix),
                        "stderr 归一化后不一致",
                    )

    def test_port_matches_recorded_golden(self) -> None:
        """端口输出与仓内 golden(采集自 bash 原件)一致。"""
        data = load_fixture()
        for case in data["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    materialize(case, root)
                    stage_gates(root)
                    rc_p, out_p, err_p = run_port(root, case["args"])
                    posix = posix_root(root)
                    self.assertEqual(rc_p, case["expect_exit"], "退出码与 golden 不一致")
                    self.assertEqual(
                        canon(out_p, root, posix),
                        canon(case["expect_stdout"].encode("utf-8")),
                        "stdout 与 golden 不一致",
                    )
                    self.assertEqual(
                        canon(err_p, root, posix),
                        canon(case.get("expect_stderr", "").encode("utf-8")),
                        "stderr 与 golden 不一致",
                    )

    def test_golden_records_the_original_fingerprint(self) -> None:
        """corpus 必须保留原件指纹与身份字段(原件被删后也要成立)。"""
        data = load_fixture()
        self.assertEqual(data["source_gate"], "scripts/check-naming.sh")
        self.assertEqual(data["gate"], "scripts/check-naming.py")
        self.assertTrue(
            data["source_sha1"], "corpus 必须保留 source_sha1(采集时的原件指纹)"
        )

    @unittest.skipUnless(ORIGINAL.exists(), NEEDS_ORIGINAL)
    def test_golden_provenance_matches_current_original(self) -> None:
        """golden 记录的 SHA-1 必须等于当前 bash 原件的 SHA-1(原件被删后跳过)。"""
        data = load_fixture()
        self.assertEqual(data["source_sha1"], sha1_of(ORIGINAL))

    # ---------- corpus 契约 ----------

    def test_every_rule_has_a_firing_case(self) -> None:
        """R-3:每条规则至少有一个触发用例。"""
        data = load_fixture()
        used: set[str] = set()
        for case in data["cases"]:
            used.update(case.get("rules", []))
        missing = sorted(set(data["rules"]) - used)
        self.assertEqual(missing, [], f"这些规则没有触发用例: {missing}")
        unknown = sorted(used - set(data["rules"]))
        self.assertEqual(unknown, [], f"用例引用了规则表里没有的规则: {unknown}")

    def test_rule_markers_appear_in_their_cases(self) -> None:
        """规则标记必须真的出现在**至少一个**触发用例的输出里(否则映射表就是假的)。

        口径说明:标记按**规则**判定,不按「每个携带该规则的用例」判定 ——
        有些规则是环境性的(如「层未启用」只在层目录缺失的用例里出现),
        要求每个携带用例都出现标记会把正确的用例判成失败。
        """
        data = load_fixture()
        for rule, marker in RULE_MARKERS.items():
            cases = [c for c in data["cases"] if rule in c.get("rules", [])]
            self.assertTrue(cases, f"规则 {rule} 没有触发用例")
            hits = [c["name"] for c in cases if marker.encode("utf-8") in _haystack(c)]
            self.assertTrue(
                hits,
                f"规则 {rule} 的标记 {marker!r} 未出现在任何触发用例的输出里",
            )

    def test_absent_markers_never_appear(self) -> None:
        """以「缺席」为证据的规则:标记不得出现在任何触发用例的输出里。"""
        data = load_fixture()
        for rule, marker in RULE_ABSENT_MARKERS.items():
            cases = [c for c in data["cases"] if rule in c.get("rules", [])]
            self.assertTrue(cases, f"规则 {rule} 没有触发用例")
            for case in cases:
                with self.subTest(case=case["name"], rule=rule):
                    self.assertNotIn(
                        marker.encode("utf-8"),
                        _haystack(case),
                        f"规则 {rule} 的缺席标记 {marker!r} 出现在了用例输出里",
                    )

    def test_marker_sequences_preserve_order(self) -> None:
        """顺序型规则:标记必须按给定顺序出现(顺序本身就是规则)。"""
        data = load_fixture()
        for rule, sequence in RULE_MARKER_SEQUENCES.items():
            cases = [c for c in data["cases"] if rule in c.get("rules", [])]
            self.assertTrue(cases, f"规则 {rule} 没有触发用例")
            hits = []
            for case in cases:
                haystack = _haystack(case).decode("utf-8")
                positions = [haystack.find(marker) for marker in sequence]
                if all(pos >= 0 for pos in positions) and positions == sorted(positions):
                    hits.append(case["name"])
            self.assertTrue(
                hits,
                f"规则 {rule} 的标记序列 {sequence!r} 未在任何触发用例里按序出现",
            )

    def test_fail_rules_have_nonzero_exit_cases(self) -> None:
        """标成「会产生违规」的规则,其触发用例必须以非 0 退出。"""
        data = load_fixture()
        for rule, meta in data["rules"].items():
            if not meta.get("require_fail_case"):
                continue
            cases = [c for c in data["cases"] if rule in c.get("rules", [])]
            self.assertTrue(cases, f"规则 {rule} 没有触发用例")
            self.assertTrue(
                any(c["expect_exit"] != 0 for c in cases),
                f"规则 {rule} 标为会产生违规,但它的用例退出码全是 0",
            )

    def test_error_markers_absent_from_passing_cases(self) -> None:
        """通过用例的输出里不得出现任何错误措辞(防止「规则其实没生效」)。"""
        data = load_fixture()
        for case in data["cases"]:
            if case["expect_exit"] != 0:
                continue
            with self.subTest(case=case["name"]):
                haystack = canon(case["expect_stdout"].encode("utf-8")) + canon(
                    case.get("expect_stderr", "").encode("utf-8")
                )
                for marker in ERROR_MARKERS:
                    self.assertNotIn(
                        marker.encode("utf-8"),
                        haystack,
                        f"通过用例里出现了错误措辞 {marker!r}",
                    )

    def test_new_implementation_uses_the_new_identity(self) -> None:
        """R-1:新实现必须用 `check-naming.py` 身份,不得让用户看到将被删除的 .sh。"""
        source = PORT.read_text(encoding="utf-8")
        self.assertIn('"script":"check-naming.py"', source)
        self.assertNotIn('"script":"check-naming.sh"', source)
        self.assertIn("python scripts/check-naming.py", source)
        self.assertNotIn("bash scripts/check-naming.sh", source)
        self.assertNotIn("scripts/check-md-schema.sh", source)

    # ---------- 变异自证(R-10) ----------

    def _mutated_source(self, anchor: str, old: str, new: str) -> str:
        source = PORT.read_text(encoding="utf-8")
        index = source.index(anchor)
        head, tail = source[:index], source[index:]
        self.assertIn(old, tail, f"锚点 {anchor!r} 之后找不到 {old!r}")
        return head + tail.replace(old, new, 1)

    def _run_source(self, case: dict, source: str) -> tuple[int, bytes]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materialize(case, root)
            scripts = root / "scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            (scripts / "check-naming.py").write_text(source, encoding="utf-8", newline="\n")
            rc, out, _ = run_port(root, case["args"])
            return rc, canon(out, root, posix_root(root))

    def _assert_mutation_flips_case(self, anchor: str, old: str, new: str, case_name: str) -> None:
        data = load_fixture()
        case = next(c for c in data["cases"] if c["name"] == case_name)
        golden = canon(case["expect_stdout"].encode("utf-8"))
        mutated = self._mutated_source(anchor, old, new)
        rc, out = self._run_source(case, mutated)
        self.assertNotEqual(
            out,
            golden,
            f"变异 {old!r} → {new!r} 后,{case_name} 的输出没有变化 ⇒ 该反例不会红",
        )

    def test_mutation_breaks_topic_rule(self) -> None:
        """把 topic 正则改成「全部匹配」,非法 topic 的反例必须转红。"""
        self._assert_mutation_flips_case(
            'TOPIC_RE = re.compile(',
            'r"^[a-z0-9]+(-[a-z0-9]+)*$"',
            'r".*"',
            "tc-bad-topic",
        )

    def test_mutation_breaks_prd_depth_rule(self) -> None:
        """把 prd 的深度判定改坏,prd 深度反例必须转红。"""
        self._assert_mutation_flips_case(
            'if layer == "prd":',
            "if depth != 2:",
            "if depth == 2:",
            "prd-depth3",
        )

    def test_mutation_breaks_test_cases_depth_rule(self) -> None:
        """把 test_cases 的深度判定改坏,test_cases 深度反例必须转红。"""
        self._assert_mutation_flips_case(
            'elif layer == "test_cases":',
            "if depth != 2:",
            "if depth == 2:",
            "tc-depth3",
        )

    def test_mutation_breaks_plan_name_rule(self) -> None:
        """把 plan 的目录名判定改坏,plan 文件名反例必须转红。"""
        self._assert_mutation_flips_case(
            'elif layer == "plan":',
            "if not DATETOPIC_RE.fullmatch(pdir):",
            "if False:",
            "plan-bad-dir",
        )


if __name__ == "__main__":
    unittest.main()
