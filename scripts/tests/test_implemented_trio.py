"""F6:PRD / Tech Design / Plan 三件套必须**同时**进入 Implemented。

规则来源:WORKFLOW.md §5「三件套一致性规则」(WORKFLOW.md:259、:262-267)——
PRD / Tech Design / Plan 三个状态必须同时进入 `Implemented`,不允许单层先 `Implemented`。
这条规则此前只有散文,没有任何机器覆盖:散文漂移不会被 CI 发现。
本文件把它变成 `ssdctl advance --to Implemented` 里的可判定检查。

**F9 之后的形态**(本文件的写域 `scripts/tests/**`,与 F9 单载体裁决同步):
- 授权来源只剩 `criteria:`(判据全绿)与 `external:`(外部事实)—— `decision:` 已删除(R-4);
- 外部事实依据用 `--external <ref>` 提供(R-7);旧的「决定记录 + 证据链」通道已整体删除(R-1/R-2/R-5),
  所以「留痕」= 制品的状态块 + 复审块 + git 历史,**不再有 `control/evidence/**.jsonl`**;
- 断言从「每个制品一条证据文件」改成「每个制品的状态块/复审块被写对 + 控制平面不存在」。

反证目标(每条都能失败):
1. 三件套齐备且都已 Ready ⇒ 一次 advance 把三件套一起转 Implemented,每个制品各自带 `external:` 依据;
2. 同 topic 的兄弟仍在 Draft ⇒ advance 失败(退出码非零)、三个文件字节级不变;
3. 只有 PRD 一个制品 ⇒ 单独 advance 该 PRD 仍成功(缺失的层不是阻塞项);
4. 失败路径不留下任何控制平面文件(Deprecated 兄弟同样 fail-closed);
5. 兄弟已经是 Implemented ⇒ 不动它,也不阻塞本次推进。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import control_files, make_repo, read_fixture, run_cli, sha256_of

TOPIC = "trio-demo"
PRD_REL = f"prd/2026-11-22/{TOPIC}.md"
TD_REL = f"tech_design/2026-11-22-{TOPIC}/README.md"
# 制品的 rel 是**目录**(discover_artifacts 对 td 层取目录),提示与断言都用它
TD_ARTIFACT_REL = f"tech_design/2026-11-22-{TOPIC}"
PLAN_REL = f"plan/2026-11-22-{TOPIC}/{TOPIC}.md"
EXTERNAL_REF = "pr-123"

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


def trio_files(**overrides: str) -> dict[str, str]:
    """三件套夹具的**内容**(rel → 文本);overrides 用 rel → 文本 覆盖。"""
    files = {rel: read_fixture(name) for rel, name in TRIO_FIXTURES.items()}
    files.update(overrides)
    return files


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


def basis_of(text: str) -> str:
    """取状态块里的状态依据(整行值)。"""
    for line in text.split("\n"):
        if line.startswith("> **状态依据**:"):
            return line.split(":", 1)[1].strip()
    return ""


class ImplementedTrioTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    # ---------------------------------------------------------------- 工具

    def _repo(self, files: dict[str, str]) -> Path:
        return make_repo(self.base, files)

    def _advance(self, repo: Path, rel: str, *extra: str):
        return run_cli(
            repo,
            "advance",
            rel,
            "--to",
            "Implemented",
            "--external",
            EXTERNAL_REF,
            *extra,
        )

    def _digests(self, repo: Path, rels) -> dict[str, str]:
        return {rel: sha256_of(repo / rel) for rel in rels}

    # ---------------------------------------------------------------- 用例

    def test_trio_advances_together_with_external_basis(self) -> None:
        """三件套齐备且都已 Ready ⇒ 一次 advance 把三件套一起转 Implemented。

        F9:留痕 = 制品状态块 + 复审块 + git 历史 ⇒ 断言落在**制品文件**上,
        并且控制平面必须不存在(旧模型下这里有一堆 `control/evidence/*.jsonl`)。
        """
        repo = self._repo(trio_files())

        result = self._advance(repo, PRD_REL)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for rel in (PRD_REL, TD_ARTIFACT_REL, PLAN_REL):
            text = (repo / ARTIFACT_FILES[rel]).read_text(encoding="utf-8")
            self.assertIn("> **状态**: Implemented", text, f"{rel} 必须同时进入 Implemented")
            self.assertIn(f"external:{EXTERNAL_REF}", text, f"{rel} 必须带外部事实依据")
        # 不替兄弟编造依据:兄弟的依据里只有 external:,没有 criteria:
        for rel in (TD_ARTIFACT_REL, PLAN_REL):
            basis = basis_of((repo / ARTIFACT_FILES[rel]).read_text(encoding="utf-8"))
            self.assertNotIn("criteria:", basis, f"{rel} 的依据里不该出现 criteria:")
            self.assertEqual(basis, f"external:{EXTERNAL_REF}", rel)
        # F9:控制平面不存在
        self.assertEqual(control_files(repo), [], "advance 不得写控制平面")
        self.assertFalse((repo / "control").exists())

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
            self.assertEqual(sha256_of(repo / rel), digest, f"{rel} 必须字节级不变")

    def test_single_artifact_can_advance_alone(self) -> None:
        """只有 PRD 一个制品 ⇒ 单独 advance 该 PRD 仍成功(缺失的层不是阻塞项)。"""
        repo = self._repo({PRD_REL: read_fixture("trio-prd.md")})

        result = self._advance(repo, PRD_REL)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = (repo / PRD_REL).read_text(encoding="utf-8")
        self.assertIn("> **状态**: Implemented", text)
        self.assertIn(f"external:{EXTERNAL_REF}", basis_of(text))
        self.assertEqual(control_files(repo), [], "advance 不得写控制平面")

    def test_failed_advance_writes_no_control_plane(self) -> None:
        """失败路径不落任何控制平面文件;Deprecated 兄弟同样 fail-closed。"""
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
            self.assertEqual(sha256_of(repo / rel), digest, f"{rel} 必须字节级不变")
        self.assertEqual(control_files(repo), [], "失败路径不落任何控制平面文件")

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
        td_before = sha256_of(repo / TD_REL)

        result = self._advance(repo, PRD_REL)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sha256_of(repo / TD_REL), td_before, "已是 Implemented 的兄弟不应被重写")
        self.assertIn("> **状态**: Implemented", (repo / PRD_REL).read_text(encoding="utf-8"))
        self.assertIn("> **状态**: Implemented", (repo / PLAN_REL).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
