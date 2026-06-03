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

Scenario A: You have a single requirement, create a Collection directly. Go through steps 1-6.

Scenario B: You have a meeting summary containing multiple requirements. Split it into multiple Collections first, then converge individually. Go through steps 0-6.

## Workflow

> **Perspective Guide**
> The workflow uses a **dual-role collaboration model** across all steps:
> - **Agent (Drafter / Investigator / Producer)**: Extracts structure from input, drafts artifacts, marks uncertain content with `⚠`, produces technical documents downstream.
> - **Participant (Reviewer / Decider)**: Verifies drafts against what was actually discussed, resolves `⚠` markers, makes final calls on ambiguous points.
>
> Every handoff follows the same pattern: **Agent proposes → Participant decides → Agent records**.
>
> The workflow is divided into two phases:
> - **Requirements phase (Steps 0–2)**: Collection. Agent drafts from input; participant reviews; convergence discussion until all rules are verifiable. Status progression: `Draft → Collecting → Converged`.
> - **Technical phase (Steps 3–6)**: Tech Design + Implementation. Agent produces technical documents from converged Collections. Participant reviews for correctness; Agent executes. Status progression: `Draft → Ready → Executed`.

### 0. Scenario B Entry: Step 0 - Split Meeting Summary

> Agent drafts split proposal; Participant reviews; Agent drafts Collections

For Scenario B. Input is a meeting summary, either manually recorded or AI-generated. Output is a batch overview with Collection inventory + multiple Collection files in `collection/{date}-{short-topic}/`. Collections start as **Draft** and flip to **Collecting** after participant review.

How to use:
1. Determine batch folder name based on input source
2. Use prompt [Prompt 1: Split Meeting Summary]
3. **Review handoff**: Agent first presents the split proposal (inventory + relationship diagram) for your approval. Only after you confirm does the Agent draft each Collection and the global pending list.

**Lightweight mode**: When the Agent identifies ≤ 4 independent requirements with no cross-role / cross-system coupling, it may propose lightweight mode. In this case the two review rounds collapse into one, and the batch overview is simplified.

### 1. Scenario A Entry: Step 1 - Create Single Collection

> Agent drafts Collection; Participant reviews

If you only have one requirement, start here. Input is a raw requirement description. Output is a Collection file placed in `collection/{date}-{short-topic}/`, initially in **Draft** status, flipping to **Collecting** after your review.

How to use:
1. Determine batch folder name based on input source
2. Use prompt [Prompt 2: Create Single Collection]
3. **Review handoff**: Agent presents the drafted Collection with `⚠` markers on uncertain fields. Resolve them (accept / correct / add pending point); Agent flips status to Collecting.

### 2. Step 2 - Convergence Discussion

> Agent proposes convergence suggestions; Participant decides; Agent records

Input is a Collection file with status "Collecting" (located in batch folder). Output is the same file with status changed to "Converged", all ambiguity points resolved.

How to use: Use prompt [Prompt 3: Convergence Discussion]

**Collaboration pattern**: Agent reads the Collection (and BATCH-OVERVIEW if multi-Collection), produces a **Convergence Proposal** listing each pending point with an AI-suggested resolution and a "Needs your decision" section. You decide each item; Agent records your decisions into the Collection and syncs the batch overview.

For multiple Collections split from Step 0, maintain their relationships. If converging one Collection affects another, the Agent updates the other's dependency fields and the batch-level BATCH-OVERVIEW.md (specifically the Cross-Collection Relationships diagram and Global Pending Convergence List).

### 3. Step 3 - Generate Tech Design

> Executing Agent perspective

Input is a Collection file with status "Converged", plus the target repository's technical context. Output is a Tech Design file placed in `tech-design/{date}-{short-topic}/`, status "Draft".

Tech Design is the bridge between Collection (business rules) and Implementation (code-level instructions). It revolves around four core concerns: **Technical Strategy** (how to build it overall), **Metrics** (what the measurable standards are), **Solution-Level Full Investigation** (whether every part of the end-to-end process has been audited), **Requirement Transformation Fallback** (whether business intent is lost during transformation). The workflow branches by **Design Mode** (Greenfield / Brownfield), with Brownfield as the default.

