---
name: to-plan
description: Tech Design → Plan 转换流程，按 schema/plan.md 多段结构产出实施计划。引用来源自适应: v4 TD 取 ards.md / apis.md, v3 存量 TD 取 decisions.md / interactions.md。Use when 收到 Ready 状态的 Tech Design (默认 v4 四子文件), 需要产出多段结构 Plan (含变更索引 + TDD Flow + 跨文件引用对账 + 4 段完成检查)。多仓项目按 §1.5 强制分仓分组 Change。
skill-type: spec
version: 1.2
type: skill
skill-role: procedure
---

# to-plan

将 `tech_design/{date}-{topic}/`（默认 v4 四子文件, v3 存量六子文件自适应）转换为 `plan/{date}-{topic}/{topic}.md` 多段结构。

## Mode Indicator

```
[MODE: to-plan] (reading | structuring | grouping-by-repo | writing | validating)
```

| Phase | 做什么 |
|-------|--------|
| `reading` | 读 TD 子文件（默认 v4 四子文件, v3 存量六子文件自动识别）+ 对应 PRD + AGENTS.md §1 |
| `structuring` | 设计变更清单 + V 用例 + 业务/开发约束骨架 |
| `grouping-by-repo` | 按 §1.5 **强制分仓**：Change 按仓分组，V 用例按场景聚合 |
| `writing` | 写 Plan 到 `plan/{date}-{topic}/{topic}.md` |
| `validating` | 跑 `check-md-schema.sh` + `check-traceability.sh` 校验 |

## When to Use

- 收到 Ready 状态的 Tech Design（默认 v4 四子文件目录, 存量 v3 六子文件目录也识别）
- 需要产出符合多段结构的 Plan
- **多仓项目**：需要按 §1.5 强制分仓分组 Change
- 需要自动注入跨仓引用前缀

## Slash Command

```
/to-plan <tech-design-dir>
```

示例：

```
/to-plan tech_design/2026-07-03-login/
/to-plan tech_design/2026-07-03-login/README.md
```

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| Tech Design 状态 | Ready | 前置条件 |
| Tech Design 结构 | v4 四子文件 (默认) / v3 存量六子文件（按目录识别）| 输入 |
| 对应 PRD | Ready 状态 | 上下文（Goal / Scenarios 用于 V 用例） |
| AGENTS.md | §1 仓库清单 + §1.5 多仓 Plan 编排约定 + §1.6 实现基线约定 | 强制分仓 + 基线口径 |
| Schema 模板 | `schema/plan.md` | Plan 多段结构 |
| 校验脚本 | `scripts/check-md-schema.sh` + `check-traceability.sh` | 自动校验 |

## Core Concept

### Plan 多段结构

| 段 | 必填 | 关注点 |
|----|------|--------|
| 元数据 | ✓ | 状态 / 来源 TD / 来源 PRD / 创建日期 |
| 变更索引 | ✓ | 表格快速扫读（# / 文件路径 / 类型 / KD 引用 / V 引用 / 状态）|
| 变更清单 | ✓ | 每个 Change 详细描述（新增/修改/删除 + 策略约束 + KD 引用 + V 引用）|
| TDD 执行流程 | ✓ | mermaid 可视化 Red → Green → Refactor |
| 跨文件引用对账 | ✓ | KD / SYS / MOD / FR / V 闭环检查 |
| 验证用例 (V-{n}) | ✓ | 正常路径 + 异常 + 边界 |
| 业务约束 | ✓ | 前置 / 不变量 / 后置 / 副作用 |
| 开发约束 | ✓ | 并发 / 事务 / 幂等性 / 重试 / 超时 |
| 完成检查 (4 段) | ✓ | 实现层 + 验证层 + 引用层 + 流程层 |
| 变更记录 | ✓ | 版本管理 |

### TD 代际自适应 (引用来源)

