# SDD 作业流程汇总

> **文档状态**:本文记录 **2026-11-22 agent-first 改造前**的流程基线。改造后的流程以 [WORKFLOW.md](../WORKFLOW.md) 与 `scripts/ssdctl.py` 为准(见 WORKFLOW.md §5 状态推进 / §7 调度);本文保留作决策留痕,文中「agent 天花板 = `Draft`」「只由人回写」等表述均为**改前基线**,不再适用。

> **行号基线说明**:本文中的 `WORKFLOW.md:NNN` 与 `HOW_TO_USE.md:NNN` 行号引用指向 **2026-11-22 agent-first 改造前**的基线文件(commit `6fe6c4c`);行号不再对应现文件位置,保留原文仅作取证。

> **本文件是派生视图,不新增权威。** 冲突时一律以以下分列的权威为准:
> [WORKFLOW.md](../WORKFLOW.md)(agent 工作契约 · 仓根唯一真源;**怎么用**见 §11 使用指南) ·
> [AGENTS.md](../AGENTS.md)(仓库操作契约) ·
> `schema/**`(模板与门禁权威定义) ·
> `scripts/**`(裁判)。
>
> 本文件只回答一个问题:**一次作业从需求到归档,到底怎么走完。**
>
> 配套的**分析**见 [process-analysis.md](process-analysis.md):本文件说流程长什么样,那份说它意味着什么、哪里是空的。

---

## 1. 一句话

> 一次作业 = **一个 issue = 一层产物 = 一个工作区 = 一个 DSH turn**。
> agent 产出**永远停在 `Draft`**,门禁只判**形状与追溯**,升 `Ready` 与 `Implemented` **只由人**。

---

## 2. 三个正交的坐标系(先分清,后面才不会混)

| 坐标系 | 回答什么 | 谁负责 | 现状 |
|---|---|---|---|
| **产物契约** | 一个工作项**长什么样**:层路径 / 必填段 / 追溯 ID / 状态枚举 | `schema/**` + `scripts/**` | ✅ 完备 |
| **编排契约** | 一个工作项**怎么流转**:身份 / 状态 / 依赖 / 续跑 / 隔离 / 证据 / 签字 | `WORKFLOW.md` + runner | 🟡 部分(依赖闸门与写面缺失) |
| **持久化后端** | 状态**存在哪** | 文件系统(替代 Linear + GitHub) | ❌ 未落地 |

> Symphony 提供的是**中间那层的形状**;它自己不用文件系统当真相源,所以第三层是自造的。

---

## 3. 主干:5 步 + 1 可选层

```text
Step 0 原始素材 ──▶ Step 1 PRD ──▶ Step 2 Tech Design ──▶ Step 3 Plan ──▶ Step 4 外部代码仓 TDD
   (只读)            Layer 1       Layer 2(v4 4 子文件)   Layer 3          (≥1 关联代码仓才存在)
                                        │
                                        └──▶ Layer 4 Test Cases(可选)
```

| 步 | 输入 | 输出 | 状态 | 位置 |
|---|---|---|---|---|
| 0 收集原始需求 | 外部输入 | 原始素材(只读) | — | `prd/{YYYY-MM-DD}/*.md` 或 `material/{YYYY-MM-DD}/` |
| 1 加工为 PRD | 素材 + issue | PRD | `Draft` → 人签 → `Ready` | `prd/{date}/{topic}.md` |
| 2 PRD → TD | PRD(`Ready`) | Tech Design v4 | `Draft` → 人签 → `Ready` | `tech_design/{date}-{topic}/` |
| 3 TD → Plan | TD(`Ready`) | Plan | `Draft` → 人签 → `Ready` | `plan/{date}-{topic}/{topic}.md` |
| 4 TDD 执行 | Plan | 代码 + 测试 | 人工回写 → `Implemented` | **外部**代码仓 |
| L4 测试用例(可选) | PRD + TD | 黑盒用例 | `Draft` → `Ready` → `Implemented` | `test_cases/{date}/{topic}.md` |

**跨层硬约束(⚠ 流程义务,不是机器门禁)**:上游必须已是 `Ready` 才准写下游;缺上游 / 上游不是 `Ready` ⇒ **不产出猜测的规格**,如实报告并结束。

