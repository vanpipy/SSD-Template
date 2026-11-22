"""`scripts/check-md-schema.sh` 的反证测试: 契约里每条规则都必须**能失败**。

形态(Lead 的验收要求): 搭一个临时仓 → 改掉制品的一行 → 跑门禁 →
断言**退出码 1** 且输出**点名该条规则**。断言写在测试里, 所以规则一旦
从门禁里被删掉(或退化成恒真), 这个测试就会红 —— 门禁不会「悄悄放过」。

运行: `python -m unittest discover -s scripts/tests -t scripts/tests`
(需要 bash: Windows 上优先用 Git Bash, POSIX 上用 PATH 里的 bash;
可用环境变量 `SSDCTL_BASH` 指定解释器。)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR, write_text  # noqa: F401  (把 scripts/ 放进 sys.path)

GATE = SCRIPTS_DIR / "check-md-schema.sh"
DATE_DIR = "2026-11-22"
TOPIC = "demo-feature"


def _bash() -> str | None:
    """找一个能跑本仓 shell 门禁的 bash。

    Windows 上 PATH 里的 `bash` 可能是 WSL 转发(不接受 Windows 路径),
    所以先找 Git Bash; 找不到就返回 None(测试 skip, 而不是假装通过)。
    """
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

# 一份**合规**的 Ready PRD: 状态块 4 行 + 复审块 4 行都填满。
READY_PRD = """# PRD: demo-feature

> **状态**: Ready
> **状态主体**: agent:sddctl
> **状态时间**: 2026-11-22T23:30:00+08:00
> **状态依据**: criteria:PRD-READY-01

## 为什么 (Why)

- 门禁必须能识别违规制品。

## 目标 (Goal)

- [ ] AC-1 门禁能识别缺字段的 Ready 制品

## 场景 (Scenarios)

### 场景 1

**Given** 某个 Ready 制品
**When** 跑字段门禁
**Then** 退出码为 1

## 不在范围内 (Out of Scope)

- 不做界面。

## 复审 (Review)

> **评审人**: agent:sddctl
> **评审日期**: 2026-11-22
> **评审结论**: 通过
> **评审方式**: 自动判据

## 变更记录 (Change Log)

- 2026-11-22 初版。
"""

# Draft 制品: 后三行可缺省(契约 §3.1), 复审块可留空 —— 门禁不得误伤。
DRAFT_PRD = """# PRD: demo-feature

> **状态**: Draft

## 为什么 (Why)

- 门禁必须能识别违规制品。

## 目标 (Goal)

- [ ] AC-1 门禁能识别缺字段的 Ready 制品

## 场景 (Scenarios)

### 场景 1

**Given** 某个 Ready 制品
**When** 跑字段门禁
**Then** 退出码为 1

## 不在范围内 (Out of Scope)

- 不做界面。

## 复审 (Review)

> **评审人**:
> **评审日期**:
> **评审结论**:
> **评审方式**:

## 变更记录 (Change Log)

