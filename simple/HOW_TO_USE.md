# SSD-Template 使用指南

## 核心理念

### Why-First

在写任何代码前,回答四个问题:

1. **为什么有这个流程?** — 它解决什么问题?
2. **具体解决什么问题?** — 问题是什么?
3. **代码为什么这样设计?** — 决策依据是什么?
4. **这应该放在哪里?** — 哪个组件负责?

### Given/When/Then

用自然语言描述行为:

- **Given** — 前置条件
- **When** — 触发动作
- **Then** — 预期结果

### 复审机制

每个 PRD 定期复审,防止 feature rot:

- **仍然重要?** — Yes / No / 重新定义
- **应当保留?** — Yes / No
- **可以删除?** — Yes / No

### Harness 原则

工作流是固定的 harness,不是灵活的建议:

- 5 步必须走完,不简化
- 每步有明确的"完成门"
- 违反则失败,不跳过

## 如何使用本指南

### 谁来读

本指南面向 AI agent 和开发者,用于规范从需求到代码的完整流程。

### 从哪里开始

当有新的需求时:

1. **准备原始需求** — 将原始文档放入 `prd/{YYYY-MM-DD}/`，执行 Step 1 产出 PRD 到 `prd/{YYYY-MM-DD}-processed/{topic}.md`
2. **创建 tech_design** — 执行 Step 2，产出 `tech_design/{YYYY-MM-DD}-{topic}/{topic}.md`
3. **创建 plan** — 执行 Step 3，产出 `plan/{YYYY-MM-DD}-{topic}/{topic}.md`
4. **执行 TDD** — 按 Plan 的验证用例进入 Red → Green → Refactor，完成后 PRD 状态变为 `Implemented`

### 命名规范

三层目录使用**完全一致**的命名规则，确保 Step 2 输出能直接作为 Step 3 输入：

```
prd/{YYYY-MM-DD}-processed/{topic}.md        ← Step 1 输出
tech_design/{YYYY-MM-DD}-{topic}/{topic}.md  ← Step 2 输出（日期取自 PRD 文件夹名）
plan/{YYYY-MM-DD}-{topic}/{topic}.md         ← Step 3 输出（日期和 topic 与 tech_design 一致）
```

**关键约束**：
- `{YYYY-MM-DD}` 三层保持相同日期（需求产生日期）
- `{topic}` 使用小写连字符，如 `order-flow`、`member-login`
- tech_design 和 plan 的文件夹名必须带日期前缀，否则 Step 3 提示词无法匹配输入

### 快捷调用方式

每一步直接引用对应 prompt 文件 + 指定输入路径:

```
# Step 1: 原始需求 → PRD（文件夹级，批量处理）
请根据 prompts/prd.md 处理 prd/{YYYY-MM-DD} 的文档

# Step 2: PRD → Tech Design（文件夹级，批量处理文件夹内所有 PRD）
请根据 prompts/tech_design.md 处理 prd/{YYYY-MM-DD}-processed 的文档, 仓库地址 {project-path}

# Step 2: PRD → Tech Design（单文件，处理指定 PRD）
请根据 prompts/tech_design.md 处理 prd/{YYYY-MM-DD}-processed/{topic}.md, 仓库地址 {project-path}

# Step 3: Tech Design → Plan（文件夹级，批量处理文件夹内所有 Tech Design）
请根据 prompts/plan.md 处理 tech_design/{YYYY-MM-DD}-{topic} 的文档, 仓库地址 {project-path}

# Step 3: Tech Design → Plan（单文件，处理指定 Tech Design）
请根据 prompts/plan.md 处理 tech_design/{YYYY-MM-DD}-{topic}/{topic}.md, 仓库地址 {project-path}
```

### 遇到问题时

- **不确定填什么?** → 查看对应 schema 模板 [schema/prd.md](schema/prd.md)
- **不知道覆盖哪些场景?** → 参考下方完成检查清单
- **不确定一个需求走多深?** → 默认走完 5 步,不简化

### 状态流转

```
prd       : Active ──────────────────────────────────→ Implemented
                                                         (TDD 全部 V 用例通过后)
            Active → Deprecated (需求废弃)

tech_design: Draft → Ready ──────────────────────────→ (与 PRD 同步变为 Implemented)

plan      : Draft → Ready ────────────────────────────→ Executed
                                                         (所有 Change 完成、V 用例通过后)
```

| 层 | 状态 | 含义 |
|----|------|------|
| PRD | Active | 内容完整，可进入 Tech Design |
| PRD | Implemented | TDD 完成，功能已上线 |
| PRD | Deprecated | 需求已废弃 |
| Tech Design | Ready | 设计完整，可进入 Plan |
| Plan | Ready | 可执行，进入 TDD 阶段 |
| Plan | Executed | 所有 V 用例通过，完成检查全部勾选 |

> `Draft` 状态仅用于人工手写时内容尚未完整的情况；通过 prompts 自动产出的文件直接设为 `Active`（PRD）或 `Ready`（Tech Design / Plan）。

## 目录组织

