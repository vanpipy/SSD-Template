# AGENTS.md

<!--
本文件是 merchandising 项目的 AGENTS.md (fork 自 SSD-Template)。
SSD-Template 是通用模板,本文件按本项目的实际仓库与流程改写。
-->

> AI agent 在 merchandising 规格仓库工作时的操作契约。
> **核心原则**:以 skill 为执行单元。agent 不直接拼装 `schema/` 模板或 `scripts/` 校验脚本,而是调用 `skills/` 下的 skill。
> 每次开始工作前,先读本文件 + 读 `skills/<skill-name>/SKILL.md`(skill 内部已封装 schema 读取 + scripts 校验流程)。

---

## 1. 仓库 (Repositories)

> **本仓库是文档/规格仓库,不是代码仓库**。它是 merchandising 项目的规格真源。
> 关联 **2 个代码仓库**(B = 后端, C = 前端),见 §1.1。

### 1.1 仓库清单

> **本节用途**:登记本项目的**全部仓库**(Wiki + 2 个代码仓),是 §1.2 / §1.3 / §1.4 / §1.5 / §1.6 / §1.7 的**唯一数据源**(single source of truth)。
> **禁止**:本节**不**附 check/detect 脚本。仓库存在性由 §1.4 Clone Protocol 处理(agent 主动 `git clone`,不写自定义脚本)。

#### 标识约定

| 标识 | 角色 | 说明 |
|------|------|------|
| **A** | Wiki / Spec 仓库 | **本仓库**(固定),所有 spec 的源 |
| **B** | Code workspace (后端) | merchandising 后端服务仓 |
| **C** | Code workspace (前端) | merchandising Vue PC 前端仓 |
| **N** | 占位符 | §1.1 表中任意非 A 行(便于泛指) |

#### 布局:A + B + C (3 仓)

```text
~/Project/
├── SSD-merchandising/                       ← A (current dir, ./)
└── merchandising-workspace/                 ← 伪伞形工作区 (父目录)
    ├── busyming-merchandising/               ← B (../merchandising-workspace/busyming-merchandising/)
    └── busyming-merchandising-vue-pc/        ← C (../merchandising-workspace/busyming-merchandising-vue-pc/)
```

| 标识 | 仓库 | Git URL | 本地路径 | 角色 | 主要语言 | 说明 |
|------|------|---------|----------|------|----------|------|
| **A** | `SSD-merchandising` | (本地 fork, 源自 `SSD-Template`) | `./` | Wiki / Spec | Markdown | **本仓库**(规格真源) |
| **B** | `busyming-merchandising` | `git@codeup.aliyun.com:63e991ce3f24888125dabd43/busyming-product/busyming-product-be/busyming-merchandising.git` | `../merchandising-workspace/busyming-merchandising/` | Code workspace | Java / Maven | 后端服务仓, 9 个 Maven 模块 |
| **C** | `busyming-merchandising-vue-pc` | `git@codeup.aliyun.com:63e991ce3f24888125dabd43/busyming-product/busyming-product-fe/busyming-merchandising-vue-pc.git` | `../merchandising-workspace/busyming-merchandising-vue-pc/` | Code workspace | Vue 3 / TypeScript | PC 前端仓, Vite + Vitest |

> **关键点**:**标识** (B/C) 是逻辑标签,稳定不变;**目录名** 由 Git URL 决定,fork 时可改名而引用语法 (`{B}/path`) 不受影响。
> B / C 位于伪伞形工作区 `merchandising-workspace/` 内。该工作区是**独立仓库**,与 A 不构成 submodule 关系;两仓各自独立 clone,各自独立提交。
> 新增代码仓时,在本表加一行,并同步 §1.3 / §1.4。

### 1.2 跨仓库引用约定

| 引用类型 | 写法 | 示例 | 来源 |
|----------|------|------|------|
| 本仓库内引用 (A) | `schema/path` / `prd/path` / `tech_design/path` / `plan/path` | `schema/prd.md`, `prd/2026-06-22/login.md` | 当前文件位置 |
| 跨仓库引用 (B / C) | `{标识}/{path}` (用 §1.1 标识列) | `{B}/busyming-merchandising-service/src/...`, `{C}/src/modules/...` | §1.1 标识 + 本地路径 |

