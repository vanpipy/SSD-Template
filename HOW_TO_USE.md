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
│   └── DEPENDENCY-MATRIX.md       # Batch-level dependency matrix
└── DEPENDENCY-MATRIX.md           # Global dependency matrix (optional)

tech-design/
├── {date}-{short-topic}/           # Batch folder
│   └── td-01-xxx.md               # Tech Design files

implementation/
├── {date}-{short-topic}/           # Batch folder
│   ├── impl-01-xxx.md             # Implementation files
│   └── code/                      # Generated code (optional)
```

- **Batch folder naming**: `{YYYY-MM-DD}-{short-topic}`
- **Each batch** contains: all files generated from this input + dependency matrix
- **Dependency matrix**: batch-level for intra-batch dependencies, global for cross-batch

## Use Cases

Scenario A: You have a single requirement, create a Collection directly. Go through steps 1-6.

Scenario B: You have a meeting summary containing multiple requirements. Split it into multiple Collections first, then converge individually. Go through steps 0-6.

## Workflow

### 0. Scenario B Entry: Step 0 - Split Meeting Summary

For Scenario B. Input is a meeting summary, either manually recorded or AI-generated. Output is multiple Collection files, each corresponding to an independent requirement point, placed in `collection/{date}-{short-topic}/`, all with status "Collecting".

How to use:
1. Determine batch folder name based on input source
2. Use prompt [Prompt 1: Split Meeting Summary]

### 1. Scenario A Entry: Step 1 - Create Single Collection

If you only have one requirement, start here. Input is a raw requirement description. Output is a Collection file placed in `collection/{date}-{short-topic}/`, status "Collecting".

How to use:
1. Determine batch folder name based on input source
2. Use prompt [Prompt 2: Create Single Collection]

### 2. Step 2 - Convergence Discussion

Input is a Collection file created in Step 0 or Step 1 (located in batch folder). Output is the same file with status changed to "Converged", all ambiguity points resolved.

How to use: Use prompt [Prompt 3: Convergence Discussion]

For multiple Collections split from Step 0, maintain their dependencies. If converging one Collection affects another, update the other's dependency fields and the batch-level DEPENDENCY-MATRIX.md.

### 3. Step 3 - Generate Tech Design

Input is a Collection file with status "Converged", plus the target repository's technical context. Output is a Tech Design file placed in `tech-design/{date}-{short-topic}/`, status "Draft".

Tech Design is the bridge between Collection (business rules) and Implementation (code-level instructions). It translates Given/When/Then business scenarios into concrete API contracts, data models, and technical execution paths, providing direct input for the Implementation change list.

How to use:
1. Create a batch folder under `tech-design/` with the same name as the collection batch
2. Use prompt [Prompt 4: Generate Tech Design]

Review focus: Do API contracts cover all business scenarios? Are data model fields complete? Do architecture decisions have alternatives and rationale? Is the scenario-to-technical-path mapping complete? After approval, change status from "Draft" to "Ready", and backfill the Tech Design file path into the Collection's Related Tech Design field.

### 4. Step 4 - Generate Implementation Plan

Input is a Tech Design file with status "Ready". Output is an Implementation file placed in `implementation/{date}-{short-topic}/`, status "Draft".

How to use:
1. Create a batch folder under `implementation/` with the same name as the collection batch
2. Use prompt [Prompt 5: Generate Implementation Plan]

### 5. Step 5 - Review Implementation Plan

Input is an Implementation file with status "Draft". Output is the same file with status changed to "Ready".

After AI generates the Implementation draft, you need to review it. Focus on: whether the change list's structural requirements are consistent with the Tech Design's API contracts and data models, and whether verification cases cover core paths. After approval, change status from "Draft" to "Ready", change the corresponding Collection's status from "Converged" to "Completed", and backfill the Implementation file path into the Collection's Related Implementation field.

### 6. Step 6 - Execute Implementation

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
Step 1 Create Collection. Input: raw requirement, output: Collection file with status "Collecting" (in batch folder).
Step 2 Convergence. Input: Collection file with status "Collecting", output: same file with status "Converged".
Step 3 Generate Tech Design. Input: Collection file with status "Converged", output: Tech Design file with status "Draft" (in batch folder).
Step 4 Generate Plan. Input: Tech Design file with status "Ready", output: Implementation file with status "Draft" (in batch folder).
Step 5 Review. Input: Implementation file with status "Draft", output: same file with status "Ready".
Step 6 Execute. Input: Implementation file with status "Ready", output: implementation code.

Scenario B: Meeting summary entry.
Step 0 Split. Input: meeting summary, output: multiple Collection files with status "Collecting" (in same batch folder).
Each subsequent step executes independently for each Collection, same as Scenario A.

Related Files

- Collection template: schema/collection.md
- Tech Design template: schema/tech-design.md
- Implementation template: schema/implementation.md

---

## Prompt 1: Split Meeting Summary

Input: Meeting summary, can be pasted full text or local file path.
Output: Multiple Collection files and dependency matrix, placed in batch folder `collection/{date}-{short-topic}/`.

Prompt content:

Task: Analyze meeting summary, identify independent requirements, generate Collection files.

Steps:
1. Extract requirements. Scan the summary text, find all independent functional or capability requirements. Each requirement must have clear boundaries, non-overlapping and complete.
2. Determine granularity. If a requirement involves multiple different business scenarios or has excessive complexity product, split it into multiple sub-requirements.
3. Fill template. For each requirement, generate a Collection file following schema/collection.md format:
   - Required Section:
     - Original Request: Preserve original text from the summary without rewriting.
     - Discussion Scope: Infer Focus from summary content; Not Applicable must be explicitly stated — extract from exclusions in the summary or common-sense boundaries, at least one entry.
     - Converged Rules: Only fill scenarios with explicit conclusions in the summary, using Given/When/Then format. Then must contain verifiable specific conditions — vague descriptions like "complete XX" are not accepted. Leave empty if no conclusion.
     - Pending Convergence Points: Beyond explicitly unresolved issues in the summary, also extract implicit ambiguities — vague verbs (handle, optimize, improve), undefined business terms, implied exception scenarios, operations with unspecified roles or permissions. Each point must state what it blocks.
   - Supplementary Section: Fill Discussion & Decision Log, Dependencies, Technical Constraints from whatever can be extracted from the summary; leave empty if nothing is extractable.
4. Annotate dependencies. Analyze invocation and dependency relationships between requirements, annotate in each Collection's Dependencies field.
5. Generate matrix. Generate DEPENDENCY-MATRIX.md in the batch folder, format: RequirementA → depends on → RequirementB, list each line clearly.

Constraints:
- All output files must be placed in the batch folder.
- Each Collection's status field must be set to "Collecting".
- Do not add business content not present in the summary.
- If a requirement has absolutely no details in the summary, still generate a Collection but only fill Original Request, leave others empty.
- All four Required Section fields must not be left empty (except Converged Rules, which may be empty if no conclusions exist).

---

## Prompt 2: Create Single Collection

Input: A raw requirement description, can be natural language.
Output: A Collection file with status "Collecting", placed in batch folder `collection/{date}-{short-topic}/`.

Prompt content:

Task: Convert raw requirement into a Collection file. Focus on filling the Required Section; pre-fill Supplementary Section as needed.

Steps:
1. Create file following schema/collection.md format in the batch folder.
2. **Original Request**: Preserve user's original text without rewriting.
3. **Discussion Scope**:
   - In Scope: Infer business domain and functional boundaries from requirement content.
   - Out of Scope: If the requirement or meeting explicitly excludes certain features (e.g., "not in phase 1", "not our responsibility"), they must be listed here. If no explicit exclusions, write "No explicit exclusions yet".
4. **Converged Rules**: Only fill scenarios with explicit conclusions, using Given/When/Then format. The "Then" must contain verifiable concrete conditions. If a rule's "Then" can only be written as a vague description like "complete XX" or "support XX", it has not converged — do not add it to Converged Rules, move it to Pending Convergence Points instead.
5. **Pending Convergence Points**: Fill in two categories, each point noting which rule it blocks.
   - Explicit ambiguities: Uncertainties explicitly mentioned in the requirement (e.g., "to be decided later", "not yet confirmed").
   - Implicit ambiguities: For each written "Then", check whether there are implied technical or business details not yet clarified. For example:
     - "Refund via original payment method" — refund time window? partial refund?
     - "Refundable quantity" — initial value? deduction logic?
     - "Bind to store" — where is binding data stored? what login credentials?
     Add these implicit ambiguities to Pending Convergence Points.
6. **Supplementary Section**: If the requirement already contains discussion records, dependencies, technical constraints, or reference documents, pre-fill the corresponding Supplementary Section fields. Leave empty if none.
7. **Identification & Association**: Extract core functionality for Topic, name with brief phrase. Set status to "Collecting".

Constraints:
- File must be placed in the specified batch folder.
- Do not add information not present in the requirement.
- Do not prematurely converge rules that are not yet confirmed.
- Prefer writing more Pending Convergence Points over writing uncertain content as Converged Rules.

---

## Prompt 3: Convergence Discussion

Input: A Collection file with status "Collecting" or previously existed but needs further convergence.
Output: Updated same Collection file. If cross-Collection dependency changes are involved, update the batch-level DEPENDENCY-MATRIX.md.

Prompt content:

Task: Analyze Collection file, assist in completing requirement convergence. The goal is to bring all Converged Rules to verifiable granularity and clear all Pending Convergence Points.

Steps:
1. **Granularity Check**. Review each Converged Rule's "Then":
   - If "Then" contains vague descriptions like "complete XX", "support XX", "implement XX" without verifiable concrete conditions, this rule is **not qualified**. Demote it to Pending Convergence Points, or split into finer sub-scenarios.
   - Qualified "Then" examples: "System returns 200 status code with order number", "Cart item quantity +1, total price recalculated".
   - Unqualified "Then" examples: "Binding completed", "Aggregate payment supported", "Order query successful".
2. **Analyze Pending Convergence Points**. Check each issue in "Requires Human Decision" and "AI Can Attempt Convergence". For AI-can-attempt issues, provide suggested solutions with rationale. For human-decision issues, point out blocking points and possible impact scope.
3. **Implicit Ambiguity Mining**. For each qualified rule, check once more: when implementing this rule, would a developer ask "how exactly?" If yes, add implicit ambiguity points. Common patterns:
   - Operations involving external systems — how to handle timeout? how to degrade on failure?
   - Operations involving data changes — how to handle concurrent writes? how to ensure idempotency?
   - Operations involving user input — what are the validation rules? how to respond to invalid input?
4. **Identify Gaps**. Check if Converged Rules cover all major scenarios within scope: at least one normal path + at least one exception path. If gaps found, supplement in Pending Convergence Points.
5. **Check Consistency**. Check for logical contradictions between Converged Rules. Check consistency between Discussion Scope and Converged Rules.
6. **Generate Follow-up Questions**. List key questions needing human confirmation, each with context and AI suggestions.
7. **Update Dependencies**. If convergence involves cross-Collection dependency changes, update the batch-level DEPENDENCY-MATRIX.md.
8. **Convergence Completion Determination**. Status may be changed to "Converged" if and only if all of the following are satisfied:
   - Granularity check fully passed (every "Then" is verifiable)
   - All Pending Convergence Points cleared (converted to rules or marked as deferred decisions)
   - Convergence Checklist fully checked off

Constraints:
- Do not modify content requiring human decision without authorization.
- Do not delete any existing discussion and decision records.
- Suggested solutions must be marked as "AI Suggestion".
- Prefer extending the convergence cycle over marking as "Converged" with insufficient granularity.

---

## Prompt 4: Generate Tech Design

Input: A Collection file with status "Converged" and target repository information.
Output: A Tech Design file with status "Draft", placed in `tech-design/{date}-{short-topic}/`.

Prompt content:

Task: Convert a converged Collection into a Tech Design file, completing the translation from business rules to technical contracts.

Steps:
0. Check prerequisites. If the target repository is not specified in the input context, ask the user: "Which repository should this tech design target?" Do not proceed without this information.
1. Scan repository. Read the target repository's Agent instruction files (AGENTS.md / CLAUDE.md / .cursorrules), tech stack, existing data models, API patterns, middleware, etc. Fill in the Repository Context.
2. Fill identification. Name consistent with Collection topic, version set to 1.0.0, status set to "Draft", source backfilled with Collection path.
3. Fill applicability. Inherit from Collection, supplement with technical boundaries (e.g., "covers API layer only, excludes UI").
4. Architecture decisions. For key design questions (storage, protocol, layering, etc.), list alternatives, selection, and rationale. Each decision must have at least two alternatives.
5. Define data models. Define data structures for each business entity down to field level, annotate field constraints and storage. Link back to Collection scenarios.
6. Define API contracts. Define interfaces for each user operation, including endpoint, request/response fields, pre/postconditions, side effects. Each API must link to a specific Collection scenario.
7. Map scenarios to technical paths. Map each Collection Given/When/Then scenario to concrete technical steps: which API is triggered → what is validated → which model is read/written → which external system is called → what is returned.
8. Define external system integrations. List all external systems requiring interaction with integration specifications.
9. Define error handling strategy. Unified error code system and degradation plans.
10. Plan implementation order. Order by dependency: foundation before application, data before interfaces.
11. Fill change log. Add initial version record.
12. Backfill association. Backfill Tech Design path into Collection's Related Tech Design field.

Mapping table (Collection → Tech Design):
- Topic → Name
- Applicability → Applicability (supplement technical boundaries)
- Converged Rules.Scenario → API Contracts (at least one endpoint per scenario)
- Converged Rules.Given → API preconditions, request parameters
- Converged Rules.When → API endpoint trigger
- Converged Rules.Then → API response, postconditions, side effects
- Dependencies.External Systems → External System Integration
- Technical Constraints → Technical Constraints (inherited & supplemented)
- Converged Rules.Scenario → Scenario-to-Technical-Path Mapping

Constraints:
- Output file must be placed in the tech-design subfolder with the same name as the collection batch.
- Every Collection scenario must have a corresponding entry in API Contracts and Scenario Mapping.
- Do not add business rules not present in the Collection, but technical-level decisions are allowed.
- Data models must be specified down to field level; API contracts must be specified down to request/response field level.
- Architecture decisions must include alternatives and rationale.

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
