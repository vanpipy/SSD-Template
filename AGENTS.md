# AGENTS.md (Template)

<!--
TEMPLATE_VERSION: v1.0
本文件是 SSD-Template 的 wiki AGENTS.md 模板。
本仓库是文档/规格仓库,不是代码仓库。

Fork 后:
  - 必改: 维度 1(仓库)+ 维度 2(项目信息)
  - 保持: 维度 3(使用方式)通常不变
  - 必删: 维度 1.1 不适用的 code repo 行, 维度 4 不需要的附录
-->

> AI agent 在**本仓库(文档/规格仓库)** 工作时的操作契约。
> 每次开始工作前,先读本文件 + 读 `schema/` 对应模板。

---

## 1. 仓库 (Repositories)                              ← 维度 1:Fork 后必改

> **本仓库永远是文档/规格仓库,不是代码仓库**。
> 代码仓库可从 0 到 N 个,本仓库通过 `tech_design/` 和 `plan/` 协调所有代码仓库。

### 1.1 仓库清单

| 仓库 | 角色 | 主要语言 | 说明 |
|------|------|----------|------|
| `本仓库` | 文档/规格库 | Markdown | **本仓库**(固定) |
| `{CODE_REPO_1}` | {e.g. 后端} | {e.g. Python} | 通过 tech_design/plan 引用 |
| `{CODE_REPO_2}` | {e.g. 前端} | {e.g. TypeScript} | 通过 tech_design/plan 引用 |
| `{CODE_REPO_3}` | {e.g. 共享代码} | {e.g. TypeScript} | 可选 |
| ... | | | 按需加行 |

> **0 代码仓库** (纯文档项目): 删掉所有 code repo 行
> **1+ 代码仓库**: 列出所有相关代码仓库

### 1.2 跨仓库引用约定

| 引用类型 | 写法 | 示例 |
|----------|------|------|
| 指向代码仓库 | `{仓库前缀}/path` | `web-backend/src/services/auth.ts` |
| 共享代码 | `{仓库前缀}/path` | `web-shared/types/api.ts` |
| 本仓库内引用 | `schema/path` 或 `prd/path` | `schema/prd.md`, `prd/{date}-processed/{topic}.md` |

> **建议**: 代码仓库使用**统一前缀**(如 `web-frontend` / `web-backend`)
> **禁止**: 在本仓库中引用 `src/`(本仓库没有 src/)

### 1.3 代码仓的本地 AGENTS (1+ 代码仓库时,可选)

> **关键**: 技术栈、代码规范、构建/测试命令放在**代码仓的 AGENTS.md** 中
> 本节只**登记**这些本地 AGENTS 的存在和位置(不重复内容)

| 仓库 | 本地 AGENTS 路径 | 内容范围(参考) |
|------|------------------|----------------|
| `{CODE_REPO_1}` | `AGENTS.md` | 技术栈 / 代码规范 / 构建测试 |
| `{CODE_REPO_2}` | `AGENTS.md` | 技术栈 / 代码规范 / 构建测试 |

---

## 2. 项目信息 (Project Info)                            ← 维度 2:Fork 后必改

> **本节只描述"项目是什么",不描述"用什么技术实现"**(技术栈见 1.3 代码仓 AGENTS)

| 字段 | 值 |
|------|-----|
| 项目类型 | `{PROJECT_TYPE}` (e.g. Web 全栈 / 移动端 / 后端服务 / 纯文档模板) |
| 项目描述 | `{PROJECT_DESCRIPTION}` (一句话) |
| 沟通语言 | `{COMMUNICATION_LANGUAGE}` (e.g. 中文 / English) |
| 负责人 | `{GITHUB_HANDLE}` |

---

## 3. 使用方式 (Usage)                                  ← 维度 3:固定

> **本节是 SSD-Template 的标准工作流**,通常 fork 后保持不变。
> 修改前请确认改动有充分理由,否则会影响跨项目的兼容性。

### 3.1 工作流 (3 步 spec + 交接)

> **关键**: wiki AGENTS 只管**写规格**。代码相关执行(TDD/构建/测试)在**代码仓的 AGENTS.md** 中。

| 步骤 | 输入 | 输出 | 状态 | 位置 |
|------|------|------|------|------|
| 1. 收集原始需求 | 外部输入 | 原始素材 | (只读) | `prd/{YYYY-MM-DD}/` |
| 2. Step 1: 加工为 PRD | `prd/{date}/` | PRD | Draft → Active | `prd/{date}-processed/{topic}.md` |
| 3. Step 2: PRD → Tech Design | PRD | Tech Design(7 文件) | Ready | `tech_design/{date}-{topic}/` |
| 4. Step 3: Tech Design → Plan | Tech Design | Plan | Ready | `plan/{date}-{topic}/{topic}.md` |
| 5. **交接 (Handoff)** | Plan (Ready) | 移交给代码仓 | (代码仓执行) | (代码仓) |

> **Step 2 提示**: KD 可涉及技术决策(如"用什么缓存"),但**具体技术栈由各代码仓 AGENTS 规定**
> **Step 3 提示**: V 用例描述"测什么",**怎么测见各代码仓 AGENTS**
> **Step 5 提示**: 代码仓完成 TDD 后,**由人工或 agent 回写** wiki Plan 状态为 `Executed`

### 3.2 命名规范

