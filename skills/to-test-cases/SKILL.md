---
name: to-test-cases
description: 从 PRD + Tech Design 生成黑盒测试用例（Markdown）。触发词：测试用例、test cases、QA、验收标准。v2.4：适配 TD v4 四子文件结构（README/ards/apis/data-model），存量 v3 九子文件按对应关系读取。v2.3：PRD But 逐条覆盖 + 环境边界 Checklist + 默认值用例 + OQ 收敛用例。
skill-type: spec
version: 2.4
type: skill
skill-role: procedure
---

# to-test-cases

> **角色**：资深测试架构师，精通黑盒测试方法论、前后端分离架构测试、端到端链路验证。

从 Ready 状态的 PRD + Tech Design 生成结构化黑盒测试用例（Markdown，模板 `schema/test_case.md`），产出到 `test_cases/{YYYY-MM-DD}/`。

> **前缀路由**：README 登记表 `TEST-*` 前缀条目以本 skill 为流水线入口——测试类素材（`material/{date}/{file}.md`）可直接转化为 Layer 4 用例，元信息「来源」行指向素材路径（check-traceability T9 已支持 `material/*` 前缀）。

> **v2.1 机制对齐（2026-08-06）**：
> - 输出口径由 YAML 改为 **Markdown**（对齐全部存量与 check-md-schema 校验）
> - 状态枚举与三件套统一：**Draft / Ready / Implemented / Deprecated**（独立生命周期，不与三件套联动）
> - 层定位：来源 = **PRD + Tech Design**；产出是 **Plan 的参考比照对象**（V 用例 ↔ TC 用例同主题互为参照）
> - Step 6 收尾强制：`scripts/sync-test-index.sh` 再生成索引 + `scripts/check-md-schema.sh <新文件>` 校验

> **v2.3 覆盖强化（2026-08-07，pay-voice 审计教训）**：
> - **But 分支是一等测试点**：先 `grep -c '\*\*But\*\*'` 数出 PRD 的 But 总数，每个 But ≥1 条用例，不允许丢失（系统静音/弱网这类边界都住在 But 里）
> - **环境边界 Checklist**：网络（弱网/离线/切换）、系统声道（静音/最低音量）、生命周期（重启/后台）、权限角色、数据边界——逐维对照 PRD 的 But
> - **默认值用例**：PRD Goal 显式默认值（如总开关默认开/音量默认 60）必须有初始状态验证用例
> - **OQ 收敛用例**：TD ards.md「探索记录」的 OQ 收敛方式若点名测试用例（如离线冒烟），必须生成对应用例并标注 OQ 关联（存量 v3 TD：exploration.md）

## 流程

```
Step 1: Confirming          → 确认输入/审核/平台/范围
Step 2: Resolving Business  → 定位/创建 test-business/{product}/
Step 3: Analyzing           → 提取功能点 + 用户确认（源文档只读一次，后续靠索引）
Step 4: Generating          → 三层用例(前端/后端/E2E) + 优先级 + 平台特异性
Step 5: Reviewing           → 4角色独立评审(≤3轮) + 用户确认
Step 6: Writing             → 输出 Markdown 用例 + 要点 + 索引再生成 + 知识库回写 + 校验
```

每步详细指令见 `prompts/step{N}-*.md`，执行到该步时读取。

## 使用

```
/to-test-cases <prd-path> <tech-design-dir>
/to-test-cases prd/2026-07-03/login.md tech_design/2026-07-03-login/
/to-test-cases prd/2026-07-03/login.md --analyze
/to-test-cases prd/2026-07-03/login.md --smoke
```

只给一个参数时自动推断另一个（同 date-topic）。

## 执行范围

| 范围 | 触发 | 执行步骤 | 产出 |
|------|------|---------|------|
| **full**（默认）| 无关键词 | Step 1-6 全走 | 主用例 .md + 要点 + 索引再生成 + 回写 |
| **analyze** | `--analyze`「只分析」 | Step 1-3 | 功能点清单 + 优先级建议（不生成用例）|
| **smoke** | `--smoke`「冒烟」 | Step 1-6（Step 4 仅生成 P0）| `{topic}-smoke.md`（仅 P0 主路径）+ 索引再生成 |

