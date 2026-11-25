"""`scripts/check-md-schema.py` 的端口等价性测试: golden + 逐字节等价 + 变异自证。

corpus = `fixtures/md-schema-corpus.json`:
  * golden **只能由 bash 原件采集** —— `--collect` 模式现场跑原件采集, 不从新实现反推;
  * `source_sha1` 记录 bash 原件的 SHA-1, 防止 golden 与原件漂移;
  * `expect_stdout` 存的是**归一化**后的 golden(与本文件下方的归一化段
    `canon()` 同规则: 临时根路径 → `{ROOT}`、调用前缀 → `{RUN} scripts/`、
    门禁身份名 → `{GATE-md}`); 归一化之外任何字节不同即失败。

四条断言线:
  1. bash 原件现场重跑 ⇒ 复现已存 golden(golden 没被手改);
  2. Python 端口 ⇒ 复现同一 golden(行为等价, stdout + 退出码);
  3. bash 与 Python 的 **stdout 与 stderr** 归一化后逐字节相同;
  4. 每条规则的**正例 / 反例**都真的落在语料里(手写期望, 不是抄 golden)。

运行:
  python -m unittest discover -s scripts/tests -t scripts/tests -k check_md_schema
  python scripts/tests/test_check_md_schema_port.py --collect   # 重新采集 golden
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

from _support import SCRIPTS_DIR, write_text  # noqa: F401  (把 scripts/ 放进 sys.path)
from test_md_schema_gate import DRAFT_PRD, READY_PRD

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
PY_GATE = SCRIPTS_DIR / "check-md-schema.py"
BASH_GATE = SCRIPTS_DIR / "check-md-schema.sh"
CORPUS_PATH = TESTS_DIR / "fixtures" / "md-schema-corpus.json"

DATE_DIR = "2026-11-22"
TOPIC = "demo-feature"
PRD_REL = f"prd/{DATE_DIR}/{TOPIC}.md"
TD_REL = f"tech_design/{DATE_DIR}-{TOPIC}"
PLAN_REL = f"plan/{DATE_DIR}-{TOPIC}"
TC_REL = f"test_cases/{DATE_DIR}/{TOPIC}.md"


def _bash() -> str | None:
    """找一个能跑本仓 shell 门禁的 bash(找不到就 skip, 不假装通过)。"""
    override = os.environ.get("SSDCTL_BASH")
    if override:
        return override
    if os.name == "nt":
        for candidate in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ):
            if os.path.exists(candidate):
                return candidate
    return shutil.which("bash")


BASH = _bash()


# --- 归一化(与仓内差分口径的 canon() 同规则) ---

def canon(data: bytes, root: Path, posix_root: str) -> bytes:
    text = data.decode("utf-8", "replace")
    windows = str(root)
    for variant in (windows, windows.replace("\\", "\\\\")):
        if variant:
            text = text.replace(variant, "{ROOT}")
    if posix_root:
        text = text.replace(posix_root, "{ROOT}")
    text = text.replace("bash scripts/", "{RUN} scripts/").replace("python scripts/", "{RUN} scripts/")
    text = text.replace("check-md-schema.sh", "{GATE-md}").replace("check-md-schema.py", "{GATE-md}")
    return text.encode("utf-8")


def _posix_root(root: Path) -> str:
    if BASH is None:
        return ""
    proc = subprocess.run([BASH, "-c", f'cd "{root}" && pwd'], capture_output=True)
    return proc.stdout.decode("utf-8", "replace").strip()


# --- 语料样本(复用既有反证测试的 READY_PRD / DRAFT_PRD; 其余按 schema 模板补齐) ---

TD_README = """# TD: demo-feature

> **状态**: Ready
> **状态主体**: agent:sddctl
> **状态时间**: 2026-11-22T23:30:00+08:00
> **状态依据**: criteria:TD-READY-01

## 场景映射

| 场景 | 决策 | 约束 |
| --- | --- | --- |
| S-1 | KD-1 | 幂等写入 |

## 门禁清单

- [ ] AC-1 场景映射覆盖 PRD 全部场景

## 变更记录

- 2026-11-22 初版。

## 复审 (Review)

> **评审人**: agent:sddctl
> **评审日期**: 2026-11-22
> **评审结论**: 通过
> **评审方式**: 自动判据
"""

TD_ARDS = """# ARD: demo-feature

## KD-1: 采用幂等写入

- 理由: 避免重复提交。

## 门禁清单

- [ ] AC-1 每个决策都有备选

## 变更记录

- 2026-11-22 初版。
"""

TD_APIS = """# API: demo-feature

## 接口清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /orders | 查询订单 |

## 门禁清单

