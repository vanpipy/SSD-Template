# Collection: [Topic]

> **Perspective: Participant**
> Collection is designed for the people who participated in the requirement discussion. Your goal is to capture what was agreed upon and flag what is still unclear.
> - Write what you actually know. Don't fabricate content just to fill a field.
> - Given/When/Then is a tool to help you discover "did I actually think this through", not a formatting requirement. If you can't write a concrete Then, put it in Pending Convergence Points instead.
> - Low barrier to create: four required fields, fill as much as you can, complete the rest during convergence.

> This template is divided into **Required Section** and **Supplementary Section**.
> - **Required Section**: Must be filled when creating a collection. This is the core content of the Collection.
> - **Supplementary Section**: Filled progressively during convergence discussions. Not required at creation time.

---

## Required Section

### Original Request

[The original statement from the user or the initial description from the requirement source. Preserve original context and wording — no rewriting. Can be a paragraph, a sentence, or even a complaint.]

### Discussion Scope
- In Scope: [Business domains and functional boundaries covered by this discussion]
- Out of Scope: [Explicitly excluded content. If the meeting or requirement explicitly states "we won't do this", "not in phase 1", "not our responsibility", it must be written here]

### Converged Rules

> Each rule describes a specific business scenario. The "Then" must contain verifiable concrete conditions — vague descriptions like "complete XX" or "support XX" are not allowed.
> If you cannot write concrete conditions, the rule has not yet converged — move it to Pending Convergence Points instead.

#### Scenario: [Scenario Name]
- Given [Precondition — what triggers this]
- When [Trigger action — who did what]
- Then [Expected result — what specific change does the system produce, verifiable]

#### Scenario: [Scenario Name]
- Given [...]
- When [...]
- Then [...]

### Pending Convergence Points

> Record all unresolved ambiguities. Each point must state what it blocks — which rule cannot converge until this is resolved.

#### Requires Human Decision
- [Question] — Blocks: [which rule's convergence is blocked by this question]

#### AI Can Attempt Convergence
- [Question] — Blocks: [which rule's convergence is blocked by this question] — AI Suggestion: [AI's suggested approach based on existing context, marked as "AI Suggestion"]

---

## Convergence Checklist

> Before changing status to "Converged", verify each item. Status may only change when all items are satisfied.

- [ ] Every "Then" contains verifiable concrete conditions (no vague descriptions like "complete XX" or "support XX")
- [ ] Major scenarios within scope are covered (normal path + at least one exception path)
- [ ] All Pending Convergence Points have been resolved (decisions made and converted to rules, or explicitly marked as deferred)
- [ ] No logical contradictions between Converged Rules
- [ ] Dependencies are confirmed (filled in or explicitly marked "None")

---

## Supplementary Section

> The following sections are filled progressively during convergence discussions. They may be pre-filled if information is already available at creation time, but this is not required.

### Discussion & Decision Log

#### Clarification Q&A
- Q: [Key question]
- A: [Clear answer]
- Impact: [Which rule or direction this answer influences]

#### Rejected Options
- [Option discussed but decided against] — Rejection Reason: [Why not]

#### Deferred Decisions
- [Item not processed now, deferred to future versions] — Reason: [Why deferred]

### Dependencies
- Dependencies on Other Features: [Preceding or follow-up dependencies mentioned in discussion, e.g., "requires C01 login binding to be completed first"]
- Dependencies on External Systems: [External interfaces or services mentioned in discussion, e.g., "payment gateway"]

### Technical Constraints
- [Technical limitations, performance requirements, security requirements mentioned in discussion]

### Reference Documents
- [Document Name]: [Link or path] — [Brief description of what this document provides]

---

## Identification & Association

> Administrative information. Fill the first three items at creation time; the rest are backfilled in subsequent workflow steps.

- Topic: [One-sentence description of the core issue for this collection]
- Status: [Collecting | Converged | Completed]
- Created Date: [YYYY-MM-DD]
- Participants: [List of participants in the discussion]
- Related Tech Design: [Backfill path after Tech Design is generated]
- Related Implementation: [Backfill path after Implementation is generated]
- Target Repository: [Git repository URL or local path; fill if known, otherwise confirmed during tech design generation]
