# Prd(需求文档)

> Layer 0+1 — 原始需求输入 + 收敛后的 PRD。

## 目录结构

```
prd/
├── README.md
├── {YYYY-MM-DD}/              ← Layer 0: 原始需求文件夹（输入）
│   ├── raw-doc.md             ← 原始文档，保持原样，不修改
│   └── ...
└── {YYYY-MM-DD}-processed/   ← Layer 1: 收敛后的 PRD 文件夹（Step 1 输出）
    ├── {topic-a}.md           ← 功能单元 A 的 PRD
    ├── {topic-b}.md           ← 功能单元 B 的 PRD
    └── ...
```

**命名规则**:
- 原始文件夹：`{YYYY-MM-DD}/`（需求产生日期）
- 收敛输出文件夹：`{YYYY-MM-DD}-processed/`（固定后缀 `-processed`，日期与原始文件夹一致）
- PRD 文件名：`{topic}.md`，小写连字符，如 `order-flow.md`、`member-login.md`

## 两层说明

### Layer 0 — 原始需求（`{YYYY-MM-DD}/`）

存放未经整理的原始材料：
- 传统 PRD / 产品方案文档
- 会议纪要
- 流程图（SVG / Mermaid）
- 用户抱怨 / Bug 报告

**原则**: 原始文件保持原样，不修改，只用于读取。

### Layer 1 — 收敛 PRD（`{YYYY-MM-DD}-processed/`）

由 Step 1（`prompts/prd.md`）从 Layer 0 提炼产出：
- 一个原始文件可能拆分为多个 PRD（一个 PRD = 一个独立可交付的功能单元）
- 每个 PRD 状态设为 `Active`，可直接进入 Tech Design 阶段
- 严格按照 `schema/prd.md` 模板结构

## PRD 状态流转

```
Active → (Tech Design + Plan + TDD 完成) → Implemented
Active → (需求废弃) → Deprecated
```

- **Active**: 内容完整，可进入后续流程
- **Implemented**: 所有 V 用例通过，功能已上线
- **Deprecated**: 需求已废弃，不再执行

> `Draft` 状态仅用于内容尚未完整的 PRD；通过 `prompts/prd.md` 自动产出的 PRD 直接设为 `Active`。

## 模板

见 [schema/prd.md](../schema/prd.md)

## 下一步

基于 `Active` 状态的 PRD，执行 Step 2：

```
请根据 prompts/tech_design.md 处理 prd/{YYYY-MM-DD}-processed 的文档
```
