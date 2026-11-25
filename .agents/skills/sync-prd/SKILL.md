---
name: sync-prd
description: >-
  可选层 · PRD 台账同步 (v2.0)。L1 跑 scripts/sync-prd.py 做机械登记与统计 (确定性、幂等、无 LLM、无网络),
  L2 由 agent 读素材充实「待分析」行, L3 把「待抓取」行委派给项目自定义的外部来源 skill。
  Use when 项目启用了 material/ 素材区 + 批次台账, 需要巡检台账完整性、充实骨架行、或处理外部来源待抓取行。
  默认不启用; 台账状态列是派生索引 (由 ssdctl scan 从制品状态块生成), 状态权威在制品本身, 判定权归判据;
  本 skill 只改工作区文件, 不做 git 写操作, 不自造状态。
---

# sync-prd

维护**批次 PRD 台账**（`material/{YYYY-MM-DD}/PRDS.md`, 模板见 `schema/prd-ledger.md`）：L1 机械登记（确定性脚本）+ L2 智能充实（agent）+ L3 外部来源抓取委派。

> **本 skill 是可选层, 默认关闭**。只有在项目**显式启用** `material/` 素材区 + 批次台账机制时才使用。5 步主流程（PRD → Tech Design → Plan → TDD → Layer 4）不依赖本 skill。

## 执行阶段 (内部 phase 标识)

agent 按下列 phase 顺序推进。每个 phase 开始时在汇报里写明 `phase: <name>`。

> phase 是 agent 的**内部工作分段**, 不依赖任何 UI 模式指示器, 也不假设运行环境会显示模式。

| Phase | agent 做什么 |
|-------|--------------|
| `scanning` | 跑 `scripts/sync-prd.py`（L1）：机械登记 + 刷新 README 统计块 + 输出哨兵清单 |
| `analyzing` | 读素材原文, 充实「待分析」行的 `优先级` / `验收要点` / `提出人` |
| `delegating` | 把「待抓取」行委派给**项目自定义的外部来源 skill**, 回填 `创建时间` |
| `reporting` | 输出统计与待办报告 |

## When to Use

- 项目启用了 `material/` 素材区, 新批次素材落盘后核对台账完整性
- 台账存在「待分析」哨兵（`优先级=待定` 或 `提出人=[待补]`）
- 台账存在「待抓取」哨兵（`来源=external` 且有 URL 但 `创建时间` 为空）
- 周期巡检: 核对素材区与台账是否一致
- 人工登记了新的外部来源 URL, 需要把内容抓取落盘

> **不适用**: 项目没有启用 `material/` + 台账时, 本 skill 无事可做, 直接跳过。

## 调用输入

| 输入 | 必填 | 说明 |
|------|------|------|
| 批次日期 | 否 | `YYYY-MM-DD`; 省略则巡检所有已启用批次 |

示例: 巡检 2026-08-05 批次的 PRD 台账。

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| L1 脚本 | `scripts/sync-prd.py` | 机械登记 + 统计（幂等, 退出码表达待办）; 台账状态列是**派生索引**, 由 `bash scripts/ssdctl.sh scan` 生成 |
| 台账模板 | `schema/prd-ledger.md` | 台账 11 列定义 + 哨兵定义 |
| 素材区 | `material/{YYYY-MM-DD}/` | Layer 0 只读素材来源 |
| 关联矩阵 | 根 `README.md`「PRD关联矩阵」章节 | 关系边提议的比对基准 |
| 外部来源 skill | **项目自定义** | 抓取 `来源=external` 的 URL。**模板不内置任何抓取器** |
| 工作目录 | 仓根目录 | 脚本假设此位置 |

## Core Concept

### 台账 11 列

台账表格的列顺序与名称**严格统一**, 校验脚本按此格式抓取值（定义见 `schema/prd-ledger.md`）。

