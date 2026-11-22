---
name: to-tech-design
description: >-
  PRD → Tech Design 转换流程 (v2.1)。默认 v4 四子文件 (README 综合描述 + ards 架构决策与方案对比 + apis 接口契约与时序 + data-model ER 图);
  v3 六子文件为存量格式, 需显式 opt-in 才产出。Use when 收到上游 PRD 已达 Ready, 需要产出 Tech Design (默认 v4, 4 子文件)。
  agent 自主推进: 判据全绿即由 agent 起草复审自评并用 ssdctl advance 推到 Ready; 人工可选复核并落决定记录。
---

# to-tech-design

将 `prd/{date}/{topic}.md`（Ready 状态, 无 `-processed` 后缀）转换为 `tech_design/{date}-{topic}/`.

## 代际选择 (默认 v4, v3 显式 opt-in / 仅存量)

| 形态 | 子文件 | 模板来源 | 适用场景 |
|------|--------|----------|----------|
| **v4** (默认) | README 综合描述 + **ards** 架构决策+方案对比+探索深度声明+OQ/Spikes/Pivot+Gap 对比 + **apis** 接口契约+时序图 (SYS/MOD) + data-model ER 图 | `schema/tech_design/` | 新建 Tech Design 的默认形态 |
| **v3** (存量, 显式 opt-in) | README + decisions + data-model + api-contracts + scenario-mapping + quality (+ interactions 条件) | `schema/tech_design/v3/` | 仅当项目已有存量 v3 TD, 需要按 v3 增量补 TD |

> **默认代际 = v4**。新建 Tech Design 一律走 v4 四子文件, 不需要显式声明代际。
> **v3 是存量兼容路径**: 模板已移入 `schema/tech_design/v3/`, 只在明确要求「按 v3 产出」时才走 v3 分支。
> **代际识别**: 门禁引擎按 `ards.md` / `apis.md` 是否存在自动判定 v4 (双模式). v3 → v4 不强制迁移, 存量 v3 目录保留原样。

## 执行阶段 (内部 phase 标识)

agent 按下列 phase 顺序推进。每个 phase 开始时在汇报里写明 `phase: <name>`, 便于人工追溯。

> phase 是 agent 的**内部工作分段**, 不依赖任何 UI 模式指示器, 也不假设运行环境会显示模式。

| Phase | agent 做什么 |
|-------|--------------|
| `reading` | 读 PRD + schema 子文件模板 (默认 v4 4 个; v3 显式 opt-in 时读 `schema/tech_design/v3/`) |
| `structuring` | 设计子文件内容骨架 (默认 v4: README 场景映射 + ards + apis + data-model) |
| `injecting-context` | 从 `AGENTS.md` §1 读多仓关系, 决定跨仓引用前缀 |
| `writing` | 写子文件到 `tech_design/{date}-{topic}/` (默认 v4 4 个; v3 opt-in 时 6 个 + 条件 interactions), 状态块写 `Draft` |
| `validating` | 跑 `bash scripts/ssdctl.sh criteria tech_design/{date}-{topic}/README.md` 逐条判定并汇报退出码 |
| `advancing` | 判据全绿则 `bash scripts/ssdctl.sh advance tech_design/{date}-{topic}/README.md --to Ready` 代写状态块与复审块 |

## When to Use

- 收到已就绪的 PRD (上游 PRD 状态为 `Ready`, 由 `ssdctl advance` 按判据推进)
- 需要产出符合 **v4 四子文件**结构的 Tech Design（默认形态, 无需声明代际）
- 存量项目明确要求按 v3 格式增量补 TD（显式 opt-in）
- 需要自动注入多仓上下文

## 调用输入

| 输入 | 必填 | 说明 |
|------|------|------|
| PRD 路径 | 是 | `prd/{YYYY-MM-DD}/{topic}.md`; 传目录表示批量处理整个分桶 |

示例: 用 `prd/2026-07-03/login.md` 产出一份 Tech Design; 或用 `prd/2026-07-03/` 批量处理。

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| PRD 状态 | Ready | 前置条件 (上游 PRD 状态为 `Ready`; 由 `ssdctl advance` 按判据推进) |
| Schema 模板 (默认 v4) | `schema/tech_design/{README,ards,apis,data-model}.md` | v4 四子文件模板 |
| Schema 模板 (v3 opt-in) | `schema/tech_design/v3/*.md` | v3 存量模板, 仅显式 opt-in 时读 |
| AGENTS.md | §1 仓库清单 + §1.2 跨仓引用约定 + §1.6 实现基线约定 | 多仓上下文 + 基线口径 |
| 判据与门禁 | `scripts/ssdctl.py` | 唯一入口: `criteria` 逐条判定 + `gate` 全仓（v4 / v3 双模式）|
| Code 仓 | §1.1 登记的 code 仓 | 跨仓引用前缀 + 实现基线核对 |

