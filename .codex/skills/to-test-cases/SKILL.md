---
name: to-test-cases
description: 从 PRD + Tech Design 生成黑盒测试用例 (Markdown) (v2.5)。适配 TD v4 四子文件结构 (README/ards/apis/data-model), 存量 v3 六子文件按对应关系读取。PRD But 逐条覆盖 + 环境边界 Checklist + 默认值用例 + OQ 收敛用例。Use when 需要为已就绪的 PRD + TD 产出黑盒用例集, 或只做功能点分析 / 只出冒烟用例。agent 只能产出 Draft 状态, Ready 与 Implemented 由人工写入。
---

# to-test-cases

> **角色**：资深测试架构师，精通黑盒测试方法论、前后端分离架构测试、端到端链路验证。

从 Ready 状态的 PRD + Tech Design 生成结构化黑盒测试用例（Markdown，模板 `schema/test_case.md`），产出到 `test_cases/{YYYY-MM-DD}/`。

> **前缀路由**：README 登记表 `TEST-*` 前缀条目以本 skill 为流水线入口。测试类素材（`material/{date}/{file}.md`）可直接转化为 Layer 4 用例，元信息「来源」行指向素材路径（check-traceability T9 已支持 `material/*` 前缀）。

> **v2.1 机制对齐（2026-08-06）**：
> - 输出口径由 YAML 改为 **Markdown**（对齐全部存量与 check-md-schema 校验）
> - 状态枚举与三件套统一：**Draft / Ready / Implemented / Deprecated**（独立生命周期，不与三件套联动）
> - 层定位：来源 = **PRD + Tech Design**；产出是 **Plan 的参考比照对象**（V 用例 ↔ TC 用例同主题互为参照）
> - Step 6 收尾强制：`scripts/sync-test-index.sh` 再生成索引 + `scripts/check-md-schema.sh <新文件>` 校验

> **v2.3 覆盖强化（2026-08-07，pay-voice 审计教训）**：
> - **But 分支是一等测试点**：先 `grep -c '\*\*But\*\*'` 数出 PRD 的 But 总数，每个 But ≥1 条用例，不允许丢失（系统静音/弱网这类边界都住在 But 里）
> - **环境边界 Checklist**：网络（弱网/离线/切换）、系统声道（静音/最低音量）、生命周期（重启/后台）、权限角色、数据边界。逐维对照 PRD 的 But
> - **默认值用例**：PRD Goal 显式默认值（如总开关默认开/音量默认 60）必须有初始状态验证用例
> - **OQ 收敛用例**：TD ards.md「探索记录」的 OQ 收敛方式若点名测试用例（如离线冒烟），必须生成对应用例并标注 OQ 关联（存量 v3 TD：exploration.md）

## 流程

> 下列 Step 是 agent 的**内部工作分段**, 不依赖任何 UI 模式指示器; 每步开始时在汇报里写明 `phase: <step>`。

```
Step 1: Confirming          → 确认输入/审核/平台/范围
Step 2: Resolving Business  → 定位/创建 test-business/{product}/
Step 3: Analyzing           → 提取功能点 + 用户确认（源文档只读一次，后续靠索引）
Step 4: Generating          → 三层用例(前端/后端/E2E) + 优先级 + 平台特异性
Step 5: Reviewing           → 4角色独立评审(≤3轮) + 用户确认
Step 6: Writing             → 输出 Markdown 用例 + 要点 + 索引再生成 + 知识库回写 + 校验
```

每步详细指令见 `prompts/step{N}-*.md`，执行到该步时读取。

## 调用输入

| 输入 | 必填 | 说明 |
|------|------|------|
| PRD 路径 | 是 | `prd/{YYYY-MM-DD}/{topic}.md` |
| Tech Design 目录 | 否 | `tech_design/{YYYY-MM-DD}-{topic}/`; 只给一个参数时自动推断另一个（同 date-topic）|
| 变体 | 否 | `--analyze` 只分析 / `--smoke` 只出冒烟 |

示例: 用 `prd/2026-07-03/login.md` 与 `tech_design/2026-07-03-login/` 生成黑盒用例。

## 执行范围

| 范围 | 触发 | 执行步骤 | 产出 |
|------|------|---------|------|
| **full**（默认）| 无关键词 | Step 1-6 全走 | 主用例 .md + 要点 + 索引再生成 + 回写 |
| **analyze** | `--analyze`「只分析」 | Step 1-3 | 功能点清单 + 优先级建议（不生成用例）|
| **smoke** | `--smoke`「冒烟」 | Step 1-6（Step 4 仅生成 P0）| `{topic}-smoke.md`（仅 P0 主路径）+ 索引再生成 |

## 前置条件

- PRD + Tech Design **状态均为 `Ready`**（统一枚举；任一未达 Ready 则中止）。`Ready` 由人工 reviewer 在各自产物的 `## 复审 (Review)` 段签署三行后写入, agent 不自行翻状态。
- 业务目录 `test-business/{product}/`（不存在则自动创建）

> **目录职责**：`test-business/` 积累业务知识规则；`test_cases/` 存放用例产出。两者分离。

## 状态推进边界 (agent 权限天花板 = Draft)

| 状态 | 谁能写 | agent 能做什么 |
|------|--------|----------------|
| `Draft` | **agent** | 写用例文档 + 跑门禁 + 报告结论 |
| `Ready` | **人工 reviewer** | 只能等: 不得翻状态, 不得代填 `评审人` / `评审日期` / `评审结论` |
| `Implemented` | **仅人工** | 只能等: 执行验收通过后由人工回写 |
| `Deprecated` | **人工决策** | 只能等: 上游 Deprecated 之后的机械级联由人工触发 |