**跨仓库引用规则**:

- `{标识}` 必须**严格**匹配 §1.1 "标识" 列 (A / B / C),一一对应
- 路径**相对于该标识的 本地路径** (如 `{B}/busyming-merchandising-service/...` 解析为 §1.1 B 行 本地路径 + `/busyming-merchandising-service/...`)
- **禁止**口语化引用(`后端仓库` / `前端项目` 等)
- **禁止**在 A 仓库 spec 文件中引用 `src/` / `cmd/` / `pkg/` / `internal/` 等代码目录前缀。这些是 B/C 内部约定,A 不应假设
- 引用 B/C 路径时**必须带仓库内的顶层模块/目录前缀**(如 `{B}/busyming-merchandising-domain/...`),因为 B 仓是多 Maven 模块结构

> 多仓项目 Plan 的 Change 分仓规则(强制 B / C 分组)见 [`to-plan` skill §多仓强制分仓](skills/to-plan/SKILL.md)。

### 1.3 代码仓的本地 AGENTS

> 本项目有 2 个代码仓库,本节登记各代码仓的 AGENTS.md 路径,便于 §3.4 实现侧门禁清单可被引用。

| 标识 | AGENTS.md 路径 |
|------|---------------|
| **A** | `./AGENTS.md` (本文件) |
| **B** | `../merchandising-workspace/busyming-merchandising/AGENTS.md` |
| **C** | `../merchandising-workspace/busyming-merchandising-vue-pc/AGENTS.md` |

> **实现侧门禁清单生效**。§4 完成检查的代码/Lint/测试项由 B / C 两个 AGENTS.md 定义。
> 标识 → AGENTS 路径的映射应与 §1.1 同步(fork 修改 §1.1 时,本表对应行也要更新)。

### 1.4 工作开始前 · 仓库补齐 (Clone Protocol)

> **本节用途**:定义 agent 在 §3 工作流开始前如何确保 §1.1 列出的所有仓库已存在于本地工作区。
> **原则**:补齐操作由 agent 主动执行 `git clone`,**不**写自定义 check 脚本(沿用 §1.1 禁止约束)。

#### Step 1 · 核对 A (本仓库)

```bash
git remote -v
# output 应与 §1.1 A 行 Git URL 一致
```

不一致 → **停止**,先解决目录错误再继续(可能身在 fork 而非本仓库)。

#### Step 2 · 遍历 §1.1,补齐 B / C (代码仓)

**通用模式**(按 §1.1 表的每一非 A 行执行):

```bash
[[ -d <本地路径> ]] || git clone <Git URL> <本地路径>
```

**具体应用**(以 §1.1 A + B + C 布局为准):

```bash
# §1.1 B 行: ../merchandising-workspace/busyming-merchandising/
[[ -d ../merchandising-workspace/busyming-merchandising ]] || \
  git clone git@codeup.aliyun.com:63e991ce3f24888125dabd43/busyming-product/busyming-product-be/busyming-merchandising.git \
    ../merchandising-workspace/busyming-merchandising

# §1.1 C 行: ../merchandising-workspace/busyming-merchandising-vue-pc/
[[ -d ../merchandising-workspace/busyming-merchandising-vue-pc ]] || \
  git clone git@codeup.aliyun.com:63e991ce3f24888125dabd43/busyming-product/busyming-product-fe/busyming-merchandising-vue-pc.git \
    ../merchandising-workspace/busyming-merchandising-vue-pc
```

> B / C 位于伪伞形工作区 `merchandising-workspace/` 内。该工作区本身是独立仓库;若它尚未 clone,先 clone 工作区再 clone 子仓。

#### Step 3 · 验证工作区拓扑

完成后,本地工作区应呈现 §1.1 表的镜像布局:

```bash
ls -la ..
# 应见: SSD-merchandising/  merchandising-workspace/
```

#### Step 4 · 跨仓库引用启用

