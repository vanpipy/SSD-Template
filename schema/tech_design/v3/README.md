# Tech Design: {topic} (Index)

> **状态**: Draft | Ready | Implemented | Deprecated
> **状态主体**: agent:{id} | human:{handle}
> **状态时间**: {YYYY-MM-DDTHH:MM:SS±HH:MM}
> **状态依据**: criteria:{id}[,{id}…] | decision:{path}#{anchor} | external:{ref}
> **来源 PRD**: [../../prd/{YYYY-MM-DD}/{topic}.md](../../prd/{YYYY-MM-DD}/{topic}.md)
> **创建日期**: {YYYY-MM-DD}
> **最后更新**: {YYYY-MM-DD}

> **状态取值**: 只能是 `Draft` / `Ready` / `Implemented` / `Deprecated` 四者之一, 不得自造状态名。
> **主体口径**: `agent:<id>` = 机器写入, `human:<handle>` = 人工写入。**agent 不得填 `human:` 前缀、不得代填人名**(INV-3)。
> **状态推进**: agent 按 `schema/criteria.json` 的判据推进 —— 判据全绿即可由机器代写 `Ready`;`Implemented` 需外部事实(`external:` 依据, 如外部代码仓 PR merged);人工可在 `control/decisions/` 落决定后由机器代写;上游转 `Deprecated` 时, 引用本 TD 的 Plan / Test Case 一并 `Deprecated`。
> **依据形式**: `criteria:<id>[,<id>…]` = 判据 id;`decision:<path>#<anchor>` = 人工介入记录;`external:<ref>` = 外部事实。`Draft` 态写当次生成的 `状态主体`/`状态时间`/`状态依据`;升 `Ready` / `Implemented` 时后三行必填且非空。
> **状态口径**: 本 README 的状态行是**本 TD 目录的唯一状态源**, 子文件的状态行跟随本文件。
> **复审块 (4 行, 机器校验)**: `评审人` / `评审日期` / `评审结论` / `评审方式` 4 行都要写(`Draft` 态值可留空, 升 `Ready` 前 4 行必填非空)。取值: 评审人 = `agent:<id>` | 裸 handle(人工), 评审日期 = `YYYY-MM-DD`, 评审结论 = 通过 | 有条件通过 | 需返工, 评审方式 = 自动判据 | 人工介入 | 外部事实。`评审人` 为 `agent:*` 时 `评审方式` 不得为 `人工介入`。
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
- [ ] `## 复审 (Review)` 四行(评审人 / 评审日期 / 评审结论 / 评审方式)已由 agent 按 `schema/criteria.json` 判据填写, 状态从 `Draft` 改为 `Ready`; `评审人` 写 `agent:<id>`, 人工复核时改填人名

---

## 复审 (Review)

> 本段是**机器必填段**。四行(`评审人` / `评审日期` / `评审结论` / `评审方式`)是**评审签署**载体 —— `Draft` 阶段清空, 升 `Ready` 前由 agent 按 `schema/criteria.json` 的判据填写真值并翻转状态。
> `评审人` 取值: `agent:<id>` = 机器签署, 裸 handle = 人工签署。**agent 不得填 `human:` 前缀、不得代填人名**(INV-3)。
> `评审方式` 取值: `自动判据` / `人工介入` / `外部事实`;`评审人` 为 `agent:*` 时 `评审方式` 不得为 `人工介入`。
> Tech Design 的 `Implemented` 需外部事实依据(外部代码仓 PR merged), 且 PRD / Tech Design / Plan 三件套必须同时回写。

> **评审人**: agent:{id} | {github-handle}
> **评审日期**: {YYYY-MM-DD}
> **评审结论**: {通过 / 有条件通过 / 需返工}
> **评审方式**: {自动判据 / 人工介入 / 外部事实}

---

## 变更记录 (Change Log)

| 日期 | 变更 |
|------|------|
| {YYYY-MM-DD} | 初始 |
