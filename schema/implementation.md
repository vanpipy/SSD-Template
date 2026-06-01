# Skill: [Skill Name]

## Identification
- Name: [Skill Name]
- Description: [One-sentence description of what this skill does]
- Version: [Semantic version number]
- Status: [Draft | Ready | Deprecated]
- Source: [Path to the corresponding collection entry in the collection directory; can be omitted if none]

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

## Verification
- [Scenario Description]: Expected [Expected Result]
- [Scenario Description]: Expected [Expected Result]
- [Scenario Description]: Expected [Expected Result]
- [Scenario Description]: Expected [Expected Result]

## Change Log
- [Version] / [Date] / [Change content and reason]