> **这条今天由谁执行?** 只有 `WORKFLOW.md` 的上游表(`WORKFLOW.md:92-96`)与 `WORKFLOW.md:302` —— 即 **agent 读自己的 prompt 时遵守**。
> **没有任何脚本判定它**:`scripts/` 里唯一的跨层状态比较是 `Deprecated` 级联(`check-traceability.sh:542-544` / `:552-554` / `:570-572`);`Ready` 在 `check-md-schema.sh` 中**只校验本制品自己的复审三行**(`check-md-schema.sh:324-347`)。
> **实测反证**(临时副本,已删除):`Draft PRD → Draft TD → Draft Plan → Draft TC` 全链,**5 个门禁全 exit 0** —— 上游不是 `Ready` 也照样能写出下游并全绿。
> ⇒ 这条规则的**归属裁决**见 §12(待决)。

---

## 4. 每层规格卡

### Layer 1 · PRD

- **路径**:`prd/{YYYY-MM-DD}/{topic}.md`(`topic` = `^[a-z0-9]+(-[a-z0-9]+)*$`)
- **机器必填 5 段**:`## 为什么 (Why)` · `## 目标 (Goal)` · `## 场景 (Scenarios)` · `## 不在范围内 (Out of Scope)` · `## 复审 (Review)`
- **推荐段**(不参与机器校验):`## 链接 (Links)` · `## 变更记录 (Change Log)`
- **状态行**:`> **状态**: Draft`
- **场景要求**:正常路径 + 至少一个异常(`**But**` 分支)

### Layer 2 · Tech Design(默认 v4)

- **路径**:`tech_design/{YYYY-MM-DD}-{topic}/`,**4 个子文件**
- **必填子文件**:`README.md` · `ards.md` · `apis.md` · `data-model.md`
- **每个子文件**都要有 `## 门禁清单 (Completion Gate)` + `## 变更记录 (Change Log)`
- **`README.md` 额外**:`## 场景映射 (Scenario Mapping)`(固定 6 列)+ `## 实现基线 (Implementation Baseline)`(6 列快照)
- **代际**:v4 = 默认;v3 六件套仅存量目录或显式 opt-in
- **场景完整性**:PRD 每个 Given/When/Then(含 `**But**`)都必须在场景映射表里出现

### Layer 3 · Plan

- **路径**:`plan/{YYYY-MM-DD}-{topic}/{topic}.md`(**文件名 == 目录 topic**)
- **必填段**:`## 变更清单 (Changes)`(`### Change #1:`)+ `### V-1:` + `## 跨文件引用对账 (Cross-Reference Reconciliation)` + `## 复审 (Review)`
- **完整 8 段**:变更索引 / 变更清单 / TDD 执行流程 / 跨文件引用对账 / 验证用例(V) / 业务约束 / 开发约束 / 完成检查(实现层 / 验证层 / 引用层 / 流程层)
- **v2 单段 Plan 不再豁免**,一律判违规
- **多仓**:Change 按仓分组(`#### {标识} 变更`),**V 用例不按仓分组**(按业务场景聚合)
- **不写完整代码**:Plan 只写策略与约束

### Layer 4 · Test Cases(可选)

- **路径**:`test_cases/{YYYY-MM-DD}/{topic}.md`(可另出 `-smoke.md` / `-key-points.md`)
- **元信息 7 必填**:主题 / 业务产品 / 目标平台 / 来源 / 生成日期 / 状态 / 用例总数
- **3 可选**:来源 Tech Design / 来源 Plan / 最后更新
- **必填段**:`## 用例总览 (Test Suite Overview)`

---

## 5. 状态机:两套状态,一条强制关系

| | 载体 | 取值 | 谁写 |
|---|---|---|---|
| **产物状态** | 产物文件的状态行 | `Draft` / `Ready` / `Implemented` / `Deprecated` | **只由人**(agent 天花板 = `Draft`) |
| **编排状态**(规划中) | 工作项文件的 `state` | `Todo` / `In Progress` / `Review` / `Done` / `Cancelled` | runner 推进,人裁决 |

**唯一强制关系**:
> 编排状态 = `Done` ⇒ 产物状态 ∈ {`Ready`, `Implemented`} 且评审 `decision == approve`。
> 反向不强制(产物已 `Ready` 但工作项未归档是合法的)。

**状态推进规则**:

| 当前 → 下一 | 谁写 | 准入条件 |
|---|---|---|
| — → `Draft` | agent | 产物写完 + 该层门禁全绿 |
| `Draft` → `Ready` | **人** | 复审段三行填真值(`评审人` / `评审日期` / `评审结论`) |
| `Ready` → `Implemented` | **人** | ≥1 外部代码仓:TDD 全过 + 外部 PR merged + **三件套同时**回写 |
| `*` → `Deprecated` | **人** | 需求废弃 / 复审决定;上游废弃时下游级联 |

