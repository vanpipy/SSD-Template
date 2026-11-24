"""F9 R-7 / A-13:「旧命令形态残留」规则的**判别性**单测。

规则本体在 `scripts/acceptance/agent-first-acceptance.py` 的 `legacy_command_hits()`:

- 文档里出现 `python scripts/ssdctl.py`,且该行**不在**否定语境里 ⇒ 违规(要报出来);
- 该行在否定语境里(例如「写 `python scripts/ssdctl.py` 会让 agent 在本机第一步就失败」
  —— 这是解释**为什么不能用**,不是教人用)⇒ 豁免,但要在明细里列出来(不静默放过)。

为什么要单测这条规则:它是**验收脚本里的一条断言**,不是库代码;
一旦它的判别方向写反(把真残留放过,或把解释句当残留),验收就失去意义。
所以这里给正例与反例各一条**能失败**的断言:

- 判别方向反了 ⇒ 正例的 `assertTrue(offenders)` 会红;
- 豁免写得太宽 ⇒ 反例的 `assertEqual(offenders, [])` 会红。
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR

ACCEPTANCE_PY = SCRIPTS_DIR / "acceptance" / "agent-first-acceptance.py"


def _load_acceptance_module():
    """按文件路径加载验收脚本(文件名带连字符,不能直接 import)。

    模块级会挑 Git Bash;找不到就 SystemExit —— 那时用例 skip,
    而不是假装通过。
    """
    spec = importlib.util.spec_from_file_location("agent_first_acceptance", ACCEPTANCE_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit as exc:  # 找不到可用 bash
        raise unittest.SkipTest(f"验收脚本无法加载(缺 bash?): {exc}") from exc
    return module


class LegacyCommandRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.acc = _load_acceptance_module()

    def test_command_usage_is_flagged(self) -> None:
        """真残留(教人照着跑)必须被点名。"""
        text = "调用形态:\n\n```bash\npython scripts/ssdctl.py scan\n```\n"

        offenders, exempted = self.acc.legacy_command_hits(text)

        self.assertTrue(offenders, "把旧命令形态写成可执行命令的行必须被报出来")
        self.assertTrue(any("python scripts/ssdctl.py" in item for item in offenders))
        self.assertEqual(exempted, [], "这行没有否定语境,不该被豁免")

    def test_negative_explanation_is_exempted(self) -> None:
        """解释「为什么不能用」的行必须豁免 —— 否则验收脚本会误报自己的契约文档。"""
        text = (
            "包装器依次尝试候选,全都不行时 exit 2。\n"
            "写 `python scripts/ssdctl.py` 会让 agent 在本机第一步就失败。\n"
        )

        offenders, exempted = self.acc.legacy_command_hits(text)

        self.assertEqual(offenders, [], "否定语境里的说明行不该算残留")
        self.assertEqual(len(exempted), 1, "豁免项要能被数出来(不静默放过)")

    def test_clean_doc_has_no_hits(self) -> None:
        """干净文档(只用新形态)既不违规也不豁免。"""
        text = "统一用 `bash scripts/ssdctl.sh <子命令>`。\n"

        offenders, exempted = self.acc.legacy_command_hits(text)

        self.assertEqual(offenders, [])
        self.assertEqual(exempted, [])

    def test_multiline_prose_explanation_is_exempted(self) -> None:
        """契约文档里那类说明常**跨行** —— 按段落判定才不误报。

        这是实测踩到的形态:`docs/contracts/agent-first-implementation.md:200-201`
        把「写 X 会让 agent 在本机第一步就失败」拆成两行,只按单行看会误报。
        """
        text = (
            "包装器依次尝试候选,全都不行时 exit 2 并列出试过的候选,**不静默继续**。\n"
            "写 `python scripts/ssdctl.py` 会让 agent 在本机\n"
            "第一步就失败,进而退回去手改状态行(本轮要禁止的行为)。\n"
        )

        offenders, exempted = self.acc.legacy_command_hits(text)

        self.assertEqual(offenders, [], "跨行的否定语境说明不该算残留")
        self.assertEqual(len(exempted), 1, "豁免项要能被数出来(不静默放过)")

    def test_code_fence_hit_is_always_an_offender(self) -> None:
        """代码块 = 可照抄的指令 ⇒ 块内的命中一律违规(哪怕同一块里有否定词)。"""
        text = (
            "```bash\n"
            "# 不要用 python scripts/ssdctl.py\n"
            "python scripts/ssdctl.py scan\n"
            "```\n"
        )

        offenders, exempted = self.acc.legacy_command_hits(text)

        self.assertEqual(len(offenders), 2, f"代码块内两处命中都应违规: {offenders}")
        self.assertEqual(exempted, [], "代码块内的命中不该被豁免")

    def test_hit_reports_line_number(self) -> None:
        """违规项要带行号 —— 否则报告只能靠人肉找。"""
        text = "第 1 行\n第 2 行\npython scripts/ssdctl.py gate\n"

        offenders, _ = self.acc.legacy_command_hits(text)

        self.assertEqual(len(offenders), 1)
        self.assertTrue(offenders[0].startswith("3:"), f"应报第 3 行,实得 {offenders[0]!r}")


if __name__ == "__main__":
    sys.exit(unittest.main())