How to use:
1. Create a batch folder under `tech-design/` with the same name as the collection batch
2. Use prompt [Prompt 4: Generate Tech Design]

Review focus: Does the technical strategy clearly define the overall roadmap and key decisions? Do metrics provide specific numbers instead of vague descriptions? Does the solution-level full investigation cover all three dimensions (end-to-end flow, component interaction, data flow) at an auditable level of granularity? Does the coverage matrix in the fallback strategy verify each Collection scenario line by line? Do degradation plans state the business impact? Do the four pillars pass the cross-cutting consistency review with no internal conflicts? After approval, change status from "Draft" to "Ready", and backfill the Tech Design file path into the Collection's Related Tech Design field.

### 4. Step 4 - Generate Implementation Plan

> Executing Agent perspective

Input is a Tech Design file with status "Ready". Output is an Implementation file placed in `implementation/{date}-{short-topic}/`, status "Draft".

How to use:
1. Create a batch folder under `implementation/` with the same name as the collection batch
2. Use prompt [Prompt 5: Generate Implementation Plan]

### 5. Step 5 - Review Implementation Plan

> Executing Agent perspective (human review)

Input is an Implementation file with status "Draft". Output is the same file with status changed to "Ready".

After AI generates the Implementation draft, you need to review it. Focus on: whether the change list's structural requirements are consistent with the Tech Design's API contracts and data models, and whether verification cases cover core paths. After approval, change status from "Draft" to "Ready", change the corresponding Collection's status from "Converged" to "Completed", and backfill the Implementation file path into the Collection's Related Implementation field.

### 6. Step 6 - Execute Implementation

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

Scenario A: Single requirement entry.
Step 1 Create Collection. Input: raw requirement, output: Collection file with status "Draft" → "Collecting" after participant review (in batch folder).
Step 2 Convergence. Input: Collection file with status "Collecting", output: same file with status "Converged".
Step 3 Generate Tech Design. Input: Collection file with status "Converged", output: Tech Design file with status "Draft" (in batch folder).
Step 4 Generate Plan. Input: Tech Design file with status "Ready", output: Implementation file with status "Draft" (in batch folder).
Step 5 Review. Input: Implementation file with status "Draft", output: same file with status "Ready".
Step 6 Execute. Input: Implementation file with status "Ready", output: implementation code.

Scenario B: Meeting summary entry.
Step 0 Split. Input: meeting summary, output: BATCH-OVERVIEW.md + multiple Collection files, all initially "Draft" → "Collecting" after participant review (in same batch folder).
Each subsequent step executes independently for each Collection, same as Scenario A.

Related Files

- Collection template: schema/collection.md
- Batch overview template: schema/batch-overview.md
- Tech Design template: schema/tech-design.md
- Implementation template: schema/implementation.md

---

## Prompt 1: Split Meeting Summary

Input: Meeting summary, can be pasted full text or local file path.
Output: A batch overview (`BATCH-OVERVIEW.md`) plus multiple Collection files, placed in batch folder `collection/{date}-{short-topic}/`. Collections start as Draft and flip to Collecting after participant review.

Prompt content:

