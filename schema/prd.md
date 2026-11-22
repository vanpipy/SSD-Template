# PRD: {主题}

> **状态**: Draft | Ready | Implemented | Deprecated
> **负责人**: {github-handle}
> **创建日期**: {YYYY-MM-DD}
> **最后更新**: {YYYY-MM-DD}

> **状态取值**: 只能是 `Draft` / `Ready` / `Implemented` / `Deprecated` 四者之一, 不得自造状态名。
> **状态推进**: agent 可写上限 = `Draft`;`Ready` 由**人工 reviewer** 在 `## 复审 (Review)` 签署后翻转;`Implemented` 仅人工在外部代码仓 PR merged 后回写;上游转 `Deprecated` 时, 引用本 PRD 的 Tech Design / Plan / Test Case 一并 `Deprecated`。
> **必填段 (机器校验, 5 段)**: `## 为什么 (Why)` / `## 目标 (Goal)` / `## 场景 (Scenarios)` / `## 不在范围内 (Out of Scope)` / `## 复审 (Review)`。
> **推荐段 (人工维护, 门禁不校验, 2 段)**: `## 链接 (Links)` / `## 变更记录 (Change Log)`。

---

## 为什么 (Why)

**这个需求为什么存在？解决什么问题？**

> 一句话: 这个 PRD 是为了 [问题] 而存在,期望达成 [目的]。

---

## 目标 (Goal)

**交付什么可验证的结果？**

- [ ] 验证标准 1(可观察/可测量)
- [ ] 验证标准 2

---

## 场景 (Scenarios)

> 用 Given/When/Then 描述用户与系统的交互。
> 每个 "Then" 必须包含可验证的具体条件——"完成 XX"、"支持 XX" 这类模糊描述不允许。

### 场景: {名称}

**Given** {前置条件}
**When** {触发动作}
**Then** {预期结果}
**But** {异常处理（可选）}

### 场景: {另一个场景}

**Given** {前置条件}
**When** {触发动作}
**Then** {预期结果}

---

## 不在范围内 (Out of Scope)

- 明确不做的 1
- 明确不做的 2

---

## 链接 (Links)

| 类型 | 标识 | 说明 |
|------|------|------|
| 来源 Raw | prd/{YYYY-MM-DD}/ | 原始需求输入(多文件,只读) |
| 关联 Tech Design | tech_design/{YYYY-MM-DD}-{topic}/ | 后续技术设计(**目录式**, 入口文件 README.md) |
| 关联 Plan | plan/{YYYY-MM-DD}-{topic}/{topic}.md | 后续实施计划 |

> 本段是**推荐段**(人工维护, 门禁不校验)。Tech Design 与 Plan 都是**目录式**产物, 引用时写目录 / 文件路径, 不写单文件 `{id}.md`。

---

## 复审 (Review)

> 本段是**机器必填段**。上半三行(`评审人` / `评审日期` / `评审结论`)是**评审签署**载体 —— `Draft` 阶段清空(不留 `{...}` 占位符), 升 `Ready` 前由**人工 reviewer** 填写真值并翻转状态, agent 不得自行填写或翻转。
> 下半部分是**周期性复审**(防止 feature rot——每过一段时间确认这个 PRD 是否仍然值得投入), 与评审签署是两件事, 两者都要填真日期。

> **评审人**: {github-handle}
> **评审日期**: {YYYY-MM-DD}
> **评审结论**: {通过 / 有条件通过 / 需返工}

**复审日期**: {YYYY-MM-DD}

| 问题 | 答案 |
|------|------|
| 仍然重要? | Yes / No / 重新定义 |
| 应当保留? | Yes / No |
| 可以删除? | Yes / No |

---

## 变更记录 (Change Log)

| 日期 | 变更 |
|------|------|
| {YYYY-MM-DD} | 初始草稿 |