Plan 引用的外部标识符来自 TD 的不同文件, **按 TD 代际取源**。TD 目录内有 `ards.md` 或 `apis.md` → v4; 否则 → v3 存量。

| 标识 | v4 来源 (默认) | v3 存量来源 |
|------|-----------------|-------------|
| KD-{n} | `../../tech_design/{date}-{topic}/ards.md` | `../../tech_design/{date}-{topic}/decisions.md` |
| SYS-{n} / MOD-{n} | `../../tech_design/{date}-{topic}/apis.md` | `../../tech_design/{date}-{topic}/interactions.md` |
| FR-{n} (PRD 需求) | `../../prd/{date}/{topic}.md` | `../../prd/{date}/{topic}.md` |
| V-{n} (验证用例) | 本文件 | 本文件 |

> **路径深度**: Plan 位于 `plan/{date}-{topic}/{topic}.md`, 到 `tech_design/` 与 `prd/` 都是**两级**相对路径 (`../../`)。写对账表的「来源」列时用 `../../` 前缀, 不要用 `../`。

### 实现基线约定 (§1.6)

当项目关联代码仓 (§1.1 登记了 ≥1 个非 A 标识) 时, Plan 记录**实施基线**, 让实现者知道在哪个分支/SHA 上动手:

| 项 | 规则 |
|----|------|
| 基线来源 | TD `README.md` 的 `## 实现基线` 段 (6 列: 仓库 / 分支 / SHA / 核对日期 / 核对项 / 状态) |
| Plan 写法 | 在元信息或「跨文件引用对账」表后记一行基线摘要: `{标识} @ {短SHA} ({分支})` |
| 仓库标识 | 取 §1.1「标识」列, 不写目录名 |
| 0 代码仓项目 | 不写基线行, 或写「不适用: 本项目无关联代码仓」|
| 证据锚点 | 现状结论引代码位置时用 `{标识}@{短SHA}:{路径}#L{行号}` (§1.7) |

### 多仓强制分仓（§1.5）

**Change 按仓分组**。前/后端关注点完全不同：

```markdown
## 变更清单

### B 变更

> KD-{n} / V-{n} 主要约束 B 仓的模块边界、UI 状态机、客户端校验、缓存策略

#### Change #1: `B/app/services/auth.ts`
**遵循决策**: KD-{n}
**验证**: V-{n}

#### Change #2: `B/packages/core/src/interceptors/signature.ts`
[...]

### C 变更

> KD-{n} / V-{n} 主要约束 C 仓的服务端编排、签名校验、网关出口

#### Change #N: `C/api/controller/SessionController.java`
[...]

### 验证用例（V-{n} 跨仓覆盖，按场景聚合）

> V 用例**不按仓分组**，按业务场景聚合（如"登录失败重试"覆盖 B 仓提单 + C 仓调用）。
> 但每个 Change **按仓分组**，因为 Change 的"实施约束"是仓特定的。
```

> **分组标题格式**: 按 AGENTS.md §1.5, 仓库组标题写 `### {仓库标识} 变更`（标识取 §1.1「标识」列）。**不**写「前端变更」「后端变更」这类自造标签。

### 跨仓引用格式（§1.2）

| 类型 | 写法 | 状态 |
|------|------|------|
| 推荐 | `{仓库前缀}/{相对路径}` | ✅ |
| 口语化 | `{仓库名} 仓库` | ❌ 禁止 |
| 裸路径 | `{相对路径}` | ❌ 禁止 |

## Execution Steps

### 1. Reading Phase

**TD 代际识别**（用 check-md-schema.sh 或直接看子文件是否存在）：

```bash
# v4 模式 (默认): 读 4 子文件
if [[ -f "$TD_DIR/ards.md" || -f "$TD_DIR/apis.md" ]]; then
  for f in README.md ards.md apis.md data-model.md; do
    cat "$TD_DIR/$f"
  done
else
  # v3 存量模式: 读 6 必填子文件 (+ 条件 interactions)
  for f in README.md decisions.md data-model.md \
           api-contracts.md scenario-mapping.md quality.md; do
    cat "$TD_DIR/$f"
  done
  [[ -f "$TD_DIR/interactions.md" ]] && cat "$TD_DIR/interactions.md"
fi
```

