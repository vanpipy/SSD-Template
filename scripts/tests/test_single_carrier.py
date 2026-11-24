"""F9(单载体):授权来源、控制平面、CLI 表面、跨制品一致性 —— 机器层的反证测试。

需求来源:`docs/contracts/f9-single-carrier.md`(权威)
  R-4 授权来源只剩 `criteria:` / `external:`(`decision:` 删除)
  R-5 派生视图只打印、不落盘
  R-6 `scan --check` 改为跨制品一致性检查
  R-7 CLI 表面:删 `decide` / `evidence`,加 `--external`
  R-1/R-5 `control/` 控制平面整体删除(留痕 = 制品 + git)

R-2/R-3(人工接入的签名回路:署名保留、`--actor` 拒绝、决定通道消失)放在
`test_human_signature.py` —— 那里是「人怎么接入」的入口;本文件管「机器怎么判」。

**判别点**:每个用例的 docstring 写明「在旧模型(决定文件 + 证据链)下它为什么会红」。
恒真的用例(旧模型下同样绿)在交付报告里单列,不算数。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import (
    REPO_ROOT,
    control_files,
    make_criteria,
    make_repo,
    read_fixture,
    run_cli,
    sha256_of,
)

DATE = "2026-11-22"
TOPIC = "demo-feature"
PRD_REL = f"prd/{DATE}/{TOPIC}.md"
TD_REL = f"tech_design/{DATE}-{TOPIC}/README.md"
PLAN_REL = f"plan/{DATE}-trio-demo/trio-demo.md"
TRIO_PRD_REL = f"prd/{DATE}/trio-demo.md"

# 一条**非阻断**判据:样例 PRD 没有「附加说明 (Notes)」段 ⇒ 它失败,但 blocking=false。
# 用来验证 R-4「非阻断失败必须在复审段点名才放行」。
OPTIONAL_NOTE = {
    "id": "PRD-OPTIONAL-NOTE",
    "layer": "prd",
    "title": "PRD 建议补「附加说明 (Notes)」段(非阻断)",
    "kind": "section_exists",
    "params": {"sections": ["附加说明 (Notes)"]},
    "blocking": False,
    "source": "docs/contracts/agent-first-implementation.md:240",
}


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


class SingleCarrierTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    # ------------------------------------------------------------- R-7 CLI 表面

    def test_decide_subcommand_is_gone(self) -> None:
        """R-7:`decide` 子命令不存在。

        判别点:旧模型下 `decide --help` 退出码 0(子命令存在);
        新模型下 argparse 报「invalid choice」并退出 2。
        """
        repo = make_repo(self.base)
        result = run_cli(repo, "decide", "--help")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("decide", result.stdout + result.stderr)

    def test_evidence_subcommand_is_gone(self) -> None:
        """R-7:`evidence` 子命令不存在(证据链已随 `control/` 一起删除)。

        判别点:旧模型下 `evidence --help` 退出码 0。
        """
        repo = make_repo(self.base)
        result = run_cli(repo, "evidence", "--help")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("evidence", result.stdout + result.stderr)

    def test_advance_help_has_external_and_no_decision(self) -> None:
        """R-7:`advance` 有 `--external`、没有 `--decision`。

        判别点:旧模型下 help 里只有 `--decision`,没有 `--external`。
        """
        repo = make_repo(self.base)
        result = run_cli(repo, "advance", "--help")
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        self.assertIn("--external", out)
        self.assertNotIn("--decision", out)

    def test_scan_json_shape_is_unchanged(self) -> None:
        """R-7:`scan --json` 的形状不变(编排侧依赖它)。

        **这条是回归护栏,不是判别点** —— 旧模型下形状本来就一样。
        """
        repo = make_repo(self.base, {PRD_REL: read_fixture("good-prd.md")})
        result = run_cli(repo, "scan", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("generated_at", payload)
        self.assertIsInstance(payload["artifacts"], list)
        self.assertTrue(payload["artifacts"], "样例仓里应当扫到 1 个制品")
        required = {
            "path",
            "state",
            "dispatchable",
            "dependency_permission",
            "upstream",
            "missing",
        }
        for item in payload["artifacts"]:
            self.assertTrue(
                required.issubset(item.keys()),
                f"scan --json 的制品条目缺字段: {sorted(required - set(item.keys()))}",
            )

    # --------------------------------------------------- R-4 授权来源只剩两种

    def test_nonblocking_failure_without_known_issue_is_blocked(self) -> None:
        """R-4:非阻断判据失败、复审段又没点名它 ⇒ 阻断且零改动。

        判别点:旧模型下「非阻断失败 + 无决定记录」一律阻断(退出码 1);
        新模型下只要复审段写了 `> **已知问题**: <id> — <说明>` 就该放行。
        """
        criteria = make_criteria(self.base, extra=[OPTIONAL_NOTE])
        repo = make_repo(
            self.base,
            {PRD_REL: read_fixture("good-prd-human-review.md")},
            criteria=criteria,
        )
        target = repo / PRD_REL
        before = sha256_of(target)

        result = run_cli(repo, "advance", PRD_REL, "--to", "Ready")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        out = result.stdout + result.stderr
        self.assertIn("PRD-OPTIONAL-NOTE", out)
        self.assertEqual(sha256_of(target), before, "被阻断时目标文件必须零改动")
        self.assertEqual(control_files(repo), [], "被阻断时不得留下任何控制平面文件")

    def test_decision_prefix_in_basis_is_rejected(self) -> None:
        """R-4/R-9:状态依据里的 `decision:` 前缀不再合法。

        判别点:旧模型 `parse_basis` 接受 `criteria|decision|external`;
        新模型只接受 `criteria|external` ⇒ `decision:` 必须被报出来。
        """
        repo = make_repo(
            self.base,
            {
                PRD_REL: set_state(
                    read_fixture("good-prd-human-review.md"),
                    "Ready",
                    basis="decision:control/decisions/d1.md#D1",
                )
            },
        )

        result = run_cli(repo, "scan", "--check")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        out = result.stdout + result.stderr
        self.assertIn("状态依据", out)
        self.assertIn("decision", out)

    def test_external_prefix_in_basis_is_accepted(self) -> None:
        """R-4:`external:` 前缀仍然合法(护栏:别把合法依据一起拒了)。

        **这条是回归护栏** —— 旧模型下也绿。
        """
        repo = make_repo(
            self.base,
            {
                PRD_REL: set_state(
                    read_fixture("good-prd-human-review.md"),
                    "Ready",
                    basis="criteria:PRD-SEC-WHY,external:pr-123",
                )
            },
        )

        result = run_cli(repo, "scan", "--check")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --------------------------------------------- R-6 scan --check 跨制品一致性

    def test_upstream_not_ready_is_reported(self) -> None:
        """R-6(a):上游还没 Ready,下游却是 Ready ⇒ `scan --check` 退出非零并点名。

        判别点:旧模型的 `scan --check` 比对的是 `control/state.json`,
        报的是「控制面未初始化」,**不会**出现「上游未 Ready」这几个字。
        """
        repo = make_repo(
            self.base,
            {
                PRD_REL: read_fixture("good-prd.md"),
                TD_REL: read_fixture("ready-td-readme.md"),
            },
        )

        result = run_cli(repo, "scan", "--check")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("上游未 Ready", result.stdout + result.stderr)

    def test_trio_atomicity_is_reported(self) -> None:
        """R-6(b):同 topic 的三件套里有一个 Implemented、另一个不是 ⇒ 退出非零。

        判别点:旧模型的 `scan --check` 不做三件套原子性检查(它只看 state.json)。
        """
        repo = make_repo(
            self.base,
            {
                TRIO_PRD_REL: set_state(
                    read_fixture("trio-prd.md"),
                    "Implemented",
                    basis="criteria:PRD-SEC-WHY,external:pr-1",
                ),
                PLAN_REL: set_state(read_fixture("trio-plan.md"), "Draft"),
            },
        )

        result = run_cli(repo, "scan", "--check")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("三件套未同时就绪", result.stdout + result.stderr)

    def test_consistent_repo_passes_the_check(self) -> None:
        """R-6:自洽的仓 ⇒ `scan --check` 退出 0(护栏:别把正常仓也判红)。

        判别点:旧模型下若 `control/state.json` 不存在,`scan --check` 会以
        「控制面未初始化」退出 1 ⇒ 旧模型下这条是红的。
        """
        repo = make_repo(self.base, {PRD_REL: read_fixture("good-prd.md")})

        result = run_cli(repo, "scan", "--check")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_repo_passes_the_check(self) -> None:
        """R-6:真实仓 ⇒ `scan --check` 退出 0(需求集明写的验收点)。

        判别点:旧模型下真实仓没有 `control/state.json` 时会退出 1。
        """
        result = run_cli(REPO_ROOT, "scan", "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --------------------------------- R-1/R-5 控制平面整体删除(留痕 = 制品 + git)

    def test_advance_creates_no_control_plane(self) -> None:
        """R-1/R-5:一次成功的 advance 之后,仓里仍然没有 `control/`。

        判别点:旧模型下 advance 会写 `control/evidence/**.jsonl` ⇒ 该目录必然出现。
        """
        repo = make_repo(self.base, {PRD_REL: read_fixture("good-prd-human-review.md")})

        result = run_cli(repo, "advance", PRD_REL, "--to", "Ready")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(control_files(repo), [], "advance 不得写控制平面")
        self.assertFalse(
            (repo / "control").exists(), "advance 不得创建 control/ 目录"
        )

    def test_scan_creates_no_state_file(self) -> None:
        """R-5:`scan` 只打印派生视图,不落盘。

        判别点:旧模型下 `scan` 会写 `control/state.json`。
        """
        repo = make_repo(self.base, {PRD_REL: read_fixture("good-prd.md")})

        result = run_cli(repo, "scan")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(control_files(repo), [], "scan 不得写控制平面")
        self.assertFalse((repo / "control" / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