**不引入 `Implementing` 中间态** —— 它会增加一张状态图 + 一套转换规则 + 一个跨仓写权限,解决的都是代码仓自己能解决的问题(git branch / PR list 就是权威数据源)。

---

## 6. 门禁:9 个脚本,5 必跑 + 4 条件

退出码:`0` = 通过,`1` = 存在违规,`2` = 调用 / 环境错误。**脚本缺失 = 跳过,不是失败。**

| 脚本 | 何时跑 | 查什么 |
|---|---|---|
| `scripts/check-naming.sh` | 每次 | 目录 / 文件命名与层结构形状 |
| `scripts/check-md-schema.sh` | 每次 | 必填段、状态枚举、阶段感知 |
| `scripts/check-traceability.sh` | 每次 | 跨层引用闭环(KD / V / FR / SYS / MOD) |
| `scripts/check-doc-links.py` | 每次 | 仓内 Markdown 相对链接死链 |
| `scripts/check-line-endings.sh` | 每次 | 受版本控制的文本文件不得含 CR |
| `scripts/check-repo-baseline.sh` | **TD 有产物**时 | `## 实现基线` 的 6 列快照 |
| `scripts/sync-prd.sh` | **`material/` 存在**时 | PRD 台账 + 根 README 统计块(再生) |
| `scripts/sync-test-index.sh` | **用例层有产物**时 | `test_cases/_index.md`(再生) |
| `scripts/deep-scan.py` | **`deep/` 存在**时 | 理解底座台账 |

**再生块规则**:`--check` 退出 1(提示已过期)⇒ 跑一次**写模式** ⇒ 再 `--check` 复查;**判定取第二次**。写模式幂等;**不得手改**统计块 / `_index.md` / 台账。

**空转语义**:层目录不存在 ⇒ 该层跳过;层目录存在但无制品 ⇒ ⚠ 且 exit 0;**全仓无任何产物 ⇒ exit 1**。

**阶段感知**:门禁必须接受 agent 的合法中间产物(`Draft` PRD 缺复审三行 ⇒ 通过);`Ready` 阶段则三行必须是真值。

---

## 7. 编排运行时:runner 的一轮

`WORKFLOW.md` 的 front matter = 编排配置;正文 = 每个 issue 一次的 agent prompt(只有 `issue.*` 与 `attempt` 两个合法模板变量)。

```text
1. 选活        select_issues: state ∈ active ∧ state ∉ terminal ∧ is_routable(labels)
2. 建工作区    prepare_workspace → after_create hook(clone + core.autocrlf=false)
3. before_run  hook
4. 取会话      {workspace.root}/.symphony/sessions.json → (attempts, session_id)
5. 渲 prompt   issue.* + attempt(首轮为空 ⇒ 走「首轮分支」)
6. 跑一个 turn  有 session ⇒ run_turn(session_id);否则 start_session
7. 收产物      prd/ tech_design/ plan/ test_cases/ material/ 下排除 README.md 与 _index.md
8. after_run   hook
9. 跑门禁      5 必跑 + 4 条件;任一非 0 ⇒ status = gates_failed
10. 记账+存证   sessions.json(attempts+1)+ {root}/.symphony/runs/{issue}.json
11. 终态清理   issue 达终态 ⇒ before_remove hook + 删除工作区
```

**续跑**:同一个 issue 的第二个 attempt 复用同一 DSH session(`--session-id`),并把 `attempt` 渲染进 prompt 走「续跑分支」——**不要从头再来**,先看 `git status` / `git log` 与上轮已写文件。

**证据**:每轮写一份 `{root}/.symphony/runs/{issue}.json`(status / attempt / session / artifacts / 全部门禁的 exit code 与输出摘要)。

---

## 8. 机器判 vs 人判(分界线)

| 机器能判(有退出码) | 只有人能判(无脚本) |
|---|---|
| 命名与层结构形状 | `Draft → Ready` 的评审**实质** |
| 必填段是否存在、标题是否逐字一致 | `Ready → Implemented` 的外部 PR 是否真 merged |
| 状态枚举取值是否合法 | `* → Deprecated` 的决策 |
| 阶段感知(`Draft` 留空 vs `Ready` 填真值) | 复审三问(仍然重要 / 应当保留 / 可以删除) |
| 跨层引用闭环(KD / V / FR / SYS / MOD 白名单) | 证据锚点指向的代码**是否真支持该断言**(只人工抽查,不改退出码) |
| 占位符清零、复审三行不写占位 | 量化指标是否合理、场景是否真覆盖 |
| 死链、CRLF、台账 / 索引一致性 | |
| 基线快照的 SHA 是否本地存在 | |

