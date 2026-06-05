# Plan(实施计划)

> Layer 3 — 可执行的变更清单 + 验证用例。

## 文件夹结构

```
plan/
├── README.md
└── {YYYY-MM-DD}-{topic}/      ← 按功能组织的子文件夹
    └── {topic}.md             ← 内容文件,文件名简化为功能名
```

**子文件夹命名**: `{YYYY-MM-DD}-{简短主题}`
**文件命名**: `{简短主题}.md`

## 放什么

- 变更清单: 每个文件 + 变更描述(新增/修改/删除) + 策略约束
- 验证用例 (V1, V2...) — Given/When/Then,在 TDD 阶段自动化执行
- 业务约束 + 开发约束
- 7 项完成检查

## 模板

见 [schema/plan.md](../schema/plan.md)

## 下一步

按 Plan 进入 TDD 循环(Red → Green → Refactor),完成后 prd 状态变为 Implemented。