- 2026-11-22 初版。
"""


def _run_gate(text: str) -> tuple[int, str]:
    """在临时仓里跑字段门禁, 返回 (退出码, 输出)。"""
    assert BASH is not None
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(GATE, repo / "scripts" / "check-md-schema.sh")
        write_text(repo / "prd" / DATE_DIR / f"{TOPIC}.md", text)
        proc = subprocess.run(
            [BASH, "scripts/check-md-schema.sh", "--root", "."],
            cwd=str(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    return proc.returncode, proc.stdout + proc.stderr


@unittest.skipIf(BASH is None, "找不到可用的 bash(设置 SSDCTL_BASH 或安装 Git Bash)")
class FieldGateRulesTest(unittest.TestCase):
    """每条规则一个用例: 期望退出码 + 期望输出片段。"""

    def assertGate(self, text: str, want_rc: int, want_text: str | None = None) -> None:
        rc, out = _run_gate(text)
        self.assertEqual(
            rc,
            want_rc,
            f"退出码不符(期望 {want_rc}, 实得 {rc})\n--- 输出 ---\n{out}",
        )
        if want_text is not None:
            self.assertIn(
                want_text,
                out,
                f"输出没有点名这条规则(期望包含 {want_text!r})\n--- 输出 ---\n{out}",
            )

    # --- 正例: 不得误伤 ---

    def test_ready_artifact_passes(self) -> None:
        """合规的 Ready 制品全绿。"""
        self.assertGate(READY_PRD, 0)

    def test_draft_may_omit_optional_rows(self) -> None:
        """Draft 态缺状态三行 / 复审四行都合法(契约 §3.1、§3.2)。"""
        self.assertGate(DRAFT_PRD, 0)

    def test_multiple_criteria_ids_share_one_prefix(self) -> None:
        """`criteria:<id>[,<id>…]` 是规范形态(与判据正则一致), 不得判非法。"""
        text = READY_PRD.replace(
            "criteria:PRD-READY-01", "criteria:PRD-READY-01,PRD-READY-02"
        )
        self.assertGate(text, 0)

    def test_mixed_basis_prefixes_pass(self) -> None:
        """criteria / decision / external 混排合法。"""
        text = READY_PRD.replace(
            "criteria:PRD-READY-01",
            "criteria:PRD-READY-01,decision:control/decisions/d1.md#D1",
        )
        self.assertGate(text, 0)

    # --- 反证: 每条规则都要能失败 ---

    def test_ready_missing_state_subject_fails(self) -> None:
        """状态 ≥ Ready 时缺 `状态主体` ⇒ 违规。"""
        text = READY_PRD.replace("> **状态主体**: agent:sddctl\n", "")
        self.assertGate(text, 1, "状态主体")

    def test_ready_missing_state_time_fails(self) -> None:
        """状态 ≥ Ready 时缺 `状态时间` ⇒ 违规。"""
        text = READY_PRD.replace("> **状态时间**: 2026-11-22T23:30:00+08:00\n", "")
        self.assertGate(text, 1, "状态时间")

    def test_ready_missing_state_basis_fails(self) -> None:
        """状态 ≥ Ready 时缺 `状态依据` ⇒ 违规。"""
        text = READY_PRD.replace("> **状态依据**: criteria:PRD-READY-01\n", "")
        self.assertGate(text, 1, "状态依据")

    def test_state_time_without_timezone_fails(self) -> None:
        """状态时间必须是带时区的 ISO-8601。"""
        text = READY_PRD.replace("2026-11-22T23:30:00+08:00", "2026-11-22 23:30:00")
        self.assertGate(text, 1, "ISO-8601")

    def test_state_basis_without_known_prefix_fails(self) -> None:
        """状态依据每项必须带 criteria:/decision:/external: 前缀。"""
        text = READY_PRD.replace("criteria:PRD-READY-01", "我觉得可以")
        self.assertGate(text, 1, "状态依据项非法")

    def test_state_basis_garbage_after_criteria_fails(self) -> None:
        """criteria 组后面跟一个无前缀的垃圾项 ⇒ 违规(不是「延续 id」)。"""
        text = READY_PRD.replace("criteria:PRD-READY-01", "criteria:PRD-READY-01,我可以")
        self.assertGate(text, 1, "状态依据项非法")

    def test_ready_missing_reviewer_fails(self) -> None:
        """状态 ≥ Ready 时缺 `评审人` ⇒ 违规。"""
        text = READY_PRD.replace("> **评审人**: agent:sddctl\n", "")
        self.assertGate(text, 1, "评审人")

    def test_review_date_must_be_iso_date_fails(self) -> None:
        """评审日期必须是 YYYY-MM-DD。"""
        text = READY_PRD.replace("> **评审日期**: 2026-11-22", "> **评审日期**: 22/11/2026")
        self.assertGate(text, 1, "评审日期")

    def test_ready_missing_review_conclusion_fails(self) -> None:
        """状态 ≥ Ready 时缺 `评审结论` ⇒ 违规(不是 warning)。"""
        text = READY_PRD.replace("> **评审结论**: 通过\n", "")
        self.assertGate(text, 1, "评审结论")

    def test_review_conclusion_outside_domain_fails(self) -> None:
        """评审结论取值域 = 通过 / 有条件通过 / 需返工。"""
        text = READY_PRD.replace("> **评审结论**: 通过", "> **评审结论**: 大概可以")
        self.assertGate(text, 1, "评审结论取值非法")

    def test_ready_missing_review_method_fails(self) -> None:
        """状态 ≥ Ready 时缺 `评审方式` ⇒ 违规。"""
        text = READY_PRD.replace("> **评审方式**: 自动判据\n", "")
        self.assertGate(text, 1, "评审方式")

    def test_review_method_outside_domain_fails(self) -> None:
        """评审方式取值域 = 自动判据 / 人工介入 / 外部事实。"""
        text = READY_PRD.replace("> **评审方式**: 自动判据", "> **评审方式**: 随便")
        self.assertGate(text, 1, "评审方式取值非法")

    def test_agent_reviewer_cannot_claim_human_review_fails(self) -> None:
        """评审人是 agent:* 时, 评审方式不得为「人工介入」(INV-3)。"""
        text = READY_PRD.replace("> **评审方式**: 自动判据", "> **评审方式**: 人工介入")
        self.assertGate(text, 1, "人工介入")

    def test_deprecated_basis_may_not_use_criteria_fails(self) -> None:
        """Deprecated 态的状态依据只能是 decision: / external:。"""
        text = READY_PRD.replace("> **状态**: Ready", "> **状态**: Deprecated")
        self.assertGate(text, 1, "Deprecated")


if __name__ == "__main__":
    unittest.main()
