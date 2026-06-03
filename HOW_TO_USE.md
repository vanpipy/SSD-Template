# Skill-Driven Usage Guide

## What This Guide Solves

You have a requirement — it could be a user's complaint, a product statement, a vague discussion, or a complete meeting minutes. You need to turn it into an actionable implementation plan that AI can directly compile into code. This guide tells you how to do it step by step.

## Directory Organization

Each input creates a **batch subfolder** that consolidates all outputs from that batch:

```
collection/
├── {date}-{short-topic}/           # Batch folder
│   ├── C01-xxx.md                 # Collection files
│   ├── C02-xxx.md                 # Collection files
│   └── BATCH-OVERVIEW.md          # Batch overview (Agent's splitting artifact)

tech-design/
├── {date}-{short-topic}/           # Batch folder
│   └── td-01-xxx.md               # Tech Design files

implementation/
├── {date}-{short-topic}/           # Batch folder
│   ├── impl-01-xxx.md             # Implementation files
│   └── code/                      # Generated code (optional)
```

- **Batch folder naming**: `{YYYY-MM-DD}-{short-topic}`
- **Each batch** contains: all files generated from this input + batch overview
- **Batch overview**: the Agent's splitting artifact; downstream Agents read it as global context

## Use Cases

One entry point for all inputs: a single requirement, a meeting summary, or anything in between. Go through steps 1–5.

## Workflow

> **Perspective Guide**
> The workflow uses a **dual-role collaboration model** across all steps:
> - **Agent (Drafter / Investigator / Producer)**: Extracts structure from input, drafts artifacts, marks uncertain content with `⚠`, produces technical documents downstream.
> - **Participant (Reviewer / Decider)**: Verifies drafts against what was actually discussed, resolves `⚠` markers, makes final calls on ambiguous points.
>
> Every handoff follows the same pattern: **Agent proposes → Participant decides → Agent records**.
>
> The workflow is divided into two phases:
> - **Requirements phase (Steps 1–2)**: Collection. Agent drafts from input; participant reviews; convergence discussion until all rules are verifiable. Status progression: `Collecting → Converged`.
> - **Technical phase (Steps 3–5)**: Tech Design + Implementation. Agent produces technical documents from converged Collections. Participant reviews for correctness; Agent executes. Status progression: `Draft → Ready → Executed`.

### 1. Step 1 - Collect Requirements

> Agent drafts Collection(s); Participant reviews

Input is any requirement material — a single requirement description, a meeting summary, a product statement, a discussion transcript, or anything in between. The Agent auto-detects whether the input yields one Collection or many, applies the split/merge principles, and drafts accordingly. Output is one or more Collection files placed in `collection/{date}-{short-topic}/`, status **Collecting**.

How to use:
1. Determine batch folder name based on input source
2. Use prompt [Prompt 1: Collect Requirements]
3. **Review handoff**: Agent presents the drafted Collection(s) with `⚠` markers on uncertain fields. If the input yielded multiple Collections, the Agent also presents the batch overview (inventory + relationship diagram) first, then the individual Collections. Resolve `⚠` markers (accept / correct / add pending point).

**Lightweight mode**: When the Agent identifies ≤ 4 independent requirements with no cross-role / cross-system coupling, it may propose lightweight mode. In this case the batch overview is simplified and Collections may be merged.

### 2. Step 2 - Convergence Discussion

> Agent proposes convergence suggestions; Participant decides; Agent records

Input is a Collection file with status "Collecting" (located in batch folder). Output is the same file with status changed to "Converged", all ambiguity points resolved.

How to use: Use prompt [Prompt 2: Convergence Discussion]

**Collaboration pattern**: Agent reads the Collection (and BATCH-OVERVIEW if multi-Collection), produces a **Convergence Proposal** listing each pending point with an AI-suggested resolution and a "Needs your decision" section. You decide each item; Agent records your decisions into the Collection and syncs the batch overview.

For multiple Collections split from Step 1, maintain their relationships. If converging one Collection affects another, the Agent updates the batch-level BATCH-OVERVIEW.md (specifically the Cross-Collection Relationships diagram and Global Pending Convergence List).

### 3. Step 3 - Generate Tech Design

> Executing Agent perspective

Input is a Collection file with status "Converged", plus the target repository's technical context. Output is a Tech Design file placed in `tech-design/{date}-{short-topic}/`, status "Draft".