A 中的 spec 文件现在可通过 §1.2 `{标识}/path` 语法引用 B / C 的具体文件。

### 1.5 多仓 Plan 编排 (Multi-repo Plan)

> **本节用途**:定义多仓项目产出 Plan 时,Change 如何按仓分组。
> **依据**:`skills/to-plan` skill 的 12 处 `§1.5` 引用以此节为准。
> **0 代码仓项目**:不分组。Change 直接列在 `## 变更清单` 下,视为单一分组。(本项目有 B / C,适用下方分组规则)

**分组规则**:

| 项 | 约定 |
|----|------|
| 仓库标识 | 取自 §1.1「标识」列 (A / B / C / ...)。**不**用目录名,**不**用口语化名称 |
| 分组标题 | `#### {仓库标识} 变更`(固定 h4,与 §1.5 示例一致) |
| Change 条目 | `#### Change #N: {标识}/{路径}` |
| 文件路径 | **必须**带 `{标识}/` 前缀(§1.2 跨仓库引用约定) |
| 验证用例 (V) | **不按仓分组**,按业务场景聚合,一个场景可横跨多仓 |
| 组内说明 | 组标题下用 `>` 引用块写该仓承担的 KD / V 关注点 |

**为什么 Change 按仓分组**:Change 的「实施约束」是仓特定的。依赖管理 / 构建方式 / 部署拓扑 / 目录约定各仓不同,按仓分组后每个仓的实施者只读自己那节。

**为什么 V 用例不按仓分组**:V 用例描述的是**业务场景**,一个场景往往横跨多个仓。按场景聚合才能保证端到端覆盖不漏,按仓分组反而会把一个场景拆断。

**示例**(以 §1.1 A + B + C 布局为例):

```markdown
## 变更清单

#### B 变更

> KD-1 / V-1 主要约束 B 仓的接口编排与入参校验

#### Change #1: `B/api/controller/SessionController.java`
**遵循决策**: KD-1
**验证**: V-1

#### C 变更

> KD-2 / V-1 主要约束 C 仓的数据持久化与事务边界

#### Change #2: `C/service/session/SessionRepository.java`
**遵循决策**: KD-2
**验证**: V-1

### 验证用例 (V-1 跨仓覆盖,按场景聚合)

> V 用例不按仓分组。V-1 同时覆盖 B 仓的接口校验与 C 仓的持久化。
```

> **层级兼容**:`scripts/check-md-schema.sh` 只识别 `### Change #N:` 与 `#### Change #N:` 两种 Change 标题。仓库组标题占 h4 时,Change 条目同样落 h4(脚本按标题正则匹配,不按嵌套层级),V 用例仍用 h3 `### V-{n}:` 以便脚本识别。

### 1.6 实现基线 (Implementation Baseline)

> **本节用途**:Tech Design 的 `## 实现基线` 段记录「设计所基于的代码现状快照」。
> **目的**:防止设计与当前实现脱节。基线是**快照**不是承诺。核对不一致时,应更新基线或更新设计,二者必居其一。

**表格格式**(固定 6 列,`scripts/check-repo-baseline.sh` 按此解析):

```markdown
## 实现基线

| 仓库 | 分支 | SHA | 核对日期 | 核对项 | 状态 |
|------|------|-----|----------|--------|------|
| B | {分支} | {短SHA} | {YYYY-MM-DD} | {核对内容} | ✓ |
```

| 列 | 填写规则 |
|----|----------|
| 仓库 | §1.1 登记的**标识**(如 `A` / `B` / `C`)。脚本据此解析本地路径 |
| 分支 | 核对时的分支名 |
| SHA | 短 SHA,取法见 §1.7 |
| 核对日期 | 本次核对的日期 `{YYYY-MM-DD}` |
| 核对项 | 本次核对的内容(如「会话存储位置未变」) |
| 状态 | `✓` 一致 / `⚠` 不一致或仓库未登记 / `○` 不适用或跳过 |

**本项目示例**(2 个代码仓,每个 Tech Design 至少核对其所触及的仓):

