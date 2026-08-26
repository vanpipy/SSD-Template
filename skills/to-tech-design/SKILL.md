---
name: to-tech-design
description: PRD → Tech Design 转换流程, 支持 v3 6 子文件 (存量) 与 v4 4 子文件 (新约定) 双模式。v4 子文件: README 综合描述 + ards 架构决策+方案对比+探索机制 + apis 接口契约+时序 + data-model ER 图。v3 子文件: README + decisions + data-model + api-contracts + scenario-mapping + quality (+ interactions 条件)。Use when 收到 Ready 状态的 PRD, 需要产出 Tech Design (默认 v3, 显式 opt-in v4)。
skill-type: spec
version: 1.1
type: skill
skill-role: procedure
---

# to-tech-design

将 `prd/{date}/{topic}.md`（Ready 状态, 无 `-processed` 后缀）转换为 `tech_design/{date}-{topic}/`.

## 代际选择 (默认 v3, opt-in v4)

| 形态 | 子文件 | 适用场景 |
|------|--------|----------|
| **v3** (默认, 存量) | README + decisions + data-model + api-contracts + scenario-mapping + quality (+ interactions 条件) | 维护既有 v3 项目, 增量补 TD |
| **v4** (新约定, opt-in) | README 综合描述 + **ards** 架构决策+方案对比+探索深度声明+OQ/Spikes/Pivot+Gap 对比 + **apis** 接口契约+时序图 (SYS/MOD) + data-model ER 图 | 新建项目, 探索机制必填, 决策可追溯 |

> **校验脚本**: `check-md-schema.sh` 双模式识别 (按 `ards.md`/`apis.md` 存在判定 v4). v3 → v4 迁移无需触动存量目录, 新建目录按 opt-in 选择.

## Mode Indicator

```
[MODE: to-tech-design] (reading | structuring | injecting-context | writing | validating)
```

| Phase | 做什么 |
|-------|--------|
| `reading` | 读 PRD + schema 子文件模板（v3 7 或 v4 4） |
| `structuring` | 设计子文件内容骨架（v3 KD/数据模型/API 等 / v4 ards+apis+data-model+README 场景映射） |
| `injecting-context` | 从 AGENTS.md §1 读多仓关系，决定跨仓引用前缀 |
| `writing` | 写子文件到 `tech_design/{date}-{topic}/`（v3 7 个 / v4 4 个） |
| `validating` | 跑 `check-md-schema.sh` 校验 |

## When to Use

- 收到 Active 状态的 PRD
- 需要产出符合 v3 7 子文件 / v4 4 子文件结构的 Tech Design（默认 v3, opt-in v4）
- 需要自动注入多仓上下文

## Slash Command

```
/to-tech-design <prd-path>
```

示例：

```
/to-tech-design prd/2026-07-03/login.md
/to-tech-design prd/2026-07-03/      # 批量处理整个分桶
```

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| PRD 状态 | Active | 前置条件 |
| Schema 模板 | `schema/tech_design/*.md` | v3 7 子文件 / v4 4 子文件（按需）|
| AGENTS.md | §1 仓库清单 + §1.2 跨仓引用约定 | 多仓上下文 |
| 校验脚本 | `scripts/check-md-schema.sh` | 自动校验 |
| Code 仓 | 关联的 code 仓（如 client + server）| 跨仓引用前缀 |

## Core Concept

### 子文件职责 (按所选代际)

#### v3 模式 (存量, 默认)

| 子文件 | 必填 | 关注点 |
|--------|------|--------|
| README.md | ✓ | 入口/索引，摘要 + 子文件导航 |
| decisions.md | ✓ | KD-{n}（Context/Decision/Alternatives/Rationale/Enforced by）|
| data-model.md | ✓ | 实体/字段/约束，关联场景 |
| api-contracts.md | ✓ | 端点 + 请求/响应 + 错误码 |
| scenario-mapping.md | ✓ | PRD 场景 → 实现路径（覆盖所有 Given/When/Then）|
| interactions.md | 条件 | 系统级/模块级 mermaid sequence diagram |
| quality.md | ✓ | 指标 + 降级 + 错误处理 |

#### v4 模式 (新约定, opt-in)

| 子文件 | 必填 | 关注点 |
|--------|------|--------|
| README.md | ✓ | 综合描述 + `## 场景映射` 段 (6 列表, 与 v3 的 scenario-mapping.md 等效, 合并入口) |
| ards.md | ✓ | 探索深度声明 + 方向选择总表 + Solution Space 候选方案对比 + **KD-{n}** (Context/Decision/Alternatives/Rationale/Enforced by) + Open Questions/Spikes/Pivot Triggers + Gap 表 + 风险缓解 |
| apis.md | ✓ | 接口契约 (全响应变体) + 枚举速查 + 组装规则 + 时序图 (SYS-{n} 系统级 / MOD-{n} 模块级) |
| data-model.md | ✓ | ER 图 / 数据结构 |

> **v4 不需要** decisions.md / api-contracts.md / scenario-mapping.md / quality.md / interactions.md — 内容已合并到 ards.md + apis.md + README.md 场景映射。
> **迁移 v3 → v4**: 不强制迁移, 存量目录保留 v3; 新建目录 opt-in v4。

