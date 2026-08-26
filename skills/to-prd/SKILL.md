---
name: to-prd
description: 原始需求 → PRD 转换流程，按 schema/prd.md 模板提炼产出 PRD。Use when 收到 material/{YYYY-MM-DD}/ 或 prd/{YYYY-MM-DD}/ 下原始素材（用户抱怨、会议纪要、技术方案），需要提炼为符合规范的 PRD 文件 (输出到 prd/{YYYY-MM-DD}/{topic}.md, 无 -processed 后缀)。Use when 启用 material/ 可选层时, 也支持 material/ → PRD 流水线。
skill-type: spec
version: 1.1
type: skill
skill-role: procedure
---

# to-prd

将 `prd/{YYYY-MM-DD}/` 下的原始素材提炼为 `prd/{YYYY-MM-DD}/{topic}.md`（**新约定**: 无 `-processed` 后缀）, 遵循 `schema/prd.md` 模板.

## Mode Indicator

启动后 agent 系统提示显示：

```
[MODE: to-prd] (reading | extracting | writing | validating)
```

阶段说明：

| Phase | 做什么 |
|-------|--------|
| `reading` | 读取原始素材 (prd/{date}/ 或可选 material/{date}/) + schema 模板 + 项目 AGENTS.md §1 |
| `extracting` | 提炼 Why/Goal/Scenarios/Out of Scope/Review |
| `writing` | 写出 PRD 到 `prd/{date}/{topic}.md` (新约定, 无 -processed) |
| `validating` | 跑 `scripts/check-md-schema.sh` 校验 |

## When to Use

- 用户提供原始需求（用户抱怨、会议纪要、需求文档），已放入 `prd/{YYYY-MM-DD}/`
- 需要产出符合 `schema/prd.md` 的 PRD
- 需要自动跑校验脚本

## Slash Command

```
/to-prd <date>
```

示例：

```
/to-prd 2026-07-03
```

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| Schema 模板 | `schema/prd.md` | PRD 结构定义（v3 状态用 Ready） |
| AGENTS.md | `AGENTS.md` §1 | 注入多仓上下文（如 SSD-Template 关联 client + server） |
| 校验脚本 | `scripts/check-md-schema.sh` | 自动校验产出 PRD |
| 原始素材 | `prd/{YYYY-MM-DD}/*.md` | Layer 0 只读输入 |

## Core Concept

### 提炼映射

| Schema 字段 | 来源 | 必填 |
|-------------|------|------|
| Why | 业务背景 + 用户痛点 → 一句话 | ✓ |
| Goal | 功能清单 + 验收标准 → 可观察/可测量项 | ✓ |
| Scenarios | 流程图主路径 + 异常分支 → Given/When/Then | ✓（≥1 异常）|
| Out of Scope | 框架阶段 + 依赖外部 → 明确不做 | ✓（≥2 项）|
| Review | 复审日期 + 3 问答案 | ✓ |
| Status | 提炼完成后设 `Ready` | ✓ |

### 拆分粒度

| 输入 | 输出 | 规则 |
|------|------|------|
| 1 原始文件 → 1 功能 | 1 PRD | 默认 |
| 1 原始文件 → N 功能 | N PRD | 按功能拆 |
| N 原始文件 → 1 功能 | 1 PRD | 合成 |

## Execution Steps

### 1. Reading Phase

读取 3 个关键文件：

1. **原始素材**：`prd/{YYYY-MM-DD}/*.md`
2. **Schema 模板**：`schema/prd.md`
3. **项目上下文**：`AGENTS.md` §1（如有）

> 💡 多仓上下文通常不影响 PRD 提炼，但有助于理解"Out of Scope"边界。

### 2. Extracting Phase

按"Core Concept → 提炼映射"逐字段提炼，每字段附：
- 数据来源（哪个原始文件段落）
- 提炼理由（为什么这样写）

### 3. Writing Phase

- 输出路径：`prd/{YYYY-MM-DD}/{topic}.md`（**新约定**：无 `-processed` 后缀）
- `topic` 命名规则：小写连字符（lowercase-with-hyphens），如 `checkout-flow` / `member-login`
- **不修改** Layer 0 原始文件

### 4. Validating Phase

执行：

```bash
./scripts/check-md-schema.sh
```

要求：返回 0，无 `✗` 错误；`○ v2 跳过` 黄色提示可忽略。

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 用 `Active` 状态字段 | 用 `Ready`（v3 术语） |
| 写模糊 Goal（"支持 XX"、"完成 XX"）| 写可观察 Goal（"输入手机号后，2s 内返回会员信息"） |
| 只写正常场景 | 必须 ≥1 异常场景（`But` 子句） |
| 省略 Out of Scope | ≥2 项明确不做 |
| 修改 Layer 0 原始文件 | 只读，不动 |
| 添加 schema 之外的章节 | 严格按 schema 5 段 |
| 复审日期写 `{YYYY-MM-DD}` 占位符 | 写真实日期 |
| 用旧字段名 `来源 Prd` | 用 v3 字段名 `来源 Raw` |