Tech Design is the bridge between Collection (business rules) and Implementation (code-level instructions). It revolves around four core concerns: **Technical Strategy** (how to build it overall), **Metrics** (what the measurable standards are), **Solution-Level Full Investigation** (whether every part of the end-to-end process has been audited), **Requirement Transformation Fallback** (whether business intent is lost during transformation). The workflow branches by **Design Mode** (Greenfield / Brownfield), with Brownfield as the default.

How to use:
1. Create a batch folder under `tech-design/` with the same name as the collection batch
2. Use prompt [Prompt 3: Generate Tech Design]

Review focus: Does the technical strategy clearly define the overall roadmap and key decisions? Do metrics provide specific numbers instead of vague descriptions? Does the solution-level full investigation cover all three dimensions (end-to-end flow, component interaction, data flow) at an auditable level of granularity? Does the coverage matrix in the fallback strategy verify each Collection scenario line by line? Do degradation plans state the business impact? Do the four pillars pass the cross-cutting consistency review with no internal conflicts? After approval, change status from "Draft" to "Ready", and backfill the Tech Design file path into the Collection's Related Tech Design field.

### 4. Step 4 - Generate Implementation Plan

> Executing Agent perspective

Input is a Tech Design file with status "Ready". Output is an Implementation file placed in `implementation/{date}-{short-topic}/`, status "Draft".

How to use:
1. Create a batch folder under `implementation/` with the same name as the collection batch
2. Use prompt [Prompt 4: Generate Implementation Plan]

Review focus: After AI generates the draft, check whether the change list's structural requirements are consistent with the Tech Design's API contracts and data models, and whether verification cases cover core paths. After approval, change status from "Draft" to "Ready", change the corresponding Collection's status from "Converged" to "Completed", and backfill the Implementation file path into the Collection's Related Implementation field.

### 5. Step 5 - Execute Implementation

> Executing Agent perspective

Input is an Implementation file with status "Ready", plus current project context such as codebase path and tech stack description.

**Trigger command:**
```
/execute implementation {path-to-impl-file}
```

Agent will read the Implementation file and execute according to the guidance within.

### Supplementary: Modify Existing Implementation Plan

1. If an Implementation with status "Draft" needs modification, edit it directly.
2. If an Implementation with status "Ready" or "Completed" needs modification, do not edit it directly. Go back to Step 1, create a new Collection. Fill in the Related Implementation field with the path to the Implementation to be modified, and clearly state the topic of what needs changing. After convergence, proceed through tech design and implementation plan generation. After approval, the new version status becomes "Ready", and the old version is kept in the change log.
3. If only the tech design needs adjustment (no business rule changes), create a new Tech Design version directly and regenerate the Implementation.

---

## Input/Output Quick Reference

Step 1 Collect Requirements. Input: any requirement material (single requirement, meeting summary, or in between), output: one or more Collection files with status "Collecting" plus a batch overview if multi-Collection (in batch folder).
Step 2 Convergence. Input: Collection file with status "Collecting", output: same file with status "Converged".
Step 3 Generate Tech Design. Input: Collection file with status "Converged", output: Tech Design file with status "Draft" (in batch folder).
Step 4 Generate Plan. Input: Tech Design file with status "Ready", output: Implementation file with status "Draft" (in batch folder). After approval, status changes to "Ready".
Step 5 Execute. Input: Implementation file with status "Ready", output: implementation code.

Related Files

- Collection template: schema/collection.md
- Batch overview template: schema/batch-overview.md
- Tech Design template: schema/tech-design.md
- Implementation template: schema/implementation.md

---

## Prompt 1: Collect Requirements

Input: Any requirement material — a single requirement description, a meeting summary, a product statement, a discussion transcript, or anything in between. Can be pasted full text or a local file path.
Output: One or more Collection files placed in batch folder `collection/{date}-{short-topic}/`, status "Collecting". If the input yields multiple Collections, also produces `BATCH-OVERVIEW.md`.

Prompt content:

Task: Convert requirement material into Collection file(s), applying split/merge principles to decide whether the output is one Collection or many. You are the drafter; the participant is the reviewer and decider. Mark uncertain content with `⚠` so the participant knows where judgment is required. Do not skip the review checkpoint.

Steps:

1. **Auto-detect input type**. Read the input and decide:
   - **Single-requirement input**: a single clear requirement with no independent sub-requirements → produces 1 Collection. Skip to step 3.
   - **Multi-requirement input**: a meeting summary, discussion transcript, or any input with multiple independent requirements → produces multiple Collections + a batch overview. Continue with step 2.
