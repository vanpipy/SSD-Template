# 需求集: 用文件系统承载长任务系统 (任务流转层)

work-item: `task-flow-layer`
状态: **设计定稿 · 代码未动**（本轮只做分析, 实施需另行授权）
关联: `phase0-phase1-contract.md`（§7 Phase 2 运行器契约, 已落地）· `symphony-migration.md`（R1–R7, 已 met）
决策来源: 用户 m01593「本质上的问题是如何使用文件系统来支持长任务系统运转」

> **状态更新(2026-11-24 · 审计后修正)**
> - 本文件属于 **Symphony 编排线**, 该线已按用户 m01732「先把 symphony 搁置」**搁置**;当前生效的调度依据是仓内 `ssdctl scan`(`WORKFLOW.md:46`, `:86-88`)。
> - **C-8 的 `check-flow.sh` 从未创建**(全仓 0 命中, 无此文件)。它在本文件里是「拟新增」条目, 不是对既有脚本的引用, 但在本文件之外没有任何实现依据, 容易被误当成既有门禁。
> - 当前仓内等价门禁 = `bash scripts/ssdctl.sh gate`(8 门禁 + 判据 + 制品自洽性)与 `bash scripts/ssdctl.sh scan --check`(派生状态与磁盘一致)。二者均已在 CI `.github/workflows/spec-check.yml` 中接线。
> - ⇒ **不要按 C-8 原样实现 `check-flow.sh`**。若 Symphony 线重启,须先重写 C-8 使其与 `ssdctl` 契约对齐,再开工。

---

## §0 结论摘要

用户判断成立, 但需精确化一层:

| 层 | 内容 | 归属 |
|---|---|---|
| **产物契约** | 一个工作项**长什么样**: 层 / schema / 追溯 / 状态枚举 / 必填段 | SSD-Template 已有 (`schema/**` + 门禁) |
| **编排契约** | 一个工作项**怎么流转**: 身份 / 状态 / 依赖 / 续跑 / 隔离 / 证据 / 签字 | **Symphony 提供形状**, 内容按 SSD 语义裁剪 |
| **持久化后端** | 状态**存在哪** | **文件系统** — Symphony 自己不用文件系统 (Linear + GitHub), 故此层**全部自造**, 不受 Symphony 规范约束 |

⇒ 准确的表述: **Symphony 提供任务系统的语义, 文件系统是在没有 Linear/GitHub 时选的持久化替身。**

**「用文件系统承载长任务」的真正难点不是「存」, 是「可重入」**: 任何时刻进程被杀, 重启后**只读文件系统**必须重建出同样的判断。

---

## §1 九原语 → 现状盘点 (含两个实测缺口)

长任务要跑起来, 文件系统必须承载 9 个原语:

| # | 原语 | 为何必需 | Symphony 给形状 | SSD 现状 |
|---|---|---|---|---|
| 1 | 工作单元身份 | 跨会话指认同一件事 | tracker issue | ⚠️ runner 侧有 `Issue.id/identifier`, 但**载体是 runner 仓里的一个 JSON 数组** |
| 2 | 编排状态 | 能不能开工 / 能不能推进 | tracker state | ⚠️ 有 `state` 字段, 但**无写路径** — runner 只读 |
| 3 | 依赖 / 阻塞 | 决定并行还是串行 | issue `blocks` → `blocked_by` | 🔴 **闸门未实现** (见 §2 缺口 G-1) |
| 4 | 续跑锚点 | 崩了能接着跑 | attempt / `--session-id` | ⚠️ `attempt`/`session` 在编排器内, **不在工作项载体里** |
| 5 | 工作区隔离 | 并发不打架 | workspace + `after_create` | ✅ 已实现 |
| 6 | 产物落点 | 工作项 ↔ 产物绑定 | PR ↔ branch | ⚠️ `branch_name` 字段在, 产物路径靠约定 |
| 7 | 证据 | 评审可判 | PR diff + CI + 评论 | ⚠️ 锚点格式已有; 门禁输出**不留存** (可重算 → 见 §3 纪律 a) |
| 8 | 审计轨迹 | 谁何时改了什么 | git | ⚠️ 只覆盖产物, **不覆盖状态推进** (状态推进载体不在 git 里) |
| 9 | 租约 / 单写者 | 两个 agent 不抢同一工作项 | tracker 天然并发模型 | ❌ 无 |