> **状态是本仓最核心的概念,却恰恰是唯一没有机器门禁的一环** —— 所以人工评审是流程的**必要环节**,不是形式。
> 门禁只能证明「字段齐、形状对、引用对得上」,证明不了「内容对」。

---

## 9. 当前实例状态(实测)

- **唯一真实产物**:`prd/2026-11-22/layer-checklist.md`(72 行,状态 `Draft`,复审三行留空)—— 即 Layer 1 自检清单本身。
- `tech_design/` `plan/` `test_cases/` 只有 `README.md` / `_index.md`,**无制品**;无 `material/`、无 `deep/`。
- **只读门禁实测**(本次运行,仓根):`check-naming.sh` / `check-md-schema.sh` / `check-traceability.sh` / `check-line-endings.sh` / `sync-prd.sh --check` / `sync-test-index.sh --check` / `check-doc-links.py`(49 文件 / 162 链接)—— **全部 exit 0**。
- 端到端:DSH 真跑一轮产出 PRD → 6 个门禁全 0 → 进程 exit 0(证据 `.swarm/evidence/a17-run2/`)。

---

## 10. 已知缺口

| # | 缺口 | 证据 | 后果 |
|---|---|---|---|
| **G-1** | **依赖闸门未实现** —— `dispatchable` 是存储字段;`blocked_by` 被解析后**从未参与判定**(死数据) | `tracker.py:147-161` / `:369-395` | 依赖链形同虚设;「上游 `Ready` 才准写下游」今天**只是 agent 的 prompt 义务**,机器零覆盖(§3 实测反证) |
| **G-2** | **tracker 无写路径** —— Protocol 自述是只读面 | `tracker.py:120-135` | 状态推进**没有任何自动机制**;人只能手改 JSON |
| **G-6** | **`deep-scan.py` 退出码只有 0/1(无 2)** —— 偏离 M1 的 0/1/2 契约 | `scripts/deep-scan.py:39-41` | 环境错误会被当成「有违规」;接入 CI 门禁会误判 |
| **G-7** | **`check-doc-links.py` 在 git 仓内只查已跟踪的 .md** | `scripts/check-doc-links.py:59`(`git ls-files`) | 仓内 **21 个未跟踪 .md**(含本文 `docs/operation-flow.md`)**不被死链检查覆盖** |
| **G-8** | **`--stage` 只在 `check-md-schema.sh` 真正生效**;`check-traceability.sh` / `check-line-endings.sh` / `check-naming.sh` 接受但无效果;另 4 个脚本无此参数 | 各脚本 CLI 段 | 「按阶段收紧」只在字段校验里成立;追溯 / 行尾 / 命名不受阶段影响 |
| G-3 | **CI 未在 GitHub Actions 真跑**(本机不能 push) | — | CI 绿灯基线只是本地序列模拟 |
| G-4 | **`linear` tracker 未实现**(无凭据) | — | `--tracker linear` 早失败,不会静默退化 |
| G-5 | `schema/tech_design/v3/` 代际分支未实测;`schema/**` 与 `scripts/**` 的「推荐 vs 必填」多靠反推 | — | 低风险遗漏 |

> G-1 / G-2 的修复设计见 `.swarm/requirements/phase2-task-flow.md` §2 / §6(**代码未动**)。

---

## 11. 实物对照(逐脚本 / 逐 skill 实测,非引述)

### 11.1 门禁脚本能力边界