**目录命名**:
- `prd/{YYYY-MM-DD}/` 和 `prd/{YYYY-MM-DD}-processed/` — 日期分桶
- `tech_design/{YYYY-MM-DD}-{topic}/` — 日期 + topic 子文件夹
- `plan/{YYYY-MM-DD}-{topic}/{topic}.md` — 日期 + topic 子文件夹 + 单文件

**topic 规则**:
- 使用**小写连字符**,如 `order-flow` / `member-login` / `staff-management`
- tech_design 和 plan 的文件夹名**必须带日期前缀**

**跨文件引用**(相对路径):
- Tech Design 引用 PRD: `../../prd/{date}-processed/{topic}.md`
- Plan 引用 Tech Design: `../../tech_design/{date}-{topic}/{topic}.md`
- Plan 引用 PRD: `../../prd/{date}-processed/{topic}.md`

### 3.3 状态流转

| 层 | 起始 | 终态 | 触发 |
|----|------|------|------|
| PRD | Draft | Active | Step 1 完成所有检查清单 |
| PRD | Active | Implemented | **人工/agent 回写**(代码仓完成) |
| Tech Design | Draft | Ready | Step 2 完成所有检查清单 |
| Plan | Draft | Ready | Step 3 完成所有检查清单 |
| Plan | Ready | Executed | **人工/agent 回写**(代码仓完成 TDD) |

> **回写说明**:
> - wiki **不自动**回写状态(`Active → Implemented`、`Ready → Executed`)
> - 由人工或 agent 在收到代码仓完成通知后**手动修改** Plan/PRD 文件 frontmatter
> - 显式回写避免 wiki 假设代码仓完成了实际未完成的工作

### 3.4 检查清单 (wiki 视角)

> wiki 只检查**规格侧**的检查清单。**实现侧**(代码/Lint/测试)的检查清单见各代码仓 AGENTS。

**每个 PRD**:
- [ ] **Why** 用一句话具体问题陈述
- [ ] **Goal** 每条可观察可测量
- [ ] **Scenarios** 覆盖正常 + 至少一个异常
- [ ] **Out of Scope** 至少 2 条
- [ ] **Review** 已填写

**每个 Tech Design** (7 文件):
- [ ] **7 个子文件** 全部按 `schema/tech_design/` 检查清单通过
- [ ] **`interactions.md` 必填门** 已检查
- [ ] **跨文件引用** (KD, V, FR, SC, SYS, MOD) 已对账

**每个 Plan**:
- [ ] **变更清单** 完整,引用 `KD-{n}`
- [ ] **验证用例 V-{n}** 覆盖正常+异常+边界,Then 可断言
- [ ] **业务约束 + 开发约束** 已填写
- [ ] **跨文件引用对账**

> **实现侧检查清单**(在代码仓 AGENTS,不在这里): 代码实现、类型检查、Lint、测试通过

### 3.5 禁止行为

- ❌ **不修改 `schema/` 下的模板文件**(除非显式要求更新工作流规范)
- ❌ **不省略日期前缀**——`tech_design/` 和 `plan/` 文件夹名必须带 `{YYYY-MM-DD}-`
- ❌ **不在 Plan 中写完整代码**——只写策略和约束,代码在 TDD 阶段产出
- ❌ **不遗漏 PRD 场景**——Tech Design 场景映射必须覆盖所有 Given/When/Then
- ❌ **不假设代码仓完成**——Plan 状态 `Executed` / PRD 状态 `Implemented` 必须由人工/agent 显式回写

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
| 某代码仓的约定 | `{CODE_REPO}/AGENTS.md` |
| 历史参考(已弃用方案) | `legacy/` |

---

## 4. 附录 (Appendices)                                ← 可选

### A. 定制指南 (给 fork 的人读)

**必须替换**:
- 维度 1 全部内容(仓库清单、跨仓引用、本地 AGENTS 登记)
- 维度 2 全部字段(项目类型、描述、沟通语言、负责人)

**必须删除**:
- 维度 1.1 中不适用的 code repo 行
- 维度 1.3 中不适用的本地 AGENTS 登记行
- 维度 4 中不需要的附录

**必须保留**:
- 维度 3 全部(3 步工作流 + 命名 + 状态 + 检查清单 + 禁止行为 + 快速定位)
- 维度 1 / 2 的小节结构

### B. prompts 策略选择 (项目决定)

> pos-wiki 的经验:`prompts/{prd,tech_design,plan}.md` 目录容易漂移(文件丢失或与 AGENTS.md 不一致)

**选项 (a)**: 不维护 `prompts/` 目录(推荐起步)
- 所有执行指令内联在本 AGENTS.md
- 优点: 单一信息源,无漂移风险
- 缺点: AGENTS.md 变长

**选项 (b)**: 维护 `prompts/` 目录
- 每个 step 单独 prompt 文件
- 优点: 可独立引用、版本化
- 缺点: 两份规范需要同步,有漂移风险

**选择流程**:
1. 评估 prompt 文件是否被多个项目/agent 复用
2. 如是,选 (b); 如否,选 (a)
3. 选定后,删除另一个选项对应的所有引用

### C. Evaluator 阶段启用条件 (可选)

> 引入 Evaluator 阶段(参考 sages/gaoyao 5 phase 审计)时,启用条件:
> - 决策影响 ≥ 3 个 PRD
> - 涉及长期架构(数据库/通信协议/部署拓扑)
> - 即将上线的功能需独立审计

不启用时: 保持 3 步工作流,检查清单由 wiki + 代码仓的静态检查保障。