## Core Concept

### 子文件职责 (按所选代际)

#### v4 模式 (默认)

| 子文件 | 必填 | 关注点 |
|--------|------|--------|
| README.md | ✓ | 综合描述 + Context (现状边界 / 硬约束 / 软约束) + `## 场景映射` 段 (6 列表, 覆盖所有 Given/When/Then) + 质量保证 + 关联验证用例 (V 预分配) + `## 实现基线` 段 (§1.6) |
| ards.md | ✓ | 探索深度声明 + 方向选择总表 + Solution Space 候选方案对比 (≥2) + **KD-{n}** (Context/Decision/Alternatives/Rationale/Enforced by) + Open Questions/Spikes/Pivot Triggers + 现状 Gap 表 + 风险缓解 |
| apis.md | ✓ | 接口契约 (全响应变体) + 枚举速查 + 组装规则 + 时序图 (SYS-{n} 系统级 / MOD-{n} 模块级) |
| data-model.md | ✓ | ER 图 (`erDiagram`) + 数据结构明细; 无数据模型变更时必须显式声明 |

> **v4 不需要** decisions.md / api-contracts.md / scenario-mapping.md / quality.md / interactions.md。这 5 个文件的内容已合并进 v4 四子文件。
> **v4 识别标志**: 目录内存在 `ards.md` 或 `apis.md`。校验脚本据此走 v4 分支。

#### v3 模式 (存量, 显式 opt-in)

| 子文件 | 必填 | 关注点 |
|--------|------|--------|
| README.md | ✓ | 入口/索引, 摘要 + 子文件导航 |
| decisions.md | ✓ | KD-{n}（Context/Decision/Alternatives/Rationale/Enforced by）|
| data-model.md | ✓ | 实体/字段/约束, 关联场景 |
| api-contracts.md | ✓ | 端点 + 请求/响应 + 错误码 |
| scenario-mapping.md | ✓ | PRD 场景 → 实现路径（覆盖所有 Given/When/Then）|
| interactions.md | 条件 | 系统级/模块级 mermaid sequence diagram |
| quality.md | ✓ | 指标 + 降级 + 错误处理 |

> v3 模板来源为 `schema/tech_design/v3/`。写存量 v3 TD 时从该目录取模板, 不要从 `schema/tech_design/` 顶层取（顶层是 v4）。

### 何时需要 interactions.md (仅 v3 适用)

满足**任一**条件时必填：

- 场景映射表行数 ≥ 5
- 涉及外部接口调用
- 涉及 ≥ 2 个内部模块协作
- 包含异步流程 / 状态机 / 重试逻辑

否则可在 README.md 显式标注"不适用"跳过。

> v4 模式下时序图直接写在 `apis.md` 的 SYS-{n} / MOD-{n} 段, 不需要独立 interactions.md。

### 实现基线段 (v4 README.md)

v4 的 `README.md` 含 `## 实现基线` 段, 固定 6 列（仓库 / 分支 / SHA / 核对日期 / 核对项 / 状态）, 口径见 AGENTS.md §1.6:

| 项 | 规则 |
|----|------|
| 仓库列 | 填 §1.1 登记的**标识**, 不写仓库目录名 |
| 状态列 | `✓` 一致 / `⚠` 不一致或未登记 / `○` 不适用或跳过 |
| 0 代码仓项目 | 写单行 `> 不适用: 本项目无关联代码仓` 即可, 校验按 `○` 跳过 |
| 证据锚点 | 现状结论引代码位置时用 `{标识}@{短SHA}:{路径}#L{行号}` 格式（§1.7）|

### 多仓上下文注入

从 `AGENTS.md §1` 自动读：

| 注入内容 | 用途 |
|----------|------|
| §1.1 仓库清单 | 决定 Change 涉及的仓库 + 实现基线表的仓库标识 |
| §1.2 跨仓引用约定 | 跨仓引用必须带前缀 |
| §1.3 代码仓 AGENTS 索引 | 跨仓引用时给出 AGENTS 路径 |