| # | 列 | 取值 |
|---|-----|------|
| 1 | `#` | 序号 (1-based) |
| 2 | `ID` | `{前缀}-{YYYYMMDD}-{NN}` |
| 3 | `PRD 名称` | 一句话主题 |
| 4 | `优先级` | `P0` / `P1` / `P2` / `待定` |
| 5 | `验收要点` | 1-2 句话核心验收标准 |
| 6 | `状态` | `待分析` / `Draft` / `Ready` / `Implemented` / `Deprecated` | **派生索引**: 值从制品状态块生成, 权威在制品本身 |
| 7 | `来源` | `local` / `external` / `internal` |
| 8 | `关联素材` | 仓内路径 或 仓外 URL |
| 9 | `创建时间` | `YYYY-MM-DD` |
| 10 | `更新时间` | `YYYY-MM-DD` |
| 11 | `提出人` | 登记人 handle, 未识别时 `[待补]` |

> **`来源` 枚举只有 3 个**: `local`（本地素材）/ `external`（外部来源, URL）/ `internal`（内部转写）。不引入任何具体外部平台名。

### ID 前缀路由 (4 个)

素材 ID 前缀决定流水线入口:

| 前缀 | 流水线入口 |
|------|-----------|
| `PRD-` | `.agents/skills/to-prd/SKILL.md` |
| `TECH-` | `.agents/skills/to-tech-design/SKILL.md` |
| `TEST-` | `.agents/skills/to-test-cases/SKILL.md` |
| `PLAN-` | `.agents/skills/to-plan/SKILL.md` |

### 哨兵定义

| 哨兵 | 判定条件 | 处置 | 归属 phase |
|------|----------|------|------------|
| **待分析** | `优先级=待定` 或 `提出人=[待补]` | agent 读素材原文充实行 | `analyzing` |
| **待抓取** | `来源=external` 且有 URL 但 `创建时间` 为空 | 委派给项目自定义外部来源 skill | `delegating` |

### 职责边界

| 做 | 不做 |
|----|------|
| L1 骨架行补登记（台账只增, 直写）| 收敛产出 PRD（那是 `.agents/skills/to-prd/SKILL.md` 的职责）|
| 充实待分析行的 `优先级` / `验收要点` / `提出人` | 改动已充实的历史行 |
| 关系边**提议**（写入前需确认）| 未经确认直写 README 矩阵 |
| 委派外部抓取 + 回填 `创建时间` | 修改素材原文内容 |
| 统计汇报 | 任何 git 写操作 |
| 台账状态列按 `ssdctl scan` 派生再生 | 手改台账状态列 |

## Execution Steps

### 1. Scanning Phase (L1, 机械部分)

```bash
# 在仓根目录执行
PY="$(bash scripts/ssdctl.sh --python)"
LC_ALL=C.UTF-8 "$PY" scripts/sync-prd.py
```

| 项 | 约定 |
|----|------|
| 性质 | **确定性脚本**: 幂等, 无 LLM, 无网络 |
| 作用 1 | 机械补登记骨架行（台账只增）|
| 作用 2 | 重写根 `README.md` 的统计块（`<!-- prd-stats:begin -->` 与 `<!-- prd-stats:end -->` 之间; 标记外的内容永不触碰）|
| 作用 3 | 输出哨兵清单（待分析 / 待抓取 / 孤儿行）|
| 退出码 0 | 无待办 |
| 退出码 1 | 存在待分析 / 待抓取 / 孤儿行 |
| 退出码 2 | 环境错误（无法正常工作）|

> **也可写成 `"$PY" scripts/sync-prd.py`**（与 `material/README.md` 的快速命令一致）。

收集脚本输出里的哨兵清单, 作为后续 phase 的输入。

> **幂等**: 重复跑同一批次, 结果一致, 不产生重复行。

### 2. Analyzing Phase (L2, agent 部分)

对每个「待分析」哨兵行:

1. 读该行「关联素材」指向的素材原文（`来源=local` 读仓内路径; `来源=internal` 读内部转写件）。
2. 填三列:
   - `优先级`: `P0`（核心）/ `P1`（重要）/ `P2`（辅助）, 按业务影响判断;
   - `验收要点`: 一句话可验证标准;
   - `提出人`: 从原文识别登记人; **无法识别就保持 `[待补]` 并在报告点名**, 不要编造。
