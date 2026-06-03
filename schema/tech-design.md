# Tech Design: [Topic]

> **Perspective: Executing Agent — Focus on Strategy, Metrics, Investigation, Fallback**
> Tech Design is the bridge between business rules and code implementation. Its core responsibilities are:
> - **Strategy**: Define the technical roadmap and architectural direction. Not just "what to pick", but "how to build the whole thing" — including tech roadmap, integration patterns, data management strategy, deployment and scaling approach. Every strategic decision must have alternatives and rationale.
> - **Metrics**: Define measurable technical targets. Don't write "high performance", write specific latency, throughput, availability, and capacity numbers. Metrics are both acceptance criteria and constraints for design decisions.
> - **Investigation**: Conduct a comprehensive investigation of the entire process at the solution level. Not just "the main flow works", but expand every step to an auditable level of detail — where does input come from, what is the processing logic, where does output go, under what conditions does it fail, what does failure impact. The Agent uses the investigation to understand the full picture, not just the main trunk.
> - **Fallback**: Ensure business intent is preserved after requirement transformation. Every Collection scenario must have a corresponding technical path; if technical constraints prevent full implementation, the degradation plan must be explicit with stated business impact. The Agent uses the fallback strategy to know when to take the normal path vs. the degraded path.

## Identification
- Name: [Tech design name, usually consistent with Collection topic]
- Description: [One-sentence description of the technical objective]
- Version: [Semantic version number]
- Status: [Draft | Ready | Deprecated]
- Design Mode: [Greenfield | Brownfield]
- Source: [Path to the corresponding Collection file in the collection directory]
- Related Implementation: [Backfill path after Implementation is generated; initially empty]
- Target Repository: [Inherited from Collection, or confirmed here; may be left empty for greenfield]

## Applicability
- Applicable: [Inherited from Collection, may supplement technical boundaries, e.g., "covers HTTP API layer only, excludes UI"]
- Not Applicable: [Inherited from Collection, may supplement technical exclusions]

## Repository Context (Design-Time Scan)

> Fill according to design mode:
> - **Brownfield**: Two-pass scan — first pass reads repo-level AGENTS.md / CLAUDE.md / .cursorrules (the authoritative conventions maintained by repo owners, read first to avoid misinterpreting patterns downstream); second pass scans the codebase against these conventions. For each sub-field, list 1-2 typical/representative file paths — exhaustive enumeration is not required; deeper model and interface exploration happens in the "Scenario Mapping & Solution-Level Full Investigation" step.
> - **Greenfield**: Replace this section with "Problem Domain Context" — requirement boundaries, candidate tech stack, similar-system references, to feed the technical strategy rationale downstream.

- Tech Stack: [Existing tech stack, used to constrain design choices]
- Existing Data Models: [Typical paths to related tables/types/schemas, 1-2 representative files]
- Existing API Patterns: [API style used by the project, e.g., REST / GraphQL / RPC, with 1-2 representative endpoints]
- Existing Middleware/Infrastructure: [Auth, logging, message queues, caching, etc., with names and typical config paths]
- Reference Modules: [Existing modules with similar functionality, used as design reference, 1-2 typical modules]

## Technical Strategy

> Define the overall technical roadmap and architectural direction. Not just recording "what was picked", but answering "how to build it overall and why".
> Every strategic decision must include alternatives and rationale; conclusions-only entries are not allowed.

### Overall Technical Roadmap
- Architecture Style: [e.g., Monolith / Microservices / Serverless / Hybrid] — Rationale: [Why this style]
- Integration Pattern: [e.g., Synchronous API / Event-driven / Message Queue] — Rationale: [...]
- Data Management Strategy: [e.g., Single database / Read-write split / Local cache + remote sync] — Rationale: [...]
- Deployment Approach: [e.g., Containerized / Cloud functions / Edge computing] — Rationale: [...]

### Key Decisions

#### AD-1: [Decision Name, e.g., "Data Storage Selection"]
- Context: [Why this decision is needed]
- Alternatives:
  1. [Option A] — [Pros and cons]
  2. [Option B] — [Pros and cons]
- Choice: [Selected option]
- Rationale: [Why this was chosen, what was sacrificed]
- Impact: [Constraints this decision imposes on subsequent design]

#### AD-2: [Decision Name]
- Context: [...]
- Alternatives: [...]
- Choice: [...]
- Rationale: [...]
- Impact: [...]

## Metrics

> Define measurable technical targets. Don't write "high performance" or "low latency" — provide specific numbers.
> Metrics serve as both design decision constraints and post-Implementation acceptance criteria.

### Performance Metrics
| Metric | Target | Measurement Method | Related Scenarios |
|--------|--------|-------------------|-------------------|
| [e.g., API response time P99] | [e.g., < 200ms] | [e.g., APM monitoring] | [Related Collection scenario] |
| [e.g., Concurrent capacity] | [e.g., 100 QPS] | [e.g., Load testing tool] | [...] |