| 脚本 | 契约 | 退出码 | TARGET | 关键边界(实测) |
|---|---|---|---|---|
| `check-line-endings.sh` | M7 | 0/1/2 | 文件 / 目录 | 范围 = `git ls-files`;含 NUL 视为二进制跳过;`--stage` 接受但**无效果** |
| `check-naming.sh` | M2+M6 | 0/1/2 | 层目录 / 层内文件 | 三态:层不存在→跳过;层存在无制品→⚠ 且 **0**;**全仓无产物→1**;TARGET 非层路径→2 |
| `check-md-schema.sh` | M3/M4/M5 | 0/1/2 | 层内文件 / `tech_design/<dir>` | 单文件模式也 **exit 1**(违规数不当退出码);`--stage` **只能收紧**,放宽报错;层根目录 TARGET→2 |
| `check-traceability.sh` | T1–T12 | 0/1/2 | 层内文件 | TARGET 必须在 4 层之下,否则 2;`--stage` **无效果**;跨层只比 `Deprecated` |
| `check-repo-baseline.sh` | 实现基线 | 0/1/2 | TD README / 目录 | 额外 `--max-age-days`(默认 7)→ 超龄只 **warn**;`○` / 「不适用」→ 整体跳过;仓未登记 → warn |
| `check-doc-links.py` | M12 | 0/1/2 | **无** | 只查**已跟踪** .md;`{}` 占位与 `#L12` 不算死链;标题锚点只 ⚠;外链不查(无网络) |
| `sync-prd.sh` | 台账 | 0/1/2 | **无** | 只写 `material/{date}/PRDS.md` + 根 README 统计块;`--check` 退 1 = 漂移;**CI 不用它的退出码**(改用写模式 + git diff 比对) |
| `sync-test-index.sh` | 用例索引 | 0/1/2 | **无** | 只写 `test_cases/_index.md`;`test_cases/` 不存在 → 跳过 **0** |
| `deep-scan.py` | 理解底座 | **0/1(无 2)** | **无** | 指纹 = git blob sha1;只重写 `deep/INDEX.md` 的 inventory 区间;台账 5 状态**与层状态机无关** |

### 11.2 九个 skill 的边界

| skill | 输入 → 产出 | 一句话边界 |
|---|---|---|
| `to-prd` | `prd/{date}/*.md` → `prd/{date}/{topic}.md` | 只产出 `Draft` |
| `to-tech-design` | PRD → `tech_design/{date}-{topic}/`(v4 四件) | v3 六件套需**显式 opt-in** |
| `to-plan` | TD 目录 → `plan/{date}-{topic}/{topic}.md` | 引用来源随 v4/v3 自适应 |
| `validate-spec` | 整仓 / 单文件 / 单目录 → 校验报告 | **唯一改退出码的入口**;证据锚点只 ⚠ |
| `to-test-cases` | PRD + TD → `test_cases/{date}/{topic}.md` | `Ready` 需 `-key-points.md` 伴生 |
| `sync-status` | 目标文档 → 状态行更新 | **只执行人工明确指定的那一次转换** |
| `sync-prd` | 批次日期 → `material/{date}/PRDS.md` | 可选层;无 git 写操作 |
| `to-deep-understand` | 范围 → `deep/` | 可选层;**只写 `deep/`**;不得代答 Q-{n}、不得编造 SHA/行号 |
| `commit` | 变更内容 → commit message | `Reviewed-by:` **只能取自产物复审段**;产物仍 `Draft` 时**整行不写** |

### 11.3 盘点标记的不确定项

1. 「推荐段 vs 必填段」只有 `schema/prd.md:11` **自述**过;其余是从脚本 grep 清单反推的**推断**。
2. `schema/**` 与 `.codex/skills/**` 的判定来自脚本;**若模板与脚本漂移,以脚本为准**(裁判即权威)。
3. 盘点 lane 零写操作、零 git 写操作;临时探针副本已删除。

---

## 12. 待决(一个真问题 + 一个小问题)

### 12.1 「上游必须 `Ready`」这条义务该归给谁?

| 选项 | 做法 | 代价 |
|---|---|---|
| **(a) 现状** | 只写在 `WORKFLOW.md`,由 agent prompt 承担 | 非 agent 生产者、或不守规矩的 agent 可**静默越级**,产物层门禁全绿(已实测) |
| **(b) 产物层门禁** | 在 `check-traceability.sh` 加跨层状态前置检查 | **会把合法的「上游还在评审中、下游已在起草」判死**;产物门禁只该管形状与追溯,不该管编排次序 |
| **(c) 编排层门禁(推荐)** | runner 派发前计算 `dispatchable`:上游 issue 未终态 ⇒ 不派发;上游产物状态 ≠ `Ready` ⇒ 不派发 | 需修 G-1(`blocked_by` 参与计算)+ 读上游产物状态(跨仓) |

**推荐 (c)**,与 Symphony 的 Linear adapter 同构(`linear/client.ex:501-511`:`todo` 态且有非终态 blocker ⇒ `dispatchable=false`)—— **闸门属于编排层,不属于产物门禁**。这也正好落进 G-1 的修复范围。

### 12.2 本文是否入 git

`docs/operation-flow.md` **当前未跟踪** ⇒ 受 G-7 影响,**死链检查覆盖不到它**。入 git 才能被门禁看见(同时也落实「契约/说明随仓走」这条原则)。

