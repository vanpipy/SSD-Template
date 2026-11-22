---
name: to-plan
description: >-
  Tech Design → Plan 转换流程 (v1.2), 按 schema/plan.md 多段结构产出实施计划。引用来源自适应, v4 TD 取 ards.md / apis.md,
  v3 存量 TD 取 decisions.md / interactions.md。Use when 收到已就绪的 Tech Design (默认 v4 四子文件), 需要产出多段结构 Plan
  (含变更索引 + TDD Flow + 跨文件引用对账 + 4 段完成检查)。多仓项目按 §1.5 强制分仓分组 Change。agent 只能产出 Draft 状态,
  Ready 与 Implemented 由人工写入。
---

# to-plan

将 `tech_design/{date}-{topic}/`（默认 v4 四子文件, v3 存量六子文件自适应）转换为 `plan/{date}-{topic}/{topic}.md` 多段结构。

## 执行阶段 (内部 phase 标识)

agent 按下列 phase 顺序推进。每个 phase 开始时在汇报里写明 `phase: <name>`, 便于人工追溯。

> phase 是 agent 的**内部工作分段**, 不依赖任何 UI 模式指示器, 也不假设运行环境会显示模式。

| Phase | agent 做什么 |
|-------|--------------|
| `reading` | 读 TD 子文件 (默认 v4 四子文件, v3 存量六子文件自动识别) + 对应 PRD + `AGENTS.md` §1 |
| `structuring` | 设计变更清单 + V 用例 + 业务/开发约束骨架 |
| `grouping-by-repo` | 按 §1.5 **强制分仓**: Change 按仓分组, V 用例按场景聚合 |
| `writing` | 写 Plan 到 `plan/{date}-{topic}/{topic}.md`, 状态行写 `Draft` |
| `validating` | 跑 `scripts/check-md-schema.sh` + `scripts/check-traceability.sh` 校验并汇报退出码 |

## When to Use

- 收到已就绪的 Tech Design（默认 v4 四子文件目录, 存量 v3 六子文件目录也识别）
- 需要产出符合多段结构的 Plan
- **多仓项目**：需要按 §1.5 强制分仓分组 Change
- 需要自动注入跨仓引用前缀

## 调用输入

| 输入 | 必填 | 说明 |
|------|------|------|
| Tech Design 目录 | 是 | `tech_design/{date}-{topic}/`; 也可直接给该目录下的 `README.md` |

示例: 用 `tech_design/2026-07-03-login/` 产出一份 Plan。

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| Tech Design 状态 | Ready | 前置条件 (上游 TD 由人工 reviewer 签署后翻到 `Ready`) |
| Tech Design 结构 | v4 四子文件 (默认) / v3 存量六子文件（按目录识别）| 输入 |
| 对应 PRD | Ready 状态 | 上下文（Goal / Scenarios 用于 V 用例） |
| AGENTS.md | §1 仓库清单 + §1.5 多仓 Plan 编排约定 + §1.6 实现基线约定 | 强制分仓 + 基线口径 |
| Schema 模板 | `schema/plan.md` | Plan 多段结构 |
| 校验脚本 | `scripts/check-md-schema.sh` + `check-traceability.sh` | 自动校验 |

## Core Concept

### Plan 多段结构

| 段 | 必填 | 关注点 |
|----|------|--------|
| 元数据 | ✓ | 状态 / 来源 TD / 来源 PRD / 参考 Test Cases / 创建日期 / 最后更新 |
| 变更索引 | ✓ | 表格快速扫读（# / 文件路径 / 类型 / KD 引用 / V 引用 / 状态）|
| 变更清单 | ✓ | 每个 Change 详细描述（新增/修改/删除 + 策略约束 + KD 引用 + V 引用）|
| TDD 执行流程 | ✓ | mermaid 可视化 Red → Green → Refactor |
| 跨文件引用对账 | ✓ | KD / SYS / MOD / FR / V 闭环检查 |
| 验证用例 (V-{n}) | ✓ | 正常路径 + 异常 + 边界 |
| 业务约束 | ✓ | 前置 / 不变量 / 后置 / 副作用 |
| 开发约束 | ✓ | 并发 / 事务 / 幂等性 / 重试 / 超时 |
| 完成检查 (4 段) | ✓ | 实现层 + 验证层 + 引用层 + 流程层 |
| 变更记录 | ✓ | 版本管理 |

