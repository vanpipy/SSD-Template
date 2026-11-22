# PRD: {主题}

> **状态**: Draft | Ready | Implemented | Deprecated
> **状态主体**: agent:{id} | human:{handle}
> **状态时间**: {YYYY-MM-DDTHH:MM:SS±HH:MM}
> **状态依据**: criteria:{id}[,{id}…] | decision:{path}#{anchor} | external:{ref}
> **负责人**: {github-handle}
> **创建日期**: {YYYY-MM-DD}
> **最后更新**: {YYYY-MM-DD}

> **状态取值**: 只能是 `Draft` / `Ready` / `Implemented` / `Deprecated` 四者之一, 不得自造状态名。
> **主体口径**: `agent:<id>` = 机器写入, `human:<handle>` = 人工写入。**agent 不得填 `human:` 前缀、不得代填人名**(INV-3)。
> **状态推进**: agent 按 `schema/criteria.json` 的判据推进 —— 判据全绿即可由机器代写 `Ready`;`Implemented` 需外部事实(`external:` 依据, 如外部代码仓 PR merged);人工可在 `control/decisions/` 落决定后由机器代写;上游转 `Deprecated` 时, 引用本 PRD 的 Tech Design / Plan / Test Case 一并 `Deprecated`。
> **依据形式**: `criteria:<id>[,<id>…]` = 判据 id 列表, `decision:<path>#<anchor>` = 人工介入记录, `external:<ref>` = 外部事实。**状态块 4 行都要写** —— `Draft` 态写当次生成的 `状态主体` / `状态时间` / `状态依据`;升 `Ready` / `Implemented` 时后三行必填且非空。
> **必填段 (机器校验, 5 段)**: `## 为什么 (Why)` / `## 目标 (Goal)` / `## 场景 (Scenarios)` / `## 不在范围内 (Out of Scope)` / `## 复审 (Review)`。
> **复审块 (4 行, 机器校验)**: `评审人` / `评审日期` / `评审结论` / `评审方式` 4 行都要写(`Draft` 态值可留空, 升 `Ready` 前 4 行必填非空)。取值: 评审人 = `agent:<id>` | 裸 handle(人工), 评审日期 = `YYYY-MM-DD`, 评审结论 = 通过 | 有条件通过 | 需返工, 评审方式 = 自动判据 | 人工介入 | 外部事实。`评审人` 为 `agent:*` 时 `评审方式` 不得为 `人工介入`。
> **推荐段 (人工维护, 门禁不校验, 2 段)**: `## 链接 (Links)` / `## 变更记录 (Change Log)`。
> **稳定 ID**: 目标条 `- [ ] AC-n <验收标准>`;场景标题 `### 场景: S-n <名称>`;场景内 `**覆盖**: AC-n, AC-n`(写在 `**Given**` 之前)。每个 `AC-n` 至少被一个 `S-n` 覆盖, 每个 `S-n` 至少覆盖一个 `AC-n`。

---

## 为什么 (Why)

**这个需求为什么存在？解决什么问题？**

> 一句话: 这个 PRD 是为了 [问题] 而存在,期望达成 [目的]。

---

## 目标 (Goal)

**交付什么可验证的结果？**

> 每条验收标准带稳定 ID `AC-n`(行级裁决的最小单元载体);`AC-n` 在本文件内唯一, 且至少被一个场景覆盖。

- [ ] AC-1 验证标准 1(可观察/可测量)
- [ ] AC-2 验证标准 2

---

## 场景 (Scenarios)

> 用 Given/When/Then 描述用户与系统的交互。
> 每个 "Then" 必须包含可验证的具体条件——"完成 XX"、"支持 XX" 这类模糊描述不允许。
> 每个场景标题带稳定 ID `S-n`, 并用 `**覆盖**:` 行声明它覆盖哪些 `AC-n`;每个 `AC-n` 至少被一个 `S-n` 的覆盖行覆盖。

### 场景: S-1 {名称}

**覆盖**: AC-1, AC-2

**Given** {前置条件}
**When** {触发动作}
**Then** {预期结果}
**But** {异常处理（可选）}

### 场景: S-2 {另一个场景}

**覆盖**: AC-2

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

> 本段是**机器必填段**。上半四行(`评审人` / `评审日期` / `评审结论` / `评审方式`)是**评审签署**载体 —— `Draft` 阶段清空(不留占位符), 升 `Ready` 前由 agent 按 `schema/criteria.json` 的判据填写真值并翻转状态。
> `评审人` 取值: `agent:<id>` = 机器签署, 裸 handle = 人工签署。**agent 不得填 `human:` 前缀、不得代填人名**(INV-3)。
> `评审方式` 取值: `自动判据` / `人工介入` / `外部事实`;`评审人` 为 `agent:*` 时 `评审方式` 不得为 `人工介入`。
> 下半部分是**周期性复审**(防止 feature rot——每过一段时间确认这个 PRD 是否仍然值得投入), 与评审签署是两件事, 两者都要填真日期。

> **评审人**: agent:{id} | {github-handle}
> **评审日期**: {YYYY-MM-DD}
> **评审结论**: {通过 / 有条件通过 / 需返工}
> **评审方式**: {自动判据 / 人工介入 / 外部事实}

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
