# Data Models: {topic}

> **状态**: Draft | Ready
> **来源**: [./README.md](./README.md)
> **创建日期**: {YYYY-MM-DD}
> **最后更新**: {YYYY-MM-DD}

---

## {模型名 1}

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一标识 |
| {field} | {type} | {说明} |

**约束**:
- {field} 不可为空
- {field} 范围: {range}

**关联场景**: PRD 场景 {n}
**引用决策**: KD-{n}
**时序图**: SYS-{n} / MOD-{n}

---

## {模型名 2}

...

---

## 检查清单 (Completion Checklist)

- [ ] 每个模型有字段表 + 约束段
- [ ] 主键、外键、索引明确
- [ ] 关联场景、决策、时序图编号已填写
- [ ] 数据类型用 TS / SQL / JSON Schema 等具体类型,**不用 `string` / `number` 泛指**

---

## 变更记录 (Change Log)

| 日期 | 变更 |
|------|------|
| {YYYY-MM-DD} | 初始 |