### Quality Metrics
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| [e.g., API availability] | [e.g., 99.9%] | [e.g., Health check + monitoring alerts] |
| [e.g., Data consistency] | [e.g., Eventually consistent, delay < 5s] | [e.g., Reconciliation script] |

### Capacity Metrics
| Metric | Target | Notes |
|--------|--------|-------|
| [e.g., Max hold orders per device] | [e.g., 5] | [Business constraint source] |
| [e.g., Order retention period] | [e.g., 90 days] | [Storage capacity estimation basis] |

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

## Requirement Transformation Fallback Strategy

> Ensure Collection business intent is not lost or distorted after transformation to technical paths.
> This is the core safety net of Tech Design.

### Coverage Matrix

> Line-by-line verification: does every Collection scenario have a corresponding technical path?

| Collection Scenario | Technical Path | Coverage Status | Notes |
|--------------------|---------------|-----------------|-------|
| [Scenario name] | [Corresponding mapping number] | ✅ Fully covered | — |
| [Scenario name] | [Corresponding mapping number] | ⚠️ Partially covered | [What's missing and why] |
| [Scenario name] | — | ❌ Not covered | [Reason and alternative approach] |

### Degradation Plans

> When technical constraints prevent full fulfillment of business requirements, specify the degradation plan and business impact.

#### [Degradation scenario, e.g., "Payment channel unavailable"]
- Trigger Condition: [When does degradation activate]
- Degraded Behavior: [How the system behaves — e.g., prompt user to retry, switch to backup channel]
- Business Impact: [User experience change after degradation — e.g., cannot complete payment, but browsing and cart still work]
- Recovery Condition: [When to exit degradation and resume normal path]
- Related Collection Scenarios: [Affected original scenarios]

### Omission Risks

> Record potential gaps identified during design, preventing them from surfacing only at implementation time.

- [Risk, e.g., "Real-time member pricing queries may timeout under high concurrency"] — Current Mitigation: [How the design addresses it] — Residual Risk: [What may still happen]

## Solution-Level Full Investigation

> Conduct a comprehensive investigation of the entire process at the solution level.
> Not just verifying "the main flow works", but expanding every step to an auditable level of detail, ensuring the solution has no blind spots.

### End-to-End Flow Investigation

> Select the most critical business flow (from user trigger to final result), expand step by step.

#### Flow: [Core flow name, e.g., "Complete Checkout Process"]

| Step | Input | Processing Logic | Output | Failure Condition | Failure Impact | Components Involved |
|------|-------|-----------------|--------|-------------------|----------------|-------------------|
| [1. Member identification] | [Phone/member card] | [Query member system, match identity] | [Member tier + pricing] | [Timeout / no match] | [Degrade to non-member pricing] | [Member system] |
| [2. Product addition] | [Scan/search/select] | [Query product catalog, add to settlement] | [Product + price + qty] | [Invalid barcode / out of stock] | [Notify and skip item] | [Product service] |
| [3. Amount calculation] | [Settlement list] | [Apply discount rules, calculate total] | [Payable amount] | [Discount engine error] | [Settle at original price] | [Discount engine] |
| [4. Payment] | [Amount + payment method] | [Call payment channel / record cash] | [Payment result] | [Timeout / channel error] | [Enter dispute flow] | [Payment gateway] |
| [5. Order creation] | [Payment result + settlement] | [Create online order, update status] | [Order ID + e-receipt] | [Create order API failure] | [Local buffer + retry] | [Order service] |

### Component Interaction Investigation

> List all components involved (internal modules + external systems), specify the protocol, data format, and failure boundary for each interaction pair.

| Caller | Callee | Protocol | Data Format | Timeout | Failure Handling | Existing Implementation |
|--------|--------|----------|-------------|---------|-----------------|----------------------|
| [Mobile POS client] | [Product service] | [REST] | [JSON] | [3s] | [Use local cache] | [Yes/No] |
| [...] | [...] | [...] | [...] | [...] | [...] | [...] |

### Data Flow Investigation

> Trace core business objects through the entire process, ensuring data integrity and consistency.

#### Data Object: [e.g., "Settlement List"]
- Created: [Which step, which API]
- Modified: [Which steps modify it, what changes each time]
- Read: [Which steps need to read it]
- Archived/Deleted: [Final state and retention policy]
- Consistency Risk: [Which concurrency or failure scenarios could cause data inconsistency]

### Investigation Conclusions

> Based on the investigation above, summarize the solution's completeness and risks.

- Coverage Completeness: [The solution covers all known steps / The following steps are not yet clear: ...]
- Key Risks: [High-risk points found during investigation, e.g., single point of failure, data inconsistency, performance bottleneck]
- Requires Deep Dive: [Technical questions needing POC validation or further discussion]

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
