# BDD Spec: {Feature Name}

> **Links**: 
> - PRD: [{prd-id}.md]()
> - ARD: [{ard-id}.md]()（如果有）
> **Owner**: {github-handle}
> **Status**: Draft | Ready | Passing

---

## Feature: {Feature Name}

**Why does the user need this?**

_{一句话说明用户为什么需要这个功能，对应 PRD 的 motivation}_

---

## Background

**Given** {共享的前置条件}

---

## Scenarios

### Scenario: {场景名}

**Given** {前置条件}  
**And** {另一个前置条件（可选）}  
**When** {用户动作}  
**Then** {预期结果}  
**And** {另一个结果（可选）}

**But** if {错误条件}  
**Then** {错误处理}

---

### Scenario: {边界条件}

**Given** {边界情况}  
**When** {动作}  
**Then** {边界情况结果}

---

## Examples

| {param1} | {param2} | expected |
|----------|-----------|----------|
| {value1} | {value2} | {result1} |
| {value3} | {value4} | {result2} |

---

## Step Definitions

### Given Steps

```python
@given('{precondition}')
def step_given(context):
    """前置条件设置"""
    pass
```

### When Steps

```python
@when('{action}')
def step_when(context):
    """执行动作"""
    pass
```

### Then Steps

```python
@then('{result}')
def step_then(context):
    """验证结果"""
    pass
```

---

## Verification

运行以下命令执行 BDD 测试：

```bash
behave specs/{feature-name}.md
```

---

## Changelog

| Date | Change |
|------|--------|
| {YYYY-MM-DD} | Initial draft |