### 元信息 6 项 (与 schema/plan.md 逐字对齐)

Plan 头部的元信息块必须写满 **6 项**, 顺序与 `schema/plan.md` 一致:

| # | 字段 | 写法 | 说明 |
|---|------|------|------|
| 1 | `> **状态**` | `Draft` / `Ready` / `Implemented` / `Deprecated` | agent 只写 `Draft` |
| 2 | `> **来源 Tech Design**` | `../../tech_design/{date}-{topic}/` | 两级相对路径 |
| 3 | `> **来源 PRD**` | `../../prd/{date}/{topic}.md` | 两级相对路径 |
| 4 | `> **参考 Test Cases**` | `test_cases/{YYYY-MM-DD}/{topic}.md` | **可选行**: 填了必须是仓内真实存在、且以 `test_cases/` 开头的路径(用反引号包裹); 不适用就**删掉整行** |
| 5 | `> **创建日期**` | `YYYY-MM-DD` | 真实日期, 不留占位符 |
| 6 | `> **最后更新**` | `YYYY-MM-DD` | 真实日期, 不留占位符 |

> `scripts/check-traceability.sh` 的 T11 会校验「参考 Test Cases」行的路径是否存在; 该行**不存在**时跳过校验, 但**存在时必须指向真实文件**。

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

#### B 变更

> KD-{n} / V-{n} 主要约束 B 仓的模块边界、UI 状态机、客户端校验、缓存策略

#### Change #1: `B/app/services/auth.ts`
**遵循决策**: KD-{n}
**验证**: V-{n}

#### Change #2: `B/packages/core/src/interceptors/signature.ts`
[...]

#### C 变更

> KD-{n} / V-{n} 主要约束 C 仓的服务端编排、签名校验、网关出口

#### Change #N: `C/api/controller/SessionController.java`
[...]

## 验证用例 (Verification)

### V-{n}: 跨仓场景名

> V 用例**不按仓分组**，按业务场景聚合（如"登录失败重试"覆盖 B 仓提单 + C 仓调用）。
> 但每个 Change **按仓分组**，因为 Change 的"实施约束"是仓特定的。
```

> **分组标题格式**: 按 AGENTS.md §1.5, 仓库组标题写 `#### {仓库标识} 变更`（标识取 §1.1「标识」列）。**不**写「前端变更」「后端变更」这类自造标签。
> **Change 标题层级**: 多仓时组标题与组内 Change 都是 h4 (`#### {标识} 变更` / `#### Change #N: {标识}/{路径}`); 单仓 / 0 代码仓时 Change 直接落 h3 (`### Change #1: {文件路径}`)。`check-md-schema.sh` 两种层级都识别。
> **V 用例层级**: V 用例段独立于变更清单段, 段标题 h2 `## 验证用例 (Verification)`, 用例标题 h3 `### V-{n}: {场景名}`。

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
   - `#### B 变更`
   - `#### C 变更`
   - V 用例段独立: `## 验证用例 (Verification)` + `### V-{n}: {场景名}`
4. **路径加前缀**：所有文件路径加 `{仓库标识}/`

> 子标题里的仓库用 §1.1 的**标识**, 不用目录名, 也不用自造标签。标识是稳定逻辑标签, 目录名可随 Git URL 变。

### 4. Writing Phase

```bash
plan_dir="plan/{date}-{topic}/"
mkdir -p "$plan_dir"

# 写 Plan 文件
echo "$content" > "$plan_dir/{topic}.md"
```