```markdown
## 实现基线

| 仓库 | 分支 | SHA | 核对日期 | 核对项 | 状态 |
|------|------|-----|----------|--------|------|
| B | {后端分支} | {短SHA} | {YYYY-MM-DD} | {核对内容} | ✓ |
| C | {前端分支} | {短SHA} | {YYYY-MM-DD} | {核对内容} | ✓ |
```

> 只涉及单端的 Tech Design,把**不涉及**的那一行写 `○` 并在「核对项」注明「本次不涉及前端」。

**脚本**:`scripts/check-repo-baseline.sh`。仓库 → 本地路径的映射**从 §1.1「本地路径」列解析**,脚本内不硬编码任何仓名。未登记的仓库记 `⚠` 并跳过存在性校验。

### 1.7 证据锚点 (Evidence Anchors)

> **本节用途**:任何关于**当前实现状态**的结论都必须带证据锚点,使第三方可独立复核。
> **性质**:这是**约定 + 人工抽查**,不是脚本门禁。

**格式**:

```text
{仓库标识}@{短SHA}:{路径}#L{行号}
```

例:`B@a1b2c3d:src/service.ts#L42`。仓库标识取自 §1.1。

**取短 SHA**:

```bash
git -C <仓库本地路径> rev-parse --short HEAD
```

**规则**:

| 断言类型 | 是否需要锚点 |
|----------|--------------|
| 现状断言(已实现 / 已修复 / 当前不存在) | **需要** |
| 设计意图 / 未来计划 | 不需要 |
| 规格文档内的约定 | 不需要,引用仓内文档路径即可 |

- 锚点必须能定位到**具体行**,不写 `#L?`
- 锚点里的路径是**仓内相对路径**,不带 `{标识}/` 前缀

**0 代码仓项目**:本节不适用。现状断言改为引用仓内文档路径(如 `prd/2026-07-03/login.md`)。(本项目有 B / C,适用上方锚点格式)

**校验方式**:`/validate-spec` 复核阶段**人工抽查**,命中无锚点的现状结论时报告 `⚠`,但**不改变脚本退出码**。脚本无法判定「已实现」是否有证据,故不做强制门禁。

---

## 2. 项目信息 (Project Info)

| 字段 | 值 |
|------|-----|
| 项目类型 | 业务系统 (商品陈列) |
| 项目描述 | merchandising 商品陈列平台。本仓为规格真源,关联 B (后端 Java) / C (前端 Vue3) 两个代码仓,规格产出后由 coding agent 消费实施 |
| 沟通语言 | 中文 |
| 负责人 | merchandising 团队 |

> **本仓与代码仓的关系**:本仓只存规格与计划。**不**在 A 仓写业务代码。
> 实施在 B / C 仓进行,各自独立分支与提交;实现完成后人工回写 A 仓 Plan 状态为 `Implemented`。

---

## 3. 使用方式 (Usage)

### 3.1 工作流 (5 步 spec)

> **5 步工作流与 HOW_TO_USE.md 对齐**:
> Step 0(收集原始需求) + Step 1(加工为 PRD) + Step 2(PRD → Tech Design) + Step 3(Tech Design → Plan) + Step 4(TDD 执行)
>
> **本项目有 2 个代码仓 (B / C),Step 4 (TDD) 启用**。规格进入 `Ready` 后由 coding agent 在 B / C 仓实施,完成后人工回写 `Implemented`。
>
> **Layer 4 (`test_cases/`)** 是可选质量层,启用时通过 `/to-test-cases` 生成黑盒用例,作为 Plan V 用例的参考比照对象。

| 步骤 | 输入 | 输出 | 状态 | 位置 |
|------|------|------|------|------|
| Step 0: 收集原始需求 | 外部输入 | 原始素材 | (只读) | `prd/{YYYY-MM-DD}/` 或 `material/{YYYY-MM-DD}/` (可选) |
| Step 1: 加工为 PRD | `/to-prd <date>` | PRD | Ready | `prd/{date}/{topic}.md` |
| Step 2: PRD → Tech Design | `/to-tech-design <prd-path>` | Tech Design(v4 默认 4 子文件 / v3 存量 6+1) | Ready | `tech_design/{date}-{topic}/` |
| Step 3: Tech Design → Plan | `/to-plan <tech-design-dir>` | Plan | Ready | `plan/{date}-{topic}/{topic}.md` |
| Step 4: TDD 执行(仅 ≥1 外部代码仓) | Plan | 代码 + 测试 | Ready → Implemented | 外部代码仓 |
| Layer 4(可选) 测试用例 | `/to-test-cases <prd-path> <td-dir>` | Test Cases(主/冒烟/要点) | Draft → Ready → Implemented | `test_cases/{date}/{topic}.md` |

