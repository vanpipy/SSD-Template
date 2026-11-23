# AGENTS.md

> AI agent 在**规格仓库(spec repo)**工作时的操作契约。
> **核心原则**:以 skill 为执行单元。agent 不直接拼装 `schema/` 模板或 `scripts/` 校验脚本,而是调用 `.codex/skills/<name>/SKILL.md`。
> 每次开始工作前,先读本文件 + 读对应 skill 的 `SKILL.md`(skill 内部已封装 schema 读取 + scripts 校验流程)。
>
> **契约真源**:`WORKFLOW.md`(状态推进、调度依据、硬禁止以它为准)。
> **状态与调度的唯一入口**:`scripts/ssdctl.py`(实施契约 `.swarm/requirements/agent-first-implementation.md` §5);
> 调度依据 = **仓内 `ssdctl scan`**,不是外部编排器(实施契约 §7、§11)。
> **推进主体**:agent 自主推进,人类**可**手动介入(决策记录 `control/decisions/`)。

---

## 1. 仓库 (Repositories)

> **本仓库是文档/规格仓库,不是代码仓库**。它永远是 spec 真源,只存规格与计划。
> 是否关联外部代码仓由项目决定:**关联时**在 §1.1 登记一行;**不关联时**表里只有 A 行,按 §1.6 的「0 代码仓」写法执行。

### 1.1 仓库清单

> **本节用途**:登记本项目的**全部仓库**(本 spec 仓 + 可选的外部代码仓),是 §1.2 / §1.3 / §1.4 / §1.5 / §1.6 / §1.7 的**唯一数据源**(single source of truth)。
> **禁止**:本节**不**附 check/detect 脚本。仓库存在性由 §1.4 Clone Protocol 处理(agent 主动 `git clone`,不写自定义脚本)。

**本模板默认 0 关联代码仓** —— 下表只有 A 行即表示「纯规格仓」。

| 标识 | 仓库 | Git URL | 本地路径 | 角色 | 主要语言 | 说明 |
|------|------|---------|----------|------|----------|------|
| **A** | (本仓库) | (本仓 remote) | `./` | Wiki / Spec | Markdown | 规格真源,固定为 A |

> **填写指引**(每个外部代码仓一行):
> - **标识**:单字母逻辑标签(A / B / C / ...),**稳定不变**。目录名可随 fork 改名,而引用语法 `{B}/path` 不受影响。
> - **Git URL / 本地路径**:`git clone` 用的地址,以及该仓在**本地文件系统**的位置;§1.4 的 clone 命令与 §1.6 的基线校验都按「本地路径」列解析。
> - **角色**:`Wiki / Spec` 或 `Code workspace`;**主要语言**仅供阅读者参考,不参与校验。
> - **禁止**:把目录名当标识、登记未实际 clone 的仓、写口语化名称(如「后端仓库」)。

#### 标识约定

| 标识 | 角色 | 说明 |
|------|------|------|
| **A** | Wiki / Spec 仓库 | **本仓库**(固定),所有 spec 的源 |
| **B** / **C** / ... | Code workspace | §1.1 表中登记的外部代码仓 |
| **N** | 占位符 | §1.1 表中任意非 A 行(便于泛指) |

### 1.2 跨仓库引用约定

| 引用类型 | 写法 | 示例 | 来源 |
|----------|------|------|------|
| 本仓库内引用 (A) | `schema/path` / `prd/path` / `tech_design/path` / `plan/path` | `schema/prd.md`, `prd/2026-11-22/layer-checklist.md` | 当前文件位置 |
| 跨仓库引用 (B / C) | `{标识}/{path}` (用 §1.1 标识列) | `{B}/service/src/...`, `{C}/src/modules/...` | §1.1 标识 + 本地路径 |

**跨仓库引用规则**:

- `{标识}` 必须**严格**匹配 §1.1 "标识" 列,一一对应
- 路径**相对于该标识的 本地路径**(如 `{B}/service/src/x` 解析为 §1.1 B 行 本地路径 + `/service/src/x`)
- **禁止**口语化引用(`后端仓库` / `前端项目` 等)
- **禁止**在 A 仓 spec 文件中引用 `src/` / `cmd/` / `pkg/` / `internal/` 等代码目录前缀。这些是外部代码仓内部约定,A 不应假设
- 引用外部仓路径时**必须带仓库内的顶层模块/目录前缀**(多模块结构的仓尤其需要)

