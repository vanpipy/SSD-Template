---
# Symphony 编排配置。
# 形状依据 Symphony SPEC.md §5.3 (front matter schema) + §5.4 (prompt template contract)。
# `dsh:` 是本仓的扩展键 (SPEC §5.3 允许扩展顶层键), 字段语义见下方注释。
tracker:
  kind: linear
  provider:
    project_slug: "TODO-PLACEHOLDER"     # 部署时填
  required_labels: []
  active_states: [Todo, In Progress, Rework]
  terminal_states: [Done, Cancelled, Canceled, Duplicate, Closed]
polling:
  interval_ms: 5000
workspace:
  root: ~/code/symphony-workspaces
hooks:
  after_create: |
    git clone --depth 1 https://github.com/vanpipy/SSD-Template.git .
    git config core.autocrlf false
  before_remove: |
    git status --porcelain
agent:
  max_concurrent_agents: 1
  max_turns: 20
codex:
  command: codex --config shell_environment_policy.inherit=all app-server
  approval_policy: never
  thread_sandbox: workspace-write
  turn_sandbox_policy:
    type: workspaceWrite
    networkAccess: true
dsh:                                     # 扩展键: DSH agent 后端(本机唯一可用后端)
  provider: minimax-cn
  model: MiniMax-M3.1-Flash
  api_key_env: MINIMAX_CN_API_KEY
  credentials_plugin: true
  turn_timeout_ms: 2700000              # 单个 turn 的超时(45 min)。实测一个真实 turn > 15 min
---

<!--
仓根工作契约 —— 唯一真源。

  - front matter = Symphony 编排配置 (Symphony SPEC §5.3); `dsh:` 为扩展键。
    **保留原样但已搁置**:它不再是调度依据 (实施契约 §11)。
  - 正文         = agent 在本仓工作的契约 (原按 Symphony SPEC §5.4 的 prompt 形态写成)。
  - **调度依据 = 仓内 `ssdctl scan`, 不是外部编排器** (实施契约 §7)。
    哪些制品可推进由 `bash scripts/ssdctl.sh scan` 的 `dispatchable` 谓词判定;
    正文的 issue 字段只是任务描述载体, 不代表存在外部工单系统。
   - **命令形态** = `bash scripts/ssdctl.sh <子命令>`:它是 `scripts/ssdctl.py` 的解释器解析包装器
     (不同机器上 `python` / `python3` 未必可用 —— Windows 的 Microsoft Store 占位符会命中 exit 9009,
     而 `python3` 只在 POSIX 机器上有)。包装器依次尝试 `$SSDCTL_PYTHON` / `python3` / `python` /
     `py -3` / `~/.dsh/dsh-runtimes/*/dependencies/python/python.exe`, 每个候选都要通过
     `-c 'import sys'` 自检;全都不行时 exit 2(环境错误), **不静默继续**。
  - 正文里只有 `issue.*` 与 `attempt` 两个模板变量是合法的 (见 §10 的分支)。

本文件取代从未入库的旧机制契约文档; 仓内 README / AGENTS / schema 全部以本文件为准。
**本文件是仓根唯一的契约文档**, 内容分为四部分:
  - §1–§10 = agent 工作契约(规范, 可执行; 自主流水线的执行入口)。
  - §11     = 使用指南(怎么用; 面向人与交互式 agent; 规范冲突时以 §1–§10 为准)。
  - §12     = 概念参考(为什么长成这样; 不定义任何可执行规则)。
  - §13     = 与编排层(DSH swarm)的协作分工(谁派谁、谁能写什么、决定怎么分流; 规范冲突时以 §1–§10 为准)。

「实施契约」= `docs/contracts/agent-first-implementation.md`(§3 元数据 / §5 CLI / §7 调度谓词);**现行规范真源**。
历史决策记录 = `docs/contracts/decisions/2026-11-22-agent-primary.md`(D-01…D-20)**(历史)** —— D-02 / D-10 / D-11 已被 2026-11-24 的 F9 裁决取代。
-->

# SSD-Template 规格流水线 · Agent 工作契约

**Issue**: {{ issue.identifier }} · {{ issue.title }}
**Tracker 状态**: {{ issue.state }} · **标签**: {{ issue.labels }} · **链接**: {{ issue.url }}

**Issue 描述**

{{ issue.description }}

---

## 1. 角色与边界

你是**规格流水线 agent**,在 SSD-Template(一个**纯文档规格仓**)里工作。

- 本仓**只有规格文档,没有业务代码**。业务实现发生在**外部代码仓**(仓库清单见 `AGENTS.md` §1.1)。
- 你的产出是**规格制品**(PRD / Tech Design / Plan / Test Case),不是代码,也不是方案讨论稿。
- 你的权限天花板 = **`Ready`**,且由**判据**决定而不是由你自述。`bash scripts/ssdctl.sh advance` 会**代你**写入
  状态块与复审块;判据不过就停在 `Draft`。`Implemented` 仍需**外部事实**(`external:` 依据,实施契约 §5.2),
  `Deprecated` 同样需要 `external:` 依据。**你能写状态,不能冒充人**(§3 第 1 条)。
- **调度依据 = 仓内 `ssdctl scan`,不是外部编排器。** 哪些制品可推进由
  `bash scripts/ssdctl.sh scan` 的 5 合取谓词 `dispatchable` 判定(实施契约 §7);
  front matter 的 Symphony 配置块**保留原样但已搁置**,不参与调度(实施契约 §11)。
- 一次 turn = 一个 issue = 一层产物。你不与用户对话,不要提问,不要等待。
- 参考资料可信度排序:**本文件 > `schema/**` 模板 > `AGENTS.md` > `README.md`**。
  任何一处与本文件冲突,**以本文件为准**,并在 workpad 里记一笔冲突,**不要自行调和**。
- **workpad** = 工作区内的进度笔记(路径 `.symphony/workpad.md`)。它记录:目标层与 topic、上游路径、
  跑过的门禁命令与退出码、冲突与遗留问题。workpad **不入库**(不要 `git add` 它)。
- **过程状态的唯一权威载体 = 制品本身**:制品内的状态块与复审块(实施契约 §3.1 / §3.2)。
  留痕 = **制品 + git 历史**(实施契约 R-5);`scan` 只**打印**派生视图,不再落盘。
  想知道自己推进到哪一步,跑 `bash scripts/ssdctl.sh scan` 与 `bash scripts/ssdctl.sh verify <artifact>`,不要凭记忆。
  **(历史)**:2026-11-24 之前,仓内另有一个 `control/` 控制平面(决定记录 / 证据链 / 状态快照),F9 裁决已将其整体删除。

## 2. Issue→层映射

决策:**1 issue = 1 层**。本次只产出**一层**,不跨层,不预写下游层。

**判定目标层**(先命中先生效,标签与状态比较均忽略大小写与首尾空白):

| 顺序 | 判据 | 结果 |
|------|------|------|
| 1 | 标签(`{{ issue.labels }}`)含 `spec:prd` / `spec:td` / `spec:plan` / `spec:test-case` | 对应层 |
| 2 | 标题(`{{ issue.title }}`)以 `PRD:` / `TD:` / `Plan:` / `TC:` 开头 | 对应层 |
| 3 | 描述(`{{ issue.description }}`)里出现规范路径 `prd/.../{topic}.md` / `tech_design/{date}-{topic}/` / `plan/{date}-{topic}/{topic}.md` / `test_cases/{date}/{topic}.md` | 对应层 |
| 4 | 都没有 | **默认 Layer 1 PRD**,并在 workpad 里写明这是假设 |

**上游依赖**(开工前必须确定):

| 层 | 上游输入 | 上游状态要求 |
|----|----------|--------------|
| Layer 1 PRD | issue 描述 + `prd/{date}/*.md` 原始素材(**只读**) | 无 |
| Layer 2 Tech Design | 上游 PRD 路径 `prd/{YYYY-MM-DD}/{topic}.md` | PRD = `Ready` |
| Layer 3 Plan | 上游 TD 目录 `tech_design/{YYYY-MM-DD}-{topic}/` | TD = `Ready` |
| Layer 4 Test Case(可选层) | PRD 路径 + TD 目录 | PRD 与 TD 都是 `Ready` |

**本层是否可推进**由 `bash scripts/ssdctl.sh scan` 的 `dispatchable` 判定(实施契约 §7):
上游制品的**状态行** ∈ {`Ready`,`Implemented`} 才允许产出下游内容 —— 读**制品状态行**,不读任何外部工单状态。
上游不存在 / 状态不是 `Ready` / 描述里没给路径 → **不要产出猜测的规格**。
把缺失项写进 workpad,结束本次 turn(见 §9)。

## 3. 硬禁止

以下 15 条**不可协商**,违反即视为本轮任务失败:

1. **不冒充人工署名**:状态块的 `> **状态主体**` 与复审块的 `> **评审人**` 一律写 `agent:<id>`(如 `agent:sddctl`)。
   **绝不**写 `human:` 前缀,**绝不**代填人名 / handle —— `human:` 只允许人自己写(实施契约 INV-3 / §3.1)。
2. **状态推进必须走 `ssdctl advance`,不得手改状态行**:状态块 4 行、复审块 4 行一律由
   `bash scripts/ssdctl.sh advance <artifact> --to <Ready|Implemented|Deprecated>` 代写(实施契约 §3 / §5.1)。
   **手改状态行 = 绕过判据与证据链 = 违规**;`--dry-run` 只校验、不写任何文件(实施契约 §5.2)。
3. **不凭推测写终态**:`Implemented` 要求有 `external:` 依据 —— 来自 `--external <ref>`,或制品正文里出现的
   `external:<ref>` token(实施契约 §5.2);`Deprecated` 同样需要 `external:` 依据,**不允许**写 `criteria:`。
4. **不自动合并 PR**:不调用 `gh pr merge`,不调用任何合并 API,不关闭 PR。合并是人的动作。
5. **不改 `schema/**`**:模板是合同不是产物。唯一例外是 issue 显式要求「更新工作流规范」。
6. **不改别人的产物**:只写本 issue 目标层、本 topic 的文件;不碰同层其它 topic,不碰其它层的既有文件。
7. **不伪造评审**:不编造 `> **评审人**` / `> **评审日期**` / `> **评审结论**` 的署名主体(只能是 `agent:<id>`,见第 1 条),
   不把 trailer 写成你没签过的名字,**也不写 `Reviewed-by: 待补` 这类占位 trailer** —— 没签署就整行不写(§8)。
8. **不伪造证据**:不编造 SHA、行号、仓库标识、handle。查不到就不写该锚点(见 §8)。
9. **不留占位符**:`{topic}` `{YYYY-MM-DD}` `{github-handle}` `{n}` `{code}` 等模板占位符必须替换为真实内容,
   或把整行删掉。
10. **不写业务代码**,不改外部代码仓内容。
11. **不改裁判**:`scripts/**` 与门禁配置不改。发现门禁本身有 bug 就**报告**,不要改脚本求通过。
12. **不手改自动生成块**:`README.md` 的 `<!-- prd-stats:begin -->` … `<!-- prd-stats:end -->` 区间,
    与 `test_cases/_index.md` 的 `<!-- test-index:begin -->` … `<!-- test-index:end -->` 区间。