2. **Split decision** (multi-requirement input only). List every requirement mentioned, then decide granularity per the following principles:
   - **Split when**: business capability boundaries are clear (login vs settlement vs return), lifecycles are independent (create/modify/archive are not in the same flow), operated by different roles (clerk vs customer vs admin).
   - **Merge when**: end-to-end flow that hangs together (add item → pay → receipt), shares most data models and external systems, always mentioned together in discussion, would yield a thin Collection on its own (fewer than 2 rules).
   - **Prefer fewer Collections over more**: a merged Collection can host multiple Scenario sub-sections; the cross-Collection management cost of splitting is higher than the reading cost.
   - **Soft cap**: if your split produces more than 8 Collections, provide an explicit justification for each beyond the 8th.
   - **Lightweight-mode check**: if independent requirements ≤ 4 AND no cross-role / cross-system coupling, propose lightweight mode (state reason at the top of the batch overview). In lightweight mode, Collections may be merged further and the batch overview is simplified.
   - If multi-requirement, present the proposed split count and rationale, Collection inventory table, cross-Collection relationship diagram, and any "split decisions I'm unsure about" before continuing. Wait for the participant to (a) accept, (b) request merges/splits, or (c) request a lightweight re-split. Adjust the inventory and relationships per feedback.
3. **Draft each Collection**. For each requirement (single or split from multi), generate a Collection file following `schema/collection.md` format. Set status to "Collecting". For uncertain fields, mark with `⚠` so the participant knows where judgment is required:
   - Required Section:
     - Original Request: Preserve original text from the input without rewriting.
     - Discussion Scope: Infer Focus from input content; Out of Scope must be explicitly stated, at least one entry. If no explicit exclusions, write "No explicit exclusions yet".
     - Converged Rules: Choose format by content type — Scenarios use Given/When/Then, Architecture Decisions use "Decision/Options/Choice/Rationale", Business Constraints use natural language + impact scope. Only fill content with explicit conclusions; leave empty if no conclusions. If a rule's "Then" can only be written as a vague description like "complete XX" or "support XX", it has not converged — move it to Pending Convergence Points instead. Mark any inferred-but-unstated rule with `⚠`.
     - Pending Convergence Points: Beyond explicitly unresolved issues in the input, also extract implicit ambiguities (vague verbs, undefined terms, implied exceptions, unspecified roles or permissions). Each point must state what it blocks. For each written "Then", check whether there are implied technical or business details not yet clarified (e.g., "refund via original payment method" — time window? partial refund?).
4. **Create or update batch overview** (multi-requirement input, or single-requirement with cross-system dependencies). Create `BATCH-OVERVIEW.md` following `schema/batch-overview.md` format with: Batch Metadata, Collection Inventory, Cross-Collection Relationships, Global Pending Convergence List (with Priority column: P0 / P1 / P2). For single-requirement inputs, fill only the sections relevant to a single-Collection batch.
5. **🛑 Pause for participant review**. Present to the participant:
   - Each drafted Collection (with `⚠` markers highlighted).
   - If multi-requirement: the batch overview (inventory, relationship diagram, Global Pending Convergence List grouped by priority).
   - A short list of "decisions I need you to make" at the top.
   Wait for the participant to resolve `⚠` markers (accept / correct / add pending point). Status is already "Collecting" — no flip needed at this step.

---

## Prompt 2: Convergence Discussion

Input: One or more Collection files with status "Collecting", plus the batch-level `BATCH-OVERVIEW.md` (if the batch has multiple Collections).
Output: Updated Collection file(s). If cross-Collection dependency changes are involved, updated `BATCH-OVERVIEW.md`. Status may flip from "Collecting" to "Converged" at the end.

Prompt content:

Task: Produce a **Convergence Proposal** for the participant, then record the participant's decisions. The goal is to bring all Converged Rules to verifiable granularity and clear all Pending Convergence Points. You propose; the participant decides; you record.

Steps:

**Phase 1 — Produce Convergence Proposal**

1. **Granularity Check**. Review each Converged Rule's "Then":
   - If "Then" contains vague descriptions like "complete XX", "support XX", "implement XX" without verifiable concrete conditions, this rule is **not qualified**. In your proposal, recommend demoting it to Pending Convergence Points or splitting into finer sub-scenarios.
   - Qualified "Then" examples: "System returns 200 status code with order number", "Cart item quantity +1, total price recalculated".
   - Unqualified "Then" examples: "Binding completed", "Aggregate payment supported", "Order query successful".
