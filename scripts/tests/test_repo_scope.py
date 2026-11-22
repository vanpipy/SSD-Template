"""跨层判据(`scope=repo`)的测试。

契约 §4.1:`coverage_complete` 支持可选参数 `scope`(`doc` 默认 / `repo`)+ `from_layer` + `to_layer`。
`scope=repo` 的判据是**跨层**不变式:上游层声明的每个 ID,必须被下游层的某个声明经
`via_field` 覆盖。单文档求值做不到,必须把全仓制品集合喂给引擎。

本模块覆盖三件事:
1. 判据**能失败**:PRD 声明 S-1/S-2,Plan 只覆盖 S-1 ⇒ 必须报出 S-2 未覆盖;
2. 判据**能通过**:Plan 覆盖 S-1/S-2 ⇒ 无违规;
3. **不支持的参数必须显式失败**(报「不支持的 scope」),绝不允许静默通过 ——
   静默通过会把 Plan 的覆盖不变式变成假绿,比缺这条判据更危险。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import make_repo, read_fixture, run_cli  # noqa: E402  (sys.path 由 _support 注入)

from lib.criteria import (  # noqa: E402
    Criterion,
    CriteriaError,
    Document,
    RepoDocument,
    evaluate_repo,
    load_criteria,
)


def _criterion(params: dict, layer: str = "plan") -> Criterion:
    return Criterion(
        id="PLAN-COVERAGE-S",
        layer=layer,
        title="跨层覆盖",
        kind="coverage_complete",
        params=params,
        blocking=True,
        source="schema/plan.md:44",
    )


def _doc(rel: str, text: str) -> Document:
    return Document(rel=rel, files=[(rel, text.split("\n"))])


REPO_PARAMS = {
    "from_prefix": "S",
    "to_prefix": "V",
    "via_field": "场景",
    "scope": "repo",
    "from_layer": "prd",
    "to_layer": "plan",
}


class RepoScopeTests(unittest.TestCase):
    def test_repo_scope_reports_uncovered_scenario(self) -> None:
        """PRD 声明 S-1/S-2,Plan 只覆盖 S-1 ⇒ 必须报出 S-2 未覆盖。"""
        docs = [
            RepoDocument("prd", "scope-demo", _doc("prd/scope-demo.md", read_fixture("scope-prd.md"))),
            RepoDocument("plan", "scope-demo", _doc("plan/scope-demo.md", read_fixture("scope-plan.md"))),
        ]
        result = evaluate_repo([_criterion(REPO_PARAMS)], "plan", docs)

        self.assertFalse(result.passed, "覆盖不全时判据必须失败")
        messages = [item.message for item in result.failures]
        self.assertTrue(
            any("S-2" in message and "无场景覆盖" in message for message in messages),
            f"必须报出 S-2 未覆盖,实际: {messages}",
        )
        self.assertFalse(
            any(message.startswith("S-1 ") for message in messages),
            f"S-1 已被覆盖,不该报它: {messages}",
        )

    def test_repo_scope_passes_when_every_scenario_is_covered(self) -> None:
        """全覆盖 ⇒ 无违规(证明上面那条不是恒失败)。"""
        docs = [
            RepoDocument("prd", "scope-demo", _doc("prd/scope-demo.md", read_fixture("scope-prd.md"))),
            RepoDocument(
                "plan", "scope-demo", _doc("plan/scope-demo.md", read_fixture("scope-plan-full.md"))
            ),
        ]
        result = evaluate_repo([_criterion(REPO_PARAMS)], "plan", docs)

        self.assertTrue(result.passed, f"全覆盖时判据必须通过: {[i.message for i in result.failures]}")
        self.assertEqual([], result.failures)

    def test_repo_scope_without_context_fails_closed(self) -> None:
        """没有全仓上下文 ⇒ 判失败,不是静默通过。"""
        result = evaluate_repo([_criterion(REPO_PARAMS)], "plan", None)

        self.assertFalse(result.passed)
        self.assertTrue(
            any("缺少跨层求值上下文" in item.message for item in result.failures),
            f"必须报缺少上下文: {[i.message for i in result.failures]}",
        )

    def test_unsupported_scope_fails_loudly(self) -> None:
        """不支持的 scope 值 ⇒ 显式失败(报「不支持的 scope」),严禁静默通过。"""
        params = dict(REPO_PARAMS)
        params["scope"] = "workspace"
        result = evaluate_repo([_criterion(params)], "plan", [])

        self.assertFalse(result.passed)
        self.assertTrue(
            any("不支持的 scope" in item.message for item in result.failures),
            f"必须报不支持的 scope: {[i.message for i in result.failures]}",
        )

    def test_repo_scope_needs_from_and_to_layer(self) -> None:
        """缺 from_layer/to_layer ⇒ 显式失败(参数契约 §4.1.1: 抛错,不放行)。"""
        params = {"from_prefix": "S", "to_prefix": "V", "via_field": "场景", "scope": "repo"}
        with self.assertRaises(CriteriaError) as ctx:
            evaluate_repo([_criterion(params)], "plan", [])
        self.assertIn("from_layer", str(ctx.exception))

    def test_load_rejects_unsupported_scope(self) -> None:
        """加载期就拒绝 scope 写错的判据文件(退出码 2 的来源),不靠运行时兜底。"""
        with tempfile.TemporaryDirectory() as base:
            path = Path(base) / "criteria.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "criteria": [
                            {
                                "id": "PLAN-COVERAGE-S",
                                "layer": "plan",
                                "title": "跨层覆盖",
                                "kind": "coverage_complete",
                                "params": {
                                    "from_prefix": "S",
                                    "to_prefix": "V",
                                    "via_field": "场景",
                                    "scope": "workspace",
                                    "from_layer": "prd",
                                    "to_layer": "plan",
                                },
                                "blocking": True,
                                "source": "schema/plan.md:44",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(CriteriaError) as caught:
                load_criteria(path)
            self.assertIn("scope 不受支持", str(caught.exception))

    def test_load_rejects_repo_scope_without_layers(self) -> None:
        """scope=repo 但缺层级参数 ⇒ 加载期拒绝。"""
        with tempfile.TemporaryDirectory() as base:
            path = Path(base) / "criteria.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "criteria": [
                            {
                                "id": "PLAN-COVERAGE-S",
                                "layer": "plan",
                                "title": "跨层覆盖",
                                "kind": "coverage_complete",
                                "params": {
                                    "from_prefix": "S",
                                    "to_prefix": "V",
                                    "via_field": "场景",
                                    "scope": "repo",
                                },
                                "blocking": True,
                                "source": "schema/plan.md:44",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(CriteriaError) as caught:
                load_criteria(path)
            self.assertIn("from_layer", str(caught.exception))

    def test_cli_reports_cross_layer_gap(self) -> None:
        """端到端:`ssdctl criteria <plan>` 必须 exit 1 并报出 S-2。"""
        with tempfile.TemporaryDirectory() as base:
            repo = make_repo(
                Path(base),
                files={
                    "prd/2026-11-22/scope-demo.md": read_fixture("scope-prd.md"),
                    "plan/2026-11-22-scope-demo/scope-demo.md": read_fixture("scope-plan.md"),
                },
            )
            completed = run_cli(repo, "criteria", "plan/2026-11-22-scope-demo/scope-demo.md")

            self.assertEqual(1, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("S-2 无场景覆盖", completed.stdout)
            self.assertIn("PLAN-COVERAGE-S", completed.stdout)


if __name__ == "__main__":
    unittest.main()
