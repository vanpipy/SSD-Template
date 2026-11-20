# Plan(实施计划)

> Layer 3。可执行的变更清单 + 验证用例。

## 文件夹结构

```text
plan/
├── README.md
└── {YYYY-MM-DD}-{topic}/      ← 按功能组织的子文件夹
    └── {topic}.md             ← 内容文件,文件名 = 目录名里的 topic
```

**子文件夹命名**: `{YYYY-MM-DD}-{简短主题}`,小写连字符。
**文件命名**: `{简短主题}.md`,必须与目录名中的 topic 一致。

## 放什么

| 段 | 内容 |
|----|------|
| 变更索引 | 表格快速扫读(# / 文件路径 / 类型 / KD 引用 / V 引用 / 状态) |
| 变更清单 | 每个 Change 的变更描述(新增 / 修改 / 删除)+ 策略约束 + KD 引用 + V 引用 |
| TDD 执行流程 | mermaid 可视化 Red → Green → Refactor |
| 跨文件引用对账 | KD / SYS / MOD / FR / V 闭环检查 |
| 验证用例 (V-{n}) | Given / When / Then,正常路径 + 异常 + 边界 |
| 业务约束 | 前置 / 不变量 / 后置 / 副作用 |
| 开发约束 | 并发 / 事务 / 幂等性 / 重试 / 超时 |
| 完成检查 | 4 段:实现层 / 验证层 / 引用层 / 流程层 |

> ⚠️ **设计原则**:Plan 是「实施指南」,不是「替代实现」。变更描述用文字说明策略和约束,完整代码在 TDD 阶段产出。

## 多仓分仓编排

项目关联 ≥1 个外部代码仓时,变更清单**按仓分组**:

| 项 | 约定 |
|----|------|
| 分组标题 | `#### {仓库标识} 变更`,标识取自 [AGENTS.md](../AGENTS.md) §1.1 |
| Change 条目 | `#### Change #N: {标识}/{路径}`,路径**必须**带 `{标识}/` 前缀 |
| 验证用例 (V) | **不按仓分组**,按业务场景聚合,一个场景可横跨多仓 |

完整规则见 [AGENTS.md](../AGENTS.md) §1.5。

```markdown
## 变更清单

#### B 变更

> KD-1 / V-1 主要约束 B 仓的接口编排与入参校验

#### Change #1: `B/api/controller/SessionController.java`
**遵循决策**: KD-1
**验证**: V-1
```

> 0 代码仓项目不分仓。Change 直接列在 `## 变更清单` 下,视为单一分组。

## 状态

`Ready → Implemented`。0 关联代码仓时停留在 `Ready`,标记 "Awaiting TDD in external code repo"。

## 模板

见 [schema/plan.md](../schema/plan.md)

## 下一步

按 Plan 进入 TDD 循环(Red → Green → Refactor),完成后回写 PRD / Tech Design / Plan 三件套状态为 `Implemented`。
