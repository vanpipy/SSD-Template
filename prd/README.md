# PRD(产品需求)

> Layer 0 + Layer 1 — 原始需求 + 收敛后的 PRD(双层结构)。

## 文件夹结构

```text
prd/
├── README.md
├── {YYYY-MM-DD}/              ← Layer 0: 原始需求(多文件,只读)
│   ├── {source-1}.md
│   ├── {source-2}.md
│   └── {source-3}.md
└── {YYYY-MM-DD}-processed/    ← Layer 1: 收敛后的 PRD(Step 1 产出)
    ├── {topic-1}.md
    └── {topic-2}.md
```

**日期文件夹命名**: `{YYYY-MM-DD}/` (原始) / `{YYYY-MM-DD}-processed/` (PRD)
**原始文件命名**: `{来源描述}.md`,可多个
**PRD 命名**: `{简短主题}.md`,一个日期可多个 PRD(1:N 关系)

## 两层职责

| 层 | 位置 | 状态 | 职责 |
|----|------|------|------|
| Layer 0 | `prd/{date}/` | 只读 | 原始输入(会议纪要、用户反馈、流程图等) |
| Layer 1 | `prd/{date}-processed/` | Active | 收敛后的 PRD,经过 Step 1 加工 |

## 转换关系

- **1:1**: 一份原始文档对应一个 PRD
- **1:N**: 一份原始文档(如 `history-apis.md`)拆成多个 PRD
- **N:1**: 多份原始文档合成一个 PRD
- **N:N**: 更复杂的 1→N→M 组合

## 放什么(Layer 1 PRD)

- 产品的"为什么"、"目标"、"场景"、"不在范围"
- 状态机: Draft → Active → Implemented | Deprecated

## 模板

见 [schema/prd.md](../schema/prd.md)

## 下一步

基于 Active PRD,产出 `tech_design/{date}-{topic}/`(多文件结构,见 [tech_design/README.md](../tech_design/README.md))。
