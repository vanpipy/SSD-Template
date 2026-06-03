# Batch Overview: [Topic]

> **Perspective: The Agent executing Prompt 1 (Split Meeting Summary)**
> The batch overview is **the Agent's artifact from splitting the meeting summary**, not a file participants actively maintain.
> - In Prompt 1, the Agent is responsible for: splitting Collections, generating the batch overview, and maintaining cross-Collection relationships.
> - Participants only glance at it during review to confirm the split is reasonable; ongoing maintenance is the Agent's job.
> - Downstream Agents (Prompt 3 Convergence Discussion, Prompt 4 Generate Tech Design) read the batch overview as global context to understand cross-Collection relationships.
> - One batch has exactly one batch overview, kept in sync by the Agent as Collections change.

> This template is divided into **Required Section** and **Supplementary Section**.
> - **Required Section**: Must be filled by the Agent when creating the batch.
> - **Supplementary Section**: Filled by the Agent progressively as Collections converge.

---

## Required Section

### Batch Metadata

- Topic: [One-sentence description of the core issue for this batch]
- Created Date: [YYYY-MM-DD]
- Source: [Meeting summary path / requirement document path / other source]
- Participants: [List of participants in the discussion]
- Target Repository: [Git repository URL or local path; leave empty if unknown, confirmed during tech design generation]

### Collection Inventory

> All Collections in this batch, one row per Collection. Status is kept in sync with each Collection.

| ID | File Path | Topic | Status | Summary |
|----|-----------|-------|--------|---------|
| C01 | [path] | [topic] | [Collecting / Converged / Completed] | [One-sentence summary] |
| C02 | [path] | [topic] | [status] | [summary] |
| ... | ... | ... | ... | ... |

### Cross-Collection Relationships

> Describe invocation / dependency / sharing relationships between Collections. Prefer a simple diagram; add textual explanation only for complex cases.

```
[C01] --[relationship type, e.g., "prerequisite / data-sharing / invocation"]--> [C02]
```

#### Relationship Type Key
- **Prerequisite**: A must be completed before B can start
- **Data Sharing**: A and B read/write the same data/model
- **Invocation**: A directly triggers B in the business flow
- **Mutually Exclusive**: A and B do not occur together

### Global Pending Convergence List

> Aggregated unresolved ambiguities from all Collections, with source links. Participants consult this list for focused discussion instead of opening each Collection.

| Source | Pending Point | Blocks |
|--------|---------------|--------|
| [C01#point1] | [question description] | [which rule's convergence is blocked] |
| [C02#point3] | [question description] | [blocks] |
| ... | ... | ... |

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
