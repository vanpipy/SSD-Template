# Tech Design(技术设计)

> Layer 2 — 关键决策、数据模型、API 契约、场景映射、时序图、质量保证。

## 文件夹结构

```text
tech_design/
├── README.md
└── {YYYY-MM-DD}-{topic}/      ← 按功能组织的子文件夹
    ├── README.md              ← 入口/索引(必填)
    ├── decisions.md           ← 关键决策(必填)
    ├── data-model.md          ← 数据模型(必填)
    ├── api-contracts.md       ← API 契约(必填)
    ├── scenario-mapping.md    ← 场景映射(必填)
    ├── interactions.md        ← 时序图(视情况)
    └── quality.md             ← 指标 + 降级 + 错误(必填)
```

**子文件夹命名**: `{YYYY-MM-DD}-{简短主题}`

## 子文件职责

| 文件 | 职责 | 必填 |
|------|------|------|
| README.md | 入口/索引 + 摘要 + 完成门 | 是 |
| decisions.md | 关键决策 (KD-1, KD-2...) | 是 |
| data-model.md | 数据模型 + 实体关系 | 是 |
| api-contracts.md | API 端点 + 请求/响应 | 是 |
| scenario-mapping.md | PRD 场景 → 组件/数据 映射 | 是 |
| interactions.md | 系统级 + 模块级时序图 (Mermaid) | 视情况 |
| quality.md | 指标 + 降级策略 + 错误处理 | 是 |

**`interactions.md` 必填条件**（任一满足）:
- 场景映射表行数 ≥ 5
- 涉及外部接口调用
- 涉及 ≥ 2 个内部模块协作
- 包含异步流程、状态机或重试逻辑

## 模板

见 [schema/tech_design/](../schema/tech_design/) 下的 7 个子模板

## 下一步

基于 Ready Tech Design,产出 `plan/{date}-{topic}/{topic}.md`。