**引用来源**（写 Plan 引用 KD / SYS / MOD 时使用对应文件）：

| 标识 | v4 (默认) | v3 存量 |
|------|-----------|---------|
| KD-{n} | `ards.md` | `decisions.md` |
| SYS-{n} / MOD-{n} | `apis.md` | `interactions.md` |

# 读对应 PRD
PRD_PATH="prd/${DATE}/${TOPIC}.md"
cat "$PRD_PATH"

# 读 AGENTS.md §1（注入多仓上下文 + 实现基线约定）
sed -n '/^## 1\. /,/^## 2\. /p' AGENTS.md
```

### 2. Structuring Phase

按"Core Concept → Plan 多段结构"设计骨架：

1. **变更索引表**：扫读所有 Change
2. **变更清单**：每个文件一个 Change 条目（KD 引用 + V 引用）
3. **TDD Flow**：mermaid Red → Green → Refactor
4. **跨文件引用对账**：KD / SYS / MOD / FR / V 闭环
5. **V 用例**：正常 + 异常 + 边界
6. **业务/开发约束**

### 3. Grouping-by-Repo Phase

**关键**：按 §1.5 强制分仓：

1. **识别仓库**：从 AGENTS.md §1.1 读仓库清单的**标识**列（如 `[B, C]`）
2. **分配 Change**：根据 TD 中提及的文件路径前缀分到对应仓
3. **生成子标题**：
   - `### B 变更`
   - `### C 变更`
   - `### 验证用例（V-{n} 跨仓覆盖，按场景聚合）`
4. **路径加前缀**：所有文件路径加 `{仓库标识}/`

> 子标题里的仓库用 §1.1 的**标识**, 不用目录名, 也不用自造标签。标识是稳定逻辑标签, 目录名可随 Git URL 变。

### 4. Writing Phase

```bash
plan_dir="plan/{date}-{topic}/"
mkdir -p "$plan_dir"

# 写 Plan 文件
echo "$content" > "$plan_dir/{topic}.md"
```

**Plan 状态**：用 `Ready`（不产出 `Draft`）。

### 5. Validating Phase

```bash
# schema 校验
./scripts/check-md-schema.sh plan/{date}-{topic}/{topic}.md

# 追溯校验（KD / V 闭环）
./scripts/check-traceability.sh
```

要求：多段结构 Plan（有 `## 变更索引`）→ 严格校验全部段；返回 0，无 `✗`。

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| Plan 状态用 `Draft` | 直接 `Ready`（不产出 Draft） |
| Change 不引用 KD / V | 每个 Change 必须引用 KD-{n} + V-{n} |
| 写完整代码 | 只写策略和约束（代码在 TDD 阶段产出）|
| V 用例 Then 模糊（"系统正常运行"）| Then 可被断言（"pendingUpdate 重置为 false"）|
| 只写正常路径 | 正常 + 异常 + 边界 3 类缺一不可 |
| 单仓项目也按多仓分节 | 单仓不分节，1 级标题即可 |
| 多仓项目不按仓分节 | **强制按仓分**（§1.5） |
| 仓库组标题自造标签（「前端变更（B）」）| 按 §1.5 写 `### {仓库标识} 变更` |
| Change 标题用裸路径（`app/services/auth.ts`）| 加仓库标识前缀（`B/app/services/auth.ts`）|
| 用口语化引用（"B 仓库"）| 用标识（`B`）+ §1.2 格式 |
| Change 粒度粗（"修改 Service 层"）| 精确到文件（`B/app/services/auth.ts`）|
| 对账表来源写成 `../tech_design/...` | Plan 在两级目录下, 用 `../../tech_design/...` |
| v4 TD 却引用 `decisions.md` / `interactions.md` | v4 取 `ards.md` / `apis.md`, v3 存量才取旧文件 |
| 引用 `SC-N`（已废弃）| 用 `KD-N` / `V-N` / `FR-N` / `SYS-N` / `MOD-N` |