2. **Propose resolutions for Pending Convergence Points**. For each pending point, propose one of:
   - **Resolve with AI suggestion**: if context allows a reasonable inference, state the inference with rationale (marked as "AI Suggestion").
   - **Escalate to participant**: if human decision is required, state the blocking impact and 2-3 candidate options for the participant to choose from.
   - **Defer explicitly**: if the point does not block convergence of any in-scope rule, recommend deferring and state why.
3. **Priority assessment**. Assign or reconfirm Priority (P0 / P1 / P2) for each pending point, per the definitions in schema/batch-overview.md.
4. **Implicit Ambiguity Mining**. For each qualified rule, check once more: when implementing this rule, would a developer ask "how exactly?" If yes, add new implicit ambiguity points. Common patterns:
   - Operations involving external systems — how to handle timeout? how to degrade on failure?
   - Operations involving data changes — how to handle concurrent writes? how to ensure idempotency?
   - Operations involving user input — what are the validation rules? how to respond to invalid input?
5. **Identify Gaps**. Check if Converged Rules cover all major scenarios within scope: at least one normal path + at least one exception path. If gaps found, propose new pending points.
6. **Check Consistency**. Check for logical contradictions between Converged Rules. Check consistency between Discussion Scope and Converged Rules.
7. **🛑 Present Convergence Proposal to participant**. The proposal has three sections:
   - **AI Suggestions (accept / reject / edit)**: each pending point with an AI-suggested resolution.
   - **Needs your decision**: each pending point requiring human choice, with 2-3 candidate options.
   - **Proposed deferrals**: pending points recommended for deferral, with rationale.
   Do not write into the Collection yet. Wait for the participant.

**Phase 2 — Record participant decisions**

8. **Record decisions**. For each item in the proposal, apply the participant's decision:
   - Accept AI suggestion → convert to Converged Rule or mark deferred.
   - Reject / edit AI suggestion → write the participant's version.
   - Human-decision item → record the chosen option with rationale.
   - Deferred item → mark as deferred with rationale.
9. **Update Dependencies**. If convergence involves cross-Collection relationship changes, update the batch-level `BATCH-OVERVIEW.md` (Cross-Collection Relationships diagram, Global Pending Convergence List, and any affected inventory rows).
10. **Convergence Completion Determination**. Status may be changed to "Converged" if and only if all of the following are satisfied:
    - Granularity check fully passed (every "Then" is verifiable)
    - All Pending Convergence Points cleared (converted to rules or marked as deferred decisions)
    - Convergence Checklist fully checked off
11. **Flip status and sync batch overview**. Flip each converged Collection's status to "Converged" and update the corresponding inventory row and Global Pending Convergence List in `BATCH-OVERVIEW.md`.

---

## Prompt 3: Generate Tech Design

Input: A Collection file with status "Converged" and target repository information.
Output: A Tech Design file with status "Draft", placed in `tech-design/{date}-{short-topic}/`.

Prompt content:

Task: Convert a converged Collection into a Tech Design file, completing the translation from business rules to technical contracts.

Steps:
0. Check prerequisites.
   - First ask the design mode: "Is this a greenfield design (no existing repository) or a brownfield design (based on an existing repository)?" Do not proceed until confirmed.
   - If **brownfield**: Ask for the target repository address. Do not proceed until provided.
   - If **greenfield**: Target repository is optional and may be left empty.
1. Context gathering (branches by design mode):
   - **Brownfield**: Two-pass repository scan — first pass reads repo-level AGENTS.md / CLAUDE.md / .cursorrules (the authoritative conventions maintained by repo owners, read first to avoid misinterpreting patterns downstream); second pass scans the codebase against these conventions and fills in the Repository Context. For each sub-field, list 1-2 typical/representative file paths — exhaustive enumeration is not required.
   - **Greenfield**: Problem-domain investigation — requirement boundaries, candidate tech stack, similar-system references. Fill in the Problem Domain Context to feed the rationale for technical strategy decisions downstream.
2. Fill identification. Name consistent with Collection topic, version set to 1.0.0, status set to "Draft", **Design Mode** filled per Step 0 conclusion, source backfilled with Collection path.
3. Fill applicability. Inherit from Collection, supplement with technical boundaries (e.g., "covers API layer only, excludes UI").
4. Scenario mapping & solution-level full investigation (merged step).
   For each Collection scenario, unfold the complete technical execution path, covering three dimensions:
   - End-to-end flow investigation (input, processing logic, output, failure conditions, failure impact, and involved components for each step)
   - Component interaction investigation (caller, callee, protocol, data format, timeout, failure handling, and whether an existing implementation exists)
   - Data flow investigation (create, modify, read, archive/delete paths and consistency risks for each data object)
   Brownfield must additionally tag each step as "reuse existing / modify existing / add new" and point to the corresponding existing code location; greenfield focuses on candidate technical paths and similar-system references.
   Output investigation conclusions: coverage completeness, key risks, and points requiring further investigation.