> 多仓项目 Plan 的 Change 分仓规则见 §1.5,`to-plan` skill 以该节为准。

### 1.3 代码仓的本地 AGENTS

> 项目关联代码仓时,本节登记各代码仓的 AGENTS.md 路径,便于 §3.4 实现侧门禁清单被引用。

| 标识 | AGENTS.md 路径 |
|------|---------------|
| **A** | `./AGENTS.md` (本文件) |
| **B** / **C** / ... | (按 §1.1 本地路径填写) |

> **实现侧门禁清单生效**:§3.4 完成检查的代码 / Lint / 测试项由各代码仓自己的 AGENTS.md 定义。
> 标识 → AGENTS 路径的映射应与 §1.1 同步。

### 1.4 工作开始前 · 仓库补齐 (Clone Protocol)

> **本节用途**:定义 agent 在 §3 工作流开始前如何确保 §1.1 列出的所有仓库已存在于本地工作区。
> **原则**:补齐操作由 agent 主动执行 `git clone`,**不**写自定义 check 脚本。

#### Step 1 · 核对 A (本仓库)

```bash
git remote -v
# output 应与 §1.1 A 行 Git URL 一致
```

不一致 → **停止**,先解决目录错误再继续(可能身在 fork 而非本仓库)。

#### Step 2 · 遍历 §1.1,补齐每个非 A 行

```bash
[[ -d <本地路径> ]] || git clone <Git URL> <本地路径>
```

> §1.1 只有 A 行时,本步骤无操作,直接进入 Step 3。

#### Step 3 · 验证工作区拓扑

```bash
ls -la ..
```

本地目录应呈现 §1.1 表的镜像布局(每个登记仓一个目录)。

#### Step 4 · 跨仓库引用启用

A 中的 spec 文件现在可通过 §1.2 `{标识}/path` 语法引用外部代码仓的具体文件。

### 1.5 多仓 Plan 编排 (Multi-repo Plan)

> **本节用途**:定义多仓项目产出 Plan 时,Change 如何按仓分组。
> **依据**:`.codex/skills/to-plan/SKILL.md` 的 10 处 `§1.5` 引用以此节为准。
> **0 代码仓项目**:不分组。Change 直接列在 `## 变更清单` 下,视为单一分组。

**分组规则**:

| 项 | 约定 |
|----|------|
| 仓库标识 | 取自 §1.1「标识」列。**不**用目录名,**不**用口语化名称 |
| 分组标题 | `#### {仓库标识} 变更`(固定 h4) |
| Change 条目 | `#### Change #N: {标识}/{路径}` |
| 文件路径 | **必须**带 `{标识}/` 前缀(§1.2 跨仓库引用约定) |
| 验证用例 (V) | **不按仓分组**,按业务场景聚合,一个场景可横跨多仓 |
| 组内说明 | 组标题下用 `>` 引用块写该仓承担的 KD / V 关注点 |

**为什么 Change 按仓分组**:Change 的「实施约束」是仓特定的。依赖管理 / 构建方式 / 部署拓扑 / 目录约定各仓不同,按仓分组后每个仓的实施者只读自己那节。

**为什么 V 用例不按仓分组**:V 用例描述的是**业务场景**,一个场景往往横跨多个仓。按场景聚合才能保证端到端覆盖不漏,按仓分组反而会把一个场景拆断。

**示例**(2 个代码仓 B / C 时):

```markdown
## 变更清单

#### B 变更

> KD-1 / V-1 主要约束 B 仓的接口编排与入参校验

#### Change #1: `B/service/controller/SessionController.java`
**遵循决策**: KD-1
**验证**: V-1

#### C 变更

> KD-2 / V-1 主要约束 C 仓的数据持久化与事务边界

#### Change #2: `C/service/session/SessionRepository.java`
**遵循决策**: KD-2
**验证**: V-1

### 验证用例 (V-1 跨仓覆盖,按场景聚合)
```