### 何时需要 interactions.md (仅 v3 适用)

满足**任一**条件时必填：

- 场景映射表行数 ≥ 5
- 涉及外部接口调用
- 涉及 ≥ 2 个内部模块协作
- 包含异步流程 / 状态机 / 重试逻辑

否则可在 README.md 显式标注"不适用"跳过。

> v4 模式下时序图直接写在 `apis.md` 的 SYS-{n} / MOD-{n} 段，不需要独立 interactions.md。

### 多仓上下文注入

从 `AGENTS.md §1` 自动读：

| 注入内容 | 用途 |
|----------|------|
| §1.1 仓库清单 | 决定 Change 涉及的仓库 |
| §1.2 跨仓引用约定 | 跨仓引用必须带前缀 |
| §1.3 代码仓 AGENTS 索引 | 跨仓引用时给出 AGENTS 路径 |

## Execution Steps

### 1. Reading Phase

```bash
# 读 PRD
cat "$PRD_PATH"

# 读 schema 子文件模板 (按代际)
ls schema/tech_design/
for f in schema/tech_design/*.md; do cat "$f"; done

# 读 AGENTS.md §1
sed -n '/^## 1\. /,/^## 2\. /p' AGENTS.md
```

### 2. Structuring Phase

按"Core Concept → 子文件职责（按所选代际）"设计每个子文件内容骨架：

**v3 模式（默认）**:
1. **识别 KD**：PRD 中存在 ≥2 方案的设计选择 → 必须记录为 KD
2. **数据模型**：列出实体 + 字段 + 约束
3. **API 契约**：每个端点 + 请求/响应
4. **场景映射**：PRD 每个 Given/When/Then 必出现在映射表
5. **时序图**（条件）：如满足触发条件
6. **质量保证**：具体数字指标 + 降级策略 + 错误处理

**v4 模式（opt-in）**:
1. **ards.md**：每个设计选择 → KD-{n} 段（5 段结构 + Solution Space 候选 ≥2 + Spikes/Pivot）
2. **apis.md**：每个接口 + 时序图（系统级 SYS-{n} / 模块级 MOD-{n}）
3. **data-model.md**：实体 + 字段 + 约束（与 v3 一致）
4. **README.md**：综合描述 + 场景映射 6 列表（覆盖 PRD 所有 Given/When/Then）

### 3. Injecting-Context Phase

从 AGENTS.md §1 解析：

```
仓库清单: [client, server]
引用前缀: client/, server/
关联 AGENTS: ~/Project/client/AGENTS.md, ~/Project/server/AGENTS.md
```

把所有跨仓引用按 §1.2 格式化：

```markdown
# 错 ❌
app/services/auth.ts
api/facade/read/LoginServiceClient.java
client 仓库

# 对 ✅
client/app/services/auth.ts
server/api/facade/read/LoginServiceClient.java
client (从 §1.1 仓库清单)
```

### 4. Writing Phase

```bash
td_dir="tech_design/{date}-{topic}/"
mkdir -p "$td_dir"

# v3 模式 (默认): 写 7 子文件 (含条件 interactions)
if [[ "$mode" == "v3" ]]; then
  for sub in README decisions data-model api-contracts scenario-mapping quality; do
    echo "$content_for_$sub" > "$td_dir/$sub.md"
  done
  if needs_interactions; then
    echo "$interactions_content" > "$td_dir/interactions.md"
  fi
fi

# v4 模式 (opt-in): 写 4 子文件 (README 综合描述 + ards + apis + data-model)
if [[ "$mode" == "v4" ]]; then
  for sub in README ards apis data-model; do
    echo "$content_for_$sub" > "$td_dir/$sub.md"
  done
  # README 必须含 ## 场景映射 段 (6 列表), ards 必须含 ## KD-{n}: 段, apis 必须含 ## 接口契约 + 时序图 (SYS/MOD) 段
fi
```

### 5. Validating Phase

```bash
./scripts/check-md-schema.sh tech_design/{date}-{topic}/
```

要求：双模式自动识别（ards.md 或 apis.md 存在 → v4 校验 4 子文件；否则 → v3 校验 7 子文件 + 条件 interactions.md）；返回 0，无 `✗`。

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 省略 README.md | 必填，作为入口索引 |
| KD 缺 5 段（Context/Decision/Alternatives/Rationale/Enforced by）| KD 必须完整 5 段 |
| KD 只有 1 个备选方案 | 至少 2 个备选方案 |
| 场景映射表漏 PRD 场景 | 全部 PRD Given/When/Then 必出现 |
| 指标用模糊描述（"响应要快"）| 具体数字（P99 < 500ms）|
| 外部接口无降级策略 | 每个外部调用必须有降级 |
| 跨仓引用用裸路径（`app/services/auth.ts`）| 带仓库前缀（`client/app/services/auth.ts`）|
| 跨仓引用口语化（"client 仓库"）| 用 §1.1 仓库清单名称 |
| 把数据用 `string` 泛指 | 用 TS / SQL / JSON Schema 具体类型 |
| 错误码用 `4xx` 泛指 | 用具体值（`400` / `401` / `403`）|