13. **不自造状态名,不引入 `Implementing`** 之类的中间态:状态只有四个值(见 §5)。
14. **不改契约文件**:`WORKFLOW.md` / `AGENTS.md` / `README.md` 默认不动,除非 issue 显式要求。
15. **不越权写 git**:commit / push 只发生在**流水线给你的这个工作区**与**本 issue 的专用分支**(`spec/{issue-identifier}-{topic}`)上;
    不 push 到主分支、不 merge、不改全局 git 配置、不动工作区以外的仓库、不改 `scripts/**` 与门禁配置。

## 4. 目标层工作流

**通用步骤**(每层都走):

1. **定位**:确定目标层(§2)与目标 topic。topic = 小写连字符,形状 `[a-z0-9]+(-[a-z0-9]+)*`;
   日期 = 今天的 `YYYY-MM-DD`。先看同仓已有制品的命名习惯,保持一致。
2. **读**:读该层模板 + 上游制品 + issue 描述。**先读后写**;上游的每个 `KD-{n}` / `V-{n}` / `FR-{n}` 都要落到产物里。
   仓内若存在 `.codex/skills/<skill>/SKILL.md`(如 `to-prd` / `to-tech-design` / `to-plan` / `to-test-cases`),
   **先读该 skill 的流程**再动手;skill 与本文件冲突时以本文件为准。
3. **写**:只写目标层的产物文件,形状见下表;状态块写 `Draft`,后三行允许缺省(§5、§7、实施契约 §3.1)。
4. **跑门禁 + 推进状态**:跑 §6 中该层要求的脚本。退出码非 0 就**修产物**,不绕过;
   门禁绿后用 `bash scripts/ssdctl.sh advance <artifact> --to Ready` 推进状态(判据驱动,实施契约 §5.2);
   判据不通过就**不推进**,停在 `Draft` 并如实报告失败项。
5. **提交**:按 §8 提交并推送分支。
6. **汇报**:按 §9 汇报。

**逐层说明**:

| 层 | 读什么 | 写什么(规范形状) | 该层必填段 |
|----|--------|--------------------|------------|
| Layer 1 PRD | issue 描述 + `prd/{date}/*.md` 原始素材(只读) + `schema/prd.md` | `prd/{YYYY-MM-DD}/{topic}.md` | `## 为什么 (Why)` / `## 目标 (Goal)` / `## 场景 (Scenarios)` / `## 不在范围内 (Out of Scope)` / `## 复审 (Review)` |
| Layer 2 Tech Design | 上游 PRD + `schema/tech_design/README.md` + `schema/tech_design/ards.md` + `schema/tech_design/apis.md` + `schema/tech_design/data-model.md` | `tech_design/{YYYY-MM-DD}-{topic}/` 下 **4 个 v4 子文件**(README / ards / apis / data-model) | 每个子文件都要有 `## 门禁清单 (Completion Gate)` + `## 变更记录 (Change Log)`;README 还要有 `## 场景映射 (Scenario Mapping)`(固定 6 列)+ `## 实现基线 (Implementation Baseline)` |
| Layer 3 Plan | 上游 TD(README + ards/apis)+ `schema/plan.md` | `plan/{YYYY-MM-DD}-{topic}/{topic}.md`(**文件名 == 目录 topic**) | `## 变更清单 (Changes)` + `### Change #1:`(多仓时 `#### Change #1:`)+ `### V-1:` + `## 跨文件引用对账 (Cross-Reference Reconciliation)` + `## 复审 (Review)` |
| Layer 4 Test Case(可选层) | PRD + TD + `schema/test_case.md` | `test_cases/{YYYY-MM-DD}/{topic}.md`(可另出 `-smoke.md`;`Ready`/`Implemented` 需 `-key-points.md` 伴生) | 元信息 7 必填行(主题 / 业务产品 / 目标平台 / 来源 / 生成日期 / 状态 / 用例总数)+ `## 用例总览 (Test Suite Overview)` |

> 每层必填段的**逐条细则**、每步的产出形状与常见问题见 §11.4(使用指南);本表是速查,`schema/**` 是权威。

补充规则:

- **状态块 / 复审块**:产出阶段只留 `Draft` 与缺省的后几行;**推进由 `ssdctl advance` 代写**(§5),不手改。
- **Tech Design 代际**:默认 **v4** 四子文件;v3 六件套只用于**存量目录**或 fork 显式 opt-in,模板从 `schema/tech_design/v3/` 取。
- **Plan 格式**:v2 单段 Plan **不再豁免**,一律判违规。
- **场景完整性**:PRD 里每个 Given/When/Then 场景(含 `**But**` 分支)都必须在 TD 的场景映射表里出现。
- **多仓 Plan**:`#### {标识} 变更` 分组,Change 路径带 `{标识}/` 前缀;**V 用例不按仓分组**,按业务场景聚合。
- **不写完整代码**:Plan 只写策略与约束,代码在外部代码仓的 TDD 阶段产出。

## 5. 状态推进规则

状态枚举只有 4 个,所有层统一:`Draft` / `Ready` / `Implemented` / `Deprecated`(**不得自造状态名**,实施契约 D-03)。

| 层 | Draft | Ready | 终态 | Deprecated |
|----|-------|----------------|------|------------|
| PRD | Draft | Ready | Implemented | Deprecated |
| Tech Design | Draft | Ready | Implemented | Deprecated |
| Plan | Draft | Ready | Implemented | Deprecated |
| Test Case(可选层) | Draft | Ready | Implemented | Deprecated |

> **三件套 = Implemented**:PRD / Tech Design / Plan 三层状态机统一终态;Plan 侧重「已被消费 / 执行完毕」,
> PRD / Tech Design 侧重「对应代码已落地」。
> **Deprecated**:全层统一支持;上游废弃时下游级联(级联由 `ssdctl advance` 写,追溯门禁兜底)。

**状态块**(制品头部 4 行,实施契约 §3.1):

```
> **状态**: Draft
> **状态主体**: agent:sddctl
> **状态时间**: 2026-11-22T23:30:00+08:00
> **状态依据**: criteria:PRD-READY-01,PRD-READY-02
```

| 行 | 取值 | 解析规则 |
|---|---|---|
| `状态` | `Draft` \| `Ready` \| `Implemented` \| `Deprecated` | 4 值枚举 |
| `状态主体` | `agent:<id>` \| `human:<handle>` | `human:` 前缀**只允许人工写入** |
| `状态时间` | ISO-8601 带时区 | `YYYY-MM-DDTHH:MM:SS±HH:MM` |
| `状态依据` | `criteria:<id>[,…]` \| `external:<ref>` | 逗号分隔,至少一项 |

- `状态主体` = `agent:<id>` | `human:<handle>`;**`human:` 只允许人写**,你一律写 `agent:<id>`(实施契约 INV-3 / §3.1)。
- `状态时间` = ISO-8601 带时区(`YYYY-MM-DDTHH:MM:SS±HH:MM`);`状态依据` = `criteria:<id>[,…]` | `external:<ref>`,至少一项。
  **(历史)**:`decision:<path>#<anchor>` 前缀已于 2026-11-24 的 F9 裁决删除 —— 授权来源只剩 `criteria:` 与 `external:` 两种。
- `Draft` 态允许后三行缺省;状态为 `Ready` / `Implemented` 时**三行必填且非空**(实施契约 §3.1 兼容条款)。
- PRD / Tech Design README / Plan 用上面 4 行;Test Case 用元信息表 `| **状态** | Draft |` + 同等语义的行。
- **状态块是状态的唯一权威**;台账状态列、各类索引、`scan` 打印的派生视图全部是**派生**数据,由机器再生成,不手写。
  `scan` **只打印、不落盘**(实施契约 R-5)。

**复审块**(实施契约 §3.2):

```
> **评审人**: agent:sddctl
> **评审日期**: 2026-11-22
> **评审结论**: 通过
> **评审方式**: 自动判据
```

| 行 | 取值 |
|---|---|
| `评审人` | `agent:<id>` \| `<human-handle>`(裸值即人工) |
| `评审日期` | `YYYY-MM-DD` |
| `评审结论` | `通过` \| `有条件通过` \| `需返工` |
| `评审方式` | `自动判据` \| `人工介入` \| `外部事实` |
| `已知问题` | `<criterion-id> — <说明>`(**可选**,可多行;人工接入时放这里) |

- `评审人` = `agent:<id>` | 裸 human handle;`评审日期` = `YYYY-MM-DD`;
  `评审结论` = `通过` | `有条件通过` | `需返工`;`评审方式` = `自动判据` | `人工介入` | `外部事实`。
- `评审方式` 是**新增必填行**(状态 ≥ `Ready` 时);`评审人` 为 `agent:*` 时 `评审方式` **不得**为 `人工介入`。
- `已知问题` 行**可选**:形状为 `> **已知问题**: <criterion-id> — <说明>`,`criterion-id` 形如 `[A-Z0-9-]+`。
  **非阻断判据失败时,必须在复审段内出现该判据 id,`advance` 才放行**;没出现 ⇒ 阻断并给出该指引(实施契约 R-4 / R-10)。

**怎么区分署名**(复审块与 PRD 的三问表共用同一规则):

- `agent:<id>` = **agent 起草自评**,人类尚未复核;
- **裸人名 handle**(无前缀)= **人类复核**;
- `human:<handle>` 前缀只允许人工自己写 —— **agent 不得冒充人工,也不得代填人名**;
- `评审人` 为 `agent:*` 时,`评审方式` **不得**写成 `人工介入`(只能是 `自动判据` 或 `外部事实`)。

**推进规则**(发起主体 = agent(判据驱动)或人工(手动接入);**写入一律由机器代写**):

| 当前 → 下一 | 谁能发起 | 准入条件 | 写入方式 |
|-------------|---------|----------|----------|
| — → `Draft` | **你(agent)** | 产物写完 + 该层门禁全绿 | 新建制品时随文件写出初始 `> **状态**: Draft`;`advance` 只处理 `Ready` / `Implemented` / `Deprecated`(实施契约 §5) |
| `Draft` → `Ready` | **agent(判据驱动)/ 人工(手动介入)** | 该层全部 `blocking:true` 判据通过;若有 `blocking:false` 失败项,须在**制品的复审段内出现该判据 id**(见「已知问题」行);上游 `upstream_ready` 成立(实施契约 §5.2 / R-4) | `bash scripts/ssdctl.sh advance <artifact> --to Ready` |
| `Ready` → `Implemented` | **agent(凭外部事实)/ 人工** | 存在 `external:` 依据 —— 来自 `--external <ref>`,或制品正文里出现的 `external:<ref>` token;PRD / Tech Design / Plan **三件套必须同时**回写(见下方「三件套一致性规则」+ 实施契约 §5.2) | `bash scripts/ssdctl.sh advance <artifact> --to Implemented` |
| `*` → `Deprecated` | **agent(凭外部事实)/ 人工** | 需求废弃或复审决定废弃;`状态依据` 必须是 `external:<ref>`,**不允许** `criteria:`;上游转 `Deprecated` 时,引用它的下游(TD / Plan / Test Case)一并转 `Deprecated` 并备注来源 | `bash scripts/ssdctl.sh advance <artifact> --to Deprecated` |

