# Skill: [Skill Name]

> **Perspective: Executing Agent**
> Implementation is designed for the executing Agent. The Agent will execute each item in the change list sequentially, without guessing or supplementing.
> - Every structural requirement in the change list must include function/type signatures (in code blocks). Pure natural language descriptions are not accepted.
> - Verification cases must be linked to specific change items and functions. The Agent verifies against these after execution.
> - Repository context must be fully populated during the design phase. The Agent should encounter no "TBD" information at execution time.
> - The completion checklist is the Agent's delivery standard — all items must pass.

## Identification
- Name: [Skill Name]
- Description: [One-sentence description of what this skill does]
- Version: [Semantic version number]
- Status: [Draft | Ready | Deprecated]
- Source: [Path to the corresponding Tech Design file in the tech-design directory]

## Repository Context
- Agent Instruction Source: [Qoder three-level / CLAUDE.md / .cursorrules / None — list found file paths]
  - Qoder User-level: [~/.qoder/AGENTS.md exists? Key content summary]
  - Qoder Project-level: [AGENTS.md exists? Key content summary]
  - Qoder Local-level: [AGENTS.local.md exists? Key content summary]
  - Other Tools: [CLAUDE.md / .cursorrules etc.; omit if none]
  - Build Command: [Extracted from agent instruction files, e.g., `pnpm build`]
  - Test Command: [Extracted from agent instruction files, e.g., `pnpm test`]
  - Lint Command: [Extracted from agent instruction files, e.g., `pnpm lint --fix`]
  - Key Conventions: [Core rules extracted from agent instruction files, e.g., "functional components", "co-locate tests"]
  - Conflict Record: [Contradictions with change list and resolution decisions; write "None" if no conflicts]
- Tech Stack: [From scanning checklist step 1]
- Code Style: [Naming conventions, comment patterns, directory organization, from steps 2 and 7]
- Existing Interfaces: [Route definitions, type definitions, API specs location, from steps 3 and 4]
- Reference Implementation: [Similar module paths found in step 5]
- Test Conventions: [Test directory, framework, style reference, from step 6]
- Conflict Check: [Do the files in "Changes" conflict with existing code? If yes, describe resolution]

## Applicability
- Applicable: [When this skill should be used]
- Not Applicable: [When this skill should not be used; especially note scenarios where it could be misused]

## Interface
- Input:
  - [Parameter Name] ([Type], [Required | Optional]) - [Meaning], Example: [Example Value]
- Success Output: [Description of the return structure on success]
- Failure Output: [Description of the return structure on failure]
- Error Codes:
  - [Error Code]: [Error meaning]
  - [Error Code]: [Error meaning]

## Business Constraints
- Preconditions:
  1. [Conditions that must be satisfied before calling]
  2. [Conditions that must be satisfied before calling]
- Invariants: [Constraints that always hold during execution]
- Postconditions:
  1. [Conditions that must be satisfied after successful invocation]
  2. [Conditions that must be satisfied after successful invocation]
- Side Effects:
  1. [External state changes or operations triggered by the call]
  2. [Whether side effects occur on call failure; clarify explicitly]

## Dependencies
- Preceding Skill: [Other skills that need to be called first; write "None" if none]
- Follow-up Skill: [Other skills to call after successful execution; write "None" if none]
- External Systems: [External interfaces or services depended on, with timeout configuration]
- Collaboration Mode: [Sequential | Parallel | Chain of Responsibility | Pub/Sub | Other]

## Development Constraints
- Concurrency Strategy: [How to handle concurrent invocations, lock mechanisms or conflict detection used]
- Transaction Boundary: [Which operations must be within the same transaction, which are explicitly outside transaction scope]
- Idempotency: [How idempotency is guaranteed, what the unique key for deduplication is, behavior on duplicate requests]
- Retry & Degradation:
  1. [What triggers retry, retry count and interval]
  2. [How to handle retry failure, degradation strategy or compensation mechanism]
  3. [Boundary between async callbacks and sync waiting]
- Security Requirements:
  1. [Permission validation rules]
  2. [Data masking requirements]
  3. [Audit logging requirements]
- External System Constraints:
  1. [Timeout settings when calling external systems]
  2. [How to handle external system callbacks or async notifications]

## Implementation Strategy
- Test First: [Yes | No] — Whether to generate test cases based on the "Verification" section first, then write implementation code
- Behavior Driven: [Yes | No] — Whether to describe core scenarios in Given/When/Then format before implementation

## Changes

> Execute in order of sequence number. Each change item must be a minimal independently completable unit.
> The **Structural Requirements** field must list function/class/type signatures to be defined; natural-language-only descriptions are not allowed.
> If a signature is not yet determined, mark it in Open Decisions — do not invent one.

### Created

#### Change #1: [File Path]
- Sequence: [1, 2, 3, ... — determines implementation order]
- Dependencies: [None | Depends on Change #N — explain why]
- Structural Requirements:
  ```
  // Interfaces/types/function signatures to define (pseudocode or target language)
  interface XxxRequest {
    fieldA: string    // description
    fieldB: number    // description
  }

  function doXxx(request: XxxRequest): XxxResponse {
    // Responsibility: one-sentence description of what this function does
    // Does NOT: one-sentence description of explicitly excluded behavior
  }
  ```
- Business Rule Mapping: [Which preconditions/postconditions/invariants from Business Constraints]

#### Change #2: [File Path]
- Sequence: [...]
- Dependencies: [...]
- Structural Requirements:
  ```
  ...
  ```
- Business Rule Mapping: [...]

### Modified

#### Change #N: [File Path]
- Sequence: [...]
- Dependencies: [None | Depends on Change #M]
- Modification Target: [Function name / class name / line range]
- Modification Content:
  ```
  // Before (key snippet)
  function existingFn(...) { ... }

  // After (key snippet)
  function existingFn(...newParam: Type) { ...new logic... }
  ```
- Impact Scope: [Which callers are affected? Do they need synchronous updates?]
- Business Rule Mapping: [...]

### Deleted

#### Change #N: [File Path]
- Sequence: [...]
- Deletion Reason: [...]
- Reference Cleanup: [Which references to this file need cleanup after deletion?]

## Verification

> Each verification case must be linked to a specific change item and function, ensuring traceability to implementation code.

### V1: [Scenario Name]
- Related Change: [Change #N]
- Related Function: [Function name]
- Given: [Precondition]
- When: [Operation]
- Then: [Expected Result]

### V2: [Scenario Name]
- Related Change: [Change #N]
- Related Function: [Function name]
- Given: [Precondition]
- When: [Operation]
- Then: [Expected Result]

### V3: [Boundary/Exception Scenario]
- Related Change: [Change #N]
- Related Function: [Function name]
- Given: [Precondition — condition that triggers boundary or exception]
- When: [Operation]
- Then: [Expected Result — error code, degradation behavior, etc.]

---

## Completion Checklist

> Check off each item after execution. All items must be complete to be considered Done.
> Commands source: build/test/lint commands recorded in Repository Context.

- [ ] **Code Implementation** — All change items in the Changes section completed in sequence order
- [ ] **Type Check** — Type check command from Repository Context passes with no errors
- [ ] **Lint Passes** — Lint command from Repository Context passes with no errors
- [ ] **Tests Pass** — All verification cases converted to tests and passing
- [ ] **No Outstanding TODOs** — No unresolved TODO or FIXME in the code
- [ ] **PR Created** — PR created per Source Control requirements (if applicable)

## Change Log
- [Version] / [Date] / [Change content and reason]