3. 查根 `README.md`「PRD关联矩阵」的关系边表, 判断该需求与既有 PRD 是否存在关系。关系类型取 8 类枚举: `supersede` / `inherit` / `depend` / `shared` / `conflict` / `relate` / `split-from` / `merge-into`（见 `schema/prd-matrix.md`）。
4. 有发现 → 生成**关系边提议**（节点 A / 关系 / 节点 B / 证据）, 列入报告; **经人工或调用方确认后**才写入 README 矩阵。

### 3. Delegating Phase (外部来源抓取委派)

对每个「待抓取」哨兵行（`来源=external` 且有 URL 但 `创建时间` 为空）:

1. **模板不内置任何外部抓取器**。项目必须自己提供一个外部来源 skill（由项目维护者编写, 可能依赖该项目的外部平台凭据与网络可达性）。
2. 委派方式: 把该行的 URL 交给项目自定义 skill, 由它把内容落盘到 `material/{date}/` 下, 并回报落盘路径。
3. 抓取成功 → 回填台账该行 `创建时间`（`YYYY-MM-DD`）, 并把落盘路径追加进「关联素材」列。
4. 抓取失败 → `创建时间` **保持空**（哨兵保留）, 在报告里点名该行与失败原因。

> **没有项目自定义 skill 时的处理**: 跳过抓取, 在报告里把所有「待抓取」行标为「待抓取-环境未就绪（项目未提供外部来源 skill）」。**不要**自己写一次性抓取脚本, **不要**把任何具体外部平台名写进本 skill。

对已抓取行的周期复抓:

1. 重新抓取, 与本地快照基线比对。
2. **内容有变化** → 覆盖素材快照 + 回填 `更新时间`（`创建时间` 不动）; 若该行状态已是 `Ready` 或更后, 在报告里输出下游重审信号「外部源已变更, 关联 PRD 需重审」（是否修订 PRD 按跨层协调规则走, 本 skill 不改 PRD）。
3. **无变化** → 不动台账。

### 4. Reporting Phase

```markdown
# PRD 台账同步报告 {YYYY-MM-DD}

## 统计
批次覆盖 / 素材数 / 台账行数 / 本次补登记 / 来源分布 (local/external/internal)

## 待办
- 待分析清单 (PRD-ID + 批次)
- 待抓取清单 (PRD-ID + URL + 失败原因)
- 孤儿行清单
- 外部源更新 → 下游重审信号 (PRD-ID + 关联 PRD)

## 关系边提议（待确认）
| 节点 A | 关系 | 节点 B | 证据 |
```

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 跳过 L1 直接手工补行 | 先跑脚本, 机械部分交给确定性代码 |
| 跳过脚本手工改 README 统计块 | 统计块由 `scripts/sync-prd.py` 幂等再生 |
| 直写关系边进 README | 先提议, 确认后写入 |
| 复抓无变化也回填更新时间 | 只有内容变化才回填 |
| 把待抓取行的空创建时间手工填上 | `创建时间` 只由抓取成功事件回填 |
| 为凑 `提出人` 编造 handle | 识别不到就保持 `[待补]` 并点名 |
| 收敛台账行 / 产出 PRD | 那是 `.agents/skills/to-prd/SKILL.md` 的职责 |
| 在本 skill 里写死某个外部平台的抓取逻辑 | 外部抓取交给**项目自定义 skill**; 模板零外部工具依赖 |
| 用模板外的来源值（如具体平台名）| `来源` 只有 `local` / `external` / `internal` |
| 跑 git commit/push | 本 skill 只改工作区文件; 提交动作由人执行 (见 `.agents/skills/commit/SKILL.md`) |
| 把台账行状态改成 `Ready` / `Implemented` | 台账状态列是派生索引, 由 `ssdctl scan` 从制品状态块生成; 判定权归判据, 不在本 skill |

## 禁止行为 (Agent 权限边界)

| ❌ Don't | ✅ Do |
|----------|-------|
| 自行 `git commit` / `git push` / 切换或创建分支 | 只改工作区文件; git 写操作由人执行 (见 `.agents/skills/commit/SKILL.md`) |
| 手改台账状态列 | 台账状态列是派生索引, 由 `ssdctl scan` 再生 |
| 编造 `提出人` handle / URL / 抓取结果 | 识别不到就保持 `[待补]` 并点名 |
| 修改 `schema/**` 下的模板 | 只读 `schema/prd-ledger.md` / `schema/prd-matrix.md` |
| 静默覆盖台账历史行 | 只增不改; 冲突登记待人工裁决 |
| 留下 `{...}` 占位符 | 填真实值, 不适用就删整行 |