> **层级兼容**:`scripts/check-md-schema.sh` 按标题正则识别 `### Change #N:` 与 `#### Change #N:` 两种 Change 标题(不按嵌套层级),仓库组标题占 h4 时 Change 条目同样落 h4,V 用例仍用 h3 `### V-{n}:`。

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
| 仓库 | §1.1 登记的**标识**。脚本据此解析本地路径 |
| 分支 | 核对时的分支名 |
| SHA | 短 SHA,取法见 §1.7 |
| 核对日期 | 本次核对的日期 `{YYYY-MM-DD}` |
| 核对项 | 本次核对的内容 |
| 状态 | `✓` 一致 / `⚠` 不一致或仓库未登记 / `○` 不适用或跳过 |

**0 代码仓项目**:删除表格,改写单行 `> 不适用: 本项目无关联代码仓`(脚本按 `○` 跳过)。

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

**0 代码仓项目**:本节不适用。现状断言改为引用仓内文档路径(如 `prd/2026-11-22/layer-checklist.md`)。

**校验方式**:`validate-spec` skill 复核阶段**人工抽查**,命中无锚点的现状结论时报告 `⚠`,但**不改变脚本退出码**。脚本无法判定「已实现」是否有证据,故不做强制门禁。

---

## 2. 项目信息 (Project Info)

> **fork 时填写**。模板默认留占位,不要在模板仓里填具体业务。

| 字段 | 值 |
|------|-----|
| 项目类型 | (待填:业务系统 / 工具 / 平台 / ...) |
| 项目描述 | (待填:一句话说明本仓定位与关联代码仓) |
| 沟通语言 | (待填) |
| 负责人 | (待填) |

> **本仓与代码仓的关系**:本仓只存规格与计划。**不**在 A 仓写业务代码。
> 实施在外部代码仓进行,各自独立分支与提交;外部 PR merged 后,由 `ssdctl advance` 在**外部事实**证据齐备时代写 A 仓状态为 `Implemented`(实施契约 §5.2);**合并动作仍由人执行**。

---

## 3. 使用方式 (Usage)

### 3.1 工作流 (5 步 spec)

> Step 0(收集原始需求) + Step 1(加工为 PRD) + Step 2(PRD → Tech Design) + Step 3(Tech Design → Plan) + Step 4(TDD 执行)
>
> **本仓有 ≥1 关联代码仓时**,Step 4 启用:规格进入 `Ready` 后由 coding agent 在代码仓实施;外部 PR merged 后,
> `ssdctl advance` 在**外部事实**证据齐备时代写 `Implemented`(实施契约 §5.2),**合并动作仍由人执行**。
> **0 关联代码仓时**,Step 4 不存在,规格停留在 `Ready`。
>
> **Layer 4(`test_cases/`)** 是可选质量层,启用时通过 `to-test-cases` 生成黑盒用例,作为 Plan V 用例的参考比照对象。

| 步骤 | 输入 | 输出 | 状态 | 位置 |
|------|------|------|------|------|
| Step 0: 收集原始需求 | 外部输入 | 原始素材 | (只读) | `prd/{YYYY-MM-DD}/` 或 `material/{YYYY-MM-DD}/` (可选) |
| Step 1: 加工为 PRD | `to-prd <date>` | PRD | Draft → Ready | `prd/{date}/{topic}.md` |
| Step 2: PRD → Tech Design | `to-tech-design <prd-path>` | Tech Design(v4 默认 4 子文件 / v3 存量 6+1) | Draft → Ready | `tech_design/{date}-{topic}/` |
| Step 3: Tech Design → Plan | `to-plan <tech-design-dir>` | Plan | Draft → Ready | `plan/{date}-{topic}/{topic}.md` |
| Step 4: TDD 执行(仅 ≥1 外部代码仓) | Plan | 代码 + 测试 | Ready → Implemented | 外部代码仓 |
| Layer 4(可选) 测试用例 | `to-test-cases <prd-path> <td-dir>` | Test Cases(主/冒烟/要点) | Draft → Ready → Implemented | `test_cases/{date}/{topic}.md` |

