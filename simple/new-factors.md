# New Factors And New Questions

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
status: Active
owner: leroy
---

# Scheduled eval runs

Why: ...

Problem: ...

Goal: ...

Journey: ...
```

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

1. $adr -- which rules govern these changes
2. $prd -- which goals does this serve
3. $ui-loop -- iterate fast, reconcile after
4. $test -- run focused test suite
5. Goal exception -- decisions and pending work

## Drawbacks

1. Context-heavy - Slow feedback loop.
2. But that's the goal, no? -- Long-running tasks.

## Summary

1. ADRs -- record decisions
2. PRDs -- capture goals
3. BDD -- run you specs
4. Design system -- rule your UI
5. Harness -- enforce the loop

> May the SPEC be with you