## 前置条件

- PRD + Tech Design **状态均为 `Ready`**（统一枚举；任一未达 Ready 则中止）
- 业务目录 `test-business/{product}/`（不存在则自动创建）

> **目录职责**：`test-business/` 积累业务知识规则；`test_cases/` 存放用例产出。两者分离。

## 状态机（与三件套同枚举，独立生命周期）

| 转换 | 条件 |
|------|------|
| 生成 | 新用例文档初始状态 `Draft` |
| Draft → Ready | Step 5 评审通过 + `{topic}-key-points.md` 就位（check-md-schema 机器校验） |
| Ready → Implemented | 执行验收通过，**人工回写**（本 skill 不负责） |
| * → Deprecated | 上游 PRD/TD Deprecated 级联；上游复审变更 → 回退 Draft 并备注「需重审」（由 `sync-status` 编排，check-traceability T12 兜底检测漏级联） |

## 运行模式

| 模式 | 触发 | 行为 |
|------|------|------|
| 逐步确认（默认）| 无关键词 | 每步暂停等确认 |
| 自动模式 | 「自动」「不用确认」| 仅 Step 5 后强制暂停 |

## Anti-Patterns

| ❌ | ✅ |
|----|----|  
| 业务硬编码 | 从 PRD/TD 动态提取 |
| 多平台混合 | 每次单平台 |
| 跳过确认 | 按模式执行 |
| 只写正常路径 | 必须含异常/边界 |
| 优先级全 P1 | 按矩阵区分 P0-P3 |
| 重读源文档 | Step 3 提取一次，后续靠索引 |
| 手改 `_index.md` | 跑 `scripts/sync-test-index.sh` 再生成 |
| 自造状态名（Reviewed/Approved） | 统一枚举 Draft/Ready/Implemented/Deprecated |
| 来源引素材路径 | 优先引 `prd/{date}/` 与 TD 目录 |
| But 分支不数不逐条覆盖 (v2.3) | 先 `grep -c '\*\*But\*\*'` 数，每个 But ≥1 条用例 |
| 只测功能异常，漏环境边界（弱网/静音/重启/角色）(v2.3) | 环境边界 Checklist 逐维对照 |
| PRD Goal 显式默认值无初始状态用例 (v2.3) | 默认值一律有初始状态验证 |
| ards 探索记录 OQ 收敛方式点名 TC 却无收敛用例 (v2.3) | 生成收敛用例并标注 OQ 关联 |

## 参考文件（按需读取）

| 文件 | 读取时机 |
|------|---------|  
| [schema/test_case.md](../../schema/test_case.md) | Step 6（输出结构权威模板） |
| [references/priority-matrix.md](references/priority-matrix.md) | Step 4 |
| [references/review-checklist.md](references/review-checklist.md) | Step 5 |
| [references/platform-dimensions.md](references/platform-dimensions.md) | Step 4 |
| [references/system-knowledge.md](references/system-knowledge.md) | Step 4（不定期更新）|

> `references/yaml-schema.md` / `examples/sample-output.yaml` 为 v2.0 遗留，仅历史参考；新产出以 `schema/test_case.md` 为准。

## Related Skills

- `to-prd` / `to-tech-design`：上游输入（来源方向）
- `to-plan`：下游消费方——Plan 编制时以本层 Ready 用例集为参考比照（Plan 元信息「参考 Test Cases」行，T11 校验）；同主题 Plan 已存在时双向核对主题覆盖（V 用例 ↔ TC 用例）
- `validate-spec`：校验脚本（含 test_cases 的 check-md-schema / check-naming / check-traceability T9-T12）
- `sync-status`：生命周期编排——Implemented 人工回写 / Deprecated 级联 / 复审回退