> 代码仓库存在时,规格完成(`Ready`)后进入 Step 4 实施,实施完成回写 `Implemented`。
> **不产出 Draft 状态**。`to-prd` / `to-tech-design` / `to-plan` skill 完成后直接设 `Ready`。
> **Layer 4 例外**: Test Cases 初始产出 `Draft`,评审通过 + 要点伴生就位后升 `Ready`(见 §3.3)。
> 详细调用示例见 §3.6,Skill 注册见 §3.7。
> **可选层**: `material/`(Layer 0 素材区)、`test_cases/`(Layer 4 质量层)、`test-business/`(业务知识库)、`deep/`(理解底座)、PRD 台账 + 关联矩阵 仅在项目启用时存在。不存在则跳过对应校验。

### 3.2 命名规范

**目录命名**:
- `prd/{YYYY-MM-DD}/{topic}.md` · 日期分桶,PRD 文件名用小写连字符 topic
- `material/{YYYY-MM-DD}/` · 可选 Layer 0 素材区(项目启用时存在)
- `tech_design/{YYYY-MM-DD}-{topic}/` · 日期 + topic 子文件夹
- `plan/{YYYY-MM-DD}-{topic}/{topic}.md` · 日期 + topic 子文件夹 + 单文件
- `test_cases/{YYYY-MM-DD}/{topic}.md` · 可选 Layer 4 质量层(项目启用时存在;允许 `-smoke` / `-key-points` 后缀)
- `test-business/{product}/` · 可选业务知识库(`/to-test-cases` Step 2 自动创建;积累业务规则 + 已知陷阱 + 系统特定测试点)
- `deep/` · 可选理解底座(项目启用时存在)

**topic 规则**:
- 使用**小写连字符**
- tech_design 和 plan 的文件夹名**必须带日期前缀**

**跨文件引用**(相对路径):
- Tech Design 引用 PRD: `../../prd/{date}/{topic}.md`
- Plan 引用 Tech Design: `../../tech_design/{date}-{topic}/{topic}.md`
- Plan 引用 PRD: `../../prd/{date}/{topic}.md`

**Tech Design 代际选择**(默认 v4, v3 为存量 / 显式 opt-in):
- **v4** (默认): `README.md` 综合描述 + `ards.md` 架构决策+方案对比+探索机制 + `apis.md` 接口契约+时序 + `data-model.md` ER 图
- **v3** (存量): `README.md` + `decisions.md` + `data-model.md` + `api-contracts.md` + `scenario-mapping.md` + `quality.md` (+ `interactions.md` 条件)
- 模板来源: `schema/tech_design/` (v4) 与 `schema/tech_design/v3/` (v3)

### 3.3 状态流转

| 层 | 起始 | 终态 | 触发 |
|----|------|------|------|
| PRD | Draft | Ready | Step 1 完成所有门禁清单 |
| Tech Design | Draft | Ready | Step 2 完成所有门禁清单 |
| Plan | Draft | Ready | Step 3 完成所有门禁清单 |
| Test Cases(可选) | Draft | Ready → Implemented | `/to-test-cases` 产出 Draft,评审通过 + `{topic}-key-points.md` 伴生 → Ready;执行通过 → Implemented(由 `/sync-status` 编排) |

> **代码仓库存在**: 规格侧有 `Implemented` 回写 (Step 4 实施完成后人工回写 Plan 状态)。
> Test Cases 状态由 `/sync-status` 编排(Implemented 回写 / Deprecated 级联 / 复审回退 Draft),独立于三件套生命周期。

