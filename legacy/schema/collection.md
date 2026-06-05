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
> This template is a single required section. All fields should be filled when creating a collection (by agent draft + participant review).

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

---

## Identification & Association

> Administrative information. Fill at creation time.

- Topic: [One-sentence description of the core issue for this collection]
- Status: [Collecting | Converged | Completed]
  - **Collecting**: Agent has drafted; participant is reviewing / convergence discussion in progress.
  - **Converged**: All rules verifiable, all pending points resolved.
  - **Completed**: Downstream artifacts (Tech Design / Implementation) have consumed this Collection.
- Created Date: [YYYY-MM-DD]
- Target Repository: [Git repository URL or local path; fill if known, otherwise confirmed during tech design generation]

---

## Lightweight Mode (for small batches)

> When a batch contains **≤ 4 independent requirements AND no cross-role / cross-system coupling**, the agent may produce a simplified Collection:
> - Merge related scenarios into a single Collection rather than splitting by capability.
> - Pending Convergence Points may be a flat bullet list without per-rule "Blocks" annotation (still encouraged but not required).
>
> The batch-level BATCH-OVERVIEW is still produced, but in simplified form (inventory table + relationship diagram only, no theme grouping or global pending list).
> The agent must explicitly state "Using lightweight mode because: [reason]" at the top of the BATCH-OVERVIEW when this applies.