### §2 两个实测缺口 (代码证据)

**G-1 · 依赖链闸门未实现** — 「上游没评审完不准写下游」今天仍只是文档约定。
- `D:\project\symphony-runner\src\symphony_runner\tracker.py:92` 已有 `blocked_by: list = field(default_factory=list)`.
- `tracker.py:147-161` `is_routable()` **只看** `dispatchable` 布尔位与 `labels`, **完全不看 `blocked_by`**.
- `MemoryTracker` 的 `dispatchable` 是**存储字段**(默认 True), 不是计算结果.
- 对照: Symphony 的 Linear adapter 在 `linear/client.ex:501-511` 里, 当 issue 状态为 `todo` 且存在非终态 blocker 时判 `dispatchable=false` —— 这正是「等上游产物评审通过」的原语.
- ⇒ 本层必须实现: `dispatchable` 由 `state` + `blocked_by` **计算**, 不再是存储字段.

**G-2 · tracker 无写路径** — 状态推进今天没有任何自动机制。
- `tracker.py:120-135` 的 `Tracker` Protocol 明确是**只读面** ("The read surface every tracker adapter provides").
- ⇒ 现状: 人只能手改 `examples/issues.json`; runner/agent 无权推进状态.
- ⇒ Symphony 里这件事是**分开的**: tracker 写属于 **agent 工具面** (§11.5 "Tracker Writes (Important Boundary)"), 不属于 adapter 核心面. 本层照抄这个切分: 核心 Protocol 保持只读, 写能力单独成面.

---

## §3 三条纪律

**(a) 真相源 vs 派生态必须分开**
- 真相源 (**入 git**): 工作项文件 —— 身份 / 状态 / 依赖 / 产物路径 / 评审结论.
- 派生态 (**可重算 / 可丢弃**): 门禁输出 / diff 快照 / workpad 中间态.
- 判据: **能从真相源重算出来的一律不当真相源存**. 门禁已支持 `--json`, 输出属派生态 —— 存它会陈旧, 不存它不损失 (脚本若改了, 真相源也跟着变了).
- ⇒ 所以**不建 `prs/` 目录**: 评审者签字前要看的四件里 (a) diff (b) 正文 (c) 证据锚点 (d) 门禁结论, 前三件已有, 第四件可重算 ⇒ **「PR 包」的信息量 ≈ 0**, 不值得为它新建目录.

**(b) 单写者 = 每个状态转移有唯一 owner**
不是「一个文件一个写者」(做不到, 因为人要签评审), 而是:
- **runner 独占**: `Todo→In Progress` / `In Progress→Review` / `Rework→In Progress`, 以及 `attempt` / `session` / `branch` / `artifacts`.
- **人独占**: `Review→{Done, Rework, Cancelled}` / `Todo→Cancelled`, 以及 review 段.
- **agent 独占**: **无** —— agent 只读控制平面, 用产物 + workpad 表达意图.
  - 依据: agent 沙箱是 workspace-write, 只能写工作区; 控制平面若独立于工作区, agent **写不了** issue 文件 ⇒ 写权天然归 runner.
  - 这与「agent 权限天花板 = `Draft`」(D-15) 同向.
- ⇒ **冻结规则**: `state == "Review"` 后 runner 对该 issue **只读** (等人签字), 避免 runner 与人的写冲突 —— 文件系统里的静默覆盖比 git 的显式冲突更坏.

**(c) 幂等重放**
同一工作项重复执行必须收敛到同一结果 ⇒ 所有写状态的动作要么幂等, 要么带 attempt 序号. Symphony 用 attempt 生命周期表达, 本层用**文件字段**落地.