### 3.4 门禁清单 (wiki 视角)

> wiki 只检查**规格侧**的门禁清单。**实现侧**(代码/Lint/测试)的门禁清单见各代码仓 AGENTS。
> 本项目有 2 个代码仓 (B / C),两侧都要过。
>
> **门禁清单的权威定义在 `schema/*` 各文件,本节不复制**。只列速查索引(避免与 schema 漂移)。

| 层 | 门禁清单位置 | 验证方式 |
|----|-------------|----------|
| PRD | `schema/prd.md` 全文 | `/validate-spec` |
| Tech Design | `schema/tech_design/README.md` + `ards.md` + `apis.md` + `data-model.md` (v4 默认 4 子文件) | `/validate-spec` |
| Plan | `schema/plan.md` 完成检查段 | `/validate-spec` |
| Test Cases(可选) | `schema/test_case.md` 全文 | `/validate-spec`(目录存在时才校验) |
| 实现基线(可选) | Tech Design `## 实现基线` 段 | `scripts/check-repo-baseline.sh`(有关联代码仓时才校验) |
| PRD 台账 / 关联矩阵(可选) | `schema/prd-ledger.md` / `schema/prd-matrix.md` | `scripts/sync-prd.sh` / `scripts/check-traceability.sh`(层存在时才校验) |

**调用方式**:三件套 Ready 前,跑 `validate-spec` skill(自动跑全部校验脚本),全部 `✓` 方可标 Ready。Test Cases Ready 前同样跑一次(目录存在时)。

### 3.5 禁止行为

- ❌ **不修改 `schema/` 下的模板文件**(除非显式要求更新工作流规范)
- ❌ **不省略日期前缀**。`tech_design/` 和 `plan/` 文件夹名必须带 `{YYYY-MM-DD}-`
- ❌ **不在 Plan 中写完整代码**。只写策略和约束,代码在 TDD 阶段产出
- ❌ **不遗漏 PRD 场景**。Tech Design 场景映射必须覆盖所有 Given/When/Then
- ❌ **不假设代码仓完成**。规格 Ready ≠ 代码已实现,回写 `Implemented` 前必须核对 B / C 仓的实际提交
- ❌ **不绕过 skill 直接拼 schema/scripts 命令**。保持调用入口单一,agent 首选 `skills/<name>/SKILL.md`

### 3.6 调用示例

```bash
# Step 1: 原始需求 → PRD
/to-prd <date>                              # 例: /to-prd 2026-07-03

# Step 2: PRD → Tech Design(单文件)
/to-tech-design <prd-path>                  # 例: /to-tech-design prd/2026-07-03/login.md
/to-tech-design <prd-dir>                   # 例: /to-tech-design prd/2026-07-03/  (批量)

# Step 3: Tech Design → Plan
/to-plan <tech-design-dir>                  # 例: /to-plan tech_design/2026-07-03-login/

# 验证(任意时点跑,产完就跑)
/validate-spec
```

> **Layer 4(可选)**:Test Cases 与状态编排:

```bash
# Test Cases: PRD + TD → 黑盒用例
/to-test-cases <prd-path> <tech-design-dir>   # 例: /to-test-cases prd/2026-07-03/login.md tech_design/2026-07-03-login/

# 状态编排:Implemented 回写 / Deprecated 级联 / 复审回退 Draft
/sync-status implement <plan-path>           # 三件套 Implemented 回写
/sync-status deprecate <prd-or-td-path>      # Deprecated 级联
/sync-status rollback <prd-path>             # 复审回退 Draft
/sync-status test-done <test-case-path>      # Test Cases Ready → Implemented
```

### 3.7 Skill 注册

skills 通过 `setup.sh` 注册到 agent 的 skills 目录(支持 claude / qoder / pi / cursor):

```bash
bash <repo>/skills/setup.sh                  # 注册到默认 4 个目录
bash <repo>/skills/setup.sh --unregister     # 注销所有
bash <repo>/skills/setup.sh --target <dir>   # 注册到指定目录
```

注册后 agent 可识别 `/to-prd` / `/to-tech-design` / `/to-plan` / `/validate-spec` / `/to-test-cases` / `/sync-status` 命令。

