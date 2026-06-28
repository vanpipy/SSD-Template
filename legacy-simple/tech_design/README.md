# Tech Design(技术设计)

> Layer 2 — 关键决策、数据模型、API 契约、场景映射。

## 文件夹结构

```
tech_design/
├── README.md
└── {YYYY-MM-DD}-{topic}/      ← 日期与来源 PRD 文件夹一致，topic 使用小写连字符
    └── {topic}.md             ← 内容文件，文件名与文件夹 topic 一致
```

**命名规则**:
- 子文件夹：`{YYYY-MM-DD}-{topic}`，如 `2026-06-09-order-flow`
- `{YYYY-MM-DD}` 取自对应 PRD 的文件夹名（`prd/2026-06-09-processed/` → `2026-06-09`）
- `{topic}` 使用小写连字符，如 `order-flow`、`member-login`、`app-update`
- **日期前缀不可省略**，否则 Step 3（Plan）提示词无法正确匹配输入路径

## 放什么

- **关键决策 (KD-1, KD-2...)** — Context / Decision / Alternatives / Rationale / Enforced by
  - 触发条件：存在 ≥2 个可行方案的设计选择，必须记录为 KD
- **数据模型** — 字段、类型、约束，标注关联的 PRD 场景
- **API 契约** — 端点、请求/响应、前置条件、后置条件、副作用
- **场景映射** — PRD 每个场景 → 组件 / 动作 / 数据模型（**不允许遗漏任何 PRD 场景**）
- **指标** — 具体数字（如 `P99 < 500ms`），不接受模糊描述
- **降级策略** — 每个外部接口调用需对应一条降级策略
- **错误处理** — 错误码、含义、HTTP 状态、处理方式

## 内部相对路径

引用来源 PRD 使用：`../../prd/{YYYY-MM-DD}-processed/{topic}.md`（两级 `../`）

## 模板

见 [schema/tech_design.md](../schema/tech_design.md)

## 状态

| 状态 | 含义 |
|------|------|
| Ready | 设计完整，可进入 Plan 阶段 |
| Implemented | 对应 PRD 已完成 TDD |

## 下一步

基于 `Ready` 状态的 Tech Design，执行 Step 3：

```
请根据 prompts/plan.md 处理 tech_design/{YYYY-MM-DD}-{topic}/{topic}.md
```

完成后 PRD 和 Tech Design 状态同步变为 `Implemented`。
