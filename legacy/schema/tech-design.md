# Tech Design: {Topic}

> **Status**: Draft | Ready | Implemented
> **Source PRD**: [prd/{id}.md]()
> **Related ARDs**: [{ard-id}.md]()（如果有独立 ARD）
> **Created**: {YYYY-MM-DD}

---

## Key Decisions

> 简单决策直接内联在此处；复杂决策引用独立 ARD 文件。
> 
> **判断标准**：如果一个决策涉及 >2 个选项，或影响多个 PRD/模块，则应创建独立 ARD 文件。

### KD-1: {决策名称}

**Context**: {背景：什么情况下需要做这个决策}

**Decision**: {最终选择：一句话描述}

**Alternatives**: 
| Option | Pros | Cons |
|--------|------|------|
| {选项A} | ... | ... |
| {选项B} | ... | ... |

**Rationale**: {为什么选这个而不是其他的}

**Enforced by**: {如何保证遵守：code review / lint / convention / test}

---

> **复杂决策** → 见 [ARD-{seq}](../ard/{date}-{topic}.md)

---

## Data Models

### {Model Name}

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier |
| {field} | {type} | {description} |

**Constraints**:
- {field} must not be null
- {field} range: {range}

**Related Scenarios**: PRD Scenario {n}

---

## API Contracts

### {API Name}

- **Endpoint**: `METHOD /path`
- **Purpose**: {一句话描述}
- **Source**: PRD Scenario {n}

**Request**:
```json
{
  "fieldA": "string, required — description",
  "fieldB": "number, optional — description, default: X"
}
```

**Response** (Success):
```json
{
  "code": 0,
  "data": {}
}
```

**Response** (Failure):
```json
{
  "code": {error_code},
  "message": "error description"
}
```

**Preconditions**: {调用前必须满足的条件}

**Postconditions**: {调用后系统状态变化}

**Side Effects**: {触发的异步操作或事件}

---

## Scenario Mapping

| Scenario | Step | Action | Component | Data Model |
|----------|------|--------|-----------|------------|
| {PRD Scenario Name} | 1 | {action} | {component} | {model} |
| | 2 | {action} | {component} | {model} |
| | 3 | {action} | {component} | {model} |
| {Another Scenario} | 1 | ... | ... | ... |

---

## Metrics

| Dimension | Metric | Target | Method |
|-----------|--------|--------|--------|
| Performance | API latency P99 | < {n}ms | APM monitoring |
| Performance | Concurrent capacity | {n} QPS | Load testing |
| Quality | Availability | {n}% | Health check |
| Capacity | {描述} | {n} | {依据} |

---

## Requirement Transformation Fallback

### Coverage Matrix

| PRD Scenario | Tech Path | Status | Notes |
|--------------|-----------|--------|-------|
| {scenario} | Scenario Mapping {n} | ✅ Fully covered | — |
| {scenario} | — | ❌ Not covered | {reason} |

### Degradation Plans

#### {降级场景}

- **Trigger**: {什么时候触发降级}
- **Degraded Behavior**: {降级后的行为}
- **Business Impact**: {对用户的影响}
- **Recovery**: {恢复条件}

---

## Error Handling

| Error Code | Meaning | HTTP Status | Handling |
|------------|---------|-------------|----------|
| {code} | {meaning} | {4xx/5xx} | {retry/degrade/report} |

---

## Changelog

| Date | Change |
|------|--------|
| {YYYY-MM-DD} | Initial |