**Plan 状态**：agent 只写 `Draft`（agent 可写上限是 `Draft`, 不是 `Ready` / `Implemented` / `Active`）。`Ready` 由人工 reviewer 在 `## 复审 (Review)` 段签署三行后翻转。

**复审签署三行**：`## 复审 (Review)` 段的 `> **评审人**` / `> **评审日期**` / `> **评审结论**` 在 `Draft` 阶段**留空**（不留 `{}` 占位符）, agent 不得自行填写或翻转状态。

### 5. Validating Phase

```bash
# schema 校验
./scripts/check-md-schema.sh plan/{date}-{topic}/{topic}.md

# 追溯校验（KD / V 闭环）
./scripts/check-traceability.sh
```

要求：多段结构 Plan（有 `## 变更索引`）→ 严格校验全部段；返回 0，无 `✗`。

## 状态推进边界 (agent 权限天花板 = Draft)

| 状态 | 谁能写 | agent 能做什么 |
|------|--------|----------------|
| `Draft` | **agent** | 写产出文件 + 跑门禁 + 报告结论 |
| `Ready` | **人工 reviewer** | 只能等: 不得翻状态, 不得代填 `评审人` / `评审日期` / `评审结论` |
| `Implemented` | **仅人工** | 只能等: 人工在外部 PR merged 后回写, 且 PRD / TD / Plan **三件套必须同时** |
| `Deprecated` | **人工决策** | 只能等: 上游 Deprecated 之后的机械级联由人工触发 |

- agent 产出 Plan 后**停在 `Draft`**, 汇报「已产出 Draft, 待人工 reviewer 签署后翻 Ready」。
- `## 复审 (Review)` 段的三行签署载体在 `Draft` 阶段留空（不留 `{}` 占位符）。

## 禁止行为 (Agent 权限边界)

| ❌ Don't | ✅ Do |
|----------|-------|
| 自行 `git commit` / `git push` | 只改工作区文件; 提交由人工决定。**Symphony 编排路径例外**: 在 Symphony 给你的工作区 + `spec/{issue-identifier}-{topic}` 分支上, 按仓根 `WORKFLOW.md` §8 提交与推送是**授权动作**; 仍禁止 push 主分支 / merge / 伪造评审 |
| 把状态写成 `Ready` / `Implemented` | 只写 `Draft` |
| 伪造 `Reviewed-by:` / SHA / 行号 / handle | 拿不准就不写 |
| 修改 `schema/**` 下的模板 | 只读 `schema/plan.md` |
| 静默覆盖冲突 | 登记冲突并交人工裁决 |
| 留下 `{...}` 占位符 | 填真实值, 不适用就删整行 |

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 自行把 Plan 状态写成 `Ready` / `Implemented` | agent 只写 `Draft`, 等人工 reviewer 签署 |
| 自行填 `评审人` / `评审日期` / `评审结论` | `Draft` 阶段三行留空, 等人工 reviewer 填写 |
| Change 不引用 KD / V | 每个 Change 必须引用 KD-{n} + V-{n} |
| 写完整代码 | 只写策略和约束（代码在 TDD 阶段产出）|
| V 用例 Then 模糊（"系统正常运行"）| Then 可被断言（"pendingUpdate 重置为 false"）|
| 只写正常路径 | 正常 + 异常 + 边界 3 类缺一不可 |
| 单仓项目也按多仓分节 | 单仓不分节，1 级标题即可 |
| 多仓项目不按仓分节 | **强制按仓分**（§1.5） |
| 仓库组标题自造标签（「前端变更（B）」）| 按 §1.5 写 `#### {仓库标识} 变更` |
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

**症状**：Plan 元信息只写了「来源 TD / 来源 PRD」等少数几项，实施者不知道从哪个 SHA 动手

**处理**：按「实现基线约定 (§1.6)」补一行基线摘要, 形如 `B @ a1b2c3d (main)`。仓库标识取 §1.1「标识」列。0 代码仓项目写「不适用: 本项目无关联代码仓」。