**三件套一致性规则**(`Ready → Implemented` 转换):

- PRD / Tech Design / Plan 三个状态**必须同时**进入 `Implemented`(不允许单层先 `Implemented`);
- 转换由 `advance` 统一写入并留痕,避免外部 PR merged 与 wiki 状态不一致;
- 提交信息里的 `Reviewed-by:` trailer 是评审动作的**记录**,取值只能来自复审块里 `评审人` 的实际值;
  它**不是**门禁依据(门禁依据是判据 + 留痕 = 状态块 + 复审块 + git 历史)。

**人与 agent 走同一条流水线**(实施契约 R-2 / R-3):

人的接入只有两种形态 —— (a) 在仓内**新增素材**(如 `material/{date}/*.md`);(b) 直接在**制品的 `## 复审 (Review)` 段里写署名**。
**不存在**「决定文件」「专属人工通道」这类旁路。写完之后,人跑的是**同一条**命令:

```bash
bash scripts/ssdctl.sh advance <artifact> --to Ready          # 与 agent 完全同一条
```

- 复审块**为空** ⇒ 由机器写(评审人 = `--actor`,评审日期 = 今天,评审结论 = `通过`,评审方式 = `自动判据`);
- 复审块**非空** ⇒ **原样保留**,机器只写状态块 —— `advance` **永不覆盖**已写的署名;
- `--actor` **只允许 `agent:<id>` 形态**;`--actor human:x` ⇒ exit 1,提示「人工署名请写在制品的 `## 复审 (Review)` 段内」;
- 非阻断判据失败时,人把该判据 id 写进复审段的 `已知问题` 行,`advance` 才放行;
- `advance` 校验失败时**直接退出非零且文件零改动**;`--dry-run` 只校验并输出计划,不写任何文件(实施契约 §5.2)。
- **(历史)**:原「人工决定记录」通道(`decide` 子命令 / `advance --decision`)已于 2026-11-24 的 F9 裁决**删除**,不再使用。

四条不可越过的线:

1. **你的天花板是 `Ready`**,且由**判据**决定,不由你自述:判据不过就停在 `Draft`。
2. **不得冒充人工**:`human:` 前缀只允许人写(实施契约 INV-3 / §3.1);你只写 `agent:<id>`。
3. **`Implemented` 需要外部事实**:没有 `external:` 依据,不得写(实施契约 §5.2)。
4. **每次状态转换都必须留下可回读留痕** = 状态块 + 复审块 + git 历史(实施契约 R-5);无留痕的转换视为非法。
   状态块 / 复审块 / 制品正文不一致时用 `bash scripts/ssdctl.sh verify <artifact>` 查。

> **状态图与跨层联动**(三层状态机图、事件源 → 联动动作图、`0 关联代码仓` 的特殊语义)见 §11.5;
> **判据决定「能不能进」,机器决定「谁写进去」** —— 判据的唯一权威位置是 `schema/criteria.json`,
> `bash scripts/ssdctl.sh criteria <artifact>` 逐条判定并给出 `claims[]`。

## 6. 门禁执行

门禁是裁判,不是建议。**退出码:0 = 通过,1 = 存在违规,2 = 调用 / 环境错误**。

调用约定:`.sh` 用 `bash scripts/<name>.sh`、`.py` 用 `python3 scripts/<name>.py`(都**不要**用 `./` 前缀;
脚本从自身位置推导仓根,任何 cwd 都可以):

> **与 `AGENTS.md` §3.4 / §3.5 的关系**:那两条讲的是「用 `validate-spec` skill、不要手拼 scripts 命令」,
> 是对**交互式 agent**(有 slash 命令的环境)的入口约定。在本仓的自主流水线里**本文件就是执行入口**,没有 slash 命令可用,
> 所以直接跑下面这张表里的脚本就是本契约规定的动作 —— 两者指向同一批脚本、同一套退出码判定,不冲突。

| 脚本 | 什么时候跑 | 查什么 |
|------|------------|--------|
| `scripts/check-naming.sh` | **每次都跑** | 目录 / 文件命名与层结构形状 |
| `scripts/check-md-schema.sh` | **每次都跑** | 必填段、状态枚举、阶段感知(草稿 / 评审 / 终态) |
| `scripts/check-traceability.sh` | **每次都跑** | 跨层引用闭环(KD / V / FR / SYS / MOD) |
| `scripts/check-doc-links.py` | **每次都跑** | 仓内受版本控制的 Markdown 相对链接死链 |
| `scripts/check-line-endings.sh` | **每次都跑** | 受版本控制的文本文件不得含 CR(行尾统一 LF) |
| `scripts/check-repo-baseline.sh` | 仅 Layer 2(且仓内登记了关联代码仓时) | Tech Design `## 实现基线` 的 6 列快照 |
| `scripts/sync-prd.sh` | **每次都跑**(写模式, 幂等) | 机械登记 PRD 台账(可选层)+ 重生成根 README 统计块 |
| `scripts/sync-prd.sh --check` | 只读复查 | 统计块 / 台账与实际制品一致 |
| `scripts/sync-test-index.sh` | 启用 Layer 4 时跑(写模式, 幂等) | 重生成 `test_cases/_index.md` |
| `scripts/sync-test-index.sh --check` | 只读复查 | 用例索引与用例元信息一致 |
| `scripts/deep-scan.py` | 仅当仓内启用 `deep/` 底座时 | 理解底座台账 |
| `bash scripts/ssdctl.sh gate` | **每次都跑** | 全仓门禁(既有 8 个)+ 判据引擎(实施契约 §8) |
| `bash scripts/ssdctl.sh scan --check` | **每次都跑** | **跨制品一致性**:上游闸门 + 三件套原子性 + 字段自洽(实施契约 R-6);**只读**,不比对任何快照文件 |

执行规则:

- **退出码 1 = 你的产物有问题** → **修产物**,然后重跑。**禁止绕过**:不改门禁、不改 `scripts/**`、不删检查项、
  不用 `--root` 指向别处、不因为「本次 diff 没碰产品目录」就跳过。
- **退出码 2 = 环境 / 调用错误**(路径写错、参数不对、目录不存在) → **修命令**,不要当通过。
- 层目录不存在 → 该层**跳过**(不是失败);层目录存在但没有制品 → ⚠ 且退出码 0;
  **全仓所有层都没有制品** → 退出码 1(「本仓没有任何规格产物,门禁无从校验」)。
- **缺下游层不是违规**:只有 PRD、或只有 PRD + TD 的仓必须能过追溯门禁;但**有下游却缺上游是违规**(例如有 Plan 却没有 TD)。
- 跑门禁时带 `NO_COLOR=1`;需要机器消费时加 `--json`。
- **`ssdctl` 的退出码同样是 0 / 1 / 2**(0=通过,1=不通过,2=用法 / 内部错误,实施契约 INV-7);
  `gate` 与 `scan --check` 必须**有非空 stdout**(防空转断言,实施契约 §8)。
  解释器名按本机实际(`python` 或 `python3`),但**子命令名与参数一字不改**(实施契约 §5)。
- **统计块 / 台账 / 用例索引不一致**(`sync-prd.sh --check` 或 `sync-test-index.sh --check` 退出 1,提示「已过期」)→
  跑**写模式** `bash scripts/sync-prd.sh`(或 `bash scripts/sync-test-index.sh`)重新生成, 再 `--check` 复查。
  写模式是**幂等**的:同一份制品跑两次结果一致。**不得手改**统计块 / `_index.md` / 台账内容 —— 那是再生块,手改会被下一次写覆盖。
- 修不动就**如实报告 exit 1 / exit 2 的原始输出**,不要伪造「已通过」。

## 7. 产出格式

严格照 `schema/**` 的模板产出:

- **不增删章节**:标题文字照抄(`## 复审 (Review)` 不是 `## 复审`),不写模板外的章节。
- **占位符清零**:所有 `{...}` 占位符替换为真实值;用不到的行(例如 Plan 的 `> **参考 Test Cases**:`)整行删除。
- **状态块与复审块按 §5 的 4+4(+1 可选)行写**:`> **状态**` 必填;`> **状态主体**` / `> **状态时间**` / `> **状态依据**`
  与 `> **评审人**` / `> **评审日期**` / `> **评审结论**` / `> **评审方式**` 在 `Draft` 阶段允许缺省
  (复审段另有可选的 `> **已知问题**: <criterion-id> — <说明>` 行),
  但**不留占位符、不填假值**。署名主体只能是 `agent:<id>`(§3 第 1 条);**推进由 `ssdctl advance` 代写**(§3 第 2 条)。
- **跨层引用写两级相对路径**:Tech Design → PRD 写 `../../prd/{date}/{topic}.md`;Plan → Tech Design 写
  `../../tech_design/{date}-{topic}/`;Plan → PRD 写 `../../prd/{date}/{topic}.md`。单级 `../` 会被追溯门禁漏检。
- **跨仓引用带仓库标识**:格式 `{标识}/{路径}`,标识取 `AGENTS.md` §1.1「标识」列;禁止口语化引用
  (「后端仓库」)与裸 `src/` `cmd/` `pkg/` `internal/`。
- **追溯 ID 用封闭白名单**:`KD-{n}` / `V-{n}` / `FR-{n}` / `SYS-{n}` / `MOD-{n}`。
  V 必须在同文件有 `### V-{n}:` 定义;KD 必须在 TD 的 `ards.md`(v4)或 `decisions.md`(v3)有 `## KD-{n}:` 标题;
  Change 段必须同时引用 KD 与 V。
- **量化指标写具体数字**,并回答「首笔 / 冷启动谁保护」;禁止「响应要快」这类模糊描述。
- **文件编码**:UTF-8,**LF 行尾**(仓库 `.gitattributes` 规定 `* text=auto eol=lf`);不要产出 CRLF 文件。

## 8. 提交与证据

**分支**:从主分支切出 `spec/{issue-identifier}-{topic}`(Symphony 工作区目录名 = issue 标识)。
**只提交本层产物**:显式列出要加入版本控制的路径,不要 `git add -A`(工作区里可能有你的临时文件)。

**作用域**:commit / push 只发生在**流水线给你的这个工作区**与**本 issue 的专用分支**上 —— 这是自主运行的前提(评审方看的是 PR diff)。
交互式会话里提交由人自己做,不要自行 commit。**禁止**:push 到主分支、merge、伪造评审签署、动工作区以外的仓库。

**提交信息**格式:

```text
<type>(<scope>): <一句话摘要>

<正文:改了什么 / 为什么 / 门禁实际结果>

Reviewed-by: <评审人 handle>
Issue: {{ issue.identifier }}
```

