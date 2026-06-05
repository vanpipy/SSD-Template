# Implementation: {Topic}

> **Status**: Draft | Ready | Executed
> **Source Tech Design**: [td-01-xxx.md]()
> **Related ARDs**: [{ard-id}.md]()
> **Created**: {YYYY-MM-DD}

---

## Changes

### Change #1: {文件路径}

**ARD Link**: [{ard-id}] — 约束这个变更的架构决策

**Structural Requirements**:
```python
def function_name(param: Type) -> Type:
    """一句话说明这个函数做什么"""
    # Does NOT: 明确排除的行为
```

```typescript
interface TypeName {
  fieldA: string    // 描述
  fieldB: number   // 描述
}
```

**Verification**: Scenario V1

---

### Change #2: {文件路径}

**ARD Link**: [{ard-id}]（如果有）

**Structural Requirements**:
```python
# ...
```

**Verification**: Scenario V2

---

## Verification

### V1: {Scenario Name}

- **Given**: {precondition}
- **When**: {action}
- **Then**: {expected result}

### V2: {Exception Scenario}

- **Given**: {error precondition}
- **When**: {action}
- **Then**: {error handling / degraded behavior}

### V3: {Boundary Scenario}

- **Given**: {boundary condition}
- **When**: {action}
- **Then**: {boundary result}

---

## Business Constraints

**Preconditions**:
1. {调用前必须满足的条件}
2. ...

**Invariants**:
- {执行过程中必须保持不变的条件}

**Postconditions**:
1. {成功后系统状态变化}
2. ...

**Side Effects**:
1. {触发的外部操作}
2. {失败时是否回滚}

---

## Development Constraints

| Constraint | Value |
|------------|-------|
| Concurrency | {策略}
| Transaction Boundary | {边界}
| Idempotency | {保证方式}
| Retry | {重试策略}
| Timeout | {超时设置} |

---

## Completion Checklist

- [ ] **Code Implementation** — 所有 Change 已完成
- [ ] **ARD Compliance** — Key Decisions 已遵守
- [ ] **Type Check** — 类型检查通过
- [ ] **Lint Passes** — 代码规范检查通过
- [ ] **Tests Pass** — 验证用例通过
- [ ] **No TODOs** — 无未解决的 TODO/FIXME
- [ ] **PR Created** — PR 已创建（如适用）

---

## Changelog

| Date | Change |
|------|--------|
| {YYYY-MM-DD} | Initial |
