# Tech Design: [Topic]

## Identification
- Name: [Tech design name, usually consistent with Collection topic]
- Description: [One-sentence description of the technical objective]
- Version: [Semantic version number]
- Status: [Draft | Ready | Deprecated]
- Source: [Path to the corresponding Collection file in the collection directory]
- Related Implementation: [Backfill path after Implementation is generated; initially empty]
- Target Repository: [Inherited from Collection, or confirmed here]

## Applicability
- Applicable: [Inherited from Collection, may supplement technical boundaries, e.g., "covers HTTP API layer only, excludes UI"]
- Not Applicable: [Inherited from Collection, may supplement technical exclusions]

## Repository Context (Design-Time Scan)

> Fill after interacting with the target repository. If the repository is not yet determined at design time, mark "TBD" — must be completed before generating Implementation.

- Tech Stack: [Existing tech stack, used to constrain design choices]
- Existing Data Models: [Paths to related tables/types/schemas already in the codebase]
- Existing API Patterns: [API style used by the project, e.g., REST / GraphQL / RPC]
- Existing Middleware/Infrastructure: [Auth, logging, message queues, caching, etc.]
- Reference Modules: [Existing modules with similar functionality, used as design reference]

## Architecture Decisions

> Record key technical decisions. Each decision must include alternatives and rationale; conclusions-only entries are not allowed.

### AD-1: [Decision Name, e.g., "Data Storage Selection"]
- Context: [Why this decision is needed]
- Alternatives:
  1. [Option A] — [Pros and cons]
  2. [Option B] — [Pros and cons]
- Choice: [Selected option]
- Rationale: [Why this was chosen, what was sacrificed]
- Impact: [Constraints this decision imposes on subsequent design]

### AD-2: [Decision Name]
- Context: [...]
- Alternatives: [...]
- Choice: [...]
- Rationale: [...]
- Impact: [...]

## Data Models

> List all data structures involved in this design. Must be specified down to field level; name-only entries are not allowed.

### [Model Name, e.g., "CartItem"]
- Purpose: [Role of this model in the system]
- Storage: [Database table name / in-memory / cache key pattern]
- Structure:
  ```
  {
    id: string            // Unique identifier
    fieldA: string        // Description
    fieldB: number        // Description
    createdAt: datetime   // Creation timestamp
  }
  ```
- Constraints: [Field-level constraints, e.g., "fieldA must not be null", "fieldB range 1-99"]
- Related Collection Scenarios: [Which Collection scenarios this model serves]

### [Model Name]
- Purpose: [...]
- Storage: [...]
- Structure: [...]
- Constraints: [...]
- Related Collection Scenarios: [...]

## API Contracts

> Define all externally exposed interfaces. Must be specified down to request/response field level.

### [API Name, e.g., "Add Item to Cart"]
- Endpoint: [METHOD /path, e.g., `POST /api/cart/items`]
- Purpose: [One-sentence description]
- Related Collection Scenario: [Which Given/When/Then scenario from Collection]
- Request:
  ```
  {
    "fieldA": "string, required — description",
    "fieldB": "number, optional — description, default: X"
  }
  ```
- Response (Success):
  ```
  {
    "code": 0,
    "data": { ... }
  }
  ```
- Response (Failure):
  ```
  {
    "code": [error code],
    "message": "error description"
  }
  ```
- Preconditions: [What must be satisfied before calling this API]
- Postconditions: [System state changes after successful call]
- Side Effects: [Triggered async operations, event publications, etc.]

### [API Name]
- Endpoint: [...]
- Purpose: [...]
- Related Collection Scenario: [...]
- Request: [...]
- Response (Success): [...]
- Response (Failure): [...]
- Preconditions: [...]
- Postconditions: [...]
- Side Effects: [...]

## Scenario-to-Technical-Path Mapping

> Core translation layer: maps each Collection business scenario to a concrete technical execution path.
> This is the direct input for the Implementation change list.

### Scenario 1: [Collection Scenario Name]
- Source: [Collection file path] # [Scenario number]
- Trigger: [User action → corresponding API endpoint]
- Execution Path:
  1. [Step 1: Receive request → which API]
  2. [Step 2: Validate → what rules]
  3. [Step 3: Read/write → which data model]
  4. [Step 4: Call external system → which integration point (if any)]
  5. [Step 5: Return result]
- Exception Path: [Where things may go wrong and how to handle]

### Scenario 2: [Collection Scenario Name]
- Source: [...]
- Trigger: [...]
- Execution Path: [...]
- Exception Path: [...]

## External System Integration

> List all external systems that require interaction, with concrete integration specifications.

### [System Name, e.g., "Payment Gateway"]
- Purpose: [Why integration is needed]
- Protocol: [HTTP / gRPC / Message Queue / WebSocket]
- Interface: [Specific endpoint or topic]
- Timeout: [Recommended timeout value]
- Retry Strategy: [How to handle failures]
- Degradation: [Fallback behavior when the external system is unavailable]
- Related Collection Scenarios: [...]

## Error Handling Strategy

> Unified error code system and handling conventions.

### Error Code Definitions
| Error Code | Meaning | Trigger Scenario | HTTP Status | Handling |
|------------|---------|------------------|-------------|----------|
| [code] | [Meaning] | [When it triggers] | [4xx/5xx] | [Retry / Degrade / Report to user] |

### Unified Handling Conventions
- Parameter validation failure: [Handling approach]
- Business rule violation: [Handling approach]
- External system timeout: [Handling approach]
- Unknown exception: [Handling approach]

## Implementation Order

> Provide execution order guidance for the Implementation change list.
> Ordered by dependency: foundation before application, data before interfaces.

1. [Step 1: What to build] — Rationale: [Why this comes first]
2. [Step 2: Description] — Depends on: Step 1 — Rationale: [...]
3. [Step 3: Description] — Depends on: Step 1, 2 — Rationale: [...]
...

## Technical Constraints (Inherited & Supplemented)
- Inherited from Collection: [Original content from Collection's Technical Constraints field]
- Supplemented during design:
  - [New technical constraint, e.g., "must use existing auth middleware"]
  - [Performance constraint, e.g., "P99 latency < 200ms"]
  - [Security constraint, e.g., "sensitive fields must be encrypted at rest"]

## Open Decisions

> Technical questions that cannot be resolved during design and require further discussion or validation.

### Requires Human Decision
- [Architecture or technology choices that must be confirmed by architect/tech lead]

### Can Be Validated via POC
- [Technical questions that can be resolved through small-scale prototype validation]

## Change Log
- [Version] / [Date] / [Change content and reason]
