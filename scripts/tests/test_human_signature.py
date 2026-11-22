"""契约 §5.2 规则 5 + §6.1:人工署名的来源约束。

反证目标(每条都能失败):
1. `--actor alice` 且没有 `--decision` ⇒ exit 1 + 目标文件 sha256 零变化 + 证据链零写;
2. `--actor agent:x` 且没有 `--decision` ⇒ 正常路径(判据驱动推进,合法);
3. 有 `--decision` 且其「操作人」是人名 ⇒ 复审块「评审人」= 该人名、「评审方式」= 人工介入;
4. 人手写的决定文件(没有「记录写入者」行)也能被解析并消费 ⇒ 证据链出现 `decision:` 引用。
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from _support import make_repo, read_fixture, run_cli, write_text

ARTIFACT_REL = "prd/2026-11-22/demo-feature.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HumanSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(
            Path(self._tmp.name),
            {ARTIFACT_REL: read_fixture("good-prd.md")},
        )
        self.target = self.repo / ARTIFACT_REL

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _evidence_files(self) -> list[Path]:
        return sorted((self.repo / "control" / "evidence").rglob("*.jsonl"))

    def test_human_actor_without_decision_is_rejected(self) -> None:
        """agent 不能靠 `--actor alice` 把人名写进复审块。"""
        before = sha256(self.target)

        result = run_cli(
            self.repo, "advance", ARTIFACT_REL, "--to", "Ready", "--actor", "alice"
        )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("人工署名必须来自 control/decisions/ 的决定记录", result.stderr)
        self.assertEqual(sha256(self.target), before, "目标文件必须零改动")
        self.assertEqual(self._evidence_files(), [], "证据链也必须零写")

    def test_agent_actor_without_decision_is_allowed(self) -> None:
        """判据驱动推进时评审人就是 agent:<id> —— 这是合法路径,不能被误杀。"""
        result = run_cli(
            self.repo, "advance", ARTIFACT_REL, "--to", "Ready", "--actor", "agent:builder"
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("> **评审人**: agent:builder", text)
        self.assertIn("> **评审方式**: 自动判据", text)

    def test_decision_supplies_the_human_signature(self) -> None:
        """决定记录的「操作人」= 复审块的「评审人」,评审方式 = 人工介入。"""
        decided = run_cli(
            self.repo,
            "decide",
            "--artifact",
            ARTIFACT_REL,
            "--action",
            "approve",
            "--actor",
            "alice",
            "--reason",
            "人工复核通过",
        )
        self.assertEqual(decided.returncode, 0, decided.stdout + decided.stderr)

        decision_file = next((self.repo / "control" / "decisions").glob("*.md"))
        decision_text = decision_file.read_text(encoding="utf-8")
        self.assertIn("> **记录写入者**: agent:ssdctl", decision_text)

        ref = f"{decision_file.relative_to(self.repo).as_posix()}#D1"
        result = run_cli(self.repo, "advance", ARTIFACT_REL, "--to", "Ready", "--decision", ref)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("> **评审人**: alice", text)
        self.assertIn("> **评审方式**: 人工介入", text)
        self.assertIn("decision:", "".join(p.read_text(encoding="utf-8") for p in self._evidence_files()))

    def test_handwritten_decision_without_writer_line_is_accepted(self) -> None:
        """人手工写的决定文件可能没有「记录写入者」行 —— 解析须容忍缺失。"""
        decision_rel = "control/decisions/2026-11-22-demo-feature.md"
        write_text(
            self.repo / decision_rel,
            "\n".join(
                [
                    "# 人工介入记录 · demo-feature",
                    "",
                    "> **决定 ID**: D1",
                    "> **时间**: 2026-11-22T23:40:00+08:00",
                    "> **操作人**: bob",
                    "> **目标制品**: " + ARTIFACT_REL,
                    "> **动作**: approve",
                    "> **范围**: all",
                    "> **理由**: 人工复核通过",
                    "",
                    "| ID | 决定 | 理由 |",
                    "|----|------|------|",
                    "| all | approve | 人工复核通过 |",
                    "",
                ]
            ),
        )

        result = run_cli(
            self.repo, "advance", ARTIFACT_REL, "--to", "Ready", "--decision", f"{decision_rel}#D1"
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("> **评审人**: bob", text)
        self.assertIn("> **评审方式**: 人工介入", text)

        records = [
            json.loads(line)
            for path in self._evidence_files()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(records, "证据链必须有记录")
        self.assertTrue(
            any(item.startswith("decision:") for item in records[0]["decisions"]),
            f"证据链必须引用 decision: —— {records[0]['decisions']}",
        )


if __name__ == "__main__":
    unittest.main()