> **agent 产出即 `Draft`**:agent 写出的三层规格一律停在 `Draft`;升 `Ready` 由 **`ssdctl advance` 按判据自动执行**
> (判据全绿即推进;人工可手动介入,见 §3.3)。判据的机器权威在 `schema/criteria.json`,**不由人工的主观判断决定**
> —— 人工介入表现为 `control/decisions/` 里的决定记录,而不是「人手敲状态行」。
> **Layer 4 例外**:Test Cases 初始产出 `Draft`,判据通过 + 要点伴生就位后升 `Ready`。
> **可选层**:`material/`(素材区)、`test_cases/`(Layer 4)、`test-business/`(业务知识库)、`deep/`(理解底座)、PRD 台账 + 关联矩阵。仅在项目启用时存在,不存在则跳过对应校验。

### 3.2 目录与命名规范

**目录命名**:
- `prd/{YYYY-MM-DD}/{topic}.md` · 日期分桶,PRD 文件名用小写连字符 topic
- `material/{YYYY-MM-DD}/` · 可选素材区(项目启用时存在)
- `tech_design/{YYYY-MM-DD}-{topic}/` · 日期 + topic 子文件夹
- `plan/{YYYY-MM-DD}-{topic}/{topic}.md` · 日期 + topic 子文件夹 + 单文件
- `test_cases/{YYYY-MM-DD}/{topic}.md` · 可选 Layer 4(允许 `-smoke` / `-key-points` 后缀)
- `test-business/{product}/` · 可选业务知识库
- `deep/` · 可选理解底座(项目启用时存在)

**topic 规则**:`^[a-z0-9]+(-[a-z0-9]+)*$`(小写字母与数字,中划线分隔)。
**tech_design 和 plan 的文件夹名必须带日期前缀**。层根只允许 `README.md` 与 `_index.md`。

**跨文件引用**(相对路径,必须两级):
- Tech Design 引用 PRD: `../../prd/{date}/{topic}.md`
- Plan 引用 Tech Design: `../../tech_design/{date}-{topic}/`
- Plan 引用 PRD: `../../prd/{date}/{topic}.md`

**Tech Design 代际选择**(默认 v4,v3 为存量 / 显式 opt-in):
- **v4**(默认):`README.md` 综合描述 + `ards.md` 架构决策 + `apis.md` 接口契约 + `data-model.md` ER 图
- **v3**(存量):`README.md` + `decisions.md` + `data-model.md` + `api-contracts.md` + `scenario-mapping.md` + `quality.md`(+ 条件 `interactions.md`)
- 模板来源: `schema/tech_design/`(v4)与 `schema/tech_design/v3/`(v3)

### 3.3 状态流转

**状态值(全层统一 4 值)**: `Draft` / `Ready` / `Implemented` / `Deprecated`。**不得自造状态名**。

| 状态 | 谁能发起 | 写入载体(一律由机器代写) | 准入条件 |
|------|--------|--------------------------|----------|
| `Draft` | **agent** | 产出文件本身的状态块(`> **状态**` / `> **状态主体**` / `> **状态时间**` / `> **状态依据**` 4 行;Draft 态后三行允许缺省) | 该层校验脚本 exit 0 |
| `Ready` | **agent(判据驱动)或人工(手动介入)** | **`bash scripts/ssdctl.sh advance` 代写**状态块 4 行 + 复审块 4 行(`> **评审人**` / `> **评审日期**` / `> **评审结论**` / `> **评审方式**`) | 该层全部 `blocking:true` 判据通过 + `upstream_ready`;`blocking:false` 失败项须有 `control/decisions/` 决定记录(实施契约 §4.2 / §5.2) |
| `Implemented` | **人工(外部事实)** | 同上,由 `advance --to Implemented` 代写;状态依据须含 `external:` 依据或 `--decision` 指定的外部事实介入记录 | 外部 PR merged 等**外部事实**齐备;三层必须**同时**进入 `Implemented`(不允许单层先转) |
| `Deprecated` | **agent 或人工** | 同上,由 `advance --to Deprecated` 代写 + 备注「级联自上游 {path}({日期})」 | 状态依据必须是 `decision:<path>#<anchor>` 或 `external:<ref>`,**不允许** `criteria:`(实施契约 §5.2) |

