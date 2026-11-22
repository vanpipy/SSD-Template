# Tech Design: {topic} (Index)

> **状态**: Draft | Ready | Implemented | Deprecated
> **来源 PRD**: [../../prd/{YYYY-MM-DD}/{topic}.md](../../prd/{YYYY-MM-DD}/{topic}.md)
> **创建日期**: {YYYY-MM-DD}
> **最后更新**: {YYYY-MM-DD}

> **状态取值**: 只能是 `Draft` / `Ready` / `Implemented` / `Deprecated` 四者之一, 不得自造状态名。
> **状态推进**: agent 可写上限 = `Draft`;`Ready` 由**人工 reviewer** 在 `## 复审 (Review)` 签署后翻转;`Implemented` 仅人工在外部代码仓 PR merged 后回写;上游转 `Deprecated` 时, 引用本 TD 的 Plan / Test Case 一并 `Deprecated`。
> **状态口径**: 本 README 的状态行是**本 TD 目录的唯一状态源**, 子文件的状态行跟随本文件。
> **代际**: v3 是**存量 / 显式 opt-in** 代际;**新建 TD 目录一律用 v4**(见 [../README.md](../README.md)), 详见 [./NOTES.md](./NOTES.md)。

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
- [ ] 所有跨文件引用 (KD, V, FR, SYS, MOD) 已对账
- [ ] `## 复审 (Review)` 三行已由**人工 reviewer** 填写, 状态从 `Draft` 改为 `Ready`

---

## 复审 (Review)

> 本段是**机器必填段**。三行(`评审人` / `评审日期` / `评审结论`)是**评审签署**载体 —— `Draft` 阶段清空, 升 `Ready` 前由**人工 reviewer** 填写真值并翻转状态, agent 不得自行填写或翻转。

> **评审人**: {github-handle}
> **评审日期**: {YYYY-MM-DD}
> **评审结论**: {通过 / 有条件通过 / 需返工}

---

## 变更记录 (Change Log)

| 日期 | 变更 |
|------|------|
| {YYYY-MM-DD} | 初始 |
