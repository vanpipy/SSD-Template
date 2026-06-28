# Prompt: Tech Design → Plan

## 你的任务

读取指定的 Ready 状态 Tech Design(以及对应 PRD),按照 `schema/plan.md` 的格式,产出可执行的 Plan 文件。

## 输入

支持两种调用模式:

**单文件模式**（处理指定 Tech Design）:
```
Tech Design 路径: tech_design/{YYYY-MM-DD}-{topic}/{topic}.md
PRD 路径:        prd/{YYYY-MM-DD}-processed/{topic}.md
输出路径:        plan/{YYYY-MM-DD}-{topic}/{topic}.md
```

**文件夹模式**（批量处理文件夹内所有 Tech Design）:
```
Tech Design 文件夹: tech_design/{YYYY-MM-DD}-{topic}/
对应 PRD 文件夹:   prd/{YYYY-MM-DD}-processed/   ← 按文件名匹配对应 PRD
输出位置:          plan/{YYYY-MM-DD}-{topic}/   ← 日期和 {topic} 与 Tech Design 文件夹名一致
```
文件夹模式下，对文件夹内每个 `.md` 文件依次执行本流程，同时从 `prd/{YYYY-MM-DD}-processed/` 中查找同名 PRD 文件（如 `order-flow.md` 对应 `prd/.../order-flow.md`），输出路径为 `plan/{YYYY-MM-DD}-{topic}/{topic}.md`。

**可选参数**:
```
仓库地址: {project-path}   ← 可选，提供后可调查现有文件结构，制定更准确的变更清单（Change 条目中的文件路径）
```
若提供仓库地址，在第一步读取 Tech Design 后，先浏览仓库目录结构，将变更清单中的文件路径对应到真实存在的文件。

## 前置条件

- Tech Design 状态必须为 `Ready`
- PRD 状态必须为 `Active`

## 执行步骤

### 第一步: 读取 Tech Design 和 PRD

理解:
- 所有 KD(关键决策)及其约束
- 所有数据模型和 API 契约
- 所有场景映射
- PRD 中的 Goal 和 Scenarios(用于后续验证用例)

### 第二步: 列出变更清单 (Changes)

**原则: Plan 是实施指南,不是替代实现。用文字描述策略和约束,不写完整代码。**

每个需要变更的文件对应一个 Change 条目:
- **文件路径**: 具体到文件
- **遵循决策**: 引用对应的 KD 编号
- **变更描述**: 新增/修改/删除什么(用文字,不用代码)
- **策略约束**: 怎么做、不做什么、为什么
- **验证**: 引用对应的 V 用例编号

**必须覆盖 Tech Design 中所有场景映射涉及的文件。**

### 第三步: 编写验证用例 (V)

从 PRD 的 Scenarios 和 Tech Design 的场景映射中提取,格式:

```
Given [具体的前置状态]
When  [具体的触发动作]
Then  [具体的可验证结果]
```

**必须覆盖三类:**
- V 正常路径: 主流程走通
- V 异常场景: 错误输入、服务失败、网络中断等
- V 边界场景: 临界值、空数据、并发等

Then 必须可以被自动化测试断言,禁止模糊描述。

### 第四步: 填写业务约束

从 PRD 和 Tech Design 中提取:
- **前置条件**: 执行前系统/数据必须满足的条件
- **不变量**: 执行过程中始终保持为真的条件
- **后置条件**: 成功后系统状态的变化
- **副作用**: 触发的异步操作、事件、通知

### 第五步: 填写开发约束

根据 Tech Design 的 KD 和 API 契约填写:

| 约束 | 值 |
|------|-----|
| 并发 | 是否需要加锁/队列 |
| 事务边界 | 哪些操作必须原子 |
| 幂等性 | 如何保证重复请求安全 |
| 重试 | 是否允许、最大次数、间隔 |
| 超时 | 各接口超时设置 |

### 第六步: 检查完成门

产出前逐项确认:

- [ ] **变更清单** 完整,每个 Change 有 KD 引用 + V 用例引用
- [ ] **验证用例** 覆盖正常 + 异常 + 边界,Then 可被断言
- [ ] **业务约束** 前置/不变量/后置/副作用均已填写
- [ ] **开发约束** 并发/事务/幂等性/重试/超时均已填写
- [ ] **完成检查** 7 项全部可勾选

## 注意事项

**命名规则**:
- 输出文件夹格式：`plan/{YYYY-MM-DD}-{topic}/`，日期和 topic 与输入的 Tech Design 文件夹名完全一致
- 文件名与 topic 一致：`plan/2026-06-09-order-flow/order-flow.md`
- 内部引用使用相对路径 `../../tech_design/...` 和 `../../prd/...`（两级 `../`）

**Change 粒度**:
- 每个 Change 对应一个具体文件（精确到文件名），不能写"修改 Service 层"这种模糊粒度
- 提供仓库地址时，文件路径应对应真实存在的文件；无仓库地址时，按合理的包结构推断路径
- 每个 Change 必须双向引用：`遵循决策: KD-{n}` + `验证: V{n}`，引用缺失视为不完整

**验证用例质量**:
- Then 必须可被自动化断言，示例：
  - 正确：`UpdateConfig.pendingUpdate 重置为 false，本地 APK 文件被删除`
  - 错误：`系统正常运行`
- 验证用例编号与 Change 中的引用必须一一对应，不能有引用但无对应用例

**不写代码**:
- Plan 中只描述策略和约束，不写具体实现代码
- 示例：写 "使用 EncryptedSharedPreferences 存储，`pendingUpdate=true` 时四字段必须原子写入"，不写具体代码

## 输出格式

严格按照 `schema/plan.md` 结构,状态设为 `Ready`。

> ⚠️ 提醒: 完整代码在 TDD 阶段产出,Plan 里只写策略和约束,不写实现代码。