## Troubleshooting

### Q1：check-md-schema.sh 报"缺少 ### Change #1:"

**症状**：Plan 报缺变更清单

**排查**：
```bash
grep -E "^### Change #" plan/{date}-{topic}/{topic}.md
```

**处理**：补 Change #1 段，格式 `### Change #1: {file-path}`。

### Q2：check-md-schema.sh 报"缺少 ### V-1:"

**症状**：Plan 报缺验证用例

**排查**：
```bash
grep -E "^### V-[0-9]+:" plan/{date}-{topic}/{topic}.md
```

**处理**：补 V-1 段，格式 `### V-1: {场景名}`。

### Q3：check-md-schema.sh 报"缺少 ## 跨文件引用对账"

**症状**：Plan 报缺对账表

**处理**：在 Plan 中段加对账表（来源列按 TD 代际取, 路径为两级 `../../`）：

```markdown
## 跨文件引用对账

| 引用类型 | 标识 | 来源 | 已对账 |
|----------|------|------|--------|
| 关键决策 | KD-1 | `../../tech_design/{date}-{topic}/ards.md` (v4) 或 `../../tech_design/{date}-{topic}/decisions.md` (v3 存量) | [x] |
| 时序图 | SYS-1 | `../../tech_design/{date}-{topic}/apis.md` (v4) 或 `../../tech_design/{date}-{topic}/interactions.md` (v3 存量) | [x] |
| 验证用例 | V-1 | 本文件 | [x] |
```

> **Change 标题层级**: 单仓用 `### Change #N: {路径}`; 多仓分仓时仓库组标题占 h3, Change 条目落 `#### Change #N: {标识}/{路径}`。`check-md-schema.sh` 两种层级都识别。

### Q4：check-traceability.sh 报"引用 KD-N 但不存在"

**症状**：Plan 引用 KD-3，但 TD 里没有 `## KD-3:`

**处理**：根据 TD 代际补对应文件：
- v4（默认）→ 在 `tech_design/{date}-{topic}/ards.md` 补 `## KD-3: ...` 段
- v3 存量 → 在 `tech_design/{date}-{topic}/decisions.md` 补 `## KD-3: ...` 段

### Q5：check-traceability.sh 报"引用 V-N 但未在验证用例段定义"

**症状**：Change 引用 V-3，但 Plan 没 `### V-3:`

**处理**：在 `## 验证用例` 段补 `### V-3: {场景名}`。

### Q6：多仓项目 Change 没分仓

**症状**：Plan 写 `### Change #1: app/services/auth.ts` + `### Change #2: api/...`，没分仓分组

**处理**：重组 Plan 结构：

```markdown
## 变更清单

### B 变更
#### Change #1: B/app/services/auth.ts
[...]

### C 变更
#### Change #N: C/api/...
[...]
```

### Q7：v2 旧 Plan 报错

**症状**：跑 check-md-schema.sh 报缺 ## 变更索引 或 V-N 命名

**原因**：v2 旧 Plan 用 `### V1:` / `### V01:` 等非标准命名，无 `## 变更索引` 段

**处理**：
- **新 Plan**：必须用多段结构
- **v2 旧 Plan**：脚本走双模式 `○ v2 跳过`（已修复的 check-md-schema.sh）

### Q8：有代码仓但 Plan 没记基线

**症状**：Plan 元信息只有「来源 TD / 来源 PRD」，实施者不知道从哪个 SHA 动手

**处理**：按「实现基线约定 (§1.6)」补一行基线摘要, 形如 `B @ a1b2c3d (main)`。仓库标识取 §1.1「标识」列。0 代码仓项目写「不适用: 本项目无关联代码仓」。

