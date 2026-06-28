# AGENTS.md

<!--
本文件是 SSD-Template 自身使用的 AGENTS.md(dogfooding 示例)。
其他项目 fork SSD-Template 时,应基于本文件结构改写为自己的版本。
-->

> AI agent 在 SSD-Template 仓库工作时的操作契约。
> 每次开始工作前,先读本文件 + 读 `schema/` 对应模板。

---

## 1. 仓库 (Repositories)

> **本仓库是文档/规格仓库,不是代码仓库**(SSD-Template 是纯文档项目)。
> 当前 **0 个代码仓库**。

### 1.1 仓库清单

| 仓库 | 角色 | 主要语言 | 说明 |
|------|------|----------|------|
| `vanpipy/SSD-Template` | 文档/规格模板 | Markdown | **本仓库**(固定) |

> 当前 0 代码仓库。如未来增加(如 `ssd-template-cli` 等工具),在此追加并定义跨仓引用。

### 1.2 跨仓库引用约定

| 引用类型 | 写法 | 示例 |
|----------|------|------|
| 本仓库内引用 | `schema/path` 或 `prd/path` | `schema/prd.md`, `prd/2026-06-22-processed/login.md` |

> 当前无代码仓库可引用。
> **禁止**: 在本仓库中引用 `src/`(本仓库没有 src/)

### 1.3 代码仓的本地 AGENTS

> 当前 0 代码仓库,本节不适用。
> 如未来增加代码仓库,在此登记各代码仓的 AGENTS.md 路径。

---

## 2. 项目信息 (Project Info)

| 字段 | 值 |
|------|-----|
| 项目类型 | 流程/文档模板 |
| 项目描述 | Spec-Driven Development(SSD)工作流脚手架,提供 3 层规格架构(PRD / Tech Design / Plan)+ 多文件 schema + AI agent 协作契约 |
| 沟通语言 | 中文 |
| 负责人 | vanpipy |

---

## 3. 使用方式 (Usage)

### 3.1 工作流 (5 步 spec)

> **5 步工作流与 HOW_TO_USE.md 对齐**:
> Step 0(收集原始需求) + Step 1(加工为 PRD) + Step 2(PRD → Tech Design) + Step 3(Tech Design → Plan) + Step 4(TDD 执行)
>
> **本项目 0 代码仓库,Step 4 (TDD) 跳过**——规格进入 `Ready` 终态即"完成"。

| 步骤 | 输入 | 输出 | 状态 | 位置 |
|------|------|------|------|------|
| Step 0: 收集原始需求 | 外部输入 | 原始素材 | (只读) | `prd/{YYYY-MM-DD}/` |
| Step 1: 加工为 PRD | `prd/{date}/` | PRD | Draft → Ready | `prd/{date}-processed/{topic}.md` |
| Step 2: PRD → Tech Design | PRD | Tech Design(7 文件) | Ready | `tech_design/{date}-{topic}/` |
| Step 3: Tech Design → Plan | Tech Design | Plan | Ready | `plan/{date}-{topic}/{topic}.md` |
| Step 4: TDD 执行(仅 ≥1 外部代码仓) | Plan | 代码 + 测试 | Ready → Implemented | 外部代码仓 |

> 0 代码仓库时,规格完成(`Ready`)即终态,无 `Implemented` 回写。

### 3.2 命名规范

**目录命名**:
- `prd/{YYYY-MM-DD}/` 和 `prd/{YYYY-MM-DD}-processed/` — 日期分桶
- `tech_design/{YYYY-MM-DD}-{topic}/` — 日期 + topic 子文件夹
- `plan/{YYYY-MM-DD}-{topic}/{topic}.md` — 日期 + topic 子文件夹 + 单文件

**topic 规则**:
- 使用**小写连字符**
- tech_design 和 plan 的文件夹名**必须带日期前缀**

**跨文件引用**(相对路径):
- Tech Design 引用 PRD: `../../prd/{date}-processed/{topic}.md`
- Plan 引用 Tech Design: `../../tech_design/{date}-{topic}/{topic}.md`
- Plan 引用 PRD: `../../prd/{date}-processed/{topic}.md`

### 3.3 状态流转

| 层 | 起始 | 终态 | 触发 |
|----|------|------|------|
| PRD | Draft | Ready | Step 1 完成所有门禁清单 |
| Tech Design | Draft | Ready | Step 2 完成所有门禁清单 |
| Plan | Draft | Ready | Step 3 完成所有门禁清单 |

> **0 代码仓库**: 无 `Implemented` 终态。规格 Ready 即"完成"。

### 3.4 门禁清单 (wiki 视角)

> wiki 只检查**规格侧**的门禁清单。**实现侧**(代码/Lint/测试)的门禁清单见各代码仓 AGENTS。
> 本项目 0 代码仓库,只看 wiki 侧。
>
> **门禁清单的权威定义在 `schema/*` 各文件,本节不复制——只列速查索引**(避免与 schema 漂移)。

