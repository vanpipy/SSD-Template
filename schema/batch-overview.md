# Batch Overview: [Topic]

> **Perspective: The Agent that splits the batch (Prompt 1 / Prompt 2)**
> The batch overview is **the Agent's working artifact**, produced when splitting input into Collections. It serves three audiences:
> - **Participant (Reviewer)**: Reads the overview once after the Agent proposes a split, to confirm the split is reasonable (right number, right boundaries, right relationships). Does not maintain it ongoing.
> - **Convergence Agent (Prompt 3)**: Reads it as global context to understand cross-Collection coupling during convergence discussions.
> - **Tech Design Agent (Prompt 4)**: Reads it to understand shared data models, infrastructure, and architectural constraints before diving into a single Collection.
>
> One batch has exactly one batch overview, kept in sync by the Agent as Collections change.

> This template is divided into **Required Section** and **Supplementary Section**.
> - **Required Section**: Must be filled by the Agent when creating the batch.
> - **Supplementary Section**: Filled by the Agent progressively as Collections converge.

---

## Draft Review Protocol

> The batch overview is produced in two passes, with an explicit review checkpoint between them.

**Pass 1 — Agent proposes split (status: Draft)**
1. Agent reads the input (meeting summary / requirement set).
2. Agent applies the split/merge decision principles from Prompt 1 Step 1.
3. Agent drafts the **Batch Metadata + Collection Inventory + Cross-Collection Relationships** sections only (not yet the global pending list).
4. Agent presents to the participant:
   - The proposed split count and rationale.
   - The Collection Inventory table.
   - The Cross-Collection relationship diagram.
   - A short list of "Split decisions I'm unsure about" (if any).

**Checkpoint — Participant reviews**
- The participant either (a) accepts the split as-is, (b) asks for merges/splits (e.g., "C03 and C04 should be one Collection"), or (c) asks for a lightweight-mode re-split.
- Agent adjusts the inventory and relationships per feedback.

**Pass 2 — Agent drafts Collections + global pending list (status: Collecting)**
1. Agent drafts each Collection per schema/collection.md, marking uncertain fields with `⚠`.
2. Agent produces the **Global Pending Convergence List** in the batch overview (aggregating pending points from all drafted Collections).
3. Agent produces the **Supplementary Section** (external dependencies, architecture decisions, themes) as far as the input allows.
4. Agent presents to the participant for a second review — this time on Collection *content*, not split structure.
5. Participant resolves `⚠` markers; status flips from Draft → Collecting on each reviewed Collection.

**Lightweight mode shortcut**: When triggered (see schema/collection.md), Pass 1 and Pass 2 may be combined into a single round because the split is trivially small. The Agent must still state the lightweight-mode rationale at the top of this file.

---

## Required Section

### Batch Metadata

- Topic: [One-sentence description of the core issue for this batch]
- Created Date: [YYYY-MM-DD]
- Source: [Meeting summary path / requirement document path / other source]
- Participants: [List of participants in the discussion]
- Mode: [Standard | Lightweight] — if Lightweight, state reason here
- Target Repository: [Git repository URL or local path; leave empty if unknown, confirmed during tech design generation]

### Collection Inventory

> All Collections in this batch, one row per Collection. Status is kept in sync with each Collection.

| ID | File Path | Topic | Status | Draft Origin | Summary |
|----|-----------|-------|--------|--------------|---------|
| C01 | [path] | [topic] | [Draft / Collecting / Converged / Completed] | [agent-prompt1 / agent-prompt2 / participant] | [One-sentence summary] |
| C02 | [path] | [topic] | [status] | [origin] | [summary] |
| ... | ... | ... | ... | ... | ... |

### Cross-Collection Relationships

> Describe invocation / dependency / sharing relationships between Collections. Prefer a simple diagram; add textual explanation only for complex cases.

```
[C01] --[relationship type]--> [C02]
```

#### Relationship Type Key
- **prerequisite**: A must be completed before B can start (ordering)
- **data-sharing**: A and B read/write the same data/model
- **invocation**: A directly triggers B in the business flow
- **constraint**: A's decision or rule restricts B's design space (e.g., architecture decision constraining a scenario)
- **alternative**: A and B are mutually exclusive options for the same problem (only one will be chosen)
- **mutually-exclusive**: A and B do not occur together at runtime (different from "alternative" — both may exist, just not in the same execution)

### Global Pending Convergence List

> Aggregated unresolved ambiguities from all Collections, with source links and priority. Participants consult this list for focused discussion instead of opening each Collection.

#### Priority Key
- **P0**: Blocks Tech Design from starting (e.g., core architecture decision, foundational data model)
- **P1**: Blocks one or more Converged Rules but does not block the whole batch
- **P2**: Polish / edge case — can be deferred without blocking downstream work

| Priority | Source | Pending Point | Blocks |
|----------|--------|---------------|--------|
| [P0 / P1 / P2] | [C01#point1] | [question description] | [which rule's convergence is blocked] |
| [priority] | [C02#point3] | [question description] | [blocks] |
| ... | ... | ... | ... |

---

## Supplementary Section

> Filled progressively as Collections converge. May be pre-filled if the source material provides this information directly.

### External Dependency Summary

> All external systems / interfaces mentioned across Collections, deduplicated and centralized.

| External System | Collections Involved | Brief Purpose |
|-----------------|----------------------|---------------|
| [system name] | [C01, C05, ...] | [why dependent] |

### Architecture Decision Summary

> All architecture decisions recorded across Collections, centralized for holistic review.

| Decision Name | Source | Choice | Brief Rationale |
|---------------|--------|--------|-----------------|
| [decision] | [C02] | [final choice] | [why] |

### Batch-Level Themes

> Cross-cutting themes that don't fit in a single Collection but affect the entire batch.

- **Shared Data Models**: [core entities shared across multiple Collections, e.g., "order / member / store"]
- **Shared Infrastructure**: [external systems / middleware / auth shared across Collections]
- **Global Constraints**: [constraints affecting the whole batch, e.g., "must support offline"]
- **Batch-Level Risks**: [cross-Collection systemic risks]
