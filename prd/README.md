# PRD(产品需求)

> Layer 1 — 经过分析和收敛后形成的产品需求。

## 文件夹结构

```
prd/
├── README.md
└── {YYYY-MM-DD}-{topic}/      ← 按功能组织的子文件夹
    └── {topic}.md             ← 内容文件,文件名简化为功能名
```

**子文件夹命名**: `{YYYY-MM-DD}-{简短主题}`
**文件命名**: `{简短主题}.md`

## 放什么

- 产品的"为什么"、"目标"、"场景"、"不在范围"
- 状态机: Draft → Active → Implemented | Deprecated

## 模板

见 [schema/prd.md](../schema/prd.md)

## 下一步

基于 Active PRD,产出 `tech_design/{date}-{topic}/{topic}.md`。
