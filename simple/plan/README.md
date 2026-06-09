# Plan(实施计划)

> Layer 3 — 可执行的变更清单 + 验证用例。

## 文件夹结构

```
plan/
├── README.md
└── {YYYY-MM-DD}-{topic}/      ← 日期和 topic 与来源 Tech Design 文件夹名完全一致
    └── {topic}.md             ← 内容文件，文件名与文件夹 topic 一致
```

**命名规则**:
- 子文件夹：`{YYYY-MM-DD}-{topic}`，与来源 `tech_design/{YYYY-MM-DD}-{topic}/` 对应
- `{topic}` 使用小写连字符，如 `order-flow`、`member-login`、`app-update`

## 放什么

- **变更清单 (Change #1, #2...)** — 每个文件一个条目，包含：
  - 文件路径（具体到文件名）
  - 遵循决策（引用 KD 编号）
  - 变更描述（新增/修改/删除，用文字，不写代码）
  - 策略约束（怎么做、不做什么）
  - 验证引用（引用 V 用例编号）
- **验证用例 (V1, V2...)** — Given/When/Then，Then 必须可被自动化断言，TDD 阶段执行
  - 必须覆盖：正常路径 + 异常场景 + 边界场景
- **业务约束** — 前置条件 / 不变量 / 后置条件 / 副作用
- **开发约束** — 并发 / 事务边界 / 幂等性 / 重试 / 超时
- **完成检查（7 项）** — 全部勾选后 Plan 状态变为 `Executed`

> ⚠️ Plan 是「实施指南」，不是「替代实现」。变更描述只写策略和约束，完整代码在 TDD 阶段产出。

## 内部相对路径

引用 Tech Design 和 PRD 使用：`../../tech_design/...` 和 `../../prd/...`（两级 `../`）

## 模板

见 [schema/plan.md](../schema/plan.md)

## 状态

| 状态 | 含义 |
|------|------|
| Ready | 可执行，进入 TDD 阶段 |
| Executed | 所有 Change 完成，V 用例全部通过，完成检查全部勾选 |

## 下一步

按 Plan 进入 TDD 循环（Red → Green → Refactor）：
1. 取一个 V 用例，写失败测试（Red）
2. 写最少代码让测试通过（Green）
3. 优化代码，保持测试通过（Refactor）

所有 V 用例通过后：
- Plan 状态 → `Executed`
- PRD 状态 → `Implemented`
