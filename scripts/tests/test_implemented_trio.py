"""F6:PRD / Tech Design / Plan 三件套必须**同时**进入 Implemented。

规则来源:WORKFLOW.md §5「三件套一致性规则」(WORKFLOW.md:259、:262-267)——
PRD / Tech Design / Plan 三个状态必须同时进入 `Implemented`,不允许单层先 `Implemented`。
这条规则此前只有散文,没有任何机器覆盖:散文漂移不会被 CI 发现。
本文件把它变成 `ssdctl advance --to Implemented` 里的可判定检查。

反证目标(每条都能失败):
1. 三件套齐备且都已 Ready ⇒ 一次 advance 把三件套一起转 Implemented,每个制品各自留一条证据;
2. 同 topic 的兄弟仍在 Draft ⇒ advance 失败(退出码非零)、目标文件字节不变;
3. 只有 PRD 一个制品 ⇒ 单独 advance 该 PRD 仍成功(缺失的层不是阻塞项);
4. 失败路径不落任何证据文件(Deprecated 兄弟同样 fail-closed);
5. 兄弟已经是 Implemented ⇒ 不动它,也不阻塞本次推进。
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from _support import make_repo, read_fixture, run_cli

TOPIC = "trio-demo"
PRD_REL = f"prd/2026-11-22/{TOPIC}.md"
TD_REL = f"tech_design/2026-11-22-{TOPIC}/README.md"
# 制品的 rel 是**目录**(discover_artifacts 对 td 层取目录),证据与提示都用它
TD_ARTIFACT_REL = f"tech_design/2026-11-22-{TOPIC}"
PLAN_REL = f"plan/2026-11-22-{TOPIC}/{TOPIC}.md"
DECISION_REL = f"control/decisions/2026-11-22-{TOPIC}.md"

TRIO_FIXTURES = {
    PRD_REL: "trio-prd.md",
    TD_REL: "trio-td-readme.md",
    PLAN_REL: "trio-plan.md",
}

# 制品 rel → 承载状态块的文件(td 层的 rel 是**目录**,状态块在它的 README.md 里)
ARTIFACT_FILES = {
    PRD_REL: PRD_REL,
    TD_ARTIFACT_REL: TD_REL,
    PLAN_REL: PLAN_REL,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trio_files(**overrides: str) -> dict[str, str]:
    """三件套夹具的**内容**(rel → 文本);overrides 用 rel → 文本 覆盖。"""
    files = {rel: read_fixture(name) for rel, name in TRIO_FIXTURES.items()}
    files.update(overrides)
    return files


def decision_text() -> str:
    """人手写的决定记录:提供「外部事实」依据与人工署名。"""
    return "\n".join(
        [
            "# 人工介入记录 · trio-demo",
            "",
            "> **决定 ID**: D1",
            "> **时间**: 2026-11-22T23:40:00+08:00",
            "> **操作人**: bob",
            f"> **目标制品**: {PRD_REL}",
            "> **动作**: approve",
            "> **范围**: all",
            "> **外部事实**: pr-123",
            "> **理由**: 外部 PR #123 已合并",
            "",
            "| ID | 决定 | 理由 |",
            "|----|------|------|",
            "| all | approve | 外部 PR #123 已合并 |",
            "",
        ]
    )


def set_state(text: str, state: str, basis: str | None = None) -> str:
    """改夹具的状态行(可选一并改状态依据),其余内容不动。"""
    lines: list[str] = []
    for line in text.split("\n"):
        if line.startswith("> **状态**:"):
            line = f"> **状态**: {state}"
        elif basis is not None and line.startswith("> **状态依据**:"):
            line = f"> **状态依据**: {basis}"
        lines.append(line)
    return "\n".join(lines)


class ImplementedTrioTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    # ---------------------------------------------------------------- 工具

    def _repo(self, files: dict[str, str], with_decision: bool = True) -> Path:
        payload = dict(files)
        if with_decision:
            payload[DECISION_REL] = decision_text()
        return make_repo(self.base, payload)

    def _advance(self, repo: Path, rel: str, *extra: str):
        return run_cli(
            repo,
            "advance",
            rel,
            "--to",
            "Implemented",
            "--decision",
            f"{DECISION_REL}#D1",
            *extra,
        )

    def _evidence(self, repo: Path) -> list[dict]:
        records: list[dict] = []
        for path in sorted((repo / "control" / "evidence").rglob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").split("\n"):
                if line.strip():
                    records.append(json.loads(line))
        return records

    def _digests(self, repo: Path, rels) -> dict[str, str]:
        return {rel: sha256(repo / rel) for rel in rels}

    # ---------------------------------------------------------------- 用例

    def test_trio_advances_together_with_one_evidence_each(self) -> None:
        """三件套齐备且都已 Ready ⇒ 一次 advance 把三件套一起转 Implemented。"""
        repo = self._repo(trio_files())

        result = self._advance(repo, PRD_REL)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for rel in (PRD_REL, TD_ARTIFACT_REL, PLAN_REL):
            text = (repo / ARTIFACT_FILES[rel]).read_text(encoding="utf-8")
            self.assertIn("> **状态**: Implemented", text, f"{rel} 必须同时进入 Implemented")
            self.assertIn("external:pr-123", text, f"{rel} 必须带外部事实依据")
        # 不替兄弟编造依据:兄弟的依据里只有 decision: 与 external:,没有 criteria:
        for rel in (TD_ARTIFACT_REL, PLAN_REL):
            basis = [
                line
                for line in (repo / ARTIFACT_FILES[rel]).read_text(encoding="utf-8").split("\n")
                if line.startswith("> **状态依据**:")
            ]
            self.assertEqual(len(basis), 1, rel)
            self.assertNotIn("criteria:", basis[0], f"{rel} 的依据里不该出现 criteria:")

        records = self._evidence(repo)
        by_artifact: dict[str, list[dict]] = {}
        for record in records:
            by_artifact.setdefault(str(record.get("artifact")), []).append(record)
        for rel in (PRD_REL, TD_ARTIFACT_REL, PLAN_REL):
            self.assertIn(rel, by_artifact, f"{rel} 必须各自留一条证据")
            self.assertEqual(len(by_artifact[rel]), 1, f"{rel} 的证据必须恰好一条")
            self.assertEqual(by_artifact[rel][0]["to"], "Implemented")

    def test_draft_sibling_blocks_the_advance(self) -> None:
        """同 topic 的兄弟仍在 Draft ⇒ advance 失败,目标文件字节级不变。"""
        files = trio_files(**{TD_REL: set_state(read_fixture("trio-td-readme.md"), "Draft")})
        repo = self._repo(files)
        before = self._digests(repo, TRIO_FIXTURES)

        result = self._advance(repo, PRD_REL)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("三件套未同时就绪", result.stderr)
        self.assertIn(TD_ARTIFACT_REL, result.stderr)
        self.assertIn("Draft", result.stderr)
        for rel, digest in before.items():
            self.assertEqual(sha256(repo / rel), digest, f"{rel} 必须字节级不变")

    def test_single_artifact_can_advance_alone(self) -> None:
        """只有 PRD 一个制品 ⇒ 单独 advance 该 PRD 仍成功(缺失的层不是阻塞项)。"""
        repo = self._repo({PRD_REL: read_fixture("trio-prd.md")})

        result = self._advance(repo, PRD_REL)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = (repo / PRD_REL).read_text(encoding="utf-8")
        self.assertIn("> **状态**: Implemented", text)
        records = self._evidence(repo)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["artifact"], PRD_REL)

    def test_failed_advance_writes_no_evidence(self) -> None:
        """失败路径不落任何证据文件;Deprecated 兄弟同样 fail-closed。"""
        files = trio_files(
            **{
                PLAN_REL: set_state(
                    read_fixture("trio-plan.md"), "Deprecated", basis="external:pr-123"
                )
            }
        )
        repo = self._repo(files)
        before = self._digests(repo, TRIO_FIXTURES)

        result = self._advance(repo, PRD_REL)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("三件套未同时就绪", result.stderr)
        self.assertIn("Deprecated", result.stderr)
        for rel, digest in before.items():
            self.assertEqual(sha256(repo / rel), digest, f"{rel} 必须字节级不变")
        self.assertEqual(self._evidence(repo), [], "失败路径不落任何证据文件")

    def test_implemented_sibling_is_left_alone(self) -> None:
        """兄弟已经是 Implemented ⇒ 不重写它,也不阻塞本次推进。"""
        files = trio_files(
            **{
                TD_REL: set_state(
                    read_fixture("trio-td-readme.md"), "Implemented", basis="external:pr-99"
                )
            }
        )
        repo = self._repo(files)
        td_before = sha256(repo / TD_REL)

        result = self._advance(repo, PRD_REL)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sha256(repo / TD_REL), td_before, "已是 Implemented 的兄弟不应被重写")
        self.assertIn("> **状态**: Implemented", (repo / PRD_REL).read_text(encoding="utf-8"))
        self.assertIn("> **状态**: Implemented", (repo / PLAN_REL).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