## 状态推进边界 (agent 主导, 人工可选手动介入)

| 动作 | 责任方 | 说明 |
|------|--------|------|
| 写 Tech Design, 状态块写 `Draft` | agent | 产出文件本身的状态块 (`状态` / `状态主体` / `状态时间` / `状态依据` 4 行; Draft 态后三行允许缺省) |
| 起草 `## 复审 (Review)` 的 `评审人` / `评审日期` / `评审结论` / `评审方式` 四行 | agent | agent 自评: `评审人` 写 `agent:<id>`, `评审方式` 写 `自动判据`; **agent 绝不写 `human:` 前缀, 也不代填人名** |
| 把状态翻成 `Ready` | agent (判据驱动) | 该层 `blocking:true` 判据全绿 + 上游 `upstream_ready`, 由 `bash scripts/ssdctl.sh advance` 代写状态块与复审块 |
| 把状态翻成 `Implemented` | agent (外部事实) | 需 `external:` 依据或 `--decision` 指定的外部事实介入记录; PRD / Tech Design / Plan 三件套必须同时推进 |
| 把状态改成 `Deprecated` | agent 或人工 | 需 `decision:` 或 `external:` 依据 (不允许 `criteria:`); 上游 PRD 已 Deprecated 之后的机械级联由 agent 执行 |

- **判定权归判据, 写入权归 agent, 人工可手动介入**: 判据全绿就推进, 人工要改结果就落一条 `control/decisions/` 决定记录, 再用 `--decision` 传入。
- **状态块永远由 `ssdctl advance` 写**; skill 与 agent 都不手改状态行, 也不教人手改。
- **agent 的状态上限是 `Ready`**; `Implemented` 仍需外部事实证据, 不靠 agent 自述。

## 禁止行为 (Agent 权限边界)

| ❌ agent 不做 | ✅ agent 改做 |
|--------------|--------------|
| 自行 `git commit` / `git push` / `git add` / 切换或创建分支 | 只改工作区文件; git 写操作由人执行 (见 `.codex/skills/commit/SKILL.md`) |
| 手改状态行 / 状态块 4 行 | 一律走 `bash scripts/ssdctl.sh advance` |
| 在复审块写 `human:` 前缀或代填人名 | 写 `agent:<id>`; `human:` 前缀**只能由人自己填**, agent 不得代填 |
| 伪造 `Reviewed-by:` / SHA / 行号 / handle / 外部依据 | 拿不准就不写; 无法核对时明确标注「未核对」 |
| 改 `schema/**` 下的模板 | 模板是契约, 只读; 发现模板与实现不一致时报告, 不自行修改 |
| 静默覆盖冲突 (两份素材对同一设计描述不一致) | 两份都保留, 登记冲突并报告人工裁决 |
| 留下模板占位符 (`KD-1` / `YYYY-MM-DD` / `TBD`) | 填真实值; 确实无法确定时**删掉整行**而不是留占位符 |

## Execution Steps

### 1. Reading Phase

```bash
# 读 PRD
cat "$PRD_PATH"

# 读 schema 子文件模板 (默认 v4: 4 个)
for f in README ards apis data-model; do
  cat "schema/tech_design/$f.md"
done

# 仅当明确要求 v3 时, 才读存量模板 (v3 显式 opt-in)
# for f in README decisions data-model api-contracts scenario-mapping quality interactions; do
#   [[ -f "schema/tech_design/v3/$f.md" ]] && cat "schema/tech_design/v3/$f.md"
# done

# 读 AGENTS.md §1 (仓库清单 / 跨仓引用 / 实现基线)
sed -n '/^## 1\. /,/^## 2\. /p' AGENTS.md
```

### 2. Structuring Phase

按"Core Concept → 子文件职责 (按所选代际)"设计每个子文件内容骨架：

**v4 模式（默认）**:
1. **README.md**：综合描述 + Context（现状边界 / 硬约束 / 软约束）+ `## 场景映射` 6 列表（覆盖 PRD 所有 Given/When/Then）+ 质量保证 + `## 实现基线` 段
2. **ards.md**：每个设计选择 → KD-{n} 段（5 段结构 + Solution Space 候选 ≥2 + Spikes/Pivot + Gap 表）
3. **apis.md**：每个接口契约（全响应变体）+ 时序图（系统级 SYS-{n} / 模块级 MOD-{n}）
4. **data-model.md**：ER 图 + 实体字段约束（无变更则显式声明）