- `Reviewed-by:` 的值**只能**取自产物文件 `## 复审 (Review)` 段里 `> **评审人**` 的**实际值** ——
  可能是 `agent:<id>`(判据自动签署),也可能是人自己写的 handle。**不得**写你没签过的名字(§3 第 1 / 7 条)。
- 若复审块尚未签署(产物仍是 `Draft`):**`Reviewed-by:` 整行不写** —— commit message 里连这一行都不要出现,
  也不写 `Reviewed-by: 待补` 这类占位;在 workpad 里说明「评审未签署, Reviewed-by 待补」。
  **不要用 agent 自己的 handle 冒充人工评审**(§3 第 1 条)。
- `Issue:` trailer 固定写当前 issue 标识。

**证据锚点**:现状断言(已实现 / 已修复 / 当前不存在)必须带锚点,格式
`{仓库标识}@{短SHA}:{路径}#L{行号}`(`AGENTS.md` §1.7)。设计意图、未来计划、规格文档内部的约定不写锚点,
引用仓内文档路径即可。锚点必须**真实可解析**;查不到就不写,不要编。

**PR 描述**必须包含:本 issue 关联的产物路径、门禁的实际输出摘要、以及上面那些证据锚点。
**不要合并 PR**(§3 第 4 条)—— 合并由人完成。

## 9. 完成判据

本次 turn 可以结束,当且仅当**全部**满足:

1. **产物完整**:目标层的规范形状文件已写完;`schema/**` 要求的必填段齐全;占位符清零;
   状态块与复审块按 §5 成形(未签署则留空,不填假值)。
2. **门禁全绿**:§6 中该层要求的脚本全部退出码 0。把**实际命令与退出码**写进 workpad。
   任何一个非 0,要么修好,要么(确实是环境问题)如实报告 exit 2 —— 不要把非 0 说成通过。
3. **提交并推送**:在工作区的 `spec/{issue-identifier}-{topic}` 分支上有且仅有本轮需要的提交;
   除 workpad 之类临时文件外,工作区没有未提交的改动。**不 push 主分支、不 merge**(§3 第 15 条)。
4. **状态推进全部经 `ssdctl advance`**:推进到的状态**不超过判据允许的上限**;没有手改状态行;
   没有冒充人工署名(§3 第 1 / 2 条)。判据不过就停在 `Draft` 并如实报告失败项。
5. **汇报**:输出「产物路径 + 门禁命令与退出码 + 当前状态(谁写的、依据是什么)+ 遗留问题 + 需要人做什么
   (合并 PR / 在制品里补署名 / 确认外部事实)」。

**不满足就不要声称完成。** 缺上游、门禁非 0、无法确定目标层 —— 这三种情况按 §2 / §6 如实报告并结束 turn,
不要产出猜测内容来「凑完成」。

## 10. 续跑与失败处理

{% if attempt %}
### 续跑分支(这是第 N 次尝试,attempt = {{ attempt }})

- **不要从头再来。** 先看工作区当前状态:`git status --short`、`git log --oneline -5`、以及上轮写到的文件。
- 上轮已完成的部分**保留**;只补没做完的部分。重新读上轮写的文件,确认它满足 §7 的格式与 §6 的门禁,
  而不是凭记忆接着写。
- 上轮已经提交并推送过:先 `git fetch` / `git pull --ff-only` 把远端分支拿下来再继续。
- 上轮因**门禁 exit 1** 中断:**这轮先跑门禁**,拿到具体违规清单再改,不要凭印象改。
- 上轮因**exit 2**(环境 / 调用错误)中断:先修命令(路径、参数、解释器),确认脚本能跑起来再谈产物。
- **不要重复提交**同一份内容;一次改动一次提交。
- **状态以仓内机器记录为准**:跑 `bash scripts/ssdctl.sh scan` 与 `bash scripts/ssdctl.sh verify <artifact>`
  复核上轮到底推进到哪一步、依据是什么,不要凭记忆。
- 若本轮判断「本 issue 在当前状态无法推进」(缺上游 / 判据不通过 / 目标层无法确定),
  **直接报告并结束**,不要靠反复重试硬推。
{% else %}
### 首轮分支(attempt 为空 = 第一次尝试)

- 从零开始:先定位目标层与 topic(§2),再读模板与上游(§4),然后 **写 → 跑门禁 → 提交 → 汇报**。
- 首轮就把目标层、目标 topic、上游路径写进 workpad,后续轮次靠它对齐。
- 首轮不要试图一次做完整个流水线:**1 issue = 1 层**(§2)。上游还没到 `Ready` 就不要写下游层。
{% endif %}

---

## 11. 使用指南 (How To Use)

> **本节面向人(以及交互式 agent)**,讲**怎么用**这套流水线。
> §1–§10 是 agent 的执行契约(规范);两者冲突时**以 §1–§10 为准**。
> 自主流水线的 agent 只执行 §1–§10,不必读本节。

### 11.1 核心理念

#### Why-First

在写任何代码前,回答四个问题:

1. **为什么有这个流程?** 它解决什么问题?
2. **具体解决什么问题?** 问题是什么?
3. **代码为什么这样设计?** 决策依据是什么?
4. **这应该放在哪里?** 哪个组件负责?

#### Given/When/Then

用自然语言描述行为:

- **Given** 前置条件
- **When** 触发动作
- **Then** 预期结果

#### 复审机制

每个 PRD 定期复审,防止 feature rot。三问由 **agent 起草并自评**,人类**可选复核**:

- **仍然重要?** Yes / No / 重新定义
- **应当保留?** Yes / No
- **可以删除?** Yes / No

> **谁写的,怎么区分**:三问答案与复审块一起落在 `## 复审 (Review)` 段,署名规则见 §5「怎么区分署名」。
> 署名为 `agent:<id>` = agent 起草自评;署名为**裸人名 handle**(无前缀)= 人类复核。
> **agent 不得填 `human:` 前缀,也不得代填人名** —— 不得冒充人工。

#### Harness 原则

工作流是固定的 harness,不是灵活的建议:

- 5 步必须走完,不简化
- 每步有明确的"门禁清单"
- 违反则失败,不跳过

### 11.2 怎么开始

#### 谁来读

本指南面向 AI agent 和开发者,用于规范从需求到代码的完整流程。
**流程由 agent 推进**:agent 依仓内判据自动产出制品并推进状态;人类**走同一条流水线** —— 需要介入时,
在仓内**新增素材**或直接在制品的 `## 复审 (Review)` 段写署名,然后跑**同一条** `bash scripts/ssdctl.sh advance <artifact> --to <状态>`,
不必逐条盯流程 —— 见 §5。

#### 从哪里开始

当有新的需求时:

1. **Step 0: 收集原始需求** 将原始描述或文件引用放入 `prd/{YYYY-MM-DD}/`(多文件),或启用 `material/{YYYY-MM-DD}/` 可选层
2. **Step 1: 加工为 PRD** 读 `prd/{YYYY-MM-DD}/`,产出 PRD 到 `prd/{YYYY-MM-DD}/{topic}.md`
3. **Step 2: PRD → Tech Design** 产出多文件 Tech Design 到 `tech_design/{YYYY-MM-DD}-{topic}/`(v4 默认 4 子文件)
4. **Step 3: Tech Design → Plan** 产出 Plan 到 `plan/{YYYY-MM-DD}-{topic}/{topic}.md`
5. **Step 4: 执行 TDD** 按 Plan 的验证用例进入 Red → Green → Refactor(仅 ≥1 关联代码仓时)

> 可选 Layer 4:`test_cases/{YYYY-MM-DD}/{topic}.md`(项目启用时存在,配合 [schema/test_case.md](schema/test_case.md) 模板产出)
> 可选素材区:`material/{YYYY-MM-DD}/`(见 [material/README.md](material/README.md))
> **状态起点**:agent 产出的三层规格先落在 `Draft`;该层判据全绿后由 **agent 自动推进**到 `Ready`(人类可随时介入,见 §5)。

#### 遇到问题时

- **不确定填什么?** 查看对应 schema 模板 [schema/prd.md](schema/prd.md)
- **不知道覆盖哪些场景?** 参考下方门禁清单(§11.7)
- **不确定一个需求走多深?** 默认走完 5 步,不简化
- **多仓项目怎么写 Plan?** 见 [AGENTS.md](AGENTS.md) §1.5 多仓 Plan 编排
- **怎么声明设计基于的代码现状?** 见 [AGENTS.md](AGENTS.md) §1.6 实现基线
- **怎么引用代码现状作为证据?** 见 [AGENTS.md](AGENTS.md) §1.7 证据锚点
- **agent 到底能写什么、不能写什么?** 见 [AGENTS.md](AGENTS.md) §3.3 状态流转 与本文件 §3 硬禁止 / §5 状态推进规则

### 11.3 目录组织(核心 4 个文件夹 + 可选层)

```text
{project-root}/
├── prd/              # 素材区 + Layer 1: PRD(素材区非独立 Layer)
├── tech_design/      # Layer 2: 技术设计(按功能组织,v4 默认 4 子文件)
├── plan/             # Layer 3: 实施计划(按功能组织)
├── schema/           # 模板定义
├── material/         # 可选: Layer 0 素材区 + 批次 PRD 台账
├── test_cases/       # 可选: Layer 4 黑盒用例
└── deep/             # 可选: 深度理解层
```

**prd/ 命名** (素材区 + Layer 1,见 [prd/README.md](prd/README.md)):

```text
prd/
└── {YYYY-MM-DD}/              ← 日期分桶(素材 + PRD 同目录)
    ├── {source-1}.md          ← 素材(只读,非 Layer 制品)
    └── {topic}.md             ← Layer 1: PRD
```

**plan/ 命名** (单文件):

```text
plan/
└── {YYYY-MM-DD}-{topic}/
    └── {topic}.md             ← 内容文件,文件名 = 目录名里的 topic
```

**tech_design/ 命名** (v4 默认,见 [tech_design/README.md](tech_design/README.md)):

```text
tech_design/
└── {YYYY-MM-DD}-{topic}/
    # v4 (默认, 4 子文件 - 存 ards.md 或 apis.md 则走 v4 校验)
    ├── README.md              ← 综合描述 + 场景映射 + 实现基线(必填)
    ├── ards.md                ← 架构决策 + 方案对比 + 探索机制 + Gap(必填)
    ├── apis.md                ← 接口契约 + 枚举速查 + 时序图(必填)
    └── data-model.md          ← ER 图 + 数据结构明细(必填)

    # v3 (存量 / 显式 opt-in, 6 子文件 + 条件 interactions)
    # ├── README.md            ← 入口/索引(必填)
    # ├── decisions.md         ← 关键决策(必填)
    # ├── data-model.md        ← 数据模型(必填)
    # ├── api-contracts.md     ← API 契约(必填)
    # ├── scenario-mapping.md  ← 场景映射(必填)
    # ├── interactions.md      ← 时序图(视情况)
    # └── quality.md           ← 指标 + 降级 + 错误(必填)
```

