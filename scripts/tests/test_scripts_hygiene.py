"""scripts/ 面的「卫生」断言:机器绑定路径、重复的门禁清单、解释器探测、--stage 契约。

这些是本轮整理(需求集 scripts-tidy.md)的**防回退**断言:
- 门禁清单只能有一份(代码里的 `GATE_SCRIPTS`),脚本不得再自带一份;
- 解释器解析只能有一个入口(`bash scripts/ssdctl.sh --python`);
- scripts/ 下不得出现机器相关的绝对路径(用户目录 / 本机工程目录 / file:// 盘符 URL);
- 与阶段无关的 3 个门禁收到 `--stage` 必须 exit 2 并说明原因。

说明:本文件自身在 `scripts/tests/` 下,扫描时**排除** `scripts/tests/` ——
否则这些断言里的模式字面量会把自己判为违规。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import REPO_ROOT, SCRIPTS_DIR
from lib import commands
from lib.criteria import Document, evaluate, load_criteria

SCRIPTS_ROOT = SCRIPTS_DIR

# 机器绑定路径:用户目录 / 本机工程目录 / file:// 盘符 URL
BANNED_PATH_PATTERNS = [
    re.compile(r"/c/Users/"),
    re.compile(r"/d/project/"),
    re.compile(r"file:///D:/"),
    re.compile(r"/Users/leroy/"),
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]"),
    re.compile(r"[A-Za-z]:[\\/]+project[\\/]"),
]

# 门禁脚本的名字:**从真源派生**(`lib/commands.py` 的 `GATE_SCRIPTS`)。
# 本文件不再自带一份硬编码清单 —— 否则「清单只有一份」这件事本身就破了自己的规矩。
GATE_SCRIPT_NAMES = [Path(script).name for script, _args in commands.GATE_SCRIPTS]

# 与阶段无关的门禁(阶段相关必填项由 check-md-schema.sh 判定)
STAGE_IRRELEVANT = [
    "check-naming.sh",
    "check-traceability.sh",
    "check-repo-baseline.sh",
]

# 允许出现「全部门禁名」的两处:真源,以及输出快照(golden)。
# 其余任何文件都不得逐个列出门禁名 —— 那就是第二份清单。
GATE_LIST_ALLOWED = {
    Path("scripts/lib/commands.py"),
    Path("scripts/tests/test_gate_json.py"),
}

# 解释器探测的典型写法:只允许出现在 scripts/ssdctl.sh 里
INTERPRETER_PROBE_PATTERNS = [
    re.compile(r"command -v python"),
    re.compile(r"which python"),
    re.compile(r"py -3"),
    re.compile(r"python3 -c"),
    re.compile(r"python -c"),
]


def _script_files() -> list[Path]:
    out = []
    for path in sorted(SCRIPTS_ROOT.rglob("*")):
        if path.suffix not in {".sh", ".py"}:
            continue
        if "tests" in path.parts:  # 排除 scripts/tests/(本文件自身含模式字面量)
            continue
        out.append(path)
    return out


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _bash() -> str:
    for candidate in (
        os.environ.get("SSDCTL_BASH"),
        r"C:\Program Files\Git\bin\bash.exe",
        shutil.which("bash"),
    ):
        if candidate and Path(candidate).exists():
            return candidate
    raise unittest.SkipTest("找不到 bash —— 无法在本机验证 shell 门禁的行为")


class ScriptsHygiene(unittest.TestCase):
    def test_no_machine_bound_paths_under_scripts(self):
        offenders = []
        for path in _script_files():
            text = _read(path)
            for number, line in enumerate(text.splitlines(), 1):
                for pattern in BANNED_PATH_PATTERNS:
                    if pattern.search(line):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")
        self.assertFalse(offenders, "scripts/ 下不允许出现机器绑定的绝对路径:\n" + "\n".join(offenders))

    def test_run_all_gates_has_no_inlined_gate_list(self):
        text = _read(SCRIPTS_ROOT / "acceptance" / "run-all-gates.sh")
        self.assertIn("gate --json", text, "run-all-gates.sh 必须消费 `ssdctl gate --json`")
        found = [name for name in GATE_SCRIPT_NAMES if name in text]
        self.assertLess(
            len(found),
            3,
            "run-all-gates.sh 不得再自带一份门禁清单(真源是 lib/commands.py 的 GATE_SCRIPTS): "
            + ", ".join(found),
        )

    def test_clone_verify_has_no_inlined_gate_list(self):
        text = _read(SCRIPTS_ROOT / "acceptance" / "clone-verify.sh")
        found = [name for name in GATE_SCRIPT_NAMES if name in text]
        self.assertLess(
            len(found),
            3,
            "clone-verify.sh 不得再自带一份门禁清单: " + ", ".join(found),
        )

    def test_ci_workflow_has_no_inlined_gate_list(self):
        """CI 工作流不得自带一份门禁清单 —— 真源只有 `lib/commands.py` 的 `GATE_SCRIPTS`。

        允许的唯一例外:「PRD 台账登记」步骤直接调用 `sync-prd.sh` 的**写模式**
        (一次具体动作,不是清单);门禁一律由 `run-all-gates.sh` 从真源渲染。
        """
        path = REPO_ROOT / ".github" / "workflows" / "spec-check.yml"
        if not path.exists():
            self.skipTest("仓内没有 CI 工作流文件 —— 本条断言不适用")
        text = _read(path)
        allowed = {"sync-prd.sh"}
        offenders = [name for name in GATE_SCRIPT_NAMES if name in text and name not in allowed]
        self.assertEqual(
            offenders,
            [],
            ".github/workflows/spec-check.yml 不得逐个列出门禁名(那会构成第二份清单): "
            + ", ".join(offenders),
        )
        counts = re.findall(r"\d+\s*个(?:既有)?门禁", text)
        self.assertEqual(
            counts,
            [],
            "CI 文件里不要硬编码门禁个数 —— 个数会随真源漂移;真源 = lib/commands.py 的 GATE_SCRIPTS",
        )

    def test_ssdctl_sh_usage_matches_ssdctl_py_subcommands(self):
        source = _read(SCRIPTS_ROOT / "ssdctl.py")
        declared = set(re.findall(r'add_parser\(\s*"([a-z-]+)"', source))
        self.assertGreaterEqual(len(declared), 1, "解析不到 ssdctl.py 的子命令表")

        usage = _read(SCRIPTS_ROOT / "ssdctl.sh")
        listed = set()
        for line in usage.splitlines():
            match = re.match(r"^#\s+bash scripts/ssdctl\.sh ([a-z][a-z-]*)\b", line)
            if match:
                listed.add(match.group(1))
        self.assertTrue(listed, "ssdctl.sh 的用法块里没解析出子命令")
        self.assertEqual(
            listed,
            declared,
            "ssdctl.sh 用法块的子命令集合必须与 ssdctl.py 的子命令表完全一致",
        )

    def test_stage_irrelevant_gates_reject_stage_flag(self):
        bash = _bash()
        for name in STAGE_IRRELEVANT:
            with self.subTest(script=name):
                for flag in ("--stage", "--stage=ready"):
                    proc = subprocess.run(
                        [bash, f"scripts/{name}", flag, "ready"],
                        cwd=str(REPO_ROOT),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    self.assertEqual(
                        proc.returncode,
                        2,
                        f"{name} {flag} 必须 exit 2(本门禁与阶段无关)",
                    )
                    self.assertIn("本门禁与阶段无关", proc.stderr)
                    self.assertIn("--stage", proc.stderr)

    def test_gate_list_has_single_source(self):
        """门禁清单只能有一份:真源是 `lib/commands.py` 的 `GATE_SCRIPTS`。

        允许的第二份是 `tests/test_gate_json.py` 的 **输出快照**(golden)——
        它记的是「gate --json 曾经输出过什么」,不是清单;真源之外的任何文件
        逐个列出门禁名,都是清单副本。
        """
        offenders = []
        for path in sorted(SCRIPTS_ROOT.rglob("*")):
            if path.suffix not in {".sh", ".py"}:
                continue
            rel = path.relative_to(REPO_ROOT)
            if rel in GATE_LIST_ALLOWED:
                continue
            text = _read(path)
            found = [name for name in GATE_SCRIPT_NAMES if name in text]
            if len(found) == len(GATE_SCRIPT_NAMES):
                offenders.append(f"{rel}: 逐个列出了全部 {len(GATE_SCRIPT_NAMES)} 个门禁名")
        self.assertEqual(
            offenders,
            [],
            "门禁清单只能有一份(真源 lib/commands.py 的 GATE_SCRIPTS):\n  "
            + "\n  ".join(offenders),
        )

    def test_gate_count_matches_contract(self):
        """门禁个数是契约的一部分 —— 增删门禁必须同时改契约与快照。"""
        self.assertEqual(
            7,
            len(GATE_SCRIPT_NAMES),
            "仓内门禁应为 7 个(真源 lib/commands.py 的 GATE_SCRIPTS)",
        )

    def test_repo_text_files_cover_tracked_files(self):
        """仓库层受检集合 = 全部受版本控制的文件(减去含 NUL 的二进制)。

        覆盖面必须与被删掉的行尾脚本逐项对齐 —— 少收 `scripts/tests/**`、
        `.gitattributes`、`.gitignore` 就等于把规则改窄了。
        """
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "-c", "core.quotePath=false", "ls-files"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            self.skipTest("git 不可用 —— 取不到受版本控制的文件清单")
        tracked = [line for line in proc.stdout.splitlines() if line.strip()]
        self.assertTrue(tracked, "git ls-files 没有输出 —— 本条断言无法执行")
        expected = set()
        for rel in tracked:
            path = REPO_ROOT / rel
            if not path.is_file():
                continue
            if commands._contains_nul(path):
                continue
            expected.add(path.resolve())
        actual = {path.resolve() for path in commands._repo_text_files(REPO_ROOT)}
        self.assertEqual(
            expected,
            actual,
            "仓库层受检集合必须等于「全部受版本控制的文件 − 含 NUL 的二进制」",
        )
        rels = {path.relative_to(REPO_ROOT).as_posix() for path in commands._repo_text_files(REPO_ROOT)}
        for must in (".gitattributes", ".gitignore"):
            self.assertIn(must, rels, f"受检集合漏掉了 {must}")
        self.assertTrue(
            any(rel.startswith("scripts/tests/") for rel in rels),
            "受检集合漏掉了 scripts/tests/** —— 测试文件也是受版本控制的文件",
        )

    def test_repo_criteria_flag_cr_injection(self):
        """注入 CR 字节 ⇒ 仓库层判据变红并指出文件与行号;撤销 ⇒ 变绿。"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "schema").mkdir(parents=True)
            (repo / "scripts").mkdir()
            shutil.copyfile(
                REPO_ROOT / "schema" / "criteria.json", repo / "schema" / "criteria.json"
            )
            target = repo / "crlf.txt"
            target.write_bytes(b"alpha\r\nbeta\r\n")
            binary = repo / "blob.bin"
            binary.write_bytes(b"head\x00tail")

            files = commands._repo_text_files(repo)
            names = {path.name for path in files}
            self.assertIn("crlf.txt", names, "受检集合必须收 CRLF 文本文件")
            self.assertNotIn("blob.bin", names, "含 NUL 字节的文件必须按二进制跳过")

            criteria = load_criteria(repo / "schema" / "criteria.json")
            result = evaluate(criteria, Document.from_repo(repo, files), "repo")
            self.assertFalse(result.passed, "注入 CR 后仓库层判据必须不通过")
            ids = [item.criterion_id for item in result.failures]
            self.assertIn("REPO-NO-CR", ids, "CR 违规必须由 REPO-NO-CR 报出")
            located = " ".join(item.locate() for item in result.failures)
            self.assertIn("crlf.txt:1", located, "必须指出文件与行号")

            target.write_bytes(b"alpha\nbeta\n")
            result = evaluate(criteria, Document.from_repo(repo, files), "repo")
            self.assertTrue(result.passed, "撤销 CR 后仓库层判据必须通过")

    def test_only_one_interpreter_probe(self):
        """解释器解析只有一个入口:scripts/ssdctl.sh。"""
        self.assertIn("command -v python3", _read(SCRIPTS_ROOT / "ssdctl.sh"))
        offenders = []
        for path in _script_files():
            if path.name == "ssdctl.sh":
                continue
            text = _read(path)
            for number, line in enumerate(text.splitlines(), 1):
                for pattern in INTERPRETER_PROBE_PATTERNS:
                    if pattern.search(line):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")
        self.assertFalse(
            offenders,
            "scripts/ 下不允许出现第二套解释器探测(统一走 `bash scripts/ssdctl.sh --python`):\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