---

## §4 最小载体 (per-issue 文件)

**「一个工作单元 = 一个文件」**, 文件兼任**工作项**与**评审单元** (不再另建 PR 目录):

```yaml
# issues/LOCAL-1-example-feature.md
---
id: LOCAL-1
title: Example feature
state: Todo                     # Todo | In Progress | Review | Done | Cancelled
labels: [ssd-spec, layer:prd]
blocked_by: []                  # 上游工作项 id
branch: spec/LOCAL-1-example-feature
artifacts:                      # 相对 SSD-Template 仓根
  - prd/2026-11-22/example-feature.md
attempt: 0                      # 最近一次 attempt 序号
session: null                   # DSH session id, 续跑用
updated_at: 2026-11-22
review:
  reviewer: null
  reviewed_at: null
  decision: null                # approve | changes-requested | reject
---
# 正文 = 触发条件 (给 agent 的 description), 不是功能说明
Use when ... (Symphony SPEC §8.1: description 应写触发条件)
```

**唯一强制规则**:
> `state == "Done"` ⇒ 对应产物的 `> **状态**:` ∈ {`Ready`, `Implemented`} **且** `review.decision == "approve"`.
> 反向**不强制**: 产物已 `Ready` 但工作项尚未 `Done` 是合法的 (评审完了, 还没归档).

**状态集**:
- `active_states` = [`Todo`, `In Progress`, `Rework`] → 可派发
- `Review` ∉ active, ∉ terminal → **等人工评审** (runner 不再投喂 turn, 工作项未结束)
- `terminal_states` = [`Done`, `Cancelled`]

**合法转移边**:
```
Todo ──runner──▶ In Progress ──runner──▶ Review
Review ──人(approve)──▶ Done
Review ──人(changes-requested)──▶ Rework ──runner──▶ In Progress
Todo/Review ──人──▶ Cancelled
```

---

## §5 载体位置 (5 种可能, 3 种存活)