5. Define technical strategy (grounded in investigation conclusions). First establish the overall technical roadmap (architecture style, integration pattern, data management strategy, deployment approach), then list alternatives, selection, and rationale for key design questions. Each decision must have at least two alternatives. **Greenfield** decisions must be fully reasoned from first principles; relying on "follow existing" to skip reasoning is not allowed.
6. Define metrics (grounded in investigation conclusions). Set measurable target values across performance, quality, and capacity dimensions, with measurement methods. No vague descriptions like "high performance" — specific numbers required.
7. Define data models (grounded in the data-flow investigation). Define data structures for each business entity down to field level, annotate field constraints and storage. Brownfield distinguishes new fields from extensions of existing models; greenfield defines end-to-end. Link back to Collection scenarios.
8. Define API contracts (grounded in the component-interaction investigation). Define interfaces for each user operation, including endpoint, request/response fields, pre/postconditions, side effects. Brownfield distinguishes new endpoints from modifications of existing endpoints; greenfield defines end-to-end. Each API must link to a specific Collection scenario.
9. Define external system integrations (grounded in investigation conclusions). List all external systems requiring interaction with integration specifications.
10. Define error handling strategy. Unified error code system and degradation plans.
11. Build requirement transformation fallback strategy. Verify the coverage matrix line by line (every Collection scenario has a corresponding technical path), define degradation plans (trigger condition, degraded behavior, business impact, recovery condition), record omission risks. The fallback strategy must be grounded in the full investigation conclusions; skipping the investigation and writing fallback directly is not allowed.
12. Plan implementation order. Order by dependency: foundation before application, data before interfaces.
13. Cross-cutting consistency review. Verify internal consistency across all decisions from Steps 5-12:
    - Are technical strategy and metrics compatible (can the chosen strategy support the metric targets)?
    - Do data models support the read/write needs of all API contracts?
    - Does the scenario mapping fully cover every Collection scenario (cross-check with the fallback coverage matrix)?
    - Are external system integrations, error handling, and implementation order mutually consistent?
    - If inconsistencies are found, revise the relevant fields and record the revision rationale.
14. Fill change log. Add initial version record.
15. Backfill association. Backfill Tech Design path into Collection's Related Tech Design field.

---

## Prompt 4: Generate Implementation Plan

Input: A Tech Design file with status "Ready".
Output: An Implementation file with status "Draft", placed in `implementation/{date}-{short-topic}/`.

Prompt content:

Task: Convert a Ready Tech Design into an Implementation file, completing the translation from technical contracts to code-level instructions.

Steps:
0. Check prerequisites. Confirm Tech Design status is "Ready" and target repository is confirmed.
1. Read input. Read all fields of the Tech Design file.
2. Fill identification. Name consistent with Tech Design, version set to 1.0.0, status set to "Draft", source backfilled with Tech Design path.
3. Fill source control. Extract branch conventions and PR requirements from the target repository's Agent instruction files and repository context.
4. Fill applicability. Map directly from Tech Design.
5. Fill interfaces. Map directly from Tech Design API Contracts; request/response structures are already defined.
6. Fill business constraints. Map preconditions/postconditions/side effects from Tech Design API Contracts. Extract invariants from common constraints across Scenario Mappings.
7. Fill dependencies. Infer preceding/follow-up Skills and collaboration mode from Tech Design's External System Integration and Scenario Mapping call chains.
8. Fill development constraints. Infer concurrency strategy, transaction boundary, idempotency, retry/degradation from Tech Design's Error Handling Strategy and Technical Constraints.
9. Generate change list. Based on Tech Design's Implementation Order, Data Models, and API Contracts, generate the concrete change list. Each change item must include sequence number, file path, structural requirements (function/type signatures), and link back to the Tech Design API or data model.
10. Fill verification. Generate verification cases for each Scenario-to-Technical-Path Mapping entry, linked to specific change items and functions.
11. Fill implementation strategy. Default test-first is "No", behavior-driven is "Yes".
12. Fill change log. Add initial version record.
13. Backfill associations. Backfill Implementation path into Tech Design's Related Implementation field, and also into Collection's Related Implementation field.
