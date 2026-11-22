"""判据**参数契约**(契约 §4.1.1)的反证测试。

一条参数写错的判据(缺必填参数 / 未知参数 / 类型或取值非法 / 非法正则),
若被放行就会变成「永远通过」的假绿 —— 那比缺这条判据更危险。
本文件逐 kind 证明这些输入**一律抛 `CriteriaError`**(CLI 退出码 2)。

每个 kind 至少有一条「参数非法 ⇒ 抛错」的用例;带正则参数的 kind 另有
一条「非法正则 ⇒ 抛错」的用例。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import *  # noqa: F401,F403  (把 scripts/ 放进 sys.path)

from lib.criteria import (
    KIND_PARAMS,
    CriteriaError,
    Criterion,
    Document,
    evaluate,
    load_criteria,
)

# 每个 kind 的一份**合法**参数(契约 §4.1)。
FULL_PARAMS: dict[str, dict] = {
    "section_exists": {"sections": ["## 目标 (Goal)"]},
    "line_present": {"regex": "^# "},
    "line_absent": {"regex": "TODO"},
    "enum_field": {"field": "状态", "values": ["Draft", "Ready"]},
    "date_format": {"field": "评审日期"},
    "checkbox_present": {"min_count": 1},
    "id_format": {"prefix": "AC", "pattern": r"^AC-\d+$"},
    "id_unique": {"prefix": "AC"},
    "id_refs_resolve": {"from_prefix": "S", "to_prefix": "AC", "via_field": "覆盖"},
    "count_min": {"regex": r"^- \[ \]", "min_count": 1},
    "no_placeholder": {"regex": r"\{[^}]+\}"},
    "coverage_complete": {"from_prefix": "AC", "to_prefix": "S", "via_field": "覆盖"},
}

DOC_TEXT = "# 样例\n\n- [ ] AC-1 目标一\n"


def criterion_dict(kind: str, params: dict, ident: str = "T-PARAM") -> dict:
    return {
        "id": ident,
        "layer": "prd",
        "title": "参数契约测试",
        "kind": kind,
        "params": params,
        "blocking": True,
        "source": "tests/test_param_contract.py:1",
    }


def write_criteria(criteria: list[dict]) -> Path:
    root = Path(tempfile.mkdtemp())
    path = root / "criteria.json"
    path.write_text(
        json.dumps({"version": 1, "criteria": criteria}, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )
    return path


class ParamContractTests(unittest.TestCase):
    """加载期:参数写错 ⇒ 抛错。"""

    def _assert_rejects(self, kind: str, params: dict, needle: str = "") -> None:
        path = write_criteria([criterion_dict(kind, params)])
        with self.assertRaises(CriteriaError) as ctx:
            load_criteria(path)
        if needle:
            self.assertIn(needle, str(ctx.exception))

    def test_every_kind_declares_a_param_contract(self):
        from lib.criteria import KINDS

        self.assertEqual(sorted(KIND_PARAMS), sorted(KINDS))
        for kind, (required, optional) in KIND_PARAMS.items():
            with self.subTest(kind=kind):
                self.assertFalse(required & optional)

    def test_missing_required_param_fails_for_every_kind(self):
        """每个 kind 缺任意一个必填参数 ⇒ 抛错(逐 kind、逐参数)。"""
        for kind, (required, _optional) in sorted(KIND_PARAMS.items()):
            if not required:
                continue
            for key in sorted(required):
                with self.subTest(kind=kind, param=key):
                    params = dict(FULL_PARAMS[kind])
                    params.pop(key)
                    self._assert_rejects(kind, params, f"缺少必填参数 {key}")

    def test_unknown_param_fails_for_every_kind(self):
        for kind in sorted(KIND_PARAMS):
            with self.subTest(kind=kind):
                params = dict(FULL_PARAMS[kind])
                params["unexpected"] = "x"
                self._assert_rejects(kind, params, "含未知参数 unexpected")

    def test_invalid_regex_fails_for_regex_kinds(self):
        for kind in ("line_present", "line_absent", "count_min", "no_placeholder", "id_format"):
            with self.subTest(kind=kind):
                params = dict(FULL_PARAMS[kind])
                params["regex" if kind != "id_format" else "pattern"] = "([unclosed"
                self._assert_rejects(kind, params, "不是合法正则")

    def test_empty_regex_fails(self):
        for kind in ("line_present", "line_absent", "count_min", "no_placeholder"):
            with self.subTest(kind=kind):
                params = dict(FULL_PARAMS[kind])
                params["regex"] = ""
                self._assert_rejects(kind, params, "必须是非空字符串")

    def test_empty_sections_and_values_fail(self):
        self._assert_rejects("section_exists", {"sections": []}, "必须是非空列表")
        self._assert_rejects("section_exists", {"sections": [""]}, "必须是非空字符串")
        self._assert_rejects("enum_field", {"field": "状态", "values": []}, "必须是非空列表")
        self._assert_rejects("enum_field", {"field": "状态", "values": [1]}, "必须是非空字符串")

    def test_bad_min_count_fails(self):
        self._assert_rejects("checkbox_present", {"min_count": 0}, "必须 >= 1")
        self._assert_rejects("checkbox_present", {"min_count": -3}, "必须 >= 1")
        self._assert_rejects("checkbox_present", {"min_count": "2"}, "必须是整数")
        self._assert_rejects("checkbox_present", {"min_count": True}, "必须是整数")
        self._assert_rejects("count_min", {"regex": "x", "min_count": 0}, "必须 >= 1")

    def test_empty_prefix_and_field_fail(self):
        self._assert_rejects("id_format", {"prefix": "", "pattern": r"^AC-\d+$"}, "必须是非空字符串")
        self._assert_rejects("id_unique", {"prefix": ""}, "必须是非空字符串")
        self._assert_rejects("date_format", {"field": ""}, "必须是非空字符串")
        self._assert_rejects(
            "id_refs_resolve",
            {"from_prefix": "S", "to_prefix": "AC", "via_field": ""},
            "必须是非空字符串",
        )

    def test_repo_scope_requires_layer_params(self):
        params = dict(FULL_PARAMS["coverage_complete"])
        params["scope"] = "repo"
        self._assert_rejects("coverage_complete", params, "必须给出 from_layer 参数")
        params["from_layer"] = "prd"
        self._assert_rejects("coverage_complete", params, "必须给出 to_layer 参数")

    def test_unsupported_scope_fails(self):
        params = dict(FULL_PARAMS["coverage_complete"])
        params["scope"] = "workspace"
        self._assert_rejects("coverage_complete", params, "scope 不受支持")

    def test_valid_criteria_still_load(self):
        """反向检查:参数合法的判据必须仍能加载(别把门禁焊死)。"""
        path = write_criteria(
            [
                criterion_dict(kind, dict(params), ident=f"T-OK-{index}")
                for index, (kind, params) in enumerate(sorted(FULL_PARAMS.items()))
            ]
        )
        criteria = load_criteria(path)
        self.assertEqual(len(criteria), len(FULL_PARAMS))


class EvaluationFailsClosedTests(unittest.TestCase):
    """求值期:绕过加载期直接构造的判据,参数非法时也必须抛错(不得静默通过)。"""

    def _criterion(self, kind: str, params: dict) -> Criterion:
        return Criterion(
            id="T-EVAL",
            layer="prd",
            title="求值期参数校验",
            kind=kind,
            params=params,
            blocking=True,
            source="tests/test_param_contract.py:1",
        )

    def test_evaluate_raises_on_missing_param(self):
        doc = Document(rel="doc.md", files=[("doc.md", DOC_TEXT.split("\n"))])
        for kind, params in (
            ("section_exists", {}),
            ("line_present", {}),
            ("enum_field", {"field": "状态"}),
            ("id_format", {"prefix": "AC"}),
            ("coverage_complete", {"from_prefix": "AC"}),
        ):
            with self.subTest(kind=kind):
                with self.assertRaises(CriteriaError):
                    evaluate([self._criterion(kind, params)], doc, "prd")

    def test_evaluate_raises_on_invalid_regex(self):
        doc = Document(rel="doc.md", files=[("doc.md", DOC_TEXT.split("\n"))])
        with self.assertRaises(CriteriaError):
            evaluate([self._criterion("line_present", {"regex": "([bad"})], doc, "prd")

    def test_empty_pattern_is_not_a_pass(self):
        """空 pattern ⇒ 形态不合规(而不是「恒真」)。"""
        from lib.artifacts import id_pattern_matches

        self.assertFalse(id_pattern_matches("", "AC-1"))
        self.assertFalse(id_pattern_matches("([bad", "AC-1"))