| 层 | 门禁清单位置 | 自动校验脚本 |
|----|-------------|-------------|
| PRD | `schema/prd.md` 全文 | `scripts/check-md-schema.sh` |
| Tech Design | `schema/tech_design/README.md` + 6 子文件 | `scripts/check-md-schema.sh` |
| Plan | `schema/plan.md` 完成检查段 | `scripts/check-md-schema.sh` + `scripts/check-traceability.sh` |

**调用方式**:`./scripts/check-md-schema.sh && ./scripts/check-traceability.sh && ./scripts/check-naming.sh` 全返回 0 方可标 Ready。

### 3.5 禁止行为

- ❌ **不修改 `schema/` 下的模板文件**(除非显式要求更新工作流规范)
- ❌ **不省略日期前缀**——`tech_design/` 和 `plan/` 文件夹名必须带 `{YYYY-MM-DD}-`
- ❌ **不在 Plan 中写完整代码**——只写策略和约束,代码在 TDD 阶段产出(本项目无 TDD)
- ❌ **不遗漏 PRD 场景**——Tech Design 场景映射必须覆盖所有 Given/When/Then
- ❌ **不假设代码仓完成**——本项目无代码仓,故此条不适用;fork 多仓项目时启用

### 3.6 快速定位文件

| 需要什么 | 去哪里找 |
|----------|----------|
| PRD 模板 | `schema/prd.md` |
| Tech Design 模板 | `schema/tech_design/` (7 个子模板) |
| Plan 模板 | `schema/plan.md` |
| 工作流全貌 | `HOW_TO_USE.md` |
| 概念参考 | `new-factors.md` |
| 某功能的需求 | `prd/{YYYY-MM-DD}-processed/{topic}.md` |
| 某功能的设计 | `tech_design/{YYYY-MM-DD}-{topic}/` |
| 某功能的实施计划 | `plan/{YYYY-MM-DD}-{topic}/{topic}.md` |
| 历史参考(已弃用方案) | `legacy/` |

---

## 4. 附录 (Appendices)

### A. 定制指南 (供 fork 参考)

> 本节为 fork SSD-Template 的项目提供定制指南。SSD-Template 自身已应用:
> - 维度 1: 0 代码仓库,本仓库为唯一文档仓库
> - 维度 2: 流程/文档模板(中文沟通,vanpipy 维护)
> - 维度 3: 标准工作流(已适配 0 代码仓库: Step 5 跳过)
> - 维度 4: 见下文 B/C

**fork 时必改**:
- 维度 1.1: 仓库清单(填入实际的代码仓库)
- 维度 1.2: 跨仓引用(增加"指向代码仓库"行)
- 维度 1.3: 代码仓的本地 AGENTS(填入实际路径)
- 维度 2: 项目信息(替换为实际项目)

**fork 时保留**:
- 维度 3 全部内容
- 维度 4 全部内容(可选)

**多仓库 fork 时的关键约束**:
- 本仓库永远是 wiki,**不是**代码仓
- 跨仓引用使用 `{仓库前缀}/path` 写法
- Step 5 (TDD) 在代码仓执行,**人工回写** wiki Plan 状态为 `Implemented`

### fork 时可选:Step 4 启动模式

> fork 项目在 ≥1 关联代码仓时,需选择 Step 4(Plan → TDD)的启动模式。

**(B) Coding agent 自取(默认推荐)**:
- **适用**:AI coding agent fork(Claude Code / aider / Cursor / Codex 等)
- **工作量**:0 额外配置
- **原理**:Plan Ready = 工作信号,coding agent 直接消费本地 wiki
- **不需要**:`Implementing` 中间态 / 调度 issue / wiki agent kickoff
- **唯一人工介入**:外部 PR merged 后回写 wiki 状态

**(C) 显式调度(仅多 agent 协调需要)**:
- **适用**:多 code agent / 多 repo fork(罕见)
- **工作量**:+1 张状态图 + 1 套转换规则 + 1 个跨仓写权限
- **原理**:wiki agent 创建 kickoff issue,code agent 认领后执行
- **反例论证**:见 [HOW_TO_USE.md "为什么不引入 `Implementing` 中间态"](HOW_TO_USE.md#为什么不引入-implementing-中间态) —— 仅在 (B) 不可行时才升级到 (C)

### B. prompts 策略选择

> SSD-Template 自身选择**(a) 不维护 `prompts/` 目录**——所有执行指令内联在本 AGENTS.md。
> 这是基于 pos-wiki 经验(`prompts/` 目录易漂移)的决策。

### C. Evaluator 阶段启用条件

> 当前**不启用** Evaluator 阶段(决策影响 < 3 个 PRD,无需独立审计)。
>
> 启用条件:
> - 决策影响 ≥ 3 个 PRD
> - 涉及长期架构(数据库/通信协议/部署拓扑)
> - 即将上线的功能需独立审计
>
> 启用方式: 引入 sages/gaoyao 5 phase 审计。
