"""调度谓词(契约 §7)的判定测试 —— 证明谓词**能失败**。

每个用例都给出「应该可派发」与「应该不可派发」两半,避免出现
「谓词恒为真」的假绿(A-8 的要求)。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import make_repo, run_cli, write_text

from lib.artifacts import discover_artifacts
from lib.dispatch import (
    PERMISSION_BLOCKED,
    PERMISSION_COMMITTABLE,
    PERMISSION_DRAFTABLE,
    evaluate_dispatch,
)

DATE = "2026-01-02"
TOPIC = "demo"


def _status_line(state: str) -> str:
    return (
        f"> **状态**: {state}\n"
        "> **状态主体**: agent:sddctl\n"
        "> **状态时间**: 2026-01-02T10:00:00+08:00\n"
        "> **状态依据**: criteria:PRD-SECTIONS\n"
    )


def _prd(state: str) -> str:
    return (
        "# PRD: 示例\n\n"
        + _status_line(state)
        + "\n## 为什么 (Why)\n\n因为。\n\n"
        "## 目标 (Goal)\n\n- [ ] AC-1 目标一\n\n"
        "## 场景 (Scenarios)\n\n### 场景: S-1 场景一\n\n"
        "**Given** 前提\n\n**When** 动作\n\n**Then** 结果\n\n"
        "**覆盖**: AC-1\n\n"
        "## 不在范围内 (Out of Scope)\n\n- 无\n\n"
        "## 复审 (Review)\n\n"
        "> **评审人**: agent:sddctl\n"
        "> **评审日期**: 2026-01-02\n"
        "> **评审结论**: 通过\n"
        "> **评审方式**: 自动判据\n"
    )


def _td() -> str:
    return (
        "# Tech Design: 示例\n\n"
        + _status_line("Draft")
        + "\n## 门禁清单 (Completion Gate)\n\n- TODO\n\n"
        "## 变更记录 (Change Log)\n\n- 2026-01-02 初稿\n\n"
        "## 复审 (Review)\n\n"
        "> **评审人**: agent:sddctl\n"
        "> **评审日期**: 2026-01-02\n"
        "> **评审结论**: 通过\n"
        "> **评审方式**: 自动判据\n"
    )


class DispatchPredicateTests(unittest.TestCase):
    """谓词的两半:上游就绪 ⇒ 可派发;上游未就绪/缺失 ⇒ 不可派发。"""

    def _dispatch(self, repo: Path, rel: str):
        artifacts = discover_artifacts(repo)
        for artifact in artifacts:
            if artifact.rel == rel:
                return evaluate_dispatch(repo, artifact, artifacts)
        raise AssertionError(f"未发现制品 {rel}; 实际有 {[a.rel for a in artifacts]}")

    def test_downstream_is_blocked_when_upstream_is_draft(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            repo = make_repo(
                Path(base),
                {
                    f"prd/{DATE}/{TOPIC}.md": _prd("Draft"),
                    f"tech_design/{DATE}-{TOPIC}/README.md": _td(),
                },
            )
            result = self._dispatch(repo, f"tech_design/{DATE}-{TOPIC}")
            self.assertFalse(result.dispatchable, "上游是 Draft 时下游不得可派发")
            self.assertEqual(result.dependency_permission, PERMISSION_DRAFTABLE)
            self.assertTrue(result.missing, "不可派发时 missing 必须列出缺什么")
            self.assertIn("Draft", " ".join(result.missing))
            self.assertEqual(result.upstream_states, ["Draft"])

    def test_downstream_is_dispatchable_when_upstream_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            repo = make_repo(
                Path(base),
                {
                    f"prd/{DATE}/{TOPIC}.md": _prd("Ready"),
                    f"tech_design/{DATE}-{TOPIC}/README.md": _td(),
                },
            )
            result = self._dispatch(repo, f"tech_design/{DATE}-{TOPIC}")
            self.assertTrue(result.dispatchable, "上游 Ready 时下游必须可派发")
            self.assertEqual(result.dependency_permission, PERMISSION_COMMITTABLE)
            self.assertEqual(result.missing, [])
            self.assertEqual(result.upstream_states, ["Ready"])

    def test_missing_upstream_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            repo = make_repo(Path(base), {f"tech_design/{DATE}-{TOPIC}/README.md": _td()})
            result = self._dispatch(repo, f"tech_design/{DATE}-{TOPIC}")
            self.assertFalse(result.dispatchable)
            self.assertEqual(result.dependency_permission, PERMISSION_BLOCKED)
            self.assertTrue(result.missing, "上游缺失必须进入 missing")

    def test_deprecated_artifact_is_not_dispatchable(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            repo = make_repo(Path(base), {f"prd/{DATE}/{TOPIC}.md": _prd("Deprecated")})
            result = self._dispatch(repo, f"prd/{DATE}/{TOPIC}.md")
            self.assertFalse(result.dispatchable, "Deprecated 不得可派发")
            self.assertTrue(result.missing)
            self.assertIn("Deprecated", " ".join(result.missing))

    def test_scan_json_reports_the_gap(self) -> None:
        """CLI 层: `scan --json` 必须把下游的缺口原样吐出来(契约 §5.3 / A-8)。"""
        with tempfile.TemporaryDirectory() as base:
            repo = make_repo(
                Path(base),
                {
                    f"prd/{DATE}/{TOPIC}.md": _prd("Draft"),
                    f"tech_design/{DATE}-{TOPIC}/README.md": _td(),
                },
            )
            done = run_cli(repo, "scan", "--json")
            self.assertEqual(done.returncode, 0, done.stderr)
            payload = json.loads(done.stdout)
            entries = {item["path"]: item for item in payload["artifacts"]}
            td = entries[f"tech_design/{DATE}-{TOPIC}"]
            self.assertFalse(td["dispatchable"])
            self.assertTrue(td["missing"], "scan --json 的 missing 必须非空")
            self.assertEqual(td["upstream_states"], ["Draft"])
            self.assertEqual(td["dependency_permission"], PERMISSION_DRAFTABLE)
            prd = entries[f"prd/{DATE}/{TOPIC}.md"]
            self.assertTrue(prd["dispatchable"], "PRD 无上游,应当可派发")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