- [ ] AC-1 每个接口有降级策略

## 变更记录

- 2026-11-22 初版。
"""

TD_DATA_MODEL = """# 数据模型: demo-feature

```erDiagram
    USER ||--o{ ORDER : places
```

## 门禁清单

- [ ] AC-1 字段类型明确

## 变更记录

- 2026-11-22 初版。
"""

TD_V3_README = """# TD: demo-feature (v3)

> **状态**: Ready
> **状态主体**: agent:sddctl
> **状态时间**: 2026-11-22T23:30:00+08:00
> **状态依据**: criteria:TD-READY-01

## 门禁清单

- [ ] AC-1 场景映射覆盖 PRD 全部场景

## 变更记录

- 2026-11-22 初版。

## 复审 (Review)

> **评审人**: agent:sddctl
> **评审日期**: 2026-11-22
> **评审结论**: 通过
> **评审方式**: 自动判据
"""

TD_V3_DECISIONS = """# 决策

## KD-1: 采用幂等写入

## 门禁清单

- [ ] AC-1

## 变更记录

- 2026-11-22 初版。
"""

TD_V3_DATA_MODEL = """# 数据模型

## 门禁清单

- [ ] AC-1

## 变更记录

- 2026-11-22 初版。
"""

TD_V3_API_CONTRACTS = """# 接口契约

## 门禁清单

- [ ] AC-1

## 变更记录

- 2026-11-22 初版。
"""

TD_V3_SCENARIO_MAPPING = """# 场景映射

| 场景 | 决策 |
| --- | --- |
| S-1 | KD-1 |

## 门禁清单

- [ ] AC-1

## 变更记录

- 2026-11-22 初版。
"""

TD_V3_QUALITY = """# 质量属性

## 门禁清单

- [ ] AC-1

## 变更记录

- 2026-11-22 初版。
"""

PLAN_DOC = """# Plan: demo-feature

> **状态**: Ready
> **状态主体**: agent:sddctl
> **状态时间**: 2026-11-22T23:30:00+08:00
> **状态依据**: criteria:PLAN-READY-01

## 变更清单

### Change #1: 仓A/src/orders.ts

- 策略: 按 PRD S-1 实现幂等写入。

## 跨文件引用对账

| 来源 | 目标 | 结论 |
| --- | --- | --- |
| PRD S-1 | V-1 | 已覆盖 |

### V-1: 幂等写入验证

- **场景**: S-1
- **Then** 重复提交不产生第二条记录。

## 复审 (Review)

> **评审人**: agent:sddctl
> **评审日期**: 2026-11-22
> **评审结论**: 通过
> **评审方式**: 自动判据

## 变更记录 (Change Log)

- 2026-11-22 初版。
"""

TEST_CASE_DOC = """# Test Case: demo-feature

> **状态**: Ready
> **状态主体**: agent:sddctl
> **状态时间**: 2026-11-22T23:30:00+08:00
> **状态依据**: criteria:TC-READY-01

## 元信息 (Metadata)

| 字段 | 值 | 必填 | 说明 |
|------|-----|------|------|
| **主题** | demo-feature | ✓ | 与目录/文件名一致 |
| **业务产品** | POS | ✓ | 业务产品 |
| **目标平台** | Web | ✓ | 运行平台 |
| **来源** | prd/2026-11-22/demo-feature.md | ✓ | 上游 PRD |
| **生成日期** | 2026-11-22 | ✓ | 首次生成日期 |
| **状态** | Ready | ✓ | Draft / Ready / Implemented / Deprecated |
| **用例总数** | 1 | ✓ | 用例总数 |

## 用例总览

| 编号 | 标题 |
| --- | --- |
| TC-001 | 幂等写入 |

## 业务背景

- 订单提交。

## 核心测试点

- 重复提交只落一条记录。

## 复审 (Review)

> **评审人**: agent:sddctl
> **评审日期**: 2026-11-22
> **评审结论**: 通过
> **评审方式**: 自动判据
"""

KEY_POINTS_DOC = """# 核心测试点: demo-feature

## 业务背景

- 订单提交。

## 核心测试点