### 3.8 快速定位文件

| 需要什么 | 去哪里找 |
|----------|----------|
| **执行工作流**(首选) | `skills/{to-prd,to-tech-design,to-plan,validate-spec,to-test-cases,sync-status}/SKILL.md` ★ |
| Skill 注册到 agent | `skills/setup.sh`(注册到 `~/.claude/skills/` 等) |
| 仓库入口(总览) | `README.md` |
| PRD 模板 | `schema/prd.md` |
| Tech Design 模板 | `schema/tech_design/` (v4 默认 4 子模板) |
| Plan 模板 | `schema/plan.md` |
| Test Case 模板(可选) | `schema/test_case.md` |
| PRD 台账模板(可选) | `schema/prd-ledger.md` |
| PRD 关联矩阵模板(可选) | `schema/prd-matrix.md` |
| 工作流全貌 | `HOW_TO_USE.md` |
| 概念参考 | `new-factors.md` |
| 机制契约(吸收取舍 + 验收标准) | `docs/mechanism-contract.md` |
| 某功能的需求 | `prd/{YYYY-MM-DD}/{topic}.md` |
| 某功能的设计 | `tech_design/{YYYY-MM-DD}-{topic}/` |
| 某功能的实施计划 | `plan/{YYYY-MM-DD}-{topic}/{topic}.md` |
| 某功能的测试用例(可选) | `test_cases/{YYYY-MM-DD}/{topic}.md`(层概览见 `test_cases/README.md`) |
| 原始素材(可选) | `material/{YYYY-MM-DD}/`(层概览见 `material/README.md`) |
| 理解底座(可选) | `deep/` |
| 命名校验 | `scripts/check-naming.sh` |
| 字段校验 | `scripts/check-md-schema.sh` |
| 追溯校验 | `scripts/check-traceability.sh` |
| 实现基线校验(可选) | `scripts/check-repo-baseline.sh` |
| PRD 台账同步(可选) | `scripts/sync-prd.sh` |
| 用例索引再生 | `scripts/sync-test-index.sh` |
| 历史参考(已弃用方案) | `legacy/` |

---

## 4. 附录 (Appendices)

### A. 定制指南 (供 fork 参考)

> 本节为 fork SSD-Template 的项目提供定制指南。**本 fork 已应用**:
> - 维度 1: 2 个代码仓库 (B 后端 / C 前端),本仓库为唯一规格仓库
> - 维度 2: 业务系统 (商品陈列,中文沟通)
> - 维度 3: 标准工作流 (Step 4 TDD 启用)
> - 维度 4: 见下文 B/C

**fork 时必改**:
- 维度 1.1: 仓库清单(填入实际的代码仓库) ← 本 fork 已改
- 维度 1.2: 跨仓引用(增加"指向代码仓库"行) ← 本 fork 已改
- 维度 1.3: 代码仓的本地 AGENTS(填入实际路径) ← 本 fork 已改
- 维度 2: 项目信息(替换为实际项目) ← 本 fork 已改

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
- **反例论证**:见 [HOW_TO_USE.md "为什么不引入 `Implementing` 中间态"](HOW_TO_USE.md#为什么不引入-implementing-中间态)。仅在 (B) 不可行时才升级到 (C)

### B. Skill 策略选择

> SSD-Template 自身选择**(a) 维护 `skills/` 目录**。所有执行流程封装在 `skills/<name>/SKILL.md`。
> 这是基于多仓 fork 经验(内联 prompt 步骤易漂移)进化出的设计。
> **fork 项目推荐沿用本策略**。直接复制 `skills/` 目录,无需重建 prompt。

### C. Evaluator 阶段启用条件

> 当前**不启用** Evaluator 阶段(决策影响 < 3 个 PRD,无需独立审计)。
>
> 启用条件:
> - 决策影响 ≥ 3 个 PRD
> - 涉及长期架构(数据库/通信协议/部署拓扑)
> - 即将上线的功能需独立审计
>
> 启用方式: 引入 sages/gaoyao 5 phase 审计。