| # | 形态 | 裁决 |
|---|---|---|
| L1 | **独立控制平面仓** `D:\project\symphony-control\` (**入 git**) | ✅ **推荐** —— spec 仓保持干净; 状态推进 = git commit, 天然是事务单元 + 审计轨迹 |
| L2 | SSD-Template 内当可选层 (与 `material/` 同级) | ⚠️ 存活但代价大 —— spec 仓自己的 PR diff 会脏, `check-naming.sh` 的 LAYERS 列表要加一层 |
| L3 | symphony-runner 仓内 | ❌ 引擎与控制面职责混; 业务数据淹没 runner 仓 |
| L4 | 纯文件系统, **不入 git** | ❌ 丢掉审计轨迹 (原语 8) —— 恰是引入 issue 的理由之一 |
| L5 | issue 入 git + PR 包不入 git | ❌ 过度设计 —— PR 包本就不该存在 (§3a) |

**判据不是「像不像 Symphony」** (Symphony 的 tracker/PR/workspace 无一在 repo 内), 而是「**替身保住了 Symphony 的哪些性质**」: ①状态有审计轨迹 ②每工作项独立工作区与续跑 ③评审有可指向的单元. L1 保住全部三条.

**跨仓路径基准**: `artifacts` 路径**相对 SSD-Template 仓根**, 由门禁按已知仓清单解析.

---

## §6 runner 侧改造清单 (含冻结签名变更单)

| # | 改动 | 触碰 |
|---|---|---|
| C-1 | 新增 `file` tracker adapter: 读 `issues/*.md` 的 front matter + 正文作 description; **每次调用重新读盘** (沿用 MemoryTracker 的既有语义) | `tracker.py` 新增类 |
| C-2 | `dispatchable` 由 `state ∈ active_states` **且** ∀ blocker ∈ `blocked_by` 状态 ∈ `terminal_states` **计算** (修 G-1) | `tracker.py:147-161` `is_routable()` |
| C-3 | 新增 **写面** `WritableTracker` Protocol (与只读 `Tracker` 分开, 照 Symphony §11.5 的边界): `set_state(identifier, state)` / `update_fields(identifier, **kw)` | `tracker.py` |
| C-4 | **变更单**: `create_tracker(settings, *, issues_file=None)` → 增加 `issues_dir: str \| Path \| None = None`. (§7.2 是冻结表, 改签名须先改契约 —— 本文件即为该变更单) | `tracker.py:301` |
| C-5 | orchestrator 状态推进: 派发前 `Todo→In Progress`; 门禁全绿后 `In Progress→Review`; `state == Review` 时**只读**该文件 (冻结规则) | `orchestrator.py` |
| C-6 | `Issue` dataclass 增字段: `artifacts: list`, `review: dict`, `updated_at` 已有; `branch_name` 已有 | `tracker.py:79-117` |
| C-7 | `WORKFLOW.md` front matter: `tracker.kind: file` + `tracker.issues_dir` | `WORKFLOW.md` |
| C-8 | 门禁: 新增 `check-flow.sh` —— 断言 ①`Done ⇒ 产物状态 ≥ Ready 且 decision == approve` ②`blocked_by` 指向存在的工作项且无环 ③产物路径存在 ④`artifacts` 与实际产物一致 | `scripts/` |
| C-9 | `check-naming.sh` 的 LAYERS 列表: 若采纳 L2 才需加层 (L1 不需要) | `scripts/check-naming.sh` |

---

## §7 验收草案 (B1–B9)

| ID | 判据 |
|---|---|
| B1 | `issues/*.md` 的 front matter 可被 runner 解析; 正文作 description |
| B2 | `blocked_by` 指向一个非终态工作项 ⇒ 该工作项**不可派发** (G-1 修复证据) |
| B3 | `blocked_by` 全部终态 ⇒ 可派发 |
| B4 | 工作项状态推进: `Todo→In Progress→Review` 由 runner 写入; `Review` 后 runner **不再写**该文件 |
| B5 | 人写 `review.decision` 与 `state: Done` 合法; 无 `approve` 却 `Done` ⇒ `check-flow.sh` exit 1 |
| B6 | `blocked_by` 成环 ⇒ `check-flow.sh` exit 1 |
| B7 | 状态推进的 git 轨迹可见 (控制平面仓 `git log` 能看到每次推进) |
| B8 | runner 全部既有测试仍绿 (新增行为不得破坏既有 179 项) |
| B9 | agent **不能**写控制平面文件 (沙箱 workspace-write 的实际边界验证) |

---

## §8 未决 (需用户裁决, 均有默认值)

| # | 问题 | 默认 |
|---|---|---|
| U-A | 控制平面放哪、要不要入 git | **L1** 独立仓, 入 git |
| U-B | 工作项文件格式 | md + YAML front matter (本文 §4) |
| U-C | 是否建 `prs/` 目录 | **不建**; 只在出现「不可重算证据」需求时再开 |
| U-D | 本轮范围 | 设计与契约先行; 实现与真跑另开一轮 (A17 已把真跑路径走通) |
| U-E | 本文件是否复制进仓 (`docs/architecture-contract.md`) | **已复制** —— 本文件即入库版本 `docs/contracts/phase2-task-flow.md`(编排目录 `.swarm` 被 gitignore,下个会话读不到改造依据) |

---

## 需求覆盖状态

| 需求 | 状态 | 依据 |
|---|---|---|
| T1 三层分解与归属 | ✅ met | §0 |
| T2 九原语盘点 | ✅ met | §1 (含 G-1 / G-2 两个实测缺口) |
| T3 三条纪律 | ✅ met | §3 |
| T4 最小载体格式 | ✅ met | §4 |
| T5 状态机分叉与冻结规则 | ✅ met | §3b / §4 |
| T6 载体位置裁决 | ✅ met | §5 |
| T7 runner 改造清单 | ✅ met | §6 (含冻结签名变更单 C-4) |
| T8 验收草案 | ✅ met | §7 |
