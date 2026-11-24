"""`scripts/README.md` 与三份入口文档的路径一致性断言(R-6 / R-7 / R-8)。

背景:仓内脚本清单只有一个真源 —— `scripts/README.md`;`README.md` / `WORKFLOW.md` /
`AGENTS.md` 各自只保留自己的角色视图(入口指路 / 什么时候跑 / 症状 → 文件),不复制明细。
本模块把这层约定变成机器断言:

1. 索引覆盖磁盘实况:每个非夹具脚本文件都在索引里出现(按**磁盘实况**遍历,不信 git);
2. 索引里提到的每个 `scripts/...` 路径都真实存在(索引不得留「已不存在的脚本路径」);
3. 三份入口文档里提到的每个 `scripts/...` 路径都真实存在,**且**都被索引覆盖;
4. 索引至少包含关键入口(顶层 2 + 门禁 8 + `scripts/acceptance/run-all-gates.sh`)。

红灯证明:把索引复制到临时文件、删掉其中一行(设置环境变量 `SSDCTL_INDEX_PATH`
指向该副本),本模块的断言 1 与断言 3 必然转红 —— 证明这些断言不是恒真的。

退出码沿用仓内约定:0 = 通过,1 = 有断言失败,2 = 用法错误。
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

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

#: 关键入口(断言 4)。
KEY_ENTRIES = (
    "scripts/ssdctl.sh",
    "scripts/ssdctl.py",
    "scripts/check-line-endings.sh",
    "scripts/check-md-schema.sh",
    "scripts/check-naming.sh",
    "scripts/check-repo-baseline.sh",
    "scripts/check-traceability.sh",
    "scripts/check-doc-links.py",
    "scripts/sync-prd.sh",
    "scripts/sync-test-index.sh",
    "scripts/acceptance/run-all-gates.sh",
)


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


if __name__ == "__main__":
    unittest.main()
