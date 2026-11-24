"""F9 R-2/R-3:人工接入 = 直接在制品里写内容,然后跑**同一条** `advance`。

规则来源:`docs/contracts/f9-single-carrier.md`
  R-2 人工接入没有专属通道(没有决定文件 / `decide` 子命令);
  R-3 同一条命令、机器不代填人名:
       - 人**先**在制品的 `## 复审 (Review)` 段写好署名,再跑 `advance`;
       - `advance` **永不覆盖**已有复审块(非空 ⇒ 原样保留;空 ⇒ 机器写);
       - `--actor` 只接受 `agent:<id>`;人工署名请写在制品的复审段内。

旧模型(决定文件 + `--decision` + 证据链)已被 F9 删除 —— 本文件把那些断言换掉,
不是删掉断言:每条都换成一个**在旧模型下会红**的新断言。

**署名形态说明**:复审块的 `评审人` 用**裸 handle**(如 `alice`),依据实施契约
`docs/contracts/agent-first-implementation.md:64` / :290 / :397 与权威判据
`schema/criteria.json:192-200`(`PRD-REVIEWER` 明写「禁止 human: 前缀」,blocking=true)。
F9 需求集 R-3 的字面写法是 `评审人: human:<handle>` —— 与实施契约/判据不一致,
已在 D3 报告里作为冲突上报给 Lead 裁决;本文件按**实施契约 + 权威判据**取裸 handle。
`human:` 前缀合法的地方是**状态主体**行(实施契约 :47),不是复审块的评审人行。

**判别点**(旧模型下为什么会红):
1. `--actor human:alice` 旧模型下是**允许**的(只是「操作者」,人工署名靠决定文件提供);
2. 旧模型的 advance 会用 `--actor` / 决定文件重写复审块 ⇒ 人工写的署名会被覆盖;
3. 旧模型有 `decide` 子命令与 `advance --decision` 参数 ⇒ 通道还在;
4. 旧模型下「非阻断判据失败 + 没有决定记录」一律阻断,人无法靠写制品来放行。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import (
    control_files,
    make_criteria,
    make_repo,
    read_fixture,
    run_cli,
    sha256_of,
)

DATE = "2026-11-22"
PRD_REL = f"prd/{DATE}/demo-feature.md"

# 一条**非阻断**判据:样例 PRD 没有「附加说明 (Notes)」段 ⇒ 它失败,但 blocking=false。
OPTIONAL_NOTE = {
    "id": "PRD-OPTIONAL-NOTE",
    "layer": "prd",
    "title": "PRD 建议补「附加说明 (Notes)」段(非阻断)",
    "kind": "section_exists",
    "params": {"sections": ["附加说明 (Notes)"]},
    "blocking": False,
    "source": "docs/contracts/agent-first-implementation.md:240",
}

# 权威判据 `schema/criteria.json:192-200` 的 `PRD-REVIEWER` **复制件**。
# 复制而不是直接引用:`scripts/tests/` 不依赖 `schema/criteria.json` 的内容,
# 但要把「评审人 只接受 `agent:<id>` 或裸 handle」这条口径钉住,否则会出现
# 「夹具判据绿、真实仓红」。`source` 必须写成 file:line 形式(判据加载器会校验)。
PRD_REVIEWER = {
    "id": "PRD-REVIEWER",
    "layer": "prd",
    "title": "评审人取值只能是 agent:<id> 或裸 handle;禁止 human: 前缀",
    "kind": "line_present",
    "params": {
        "regex": r"^> \*\*评审人\*\*:\s*(agent:[A-Za-z0-9._-]+|[A-Za-z0-9._-]+)?$"
    },
    "blocking": True,
    "source": "schema/prd.md:85",
}


def with_known_issue(text: str, criterion_id: str, note: str = "人工已确认的已知问题") -> str:
    """在制品的复审段里加一行 `> **已知问题**: <id> — <说明>`(F9 R-4/R-10)。"""
    marker = "## 复审 (Review)"
    out: list[str] = []
    inserted = False
    for line in text.split("\n"):
        out.append(line)
        if not inserted and line.startswith(marker):
            out.append("")
            out.append(f"> **已知问题**: {criterion_id} — {note}")
            inserted = True
    assert inserted, "夹具里必须有「## 复审 (Review)」段"
    return "\n".join(out)


class HumanSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    # --------------------------------------------------------------- R-3 署名

    def test_human_actor_is_rejected(self) -> None:
        """R-3:`--actor` 只接受 `agent:<id>` —— 机器不许代填人名。

        两种人名形态都要被拒:`alice`(裸 handle)与 `human:alice`。

        判别点:旧模型下 `--actor alice` 是允许的(它只是「操作者」),
        人工署名靠决定文件里的「操作人」提供 ⇒ 旧模型下这条是绿的。
        """
        repo = make_repo(self.base, {PRD_REL: read_fixture("good-prd-human-review.md")})
        target = repo / PRD_REL
        before = sha256_of(target)

        for actor in ("alice", "human:alice"):
            with self.subTest(actor=actor):
                result = run_cli(repo, "advance", PRD_REL, "--to", "Ready", "--actor", actor)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                out = result.stdout + result.stderr
                self.assertIn("agent:<id>", out)
                self.assertIn("复审", out)
                self.assertEqual(sha256_of(target), before, "被拒时目标文件必须零改动")
                self.assertEqual(control_files(repo), [], "被拒时不得留下控制平面文件")

    def test_human_signature_is_preserved_verbatim(self) -> None:
        """R-3:人写好的复审块,advance 之后**逐字保留**。

        判别点:旧模型的 advance 会按 `--actor` / 决定文件重写复审块
        ⇒ 人工写的 `alice` / `人工介入` 会被改掉。

        **关于署名形态**:复审块的 `评审人` 用**裸 handle**(实施契约
        `docs/contracts/agent-first-implementation.md:64` / :290 / :397,
        权威判据 `schema/criteria.json:192-200` `PRD-REVIEWER` 明写「禁止 human: 前缀」)。
        F9 需求集 R-3 的字面写法是 `human:<handle>` —— 两处不一致,已在 D3 报告里上报给 Lead 裁决。
        """
        repo = make_repo(self.base, {PRD_REL: read_fixture("good-prd-human-review.md")})
        target = repo / PRD_REL
        before = target.read_text(encoding="utf-8")

        result = run_cli(repo, "advance", PRD_REL, "--to", "Ready")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = target.read_text(encoding="utf-8")
        self.assertIn("> **状态**: Ready", after)
        for line in (
            "> **评审人**: alice",
            "> **评审日期**: 2026-11-22",
            "> **评审结论**: 通过",
            "> **评审方式**: 人工介入",
        ):
            self.assertIn(line, before, f"夹具本身应含这行: {line}")
            self.assertIn(line, after, f"人工写的复审行被覆盖了: {line}")

    def test_human_prefix_reviewer_is_blocked_by_criteria(self) -> None:
        """R-3(字面写法)与权威判据的冲突:**当前口径下 `human:<handle>` 进不去**。

        F9 需求集 R-3 写「人先在制品复审段写 `评审人: human:<handle>`」,
        但权威判据 `schema/criteria.json:192-200` 的 `PRD-REVIEWER`(blocking=true,
        标题「禁止 human: 前缀」)只接受 `agent:<id>` 或**裸 handle**。

        本用例把**当前口径**钉住(用**派生判据**复制权威判据的正则,不去依赖
        `schema/criteria.json` 本身):`human:alice` ⇒ 阻断判据 PRD-REVIEWER 失败
        ⇒ advance exit 1 且零改动。

        判别点:夹具判据里没有 `PRD-REVIEWER` ⇒ 不加这条派生判据时,`human:alice`
        是能过的 ⇒ 这条用例正是「夹具绿、真实仓红」的守卫。

        若 Lead 裁定放宽 `human:` 前缀(需求集 R-3 优先),改这一条即可 ——
        它是这个冲突的唯一守卫。
        """
        criteria = make_criteria(self.base, extra=[PRD_REVIEWER])
        text = read_fixture("good-prd-human-review.md").replace(
            "> **评审人**: alice", "> **评审人**: human:alice"
        )
        repo = make_repo(self.base, {PRD_REL: text}, criteria=criteria)
        target = repo / PRD_REL
        before = sha256_of(target)

        result = run_cli(repo, "advance", PRD_REL, "--to", "Ready")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        out = result.stdout + result.stderr
        self.assertIn("PRD-REVIEWER", out)
        self.assertEqual(sha256_of(target), before, "被拒时目标文件必须零改动")

    def test_empty_review_block_is_filled_by_machine(self) -> None:
        """R-3:复审块为空 ⇒ 机器写署名(评审人 = `--actor`,只能是 `agent:<id>`)。

        判别点:旧模型下复审块的值来自决定文件的「操作人」,机器不自己写
        ⇒ 旧模型下没有「机器填复审块」这条路径。
        """
        criteria = make_criteria(self.base, drop={"PRD-REVIEW-DATE"})
        repo = make_repo(
            self.base,
            {PRD_REL: read_fixture("good-prd-empty-review.md")},
            criteria=criteria,
        )
        target = repo / PRD_REL

        result = run_cli(repo, "advance", PRD_REL, "--to", "Ready")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = target.read_text(encoding="utf-8")
        self.assertIn("> **状态**: Ready", after)
        self.assertIn("> **评审人**: agent:ssdctl", after)
        self.assertNotIn("human:", after, "机器不得代填人工署名")

    # --------------------------------------------------- R-2 人工接入没有专属通道

    def test_decision_channel_is_gone(self) -> None:
        """R-2:`advance --decision` 不再是可用参数(人工接入没有专属通道)。

        判别点:旧模型下 `advance --decision <path>#D1` 是合法参数(退出码 0/1,不是 2)。
        """
        repo = make_repo(self.base, {PRD_REL: read_fixture("good-prd-human-review.md")})

        result = run_cli(
            repo, "advance", PRD_REL, "--to", "Ready", "--decision", "control/decisions/d1.md#D1"
        )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        out = result.stdout + result.stderr
        self.assertIn("--decision", out)
        self.assertIn("unrecognized", out.lower() + out)

    def test_human_known_issue_unblocks_a_nonblocking_failure(self) -> None:
        """R-3 + R-4:人只靠「在制品复审段写一行」就能放行非阻断失败。

        判别点:旧模型下「非阻断失败 + 无决定记录」一律阻断(退出码 1)
        ⇒ 旧模型下这条是红的。
        """
        criteria = make_criteria(self.base, extra=[OPTIONAL_NOTE])
        repo = make_repo(
            self.base,
            {
                PRD_REL: with_known_issue(
                    read_fixture("good-prd-human-review.md"), "PRD-OPTIONAL-NOTE"
                )
            },
            criteria=criteria,
        )
        target = repo / PRD_REL

        result = run_cli(repo, "advance", PRD_REL, "--to", "Ready")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = target.read_text(encoding="utf-8")
        self.assertIn("> **状态**: Ready", text)
        self.assertIn("PRD-OPTIONAL-NOTE", text, "人写的「已知问题」行必须保留")
        self.assertIn("> **评审人**: alice", text, "人的署名必须保留")


if __name__ == "__main__":
    unittest.main()