### 11.4 5 步工作流

```mermaid
flowchart LR
    A[原始需求] -->|Step 0 收集| B[素材]
    B -->|Step 1| C[PRD]
    C -->|Step 2| D[Tech Design]
    D -->|Step 3| E[Plan]
    E -->|Step 4 交接| F[外部代码仓 TDD]
    F -->|外部 PR merged 事实| G[wiki 三件套同时标 Implemented]
    F -->|0 关联代码仓| H[停留 Ready]
```

#### Step 0: 收集原始需求

原始素材(用户抱怨、会议纪要、需求文档)放入 `prd/{YYYY-MM-DD}/`(多文件,**只读**)。
项目需要独立的素材暂存区 + 批次 PRD 台账时,启用 [material/README.md](material/README.md) 描述的可选素材区。

> `prd/{YYYY-MM-DD}/` 是 Layer 1 的**素材区**,**不是**独立 Layer。架构层只有 3 层(Layer 1/2/3),详见 [prd/README.md](prd/README.md)。

#### Step 1: 原始素材 → Layer 1 PRD

经过分析和讨论收敛,产出 PRD 到 `prd/{YYYY-MM-DD}/{topic}.md`。agent 写入时状态是 `Draft`;该层判据全绿后由 **agent 推进到 `Ready`**(人类可在任意时刻介入)。

**转换关系**:
- **1:1**: 一份原始文档对应一个 PRD
- **1:N**: 一份原始文档(如 `history-apis.md`)拆成多个 PRD
- **N:1**: 多份原始文档合成一个 PRD
- **N:N**: 更复杂的 1→N→M 组合

**PRD 必填**(机器必填 5 段,权威定义见 [schema/prd.md](schema/prd.md)):

- **为什么 (Why)**: 一句话说明问题和目的
- **目标 (Goal)**: 可验证的成功标准(须含可勾选项 `- [ ]`)
- **场景 (Scenarios)**: Given/When/Then,覆盖正常路径 + 至少一个异常(`**But**`)
- **不在范围内 (Out of Scope)**: 明确不做的内容
- **复审 (Review)**: 评审签署四行 + still_matters / should_keep / can_delete 三问(防止 feature rot)

> `## 链接 (Links)` 与 `## 变更记录 (Change Log)` 是**推荐段**,不参与机器校验;用得到就写,不用可省。

#### Step 2: PRD → Layer 2 Tech Design

基于同 topic 的 PRD(上游 `Ready` 时可直接推进;上游仍 `Draft` 时可起草,但推进需上游先到 `Ready`),产出 `tech_design/{YYYY-MM-DD}-{topic}/`(**v4 默认** 4 子文件):

- **README.md** — 综合描述 + `## 场景映射` + `## 实现基线`
- **ards.md** — 架构决策 / 方案对比 / 探索机制 / Gap
- **apis.md** — 接口契约 / 枚举速查 / 时序图
- **data-model.md** — ER 图 / 数据结构明细

> **代际选择**:v4 是**默认代际**,新建目录一律按 v4 产出。v3(6 子文件 + 条件 interactions)是**存量 / 显式 opt-in**,校验脚本保留 v3 分支但**不迁移**存量目录。
> v4 模板见 [schema/tech_design/ards.md](schema/tech_design/ards.md) + [schema/tech_design/apis.md](schema/tech_design/apis.md)。

**Tech Design 必填**:

- **关键决策 (KD)**: 方向选择 / 方案对比 / OQ / Spikes / Pivot / Enforced by
- **场景映射**: PRD 场景 → 组件/动作/数据模型(PRD 的每个场景都要被映射)
- **实现基线**: 设计所基于的代码现状快照(见 [AGENTS.md](AGENTS.md) §1.6)
- **指标**: 具体数字(不是模糊描述)
- **降级策略**: 异常情况下的行为

#### Step 3: Tech Design → Layer 3 Plan

基于同 topic 的 Tech Design(上游 `Ready` 时可直接推进;上游仍 `Draft` 时可起草,但推进需上游先到 `Ready`),产出 `plan/{YYYY-MM-DD}-{topic}/{topic}.md`(**Ready**):
变更索引 + 变更清单 + TDD 流程 + 跨文件引用对账 + 验证用例 + 业务约束 + 开发约束 + 完成检查。

**Plan 必填**:

- **变更索引**: 表格快速扫读(# / 文件路径 / 类型 / KD 引用 / V 引用 / 状态)
- **变更清单**: 每个文件的"变更描述"(新增/修改/删除什么) + "策略约束"(怎么做、不做什么)
- **跨文件引用对账**: KD / SYS / MOD / FR / V 闭环检查
- **验证用例 (V)**: Given/When/Then,TDD 阶段执行
- **业务约束**: 前置/不变量/后置/副作用
- **开发约束**: 并发/事务/幂等性/重试/超时
- **完成检查**: 4 段(实现层 / 验证层 / 引用层 / 流程层)

> ⚠️ **设计原则**:Plan 是"实施指南",不是"替代实现"。
> 变更描述用文字说明策略和约束,指导参与的 agent 写出代码。
> 完整代码在 TDD 阶段产出,不是提前写在 Plan 里。

> **多仓项目**:变更清单按仓分组,组标题为 `#### {仓库标识} 变更`,Change 路径带 `{标识}/` 前缀,V 用例按场景聚合。完整规则见 [AGENTS.md](AGENTS.md) §1.5。

#### Step 4: 执行 (Plan → TDD → 外部代码仓)

按 Plan 进入 TDD 循环:

1. **Red** 写一个失败的测试(V 用例)
2. **Green** 写最少代码让测试通过
3. **Refactor** 优化代码,保持测试通过

完成所有 V 用例后,wiki 状态按**外部关联代码仓情况**分两条路:

- **≥1 关联外部代码仓**(代码仓位于本仓库**之外**,独立 Git 仓库 / monorepo 子目录):
  - 外部 TDD 全过 + 外部 PR merged 后,**该事实**成为状态依据(`状态依据: external:<ref>`)
  - agent 依据该事实回写本 wiki 三件套状态:PRD → **Implemented**,Tech Design → **Implemented**,Plan → **Implemented**(**三件套同时**,不允许单层先转,见 §5)
  - 人类也可以手动介入:在制品的 `## 复审 (Review)` 段写好署名,再跑**同一条** `bash scripts/ssdctl.sh advance <artifact> --to Implemented --external <ref>`,机器代写并同样留痕
- **0 关联代码仓**(纯文档项目,如 SSD-Template 自身):停留在 **Ready**,标记 "Awaiting TDD in external code repo"

> 💡 **AI Coding Agent 场景的简化路径**:
>
> 当 fork 项目的代码仓由 AI coding agent(Claude Code / aider / Cursor / Codex 等)接管时:
> - **wiki 文件本地可达** → coding agent 直接 `cat plan/.../topic.md` 即可消费,**零同步成本**
> - **Plan Ready = 工作信号** → 不需要 wiki agent 派活 / issue kickoff
> - **coding agent 自带 spec→code 工作流** → "读 plan → 写代码 → 跑测试"是其原生能力
> - **人工接入 = 新增素材 / 在制品里写署名**,然后跑同一条 `advance`,不是实时交互通道,也没有专属的人工通道
>
> **不要**为 coding agent fork 引入 wiki agent kickoff / `Implementing` 中间态 / 调度机制。
> 这是把 "Plan = 可执行规约"(executable specification)的简单模型,人为退化为 "Plan = 待派工单"的复杂模型。
> 反例论证见 §11.5。

### 11.5 状态机速览 (State Machine)

> **状态块 / 复审块的字段定义、转换触发表、三件套一致性规则以 §5 为准**(那是规范);本节只补图与联动语义。

#### 三层状态图

每层独立维护自己的状态(per-layer independent lifecycle):

```mermaid
stateDiagram-v2
    direction LR

    state "PRD" as prd {
        direction LR
        state "Draft" as p_d
        state "Ready" as p_r
        state "Implemented" as p_i
        state "Deprecated" as p_x

        [*] --> p_d
        p_d --> p_r: 判据全绿 → agent 推进(人类可介入)
        p_r --> p_i: 外部 PR merged 事实 → 三件套同时回写
        p_r --> p_x: 外部事实(external: 依据)
        p_i --> p_x: 外部事实(external: 依据)
        p_x --> [*]
    }

    state "Tech Design" as td {
        direction LR
        state "Draft" as t_d
        state "Ready" as t_r
        state "Implemented" as t_i
        state "Deprecated" as t_x

        [*] --> t_d
        t_d --> t_r: 判据全绿 → agent 推进(人类可介入)
        t_r --> t_i: 外部 PR merged 事实 → 三件套同时回写
        t_r --> t_x: 外部事实(external: 依据)
        t_i --> t_x: 外部事实(external: 依据)
        t_x --> [*]
    }

    state "Plan" as pl {
        direction LR
        state "Draft" as pl_d
        state "Ready" as pl_r
        state "Implemented" as pl_i
        state "Deprecated" as pl_x

        [*] --> pl_d
        pl_d --> pl_r: 判据全绿 → agent 推进(人类可介入)
        pl_r --> pl_i: 外部 PR merged 事实 → 三件套同时回写
        pl_r --> pl_x: 外部事实(external: 依据)
        pl_i --> pl_x: 外部事实(external: 依据)
        pl_x --> [*]
    }
```

> **推进主体 = agent**:状态由 agent 依仓内判据(`schema/criteria.json`)自动推进,写入由机器代写并留痕。
> **agent 的权限天花板 = `Ready`**(判据驱动);`Implemented` 需要**外部事实**(外部 PR merged);`Deprecated` 同样需要 `external:` 依据。
> **人与 agent 同路**:人类可手动介入,形态只有「新增素材」或「在制品的 `## 复审 (Review)` 段写署名」,然后跑**同一条** `bash scripts/ssdctl.sh advance` —— **没有实时交互通道**。
> **0 关联代码仓库**:规格停留在 Ready,标记 "Awaiting TDD in external code repo"(本仓库为纯 wiki)
> **≥1 关联外部代码仓库**:外部代码仓(位于本仓库**之外**)PR merged 后,依据该事实把 wiki 三件套状态推进到 Implemented
> **Deprecated**:3 层均支持,上游废弃时下游级联

#### 跨层协调规则

```mermaid
flowchart TB
    subgraph eventsource [事件源]
        E1[PRD Deprecated]
        E2[PRD 复审变更]
        E3[TD Plan 重大修改]
        E4[外部代码仓 PR merged]
        E5[复审超期]
        E6[人工新增素材<br/>或在制品复审段署名]
    end

    subgraph actions [联动动作]
        A1[联动 TD Plan Deprecated]
        A2[PRD 回退 Draft 重审]
        A3[PRD TD 标需重审]
        A4[三件套回写终态]
        A5[发送复审提醒]
        A6[agent 与人同路推进状态<br/>状态依据 external:...]
    end

    E1 --> A1
    E2 --> A2
    E3 --> A3
    E4 --> A4
    E5 --> A5
    E6 --> A6
    E6 --> A1
    E6 --> A4
```

> **事件源 E6 = 人工接入**:人类不直接改状态行,而是**新增素材**或直接在**制品的 `## 复审 (Review)` 段写署名**;
> agent(或人自己)跑**同一条** `bash scripts/ssdctl.sh advance <artifact> --to <状态>`,机器把状态块写好。
> 若需要外部事实,状态依据写 `状态依据: external:<ref>`。其余事件源(上游废弃、上游变更、PR merged、复审超期)同样由 agent 检测并推进 —— **人与 agent 走同一条流水线**。

#### 0 关联代码仓库的特殊语义

> ⚠️ **核心原则**:本仓库**永远是 wiki**(spec 仓库),**永远不会**变成代码仓。
> 即使项目有关联的代码仓,代码仓也**位于本仓库之外**(独立 Git 仓库 / monorepo 子目录 / 其他物理位置)。
> 本仓库**不包含** `src/`、`cmd/`、`pkg/`、`internal/` 等代码目录。这些只存在于**外部**代码仓。

**术语澄清**:

| 表述 | 准确语义 |
|------|---------|
| **本仓库 / 本 wiki** | 始终是规格文档仓库,**永远不会**变成代码仓 |
| **0 关联代码仓库** | 本 wiki 未关联任何外部代码仓库(纯文档项目) |
| **≥1 关联代码仓库** | 本 wiki 关联了 N 个**外部**代码仓库(代码仓位于本仓库**之外**) |
| **外部代码仓** | 独立 Git 仓库 / monorepo 子目录,通过 `{仓库标识}/{path}` 跨仓引用(详见 [AGENTS.md](AGENTS.md) §1.2) |
| **wiki 的 Implemented** | 外部代码仓 PR merged 后,依据该外部事实(`状态依据: external:<ref>`)回写到本 wiki 的镜像状态 |

**本模板自身(0 关联代码仓库)**:

- Step 1 产出:`prd/{YYYY-MM-DD}/{topic}.md` 状态 **Draft**(判据全绿后由 agent 推进到 Ready)
- Step 2 产出:`tech_design/{YYYY-MM-DD}-{topic}/*` 状态 **Draft**(判据全绿后由 agent 推进到 Ready,v4 默认 4 文件)
- Step 3 产出:`plan/{YYYY-MM-DD}-{topic}/{topic}.md` 状态 **Draft**(判据全绿后由 agent 推进到 Ready)
- 不进入 Implemented(无外部代码仓作为回写源)
- Tech Design 的 `## 实现基线` 段写「不适用: 本项目无关联代码仓」(见 [AGENTS.md](AGENTS.md) §1.6)

**Fork 后接入外部关联代码仓库**:

> 外部代码仓**独立**于本仓库,本仓库保持纯 wiki 状态:

- 按 [AGENTS.md](AGENTS.md) §4.A 定制指南 在 §1.1 登记外部代码仓清单(仓库地址 / 主要语言 / 角色)
- 跨仓引用统一使用 `{仓库标识}/{path}` 写法
- Step 4 (TDD) 在**外部代码仓**内执行,**不**在本仓库
- 外部 PR merged 后,agent 依据该**外部事实**(`状态依据: external:<ref>`)把本 wiki 三件套状态推进为 Implemented;人类也可手动介入 —— 在制品的 `## 复审 (Review)` 段写好署名,再跑**同一条** `bash scripts/ssdctl.sh advance <artifact> --to Implemented --external <ref>`
- 维护"外部代码仓 → 本 wiki"的状态同步规则

#### 为什么不引入 `Implementing` 中间态?

> **反例论证** 帮助 fork 项目避免错误地复杂化

如果 fork 项目考虑在 `Ready → Implemented` 之间加一个 `Implementing` 状态(表示"正在 code repo 实施中"),请先回答:

| 设想加 `Implementing` 的理由 | 实际是否需要? |
|---------------------------|---------------|
| "想看到哪些 Plan 正在被实施" | ❌ git branch / PR 状态已记录此信息,去 wiki 看是冗余 |
| "防止多个 agent 重复领取" | ❌ git branch naming 约定(`plan/{date}-{topic}`)即可去重 |
| "想统计 in-flight 工作量" | ❌ code repo 的 PR list 就是权威数据源 |
| "想在 Implementing 状态校验进度" | ❌ TDD 是细粒度过程,不适合粗粒度状态机 |

**结论**:`Implementing` 中间态为流程增加了 **+1 张状态图 + 1 套转换规则 + 1 个跨仓写权限**,但解决的全是 code repo 自己能解决的问题。

**唯一例外**:仅当 ≥2 个 code agent 同时从同一 wiki 拉活**且无 git 协调能力**时(罕见),才需要 `Implementing` 中间态 + 显式调度。参见 [AGENTS.md](AGENTS.md) §4.A 的 fork 启动模式选项。

### 11.6 何时升级

> 简化原则: 默认所有内容用 3 个 schema。只在以下情况考虑升级。

| 触发条件 | 升级方案 | 状态 |
|---------|---------|------|
| 决策影响 ≥3 个 PRD 或长期架构 | 独立 ARD:`tech_design/{date}-{topic}/ards.md` 的 `## KD-{n}` 段已内建;跨 PRD 的决策写进对应制品的复审段 / 正文 | 已内建 |
| 多需求聚合管理 | 批次 PRD 台账 `material/{date}/PRDS.md` + `scan` 打印的派生视图 | 可选层,启用即用 |
| 需要可执行 BDD 框架 | 已在 PRD/Plan 内联 Given/When/Then,无需独立 | N/A |

### 11.7 门禁清单(权威定义见 `schema/*`)

> **门禁清单的权威定义在各 `schema/*` 文件内**。本节不复制,避免与 schema 漂移。
> 下表是**速查索引**,实际勾选项以 schema 文件为准。
> **脚本执行表(什么时候跑什么脚本、退出码怎么判)以 §6 为准**,本节不重复。

| 层 | 门禁清单位置 | 自动校验 |
|----|-------------|---------|
| PRD | [schema/prd.md](schema/prd.md) 全文 + `scripts/check-md-schema.sh` | ✓ |
| Tech Design | [schema/tech_design/README.md](schema/tech_design/README.md) + 各子文件"门禁清单"段 + `scripts/check-md-schema.sh` | ✓ |
| Plan | [schema/plan.md](schema/plan.md) 完成检查段 + `scripts/check-md-schema.sh` + `scripts/check-traceability.sh` | ✓ |
| 实现基线(可选) | Tech Design `## 实现基线` 段 + `scripts/check-repo-baseline.sh` | ✓(有关联代码仓时) |

**调用方式**:§6 表中标「**每次都跑**」的脚本全部返回 0(按层 / 按条件启用的脚本按其条件额外跑)→ 「可评审」。此后由 **agent** 调 `bash scripts/ssdctl.sh advance <artifact> --to <状态>` 推进状态(机器判据驱动 + 留痕);人类需要介入时**新增素材**或**在制品的 `## 复审 (Review)` 段写署名**,然后跑**同一条** `advance`,**不**手工改状态行。
`bash scripts/ssdctl.sh` 的子命令全集:`scan` / `criteria` / `gate` / `advance` / `queue` / `verify`;`advance` 常用参数:`--to <Ready|Implemented|Deprecated>` / `--external <ref>` / `--actor agent:<id>` / `--dry-run`;退出码统一 `0` = 通过 / `1` = 存在违规 / `2` = 调用或环境错误。

判据引擎的单元测试(CI 也跑这一条):
`PY="$(bash scripts/ssdctl.sh --python)"; "$PY" -m unittest discover -s scripts/tests -t scripts/tests`
—— 解释器同样由包装器解析,CI 与本地用同一条规则;没有这一步,有人把引擎改回「永远通过」CI 仍然是绿的。

> **为什么命令形态是 `bash scripts/ssdctl.sh` 而不是「直接用解释器跑 `scripts/ssdctl.py`」**:
> `scripts/ssdctl.sh` 是 `scripts/ssdctl.py` 的**解释器解析包装器**。不同机器上 `python` 未必可用
> (Windows 的 Microsoft Store 占位符会命中 exit 9009 —— 命令存在但不是解释器),而 `python3` 只在
> POSIX 机器上有。包装器会依次尝试 `$SSDCTL_PYTHON` / `python3` / `python` / `py -3` /
> `~/.dsh/dsh-runtimes/*/dependencies/python/python.exe`,每个候选都通过 `-c 'import sys'` 自检;
> 全都不行时 exit 2 并列出试过的候选,**不静默继续**。显式指定解释器:
> `SSDCTL_PYTHON=/path/to/python bash scripts/ssdctl.sh <子命令>`。

### 11.8 可选层

全部**默认关闭**。目录或文件不存在时,对应校验自动跳过,模板自身零实例故全绿。

| 层 | 位置 | 用途 | 启用方式 | 说明 |
|----|------|------|----------|------|
| 素材区 | [material/](material/README.md) | 原始素材暂存 + 批次 PRD 台账 | 建 `material/` 目录 | Layer 0(可选) |
| PRD 台账 | `material/{YYYY-MM-DD}/PRDS.md` | 11 列台账,追踪素材到 PRD 的流转 | 建台账文件 | 模板见 [schema/prd-ledger.md](schema/prd-ledger.md) |
| PRD 关联矩阵 | 根 [README.md](README.md) 的「PRD关联矩阵」章节 | 8 类 PRD 关系边 | 在关系边表追加行 | 模板见 [schema/prd-matrix.md](schema/prd-matrix.md) |
| 测试用例 | [test_cases/](test_cases/README.md) | Layer 4 黑盒用例 | 建 `test_cases/` 目录 | 用 `to-test-cases` skill 生成 |
| 理解底座 | `deep/` | 主题模型 / 消歧 / 时间线 | 建 `deep/` 目录 | 用 `to-deep-understand` skill 生成 |

> 各层的启用方式、文件结构与校验口径见对应层 README。`validate-spec` skill **不校验** `deep/` 内容。

### 11.9 相关文件

| 文件 | 用途 |
|------|------|
| [WORKFLOW.md](WORKFLOW.md) | **契约唯一真源**:编排配置 + agent 工作契约(§1–§10)+ 使用指南(§11)+ 概念参考(§12)+ 编排层协作分工(§13) |
| [README.md](README.md) | 仓库入口(总览 + 规格统计 + PRD 关联矩阵) |
| [AGENTS.md](AGENTS.md) | 仓库操作契约(仓库清单 / 跨仓引用 / 多仓 Plan / 基线 / 证据锚点) |
| [docs/agent-first-direction.md](docs/agent-first-direction.md) | agent 优先的实施方向与取舍依据 |
| [docs/operation-flow.md](docs/operation-flow.md) | 端到端操作流程说明 |
| [docs/process-analysis.md](docs/process-analysis.md) | 现状流程分析(哪些步骤由 agent 承担、哪些保留人工) |
| [docs/contracts/agent-first-implementation.md](docs/contracts/agent-first-implementation.md) | **实施契约**:agent 流水线的元数据 / CLI / 调度谓词 |
| [docs/contracts/agent-first-direction.md](docs/contracts/agent-first-direction.md) | agent 优先的需求真源(R1–R8) |
| [docs/contracts/phase2-task-flow.md](docs/contracts/phase2-task-flow.md) | 阶段任务流契约(阶段划分 / 门禁 / 回写) |
| `docs/contracts/decisions/2026-11-22-agent-primary.md` | **(历史)** 历史决策记录:D-01…D-20(其中 D-02 / D-10 / D-11 已被 2026-11-24 的 F9 裁决取代) |
| [schema/prd.md](schema/prd.md) | PRD 模板 |
| [schema/tech_design/](schema/tech_design/) | Tech Design 模板 (v4 默认 4 子文件,v3 存量 7 子文件) |
| [schema/plan.md](schema/plan.md) | Plan 模板 |
| [schema/test_case.md](schema/test_case.md) | Test Case 模板 (可选 Layer 4) |
| [schema/prd-ledger.md](schema/prd-ledger.md) | 批次 PRD 台账模板 (可选 material/ 启用) |
| [schema/prd-matrix.md](schema/prd-matrix.md) | PRD 关联矩阵模板 (多 PRD 协作启用) |
| [.codex/skills/](.codex/skills/) | 9 个 skill 定义(仓内随仓库分发) |
| 历史代际(不再留档) | `git log --all -- <path>` / `git show <commit>:<path>`(历史代际仅存于 git 历史) |
| `schema/criteria.json` | **判据唯一权威**:每个判据的 id / kind / 阈值 / 是否 blocking |
| `scripts/ssdctl.py` | 判据与状态推进 CLI(`scan` / `criteria` / `gate` / `advance` / `queue` / `verify`) |
| **(历史)** `control/` 控制平面 | **(历史)** 决定记录 / 状态快照 / 证据链三件套 —— 已于 2026-11-24 的 F9 裁决**整体删除**;现行载体是**制品本身**(状态块 + 复审段)+ git 历史 |

#### **(历史)** `control/` 布局(已删除)

> **(历史)** 2026-11-24 之前,仓内曾有一个 `control/` 控制平面(决定记录 / 状态快照 / 证据链 / README)。
> F9 裁决把它整体删除:**过程状态的唯一权威载体是制品本身**(状态块 + 复审段),留痕 = 制品 + git 历史;
> `scan` 只打印派生视图、不落盘。需要历史事实时看 git 历史。

> 人工接入的形态只有两种:**新增素材**,或在制品的 `## 复审 (Review)` 段**写署名**;然后跑**同一条**
> `bash scripts/ssdctl.sh advance <artifact> --to <状态>` —— **没有实时交互通道**,也没有"人在回路里逐条点头"的流程。

---

## 12. 概念参考 (New Factors)

> **概念参考**。本节解释这套 harness「为什么长成这样」,**不定义任何可执行规则**。
> 可执行规则以本文件 §1–§10、§13 与 `schema/**` 模板为准;状态值只有
> `Draft` / `Ready` / `Implemented` / `Deprecated` 四个,全层统一。

### 12.1 为什么要有这条流程

1. Why do we have this flow?
2. What problem is this solving?
3. Why is the code shaped like this?
4. Where does this belong?

### 12.2 ARDs

> Record Your.Decisions

1. What decision was made
2. WHY it was made
3. HOW it is enforced
4. ADR for the decision
5. Reference docs for examples and detail

本仓的落地形态 = Tech Design 的 `ards.md` 里的 `## KD-{n}:` 段 —— 每个 KD **固定 5 段**
(背景 / 决定 / 备选方案 / 理由 / 如何强制);文件级的「方向选择与方案对比」与「探索记录(OQ / Spikes / Pivot)」
是 `ards.md` 的**独立段**,不在 KD 段里。模板见 [schema/tech_design/ards.md](schema/tech_design/ards.md):

```markdown
## KD-1: 选用乐观锁做并发控制

**背景 (Context)**: 库存扣减存在并发写,需要决定用哪种并发控制

**决定 (Decision)**: 用乐观锁(版本号)做并发控制

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 乐观锁(版本号) | 读多写少场景冲突少 | 冲突频繁时需要重试 |
| 悲观锁(行锁) | 冲突场景实现简单 | 写多场景吞吐差 |

**理由 (Rationale)**: 本仓读写比高,乐观锁冲突率低,不必引入锁等待

**如何强制 (Enforced by)**: `scripts/check-repo-baseline.sh`(设计所基于的代码现状快照)
```

> 决策落到「必须留痕并可回读」时,载体是**制品本身**:制品的 `## 复审 (Review)` 段(署名 + 日期 + 结论)或正文里的 `external:` / `criteria:` 依据,加上 git 历史(见 §5、§11.9)。

### 12.3 PRDs

> Capture.Product.Goals

1. WHY does this feature exist?
2. WHAT problem does it solve?
3. WHAT outcome we expect?
4. Does this still matter?
5. Should we keep it?
6. Can we delete it?

本仓的落地形态 = `prd/{YYYY-MM-DD}/{topic}.md` 的 5 个必填段(为什么 / 目标 / 场景 / 不在范围内 / 复审),
模板见 [schema/prd.md](schema/prd.md):

```markdown
> **状态**: Draft
> **状态主体**: agent:sddctl
> **状态时间**: 2026-11-22T23:30:00+08:00
> **状态依据**: criteria:PRD-READY-01
> **负责人**: {github-handle}
> **创建日期**: 2026-11-22
> **最后更新**: 2026-11-22

# PRD: {主题}

## 为什么 (Why)

{为什么存在}

## 目标 (Goal)

- [ ] AC-1 {验收标准}

## 场景 (Scenarios)

### 场景: S-1 {名称}

**覆盖**: AC-1

**Given** {前置条件}
**When** {触发动作}
**Then** {预期结果}

## 不在范围内 (Out of Scope)

- {明确不做的}

## 复审 (Review)

> **评审人**:
> **评审日期**:
> **评审结论**:
> **评审方式**:

**复审日期**: 2026-11-22

| 问题 | 答案 |
|------|------|
| 仍然重要? | Yes / No / 重新定义 |
| 应当保留? | Yes / No |
| 可以删除? | Yes / No |
```

> **状态值域与本仓状态机一致**:`Draft` / `Ready` / `Implemented` / `Deprecated`。
> `Draft` 由 agent 产出;该层判据全绿后由 agent 代写 `Ready`;人类**可**在 `## 复审 (Review)` 段复核
> (署名规则见 §5「怎么区分署名」)。三问(仍然重要? / 应当保留? / 可以删除?)由 **agent 起草自评**。
> **签署四行在 `Draft` 态留空**(不写占位符),升 `Ready` 前由 `ssdctl advance` 按判据填写真值;
> 状态块 4 行(状态 / 状态主体 / 状态时间 / 状态依据)在 `Draft` 态就要写全 —— 完整字段见 [schema/prd.md](schema/prd.md)。

### 12.4 BDDs

> Run.Your.Specs

1. Who wants to read AI code? Or AI tests?
2. BDD is not new, but suddenly relevant again
3. Readable and executable -- intent meets code

> **本仓没有独立的 BDD 层**:Given/When/Then 已经内联在 PRD 的 `## 场景 (Scenarios)` 与 Plan 的 `### V-{n}:` 验证用例里。
> 要不要单独立一层,取决于项目是否需要可执行的测试框架 —— 见 §11.6「何时升级」。

### 12.5 Example: 可执行规约

> Ancient technology, suddenly useful again.
> Connect directly to PRDs and critical user journeys

```yaml
Feature: Executable spec
  Spec-Driven Development does not fully close the loop
  BDD should

  Scenario: Close the loop
    Given an executable specification exists
    When cucumber runs
    Then the scenario passes
```

### 12.6 Bonus: Design System

> Rule.Your.UI

1. Rules: one primary button per page, no exceptions
2. Components: all states previewed in Lookbook
3. Built bottom-up, like code

### 12.7 Example: Enforced Architecture

> Rules link to ADRs.

1. BDD tests cannot talk directly to the database
2. Application code stays split into layers
3. Violations fail fast -- at commit time

Agent gets early feedback and works through it to reach the goal.

> 本仓的对应物 = §6 的门禁表:**违反即 exit 1**,agent 只能修产物,不能改门禁(§3 第 11 条)。

### 12.8 Skills Provide Focus

> The loop is generic

1. `to-tech-design` -- which rules govern these changes (关键决策 KD)
2. `to-prd` -- which goals does this serve
3. `to-test-cases` -- iterate fast, reconcile after
4. `validate-spec` -- run focused check suite
5. Goal exception -- decisions and pending work

> 上面的 skill 全部是**仓内** skill,定义在 `.codex/skills/<name>/SKILL.md`,随仓库分发。
> 完整 9 个 skill 的清单与调用签名见 [AGENTS.md](AGENTS.md) §3.7。

### 12.9 Drawbacks

1. Context-heavy - Slow feedback loop.
2. But that's the goal, no? -- Long-running tasks.

### 12.10 Summary

1. ADRs -- record decisions
2. PROs -- capture goals
3. BDD -- run you specs
4. Design system -- rule your UI
5. Harness -- enforce the loop
6. Criteria -- 让「能不能进 Ready」变成机器可判的问题(`schema/criteria.json`)

> May the SPEC be with you

---

## 13. 与编排层(DSH swarm)的协作分工

> **本节面向与本仓协作的编排层**(DSH swarm 的 Lead / Coordinator)与被派发的执行 lane。
> 它回答四个问题:**谁有资格被派工**、**谁能写状态**、**决定与证据放哪**、**brief 必须写什么**。
> **违反其中任意一条即视为协作失效** —— 不是风格偏好,是契约边界。

### 13.1 九条分工规则(R-1..R-9)

规则原文出自 2026-11-24 的《SDD × DSH swarm 协作审计》§7.1(审计稿**未入库**,故本文件不引用其路径);下表是**仓内可执行的版本**:
每条给出「谁做什么」与「怎么核对」。**这 9 条是协作的充分条件** —— 违反任意一条,协作即退回冲突态。

| 规则 | 内容 | 执行要求(谁做什么) | 核对方式(机器或人可验) |
|---|---|---|---|
| **R-1 身份唯一** | 权威身份 = **SDD 制品路径**;板任务 `description` 必含 `artifact: <path>`;板 id 永不是制品状态的权威 | Lead 建板任务时在 `description` 写 `artifact: prd/2026-11-22/layer-checklist.md` 这类**制品路径**;板 id 只当会话标识 | `bash scripts/ssdctl.sh scan --json` 的 `artifacts[].path` 与板任务里的 `artifact:` 路径一致;任何状态断言都引制品路径(§5),不引板 id |
| **R-2 派发必查** | Lead 派发前必须跑 `bash scripts/ssdctl.sh scan --json`,**只取 `dispatchable=true`**;swarm 板不是资格源 | Lead 在派工前先跑一次 scan,把 `dispatchable=false` 的制品**排除**在派工集合外;不派「板上看似 ready」的制品 | 派工前的那次 scan 有执行记录;被派工制品在 scan 输出里 `dispatchable=true`;板字段 `ready` / `blockedBy` **不出现在**判定依据里(§13.2) |
| **R-3 状态只走机器** | lane 只写**内容**;状态块 / 复审块**只能**由 `ssdctl advance` 写。lane 可达 `Ready`(判据驱动),**不可达 `Implemented`**(需 `external:` 依据) | lane 写完产物内容后跑 `bash scripts/ssdctl.sh advance <artifact> --to Ready`;手改状态行 = 违规(§3 第 2 条) | 状态块 4 行的「状态主体」是 `agent:<id>`;`bash scripts/ssdctl.sh verify <artifact>` 回读**制品状态块 / 复审段**,并用 git 历史核对留痕(§5) |
| **R-4 决定载体已取消** | 人与 agent **走同一条流水线**:没有专属的「决定文件」通道。人类的接入形态只有两种 —— **新增素材**,或在制品的 `## 复审 (Review)` 段**写署名**;然后跑**同一条** `bash scripts/ssdctl.sh advance <artifact> --to <状态>` | 人先在制品复审段写好署名(复审块非空时 `advance` **原样保留、永不覆盖**),再跑 `advance`;agent 与人用的是同一条命令 | `advance` 写出的复审块与人工预写的署名一致;`--actor` 只接受 `agent:<id>`(人工署名写在制品里,不走 `--actor`) |
| **R-5 留痕分流** | 转换留痕的唯一权威 = **制品本身(状态块 + 复审段)+ git 历史**;编排层的**叙事报告**(编排层工作区的 reports 目录)不作为验收证据 | lane 的叙事报告写编排层工作区;**验收只看**制品里的状态块 / 复审段与 git 历史 | `bash scripts/ssdctl.sh verify <artifact>` 读回该制品的状态块与复审段;任何门禁都不读编排层的报告目录 |
| **R-6 交互分层** | Lead(Coordinator)可对话;**执行 lane 静默**,只对 Lead 说话(`send_message` 给 Lead),不直接 `ask_user_question` | lane 需要澄清时把问题写进 workpad 并 `send_message` 给 Lead,由 Lead 决定是否问人 | lane 侧不出现对用户的提问;§1「你不与用户对话」约束的是**产制品那一轮**,不约束 Lead |
| **R-7 提交归人** | 交互式会话里 lane **不 commit**;提交 / 推送由人做。**swarm 侧对 git 写权限零规则 ⇒ brief 是唯一保险** | brief 必须写明「本轮不 commit / 不 push」;需要提交时把改动留在工作区,在汇报里列出路径 | 工作区改动**未提交**(§8「交互式会话里提交由人自己做」);§3 第 15 条的 git 边界不被越过 |
| **R-8 skill 双轨** | SDD 9 skill 管**怎么做制品**(§4 通用步骤第 2 步优先);swarm `swarm-craft-*` 管**怎么干活**;冲突时以 `WORKFLOW.md` 为准 | 做制品读 `.codex/skills/<name>/SKILL.md`;干活方法读 swarm 侧技能;两者冲突以本文件为准 | 产物形状按 §4 / §7 核对,不按通用模板核对;§1「参考资料可信度排序」以本文件最高 |
| **R-9 写集隔离** | 并行 lane **不得**写:`README.md` 统计块、`test_cases/_index.md` 索引块;也不得写**别人 issue 的制品**。`write_scopes` advisory,须由 Lead 在 brief 里点名排除 | brief 里点名两项禁写路径 + 别人的制品;lane 发现需要改这些 → **报告**,不改(§3 第 12 条) | 工作区改动清单里不出现这两类路径与别人的制品(§13.4 第 2 项) |

### 13.2 派发前置:唯一机器资格源 = 仓内 `ssdctl scan`

**编排层只负责并发与派工;资格判定只有一份实现** —— `scripts/lib/dispatch.py:262` 的 5 合取谓词:
`state_ok and not_deprecated and labels_ok and upstream_ready and layer_resolved`。
编排层**不得另造谓词**:另造谓词 = 第二个权威源(同一事实两个判据,必然分叉)。

> **Ready 闸门 = 编排层消费 `ssdctl scan` 的 dispatchable,不自造谓词。**
> 裁决 A-03(用户 m04017 已采纳;审计与裁决全文留在编排层,**不入本仓**):
> 编排层的门禁职责**只有一条** —— 把 `dispatchable=true` 的制品派出去;
> 「能不能进 `Ready`」由仓内 `advance` 按判据判定(§5),编排层**不参与判定**。
> 宿主侧不存在可复用的谓词实现(插件无进程执行能力),因此**编排层在结构上也无法**自行算出同等判据 ——
> 这不是设计缺陷,是「唯一权威源」的必然结果:**资格只看仓内 scan 的输出**。

**派发前必跑的命令**:

```bash
bash scripts/ssdctl.sh scan --json
```

**只取 `dispatchable=true` 的条目**,字段用法:

| `scan --json` 输出字段 | 含义 | 编排层怎么用 |
|---|---|---|
| `artifacts[].path` | 制品路径 = 权威身份(R-1) | 作为板任务 `artifact:` 的值 |
| `artifacts[].dispatchable` | **唯一入队条件**(`true` 才派) | `true` 才进派工集合;`false` 一律不派 |
| `artifacts[].layer` / `state` / `topic` | 层 / 当前状态 / topic | 写进 brief,让 lane 直接定位目标层与 topic(§2) |
| `artifacts[].upstream` / `missing` / `reason` | 上游、缺失项、不可派原因 | `dispatchable=false` 时把 `reason` 写进 brief,让 lane 知道先做什么 |
| `artifacts[].dependency_permission` | `blocked` / `draftable` / `committable` | 决定 lane 是「只起草」还是「可推进」(§7 的依赖许可轴) |

- **swarm 板不是资格源**:板上的 `ready` / `blockedBy` 是宿主字段透传,与 `upstream_ready` 无关(恒为真),**不得**作为入队条件。
- 上游层若要**机器强制**依赖登记,依赖点在宿主(板任务 `blockedBy`),**当前未证实**宿主按它算 ready ⇒ 本节只采信「可引用、不可强制」:资格一律以 scan 的结果为准。

### 13.3 板状态 ≠ 制品状态(降级映射)

板上的状态词、swarm 验收词表、SDD 制品状态**三套词表两两不相交**,不得互相翻译:

| 来源 | 词表 | 能否作为制品状态 |
|---|---|---|
| 板任务 `status` | 宿主字段,**无枚举** | ❌ 不能 |
| swarm 验收词表 | `met` / `not met` / `not demonstrated` / `not in scope` | ❌ 不能 |
| SDD 制品状态块 | `Draft` / `Ready` / `Implemented` / `Deprecated` | ✅ **唯一权威**(§5) |

**降级映射**(板信号 → 最多能触发的动作):

| 板上的信号 | 最多能触发 | 前置条件 |
|---|---|---|
| `completed` | `bash scripts/ssdctl.sh advance <artifact> --to Ready` | 判据全绿(`blocking:true` 全过);不绿就停在 `Draft` |
| `implemented` / `done` | **无** | `Implemented` 只能由 `bash scripts/ssdctl.sh advance <artifact> --to Implemented` 触发,且须带 `external:` 依据(`--external <ref>` 或制品正文里的 `external:` token) |
| `deprecated` | `advance <artifact> --to Deprecated` | 状态依据必须是 `external:`;**不允许** `criteria:`(§3 第 3 条) |
| `ready` / `blockedBy` | **不参与** | 宿主字段,与 `upstream_ready` 无关;资格只看 scan |

### 13.4 brief 必含项(Lead 派工时必须点名)

**`write_scopes` 是 advisory、不是锁** ⇒ **brief 是唯一保险**。下面 5 项缺一不可:

| # | brief 必含 | 写法(可直接抄) | 不写会怎样 |
|---|---|---|---|
| 1 | **权威身份 = 制品路径** | `artifact: prd/2026-11-22/layer-checklist.md`(板任务 `description` 同步写上) | lane 不知道改哪个 topic,可能改到别人的制品(§3 第 6 条) |
| 2 | **禁写清单(两项)** | 根 `README.md` 的 `<!-- prd-stats:begin -->` … `<!-- prd-stats:end -->` 统计块、`test_cases/_index.md` 的 `<!-- test-index:begin -->` … `<!-- test-index:end -->` 索引块 | 并行 lane 抢写机器写点 → 派生数据互相覆盖(§3 第 12 条) |
| 3 | **禁用 `swarm_worktree`** | 「本仓**不得**调用 `swarm_worktree`」 | worktree = 新分支 + 干净检出:算出的 `dispatchable` 基于另一快照,`advance` 写的状态块落在**不会合并**的分支上;且违反 §3 第 15 条(禁 `git checkout`) |
| 4 | **git 写权限** | 「本轮**不 commit、不 push**;提交由人做」 | lane 自造 `Reviewed-by:` 署名痕迹,或直接改主分支(§8、§3 第 7 / 15 条) |
| 5 | **人工接入形态** | 「人需要介入时:新增素材,或在制品的 `## 复审 (Review)` 段写署名,然后跑**同一条** `advance`」 | lane 以为有专属的人工通道,或手改状态行 = 违规(§3 第 2 条 / R-4) |

> 第 2 项的两个路径**逐字点名**,不要只写「别改自动生成块」—— 并行时 lane 只认得路径。
> 第 4 项与 §8「交互式会话里提交由人自己做」是同一条规则的两个说法:**交互式会话**里提交由人做;
> **本仓自主流水线**的工作区里,commit / push 只发生在 §3 第 15 条允许的专用分支上。两处都不得越界。

### 13.5 已知缺口(不掩饰)

- `dispatchable=false` 的制品**仍可被手写产出**:`dispatch.py` 是**谓词函数**,不是写拦截器。本节消掉的是「派发」这一半旁路;「写入」这一半需要仓内加写拦截,不在本节范围。
- 本节目前是**可引用、不可强制**:swarm 侧对 git 写权限与写集**零机器强制**;能被机器核对的只有仓内门禁(`bash scripts/ssdctl.sh gate`)、制品状态块与复审段。把上游层登记为板任务依赖能否机器强制,取决于宿主,**当前未证实** ⇒ brief 是唯一保险。
- **(历史)与已知代价**:2026-11-24 之前,仓内曾有 `control/` 控制平面(决定记录 / 状态快照 / 证据链),F9 裁决已整体删除。删除的代价是**机器不再能证明某个署名确系本人所写**(人工署名只以「复审段里有署名」的形式存在);这是「人与 agent 同一条流水线」的既定取舍(实施契约 R-11)。
- 板任务 `status` 无枚举、宿主板实现不可读 ⇒ 降级映射(§13.3)按**最保守**取:任何板信号都**不直接**改制品状态,只允许**触发一次 advance 尝试**。