Task: Analyze meeting summary, identify independent requirements, generate a batch overview and Collection files using a **two-pass draft-review protocol**. The batch overview is your (the Agent's) splitting artifact — downstream Agents will treat it as global context. You are the drafter; the participant is the reviewer and decider. Do not skip the review checkpoints.

Steps:

**Pass 1 — Propose split (status: Draft)**

1. **Split decision**. Read the meeting summary and list every requirement mentioned. Then decide granularity per the following principles:
   - **Split when**: business capability boundaries are clear (login vs settlement vs return), lifecycles are independent (create/modify/archive are not in the same flow), operated by different roles (clerk vs customer vs admin).
   - **Merge when**: end-to-end flow that hangs together (add item → pay → receipt), shares most data models and external systems, always mentioned together in discussion, would yield a thin Collection on its own (fewer than 2 rules).
   - **Prefer fewer Collections over more**: a merged Collection can host multiple Scenario sub-sections; the cross-Collection management cost of splitting is higher than the reading cost.
   - **Soft cap**: if your split produces more than 8 Collections, provide an explicit justification for each beyond the 8th.
2. **Lightweight-mode check**. If independent requirements ≤ 4 AND no cross-role / cross-system coupling, propose lightweight mode (state reason at the top of the batch overview). In lightweight mode, Pass 1 and Pass 2 may collapse into a single round.
3. **Draft batch overview (partial)**. Create `BATCH-OVERVIEW.md` following `schema/batch-overview.md` format. Fill in only these sections for now: Batch Metadata, Collection Inventory, Cross-Collection Relationships. Do not yet draft the global pending list or the supplementary section.
4. **🛑 Pause for participant review**. Present to the participant:
   - The proposed split count and rationale.
   - The Collection Inventory table.
   - The Cross-Collection relationship diagram.
   - A short list of "Split decisions I'm unsure about" (if any).
   - The lightweight-mode recommendation (if applicable).
   Wait for the participant to (a) accept, (b) request merges/splits, or (c) request a lightweight re-split. Adjust the inventory and relationships per feedback before proceeding.

**Pass 2 — Draft Collections + global pending list (status: Draft → Collecting after review)**

5. **Extract requirements**. Per the approved split decision, list all requirements — each with a clear boundary, non-overlapping and complete.
6. **Draft each Collection**. For each requirement, generate a Collection file following `schema/collection.md` format. Set status to "Draft" and Draft Origin to "agent-prompt1". For uncertain fields, mark with `⚠` so the participant knows where judgment is required:
   - Required Section:
     - Original Request: Preserve original text from the summary without rewriting.
     - Discussion Scope: Infer Focus from summary content; Out of Scope must be explicitly stated, at least one entry.
     - Converged Rules: Choose format by content type — Scenarios use Given/When/Then, Architecture Decisions use "Decision/Options/Choice/Rationale", Business Constraints use natural language + impact scope. Only fill content with explicit conclusions; leave empty if no conclusions.
     - Pending Convergence Points: Beyond explicitly unresolved issues in the summary, also extract implicit ambiguities (vague verbs, undefined terms, implied exceptions, unspecified roles or permissions). Each point must state what it blocks.
   - Supplementary Section: Fill Discussion & Decision Log, Dependencies, Technical Constraints from whatever can be extracted from the summary; leave empty if nothing is extractable.
7. **Complete batch overview**. After drafting all Collections, add to `BATCH-OVERVIEW.md`: the Global Pending Convergence List (with Priority column: P0 / P1 / P2), External Dependency Summary, Architecture Decision Summary, and Batch-Level Themes.
8. **Backfill relationships**. Per the relationship diagram in the batch overview, backfill cross-Collection dependencies into each Collection's Dependencies supplementary field.
9. **🛑 Pause for participant review (second round)**. Present to the participant:
   - Each drafted Collection (with `⚠` markers highlighted).
   - The Global Pending Convergence List grouped by priority.
   - The supplementary sections (external dependencies, architecture decisions, themes).
   Wait for the participant to resolve `⚠` markers (accept / correct / add pending point). After each Collection is reviewed, flip its status from "Draft" to "Collecting" and update the inventory in `BATCH-OVERVIEW.md`.

Constraints:
- All output files must be placed in the batch folder; the batch overview file must be named `BATCH-OVERVIEW.md`.
- Each Collection starts as "Draft" and flips to "Collecting" only after participant review — never skip the review checkpoints.
- Do not add business content not present in the summary.
- If a requirement has absolutely no details in the summary, still generate a Collection but only fill Original Request, leave others empty.
- All four Required Section fields must not be left empty (except Converged Rules, which may be empty if no conclusions exist).
- Split decision must have rationale; when in doubt, prefer merging and hosting multiple Scenario sub-sections within a single Collection.
- The batch overview must be derived from the Collections already generated; no fabricated content.
- Every entry in the Global Pending Convergence List must have a Priority (P0 / P1 / P2).

---

## Prompt 2: Create Single Collection

Input: A raw requirement description, can be natural language.
Output: A Collection file in batch folder `collection/{date}-{short-topic}/`. Status starts as "Draft" and flips to "Collecting" after participant review.

Prompt content:

Task: Convert raw requirement into a Collection file using a **draft-review protocol**. You are the drafter; the participant is the reviewer and decider. Mark uncertain content with `⚠` so the participant knows where judgment is required.

Steps:
1. **Lightweight-mode check**. If the batch currently has ≤ 4 Collections and no cross-role / cross-system coupling, you may use the lightweight Collection form (see schema/collection.md). State the reason at the top of the batch overview when creating or updating it.
2. **Create the file** following schema/collection.md format in the batch folder. Set status to "Draft" and Draft Origin to "agent-prompt2".
3. **Original Request**: Preserve user's original text without rewriting.
4. **Discussion Scope**:
   - In Scope: Infer business domain and functional boundaries from requirement content.
   - Out of Scope: If the requirement or meeting explicitly excludes certain features (e.g., "not in phase 1", "not our responsibility"), they must be listed here. If no explicit exclusions, write "No explicit exclusions yet".
5. **Converged Rules**: Choose format by content type — Scenarios use Given/When/Then, Architecture Decisions use "Decision/Options/Choice/Rationale", Business Constraints use natural language + impact scope. Only fill content with explicit conclusions. If a rule's "Then" can only be written as a vague description like "complete XX" or "support XX", it has not converged — do not add it to Converged Rules, move it to Pending Convergence Points instead. Mark any inferred-but-unstated rule with `⚠`.
6. **Pending Convergence Points**: Fill in two categories, each point noting which rule it blocks.
   - Explicit ambiguities: Uncertainties explicitly mentioned in the requirement (e.g., "to be decided later", "not yet confirmed").
   - Implicit ambiguities: For each written "Then", check whether there are implied technical or business details not yet clarified. For example:
     - "Refund via original payment method" — refund time window? partial refund?
     - "Refundable quantity" — initial value? deduction logic?
     - "Bind to store" — where is binding data stored? what login credentials?
     Add these implicit ambiguities to Pending Convergence Points.
7. **Supplementary Section**: If the requirement already contains discussion records, dependencies, technical constraints, or reference documents, pre-fill the corresponding Supplementary Section fields. Leave empty if none.
8. **Identification & Association**: Extract core functionality for Topic, name with brief phrase.
9. **🛑 Pause for participant review**. Present the drafted Collection to the participant, with `⚠` markers highlighted and a short list of "decisions I need you to make" at the top. Wait for the participant to resolve each marker (accept / correct / add pending point). Then flip status from "Draft" to "Collecting".
10. **Update or create batch overview**. If a `BATCH-OVERVIEW.md` exists, add this Collection to the inventory. If not, create one following `schema/batch-overview.md` and fill in the sections relevant to a single-Collection batch (metadata, inventory, any cross-system dependencies).

Constraints:
- File must be placed in the specified batch folder.
- Status starts as "Draft"; flips to "Collecting" only after participant review.
- Do not add information not present in the requirement.
- Do not prematurely converge rules that are not yet confirmed.
- Prefer writing more Pending Convergence Points over writing uncertain content as Converged Rules.
- Every inferred-but-unstated field must carry a `⚠` marker so the participant sees it explicitly.

---

## Prompt 3: Convergence Discussion

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
   - Deferred item → move to Deferred Decisions in the Discussion & Decision Log.
9. **Update Dependencies**. If convergence involves cross-Collection relationship changes, update the batch-level `BATCH-OVERVIEW.md` (Cross-Collection Relationships diagram, Global Pending Convergence List, and any affected inventory rows).
10. **Convergence Completion Determination**. Status may be changed to "Converged" if and only if all of the following are satisfied:
    - Granularity check fully passed (every "Then" is verifiable)
    - All Pending Convergence Points cleared (converted to rules or marked as deferred decisions)
    - Convergence Checklist fully checked off
11. **Flip status and sync batch overview**. Flip each converged Collection's status to "Converged" and update the corresponding inventory row and Global Pending Convergence List in `BATCH-OVERVIEW.md`.

Constraints:
- Do not write any decision into the Collection until the participant has explicitly decided. AI suggestions remain suggestions until accepted.
- Do not delete any existing discussion and decision records.
- Suggested solutions must be marked as "AI Suggestion".
- Prefer extending the convergence cycle over marking as "Converged" with insufficient granularity.
- Every change to a Collection must be reflected in the batch overview (inventory status, pending list, relationships) in the same pass.

---

## Prompt 4: Generate Tech Design

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

Mapping table (Collection → Tech Design):
- Topic → Name
- Applicability → Applicability (supplement technical boundaries)
- Converged Rules.Scenario → Scenario Mapping & Solution-Level Full Investigation (at least one complete technical path per scenario)
- Converged Rules.Given → API preconditions, request parameters
- Converged Rules.When → API endpoint trigger
- Converged Rules.Then → API response, postconditions, side effects
- Converged Rules.Scenario → API Contracts (at least one endpoint per scenario, derived from Step 4 investigation conclusions)
- Dependencies.External Systems → External System Integration
- Technical Constraints → Technical Constraints (inherited & supplemented)
- Scenario Mapping & Solution-Level Full Investigation.Conclusions → Technical Strategy, Metrics, Data Models, API Contracts, External System Integration
- Scenario Mapping & Solution-Level Full Investigation.Conclusions → Fallback Strategy.Degradation Plans and Omission Risks
- All Converged Rules → Fallback Strategy.Coverage Matrix (line-by-line verification)
- Technical Constraints + business scenario characteristics + investigation conclusions → Metrics (performance, quality, capacity)

Constraints:
- Output file must be placed in the tech-design subfolder with the same name as the collection batch.
- Design mode must be confirmed in Step 0; greenfield and brownfield Step 1 contents differ and must not be mixed.
- Every Collection scenario must have a corresponding entry in Scenario Mapping, API Contracts, and Coverage Matrix.
- Do not add business rules not present in the Collection, but technical-level decisions are allowed.
- Data models must be specified down to field level; API contracts must be specified down to request/response field level.
- Technical strategy must include overall roadmap and key decisions, each with alternatives and rationale; greenfield decisions must be fully reasoned from first principles.
- Metrics must provide specific numbers; vague descriptions are not accepted.
- Scenario mapping & solution-level full investigation must cover all three dimensions (end-to-end flow, component interaction, data flow); every step must be at an auditable level of granularity (with input/output/failure conditions/involved components); brownfield must tag each step as "reuse / modify / add new".
- The fallback strategy coverage matrix must be verified line by line; skipping is not allowed. Degradation plans and omission risks must be grounded in the full investigation conclusions; skipping the investigation and writing fallback directly is not allowed.
- Step 13 cross-cutting consistency review must be executed; any inconsistency found must be revised and the revision rationale recorded; skipping is not allowed.

---

## Prompt 5: Generate Implementation Plan

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

Mapping table (Tech Design → Implementation):
- Name → Name
- Applicability → Applicability
- API Contracts → Interface (input/output/error codes)
- API Contracts.Preconditions → Business Constraints.Preconditions
- API Contracts.Postconditions → Business Constraints.Postconditions
- API Contracts.Side Effects → Business Constraints.Side Effects
- Scenario Mapping.Common Constraints → Business Constraints.Invariants
- External System Integration → Dependencies.External Systems
- Scenario Mapping.Call Chains → Dependencies.Preceding Skill, Follow-up Skill, Collaboration Mode
- Error Handling Strategy → Development Constraints.Retry & Degradation
- Technical Constraints → Development Constraints
- Implementation Order → Changes.Sequence
- Data Models.Structure → Changes.Structural Requirements (type definitions)
- API Contracts.Endpoint → Changes.Structural Requirements (function signatures)
- Scenario-to-Technical-Path Mapping → Verification (linked to change items and functions)

Constraints:
- Output file must be placed in the implementation subfolder with the same name as the tech-design batch.
- Every structural requirement in the change list must have a corresponding entry in the Tech Design's API Contracts or Data Models.
- Do not add technical decisions not present in the Tech Design.
- Verification cases must correspond one-to-one with Tech Design's Scenario Mappings.