> **agent 权限天花板 = `Ready`**(由判据决定,不由人手决定)。agent 可产出文件、可跑门禁、可报告结论;判据全绿时由
> `bash scripts/ssdctl.sh advance` 代写 `Ready`。`Implemented` 仍需**外部事实**证据,不靠 agent 自述。
> **不得冒充人工**:`human:` 前缀**只能由人自己写**;agent 的署名一律 `agent:<id>`(实施契约 §2 INV-3、决策 D-07)。
> agent 不得代填人名、不得把 `评审方式` 写成「人工介入」。
> **状态推进必须走 `ssdctl advance`,不得手改状态行**:advance 负责校验判据、代写状态块与复审块、追加证据链
> (`control/evidence/**`,append-only)。手改状态行 = 绕过判据与证据链,属违规。
> **Ready 的机器可核验载体**是产物文件内的状态块 + 复审块;**每次转换都留可回读证据**,用
> `bash scripts/ssdctl.sh verify <artifact>` 复核三者一致。
> **Deprecated 级联**:上游转 `Deprecated` 时,引用它的下游 TD / Plan / Test Case 一并转 `Deprecated`。
> **Test Cases 状态**同样走 `ssdctl advance`(`Ready` / `Implemented` / `Deprecated`),独立于三件套生命周期;
> `advance --to` 不含 `Draft`,复审回退属人工介入,记录在 `control/decisions/`。

### 3.4 门禁清单 (wiki 视角)

> wiki 只检查**规格侧**的门禁清单。**实现侧**(代码 / Lint / 测试)的门禁清单见各代码仓自己的 AGENTS。
>
> **门禁清单的权威定义在 `schema/*` 各文件,本节不复制**。只列速查索引(避免与 schema 漂移)。

| 层 | 门禁清单位置 | 验证方式 |
|----|-------------|----------|
| PRD | `schema/prd.md` 全文 | `validate-spec` |
| Tech Design | `schema/tech_design/README.md` + `ards.md` + `apis.md` + `data-model.md` (v4 默认 4 子文件) | `validate-spec` |
| Plan | `schema/plan.md` 完成检查段 | `validate-spec` |
| Test Cases(可选) | `schema/test_case.md` 全文 | `validate-spec`(目录存在时才校验) |
| 实现基线(可选) | Tech Design `## 实现基线` 段 | `scripts/check-repo-baseline.sh`(有关联代码仓时才校验) |
| PRD 台账 / 关联矩阵(可选) | `schema/prd-ledger.md` / `schema/prd-matrix.md` | `scripts/sync-prd.sh` / `scripts/check-traceability.sh`(层存在时才校验) |

**调用方式**:用 `validate-spec` skill(它按层跑全部校验脚本),不要手拼脚本命令。脚本退出码是唯一判定依据:全部 `✓` 只说明**格式与追溯**合规;**能否进 `Ready` 由 `schema/criteria.json` 的判据决定**,由 `bash scripts/ssdctl.sh advance` 代写状态块与复审块(见 §3.3),既不由「✓ 的数量」决定,也不是人工敲状态行。

### 3.5 禁止行为