**v3 模式（存量, 显式 opt-in）**:
1. **识别 KD**：PRD 中存在 ≥2 方案的设计选择 → 必须记录为 KD
2. **数据模型**：列出实体 + 字段 + 约束
3. **API 契约**：每个端点 + 请求/响应
4. **场景映射**：PRD 每个 Given/When/Then 必出现在映射表
5. **时序图**（条件）：如满足触发条件
6. **质量保证**：具体数字指标 + 降级策略 + 错误处理

### 3. Injecting-Context Phase

从 AGENTS.md §1 解析：

```
仓库清单: [B, C]           # 取 §1.1「标识」列, 不取目录名
引用前缀: B/, C/           # 按 §1.2 的 {标识}/{path} 格式
关联 AGENTS: ../<repo-b>/AGENTS.md, ../<repo-c>/AGENTS.md
```

把所有跨仓引用按 §1.2 格式化：

```markdown
# 错 ❌
app/services/auth.ts
api/facade/read/LoginServiceClient.java
B 仓库

# 对 ✅
B/app/services/auth.ts
C/api/facade/read/LoginServiceClient.java
B (从 §1.1 仓库清单)
```

### 4. Writing Phase

```bash
td_dir="tech_design/{date}-{topic}/"
mkdir -p "$td_dir"

# v4 模式 (默认): 写 4 子文件
if [[ "$mode" == "v4" ]]; then
  for sub in README ards apis data-model; do
    echo "$content_for_$sub" > "$td_dir/$sub.md"
  done
  # README 必须含 `## 场景映射` 段 (6 列表) + `## 实现基线` 段
  # ards 必须含 `## KD-{n}:` 段
  # apis 必须含接口契约段 + 时序图 (SYS/MOD)
  # data-model 必须含 erDiagram 或「无数据模型变更」显式声明
fi

# v3 模式 (存量, 显式 opt-in): 写 6 必填子文件 (+ 条件 interactions)
if [[ "$mode" == "v3" ]]; then
  for sub in README decisions data-model api-contracts scenario-mapping quality; do
    echo "$content_for_$sub" > "$td_dir/$sub.md"
  done
  if needs_interactions; then
    echo "$interactions_content" > "$td_dir/interactions.md"
  fi
fi
```

**TD 状态块与稳定 ID**（Writing Phase 收尾）:
- 状态块 4 行写 `> **状态**: Draft`（后三行 `状态主体` / `状态时间` / `状态依据` 可缺省）; **状态行只由 `bash scripts/ssdctl.sh advance` 代写**。
- 复审块 4 行由 agent 起草自评: `评审人` 写 `agent:<id>`, `评审方式` 写 `自动判据`; **agent 绝不写 `human:` 前缀, 也不代填人名**。
- 每条架构决策写 `- KD-{n} {决策名}`, 供 Plan 的 Change 与 V 用例双向引用。

### 5. Validating Phase

```bash
# 判据逐条判定 (Tech Design 层)
bash scripts/ssdctl.sh criteria tech_design/{date}-{topic}/README.md

