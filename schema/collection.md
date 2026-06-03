# Collection: [Topic]

> **Perspective: Reviewer (Participant) + Drafter (Agent)**
> A Collection is a shared artifact between two roles:
> - **Agent (Drafter)**: Extracts facts from input (meeting summary, raw requirement, code), drafts the Collection with as much structure as possible, and marks anything uncertain with `⚠ Needs confirmation` so the participant knows where judgment is required.
> - **Participant (Reviewer + Decider)**: Verifies the draft against what was actually discussed, resolves the `⚠` markers, fills gaps the agent couldn't infer, and makes final calls on ambiguous points.
>
> This separation exists because the agent is good at structure and exhaustive extraction, but bad at knowing what was *actually agreed*. The participant is the source of truth for consensus.
>
> **Drafting principles (for the Agent)**:
> - Draft what you can ground in input. Mark anything you inferred but wasn't stated with `⚠`.
> - Given/When/Then is a tool to expose "did I think this through", not a formatting checkbox. If you can't write a concrete Then, put it in Pending Convergence Points.
> - Prefer more Pending Convergence Points over unverified Converged Rules.
>
> **Review principles (for the Participant)**:
> - You are not rewriting — you are verifying and deciding. If a draft is wrong, correct it. If it's right, remove the `⚠`. If it's missing something, add it.
> - Don't add facts that weren't discussed. If something is unclear, add a Pending Convergence Point rather than inventing an answer.
>
> This template is divided into **Required Section** and **Supplementary Section**.
> - **Required Section**: Must be filled when creating a collection (by agent draft + participant review). This is the core content.
> - **Supplementary Section**: Filled progressively during convergence discussions. Not required at creation time.

---

## Required Section

### Original Request

[The original statement from the user or the initial description from the requirement source. Preserve original context and wording — no rewriting. Can be a paragraph, a sentence, or even a complaint.]

### Discussion Scope
- In Scope: [Business domains and functional boundaries covered by this discussion]
- Out of Scope: [Explicitly excluded content. If the meeting or requirement explicitly states "we won't do this", "not in phase 1", "not our responsibility", it must be written here]

### Converged Rules

> Each rule describes an agreed-upon business/technical fact. Choose the format based on content type:
> - **Scenario** (user interaction / business flow) → Given/When/Then. The "Then" must contain verifiable concrete conditions — vague descriptions like "complete XX" or "support XX" are not allowed. If you cannot write concrete conditions, the rule has not yet converged — move it to Pending Convergence Points instead.
> - **Architecture Decision** (tech selection / pattern choice) → Decision/Options/Choice/Rationale.
> - **Business Constraint** (hard requirement that is not a scenario) → Natural language + scope of impact.

#### Scenario: [Scenario Name]
- Given [Precondition — what triggers this]
- When [Trigger action — who did what]
- Then [Expected result — what specific change does the system produce, verifiable]

#### Architecture Decision: [Decision Name]
- Decision: [The core question being decided]
- Options: [Alternatives that were discussed]
- Choice: [Final decision]
- Rationale: [Why this was chosen]

#### Business Constraint: [Constraint Name]
- Constraint: [Hard requirement that must be satisfied, described in natural language]
- Impact: [Which downstream rules/scenarios this constraint affects]

### Pending Convergence Points

> Record all unresolved ambiguities. Each point must state what it blocks — which rule cannot converge until this is resolved.

- [Question] — Blocks: [which rule's convergence is blocked by this question] — Notes: [any existing clues or possible directions, optional]

---

## Convergence Checklist

> Before changing status to "Converged", verify each item. Status may only change when all items are satisfied.

- [ ] Every Scenario "Then" contains verifiable concrete conditions (no vague descriptions like "complete XX" or "support XX")
- [ ] Every Architecture Decision has options and a rationale
- [ ] Every Business Constraint states its impact scope
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

> Administrative information. Fill the first four items at creation time; the rest are backfilled in subsequent workflow steps.

- Topic: [One-sentence description of the core issue for this collection]
- Status: [Draft | Collecting | Converged | Completed]
  - **Draft**: Agent has drafted; awaiting participant review.
  - **Collecting**: Participant has reviewed the draft; convergence discussion in progress.
  - **Converged**: All rules verifiable, all pending points resolved.
  - **Completed**: Downstream artifacts (Tech Design / Implementation) have consumed this Collection.
- Draft Origin: [agent-prompt1 | agent-prompt2 | participant-written] — how this Collection was initially produced
- Created Date: [YYYY-MM-DD]
- Participants: [List of participants in the discussion]
- Related Tech Design: [Backfill path after Tech Design is generated]
- Related Implementation: [Backfill path after Implementation is generated]
- Target Repository: [Git repository URL or local path; fill if known, otherwise confirmed during tech design generation]

---

## Lightweight Mode (for small batches)

> When a batch contains **≤ 4 independent requirements AND no cross-role / cross-system coupling**, the agent may produce a simplified Collection:
> - Merge related scenarios into a single Collection rather than splitting by capability.
> - Pending Convergence Points may be a flat bullet list without per-rule "Blocks" annotation (still encouraged but not required).
> - Supplementary Section may be omitted entirely if nothing applies.
>
> The batch-level BATCH-OVERVIEW is still produced, but in simplified form (inventory table + relationship diagram only, no theme grouping or global pending list).
> The agent must explicitly state "Using lightweight mode because: [reason]" at the top of the BATCH-OVERVIEW when this applies.
