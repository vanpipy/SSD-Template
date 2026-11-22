# New Factors And New Questions

> **概念参考**。本文件解释这套 harness「为什么长成这样」,不定义任何可执行规则。
> 可执行规则以 [WORKFLOW.md](WORKFLOW.md)(契约唯一真源)与 `schema/**` 模板为准;状态值只有
> `Draft` / `Ready` / `Implemented` / `Deprecated` 四个,全层统一。

1. Why do we have this flow?
2. What problem is this solving?
3. Why is the code shapred like this?
4. Where does this belong?

## ARDs

> Record Your.Decisions

1. What decision was made
2. WHY it was made
3. HOW it is enforced
4. ADR for the decision
5. Reference docs for examples and detail

```
---
id: ard-101
status: Accepted
enforced_by: import-linter
file_patterns:
  - "*/templates/**"
  - "*/templatetags/**"
---

# No ORM queries in templates

Context: ...

Decision: ...

Enforced: ...
```

## PRDs

> Capture.Product.Goals

1. WHY does this feature exist?
2. WHAT problem does it solve?
3. WHAT outcome we expect?
4. Does this still matter?
5. Should we keep it?
6. Can we delete it?

```
---
id: prd-101
status: Draft
owner: leroy
---

# Scheduled eval runs

Why: ...

Problem: ...

Goal: ...

Journey: ...
```

> `status` 取值域与本仓状态机一致:`Draft` / `Ready` / `Implemented` / `Deprecated`。
> `Draft` 由 agent 产出;`Ready` 起需要人工在 `## 复审 (Review)` 段签署。

## BDDs

> Run.Your.Specs

1. Who wants to read AI code? Or AI tests?
2. BDD is not new, but suddenly relevant again
3. Readable and executable -- intent meets code

## Example

> Ancient technology, suddenly useful again.
> Connect directly to PRDs and critical user journeys

```yaml
Feature: Executable spec
  Spec-Driven Develpment does not fully close the loop
  BDD should

  Scenario: Close the loop
    Given an executable specification exists
    When cucumber runs
    Then the scenario passes

```

## Bonus: Design System

> Rule.Your.UI

1. Rules: one primary button per page, no exceptions
2. Components: all states previewed in Lookbook
3. Built bottom-up, like code

## Example: Enforced Architecture

> Rules link to ADRs.

1. BDD tests cannot talk directly to the database
2. Application code stays split into layers
3. Violations fail fast -- at commit time

Agent gets early feedback and works through it to reach the goal.

## Skills Provide Focus

> The loop is generic

1. `to-tech-design` -- which rules govern these changes (关键决策 KD)
2. `to-prd` -- which goals does this serve
3. `to-test-cases` -- iterate fast, reconcile after
4. `validate-spec` -- run focused check suite
5. Goal exception -- decisions and pending work

> 上面的 skill 全部是**仓内** skill,定义在 `.codex/skills/<name>/SKILL.md`,随仓库分发。
> 完整 8 个 skill 的清单与调用签名见 [AGENTS.md](AGENTS.md) §3.7。

## Drawbacks

1. Context-heavy - Slow feedback loop.
2. But that's the goal, no? -- Long-running tasks.

## Summary

1. ADRs -- record decisions
2. PROs -- capture goals
3. BDD -- run you specs
4. Design system -- rule your UI
5. Harness -- enforce the loop

> May the SPEC be with you