# 全仓门禁 (含派生数据再生)
bash scripts/ssdctl.sh gate
```

要求: 双模式自动识别（目录内有 `ards.md` 或 `apis.md` → v4 校验 4 子文件；否则 → v3 校验 6 子文件 + 条件 interactions.md）; 退出码 0 = 判据全绿, 1 = 有不通过项（逐条列出）, 2 = 用法错误。

复审块的判定是**阶段感知**的: `Draft` 阶段只要段存在即通过（签署行残留占位符只报 ⚠）; `Ready` / `Implemented` 阶段额外要求评审日期为 `YYYY-MM-DD` 且评审人非空。agent 产出时是 `Draft`, 推进到 `Ready` 由 `ssdctl advance` 在判据全绿后代写复审块。

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 新建 TD 用 v3 六子文件 | 默认 v4 四子文件; v3 仅存量显式 opt-in |
| 从 `schema/tech_design/` 顶层取 v3 模板 | v3 模板在 `schema/tech_design/v3/` |
| 省略 README.md | 必填，作为入口索引 |
| KD 缺 5 段（Context/Decision/Alternatives/Rationale/Enforced by）| KD 必须完整 5 段 |
| KD 只有 1 个备选方案 | 至少 2 个备选方案 |
| 场景映射表漏 PRD 场景 | 全部 PRD Given/When/Then 必出现 |
| v4 目录里额外塞 decisions.md / interactions.md | v4 内容合并进四子文件, 不额外造文件 |
| 指标用模糊描述（"响应要快"）| 具体数字（P99 < 500ms）|
| 外部接口无降级策略 | 每个外部调用必须有降级 |
| 跨仓引用用裸路径（`app/services/auth.ts`）| 带仓库前缀（`B/app/services/auth.ts`）|
| 跨仓引用口语化（"B 仓库"）| 用 §1.1 仓库清单的标识 |
| 手改状态行 / 状态块 4 行 | 一律走 `bash scripts/ssdctl.sh advance` |
| 在复审块写 `human:` 前缀或代填人名 | 写 `agent:<id>`; `human:` 前缀**只能由人自己填**, agent 不得代填 |
| 把数据用 `string` 泛指 | 用 TS / SQL / JSON Schema 具体类型 |
| 错误码用 `4xx` 泛指 | 用具体值（`400` / `401` / `403`）|

## Troubleshooting

### Q1：字段判据 报"缺少必填子文件"

**症状**：报缺 README.md / ards.md / apis.md / data-model.md（v4）或 README.md / decisions.md 等（v3）

**排查**：
```bash
ls tech_design/{date}-{topic}/
```

**处理**：先确认目录属于哪一代。目录内有 `ards.md` 或 `apis.md` → v4, 补齐 4 个必填子文件（README + ards + apis + data-model）。否则 → v3, 补齐 6 个必填子文件（README + decisions + data-model + api-contracts + scenario-mapping + quality）。

### Q2：追溯判据 报"引用 KD-N 但不存在"

**症状**：README.md 的"跨文件引用对账"段引用 KD-3, 但决策文件没有 `## KD-3:`

**排查**：
```bash
grep "^## KD-" tech_design/{date}-{topic}/ards.md          # v4
grep "^## KD-" tech_design/{date}-{topic}/decisions.md      # v3 存量
```

**处理**：在对应代的决策文件补 `## KD-3: ...` 段，或从 README 删除 KD-3 引用。

### Q3：字段判据 报"缺少 interactions.md 且 README 未声明跳过"

**症状**：README 没标注 interactions.md 跳过

**适用范围**：仅 v3。v4 不需要 interactions.md。

**处理（条件满足）**：写 interactions.md（系统级 + 模块级 mermaid sequence diagram）。

**处理（条件不满足）**：在 README 的"何时需要 interactions.md"段标注：
```
- [ ] (不适用) interactions.md,场景映射 < 5 行,无外部接口调用
```

### Q4：子文件内容不连贯

**症状**：data-model.md 的实体名与 apis.md（或 v3 的 api-contracts.md）的字段名不一致

**原因**：分步写子文件时，跨文件命名漂移（v4 4 个 / v3 6 个都易犯）

**处理**：用"命名表"（统一术语表）作为写之前的强制步骤：

```markdown
| 术语 | data-model.md 写法 | apis.md 写法 |
|------|---------------------|-------------|
| 实体A | EntityAlpha | entityAlpha |
| 实体B | EntityBeta | entityBeta |
```

### Q5：跨仓引用没自动带前缀

**症状**：接口文件写 `app/services/auth.ts`，应写 `B/app/services/auth.ts`（对应 §1.1 B 行的本地路径）

**排查**：检查是否读 AGENTS.md §1（injecting-context phase）

**处理**：确保 to-tech-design 的 injecting-context phase 正确解析 §1.1 仓库清单。

### Q6：v4 目录被校验脚本判成 v3

**症状**：v4 四子文件齐全, 但脚本仍按 v3 要求补 decisions.md

**原因**：v4 识别靠 `ards.md` 或 `apis.md` 存在, 两者都没写出来时会被误判。

**处理**：确认 `ards.md` / `apis.md` 已落盘到 `tech_design/{date}-{topic}/`, 再重跑校验。

## Tips

