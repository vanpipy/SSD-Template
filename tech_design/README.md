# Tech Design(技术设计)

> Layer 2 — 关键决策、数据模型、API 契约、场景映射。

## 文件夹结构

```
tech_design/
├── README.md
└── {YYYY-MM-DD}-{topic}/      ← 按功能组织的子文件夹
    └── {topic}.md             ← 内容文件,文件名简化为功能名
```

**子文件夹命名**: `{YYYY-MM-DD}-{简短主题}`
**文件命名**: `{简短主题}.md`

## 放什么

- 关键决策 (KD-1, KD-2...) — Context/Decision/Alternatives/Rationale/Enforced by
- 数据模型 + API 契约
- PRD 场景到组件/动作/数据模型的映射
- 指标 + 降级策略 + 错误处理

## 模板

见 [schema/tech_design.md](../schema/tech_design.md)

## 下一步

基于 Ready Tech Design,产出 `plan/{date}-{topic}/{topic}.md`。
