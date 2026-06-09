# Prompt: PRD → Tech Design

## 你的任务

读取指定的 Active 状态 PRD,按照 `schema/tech_design.md` 的格式,产出对应的 Tech Design 文件。

## 输入

支持两种调用模式:

**单文件模式**（处理指定 PRD）:
```
PRD 路径: prd/{YYYY-MM-DD}-processed/{topic}.md
输出路径: tech_design/{YYYY-MM-DD}-{topic}/{topic}.md
```

**文件夹模式**（批量处理文件夹内所有 PRD）:
```
PRD 文件夹: prd/{YYYY-MM-DD}-processed/
输出位置:   tech_design/{YYYY-MM-DD}-{topic}/   ← 日期取自输入文件夹名，{topic} 取自每个 PRD 文件名
```
文件夹模式下，对文件夹内每个 `.md` 文件依次执行本流程，每个文件产出一个独立的 Tech Design，输出路径为 `tech_design/{YYYY-MM-DD}-{topic}/{topic}.md`。

**可选参数**:
```
仓库地址: {project-path}   ← 可选，提供后可在设计阶段调查现有代码结构、复用已有模型和接口
```
若提供仓库地址，在第一步读取 PRD 后，先浏览仓库目录结构，了解现有代码组织方式，在后续决策和数据模型中优先与现有代码对齐。

## 前置条件

- PRD 状态必须为 `Active`
- PRD 的 Why / Goal / Scenarios 必须已填写完整

## 执行步骤

### 第一步: 读取 PRD,整理设计输入

读取 PRD 中的所有场景(Given/When/Then),列出:
- 涉及哪些实体/数据
- 涉及哪些系统交互(API 调用、事件、异步操作)
- 有哪些状态转移
- 有哪些异常需要处理

### 第二步: 识别并记录关键决策 (KD)

**触发条件: 凡是存在 ≥2 个可行方案的设计选择,都必须记录为 KD**

常见需要决策的点:
- 数据存储方式(本地缓存 vs 实时查询)
- 状态管理策略(前端持有 vs 后端控制)
- 错误处理方式(重试 vs 降级 vs 报错)
- 接口设计(聚合 vs 拆分)

每个 KD 必须填写:
```
Context:      什么场景下需要做这个决策,涉及哪些模块
Decision:     最终选择(一句话)
Alternatives: 列出备选方案及其优缺点
Rationale:    为什么选这个而不是其他
Enforced by:  code review / lint / 约定 / 测试
```

### 第三步: 定义数据模型

- 列出每个核心实体的字段、类型、约束
- 标注每个模型关联的 PRD 场景编号
- 明确约束条件(不可为空、唯一性、范围等)

### 第四步: 定义 API 契约

- 每个接口对应一个或多个 PRD 场景
- 必须填写: 端点、请求体、成功响应、失败响应
- 必须填写: 前置条件、后置条件、副作用

### 第五步: 完成场景映射

将 PRD 的每个 Given/When/Then 场景映射到具体的:
- 组件/模块
- 动作(调用哪个接口、触发哪个事件)
- 数据模型

**不允许遗漏任何 PRD 场景**

### 第六步: 填写指标和降级策略

**指标必须是具体数字,不接受模糊描述:**
- 禁止: "响应要快"
- 正确: "API 延迟 P99 < 500ms"

**降级策略必须覆盖关键异常场景:**
- 触发条件是什么
- 降级后的行为是什么
- 对用户的影响是什么

### 第七步: 检查完成门

产出前逐项确认:

- [ ] **关键决策** 每个有完整的 Context/Decision/Alternatives/Rationale/Enforced by
- [ ] **场景映射** 覆盖 PRD 中所有场景,无遗漏
- [ ] **指标** 有具体数字,无模糊描述
- [ ] **降级策略** 已定义,覆盖关键异常

## 注意事项

**命名规则**（必须严格遵守，影响 Step 3 能否正确匹配）:
- 输出文件夹格式：`tech_design/{YYYY-MM-DD}-{topic}/`，日期取自 PRD 文件夹名（如 `prd/2026-06-09-processed/` → 日期为 `2026-06-09`）
- 文件名与文件夹 topic 一致：`tech_design/2026-06-09-order-flow/order-flow.md`
- 内部引用 PRD 使用相对路径 `../../prd/{YYYY-MM-DD}-processed/{topic}.md`（两级 `../`）

**场景映射完整性**:
- 必须逐一检查 PRD 的每个 Given/When/Then 场景，场景映射表中一条都不能漏
- 遗漏场景会导致 Plan 的验证用例覆盖不完整，TDD 阶段会有盲区

**降级策略覆盖**:
- 每个外部接口调用都需要对应一条降级策略，包含触发条件、降级行为、业务影响

## 输出格式

严格按照 `schema/tech_design.md` 结构,状态设为 `Ready`。