- ❌ **不修改 `schema/` 下的模板文件**(除非显式要求更新工作流规范)
- ❌ **不省略日期前缀**。`tech_design/` 和 `plan/` 文件夹名必须带 `{YYYY-MM-DD}-`
- ❌ **不在 Plan 中写完整代码**。只写策略和约束,代码在 TDD 阶段产出
- ❌ **不遗漏 PRD 场景**。Tech Design 场景映射必须覆盖所有 Given/When/Then
- ❌ **不假设代码仓完成**。规格 `Ready` ≠ 代码已实现,推进 `Implemented` 前必须有**外部事实**证据(外部 PR merged),并核对外部代码仓的实际提交
- ❌ **不冒充人工署名**。`human:` 前缀**只能由人自己写**;agent 只能署 `agent:<id>`,不得代填人名,不得把 `评审方式` 写成「人工介入」(实施契约 §2 INV-3、决策 D-07)
- ❌ **不手改状态行**。状态推进必须走 `bash scripts/ssdctl.sh advance` —— 由它校验判据、代写状态块与复审块、追加证据链;手改 = 绕过判据与证据链
- ❌ **不凭推测写终态**。`Implemented` 需 `external:` 依据或 `--decision` 指定的外部事实介入记录;`Deprecated` 的状态依据不允许写 `criteria:`
- ❌ **交互式会话内不绕过 skill 直接拼 schema/scripts 命令**。保持调用入口单一,agent 首选 `.codex/skills/<name>/SKILL.md`。(本仓自主流水线按 `WORKFLOW.md` §6 直接跑 scripts,不受此限)

### 3.6 调用示例

skill 定义在 `.codex/skills/<name>/SKILL.md`,front matter 只有 `name` 与 `description`。
**调用形态取决于宿主**:交互式会话里 agent 直接读该 SKILL.md 并按正文执行;宿主支持 slash 命令时可写成 `/to-prd`;本仓自主流水线里由 `WORKFLOW.md` 按 `ssdctl scan` 的调度结果驱动对应 skill。

```bash
# Step 1: 原始素材 → PRD
to-prd <date>                                # 例: to-prd 2026-11-22

# Step 2: PRD → Tech Design(单文件)
to-tech-design <prd-path>                    # 例: to-tech-design prd/2026-11-22/layer-checklist.md
to-tech-design <prd-dir>                     # 例: to-tech-design prd/2026-11-22/  (批量)

# Step 3: Tech Design → Plan
to-plan <tech-design-dir>                    # 例: to-plan tech_design/2026-11-22-layer-checklist/

# 验证(任意时点跑,产完就跑)
validate-spec
```

> **Layer 4(可选)**:Test Cases 的产出仍走 skill;**状态推进统一走 `scripts/ssdctl.py`**(实施契约 §5)——
> 不再存在「只有人能发起状态转换」这种单边授权:agent 依据判据自动推进,人可随时手动介入。

```bash
# Test Cases: PRD + TD → 黑盒用例
to-test-cases <prd-path> <tech-design-dir>   # 例: to-test-cases prd/2026-11-22/layer-checklist.md tech_design/2026-11-22-layer-checklist/
```

**状态与调度命令**(`scripts/ssdctl.py`,唯一入口;退出码 `0`=通过 / `1`=不通过 / `2`=用法或内部错误,实施契约 INV-7):

```bash
# 调度:仓内扫描,判本层是否可推进(调度依据,不是外部编排器)
bash scripts/ssdctl.sh scan [--json] [--layer L] [--check]

# 判据:单制品逐条评估
bash scripts/ssdctl.sh criteria <artifact> [--json]

# 全仓门禁(既有门禁 + 判据引擎 + 派生数据再生)
bash scripts/ssdctl.sh gate [--json]

# 状态推进(唯一写入路径;--to 不含 Draft)
bash scripts/ssdctl.sh advance <artifact> --to <Ready|Implemented|Deprecated> [--actor A] [--decision <path>#<anchor>] [--dry-run]

# 人工介入:待裁决清单 / 决定记录
bash scripts/ssdctl.sh queue <artifact> [--json]
bash scripts/ssdctl.sh decide --artifact <path> --action <approve|reject|hold|override> --actor <name> --reason <text> [--criterion <id>]

# 证据与复核
bash scripts/ssdctl.sh evidence [--artifact <path>] [--json]
bash scripts/ssdctl.sh verify <artifact>
```