```text
{project-root}/
├── prd/              # Layer 0+1: 原始需求 + 收敛后的 PRD
├── tech_design/      # Layer 2: 技术设计
├── plan/             # Layer 3: 实施计划
├── schema/           # 模板定义
└── prompts/          # 各步骤执行提示词
```

**prd/ 内部结构**（两层）:

```text
prd/
├── {YYYY-MM-DD}/              ← Layer 0: 原始需求（输入，保持原样）
│   └── raw-doc.md
└── {YYYY-MM-DD}-processed/   ← Layer 1: 收敛后的 PRD（Step 1 输出，Active 状态）
    ├── {topic-a}.md
    └── {topic-b}.md
```

**tech_design/ 和 plan/ 命名**:

```text
tech_design/
└── {YYYY-MM-DD}-{topic}/      ← 日期与 prd/{YYYY-MM-DD}-processed/ 一致
    └── {topic}.md

plan/
└── {YYYY-MM-DD}-{topic}/      ← 日期与 tech_design 文件夹一致
    └── {topic}.md
```

> `{topic}` 统一使用小写连字符，如 `order-flow`、`member-login`、`app-update`。

## 三步工作流

```mermaid
flowchart LR
    A[原始需求] --> B[prd/id/login.md Active]
    B --> C[tech_design/id/tech_design.md Ready]
    C --> D[plan/id/plan.md Ready]
    D --> E[TDD: Red → Green → Refactor]
    E --> F[src/ + 通过的测试]
    F --> G[prd 状态 → Implemented]
```

### Step 1: 发现 + 收敛 (原始需求 → PRD)

将原始需求(用户抱怨、会议纪要、需求文档)整理收敛,在 `prd/` 产出 PRD,状态从 **Draft → Active**。

**PRD 必填**:

- **为什么**: 一句话说明问题和目的
- **目标**: 可验证的成功标准
- **场景**: Given/When/Then,覆盖正常路径 + 至少一个异常
- **不在范围**: 明确不做的内容
- **复审**: still_matters / should_keep / can_delete(防止 feature rot)

#### 如何从原始文件加工成 PRD

当 `prd/` 下已有原始文档(传统 PRD、流程图、会议纪要等),按以下步骤提炼:

**1. 读取原始文件,识别输入类型**

```
原始输入可能是:
- 传统 PRD(含接口规范、页面状态矩阵、流程图)
- 会议纪要 / 用户抱怨
- 流程图(SVG / Mermaid)
- 技术方案文档
```

**2. 提炼 Why — 问"这个功能为什么存在"**

```
从原始文档中找到:
- 业务背景 / 产品定位段落
- 用户痛点描述
- 提炼成一句话: 这个 PRD 是为了 [问题] 而存在,期望达成 [目的]
```

**3. 提炼 Goal — 问"交付什么可验证的结果"**

```
从原始文档中找到:
- 功能清单 / 验收标准
- 转化为可观察/可测量的勾选项
- 避免: "支持XX"、"完成XX" 等模糊描述
- 正确: "用户输入手机号后,系统在2s内返回会员信息"
```

**4. 提炼 Scenarios — 将流程转为 Given/When/Then**

```
从原始文档中找到:
- 业务流程图的每条路径
- 页面状态矩阵的每个状态转移
- 异常场景 / 错误处理

每条路径对应一个场景:
  Given [用户所处状态 + 前置条件]
  When  [用户执行的动作]
  Then  [系统返回的可验证结果]
  But   [异常时的处理](可选)
```

**5. 确定 Out of Scope — 明确不做什么**

```
从原始文档中找到:
- 未展开的功能模块(框架阶段)
- 依赖其他系统但不在本次交付范围的部分
- 明确列出,防止范围蔓延
```

**6. 一个原始文件 vs 多个 PRD**

```
原则: 一个 PRD 对应一个独立可交付的功能单元

如果原始文件包含多个功能模块(如15个流程):
- 每个核心流程单独产出一个 PRD 文件
- 放在同一子文件夹下: prd/{date}-{topic}/
- 命名: member-login.md / member-register.md / order-flow.md
```

### Step 2: 设计 + 计划 (PRD → Tech Design → Plan)

基于 Active 状态的 PRD,产出:

- `tech_design/{date}-{topic}/{topic}.md` (**Ready**): 关键决策 + 数据模型 + API 契约 + 场景映射
- `plan/{date}-{topic}/{topic}.md` (**Ready**): 变更清单 + 验证用例 + 业务约束 + 开发约束

**Tech Design 必填**:

- **关键决策 (KD)**: Context / Decision / Alternatives / Rationale / Enforced by
- **场景映射**: PRD 场景 → 组件/动作/数据模型
- **指标**: 具体数字(不是模糊描述)
- **降级策略**: 异常情况下的行为

**Plan 必填**:

- **变更清单**: 每个文件的"变更描述"(新增/修改/删除什么) + "策略约束"(怎么做、不做什么)
- **验证用例 (V)**: Given/When/Then,TDD 阶段执行
- **业务约束**: 前置/不变量/后置/副作用
- **完成检查**: 7 项勾选