## Tips

- **状态字段**：Plan 用 `Ready`（不产出 Draft）
- **Change 必引用 KD + V**：双向引用缺一不可
- **V 用例 3 类缺一不可**：正常 + 异常 + 边界
- **Then 必须可断言**：禁止"系统正常运行"等模糊描述
- **多仓强制分仓**：前/后端关注点完全不同，分仓更有针对性
- **跨仓引用带标识前缀**：从 §1.1 仓库清单解析，不要硬编码
- **引用来源按代际取**：v4 `ards.md` / `apis.md`; v3 存量 `decisions.md` / `interactions.md`
- **路径是两级**：Plan → TD / PRD 用 `../../`
- **有代码仓就记基线**：见 §1.6
- **V 用例按场景聚合**：不按仓分组（如"登录失败重试"覆盖前后端）

## Examples

### Simple (单仓)

```
User: /to-plan tech_design/2026-07-03-login/
Agent: [MODE: to-plan] (reading)
Agent: 📂 读 TD 子文件（v4/v3 自动识别）+ 对应 PRD
Agent: [MODE: to-plan] (structuring)
Agent: 设计骨架：5 个 Change + 6 个 V 用例 + 4 段完成检查
Agent: [MODE: to-plan] (grouping-by-repo)
Agent: 单仓项目（不涉及多仓），不分节
Agent: [MODE: to-plan] (writing)
Agent: ✅ 写 plan/2026-07-03-login/login.md
Agent: [MODE: to-plan] (validating)
Agent: 🟢 check-md-schema.sh 返回 0
Agent: 🟢 check-traceability.sh 返回 0
```

### Complex (多仓)

```
User: /to-plan tech_design/2026-07-03-checkout-flow/
Agent: AGENTS.md §1: [B, C]
Agent: 读 TD 后识别:
  - 前端 Change: B/app/views/CheckoutScreen.tsx (UI)
  - 后端 Change: C/api/controller/CartController.java (服务端)
  - 共享: C/api/contract/CartContract.java (接口契约)
Agent: [MODE: to-plan] (grouping-by-repo)
Agent: 强制分仓:
  ### B 变更
    #### Change #1: B/app/views/CheckoutScreen.tsx
    #### Change #2: B/app/services/cartService.ts
  ### C 变更
    #### Change #N: C/api/controller/CartController.java
  ### 验证用例（V-{n} 跨仓覆盖，按场景聚合）
    #### V-1: 正常下单流程（跨仓协同）
    #### V-2: 库存不足异常（C 仓校验）
Agent: 对账表来源列: `../../tech_design/2026-07-03-checkout-flow/ards.md` (v4)
Agent: 基线摘要: B @ a1b2c3d (main) · C @ d4e5f6a (main)
```

## Slash Command Registration

通过 `<repo>/skills/setup.sh` 注册到 agent skills 目录：

```bash
bash <repo>/skills/setup.sh
```

## Related Skills

- `to-prd`：原始需求 → PRD
- `to-tech-design`：PRD → Tech Design（本 skill 的上游）
- `validate-spec`：跑全部校验脚本

## Cross-References

- <repo>/AGENTS.md §1.5（多仓 Plan 编排约定）
- <repo>/AGENTS.md §1.6（实现基线约定）
- <repo>/AGENTS.md §1.7（证据锚点约定）
- <repo>/AGENTS.md §3（三步工作流 Step 3）
- <repo>/schema/plan.md（多段模板）
- <repo>/schema/tech_design/（v4 TD 模板目录）
- <repo>/schema/tech_design/v3/（v3 存量 TD 模板目录）
- <repo>/scripts/check-md-schema.sh（v4 / v3 双模式校验）
- <repo>/scripts/check-traceability.sh（双模式校验）
- <repo>/HOW_TO_USE.md（完整工作流）