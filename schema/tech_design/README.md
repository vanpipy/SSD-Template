# Tech Design: {topic} (Index)

> **状态**: Draft | Ready | Implemented
> **来源 PRD**: [../../prd/{YYYY-MM-DD}-processed/{topic}.md](../../prd/{YYYY-MM-DD}-processed/{topic}.md)
> **创建日期**: {YYYY-MM-DD}
> **最后更新**: {YYYY-MM-DD}

---

## 摘要 (Summary)

[2-3 句话概述技术方案的核心思路: 用什么技术栈、关键架构决策、覆盖哪些场景]

---

## 子文件导航 (Sub-files)

| 关注点 | 文件 | 必填 | 说明 |
|--------|------|------|------|
| 关键决策 | [decisions.md](./decisions.md) | 是 | KD-1, KD-2... |
| 数据模型 | [data-model.md](./data-model.md) | 是 | 实体、字段、约束 |
| API 契约 | [api-contracts.md](./api-contracts.md) | 是 | 端点、请求/响应 |
| 场景映射 | [scenario-mapping.md](./scenario-mapping.md) | 是 | PRD 场景 → 实现路径 |
| 时序图 | [interactions.md](./interactions.md) | 视情况 | 系统级 + 模块级 |
| 质量保证 | [quality.md](./quality.md) | 是 | 指标 + 降级 + 错误 |

---

## 何时需要 interactions.md

> 如果满足以下**任一**条件,`interactions.md` 必填,否则可跳过

- [ ] 场景映射表行数 ≥ 5
- [ ] 涉及外部接口调用
- [ ] 涉及 ≥ 2 个内部模块协作
- [ ] 包含异步流程、状态机或重试逻辑

---

## 门禁清单 (Completion Gate)

- [ ] 摘要清晰,2-3 句话讲清楚方案
- [ ] 必填文件全部存在且门禁清单通过
- [ ] `interactions.md` 门禁清单已检查(创建或显式跳过,并在此处注明)
- [ ] 所有跨文件引用 (KD, V, FR, SC, SYS, MOD) 已对账
- [ ] 状态从 `Draft` 改为 `Ready`

---

## 变更记录 (Change Log)

| 日期 | 变更 |
|------|------|
| {YYYY-MM-DD} | 初始 |
