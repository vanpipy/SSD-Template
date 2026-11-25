#!/usr/bin/env python3
"""sync-prd 端口等价性单测 + 语料采集器。

被测对象:`scripts/sync-prd.py`(bash 原件 `scripts/sync-prd.sh` 的单进程 Python 端口)。

三个角色:
  1. 语料定义:`CASES` —— 每条用例给出种子文件、CLI 参数、覆盖的规则名与"期望命中的标记"。
  2. 采集器:`--collect` 现场跑 **bash 原件** 采集 golden(退出码 + stdout + stderr),
     写出 `scripts/tests/fixtures/sync-prd-corpus.json`。golden 只由原件采集,
     绝不从 Python 端口反推;临时根路径一律替换成 `{ROOT}`。
  3. 单测:golden 契约(端口输出 == 仓内 golden)、原件在场时的三方对照、变异自证、幂等性。

归一化(与 Lead 的差分器同一套口径):
  * 临时根路径(Windows 形态 / JSON 转义形态 / POSIX 形态)-> `{ROOT}`
  * 调用前缀 `bash scripts/` / `python scripts/` -> `{RUN} scripts/`
  * 脚本身份串 `sync-prd.sh` / `sync-prd.py` -> `{SYNC-prd}`
  * `统计时间: YYYY-MM-DD HH:MM` -> `统计时间: {STAMP}`

用法:
    python scripts/tests/test_sync_prd_port.py --collect        # 重新采集 golden
    python -m unittest discover -s scripts/tests -t scripts/tests
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
CORPUS_PATH = TESTS_DIR / "fixtures" / "sync-prd-corpus.json"
BASH_GATE = SCRIPTS_DIR / "sync-prd.sh"
PY_GATE = SCRIPTS_DIR / "sync-prd.py"

BASH = os.environ.get("SSDCTL_BASH") or r"C:\Program Files\Git\bin\bash.exe"
NEEDS_ORIGINAL = "bash 原件已删除(R-4 集成阶段)"

STAMP_RE = re.compile(r"统计时间: \d{4}-\d{2}-\d{2} \d{2}:\d{2}")

# ---------------------------------------------------------------------------
# 语料:台账表头(与原件 `LEDGER_HEADER` 逐字一致)
# ---------------------------------------------------------------------------

LEDGER_HEADER = (
    "| # | ID | PRD 名称 | 优先级 | 验收要点 | 状态 | 来源 | 关联素材 | 创建时间 | 更新时间 | 提出人 |\n"
    "|---|----|---------|--------|----------|------|------|----------|----------|----------|--------|\n"
)

LEDGER_PREAMBLE = (
    "# PRD 台账 — material/2026-11-20\n"
    "\n"
    "> 由 `scripts/sync-prd.sh` 维护(补登骨架行 / 标记待办行)。"
    "字段含义见 `schema/prd-ledger.md`。\n"
    "\n"
    "## PRD台账\n"
    "\n"
)

# 统计块:与原件生成的 body 逐字一致(空仓 ⇒ 分布列为空)
STATS_TABLE = (
    "| 层 | 制品 | 数量 | 状态分布 |\n"
    "|------|------|:---:|---------|\n"
    "| Layer 1 | PRD | {prd} | {prd_dist} |\n"
    "| Layer 2 | Tech Design | {td} | {td_dist} |\n"
    "| Layer 3 | Plan | {plan} | {plan_dist} |\n"
    "| Layer 4 | Test | {test} | {test_dist} |\n"
    "| 全局 | PRD关联矩阵 | {edges} 条边 | 演进链 {chains} 条 |"
)


def stats_block(prd=0, td=0, plan=0, test=0, edges=0, chains=0, prd_dist="", td_dist="",
                plan_dist="", test_dist="", stamp="2020-01-01 00:00") -> str:
    """拼一个"统计块"(标记块内部),空仓默认值即原件的输出。"""
    table = STATS_TABLE.format(
        prd=prd, td=td, plan=plan, test=test, edges=edges, chains=chains,
        prd_dist=prd_dist, td_dist=td_dist, plan_dist=plan_dist, test_dist=test_dist,
    )
    return (
        "<!-- prd-stats:begin -->\n"
        f"> 统计时间: {stamp} · 由 `scripts/sync-prd.sh` 自动生成\n"
        "\n"
        f"{table}\n"
        "<!-- prd-stats:end -->\n"
    )


README_CURRENT = "# 示例仓\n\n" + stats_block() + "\n## 其它内容\n\n标记块外的内容永不被触碰。\n"
README_STALE = "# 示例仓\n\n" + stats_block(prd=99, prd_dist="Draft 99") + "\n## 其它内容\n\n标记块外的内容永不被触碰。\n"
README_NO_MARKER = "# 示例仓\n\n## 其它内容\n\n没有标记块。\n"

# 一份"全部收敛"的台账(无待办行)
LEDGER_OK = (
    LEDGER_PREAMBLE
    + LEDGER_HEADER
    + "| 1 | PRD-20261120-01 | 示例需求 | 高 | - | 已收敛 | local | notes.md "
    "| 2026-11-20 | 2026-11-20 | alice |\n"
)

# 状态列是占位符 + 优先级待定 ⇒ 未标记的待办行
LEDGER_UNMARKED = (
    LEDGER_PREAMBLE
    + LEDGER_HEADER
    + "| 1 | PRD-20261120-01 | 示例需求 | 待定 | - | 待定 | local | notes.md "
    "| 2026-11-20 | 2026-11-20 | alice |\n"
)

# 关联素材指向不存在的文件 ⇒ 孤儿行
LEDGER_ORPHAN = (
    LEDGER_PREAMBLE
    + LEDGER_HEADER
    + "| 1 | PRD-20261120-02 | 孤儿需求 | 中 | - | 待定 | local | missing.md "
    "| 2026-11-20 | 2026-11-20 | bob |\n"
)

# 来源 external + 创建时间为空 ⇒ 待抓取
LEDGER_EXTERNAL = (
    LEDGER_PREAMBLE
    + LEDGER_HEADER
    + "| 1 | PRD-20261120-03 | 外链需求 | 中 | - | 待定 | external | https://example.com/a "
    "|  |  | bob |\n"
)

# 关联素材指向另一个文件 ⇒ 该素材未被登记(骨架行缺失)
LEDGER_UNREGISTERED = (
    LEDGER_PREAMBLE
    + LEDGER_HEADER
    + "| 1 | PRD-20261120-06 | 别的需求 | 高 | - | 已收敛 | local | other.md "
    "| 2026-11-20 | 2026-11-20 | bob |\n"
)

# 状态列已是"待分析" ⇒ 台账哨兵
LEDGER_SENTINEL = (
    LEDGER_PREAMBLE
    + LEDGER_HEADER
    + "| 1 | PRD-20261120-04 | 哨兵需求 | 高 | - | 待分析 | local | notes.md "
    "| 2026-11-20 | 2026-11-20 | alice |\n"
)

# 有段落但表头没有 ID 列
LEDGER_NO_ID_COL = (
    "# PRD 台账 — material/2026-11-20\n"
    "\n"
    "## PRD台账\n"
    "\n"
    "| 序号 | 名称 | 优先级 | 验收要点 | 状态 | 来源 | 关联素材 | 创建时间 | 更新时间 | 提出人 |\n"
    "|---|---|---|---|---|---|---|---|---|---|\n"
    "| 1 | PRD-20261120-05 | 无 ID 列 | 待定 | - | 待定 | local | notes.md "
    "| 2026-11-20 | 2026-11-20 | alice |\n"
)

# 有素材但没有"## PRD台账"段
LEDGER_NO_SECTION = "# PRD 台账 — material/2026-11-20\n\n| # | ID |\n|---|---|\n"

PRD_DRAFT = "# PRD: demo\n\n> **状态**: Draft\n\n## 为什么 (Why)\n\n- 演示\n"
PRD_READY = "# PRD: demo\n\n> **状态**: Ready\n\n## 为什么 (Why)\n\n- 演示\n"
TD_READY = "# TD: demo\n\n> **状态**: Ready\n\n## 场景映射\n\n- S-1\n"
PLAN_IMPL = "# Plan: demo\n\n> **状态**: Implemented\n\n## 变更清单\n\n### Change #1: x\n"
TESTCASE_READY = (
    "# 用例: demo\n\n"
    "| 主题 | 业务产品 | 目标平台 | 来源 | 生成日期 | 状态 | 用例总数 |\n"
    "|---|---|---|---|---|---|---|\n"
    "| demo | demo | web | prd/2026-11-20/demo.md | 2026-11-20 | Ready | 1 |\n"
)

# 原件的 read_meta_state 只认「第一列是键」的元信息表 ⇒ 状态列在首位才读得到
TESTCASE_READY_META = (
    "# 用例: demo2\n\n"
    "| 状态 | 业务产品 | 目标平台 | 来源 | 生成日期 | 用例总数 |\n"
    "|---|---|---|---|---|---|\n"
    "| Ready | demo | web | prd/2026-11-20/demo.md | 2026-11-20 | 1 |\n"
)

# ---------------------------------------------------------------------------
# 语料:用例表
# ---------------------------------------------------------------------------

CASES: list[dict] = [
    {
        "name": "cli-help",
        "files": {"README.md": "# 仓\n"},
        "args": ["--help"],
        "rules": ["cli-help"],
        "markers": ["用法:"],
    },
    {
        "name": "cli-unknown-arg",
        "files": {"README.md": "# 仓\n"},
        "args": ["--nope"],
        "rules": ["cli-unknown-arg"],
        "markers": ["未知参数"],
    },
    {
        "name": "cli-positional-arg",
        "files": {"README.md": "# 仓\n"},
        "args": ["material"],
        "rules": ["cli-positional-arg"],
        "markers": ["不接受位置参数"],
    },
    {
        "name": "cli-root-missing-value",
        "files": {"README.md": "# 仓\n"},
        "args": ["--root"],
        "rules": ["cli-root-missing-value"],
        "markers": ["--root 需要目录参数"],
    },
    {
        "name": "cli-root-missing-dir",
        "files": {"README.md": "# 仓\n"},
        "args": ["--root", "no-such-root"],
        "rules": ["cli-root-missing-dir"],
        "markers": ["--root 目录不存在"],
    },
    {
        "name": "cli-root-equals-form",
        "files": {"README.md": README_CURRENT},
        "args": ["--root=."],
        "rules": ["cli-root-equals-form"],
        "markers": ["规格统计无变化"],
    },
    {
        "name": "no-material-dir",
        "files": {"README.md": README_CURRENT},
        "args": [],
        "rules": ["material-layer-absent"],
        "markers": ["素材层未启用", "规格统计无变化"],
    },
    {
        "name": "stats-nochange",
        "files": {"README.md": README_CURRENT},
        "args": [],
        "rules": ["stats-block-unchanged"],
        "markers": ["规格统计无变化"],
        "absent_markers": ["统计回写"],
    },
    {
        "name": "stats-rewrite",
        "files": {"README.md": README_STALE},
        "args": [],
        "rules": ["stats-block-rewrite"],
        "markers": ["统计回写"],
        "absent_markers": ["规格统计无变化"],
    },
    {
        "name": "check-stats-drift",
        "files": {"README.md": README_STALE},
        "args": ["--check"],
        "rules": ["check-stats-drift"],
        "markers": ["规格统计块已过期", "--- 当前 ---", "--- 期望 ---"],
    },
    {
        "name": "readme-missing-markers",
        "files": {"README.md": README_NO_MARKER},
        "args": [],
        "rules": ["readme-missing-markers"],
        "markers": ["未找到 prd-stats 标记"],
    },
    {
        "name": "readme-missing-markers-check",
        "files": {"README.md": README_NO_MARKER},
        "args": ["--check"],
        "rules": ["readme-missing-markers-check"],
        "markers": ["缺少 prd-stats 标记块"],
    },
    {
        "name": "material-batch-new-ledger",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/notes.md": "# 素材\n",
        },
        "args": [],
        "rules": ["ledger-create", "ledger-register-skeleton"],
        "markers": ["台账新建", "追加 1 行骨架", "优先级/提出人未落实"],
    },
    {
        "name": "material-batch-register-existing",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/notes.md": "# 素材\n",
            "material/2026-11-20/PRDS.md": LEDGER_OK,
        },
        "args": [],
        "rules": ["ledger-register-skeleton"],
        "markers": ["台账无待办行"],
        "absent_markers": ["台账新建"],
    },
    {
        "name": "material-orphan-row",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/PRDS.md": LEDGER_ORPHAN,
        },
        "args": [],
        "rules": ["ledger-orphan-row"],
        "markers": ["孤儿行"],
    },
    {
        "name": "material-external-pending",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/PRDS.md": LEDGER_EXTERNAL,
        },
        "args": [],
        "rules": ["ledger-external-pending"],
        "markers": ["待抓取"],
    },
    {
        "name": "material-sentinel-row",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/notes.md": "# 素材\n",
            "material/2026-11-20/PRDS.md": LEDGER_SENTINEL,
        },
        "args": [],
        "rules": ["ledger-sentinel-row"],
        "markers": ["台账哨兵"],
    },
    {
        "name": "ledger-missing-section",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/notes.md": "# 素材\n",
            "material/2026-11-20/PRDS.md": LEDGER_NO_SECTION,
        },
        "args": [],
        "rules": ["ledger-missing-section"],
        "markers": ["台账缺少"],
    },
    {
        "name": "ledger-no-id-column",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/notes.md": "# 素材\n",
            "material/2026-11-20/PRDS.md": LEDGER_NO_ID_COL,
        },
        "args": [],
        "rules": ["ledger-no-id-column"],
        "markers": ["ID"],
    },
    {
        "name": "check-missing-ledger",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/notes.md": "# 素材\n",
        },
        "args": ["--check"],
        "rules": ["check-missing-ledger"],
        "markers": ["批次台账缺失"],
    },
    {
        "name": "check-missing-skeleton-rows",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/notes.md": "# 素材\n",
            "material/2026-11-20/PRDS.md": LEDGER_UNREGISTERED,
        },
        "args": ["--check"],
        "rules": ["check-missing-skeleton-rows"],
        "markers": ["骨架行"],
    },
    {
        "name": "check-unmarked-pending-row",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/PRDS.md": LEDGER_UNMARKED,
        },
        "args": ["--check"],
        "rules": ["check-unmarked-pending-row"],
        "markers": ["未标记的待办行"],
    },
    {
        "name": "all-layers-counted",
        "files": {
            "README.md": README_STALE,
            "prd/2026-11-20/demo.md": PRD_DRAFT,
            "tech_design/2026-11-20-demo/README.md": TD_READY,
            "plan/2026-11-20-demo/demo.md": PLAN_IMPL,
            "test_cases/2026-11-20/demo.md": TESTCASE_READY,
            "test_cases/2026-11-20/demo2.md": TESTCASE_READY_META,
        },
        "args": [],
        "rules": ["layer-counts", "distribution-order"],
        "markers": ["统计回写"],
    },
    {
        "name": "distribution-zero-omission",
        "files": {
            "README.md": README_STALE,
            "prd/2026-11-20/a-draft.md": PRD_DRAFT,
            "prd/2026-11-20/b-deprecated.md": PRD_READY.replace("Ready", "Deprecated"),
        },
        "args": [],
        "rules": ["distribution-zero-omission"],
        "markers": ["统计回写"],
    },
    {
        "name": "json-pass",
        "files": {"README.md": README_CURRENT},
        "args": ["--json"],
        "rules": ["json-payload"],
        "markers": ['"status":"pass"', '"exit_code":0'],
    },
    {
        "name": "json-pending",
        "files": {
            "README.md": README_CURRENT,
            "material/2026-11-20/PRDS.md": LEDGER_ORPHAN,
        },
        "args": ["--json"],
        "rules": ["json-payload"],
        "markers": ['"status":"pending"'],
    },
    {
        "name": "json-check-drift",
        "files": {"README.md": README_STALE},
        "args": ["--json", "--check"],
        "rules": ["json-payload", "check-stats-drift"],
        "markers": ['"status":"violation"'],
    },
    {
        "name": "root-prds-ledger",
        "files": {
            "README.md": README_CURRENT,
            "PRDS.md": LEDGER_ORPHAN,
        },
        "args": [],
        "rules": ["root-level-ledger"],
        "markers": ["孤儿行"],
    },
    {
        "name": "material-non-date-dir",
        "files": {
            "README.md": README_CURRENT,
            "material/other/PRDS.md": LEDGER_ORPHAN,
        },
        "args": [],
        "rules": ["material-non-date-dir"],
        "markers": ["孤儿行"],
    },
]

RULES: dict[str, dict] = {
    "cli-help": {"desc": "--help 输出用法到 stdout 并 exit 0", "require_fail_case": False},
    "cli-unknown-arg": {"desc": "未知参数 ⇒ stderr ⇒ exit 2", "require_fail_case": True},
    "cli-positional-arg": {"desc": "位置参数 ⇒ stderr ⇒ exit 2", "require_fail_case": True},
    "cli-root-missing-value": {"desc": "--root 缺值 ⇒ exit 2", "require_fail_case": True},
    "cli-root-missing-dir": {"desc": "--root 目录不存在 ⇒ exit 2", "require_fail_case": True},
    "cli-root-equals-form": {"desc": "--root=DIR 与 --root DIR 等价", "require_fail_case": False},
    "material-layer-absent": {"desc": "material/ 不存在 ⇒ note 跳过台账检查,不算违规", "require_fail_case": False},
    "stats-block-unchanged": {"desc": "统计块与现状一致 ⇒ ok 不回写", "require_fail_case": False},
    "stats-block-rewrite": {"desc": "统计块陈旧 ⇒ 回写标记块(块外不触碰)", "require_fail_case": False},
    "check-stats-drift": {"desc": "--check 下统计块漂移 ⇒ err + 当前/期望对比", "require_fail_case": True},
    "readme-missing-markers": {"desc": "无标记块 ⇒ warn 跳过回写", "require_fail_case": False},
    "readme-missing-markers-check": {"desc": "无标记块 + --check ⇒ err", "require_fail_case": True},
    "ledger-create": {"desc": "批次台账缺失 ⇒ 写模式新建 PRDS.md", "require_fail_case": False},
    "ledger-register-skeleton": {"desc": "素材未登记 ⇒ 补登骨架行(序号取 num 列最大值+1)", "require_fail_case": False},
    "ledger-orphan-row": {"desc": "关联素材不存在 ⇒ 孤儿行 ⇒ 待分析", "require_fail_case": True},
    "ledger-external-pending": {"desc": "来源 external 且创建时间为空 ⇒ 待抓取", "require_fail_case": True},
    "ledger-sentinel-row": {"desc": "状态列已是待分析/待抓取 ⇒ 台账哨兵也算待办", "require_fail_case": True},
    "ledger-missing-section": {"desc": "台账缺 `## PRD台账` 段 ⇒ err", "require_fail_case": True},
    "ledger-no-id-column": {"desc": "台账表无 ID 列 ⇒ err", "require_fail_case": True},
    "check-missing-ledger": {"desc": "--check 下台账缺失 ⇒ err", "require_fail_case": True},
    "check-missing-skeleton-rows": {"desc": "--check 下骨架行不足 ⇒ err", "require_fail_case": True},
    "check-unmarked-pending-row": {"desc": "--check 下待办行未标记 ⇒ err", "require_fail_case": True},
    "layer-counts": {"desc": "四层产物计数(prd/td/plan/test)", "require_fail_case": False},
    "distribution-order": {"desc": "状态分布顺序 Draft→Ready→Implemented→Deprecated→其他", "require_fail_case": False},
    "distribution-zero-omission": {"desc": "计数为 0 的分布项整项省略", "require_fail_case": False},
    "json-payload": {"desc": "JSON 载荷键序固定,status 可为 pending/violation", "require_fail_case": False},
    "root-level-ledger": {"desc": "仓根 PRDS.md 也参与待办统计", "require_fail_case": False},
    "material-non-date-dir": {"desc": "material/ 下非日期目录:登记跳过但待办标记仍执行(原件怪癖)", "require_fail_case": False},
}


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def child_env() -> dict:
    env = dict(os.environ)
    env["NO_COLOR"] = "1"
    env["LC_ALL"] = "C.UTF-8"
    return env


def seed(root: Path, files: dict) -> None:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="")


def stage(root: Path) -> None:
    """把两个门禁拷进临时树(相对路径调用,形态与 Lead 差分器一致)。"""
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    for src in (BASH_GATE, PY_GATE):
        if src.exists():
            shutil.copyfile(src, scripts / src.name)


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, env=child_env())
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


_POSIX_CACHE: dict[str, str] = {}


def posix_of(root: Path) -> str:
    key = str(root)
    if key not in _POSIX_CACHE:
        proc = subprocess.run(
            [BASH, "-c", f'cd "{root}" && pwd'], capture_output=True
        )
        _POSIX_CACHE[key] = proc.stdout.decode("utf-8", "replace").strip()
    return _POSIX_CACHE[key]


def canon(text: str, root: Path) -> str:
    """归一化(与 Lead 差分器同一套口径)。

    临时根有三种形态:Windows 原生(`C:\\...`)、JSON 转义(`C:\\\\...`)、
    Git Bash 的 POSIX 形态(本机 %TEMP% 下为 `/tmp/...`)—— 三者都要归一。
    """
    s = text
    native = str(root)
    variants = [
        native,
        native.replace("\\", "\\\\"),
        native.replace("\\", "/"),
        posix_of(root),
    ]
    for variant in variants:
        if variant:
            s = s.replace(variant, "{ROOT}")
    s = s.replace("bash scripts/", "{RUN} scripts/").replace("python scripts/", "{RUN} scripts/")
    s = s.replace("sync-prd.sh", "{SYNC-prd}").replace("sync-prd.py", "{SYNC-prd}")
    s = STAMP_RE.sub("统计时间: {STAMP}", s)
    return s


def git_blob_sha1(data: bytes) -> str:
    """`git hash-object` 的等价算法:sha1("blob <len>\\0" + data)。"""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tree_files(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in {"scripts", "__pycache__", ".git"} for part in rel.parts):
            continue
        out[rel.as_posix()] = p.read_bytes()
    return out


# ---------------------------------------------------------------------------
# 采集器
# ---------------------------------------------------------------------------


def collect() -> dict:
    """现场跑 bash 原件采集 golden。"""
    cases = []
    for case in CASES:
        with tempfile.TemporaryDirectory(prefix="sync-prd-collect-") as tmp:
            root = Path(tmp)
            seed(root, case["files"])
            stage(root)
            rc, out, err = run([BASH, "scripts/sync-prd.sh", *case["args"]], root)
            posix = posix_of(root)
            out = out.replace(posix, "{ROOT}").replace(str(root), "{ROOT}")
            err = err.replace(posix, "{ROOT}").replace(str(root), "{ROOT}")
            entry = {
                "name": case["name"],
                "files": case["files"],
                "args": case["args"],
                "rules": case["rules"],
                "expect_exit": rc,
                "expect_stdout": out,
                "expect_stderr": err,
            }
            if case.get("markers"):
                entry["markers"] = case["markers"]
            if case.get("absent_markers"):
                entry["absent_markers"] = case["absent_markers"]
            cases.append(entry)
    return {
        "gate": "scripts/sync-prd.py",
        "source_gate": "scripts/sync-prd.sh",
        "source_sha1": git_blob_sha1(BASH_GATE.read_bytes()),
        "collected_by": (
            "bash 原件逐例采集(C:\\Program Files\\Git\\bin\\bash.exe,相对路径调用),"
            "未使用 Python 端口反推;golden 只替换临时根路径为 {ROOT}"
        ),
        "root_placeholder": "{ROOT}",
        "mode": "tree",
        "normalization": (
            "basename sync-prd.sh|sync-prd.py -> {SYNC-prd}; 调用前缀 bash scripts/|python scripts/ "
            "-> {RUN} scripts/; 临时根路径(Windows / JSON 转义 / POSIX) -> {ROOT}; "
            "统计时间: YYYY-MM-DD HH:MM -> {STAMP}"
        ),
        "rules": RULES,
        "cases": cases,
    }


# ---------------------------------------------------------------------------
# 单测
# ---------------------------------------------------------------------------


def load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


class SyncPrdPortTest(unittest.TestCase):
    """端口等价性(仓内 golden 为唯一行为真源,不依赖 bash 原件在场)。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = load_corpus()
        cls.by_name = {c["name"]: c for c in cls.corpus["cases"]}

    def test_corpus_covers_all_cases(self) -> None:
        self.assertEqual(
            [c["name"] for c in self.corpus["cases"]],
            [c["name"] for c in CASES],
            "corpus 与用例表不一致(重新 --collect)",
        )
        self.assertGreaterEqual(len(self.corpus["cases"]), 16)

    def test_source_sha1_matches_bash_gate(self) -> None:
        if not BASH_GATE.exists():
            self.skipTest(NEEDS_ORIGINAL)
        self.assertEqual(
            self.corpus["source_sha1"],
            git_blob_sha1(BASH_GATE.read_bytes()),
            "corpus 记录的 source_sha1 与 bash 原件不符",
        )

    def test_port_reproduces_golden(self) -> None:
        """端口输出 == 仓内 golden(退出码 + stdout + stderr,归一化后)。"""
        for case in self.corpus["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory(prefix="sync-prd-port-") as tmp:
                    root = Path(tmp)
                    seed(root, case["files"])
                    stage(root)
                    rc, out, err = run(
                        [sys.executable, "scripts/sync-prd.py", *case["args"]], root
                    )
                    self.assertEqual(rc, case["expect_exit"], f"{case['name']}: 退出码不符")
                    self.assertEqual(
                        canon(out, root),
                        canon(case["expect_stdout"], root),
                        f"{case['name']}: stdout 与 golden 不符",
                    )
                    self.assertEqual(
                        canon(err, root),
                        canon(case["expect_stderr"], root),
                        f"{case['name']}: stderr 与 golden 不符",
                    )

    def test_port_markers_present(self) -> None:
        """每条用例的期望命中标记必须出现在输出里(语义断言,不只是字节比对)。"""
        for case in self.corpus["cases"]:
            markers = case.get("markers")
            if not markers:
                continue
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory(prefix="sync-prd-mark-") as tmp:
                    root = Path(tmp)
                    seed(root, case["files"])
                    stage(root)
                    _, out, err = run(
                        [sys.executable, "scripts/sync-prd.py", *case["args"]], root
                    )
                    blob = out + err
                    for marker in markers:
                        self.assertIn(marker, blob, f"{case['name']}: 缺标记 {marker!r}")
                    for marker in case.get("absent_markers", []):
                        self.assertNotIn(marker, blob, f"{case['name']}: 不该出现 {marker!r}")

    def test_port_is_idempotent(self) -> None:
        """写模式幂等:同一输入连跑两次,第二次不得再改任何文件。"""
        for name in ("stats-rewrite", "material-batch-new-ledger", "material-orphan-row"):
            case = self.by_name[name]
            with self.subTest(case=name):
                with tempfile.TemporaryDirectory(prefix="sync-prd-idem-") as tmp:
                    root = Path(tmp)
                    seed(root, case["files"])
                    stage(root)
                    run([sys.executable, "scripts/sync-prd.py", *case["args"]], root)
                    first = tree_files(root)
                    run([sys.executable, "scripts/sync-prd.py", *case["args"]], root)
                    second = tree_files(root)
                    self.assertEqual(
                        sorted(first), sorted(second), f"{name}: 第二次运行增删了文件"
                    )
                    for rel in first:
                        self.assertEqual(
                            first[rel], second[rel], f"{name}: {rel} 第二次运行被改动"
                        )

    def test_port_uses_new_identity(self) -> None:
        """身份串:端口一律用 `sync-prd.py`,不得残留被删的 `sync-prd.sh`。"""
        case = self.by_name["cli-help"]
        with tempfile.TemporaryDirectory(prefix="sync-prd-ident-") as tmp:
            root = Path(tmp)
            seed(root, case["files"])
            stage(root)
            _, out, err = run([sys.executable, "scripts/sync-prd.py", "--help"], root)
            blob = out + err
            self.assertIn("scripts/sync-prd.py", blob, "用法行未使用 .py 名")
            self.assertNotIn("sync-prd.sh", blob, "输出里仍残留 .sh 名")

        case = self.by_name["json-pass"]
        with tempfile.TemporaryDirectory(prefix="sync-prd-ident-") as tmp:
            root = Path(tmp)
            seed(root, case["files"])
            stage(root)
            _, out, _ = run([sys.executable, "scripts/sync-prd.py", "--json"], root)
            payload = json.loads(out)
            self.assertEqual(payload["script"], "sync-prd.py")
            self.assertEqual(
                list(payload.keys()),
                [
                    "script", "root", "mode", "status", "exit_code", "error_count",
                    "warning_count", "pending_count", "counts", "errors", "warnings",
                    "notes",
                ],
                "JSON 载荷键序与契约不一致",
            )
            self.assertEqual(
                list(payload["counts"].keys()),
                ["prd", "tech_design", "plan", "test", "matrix_edges"],
                "counts 键序与契约不一致",
            )

    def test_mutation_changes_output(self) -> None:
        """变异自证:改坏判定 ⇒ 对应用例输出必须改变。

        变异锚点用**互不包含**的标记串(替换后原文案必须消失),
        否则「变异后仍含原文案」无法证明变异真的生效。
        """
        mutations = [
            ("material-orphan-row", "孤儿行", "ORPHAN-ROW", "孤儿行"),
            ("material-external-pending", "待抓取", "PENDING-FETCH", "待抓取"),
        ]
        source = PY_GATE.read_text(encoding="utf-8")
        for case_name, needle, replacement, marker in mutations:
            with self.subTest(case=case_name):
                self.assertIn(needle, source, f"变异锚点不存在: {needle!r}")
                mutated = source.replace(needle, replacement)
                case = self.by_name[case_name]
                with tempfile.TemporaryDirectory(prefix="sync-prd-mut-") as tmp:
                    root = Path(tmp)
                    seed(root, case["files"])
                    scripts = root / "scripts"
                    scripts.mkdir(parents=True, exist_ok=True)
                    (scripts / "sync-prd.py").write_text(mutated, encoding="utf-8", newline="")
                    _, out, err = run(
                        [sys.executable, "scripts/sync-prd.py", *case["args"]], root
                    )
                    blob = out + err
                    self.assertNotIn(
                        marker, blob, f"{case_name}: 变异后仍出现原判定文案(变异无效)"
                    )


@unittest.skipUnless(BASH_GATE.exists(), NEEDS_ORIGINAL)
class SyncPrdPortAgainstOriginalTest(unittest.TestCase):
    """需要 bash 原件在场的对照(集成期原件被删 ⇒ 自动 skip)。"""

    def test_bash_original_reproduces_golden(self) -> None:
        corpus = load_corpus()
        for case in corpus["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory(prefix="sync-prd-bash-") as tmp:
                    root = Path(tmp)
                    seed(root, case["files"])
                    stage(root)
                    rc, out, err = run([BASH, "scripts/sync-prd.sh", *case["args"]], root)
                    self.assertEqual(rc, case["expect_exit"])
                    self.assertEqual(canon(out, root), canon(case["expect_stdout"], root))
                    self.assertEqual(canon(err, root), canon(case["expect_stderr"], root))

    def test_bash_and_port_are_byte_identical(self) -> None:
        """两个独立临时树:stdout/stderr/rc 三项全等 + 结果树逐文件字节相同。"""
        corpus = load_corpus()
        for case in corpus["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory(prefix="sync-prd-b-") as tb, \
                        tempfile.TemporaryDirectory(prefix="sync-prd-p-") as tp:
                    rb, rp = Path(tb), Path(tp)
                    seed(rb, case["files"])
                    seed(rp, case["files"])
                    stage(rb)
                    stage(rp)
                    rc_b, out_b, err_b = run([BASH, "scripts/sync-prd.sh", *case["args"]], rb)
                    rc_p, out_p, err_p = run(
                        [sys.executable, "scripts/sync-prd.py", *case["args"]], rp
                    )
                    self.assertEqual(rc_b, rc_p, f"{case['name']}: 退出码不同")
                    self.assertEqual(
                        canon(out_b, rb), canon(out_p, rp), f"{case['name']}: stdout 不同"
                    )
                    self.assertEqual(
                        canon(err_b, rb), canon(err_p, rp), f"{case['name']}: stderr 不同"
                    )
                    fb, fp = tree_files(rb), tree_files(rp)
                    self.assertEqual(sorted(fb), sorted(fp), f"{case['name']}: 文件树不同")
                    for rel in fb:
                        # 归一化后再比:脚本身份串(`.sh` / `.py`)与临时根路径是允许的差异
                        self.assertEqual(
                            canon(fb[rel].decode("utf-8", "replace"), rb),
                            canon(fp[rel].decode("utf-8", "replace"), rp),
                            f"{case['name']}: {rel} 内容不同",
                        )


def _collect_to_disk() -> None:
    data = collect()
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORPUS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline=""
    )
    print(f"collected {len(data['cases'])} cases -> {CORPUS_PATH}")


if __name__ == "__main__":
    if "--collect" in sys.argv:
        _collect_to_disk()
        sys.exit(0)
    unittest.main()
