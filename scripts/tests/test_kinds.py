"""判据引擎的 kind 级测试:契约 §4.1 的 12 种 kind,每种都验「通过」与「失败」两个方向。

一个不能失败的检查不算检查(本仓的工程约定)——所以每条用例都同时给出
「文档合规 → 无失败」与「文档不合规 → 至少一条失败」两个断言。
"""

from __future__ import annotations

import unittest

from _support import *  # noqa: F401,F403  (把 scripts/ 放进 sys.path)

from lib.criteria import KINDS, Criterion, Document, evaluate

GOOD_PRD = """# 样例

> **状态**: Draft

## 目标 (Goal)

- [ ] AC-1 目标一
- [ ] AC-2 目标二

## 场景 (Scenarios)

### 场景: S-1 正常路径

**覆盖**: AC-1, AC-2

## 复审 (Review)

> **评审日期**: 2026-11-22
"""


def run_kind(kind: str, params: dict, text: str, layer: str = "prd"):
    """对一段文本跑单条判据,返回求值结果。"""
    doc = Document(rel="doc.md", files=[("doc.md", text.split("\n"))])
    criterion = Criterion(
        id="T-KIND",
        layer=layer,
        title="测试判据",
        kind=kind,
        params=params,
        blocking=True,
        source="tests/test_kinds.py:1",
    )
    return evaluate([criterion], doc, layer)


class KindVocabularyTests(unittest.TestCase):
    def test_kind_vocabulary_is_exactly_twelve(self):
        self.assertEqual(
            sorted(KINDS),
            [
                "checkbox_present",
                "count_min",
                "coverage_complete",
                "date_format",
                "enum_field",
                "id_format",
                "id_refs_resolve",
                "id_unique",
                "line_absent",
                "line_present",
                "no_placeholder",
                "section_exists",
            ],
        )
        self.assertEqual(len(KINDS), 12)


class SectionExistsTests(unittest.TestCase):
    def test_passes_when_section_present_and_fails_when_absent(self):
        params = {"sections": ["目标 (Goal)"]}
        self.assertEqual(run_kind("section_exists", params, GOOD_PRD).failures, [])
        result = run_kind("section_exists", params, "# 空文档\n")
        self.assertTrue(result.failures)
        self.assertIn("目标 (Goal)", result.failures[0].message)


class LinePresentTests(unittest.TestCase):
    def test_passes_when_line_present_and_fails_when_absent(self):
        params = {"regex": r"^> \*\*状态\*\*:"}
        self.assertEqual(run_kind("line_present", params, GOOD_PRD).failures, [])
        result = run_kind("line_present", params, "# 没有状态行\n")
        self.assertTrue(result.failures)


class LineAbsentTests(unittest.TestCase):
    def test_passes_when_forbidden_line_absent_and_fails_when_present(self):
        params = {"regex": r"\|\s*来源\s*\|\s*Raw"}
        self.assertEqual(run_kind("line_absent", params, GOOD_PRD).failures, [])
        result = run_kind("line_absent", params, "| 来源 | Raw | 原始素材 |\n")
        self.assertTrue(result.failures)


class EnumFieldTests(unittest.TestCase):
    def test_passes_for_allowed_value_and_fails_for_other(self):
        params = {"field": "状态", "values": ["Draft", "Ready", "Implemented", "Deprecated"]}
        self.assertEqual(run_kind("enum_field", params, GOOD_PRD).failures, [])
        result = run_kind("enum_field", params, GOOD_PRD.replace("Draft", "Approved"))
        self.assertTrue(result.failures)
        self.assertIn("Approved", result.failures[0].message)


class DateFormatTests(unittest.TestCase):
    def test_passes_for_iso_date_and_fails_for_free_text(self):
        params = {"field": "评审日期"}
        self.assertEqual(run_kind("date_format", params, GOOD_PRD).failures, [])
        result = run_kind("date_format", params, GOOD_PRD.replace("2026-11-22", "下周二"))
        self.assertTrue(result.failures)


class CheckboxPresentTests(unittest.TestCase):
    def test_passes_when_enough_checkboxes_and_fails_when_too_few(self):
        params = {"min_count": 2}
        self.assertEqual(run_kind("checkbox_present", params, GOOD_PRD).failures, [])
        result = run_kind("checkbox_present", params, "- [ ] AC-1 只有一个\n")
        self.assertTrue(result.failures)


class IdFormatTests(unittest.TestCase):
    def test_passes_for_valid_id_and_fails_for_malformed_id(self):
        params = {"prefix": "AC", "pattern": r"^AC-[0-9]+$"}
        self.assertEqual(run_kind("id_format", params, GOOD_PRD).failures, [])
        result = run_kind("id_format", params, GOOD_PRD.replace("AC-1 目标一", "AC-1a 目标一"))
        self.assertTrue(result.failures)
        self.assertIn("AC-1a", result.failures[0].message)


class IdUniqueTests(unittest.TestCase):
    def test_passes_when_unique_and_fails_on_duplicate_declaration(self):
        params = {"prefix": "AC"}
        self.assertEqual(run_kind("id_unique", params, GOOD_PRD).failures, [])
        result = run_kind("id_unique", params, GOOD_PRD + "\n- [ ] AC-1 重复声明\n")
        self.assertTrue(result.failures)
        self.assertIn("AC-1", result.failures[0].message)


class IdRefsResolveTests(unittest.TestCase):
    def test_passes_when_reference_resolves_and_fails_on_dangling_reference(self):
        params = {"from_prefix": "S", "to_prefix": "AC", "via_field": "覆盖"}
        self.assertEqual(run_kind("id_refs_resolve", params, GOOD_PRD).failures, [])
        result = run_kind("id_refs_resolve", params, GOOD_PRD.replace("**覆盖**: AC-1, AC-2", "**覆盖**: AC-404"))
        self.assertTrue(result.failures)
        self.assertIn("AC-404", result.failures[0].message)


class CountMinTests(unittest.TestCase):
    def test_passes_when_enough_matches_and_fails_when_too_few(self):
        params = {"regex": r"^### V-[0-9]+:", "min_count": 2}
        good = "### V-1: 甲\n\n### V-2: 乙\n"
        bad = "### V-1: 甲\n"
        self.assertEqual(run_kind("count_min", params, good).failures, [])
        result = run_kind("count_min", params, bad)
        self.assertTrue(result.failures)


class NoPlaceholderTests(unittest.TestCase):
    def test_passes_when_clean_and_fails_on_placeholder(self):
        params = {"regex": r"\{[^}]+\}"}
        self.assertEqual(run_kind("no_placeholder", params, GOOD_PRD).failures, [])
        result = run_kind("no_placeholder", params, GOOD_PRD + "\n路径: {topic}/x.md\n")
        self.assertTrue(result.failures)
        self.assertIn("{topic}", result.failures[0].message)


class CoverageCompleteTests(unittest.TestCase):
    def test_passes_when_every_id_is_covered_and_fails_on_uncovered_id(self):
        params = {"from_prefix": "AC", "to_prefix": "S", "via_field": "覆盖"}
        self.assertEqual(run_kind("coverage_complete", params, GOOD_PRD).failures, [])
        result = run_kind("coverage_complete", params, GOOD_PRD.replace("**覆盖**: AC-1, AC-2", "**覆盖**: AC-1"))
        self.assertTrue(result.failures)
        self.assertIn("AC-2", result.failures[0].message)
        self.assertIn("无场景覆盖", result.failures[0].message)


if __name__ == "__main__":
    unittest.main()