- **默认就是 v4**：新 TD 不需要声明代际, 直接按四子文件写
- **v3 只在存量场景用**：模板在 `schema/tech_design/v3/`, 写之前先确认目录代际
- **KD 是核心**：≥2 方案的设计选择必须记录 KD，不可跳过
- **场景映射完整性**：PRD 每个 Given/When/Then 必出现，否则 Plan 验证用例会缺
- **指标具体数字**：`P99 < 500ms` ✓，`响应快` ✗
- **降级策略覆盖**：每个外部接口都有降级（触发条件 + 行为 + 影响）
- **多仓项目**：跨仓引用从 §1.1 读标识前缀，不要硬编码目录名
- **实现基线**：有 code 仓时在 README 的 `## 实现基线` 段核对分支/SHA, 0 code 仓写「不适用」
- **现状结论带锚点**：引用代码现状时用 `{标识}@{短SHA}:{路径}#L{行号}`（§1.7）
- **interactions.md 条件触发**（仅 v3）：不强制创建，README 显式声明跳过即可
- **Tech Design 状态**：状态块 4 行由 `ssdctl advance` 代写; agent 产出时是 `Draft`, 判据全绿即推进到 `Ready`

## Examples

### Simple (默认 v4)

```
User: 用 prd/2026-07-03/login.md 产出一份 Tech Design
Agent: phase: reading
Agent: 📂 读取 prd/2026-07-03/login.md
Agent: 📋 读取 schema/tech_design/{README,ards,apis,data-model}.md (4 个 v4 模板)
Agent: 🔧 读取 AGENTS.md §1 (仓库标识: B + C)
Agent: phase: structuring
Agent: 设计子文件骨架：KD-1 (会话存储) / KD-2 (Token 刷新策略)
Agent: phase: injecting-context
Agent: 跨仓引用前缀: B/, C/
Agent: phase: writing
Agent: ✅ 写子文件到 tech_design/2026-07-03-login/ (4 个, 状态块 Draft, 复审自评四行 agent:<id> / 自动判据)
Agent: phase: validating
Agent: 🟢 ssdctl criteria 返回 0 (判据全绿)
Agent: phase: advancing
Agent: 🟢 ssdctl advance --to Ready 代写状态块与复审块
Agent: ⏸ 已推进到 Ready；人工可复核（可选），不复核不阻塞
```

### Complex (多仓)

```
User: 用 prd/2026-07-03/checkout-flow.md 产出一份 Tech Design
Agent: PRD 涉及全链路,前后端都有变更
Agent: 设计骨架:
  - README: 场景映射 5 行 + 实现基线 (B @短SHA, C @短SHA)
  - ards: KD-1 状态机(前端维护 vs 后端控制)→ 前端维护 UI 状态,后端维护业务状态
  - apis: 5 个端点 + 时序图 SYS-1 / MOD-1
  - data-model: 3 个实体 (含 erDiagram)
Agent: 跨仓引用自动按 §1.1 格式化
```

### Legacy (存量 v3, 显式 opt-in)

```
User: 用 prd/2026-07-03/legacy-feature.md 产出一份 Tech Design（按 v3 产出）
Agent: phase: reading
Agent: 📋 读取 schema/tech_design/v3/*.md (v3 存量模板)
Agent: phase: writing
Agent: ✅ 写 6 子文件 (+ 条件 interactions) 到 tech_design/2026-07-03-legacy-feature/
Agent: 🟢 ssdctl criteria 返回 0 (v3 分支)
```

## 安装 (Installation)

skill 定义随仓库分发, agent 直接读 `.codex/skills/to-tech-design/SKILL.md` 即可, **无需注册**。

需要把 skill 装进宿主 agent 的 skills 根目录时, 用仓内安装脚本：

```bash
bash <repo>/.codex/skills/install.sh                     # 默认 ~/.codex/skills/
bash <repo>/.codex/skills/install.sh --target <dir>      # 指定目标
bash <repo>/.codex/skills/install.sh --unregister        # 注销
```

## Related Skills

- `.codex/skills/to-prd/SKILL.md`：原始需求 → PRD（本 skill 的上游）
- `.codex/skills/to-plan/SKILL.md`：Tech Design → Plan（本 skill 的下游）
- `.codex/skills/validate-spec/SKILL.md`：跑仓内判据与门禁并出统一报告

## Cross-References

- <repo>/AGENTS.md §1（多仓上下文）
- <repo>/AGENTS.md §1.6（实现基线约定）
- <repo>/AGENTS.md §1.7（证据锚点约定）
- <repo>/AGENTS.md §3.1（工作流 Step 2）
- <repo>/schema/tech_design/README.md（v4 模板）
- <repo>/schema/tech_design/v3/（v3 存量模板目录）
- <repo>/scripts/ssdctl.py（判据与门禁唯一入口）
- <repo>/HOW_TO_USE.md（完整工作流）