> `advance --dry-run` **只校验、不写文件**;`advance` 校验失败时**不写任何文件**(退出码 1)。
> `--decision` 指向 `control/decisions/<YYYY-MM-DD>-<topic>.md#<anchor>`。
> **命令形态**:一律 `bash scripts/ssdctl.sh <子命令>` —— 它是 `scripts/ssdctl.py` 的解释器解析包装器。
> 不同机器上 `python` 未必可用(Windows 的 Microsoft Store 占位符会命中 exit 9009),`python3` 只在 POSIX 机器上有;
> 包装器依次尝试 `$SSDCTL_PYTHON` / `python3` / `python` / `py -3` /
> `~/.dsh/dsh-runtimes/*/dependencies/python/python.exe`,每个候选都通过 `-c 'import sys'` 自检,
> 全都不行时 exit 2 并列出试过的候选,**不静默继续**。
> 判据引擎的单元测试(CI 也跑这一条):
> `PY="$(bash scripts/ssdctl.sh --python)"; "$PY" -m unittest discover -s scripts/tests -t scripts/tests`

### 3.7 Skill 清单

skill 定义放在仓内 `.codex/skills/<name>/SKILL.md`,随仓库一起分发;agent 运行时直接读取该目录,无需额外注册步骤。

**仓内 skill 共 9 个**:8 个规格流水线 skill(下表 1-8)+ 1 个辅助工具(第 9 行 `commit`)。

| # | skill | 作用 | 输入 | 产出 |
|---|-------|------|------|------|
| 1 | `to-prd` | 原始素材 → PRD | `prd/{date}/*.md` | `prd/{date}/{topic}.md` |
| 2 | `to-tech-design` | PRD → Tech Design(v4 默认 4 子文件) | PRD 路径 | `tech_design/{date}-{topic}/` |
| 3 | `to-plan` | PRD + Tech Design → Plan | TD 目录 | `plan/{date}-{topic}/{topic}.md` |
| 4 | `validate-spec` | 全量校验 + 证据锚点抽查 | 整仓 / 单文件 / 单目录 | 校验报告(不产出制品) |
| 5 | `to-test-cases` | PRD + TD → 黑盒用例 | PRD 路径 + TD 目录 | `test_cases/{date}/{topic}.md`(+ `-smoke` / `-key-points`) |
| 6 | `sync-status` | 四层生命周期编排(只编排步骤) | 目标文档路径 | 编排指令与备注(**状态行由 `ssdctl advance` 写**) |
| 7 | `sync-prd` | 可选层 · PRD 台账同步 | 批次日期 | `material/{date}/PRDS.md` + 根 README 统计块 |
| 8 | `to-deep-understand` | 可选层 · 深度理解层 | 范围(可选) | `deep/`(只写 `deep/`,不改规格层) |
| 9 | `commit` | 辅助工具 · 产出符合仓库约定的 commit message(含 `Reviewed-by:` trailer,取值 = 复审块 `> **评审人**` 的实际值,可能是 `agent:<id>` 或人工 handle;不得写没签过的名字) | 变更内容 | commit message(不产出制品) |

> `sync-prd` 与 `to-deep-understand` 是**可选层** skill,默认不启用。
> skill 的 front matter 只保留 `name` 与 `description`;执行细节全在正文里。
> **状态写入的唯一入口是 `scripts/ssdctl.py`**:`sync-status` 只编排步骤,不直接改状态行(见 §3.3 / §3.5)。

### 3.8 快速定位文件

