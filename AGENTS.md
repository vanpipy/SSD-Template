# AGENTS.md

<!--
本文件是 SSD-Template 自身使用的 AGENTS.md(dogfooding 示例)。
其他项目 fork SSD-Template 时,应基于本文件结构改写为自己的版本。
-->

> AI agent 在 SSD-Template 仓库工作时的操作契约。
> **核心原则**:以 skill 为执行单元——agent 不直接拼装 `schema/` 模板或 `scripts/` 校验脚本,而是调用 `skills/` 下的 skill。
> 每次开始工作前,先读本文件 + 读 `skills/<skill-name>/SKILL.md`(skill 内部已封装 schema 读取 + scripts 校验流程)。

---

## 1. 仓库 (Repositories)

> **本仓库是文档/规格仓库,不是代码仓库**(SSD-Template 自身是纯 wiki 项目)。
> 当前 SSD-Template **0 关联代码仓库**(A only),但 §1.1 展示了 fork 后接入 B / C 的多仓布局示例,fork 项目按需替换为实际仓库。

### 1.1 仓库清单

> **本节用途**:登记 fork 项目的**全部仓库**(Wiki + 0-N 个代码仓),是 §1.2 / §1.3 / §1.4 的**唯一数据源**(single source of truth)。
> **禁止**:本节**不**附 check/detect 脚本——仓库存在性由 §1.4 Clone Protocol 处理(agent 主动 `git clone`,不写自定义脚本)。

#### 标识约定

| 标识 | 角色 | 说明 |
|------|------|------|
| **A** | Wiki / Spec 仓库 | **本仓库**(固定),所有 spec 的源 |
| **B**, **C**, ... | Code workspace | fork 后接入的代码仓,通常 0-N 个 |
| **N** | 占位符 | §1.1 表中任意非 A 行(便于泛指) |

#### 布局示例:A + B + C (3 仓 fork)

```text
parent_dir/
├── SSD-Template/              ← A (current dir, ./)
├── client/                     ← B (../client/)
└── server/      ← C (../server/)
```

| 标识 | 仓库 | Git URL | 本地路径 | 角色 | 主要语言 | 说明 |
|------|------|---------|----------|------|----------|------|
| **A** | `vanpipy/SSD-Template` | `https://github.com/vanpipy/SSD-Template` | `./` | Wiki / Spec | Markdown | **本仓库**(固定,current dir) |
| **B** | `vanpipy/client` | `https://github.com/vanpipy/client` | `../client/` | Code workspace | TypeScript | 示例代码仓 (sibling of A,fork 后替换为实际仓库) |
| **C** | `vanpipy/server` | `https://github.com/vanpipy/server` | `../server/` | Code workspace | Java | 示例代码仓 (sibling of A,fork 后替换为实际仓库) |

> **关键点**:**标识** (B/C) 是逻辑标签,稳定不变;**目录名** (`client/` / `server/`) 由 Git URL 决定,fork 时可改名而引用语法 (`{B}/path`) 不受影响。
> 当前 SSD-Template 自身为 **A only** (0 代码仓,见 §1.3)。B / C 行是 fork 项目典型多仓布局示例——fork 时按需替换为实际仓库。
> 不需要代码仓时(如纯文档项目):整行删除 B / C,并把 §1.3 标注 "0 代码仓"。

### 1.2 跨仓库引用约定

| 引用类型 | 写法 | 示例 | 来源 |
|----------|------|------|------|
| 本仓库内引用 (A) | `schema/path` / `prd/path` / `tech_design/path` / `plan/path` | `schema/prd.md`, `prd/2026-06-22-processed/login.md` | 当前文件位置 |
| 跨仓库引用 (B / C / ...) | `{标识}/{path}` (用 §1.1 标识列) | `client/app/services/auth.ts`, `server/api/controller/OrderController.java` | §1.1 标识 + 本地路径 |

**跨仓库引用规则**:

- `{标识}` 必须**严格**匹配 §1.1 "标识" 列 (A / B / C / ...)——一一对应
- 路径**相对于该标识的 本地路径** (如 `{B}/app/services/auth.ts` 解析为 §1.1 B 行 本地路径 + `/app/services/auth.ts`)
- **禁止**口语化引用(`client 仓库` / `server 项目` 等)
- **禁止**在 A 仓库 spec 文件中引用 `src/` / `cmd/` / `pkg/` / `internal/` 等代码目录前缀——这些是 B/C 内部约定,A 不应假设

> 当前 SSD-Template 自身为 0 代码仓,跨仓引用行仅在 fork 后有 B/C 时生效。
> 多仓项目 Plan 的 Change 分仓规则(强制 B / C 分组)见 [`to-plan` skill §多仓强制分仓](skills/to-plan/SKILL.md)。

### 1.3 代码仓的本地 AGENTS

> 当前 0 代码仓库,本节不适用。
> 如未来增加代码仓库,在此登记各代码仓的 AGENTS.md 路径,以便 §3.4 实现侧门禁清单可被引用。

#### 布局示例(以 §1.1 A + B + C 为准)

| 标识 | AGENTS.md 路径 |
|------|---------------|
| **A** | `./AGENTS.md` (本文件) |
| **B** | `../client/AGENTS.md` |
| **C** | `../server/AGENTS.md` |

> 仅 A 时,实现侧(代码仓)门禁清单**不**生效——所有 §4 完成检查全部停留为 "未启用"。
> 标识 → AGENTS 路径的映射应与 §1.1 同步(fork 修改 §1.1 时,本表对应行也要更新)。

### 1.4 工作开始前 — 仓库补齐 (Clone Protocol)

> **本节用途**:定义 agent 在 §3 工作流开始前如何确保 §1.1 列出的所有仓库已存在于本地工作区。
> **原则**:补齐操作由 agent 主动执行 `git clone`,**不**写自定义 check 脚本(沿用 §1.1 禁止约束)。

#### Step 1 — 核对 A (本仓库)

```bash
git remote -v
# output 应与 §1.1 A 行 Git URL 一致
```

不一致 → **停止**,先解决目录错误再继续(可能身在 fork 而非本仓库)。

#### Step 2 — 遍历 §1.1,补齐 B / C / ... (代码仓)

**通用模式**(按 §1.1 表的每一非 A 行执行):

```bash
[[ -d <本地路径> ]] || git clone <Git URL> <本地路径>
```

**具体应用**(以 §1.1 A + B + C 布局为准):

```bash
# §1.1 B 行: ../client/ + https://github.com/vanpipy/client
[[ -d ../client ]] || git clone https://github.com/vanpipy/client ../client

# §1.1 C 行: ../server/ + https://github.com/vanpipy/server
[[ -d ../server ]] || git clone https://github.com/vanpipy/server ../server
```

> 0 代码仓项目(仅 A):Step 2 跳过,直接进 §3。
> 添加新仓库到 §1.1 时,只需在本节补一行对应的 `[[ -d <path> ]] || git clone ...` 即可。

#### Step 3 — 验证工作区拓扑

完成后,本地工作区应呈现 §1.1 表的镜像布局:

```bash
ls -la ..
# 应见: SSD-Template/  client/  server/  (或 fork 实际目录名)
```

#### Step 4 — 跨仓库引用启用

A 中的 spec 文件现在可通过 §1.2 `{标识}/path` 语法引用 B / C 的具体文件。

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
| Step 1: 加工为 PRD | `/to-prd <date>` | PRD | Ready | `prd/{date}-processed/{topic}.md` |
| Step 2: PRD → Tech Design | `/to-tech-design <prd-path>` | Tech Design(7 文件) | Ready | `tech_design/{date}-{topic}/` |
| Step 3: Tech Design → Plan | `/to-plan <tech-design-dir>` | Plan | Ready | `plan/{date}-{topic}/{topic}.md` |
| Step 4: TDD 执行(仅 ≥1 外部代码仓) | Plan | 代码 + 测试 | Ready → Implemented | 外部代码仓 |