## Troubleshooting

### Q1：check-md-schema.sh 报"缺少必填子文件"

**症状**：报缺 README.md / decisions.md / data-model.md 等

**排查**：
```bash
ls tech_design/{date}-{topic}/
```

**处理**：补齐缺失的 6 个必填子文件（README + decisions + data-model + api-contracts + scenario-mapping + quality）。

### Q2：check-md-schema.sh 报"引用 KD-N 但不存在"

**症状**：README.md 的"跨文件引用对账"段引用 KD-3，但 decisions.md 没有 `## KD-3:`

**排查**：
```bash
grep "^## KD-" tech_design/{date}-{topic}/decisions.md
```

**处理**：在 decisions.md 补 `## KD-3: ...` 段，或从 README 删除 KD-3 引用。

### Q3：check-md-schema.sh 报"缺少 interactions.md 且 README 未声明跳过"

**症状**：README 没标注 interactions.md 跳过

**处理（条件满足）**：写 interactions.md（系统级 + 模块级 mermaid sequence diagram）。

**处理（条件不满足）**：在 README 的"何时需要 interactions.md"段标注：
```
- [ ] (不适用) interactions.md,场景映射 < 5 行,无外部接口调用
```

### Q4：7 个子文件内容不连贯

**症状**：data-model.md 的实体名与 api-contracts.md 的字段名不一致

**原因**：分步写子文件时，跨文件命名漂移（v3 7 个 / v4 4 个都易犯）

**处理**：用"命名表"（统一术语表）作为写之前的强制步骤：

```markdown
| 术语 | data-model.md 写法 | api-contracts.md 写法 |
|------|---------------------|------------------------|
| 用户 | User | user |
| 商品 | Item | item |
| 商家 | Merchant | merchant |
```

### Q5：跨仓引用没自动带前缀

**症状**：api-contracts.md 写 `app/services/auth.ts`，应写 `client/app/services/auth.ts`(对应 §1.1 B 行的本地路径)

**排查**：检查是否读 AGENTS.md §1（injecting-context phase）

**处理**：确保 to-tech-design 的 injecting-context phase 正确解析 §1.1 仓库清单。

## Tips

- **KD 是核心**：≥2 方案的设计选择必须记录 KD，不可跳过
- **场景映射完整性**：PRD 每个 Given/When/Then 必出现，否则 Plan 验证用例会缺
- **指标具体数字**：`P99 < 500ms` ✓，`响应快` ✗
- **降级策略覆盖**：每个外部接口都有降级（触发条件 + 行为 + 影响）
- **多仓项目**：跨仓引用从 §1.1 读前缀，不要硬编码"client/"
- **interactions.md 条件触发**：不强制创建，README 显式声明跳过即可
- **Tech Design 状态**：v3 用 `Ready`（不是 `Implemented`/`Active`）

## Examples

### Simple

```
User: /to-tech-design prd/2026-07-03/login.md
Agent: [MODE: to-tech-design] (reading)
Agent: 📂 读取 prd/2026-07-03/login.md
Agent: 📋 读取 schema/tech_design/*.md (7 个模板)
Agent: 🔧 读取 AGENTS.md §1 (仓库: client + server)
Agent: [MODE: to-tech-design] (structuring)
Agent: 设计子文件骨架：KD-1 (会话存储) / KD-2 (Token 刷新策略)
Agent: [MODE: to-tech-design] (injecting-context)
Agent: 跨仓引用前缀: client/, server/
Agent: [MODE: to-tech-design] (writing)
Agent: ✅ 写子文件到 tech_design/2026-07-03-login/
Agent: [MODE: to-tech-design] (validating)
Agent: 🟢 check-md-schema.sh 返回 0
```

### Complex (多仓)

```
User: /to-tech-design prd/2026-07-03/checkout-flow.md
Agent: PRD 涉及全链路,前后端都有变更
Agent: 设计骨架:
  - KD-1: 状态机(前端维护 vs 后端控制)→ client 维护 UI 状态,server 维护业务状态
  - data-model: 3 个实体 (Cart / CartItem / Payment)
  - api-contracts: 5 个端点
    - POST client/app/services/cart.ts → server/api/controller/CartController.java
Agent: 跨仓引用自动按 §1.1 格式化
```

## Slash Command Registration

通过 `<repo>/skills/setup.sh` 注册到 agent skills 目录：

```bash
bash <repo>/skills/setup.sh
```

## Related Skills

- `to-prd`：原始需求 → PRD（本 skill 的上游）
- `to-plan`：Tech Design → Plan（本 skill 的下游）
- `validate-spec`：跑全部校验脚本

## Cross-References

- <repo>/AGENTS.md §1（多仓上下文）
- <repo>/AGENTS.md §3（三步工作流 Step 2）
- <repo>/schema/tech_design/README.md（v3 索引）
- <repo>/scripts/check-md-schema.sh（v3 双模式校验）
- <repo>/HOW_TO_USE.md（完整工作流）