## Troubleshooting

### Q1：原始素材目录不存在

**症状**：`./scripts/check-md-schema.sh` 报 `prd/2026-07-03/ not found`

**排查**：
```bash
ls prd/ | grep "2026-07-03"
```

**处理**：先创建 `prd/2026-07-03/` 目录并放入原始素材文件。

### Q2：check-md-schema.sh 报"仍含模板占位符"

**症状**：脚本报 `{TOPIC}` / `{FIELD_NAME}` 形式占位符

**原因**：占位符检测对大写前缀敏感（避免误报业务动态值如 `{env}`）

**排查**：
```bash
grep -nE '\{[A-Z][A-Z_-]+\}|\{[A-Z_-]+ [A-Z_-]+\}' prd/2026-07-03/{topic}.md
```

**处理**：把占位符替换为真实值（如 `{TOPIC}` → `member-login`）。

### Q3：check-md-schema.sh 报"无 Given/When/Then"

**症状**：脚本找不到 `**Given**` 字段

**原因**：使用了非标准字段名（如 `**Pre-condition**` 而非 `**Given**`）

**处理**：严格按 schema 用 `**Given**` / `**When**` / `**Then**` 加粗。

### Q4：check-md-schema.sh 报"复审日期无有效日期"

**症状**：复审字段检测不到 `YYYY-MM-DD` 格式

**原因**：用了占位符 `{YYYY-MM-DD}` 或留空

**处理**：写真实日期（如 `2026-07-03`），不能是占位符。

### Q5：check-md-schema.sh 报"非法引用类型"

**症状**：报 `AES-256` / `SHA-256` 等为非法引用

**说明**：实际是业务值（AES-256 加密算法），不是引用。脚本在 v3 已简化 T5（只扫描白名单引用 KD/V/FR/SYS/MOD），不应再误报。

**处理**：如果是真实误报，把 T5 检查放回 `[[ -f scripts/check-traceability.sh ]] && ./scripts/check-traceability.sh`；如仍误报，检查脚本是否更新到 v3 双模式补丁。

## Tips

- **PRD 状态字段**必填 `Ready`（v3 统一术语，与 schema/prd.md 一致）
- **Goal 项必须可观察**：避免"系统正常"、"响应快速"等模糊措辞
- **Scenarios 至少 1 个异常**：从原始素材的"异常处理"段提取，写在 `But` 子句
- **Out of Scope 至少 2 项**：从原始素材的"框架阶段" / "后续迭代"段提取
- **topic 命名用小写连字符**：`checkout-flow` ✓，`order_flow` ✗，`orderFlow` ✗
- **跨文件引用 PRD 用相对路径**：`../../prd/{date}/{topic}.md`
- **多仓项目 PRD 仍可写**：`Out of Scope` 段注明"前端 / 后端边界"，为后续 TD/Plan 留接口

## Examples

### Simple

```
User: /to-prd 2026-07-03
Agent: [MODE: to-prd] (reading)
Agent: 📂 读取 prd/2026-07-03/login-raw.md（1 个原始文件）
Agent: 📋 读取 schema/prd.md
Agent: 🔧 读取 AGENTS.md §1（关联 client + server）
Agent: [MODE: to-prd] (extracting)
Agent: 提炼 Why：用户登录是基础必备功能，当前无统一入口...
Agent: 提炼 Goal：手机号+验证码登录，2s 内完成...
Agent: 提炼 Scenarios：正常路径 + 验证码错误 + 网络异常
Agent: 提炼 Out of Scope：第三方登录（仅手机号）
Agent: [MODE: to-prd] (writing)
Agent: ✅ 写入 prd/2026-07-03/login.md
Agent: [MODE: to-prd] (validating)
Agent: 🟢 check-md-schema.sh 返回 0
Agent: [MODE: to-prd] (done)
```

### Complex (1:N 拆分)

```
User: /to-prd 2026-07-03
Agent: 原始素材包含 3 个独立功能：登录、注册、找回密码
Agent: 建议拆分：login.md / register.md / password-reset.md
Agent: 产出 3 个 PRD，每个走完整流程
```

## Slash Command Registration

通过 `skills/setup.sh` 注册到 agent skills 目录：

```bash
bash <repo>/skills/setup.sh
```

默认注册到：

- `~/.claude/skills/` （Claude Code）
- `~/.qoder/skills/` （Qoder）
- `~/.pi/agent/skills/` （pi/agent）
- `~/.cursor/skills/` （Cursor）

## Related Skills

- `to-tech-design`：PRD → Tech Design（v3 7 子文件 / v4 4 子文件，opt-in 选代际）
- `to-plan`：Tech Design → Plan（强制按仓分组 Change）
- `validate-spec`：跑全部校验脚本

## Cross-References

- <repo>/AGENTS.md §1（多仓上下文）
- <repo>/AGENTS.md §3（三步工作流 Step 1）
- <repo>/schema/prd.md（v3 模板）
- <repo>/scripts/check-md-schema.sh（v3 双模式校验）
- <repo>/HOW_TO_USE.md（完整工作流）