- agent 产出用例后**停在 `Draft`**, 汇报「已产出 Draft, 待人工 reviewer 签署后翻 Ready」。
- `## 复审 (Review)` 段的三行签署载体在 `Draft` 阶段留空（不留 `{}` 占位符）。

## 状态机（与三件套同枚举，独立生命周期）

| 转换 | 条件 |
|------|------|
| 生成 | 新用例文档初始状态 `Draft` |
| Draft → Ready | Step 5 评审通过 + `{topic}-key-points.md` 就位（check-md-schema 机器校验）；**由人工 reviewer 签署三行后写入** |
| Ready → Implemented | 执行验收通过，**人工回写**（本 skill 不负责） |
| * → Deprecated | 上游 PRD/TD Deprecated 级联；上游复审变更 → 回退 Draft 并备注「需重审」（由 `sync-status` 编排，check-traceability T12 兜底检测漏级联） |

## 运行模式

| 模式 | 触发 | 行为 |
|------|------|------|
| 逐步确认（默认）| 无关键词 | 每步暂停等确认 |
| 自动模式 | 「自动」「不用确认」| 仅 Step 5 后强制暂停 |

### 产出元信息 (7 必填 + 3 可选, 与 schema/test_case.md 对齐)

Step 6 写用例文档时, 元信息表必须与 `schema/test_case.md` 的 10 行逐字对齐: **7 行必填**(`scripts/check-md-schema.sh` 的元信息必填行, 缺一行即 exit 1)+ **3 行可选**(有则填, 无则留空或删整行)。

| 字段 | 必填 | 取值 |
|------|------|------|
| 主题 | ✓ | `{topic}`, 与目录/文件名一致 |
| 业务产品 | ✓ | `[产品名]`（POS / ERP / CRM / ...）|
| 目标平台 | ✓ | `[Web / iOS / Android / 服务端 / 跨端]` |
| 来源 | ✓ | 上游 PRD 路径 `prd/{date}/{topic}.md`（仓外用 URL）|
| 生成日期 | ✓ | `YYYY-MM-DD` 真实日期 |
| 状态 | ✓ | `Draft`（agent 上限）/ `Ready` / `Implemented` / `Deprecated` |
| 用例总数 | ✓ | 本文件用例总数（主 + 冒烟合计）|
| 来源 Tech Design | 可选 | `tech_design/{date}-{topic}/README.md` |
| 来源 Plan | 可选 | `plan/{date}-{topic}/{topic}.md` |
| 最后更新 | 可选 | `YYYY-MM-DD` 真实日期 |

- 字段名严格统一, 校验脚本按字段名抓取值; 顺序不限, 建议按上表顺序。
- `Ready` / `Implemented` 状态还要求同目录存在 `{topic}-key-points.md`（门禁校验）。

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
| 自行把用例状态翻成 `Ready` / `Implemented` | agent 只写 `Draft`, 等人工 reviewer 签署 |
| 自行填 `评审人` / `评审日期` / `评审结论` | `Draft` 阶段三行留空, 等人工 reviewer 填写 |

## 禁止行为 (Agent 权限边界)

| ❌ Don't | ✅ Do |
|----------|-------|
| 自行 `git commit` / `git push` | 只改工作区文件; 提交由人工决定。**Symphony 编排路径例外**: 在 Symphony 给你的工作区 + `spec/{issue-identifier}-{topic}` 分支上, 按仓根 `WORKFLOW.md` §8 提交与推送是**授权动作**; 仍禁止 push 主分支 / merge / 伪造评审 |
| 把状态写成 `Ready` / `Implemented` | 只写 `Draft` |
| 伪造 `Reviewed-by:` / SHA / 行号 / handle | 拿不准就不写 |
| 修改 `schema/**` 下的模板 | 只读 `schema/test_case.md` |
| 静默覆盖冲突 | 登记冲突并交人工裁决 |
| 留下 `{...}` 占位符 | 填真实值, 不适用就删整行 |

## 参考文件（按需读取）

| 文件 | 读取时机 |
|------|---------|  
| [schema/test_case.md](../../../schema/test_case.md) | Step 6（输出结构权威模板） |
| [references/priority-matrix.md](references/priority-matrix.md) | Step 4 |
| [references/review-checklist.md](references/review-checklist.md) | Step 5 |
| [references/platform-dimensions.md](references/platform-dimensions.md) | Step 4 |
| [references/system-knowledge.md](references/system-knowledge.md) | Step 4（不定期更新）|

> v2.0 的 YAML 输出口径已废弃; 新产出一律以 `schema/test_case.md` 为准。

## 安装 (Installation)

skill 定义随仓库分发, agent 直接读 `.codex/skills/to-test-cases/SKILL.md` 即可, **无需注册**。

需要把 skill 装进宿主 agent 的 skills 根目录时, 用仓内安装脚本：

```bash
bash <repo>/.codex/skills/install.sh                     # 默认 ~/.codex/skills/
bash <repo>/.codex/skills/install.sh --target <dir>      # 指定目标
bash <repo>/.codex/skills/install.sh --unregister        # 注销
```

## Related Skills

- `.codex/skills/to-prd/SKILL.md` / `.codex/skills/to-tech-design/SKILL.md`：上游输入（来源方向）
- `.codex/skills/to-plan/SKILL.md`：下游消费方。Plan 编制时以本层 Ready 用例集为参考比照（Plan 元信息「参考 Test Cases」行，T11 校验）；同主题 Plan 已存在时双向核对主题覆盖（V 用例 ↔ TC 用例）
- `.codex/skills/validate-spec/SKILL.md`：校验脚本（含 test_cases 的 check-md-schema / check-naming / check-traceability T9-T12）
- `.codex/skills/sync-status/SKILL.md`：生命周期编排。Implemented 人工回写 / Deprecated 级联 / 复审回退
