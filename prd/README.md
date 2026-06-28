# PRD(产品需求)

> **Layer 1** — 收敛后的产品需求文档。`prd/{date}/` 是 Layer 1 的**素材存放区**(非独立 Layer)。

## 架构层(共 3 层)

| Layer | 位置 | 状态 |
|-------|------|------|
| Layer 1 | `prd/{date}-processed/` | Ready → Implemented |
| Layer 2 | `tech_design/{date}-{topic}/` | Ready |
| Layer 3 | `plan/{date}-{topic}/{topic}.md` | Ready → Implemented |

> `prd/{date}/` 是 Layer 1 的**素材存放区**,**不**是独立 Layer。

## 文件夹结构

```text
prd/
├── README.md
├── {YYYY-MM-DD}/              ← 素材区(只读,非 Layer)
│   ├── {source-1}.md
│   ├── {source-2}.md
│   └── {source-3}.md
└── {YYYY-MM-DD}-processed/    ← Layer 1: PRD(Step 1 产出)
    ├── {topic-1}.md
    └── {topic-2}.md
```

**素材区文件命名**: `{来源描述}.md`,可多个
**PRD 命名**: `{简短主题}.md`,一个日期可多个 PRD(1:N 关系)

## 转换关系(素材 → Layer 1)

- **1:1**: 一份原始文档对应一个 PRD
- **1:N**: 一份原始文档(如 `history-apis.md`)拆成多个 PRD
- **N:1**: 多份原始文档合成一个 PRD
- **N:N**: 更复杂的 1→N→M 组合

## 放什么(Layer 1 PRD)

- 产品的"为什么"、"目标"、"场景"、"不在范围"
- 状态机: Draft → Ready → Implemented | Deprecated

## 模板

见 [schema/prd.md](../schema/prd.md)

## 下一步

基于 Ready PRD,产出 `tech_design/{date}-{topic}/`(多文件结构,见 [tech_design/README.md](../tech_design/README.md))。
