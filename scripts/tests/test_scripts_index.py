"""`scripts/README.md` 与三份入口文档的路径一致性断言(R-6 / R-7 / R-8)。

背景:仓内脚本清单只有一个真源 —— `scripts/README.md`;`README.md` / `WORKFLOW.md` /
`AGENTS.md` 各自只保留自己的角色视图(入口指路 / 什么时候跑 / 症状 → 文件),不复制明细。
本模块把这层约定变成机器断言:

1. 索引覆盖磁盘实况:每个非夹具脚本文件都在索引里出现(按**磁盘实况**遍历,不信 git);
2. 索引里提到的每个 `scripts/...` 路径都真实存在(索引不得留「已不存在的脚本路径」);
3. 三份入口文档里提到的每个 `scripts/...` 路径都真实存在,**且**都被索引覆盖;
4. 索引至少包含关键入口(顶层 2 + 门禁 7 + `scripts/acceptance/run-all-gates.sh`)。

红灯证明:把索引复制到临时文件、删掉其中一行(设置环境变量 `SSDCTL_INDEX_PATH`
指向该副本),本模块的断言 1 与断言 3 必然转红 —— 证明这些断言不是恒真的。

退出码沿用仓内约定:0 = 通过,1 = 有断言失败,2 = 用法错误。
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib import commands  # noqa: E402  (必须在 sys.path 调整之后)

#: 索引路径。默认取仓内 `scripts/README.md`;红灯证明时用 `SSDCTL_INDEX_PATH` 指向临时副本。
INDEX_PATH = Path(
    os.environ.get("SSDCTL_INDEX_PATH") or (SCRIPTS_DIR / "README.md")
)

#: 三份入口文档(各自只保留自己的角色视图)。
DOC_PATHS = ("README.md", "WORKFLOW.md", "AGENTS.md")

#: 仓内脚本路径的书写形式:`scripts/xxx.sh` / `scripts/lib/yyy.py`。
PATH_RE = re.compile(r"scripts/[A-Za-z0-9_][A-Za-z0-9_./\-*]*")

#: 索引里「已声明但尚未落盘」的区块:该区块内的路径暂不要求磁盘存在。
PENDING_START = "<!-- pending-scripts:start -->"
PENDING_END = "<!-- pending-scripts:end -->"

#: 夹具目录:按一组登记,不逐个文件断言存在性。
FIXTURE_PREFIX = "scripts/tests/fixtures"

#: 关键入口(断言 4)。门禁部分**从真源派生**(`lib/commands.py` 的 `GATE_SCRIPTS`)——
#: 本文件不再自带一份硬编码清单,否则「清单只有一份」这件事本身就破了自己的规矩。
KEY_ENTRIES = (
    "scripts/ssdctl.sh",
    "scripts/ssdctl.py",
    "scripts/acceptance/run-all-gates.sh",
) + tuple(script for script, _args in commands.GATE_SCRIPTS)

#: 工具数上限(需求集 R-4)。计数口径:`scripts/` 下的 `.sh` / `.py`,
#: **排除** `scripts/tests/**`(单测不是工具)、`scripts/README.md`、`__pycache__`。
#: 提高这个上限 = 工具面扩张 —— 必须在需求集里登记理由。
TOOL_COUNT_CAP = 22


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_paths(text: str) -> set[str]:
    """抽出文本里出现的**文件级** `scripts/...` 路径。

    目录引用(`scripts/`、`scripts/lib/`)与夹具组(`scripts/tests/fixtures/`)不是文件,
    不参与存在性断言;含 `*` 的写法是 glob 模式(例如 `scripts/check-*.sh`),
    只是写法记录,同样不参与存在性断言。
    """
    found: set[str] = set()
    for match in PATH_RE.finditer(text):
        candidate = match.group(0).rstrip(".,;:)")
        if candidate.endswith("/"):
            continue
        if "*" in candidate:
            continue
        found.add(candidate)
    return found


def pending_paths(index_text: str) -> set[str]:
    """索引「在途」区块内的路径(已声明、尚未落盘)。"""
    if PENDING_START not in index_text or PENDING_END not in index_text:
        return set()
    block = index_text.split(PENDING_START, 1)[1].split(PENDING_END, 1)[0]
    return extract_paths(block)


def disk_script_files() -> list[str]:
    """磁盘实况:所有非夹具、非 `__pycache__` 的脚本文件(仓库相对路径,正斜杠)。"""
    result: list[str] = []
    for dirpath, dirnames, filenames in os.walk(SCRIPTS_DIR):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            rel = (Path(dirpath) / name).resolve().relative_to(REPO_ROOT)
            posix = rel.as_posix()
            if posix.startswith(FIXTURE_PREFIX):
                continue
            result.append(posix)
    return sorted(result)


def tool_files() -> list[str]:
    """工具文件清单(仓库相对路径,正斜杠)—— R-4 的计数口径。

    与 `disk_script_files()` 的区别:这里**排除 `scripts/tests/**`** ——
    单测是「守卫工具的工具」,不算工具面的一部分;那条断言要的是「每个文件都在索引里」。
    """
    result: list[str] = []
    for dirpath, dirnames, filenames in os.walk(SCRIPTS_DIR):
        dirnames[:] = [d for d in dirnames if d not in {"__pycache__", "tests"}]
        for name in filenames:
            if Path(name).suffix not in {".sh", ".py"}:
                continue
            rel = (Path(dirpath) / name).resolve().relative_to(REPO_ROOT)
            result.append(rel.as_posix())
    return sorted(result)


class ScriptsIndexTest(unittest.TestCase):
    """索引与三份入口文档的一致性断言。"""

    def setUp(self) -> None:
        self.assertTrue(INDEX_PATH.is_file(), f"索引不存在: {INDEX_PATH}")
        self.index_text = read_text(INDEX_PATH)
        self.index_paths = extract_paths(self.index_text)
        self.pending = pending_paths(self.index_text)

    # --- 断言 1:索引覆盖磁盘实况 ---------------------------------------------
    def test_index_covers_every_script_file_on_disk(self) -> None:
        missing = [p for p in disk_script_files() if p not in self.index_text]
        self.assertEqual(
            [],
            missing,
            "索引漏掉了这些脚本文件(每个路径至少要在索引里出现一次):\n  "
            + "\n  ".join(missing),
        )

    # --- 断言 2:索引里不得出现「已不存在的脚本路径」 -------------------------
    def test_every_index_path_exists_on_disk(self) -> None:
        missing = [
            p
            for p in sorted(self.index_paths)
            if p not in self.pending and not (REPO_ROOT / p).exists()
        ]
        self.assertEqual(
            [],
            missing,
            "索引里这些路径在磁盘上不存在(要么补脚本,要么删索引行):\n  "
            + "\n  ".join(missing),
        )

    # --- 断言 3:三份文档提到的路径都存在,且都被索引覆盖 ---------------------
    def test_doc_paths_exist_and_are_covered_by_index(self) -> None:
        problems: list[str] = []
        for name in DOC_PATHS:
            doc = REPO_ROOT / name
            self.assertTrue(doc.is_file(), f"文档不存在: {doc}")
            for path in sorted(extract_paths(read_text(doc))):
                if not (REPO_ROOT / path).exists():
                    problems.append(f"{name}: 路径不存在 -> {path}")
                if path not in self.index_text:
                    problems.append(f"{name}: 路径未被索引覆盖 -> {path}")
        self.assertEqual(
            [],
            problems,
            "三份入口文档里的 scripts/... 路径必须真实存在且被索引覆盖:\n  "
            + "\n  ".join(problems),
        )

    # --- 断言 4:关键入口不能从索引里消失 -------------------------------------
    def test_index_contains_key_entries(self) -> None:
        missing = [p for p in KEY_ENTRIES if p not in self.index_paths]
        self.assertEqual(
            [],
            missing,
            "索引缺少关键入口:\n  " + "\n  ".join(missing),
        )

    # --- 断言 5:工具数封顶(R-4) ----------------------------------------------
    def test_tool_count_is_capped(self) -> None:
        """工具数封顶 —— 提高上限 = 工具面扩张,必须在需求集里登记理由。"""
        tools = tool_files()
        breakdown: dict[str, int] = {}
        for path in tools:
            parts = path.split("/")
            if len(parts) == 2:
                bucket = "scripts/"
            elif parts[1] == "lib":
                bucket = "scripts/lib/"
            else:
                bucket = f"scripts/{parts[1]}/"
            breakdown[bucket] = breakdown.get(bucket, 0) + 1
        self.assertEqual(
            TOOL_COUNT_CAP,
            len(tools),
            "工具数超过上限(提高上限必须在需求集里登记理由):\n  " + "\n  ".join(tools),
        )
        self.assertEqual(
            {"scripts/": 10, "scripts/lib/": 7, "scripts/acceptance/": 5},
            breakdown,
            "工具数分层基线变了 —— 请同步需求集里的基线数字",
        )

    # --- 断言 6:被端口的门禁只能有 Python 实现(Phase B / Phase C · R-5) -------
    def test_ported_gates_have_no_shell_implementation(self) -> None:
        """被端口的六条门禁不得再以 `.sh` 出现在门禁清单里,原件也不得留在仓内。

        Phase B 把「命名 / 字段 / 追溯」三条门禁从 bash 端口为 Python,
        Phase C 把「实现基线 / PRD 台账 / 用例索引」三条也端口为 Python:
        同一条规则只留一份实现 —— 旧的 `.sh` 原件与新的 `.py` 并存
        就是**两份实现**,谁生效取决于谁先跑,正是 Phase A 要消灭的东西。
        """
        ported = (
            "check-naming",
            "check-md-schema",
            "check-traceability",
            "check-repo-baseline",
            "sync-prd",
            "sync-test-index",
        )
        offenders = [
            script
            for script, _args in commands.GATE_SCRIPTS
            if any(script.endswith(f"{name}.sh") for name in ported)
        ]
        self.assertEqual(
            offenders,
            [],
            "被端口的门禁不得再以 .sh 出现在 GATE_SCRIPTS 里:\n  " + "\n  ".join(offenders),
        )
        leftovers = [
            f"scripts/{name}.sh"
            for name in ported
            if (REPO_ROOT / "scripts" / f"{name}.sh").exists()
        ]
        self.assertEqual(
            leftovers,
            [],
            "端口后的 bash 原件必须删除(同一条规则只留一份实现):\n  " + "\n  ".join(leftovers),
        )


if __name__ == "__main__":
    unittest.main()