## Verification

- `"$PY" scripts/sync-prd.py` 退出码为 0, 或退出码 1 且报告中已列出全部待办行
- 台账表格列数 = 11, 列名与 `schema/prd-ledger.md` 一致
- 所有 `ID` 匹配 4 个前缀之一: `PRD-` / `TECH-` / `TEST-` / `PLAN-`
- 所有 `来源` 值 ∈ {`local`, `external`, `internal`}
- 无「待分析」哨兵残留（`优先级=待定` 或 `提出人=[待补]` 的行已处理或已点名）
- 「待抓取」行要么 `创建时间` 已回填, 要么已在报告中标为环境未就绪
- README 统计块在标记之间, 标记外内容未被触碰
- 台账状态列与 `bash scripts/ssdctl.sh scan --check` 的派生结果一致（无手写漂移）

## Examples

### 日常巡检

```
User: 巡检 2026-08-05 批次的 PRD 台账
Agent: phase: scanning
Agent: L1: 批次 2026-08-05 补登记 2 行 (1 local / 1 external), 待分析 2、待抓取 1
Agent: phase: analyzing
Agent: PRD-20260805-01 充实: P1 / 验收要点「限流触发时返回 429 并带 Retry-After」/ 提出人 [某 handle]
Agent: 关系边提议: PRD-20260805-01 inherit prd/2026-07-10/legacy-feature.md (证据: 沿用同一限流组件)
Agent: phase: delegating
Agent: 待抓取行 PRD-20260805-02: 委派项目自定义外部来源 skill → 落盘 material/2026-08-05/02-xxx.md
Agent: 回填 创建时间 2026-08-05
Agent: phase: reporting
Agent: 报告输出: 补登记 2 / 关系边提议 1 条待确认
```

### 无外部来源 skill（环境未就绪）

```
Agent: phase: delegating
Agent: 待抓取行 PRD-20260805-02: 项目未提供外部来源 skill, 跳过抓取
Agent: 报告标记: 待抓取-环境未就绪 (项目未提供外部来源 skill)
Agent: 创建时间保持空, 哨兵保留
```

## 安装 (Installation)

skill 定义随仓库分发, agent 直接读 `.agents/skills/sync-prd/SKILL.md` 即可, **无需注册**。

需要把 skill 装进宿主 agent 的 skills 根目录时, 用仓内安装脚本：

```bash
bash <repo>/.agents/skills/install.sh                     # 默认 ~/.codex/skills/
bash <repo>/.agents/skills/install.sh --target <dir>      # 指定目标
bash <repo>/.agents/skills/install.sh --unregister        # 注销
```

## Related Skills

- `.agents/skills/to-prd/SKILL.md`：收敛产出 PRD（消费台账, 登记关系边）
- `.agents/skills/to-tech-design/SKILL.md` / `.agents/skills/to-plan/SKILL.md` / `.agents/skills/to-test-cases/SKILL.md`：按 ID 前缀路由的其他流水线入口
- `.agents/skills/sync-status/SKILL.md`：四层生命周期编排（状态流转与级联; 状态行由 `ssdctl advance` 写）
- `.agents/skills/validate-spec/SKILL.md`：校验链（判据与门禁走 `ssdctl.py`; 台账 / 矩阵一致性检查按产物存在与否条件启用）

## Cross-References

- <repo>/schema/prd-ledger.md（台账 11 列 + 哨兵定义 + ID 前缀）
- <repo>/schema/prd-matrix.md（8 类关系枚举, 关系边提议的取值范围）
- <repo>/material/README.md（素材区与台账层说明）
- <repo>/scripts/sync-prd.py（L1 机械登记 + 统计）
- <repo>/README.md「PRD关联矩阵」（关系边实例）
- <repo>/AGENTS.md §3.7（skill 清单与调用入口）