> 0 代码仓库时,规格完成(`Ready`)即终态,无 `Implemented` 回写。
> **不产出 Draft 状态**——`to-prd` / `to-tech-design` / `to-plan` skill 完成后直接设 `Ready`。
> 详细调用示例见 §3.7,Skill 注册见 §3.8。

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

| 层 | 门禁清单位置 | 验证方式 |
|----|-------------|----------|
| PRD | `schema/prd.md` 全文 | `/validate-spec` |
| Tech Design | `schema/tech_design/README.md` + 6 子文件 | `/validate-spec` |
| Plan | `schema/plan.md` 完成检查段 | `/validate-spec` |

**调用方式**:三件套 Ready 前,跑 `validate-spec` skill(自动跑全部 3 个 scripts),全部 `✓` 方可标 Ready。

### 3.5 禁止行为

- ❌ **不修改 `schema/` 下的模板文件**(除非显式要求更新工作流规范)
- ❌ **不省略日期前缀**——`tech_design/` 和 `plan/` 文件夹名必须带 `{YYYY-MM-DD}-`
- ❌ **不在 Plan 中写完整代码**——只写策略和约束,代码在 TDD 阶段产出(本项目无 TDD)
- ❌ **不遗漏 PRD 场景**——Tech Design 场景映射必须覆盖所有 Given/When/Then
- ❌ **不假设代码仓完成**——本项目无代码仓,故此条不适用;fork 多仓项目时启用
- ❌ **不绕过 skill 直接拼 schema/scripts 命令**——保持调用入口单一,agent 首选 `skills/<name>/SKILL.md`

### 3.6 调用示例

```bash
# Step 1: 原始需求 → PRD
/to-prd <date>                              # 例: /to-prd 2026-07-03

# Step 2: PRD → Tech Design(单文件)
/to-tech-design <prd-path>                  # 例: /to-tech-design prd/2026-07-03-processed/login.md
/to-tech-design <prd-dir>                   # 例: /to-tech-design prd/2026-07-03-processed/  (批量)

# Step 3: Tech Design → Plan
/to-plan <tech-design-dir>                  # 例: /to-plan tech_design/2026-07-03-login/

# 验证(任意时点跑,产完就跑)
/validate-spec
```

### 3.7 Skill 注册

skills 通过 `setup.sh` 注册到 agent 的 skills 目录(支持 claude / qoder / pi / cursor):

```bash
bash <repo>/skills/setup.sh                  # 注册到默认 4 个目录
bash <repo>/skills/setup.sh --unregister     # 注销所有
bash <repo>/skills/setup.sh --target <dir>   # 注册到指定目录
```

注册后 agent 可识别 `/to-prd` / `/to-tech-design` / `/to-plan` / `/validate-spec` 命令。

### 3.8 快速定位文件

| 需要什么 | 去哪里找 |
|----------|----------|
| **执行工作流**(首选) | `skills/{to-prd,to-tech-design,to-plan,validate-spec}/SKILL.md` ★ |
| Skill 注册到 agent | `skills/setup.sh`(注册到 `~/.claude/skills/` 等) |
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

### B. Skill 策略选择

> SSD-Template 自身选择**(a) 维护 `skills/` 目录**——所有执行流程封装在 `skills/<name>/SKILL.md`。
> 这是基于 pos-wiki 经验(内联 prompt 步骤易漂移)进化出的设计。
> **fork 项目推荐沿用本策略**——直接复制 `skills/` 目录,无需重建 prompt。

### C. Evaluator 阶段启用条件

> 当前**不启用** Evaluator 阶段(决策影响 < 3 个 PRD,无需独立审计)。
>
> 启用条件:
> - 决策影响 ≥ 3 个 PRD
> - 涉及长期架构(数据库/通信协议/部署拓扑)
> - 即将上线的功能需独立审计
>
> 启用方式: 引入 sages/gaoyao 5 phase 审计。