> ⚠️ **设计原则**: Plan 是"实施指南",不是"替代实现"。
> 变更描述用文字说明策略和约束,指导参与的 agent 写出代码。
> 完整代码在 TDD 阶段产出,不是提前写在 Plan 里。

### Step 3: 执行 (Plan → TDD → src/)

按 Plan 进入 TDD 循环:

1. **Red** — 写一个失败的测试(V 用例)
2. **Green** — 写最少代码让测试通过
3. **Refactor** — 优化代码,保持测试通过

完成所有 V 用例后,prd 状态变为 **Implemented**。

## 何时升级

> 简化原则: 默认所有内容用 3 个 schema。只在以下情况考虑升级。

| 触发条件 | 升级方案 | 状态 |
|---------|---------|------|
| 决策影响 ≥3 个 PRD 或长期架构 | 独立 ARD | v2 引入 |
| 多需求聚合管理 | batch-overview | v2 引入 |
| 需要可执行 BDD 框架 | 已在 PRD/Plan 内联 Given/When/Then,无需独立 | — |

## 完成检查清单

### 每个 PRD

- [ ] **为什么** 用具体问题陈述回答
- [ ] **目标** 有可验证的成功标准
- [ ] **场景** 覆盖正常 + 至少一个异常
- [ ] **不在范围** 明确说明
- [ ] **复审** 已填写

### 每个 Tech Design

- [ ] **关键决策** 已定义(每个有 Context/Decision/Alternatives/Rationale/Enforced by)
- [ ] **场景映射** 覆盖所有 PRD 场景
- [ ] **指标** 有具体数字
- [ ] **降级策略** 已定义

### 每个 Plan

- [ ] **变更清单** 完整(每个 Change 有 KD 引用 + 验证引用)
- [ ] **验证用例** 覆盖正常 + 异常 + 边界
- [ ] **完成检查** 全部勾选

## 经验与注意事项

> 本节记录实际执行工作流时积累的关键观察，帮助后续 AI agent 避免重复踩坑。

### Step 1 → Step 2 衔接

- PRD 产出后放入 `prd/{YYYY-MM-DD}-processed/`，**文件夹名带 `-processed` 后缀**，这是 Step 2 提示词的输入格式，不要省略
- 一个原始文件可能产出多个 PRD（如本次 7 个 PRD 来自 2 个原始文档），每个 PRD 独立命名

### Step 2 → Step 3 衔接

- Tech Design 文件夹名必须是 `tech_design/{YYYY-MM-DD}-{topic}/`，**日期前缀不可省略**
- 日期取自对应 PRD 的文件夹名（`prd/2026-06-09-processed/` → 日期为 `2026-06-09`）
- Step 3 提示词按文件夹名匹配，如输入 `tech_design/2026-06-09-order-flow`，则输出到 `plan/2026-06-09-order-flow/order-flow.md`

### Tech Design 质量要点

- **KD（关键决策）是核心**：每个有 ≥2 个可行方案的设计选择都必须记录为 KD，不可跳过
- **场景映射不能遗漏**：PRD 中每一个 Given/When/Then 场景都必须出现在场景映射表中，漏掉会导致 Plan 的验证用例不完整
- **指标必须是具体数字**：`< 500ms`、`≥ 99%`，不接受"响应要快"这类模糊描述
- **降级策略需覆盖每个外部依赖**：每个调用的外部接口都要有对应的超时和降级行为

### Plan 质量要点

- **Change 粒度到文件级**：每个需要新增或修改的文件对应一个 Change 条目，路径具体到文件名
- **验证用例三类缺一不可**：正常路径 + 异常场景 + 边界场景，Then 必须可被自动化断言
- **Plan 里不写代码**：只写策略和约束（"使用 EncryptedSharedPreferences"），完整代码在 TDD 阶段产出
- **每个 Change 必须双向引用**：引用 KD 编号（来自 Tech Design）+ 引用 V 用例编号（验证闭环）

### 文件路径约定

- Tech Design 内部引用 PRD 使用相对路径：`../../prd/2026-06-09-processed/{topic}.md`（因为 tech_design 是两级目录）
- Plan 内部引用 Tech Design 和 PRD 同理使用 `../../` 相对路径

### 批量处理 vs 单文件处理

- **优先单文件处理**：每次处理一个文件，质量更高、更专注
- **文件夹级批量处理**：适合同一批需求统一过一遍，但要检查每个文件的场景映射是否完整
- 提供仓库地址时，agent 会先浏览目录结构再设计，产出的文件路径更贴近真实代码结构

---

## 相关文件

| 文件 | 用途 |
|------|------|
| [schema/prd.md](schema/prd.md) | PRD 模板 |
| [schema/tech_design.md](schema/tech_design.md) | Tech Design 模板 |
| [schema/plan.md](schema/plan.md) | Plan 模板 |
| [prompts/prd.md](prompts/prd.md) | 原始需求 → PRD 执行提示词 |
| [prompts/tech_design.md](prompts/tech_design.md) | PRD → Tech Design 执行提示词 |
| [prompts/plan.md](prompts/plan.md) | Tech Design → Plan 执行提示词 |
| [new-factors.md](new-factors.md) | 深度概念参考 |
