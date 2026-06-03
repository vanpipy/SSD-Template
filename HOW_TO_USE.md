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

implementation/
├── {date}-{short-topic}/           # Batch folder
│   ├── impl-01-xxx.md             # Implementation files
│   └── code/                      # Generated code (optional)
```

- **Batch folder naming**: `{YYYY-MM-DD}-{short-topic}`
- **Each batch** contains: all files generated from this input + dependency matrix
- **Dependency matrix**: batch-level for intra-batch dependencies, global for cross-batch

## Use Cases

Scenario A: You have a single requirement, create a Collection directly. Go through steps 1-5.

Scenario B: You have a meeting summary containing multiple requirements. Split it into multiple Collections first, then converge individually. Go through steps 0-5.

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

### 3. Step 3 - Generate Implementation Plan

Input is a Collection file with status "Converged". Output is an Implementation file placed in `implementation/{date}-{short-topic}/`, status "Draft".

How to use:
1. Create a batch folder under `implementation/` with the same name as the collection batch
2. Use prompt [Prompt 4: Generate Implementation Plan]

### 4. Step 4 - Review Implementation Plan

Input is an Implementation file with status "Draft". Output is the same file with status changed to "Ready".

After AI generates the Implementation draft, you need to review it. Focus on: complete interface parameters, accurate hard constraints, verification cases covering core paths. After approval, change status from "Draft" to "Ready", and change the corresponding Collection's status from "Converged" to "Completed". Also backfill the Implementation file path into the Collection's Related Implementation field.

### 5. Step 5 - Execute Implementation

Input is an Implementation file with status "Ready", plus current project context such as codebase path and tech stack description.

**Trigger command:**
```
/execute implementation {path-to-impl-file}
```

Agent will read the Implementation file and execute according to the guidance within.

### Supplementary: Modify Existing Implementation Plan

1. If an Implementation with status "Draft" needs modification, edit it directly.
2. If an Implementation with status "Ready" or "Completed" needs modification, do not edit it directly. Go back to Step 1, create a new Collection. Fill in the Related Implementation field with the path to the Implementation to be modified, and clearly state the topic of what needs changing. After convergence, send the new Collection and old Implementation together to AI, use Prompt 4 to generate a new version. After approval, the new version status becomes "Ready", and the old version is kept in the change log.

---

## Input/Output Quick Reference

Scenario A: Single requirement entry.
Step 1 Create Collection. Input: raw requirement, output: Collection file with status "Collecting" (in batch folder).
Step 2 Convergence. Input: Collection file with status "Collecting", output: same file with status "Converged".
Step 3 Generate Plan. Input: Collection file with status "Converged", output: Implementation file with status "Draft" (in batch folder).
Step 4 Review. Input: Implementation file with status "Draft", output: same file with status "Ready".
Step 5 Execute. Input: Implementation file with status "Ready", output: implementation code.

Scenario B: Meeting summary entry.
Step 0 Split. Input: meeting summary, output: multiple Collection files with status "Collecting" (in same batch folder).
Each subsequent step executes independently for each Collection, same as Scenario A.

Related Files

- Collection template: schema/collection.md
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
3. Fill template. For each requirement, generate a Collection file following schema/collection.md format. Preserve original text in Original Request field without rewriting. Fill Converged Rules based on explicit conclusions in the summary, leave empty if no conclusion. Fill Pending Convergence Points with issues mentioned but not resolved in the summary.
4. Annotate dependencies. Analyze invocation and dependency relationships between requirements, annotate in each Collection's Dependencies field.
5. Generate matrix. Generate DEPENDENCY-MATRIX.md in the batch folder, format: RequirementA → depends on → RequirementB, list each line clearly.

Constraints:
- All output files must be placed in the batch folder.
- Each Collection's status field must be set to "Collecting".
- Do not add content not present in the summary.
- If a requirement has absolutely no details in the summary, still generate a Collection but only fill Topic and Original Request, leave others empty.

---

## Prompt 2: Create Single Collection

Input: A raw requirement description, can be natural language.
Output: A Collection file with status "Collecting", placed in batch folder `collection/{date}-{short-topic}/`.

Prompt content:

Task: Convert raw requirement into a Collection file.

Steps:
1. Create file following schema/collection.md format in the batch folder.
2. Extract core functionality from requirement for Topic field, name with brief phrase.
3. Preserve user's original text in Original Request field without rewriting.
4. Infer scope based on requirement content for Discussion Scope field (in scope and out of scope).
5. Fill Converged Rules field only with scenarios that have explicit conclusions in the requirement, using Given/When/Then format. Leave empty if no conclusion.
6. Extract ambiguous, uncertain, pending confirmation content into Pending Convergence Points, divided into "Requires Human Decision" and "AI Can Attempt Convergence" categories.
7. Set status to "Collecting".

Constraints:
- File must be placed in the specified batch folder.
- Do not add information not present in the requirement.
- Do not prematurely converge rules that are not yet confirmed.

---

## Prompt 3: Convergence Discussion

Input: A Collection file with status "Collecting" or previously existed but needs further convergence.
Output: Updated same Collection file. If cross-Collection dependency changes are involved, update the batch-level DEPENDENCY-MATRIX.md.

Prompt content:

Task: Analyze Collection file, assist in completing requirement convergence.

Steps:
1. Analyze pending convergence points. Check each issue in "Requires Human Decision" and "AI Can Attempt Convergence". For AI-can-attempt issues, provide suggested solutions with rationale. For human-decision issues, point out blocking points and possible impact scope.
2. Identify gaps. Check if Converged Rules cover all major scenarios within the applicable scope, including normal paths, boundary conditions, and exception paths. If gaps found, supplement in Pending Convergence Points.
3. Check consistency. Check for logical contradictions between Converged Rules. Check consistency between Applicability and Converged Rules.
4. Generate follow-up questions. List key questions needing human confirmation, each with context and AI suggestions.
5. Update dependencies. If convergence involves cross-Collection dependency changes, update the batch-level DEPENDENCY-MATRIX.md.

Constraints:
- Do not modify content requiring human decision without authorization.
- Do not delete any existing discussion and decision records.
- Suggested solutions must be marked as "AI Suggestion".

---

## Prompt 4: Generate Implementation Plan

Input: A Collection file with status "Converged".
Output: An Implementation file with status "Draft", placed in `implementation/{date}-{short-topic}/`.

Prompt content:

Task: Convert a converged Collection into an Implementation file.

Steps:
0. Check prerequisites. If the target repository is not specified in the input context, ask the user: "Which repository should this implementation target?" Do not proceed without this information.
1. Read input. Read all fields of the Collection file.
2. Fill identification. Extract Skill name from Topic field, summarize one-sentence description from Converged Rules. Set version to 1.0.0, status to "Draft", backfill Collection file path in Source field.
3. Fill applicability. Map directly from Collection's Applicability field.
4. Infer interfaces. Extract input parameters and output results from Converged Rules' Given/When/Then. Conditions in Given are part of input, actions in When trigger input, results in Then are output.
5. Map business constraints. Given corresponds to preconditions, Then corresponds to postconditions, common constraints across multiple scenarios generalize to invariants, state changes and external operations in Then correspond to side effects.
6. Map dependencies. Map directly from Collection's Dependencies field. If empty, infer possible dependencies based on business constraints.
7. Map development constraints. Map directly from Collection's Technical Constraints field. If empty, infer necessary concurrency strategy, transaction boundary, and idempotency requirements based on business constraints.
8. Fill verification. Generate one verification case for each scenario in Converged Rules. Scenario name corresponds to verification description, Then corresponds to expected result. Add additional boundary and exception scenario verifications.
9. Fill implementation strategy. Default test-first is "No", behavior-driven is "Yes".
10. Fill change log. Add initial version record.
11. Backfill association. After generation, backfill Implementation file path into Collection's Related Implementation field.

Mapping table (Collection → Implementation):
- Topic → Name
- Converged Rules summary → Description
- Applicability.Applicable → Applicability.Applicable
- Applicability.Not Applicable → Applicability.Not Applicable
- Given → Preconditions
- When → Interface input parameter source
- Then → Postconditions, side effects, output inference source
- Common constraints across scenarios → Invariants
- Dependencies.Other Skills → Preceding Skill, Follow-up Skill
- Dependencies.External Systems → External Systems
- Technical Constraints → Development Constraints
- Converged Rules.Scenario Name → Verification

Constraints:
- Output file must be placed in the implementation subfolder with the same name as the collection batch.
- Do not add rules not present in the Collection.
- Interface parameters must have corresponding evidence in the Converged Rules scenarios.
- Verification cases must correspond one-to-one with Converged Rules scenarios.