- 重复提交只落一条记录。
"""


def _td_v4(**overrides: str) -> dict[str, str]:
    files = {
        f"{TD_REL}/README.md": TD_README,
        f"{TD_REL}/ards.md": TD_ARDS,
        f"{TD_REL}/apis.md": TD_APIS,
        f"{TD_REL}/data-model.md": TD_DATA_MODEL,
    }
    files.update(overrides)
    return files


def _td_v3(interactions: bool = False, **overrides: str) -> dict[str, str]:
    files = {
        f"{TD_REL}/README.md": TD_V3_README,
        f"{TD_REL}/decisions.md": TD_V3_DECISIONS,
        f"{TD_REL}/data-model.md": TD_V3_DATA_MODEL,
        f"{TD_REL}/api-contracts.md": TD_V3_API_CONTRACTS,
        f"{TD_REL}/scenario-mapping.md": TD_V3_SCENARIO_MAPPING,
        f"{TD_REL}/quality.md": TD_V3_QUALITY,
    }
    if interactions:
        files[f"{TD_REL}/interactions.md"] = "# 交互\n"
    files.update(overrides)
    return files


# --- 语料表: (name, files, args, 期望退出码, 期望输出片段) ---
# 期望退出码与片段是**手写**的(不是抄 golden) —— 它们证明「每条规则都能失败」。

CASES: list[tuple[str, dict[str, str], list[str], int, str | None]] = [
    # --- PRD: 正例 ---
    ("prd-ready-valid", {PRD_REL: READY_PRD}, ["--root", "."], 0, None),
    ("prd-draft-valid", {PRD_REL: DRAFT_PRD}, ["--root", "."], 0, None),
    ("prd-ready-basis-two-criteria",
     {PRD_REL: READY_PRD.replace("criteria:PRD-READY-01", "criteria:PRD-READY-01,PRD-READY-02")},
     ["--root", "."], 0, None),
    ("prd-ready-basis-criteria-and-external",
     {PRD_REL: READY_PRD.replace("criteria:PRD-READY-01", "criteria:PRD-READY-01,external:pr-123")},
     ["--root", "."], 0, None),
    ("prd-ready-state-time-utc",
     {PRD_REL: READY_PRD.replace("2026-11-22T23:30:00+08:00", "2026-11-22T15:30:00Z")},
     ["--root", "."], 0, None),
    ("prd-ready-review-conclusion-conditional",
     {PRD_REL: READY_PRD.replace("> **评审结论**: 通过", "> **评审结论**: 有条件通过")},
     ["--root", "."], 0, None),
    ("prd-ready-review-method-external-fact",
     {PRD_REL: READY_PRD.replace("> **评审方式**: 自动判据", "> **评审方式**: 外部事实")},
     ["--root", "."], 0, None),
    ("prd-draft-known-issue-valid-id",
     {PRD_REL: READY_PRD.replace(
         "## 复审 (Review)\n",
         "## 复审 (Review)\n\n> **已知问题**: PRD-XXX-01 — 待产品确认\n")},
     ["--root", "."], 0, None),

    # --- PRD: 反例 ---
    ("prd-missing-state-line",
     {PRD_REL: READY_PRD.replace("> **状态**: Ready\n", "")},
     ["--root", "."], 1, "缺少状态行"),
    ("prd-state-template-enum",
     {PRD_REL: READY_PRD.replace("> **状态**: Ready", "> **状态**: Draft | Ready | Implemented | Deprecated")},
     ["--root", "."], 1, "状态值非法"),
    ("prd-state-illegal-value",
     {PRD_REL: READY_PRD.replace("> **状态**: Ready", "> **状态**: Banana")},
     ["--root", "."], 1, "状态值非法"),
    ("prd-ready-missing-state-subject",
     {PRD_REL: READY_PRD.replace("> **状态主体**: agent:sddctl\n", "")},
     ["--root", "."], 1, "状态主体"),
    ("prd-ready-missing-state-time",
     {PRD_REL: READY_PRD.replace("> **状态时间**: 2026-11-22T23:30:00+08:00\n", "")},
     ["--root", "."], 1, "状态时间"),
    ("prd-ready-missing-state-basis",
     {PRD_REL: READY_PRD.replace("> **状态依据**: criteria:PRD-READY-01\n", "")},
     ["--root", "."], 1, "状态依据"),
    ("prd-state-subject-illegal",
     {PRD_REL: READY_PRD.replace("> **状态主体**: agent:sddctl", "> **状态主体**: bot:sddctl")},
     ["--root", "."], 1, "状态主体非法"),
    ("prd-state-time-without-timezone",
     {PRD_REL: READY_PRD.replace("2026-11-22T23:30:00+08:00", "2026-11-22 23:30:00")},
     ["--root", "."], 1, "ISO-8601"),
    ("prd-state-basis-no-prefix",
     {PRD_REL: READY_PRD.replace("criteria:PRD-READY-01", "我觉得可以")},
     ["--root", "."], 1, "状态依据项非法"),
    ("prd-state-basis-garbage-after-criteria",
     {PRD_REL: READY_PRD.replace("criteria:PRD-READY-01", "criteria:PRD-READY-01,我可以")},
     ["--root", "."], 1, "状态依据项非法"),
    ("prd-state-basis-decision-prefix",
     {PRD_REL: READY_PRD.replace(
         "criteria:PRD-READY-01",
         "criteria:PRD-READY-01,decision:control/decisions/d1.md#D1")},
     ["--root", "."], 1, "状态依据项非法"),
    ("prd-deprecated-basis-criteria",
     {PRD_REL: READY_PRD.replace("> **状态**: Ready", "> **状态**: Deprecated")},
     ["--root", "."], 1, "Deprecated"),
    ("prd-ready-missing-reviewer",
     {PRD_REL: READY_PRD.replace("> **评审人**: agent:sddctl\n", "")},
     ["--root", "."], 1, "评审人"),
    ("prd-ready-reviewer-placeholder",
     {PRD_REL: READY_PRD.replace("> **评审人**: agent:sddctl", "> **评审人**: {handle}")},
     ["--root", "."], 1, "评审人仍是占位符"),
    ("prd-ready-review-date-not-iso",
     {PRD_REL: READY_PRD.replace("> **评审日期**: 2026-11-22", "> **评审日期**: 22/11/2026")},
     ["--root", "."], 1, "评审日期"),
    ("prd-ready-missing-review-conclusion",
     {PRD_REL: READY_PRD.replace("> **评审结论**: 通过\n", "")},
     ["--root", "."], 1, "评审结论"),
    ("prd-ready-review-conclusion-out-of-domain",
     {PRD_REL: READY_PRD.replace("> **评审结论**: 通过", "> **评审结论**: 大概可以")},
     ["--root", "."], 1, "评审结论取值非法"),
    ("prd-ready-missing-review-method",
     {PRD_REL: READY_PRD.replace("> **评审方式**: 自动判据\n", "")},
     ["--root", "."], 1, "评审方式"),
    ("prd-ready-review-method-out-of-domain",
     {PRD_REL: READY_PRD.replace("> **评审方式**: 自动判据", "> **评审方式**: 随便")},
     ["--root", "."], 1, "评审方式取值非法"),
    ("prd-agent-reviewer-cannot-claim-human-review",
     {PRD_REL: READY_PRD.replace("> **评审方式**: 自动判据", "> **评审方式**: 人工介入")},
     ["--root", "."], 1, "人工介入"),
    ("prd-missing-review-section",
     {PRD_REL: READY_PRD.replace("## 复审 (Review)", "## 评审 (Review)")},
     ["--root", "."], 1, "缺少必填段"),
    ("prd-missing-scenario-section",
     # 原件用前缀匹配 grep 段标题, 只有整段标题消失才算「缺少必填段」;
     # 这里删除标题行, 段体内容保留(段体为空 ⇒ 不再触发 Given 检查)。
     {PRD_REL: READY_PRD.replace("## 场景 (Scenarios)\n", "")},
     ["--root", "."], 1, "缺少必填段"),
    ("prd-goal-without-checkbox",
     {PRD_REL: READY_PRD.replace("- [ ] AC-1 门禁能识别缺字段的 Ready 制品", "- AC-1 门禁能识别缺字段的 Ready 制品")},
     ["--root", "."], 1, "验证标准"),
    ("prd-scenario-without-given",
     {PRD_REL: READY_PRD.replace("**Given** 某个 Ready 制品", "某个 Ready 制品")},
     ["--root", "."], 1, "Given"),
    ("prd-placeholder-left-in-body",
     {PRD_REL: READY_PRD.replace("- [ ] AC-1 门禁能识别缺字段的 Ready 制品", "- [ ] AC-1 {TOPIC}")},
     ["--root", "."], 1, "仍含模板占位符"),
    ("prd-known-issue-illegal-id",
     # 原件只在「复审」段体内查「已知问题」行, 因此该行必须落在复审段内。
     {PRD_REL: READY_PRD.replace(
         "## 复审 (Review)\n",
         "## 复审 (Review)\n\n> **已知问题**: 我觉得不对\n")},
     ["--root", "."], 1, "判据 id 非法"),

    # --- Tech Design ---
    ("td-v4-valid", _td_v4(), ["--root", "."], 0, None),
    ("td-v3-valid", _td_v3(interactions=True), ["--root", "."], 0, None),
    ("td-v3-missing-interactions-is-warn", _td_v3(), ["--root", "."], 0, "interactions.md"),
    ("td-unknown-generation",
     {f"{TD_REL}/README.md": TD_README}, ["--root", "."], 1, "无法判定代际"),
    ("td-v4-missing-readme",
     {f"{TD_REL}/ards.md": TD_ARDS, f"{TD_REL}/apis.md": TD_APIS, f"{TD_REL}/data-model.md": TD_DATA_MODEL},
     ["--root", "."], 1, "缺少必填子文件"),
    ("td-v4-missing-subfile",
     _td_v4(**{f"{TD_REL}/data-model.md": None}) if False else {
         k: v for k, v in _td_v4().items() if not k.endswith("data-model.md")},
     ["--root", "."], 1, "缺少必填子文件"),
    ("td-v4-readme-missing-scenario-mapping",
     _td_v4(**{f"{TD_REL}/README.md": TD_README.replace("## 场景映射", "## 场景对应")}),
     ["--root", "."], 1, "场景映射"),
    ("td-v4-subfile-missing-gate-section",
     _td_v4(**{f"{TD_REL}/ards.md": TD_ARDS.replace("## 门禁清单", "## 检查项")}),
     ["--root", "."], 1, "门禁清单"),
    ("td-v4-subfile-missing-change-log",
     _td_v4(**{f"{TD_REL}/ards.md": TD_ARDS.replace("## 变更记录", "## 修订记录")}),
     ["--root", "."], 1, "变更记录"),
    ("td-v4-data-model-without-er",
     _td_v4(**{f"{TD_REL}/data-model.md": TD_DATA_MODEL.replace("```erDiagram", "```mermaid")}),
     ["--root", "."], 1, "erDiagram"),
    ("td-v4-data-model-declared-no-change",
     _td_v4(**{f"{TD_REL}/data-model.md": TD_DATA_MODEL.replace("```erDiagram", "无数据模型变更\n\n```mermaid")}),
     ["--root", "."], 0, None),

    # --- Plan ---
    ("plan-valid", {f"{PLAN_REL}/{TOPIC}.md": PLAN_DOC}, ["--root", "."], 0, None),
    ("plan-missing-change-list",
     {f"{PLAN_REL}/{TOPIC}.md": PLAN_DOC.replace("## 变更清单", "## 变更")},
     ["--root", "."], 1, "缺少必填段"),
    ("plan-missing-reconciliation",
     {f"{PLAN_REL}/{TOPIC}.md": PLAN_DOC.replace("## 跨文件引用对账", "## 对账")},
     ["--root", "."], 1, "缺少必填段"),
    ("plan-change-numbering-not-from-one",
     {f"{PLAN_REL}/{TOPIC}.md": PLAN_DOC.replace("### Change #1:", "### Change #2:")},
     ["--root", "."], 1, "Change #1"),
    ("plan-v2-single-section",
     {f"{PLAN_REL}/{TOPIC}.md": PLAN_DOC.replace(
         "### Change #1: 仓A/src/orders.ts", "#### 变更说明")},
     ["--root", "."], 1, "Change #1"),
    ("plan-missing-v1",
     {f"{PLAN_REL}/{TOPIC}.md": PLAN_DOC.replace("### V-1: 幂等写入验证", "### 验证用例")},
     ["--root", "."], 1, "V-1"),

    # --- Test Case ---
    ("testcase-valid",
     {TC_REL: TEST_CASE_DOC, f"test_cases/{DATE_DIR}/{TOPIC}-key-points.md": KEY_POINTS_DOC},
     ["--root", "."], 0, None),
    ("testcase-missing-meta-field",
     {TC_REL: TEST_CASE_DOC.replace("| **用例总数** | 1 | ✓ | 用例总数 |\n", ""),
      f"test_cases/{DATE_DIR}/{TOPIC}-key-points.md": KEY_POINTS_DOC},
     ["--root", "."], 1, "元信息缺少必填行"),
    ("testcase-meta-placeholder",
     {TC_REL: TEST_CASE_DOC.replace("| **业务产品** | POS |", "| **业务产品** | {PRODUCT} |"),
      f"test_cases/{DATE_DIR}/{TOPIC}-key-points.md": KEY_POINTS_DOC},
     ["--root", "."], 1, "仍为占位符"),
    ("testcase-illegal-state",
     {TC_REL: TEST_CASE_DOC.replace("| **状态** | Ready |", "| **状态** | Approved |"),
      f"test_cases/{DATE_DIR}/{TOPIC}-key-points.md": KEY_POINTS_DOC},
     ["--root", "."], 1, "状态非合法枚举前缀"),
    ("testcase-missing-overview",
     {TC_REL: TEST_CASE_DOC.replace("## 用例总览", "## 用例一览"),
      f"test_cases/{DATE_DIR}/{TOPIC}-key-points.md": KEY_POINTS_DOC},
     ["--root", "."], 1, "用例总览"),
    ("testcase-ready-missing-key-points",
     {TC_REL: TEST_CASE_DOC}, ["--root", "."], 1, "key-points.md"),
    ("testcase-key-points-missing-section",
     {TC_REL: TEST_CASE_DOC,
      f"test_cases/{DATE_DIR}/{TOPIC}-key-points.md": KEY_POINTS_DOC.replace("## 核心测试点", "## 要点")},
     ["--root", "."], 1, "核心测试点"),

    # --- 阶段感知(--stage 只允许收紧) ---
    ("stage-ready-tightens-draft",
     {PRD_REL: DRAFT_PRD}, ["--root", ".", "--stage", "ready"], 1, "假定阶段校验"),
    ("stage-draft-relaxes-ready",
     {PRD_REL: READY_PRD}, ["--root", ".", "--stage", "draft"], 1, "放宽"),
    ("stage-implemented-tightens-ready",
     {PRD_REL: READY_PRD}, ["--root", ".", "--stage", "implemented"], 0, "假定阶段校验"),
    ("stage-invalid-value",
     {PRD_REL: READY_PRD}, ["--root", ".", "--stage", "bogus"], 2, "--stage 取值非法"),

    # --- CLI 形态 ---
    ("cli-help", {PRD_REL: READY_PRD}, ["--help"], 0, "用法"),
    ("cli-json", {PRD_REL: READY_PRD}, ["--root", ".", "--json"], 0, '"status":"pass"'),
    ("cli-root-missing-value", {PRD_REL: READY_PRD}, ["--root"], 2, "--root 需要参数"),
    ("cli-root-not-exist", {PRD_REL: READY_PRD}, ["--root", "nope"], 2, "根目录不存在"),
    ("cli-unknown-argument", {PRD_REL: READY_PRD}, ["--root", ".", "--nope"], 2, "未知参数"),
    ("cli-two-targets", {PRD_REL: READY_PRD}, ["--root", ".", PRD_REL, PRD_REL], 2, "只接受一个 TARGET"),
    ("cli-target-missing", {PRD_REL: READY_PRD}, ["--root", ".", "prd/2026-11-22/nope.md"], 2, "TARGET 不存在"),
    ("cli-target-single-file", {PRD_REL: READY_PRD}, ["--root", ".", PRD_REL], 0, "字段校验通过"),
    ("cli-target-layer-root", {PRD_REL: READY_PRD}, ["--root", ".", "prd"], 2, "层根目录不能作为单文件校验目标"),
    ("cli-target-unknown-type",
     {"other/x.md": "# x\n"}, ["--root", ".", "other/x.md"], 2, "无法识别的文件类型"),
    ("cli-target-tech-design-dir", _td_v4(), ["--root", ".", TD_REL], 0, "字段校验通过"),

    # --- 空仓 ---
    ("repo-without-artifacts", {}, ["--root", "."], 1, "没有任何规格产物"),

    # --- CRLF 输入 ---
    # bash 原件经 MSYS awk 以文本模式读取,行尾 CR 被吃掉;端口必须等价。
    ("prd-ready-crlf",
     {PRD_REL: READY_PRD.replace("\n", "\r\n")}, ["--root", "."], 0, None),
    ("prd-crlf-invalid-state-subject",
     {PRD_REL: READY_PRD.replace("\n", "\r\n").replace(
         "> **状态主体**: agent:sddctl", "> **状态主体**: bot:sddctl")},
     ["--root", "."], 1, "状态主体非法"),

    # 行尾 2 个 CR:MSYS awk 文本模式最多去掉 2 个行尾 CR(C 运行时 1 个 + awk 1 个)。
    ("prd-ready-crcrlf",
     {PRD_REL: READY_PRD.replace("\n", "\r\r\n")}, ["--root", "."], 0, None),
    ("prd-crcrlf-invalid-state-subject",
     {PRD_REL: READY_PRD.replace("\n", "\r\r\n").replace(
         "> **状态主体**: agent:sddctl", "> **状态主体**: bot:sddctl")},
     ["--root", "."], 1, "状态主体非法"),
]


def _stage_repo(root: Path, files: dict[str, str]) -> None:
    """把语料文件写进临时仓(其余门禁脚本也一并落位, 与 Lead 差分器同构)。"""
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="")
    scripts = root / "scripts"
    if not scripts.exists():
        shutil.copytree(SCRIPTS_DIR, scripts, ignore=shutil.ignore_patterns("tests", "__pycache__"))


def _run(cmd: list[str], cwd: Path) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def _run_bash(root: Path, args: list[str]) -> tuple[int, bytes, bytes]:
    assert BASH is not None
    return _run([BASH, "scripts/check-md-schema.sh", *args], root)


def _run_python(root: Path, args: list[str]) -> tuple[int, bytes, bytes]:
    # 与 bash 侧同口径: 用**相对 root 的路径**调用(错误前缀取 as-invoked 形态)。
    return _run([sys.executable, "scripts/check-md-schema.py", *args], root)


def _collect() -> dict:
    """现场跑 bash 原件采集 golden(不信任任何手写输出)。"""
    assert BASH is not None, "采集 golden 需要 bash"
    cases = []
    for name, files, args, _rc, _fragment in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir(parents=True, exist_ok=True)
            _stage_repo(root, files)
            rc, out, err = _run_bash(root, args)
            posix_root = _posix_root(root)
            canonical = canon(out, root, posix_root).decode("utf-8")
            canonical_err = canon(err, root, posix_root).decode("utf-8")
        cases.append({
            "name": name,
            "files": files,
            "args": args,
            "expect_exit": rc,
            "expect_stdout": canonical,
            "expect_stderr": canonical_err,
        })
    return {
        "gate": "scripts/check-md-schema.py",
        "source_gate": "scripts/check-md-schema.sh",
        "source_sha1": hashlib.sha1(BASH_GATE.read_bytes()).hexdigest(),
        "cases": cases,
    }


class PortEquivalenceTest(unittest.TestCase):
    """corpus golden / 行为等价 / 每条规则都能失败。

    注意:依赖 bash 原件的三个用例各自带守卫(原件在 R-4 集成阶段会被删除),
    而依赖 corpus golden 的用例在原件删除后仍必须执行 —— corpus 是唯一行为真源。
    """

    @classmethod
    def setUpClass(cls) -> None:
        if not CORPUS_PATH.exists():
            raise unittest.SkipTest(f"corpus 缺失: {CORPUS_PATH}(先跑 --collect 采集)")
        cls.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        cls.by_name = {case["name"]: case for case in cls.corpus["cases"]}

    def test_corpus_covers_every_case(self) -> None:
        """corpus 与语料表一一对应(漏采集 = 静默少覆盖, 必须红)。"""
        self.assertEqual(
            sorted(self.by_name), sorted(case[0] for case in CASES),
            "corpus 的用例集与语料表不一致(重新采集 golden)",
        )

    @unittest.skipUnless(BASH_GATE.exists(), "bash 原件已删除(R-4 集成阶段): 本用例需要原件指纹")
    def test_source_sha1_matches_current_bash_gate(self) -> None:
        """golden 记录的原件指纹必须与当前 bash 原件一致(防止原件漂移、golden 没更新)。"""
        self.assertEqual(
            self.corpus.get("source_sha1"),
            hashlib.sha1(BASH_GATE.read_bytes()).hexdigest(),
            "bash 原件已变更, golden 需要重新采集(--collect)",
        )

    @unittest.skipIf(BASH is None, "找不到可用的 bash(设置 SSDCTL_BASH 或安装 Git Bash)")
    @unittest.skipUnless(BASH_GATE.exists(), "bash 原件已删除(R-4 集成阶段): 本用例需要原件在场")
    def test_bash_original_reproduces_golden(self) -> None:
        """bash 原件现场重跑 ⇒ 复现已存 golden(golden 没被手改)。"""
        for case in self.corpus["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "repo"
                    root.mkdir(parents=True, exist_ok=True)
                    _stage_repo(root, case["files"])
                    rc, out, err = _run_bash(root, case["args"])
                    posix_root = _posix_root(root)
                    canonical = canon(out, root, posix_root).decode("utf-8")
                    canonical_err = canon(err, root, posix_root).decode("utf-8")
                self.assertEqual(rc, case["expect_exit"], "退出码与 golden 不符")
                self.assertEqual(canonical, case["expect_stdout"], "stdout 与 golden 不符")
                self.assertEqual(canonical_err, case.get("expect_stderr", ""), "stderr 与 golden 不符")

    def test_python_port_matches_golden(self) -> None:
        """Python 端口 ⇒ 与 golden 相同的退出码与 stdout/stderr(行为等价)。"""
        for case in self.corpus["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "repo"
                    root.mkdir(parents=True, exist_ok=True)
                    _stage_repo(root, case["files"])
                    rc, out, err = _run_python(root, case["args"])
                    posix_root = _posix_root(root)
                    canonical = canon(out, root, posix_root).decode("utf-8")
                    canonical_err = canon(err, root, posix_root).decode("utf-8")
                self.assertEqual(rc, case["expect_exit"], "退出码与 golden 不符")
                self.assertEqual(canonical, case["expect_stdout"], "stdout 与 golden 不符")
                self.assertEqual(canonical_err, case.get("expect_stderr", ""), "stderr 与 golden 不符")

    @unittest.skipIf(BASH is None, "找不到可用的 bash(设置 SSDCTL_BASH 或安装 Git Bash)")
    @unittest.skipUnless(BASH_GATE.exists(), "bash 原件已删除(R-4 集成阶段): 本用例需要原件在场")
    def test_python_and_bash_are_byte_identical(self) -> None:
        """两侧 stdout 与 stderr 归一化后逐字节相同。"""
        for case in self.corpus["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "repo"
                    root.mkdir(parents=True, exist_ok=True)
                    _stage_repo(root, case["files"])
                    posix_root = _posix_root(root)
                    rc_b, out_b, err_b = _run_bash(root, case["args"])
                    rc_p, out_p, err_p = _run_python(root, case["args"])
                    self.assertEqual(rc_b, rc_p, "退出码不同")
                    self.assertEqual(
                        canon(out_b, root, posix_root), canon(out_p, root, posix_root),
                        "stdout 不同",
                    )
                    self.assertEqual(
                        canon(err_b, root, posix_root), canon(err_p, root, posix_root),
                        "stderr 不同",
                    )

    def test_every_rule_has_a_positive_and_a_negative_case(self) -> None:
        """手写期望: 语料真的覆盖了「通过」与「违规」两侧, 且点名了对应规则。"""
        for name, _files, _args, want_rc, fragment in CASES:
            with self.subTest(case=name):
                case = self.by_name[name]
                self.assertEqual(case["expect_exit"], want_rc, "退出码与手写期望不符")
                stdout = case["expect_stdout"]
                stderr = case.get("expect_stderr", "")
                if want_rc == 0:
                    self.assertNotIn("✗", stdout, "期望通过的用例里出现了违规行")
                elif want_rc == 1:
                    self.assertIn("✗", stdout, "期望违规的用例里没有违规行")
                else:
                    # exit 2 = 用法/环境错误: 信息只走 stderr(与 bash 原件同口径)
                    self.assertNotIn("✗", stdout, "用法错误不应出现在 stdout")
                    self.assertNotEqual(stderr, "", "exit=2 的用例 stderr 不应为空")
                if fragment:
                    self.assertIn(fragment, stdout + stderr, "输出没有点名这条规则")

    def test_mutation_breaks_the_matching_negative_case(self) -> None:
        """变异自证: 改坏判定常量 ⇒ 对应反例的输出必须改变(还原后转绿)。

        第三个元素表示「该变异是否应当改变退出码」:
          - Deprecated criteria 守卫: 该反例的唯一违规 ⇒ 退出码 1 → 0
          - 状态枚举: 该反例还有别的违规 ⇒ 退出码不变, 但输出必须多出一条状态值非法
        """
        mutations = [
            (
                "state-enum",
                "STATE_RE = re.compile(r'^(Draft|Ready|Implemented|Deprecated)')",
                "STATE_RE = re.compile(r'^(Draft|Ready)')",
                False,
            ),
            (
                "deprecated-basis-guard",
                "if stage == 'Deprecated' and previous_prefix == 'criteria':",
                "if False and stage == 'Deprecated' and previous_prefix == 'criteria':",
                True,
            ),
        ]
        target = "prd-deprecated-basis-criteria"
        case = self.by_name[target]
        for label, old, new, expect_exit_change in mutations:
            with self.subTest(mutation=label):
                source = PY_GATE.read_text(encoding="utf-8")
                self.assertIn(old, source, f"变异点不存在: {label}")
                mutated = source.replace(old, new)
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "repo"
                    root.mkdir(parents=True, exist_ok=True)
                    _stage_repo(root, case["files"])
                    # 变异体只落在临时仓里(仓内原件不动), 调用形态与生产口径一致(相对路径)
                    mutant = root / "scripts" / "check-md-schema.py"
                    mutant.write_text(mutated, encoding="utf-8", newline="")
                    rc, out, _err = _run([sys.executable, "scripts/check-md-schema.py", *case["args"]], root)
                    canonical = canon(out, root, _posix_root(root)).decode("utf-8")
                self.assertNotEqual(
                    canonical, case["expect_stdout"],
                    f"变异 {label} 没有改变该反例的输出 —— 这条规则可能没被真正检查",
                )
                if expect_exit_change:
                    self.assertNotEqual(rc, case["expect_exit"], f"变异 {label} 没有改变退出码")


def main() -> int:
    if "--collect" in sys.argv[1:]:
        data = _collect()
        CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        CORPUS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"采集完成: {CORPUS_PATH} ({len(data['cases'])} 用例, source_sha1={data['source_sha1']})")
        return 0
    unittest.main()


if __name__ == "__main__":
    sys.exit(main())