| 需要什么 | 去哪里找 |
|----------|----------|
| **执行工作流**(首选) | `.codex/skills/{to-prd,to-tech-design,to-plan,validate-spec,to-test-cases,sync-status,sync-prd,to-deep-understand}/SKILL.md` ★ |
| 仓库契约唯一真源 | `WORKFLOW.md` |
| 仓库入口(总览) | `README.md` |
| 工作流指南与状态机 | `WORKFLOW.md` §11 使用指南 / §5 状态推进规则 |
| PRD 模板 | `schema/prd.md` |
| Tech Design 模板 | `schema/tech_design/` (v4 默认 4 子模板) |
| Plan 模板 | `schema/plan.md` |
| Test Case 模板(可选) | `schema/test_case.md` |
| PRD 台账模板(可选) | `schema/prd-ledger.md` |
| PRD 关联矩阵模板(可选) | `schema/prd-matrix.md` |
| 层概览 | `prd/README.md` · `tech_design/README.md` · `plan/README.md` · `test_cases/README.md` · `material/README.md` |
| 某功能的需求 | `prd/{YYYY-MM-DD}/{topic}.md` |
| 某功能的设计 | `tech_design/{YYYY-MM-DD}-{topic}/` |
| 某功能的实施计划 | `plan/{YYYY-MM-DD}-{topic}/{topic}.md` |
| 某功能的测试用例(可选) | `test_cases/{YYYY-MM-DD}/{topic}.md` |
| 原始素材(可选) | `material/{YYYY-MM-DD}/` |
| 理解底座(可选) | `deep/` |
| 校验脚本 | `scripts/` |
| 命名校验 | `scripts/check-naming.sh` |
| 字段校验 | `scripts/check-md-schema.sh` |
| 追溯校验 | `scripts/check-traceability.sh` |
| 实现基线校验(可选) | `scripts/check-repo-baseline.sh` |
| PRD 台账同步(可选) | `scripts/sync-prd.sh` |
| 用例索引再生 | `scripts/sync-test-index.sh` |
| 文档死链校验 | `scripts/check-doc-links.py` |
| 历史代际 | `git log --all -- <path>`(仓内不再保留归档目录) |
| 概念参考 | `WORKFLOW.md` §12 概念参考 |

---

## 4. 附录 (Appendices)

### A. 定制指南 (供 fork 参考)

> **fork 时必改**:
> - 维度 1.1:仓库清单(填入实际的外部代码仓)
> - 维度 1.2:跨仓引用(增加"指向代码仓库"行)
> - 维度 1.3:代码仓的本地 AGENTS(填入实际路径)
> - 维度 2:项目信息(替换为实际项目)
>
> **fork 时保留**:维度 3 全部内容、维度 4 全部内容(可选)。

**多仓库 fork 时的关键约束**:
- 本仓库永远是 wiki,**不是**代码仓
- 跨仓引用使用 `{仓库标识}/path` 写法
- Step 4 (TDD) 在代码仓执行;外部 PR merged 后,由 `ssdctl advance` 在**外部事实**证据齐备时代写 wiki 状态为 `Implemented`(**合并动作仍由人执行**)
- 仓内调度依据 = **`ssdctl scan`**(实施契约 §7),不依赖外部 issue tracker

### fork 时可选:Step 4 启动模式

> fork 项目在 ≥1 关联代码仓时,需选择 Step 4(Plan → TDD)的启动模式。

**(B) Coding agent 自取(默认推荐)**:
- **适用**:AI coding agent fork(Claude Code / aider / Cursor / Codex 等)
- **工作量**:0 额外配置
- **原理**:Plan Ready = 工作信号,coding agent 直接消费本地 wiki
- **不需要**:`Implementing` 中间态 / 调度 issue / wiki agent kickoff
- **人工介入点**:执行合并动作;判据存在 `blocking:false` 失败项时补 `control/decisions/` 决定记录(`ssdctl decide`)。状态行本身由 `ssdctl advance` 代写

**(C) 显式调度(仅多 agent 协调需要)**:
- **适用**:多 code agent / 多 repo fork(罕见)
- **工作量**:+1 张状态图 + 1 套转换规则 + 1 个跨仓写权限
- **原理**:wiki agent 创建 kickoff issue,code agent 认领后执行
- **反例论证**:见 `WORKFLOW.md` §11.5「为什么不引入 `Implementing` 中间态」。仅在 (B) 不可行时才升级到 (C)

### B. Skill 策略选择

> 本模板选择**(a) 维护仓内 skill 目录**(`.codex/skills/`)。所有执行流程封装在 `.codex/skills/<name>/SKILL.md`。
> 这是基于多仓 fork 经验(内联 prompt 步骤易漂移)进化出的设计。
> **fork 项目推荐沿用本策略**:复制 `.codex/skills/` 目录,无需重建 prompt。

### C. Evaluator 阶段启用条件

> 当前**不启用** Evaluator 阶段。
>
> 启用条件:
> - 决策影响 ≥ 3 个 PRD
> - 涉及长期架构(数据库 / 通信协议 / 部署拓扑)
> - 即将上线的功能需独立审计
>
> 启用方式:引入 sages/gaoyao 5 phase 审计。