> 顺带核对元信息 6 项是否写满: 状态 / 来源 Tech Design / 来源 PRD / 参考 Test Cases(可选) / 创建日期 / 最后更新。缺项时 `check-md-schema.sh` 可能仍然返回 0, 但产物与 `schema/plan.md` 不一致。

## Tips

- **状态字段**：agent 只写 `Draft`（`Ready` 由人工 reviewer 签署翻转）
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
User: 用 tech_design/2026-07-03-login/ 产出一份 Plan
Agent: phase: reading
Agent: 📂 读 TD 子文件（v4/v3 自动识别）+ 对应 PRD
Agent: phase: structuring
Agent: 设计骨架：5 个 Change + 6 个 V 用例 + 4 段完成检查
Agent: phase: grouping-by-repo
Agent: 单仓项目（不涉及多仓），不分节
Agent: phase: writing
Agent: ✅ 写 plan/2026-07-03-login/login.md (状态 Draft, 评审签署三行留空)
Agent: phase: validating
Agent: 🟢 check-md-schema.sh 返回 0
Agent: 🟢 check-traceability.sh 返回 0
Agent: ⏸ 已产出 Draft，待人工 reviewer 签署后翻 Ready
```

### Complex (多仓)

```
User: 用 tech_design/2026-07-03-checkout-flow/ 产出一份 Plan
Agent: AGENTS.md §1: [B, C]
Agent: 读 TD 后识别:
  - 前端 Change: B/app/views/CheckoutScreen.tsx (UI)
  - 后端 Change: C/api/controller/CartController.java (服务端)
  - 共享: C/api/contract/CartContract.java (接口契约)
Agent: phase: grouping-by-repo
Agent: 强制分仓:
  #### B 变更
    #### Change #1: B/app/views/CheckoutScreen.tsx
    #### Change #2: B/app/services/cartService.ts
  #### C 变更
    #### Change #N: C/api/controller/CartController.java
Agent: V 用例按场景聚合 (不按仓分组):
  ## 验证用例 (Verification)
    ### V-1: 正常下单流程（跨仓协同）
    ### V-2: 库存不足异常（C 仓校验）
Agent: 对账表来源列: `../../tech_design/2026-07-03-checkout-flow/ards.md` (v4)
Agent: 基线摘要: B @ a1b2c3d (main) · C @ d4e5f6a (main)
```

## 安装 (Installation)

skill 定义随仓库分发, agent 直接读 `.codex/skills/to-plan/SKILL.md` 即可, **无需注册**。

需要把 skill 装进宿主 agent 的 skills 根目录时, 用仓内安装脚本：

```bash
bash <repo>/.codex/skills/install.sh                     # 默认 ~/.codex/skills/
bash <repo>/.codex/skills/install.sh --target <dir>      # 指定目标
bash <repo>/.codex/skills/install.sh --unregister        # 注销
```

## Related Skills

- `.codex/skills/to-prd/SKILL.md`：原始需求 → PRD
- `.codex/skills/to-tech-design/SKILL.md`：PRD → Tech Design（本 skill 的上游）
- `.codex/skills/validate-spec/SKILL.md`：跑全部校验脚本

## Cross-References

- <repo>/AGENTS.md §1.5（多仓 Plan 编排约定）
- <repo>/AGENTS.md §1.6（实现基线约定）
- <repo>/AGENTS.md §1.7（证据锚点约定）
- <repo>/AGENTS.md §3.1（工作流 Step 3）
- <repo>/schema/plan.md（多段模板）
- <repo>/schema/tech_design/（v4 TD 模板目录）
- <repo>/schema/tech_design/v3/（v3 存量 TD 模板目录）
- <repo>/scripts/check-md-schema.sh（v4 / v3 双模式校验）
- <repo>/scripts/check-traceability.sh（双模式校验）
- <repo>/HOW_TO_USE.md（完整工作流）