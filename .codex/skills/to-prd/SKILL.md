---
name: to-prd
description: >-
  原始需求 → PRD 转换流程, 按 schema/prd.md 模板提炼产出 PRD (v2.0)。Use when 收到 prd/{YYYY-MM-DD}/ 下的原始素材
  (用户抱怨、会议纪要、技术方案), 需要提炼为符合规范的 PRD 文件 (输出到 prd/{YYYY-MM-DD}/{topic}.md, 无 -processed 后缀)。
  agent 自主推进: 判据全绿即由 agent 起草复审自评并用 ssdctl advance 推到 Ready; 人工可选复核并落决定记录。
---

# to-prd

将 `prd/{YYYY-MM-DD}/` 下的原始素材提炼为 `prd/{YYYY-MM-DD}/{topic}.md`（**新约定**: 无 `-processed` 后缀）, 遵循 `schema/prd.md` 模板.

## 执行阶段 (内部 phase 标识)

agent 按下列 phase 顺序推进。每个 phase 开始时在汇报里写明 `phase: <name>`, 便于人工追溯。

> phase 是 agent 的**内部工作分段**, 不依赖任何 UI 模式指示器, 也不假设运行环境会显示模式。

| Phase | agent 做什么 |
|-------|--------------|
| `reading` | 读取原始素材 (`prd/{date}/`) + `schema/prd.md` 模板 + `schema/criteria.json` 判据 + 项目 `AGENTS.md` §1 |
| `extracting` | 逐字段提炼 Why / Goal / Scenarios / Out of Scope / Review, 并分配稳定 ID (`AC-n` / `S-n`) |
| `writing` | 写出 PRD 到 `prd/{date}/{topic}.md` (无 `-processed` 后缀), 状态块写 `Draft` + 状态主体/时间/依据 |
| `validating` | 跑 `bash scripts/ssdctl.sh criteria <artifact>` 判据校验并汇报退出码 |
| `advancing` | 判据全绿时用 `bash scripts/ssdctl.sh advance <artifact> --to Ready` 推进; 有失败项先 `queue` 交人工裁决 |

## When to Use

- 用户提供原始需求（用户抱怨、会议纪要、需求文档），已放入 `prd/{YYYY-MM-DD}/`
- 需要产出符合 `schema/prd.md` 的 PRD
- 需要自动跑判据校验并由 agent 自主推进到 `Ready`

## 调用输入

| 输入 | 必填 | 说明 |
|------|------|------|
| 日期 `{YYYY-MM-DD}` | 是 | 指定 `prd/{YYYY-MM-DD}/` 分桶 |

示例: 用 `2026-07-03` 的素材产出一份 PRD。

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| Schema 模板 | `schema/prd.md` | PRD 结构定义（状态枚举 Draft / Ready / Implemented / Deprecated）|
| 判据权威 | `schema/criteria.json` | 本层判据的唯一权威位置（`ssdctl criteria` 读它）|
| AGENTS.md | `AGENTS.md` §1 | 注入多仓上下文（如 SSD-Template 关联 client + server）|
| 判据与门禁入口 | `scripts/ssdctl.py` | **唯一入口**: `criteria` / `gate` / `advance` / `queue` / `scan` / `evidence` / `verify` |
| 原始素材 | `prd/{YYYY-MM-DD}/*.md` | Layer 0 只读输入 |

## Core Concept

### 提炼映射

| Schema 字段 | 来源 | 必填 |
|-------------|------|------|
| Why | 业务背景 + 用户痛点 → 一句话 | ✓ |
| Goal | 功能清单 + 验收标准 → 可观察/可测量项, 每条带稳定 ID `AC-n` | ✓ |
| Scenarios | 流程图主路径 + 异常分支 → Given/When/Then, 标题带 `S-n` + `**覆盖**:` 行 | ✓（≥1 异常）|
| Out of Scope | 框架阶段 + 依赖外部 → 明确不做 | ✓（≥2 项）|
| Review | 评审签署 4 行 + 周期性复审日期 + 3 问答案 | ✓ |
| 状态块 | 状态 / 状态主体 / 状态时间 / 状态依据 | ✓ |

### 稳定 ID 分配 (与 schema/criteria.json 的覆盖判据一致)

| ID | 载体 | 写法 | 规则 |
|----|------|------|------|
| `AC-n` | PRD 目标条 | `- [ ] AC-1 <验收标准文本>` | 文件内唯一, 至少被一个 `S-n` 覆盖 |
| `S-n` | PRD 场景标题 | `### 场景: S-1 <名称>` | 文件内唯一, 至少覆盖一个 `AC-n` |
| 覆盖声明 | 场景块内 (`**Given**` 之前) | `**覆盖**: AC-1, AC-2` | 每个 `AC-n` 至少被覆盖一次 |

> **覆盖完整性是判据, 不是自觉**: `ssdctl criteria` 会按 `coverage_complete` 判据核对「每个 `AC-n` 至少被一个 `S-n` 覆盖, 每个 `S-n` 至少覆盖一个 `AC-n`」; 缺一边 ⇒ 判据不通过 ⇒ 不能进 `Ready`。

### 拆分粒度

| 输入 | 输出 | 规则 |
|------|------|------|
| 1 原始文件 → 1 功能 | 1 PRD | 默认 |
| 1 原始文件 → N 功能 | N PRD | 按功能拆 |
| N 原始文件 → 1 功能 | 1 PRD | 合成 |

## 状态推进边界 (agent 主导, 人工可选手动介入)

> **判定权归判据, 写入权归 agent**。agent 在判据全绿时**直接推进**; 人工复核是**可选**的兜底通道, 不是必经环节。

| 动作 | 主体 | 说明 |
|------|------|------|
| 写产物, 状态块写 `Draft` + 状态主体/时间/依据 | agent | `Draft` 态允许后三行有值 (依据填 `criteria:` 或空) |
| 起草 `## 复审 (Review)` 四行自评 | agent | `评审人` 写 `agent:<id>`, `评审方式` 写 `自动判据`; **agent 绝不可写 `human:` 前缀, 也不可代填人名** |
| 把状态翻成 `Ready` | **agent**（判据全绿时）| `bash scripts/ssdctl.sh advance <artifact> --to Ready`; blocking 判据全绿且上游 `Ready` 即成立 |
| 把状态翻成 `Implemented` | agent（凭外部事实）| 需 `external:` 依据（如外部代码仓 PR merged）; PRD / Tech Design / Plan 三件套必须同时回写 |
| 把状态改成 `Deprecated` | agent（凭决定记录 / 外部事实）| 依据**不能**是 `criteria:`; 必须是 `decision:<path>#<anchor>` 或 `external:<ref>` |
| 人工复核 / 驳回 / 挂起 | 人工（**可选**）| 落 `control/decisions/<date>-<topic>.md`（或跑 `ssdctl decide`), 再由 agent 用 `advance --decision <path>#<anchor>` 代写 |

- **状态块 4 行由 `ssdctl advance` 写**: agent 不手改状态行, 也不教人手改; 手改会被 `ssdctl verify` 判为状态块与证据链不自洽。
- **人工复核不是必经环节**: 没有人工决定记录时, 判据全绿即可进 `Ready`; 反过来, 有 `blocking:false` 失败项时, 必须先有 `control/decisions/` 里的对应决定记录才能进 `Ready`。
- `## 复审 (Review)` 里的**周期性复审日期**行(`**复审日期**: YYYY-MM-DD`)不是评审签署行, 任何阶段都写真实日期。

## 禁止行为 (Agent 权限边界)

| ❌ agent 不做 | ✅ agent 改做 |
|--------------|--------------|
| 自行 `git commit` / `git push` / 切分支 / 改分支 | 只改工作区文件; **提交与分支管理一律由人决定** |
| 手改状态行 / 状态块 4 行 | 用 `ssdctl advance` 推进; 要试先 `--dry-run` |
| 在复审块写 `human:` 前缀或代填人名 | 写 `agent:<id>`; `human:` 前缀**只能由人自己填**, agent 不得代填 |
| 把状态标成 `Ready` 却没跑判据 | 先 `ssdctl criteria` 看 `passed`; 不通过就 `ssdctl queue` 交人工裁决 |
| 伪造 `Reviewed-by:` / SHA / 行号 / handle | 拿不准就不写; 无法核对时明确标注「未核对」 |
| 改 `schema/**` 下的模板 | 模板是契约, 只读; 发现模板与实现不一致时报告, 不自行修改 |
| 静默覆盖冲突 (两份素材对同一功能描述不一致) | 两份都保留, 登记冲突并报告人工裁决 |
| 留下模板占位符 (`{TOPIC}` / `{YYYY-MM-DD}` / `TBD`) | 填真实值; 确实无法确定时**删掉整行**而不是留占位符 |

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
- **状态块 4 行**（顺序固定，与 `schema/prd.md` 逐字一致）：
  - `> **状态**: Draft`（枚举只有 `Draft` / `Ready` / `Implemented` / `Deprecated`，不得自造）
  - `> **状态主体**: agent:<id>`（**绝不写 `human:` 前缀**）
  - `> **状态时间**: YYYY-MM-DDTHH:MM:SS±HH:MM`
  - `> **状态依据**: criteria:<id>[,<id>…]`（`Draft` 阶段可留空；进 `Ready` 后由 `ssdctl advance` 写实）
- **稳定 ID**：目标条 `- [ ] AC-1 <验收标准文本>`；场景标题 `### 场景: S-1 <名称>`；场景块内 `**覆盖**: AC-1, AC-2`（写在 `**Given**` 之前）
- `## 复审 (Review)` 段必须存在；agent 起草**自评四行**：
  - `> **评审人**: agent:<id>`（**绝不写 `human:` 前缀, 也不代填人名**）
  - `> **评审日期**: YYYY-MM-DD`（真实日期）
  - `> **评审结论**: 通过 / 有条件通过 / 需返工`
  - `> **评审方式**: 自动判据`（agent 自评时只写 `自动判据`; 人工介入由人自己改写为 `人工介入`）
- `**复审日期**: YYYY-MM-DD` 行写真实日期
- **不修改** Layer 0 原始文件

### 4. Validating Phase

判据与门禁**一律经 `scripts/ssdctl.py`**; `scripts/check-*.sh` 只是 `ssdctl gate` 的内部实现, **不单独手拼**:

```bash
bash scripts/ssdctl.sh criteria prd/{YYYY-MM-DD}/{topic}.md
```

- 退出码: `0` 全过 / `1` 有 blocking 失败 / `2` 用法或内部错误（INV-7 全仓统一）。
- 输出 `{passed, failures[], warnings[], claims[]}`; `claims[]` 每项含 `id` / `title` / `passed`。
- 判据的**唯一权威**是 `schema/criteria.json`; 本层至少覆盖 5 个机器必填段齐全、状态枚举合法、`AC-n` / `S-n` 覆盖完整性、无占位符残留。
- `warnings[]` 非空时逐条判断: `blocking:false` 的失败项必须先有 `control/decisions/` 里的决定记录才能进 `Ready`。

### 5. Advancing Phase

判据全绿 ⇒ agent **直接推进**; 人工复核是**可选**兜底, 不是必经环节:

```bash
# 4.1 先干跑, 看它打算写什么（不写任何文件）
bash scripts/ssdctl.sh advance prd/{YYYY-MM-DD}/{topic}.md --to Ready --dry-run

# 4.2 确认后推进（写状态块 + 复审块, 并把转换追加进 control/evidence/**）
bash scripts/ssdctl.sh advance prd/{YYYY-MM-DD}/{topic}.md --to Ready --actor agent:<id>
```

- 有 `blocking:false` 失败项时: `bash scripts/ssdctl.sh queue prd/{YYYY-MM-DD}/{topic}.md` 列出待裁决项交人裁决; 人裁决后由 `ssdctl decide` 落决定记录, 再 `advance --decision control/decisions/<file>#<id>`。
- 推进后回读证据链: `bash scripts/ssdctl.sh evidence --artifact prd/{YYYY-MM-DD}/{topic}.md`。
- 自洽性复核: `bash scripts/ssdctl.sh verify prd/{YYYY-MM-DD}/{topic}.md`（状态块 / 复审块 / 证据链三者一致）。
- **不要手改状态行**: 手改会被 `ssdctl verify` 判为与证据链不自洽。

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 用 `Active` / `Reviewed` / `Approved` 自造状态 | 用 `Draft` / `Ready` / `Implemented` / `Deprecated` 四值之一 |
| 判据没跑就写 `Ready` | 先 `ssdctl criteria` 看 `passed`，全绿才 `advance --to Ready` |
| 手改状态行或状态块 4 行 | 一律走 `ssdctl advance`；agent 也不教人手改 |
| 在复审块写 `human:` 前缀或代填人名 | 写 `agent:<id>`; `human:` 前缀**只能由人自己填**, agent 不得代填 |
| 自造 ID 前缀（用 `FR-1` / `REQ-1` 充数） | 用 `AC-n` / `S-n` |
| 漏写 `**覆盖**:` 行导致 `AC-n` 没有场景覆盖 | 每个 `AC-n` 至少被一个 `S-n` 的 `**覆盖**:` 覆盖 |
| 写模糊 Goal（"支持 XX"、"完成 XX"）| 写可观察 Goal（"输入手机号后，2s 内返回会员信息"） |
| 只写正常场景 | 必须 ≥1 异常场景（`But` 子句） |
| 省略 Out of Scope | ≥2 项明确不做 |
| 修改 Layer 0 原始文件 | 只读，不动 |
| 添加 schema 之外的章节 | 严格按 schema 5 段 |
| 复审日期写 `{YYYY-MM-DD}` 占位符 | 写真实日期 |
| 用旧字段名 `来源 Prd` | 用现行字段名 `来源 Raw` |

## Troubleshooting

### Q1：原始素材目录不存在

**症状**：`ssdctl criteria` 报 `prd/2026-07-03/ not found`

**排查**：
```bash
ls prd/ | grep "2026-07-03"
```

**处理**：先创建 `prd/2026-07-03/` 目录并放入原始素材文件。

### Q2：判据报"仍含模板占位符"

**症状**：判据失败项提到 `{TOPIC}` / `{FIELD_NAME}` 形式占位符

**原因**：占位符检测对大写前缀敏感（避免误报业务动态值如 `{env}`）

**排查**：
```bash
grep -nE '\{[A-Z][A-Z_-]+\}|\{[A-Z_-]+ [A-Z_-]+\}' prd/2026-07-03/{topic}.md
```

**处理**：把占位符替换为真实值（如 `{TOPIC}` → `member-login`）。

### Q3：判据报"无 Given/When/Then"

**症状**：失败项找不到 `**Given**` 字段

**原因**：使用了非标准字段名（如 `**Pre-condition**` 而非 `**Given**`）

**处理**：严格按 schema 用 `**Given**` / `**When**` / `**Then**` 加粗。

### Q4：判据报"覆盖不完整"

**症状**：`AC-n` 没有被任何 `S-n` 的 `**覆盖**:` 行覆盖，或反之

**排查**：
```bash
grep -nE '^\- \[ \] AC-[0-9]+' prd/2026-07-03/{topic}.md
grep -nE '^\*\*覆盖\*\*: ' prd/2026-07-03/{topic}.md
```

**处理**：每个 `AC-n` 至少被一个 `S-n` 覆盖；补 `**覆盖**:` 行（写在 `**Given**` 之前），或删除没有场景支撑的 `AC-n`。

### Q5：判据报"非法引用类型"

**症状**：报 `AES-256` / `SHA-256` 等为非法引用

**说明**：实际是业务值（AES-256 加密算法），不是引用。追溯检查只扫描白名单引用 `KD` / `V` / `FR` / `SYS` / `MOD`，不应再误报。

**处理**：如果确认是误报，把追溯检查单独跑一遍定位; `bash scripts/ssdctl.sh gate` 会列出每个子门禁的退出码，按退出码定位是哪一个门禁报的；**不要改判据来迁就误报**。

## Tips

- **PRD 状态字段**必填, 枚举只有 `Draft` / `Ready` / `Implemented` / `Deprecated` 四值之一（`schema/prd.md` 统一术语）
- **判据全绿即推进**: `ssdctl criteria` 返回 `passed=true` 就可以 `advance --to Ready`; 人工复核是可选兜底, 不是必经环节
- **Goal 项必须可观察**：避免"系统正常"、"响应快速"等模糊措辞
- **Scenarios 至少 1 个异常**：从原始素材的"异常处理"段提取，写在 `But` 子句
- **Out of Scope 至少 2 项**：从原始素材的"框架阶段" / "后续迭代"段提取
- **每个 `AC-n` 至少被一个 `S-n` 的 `**覆盖**:` 行覆盖**; 每个 `S-n` 至少覆盖一个 `AC-n`
- **topic 命名用小写连字符**：`checkout-flow` ✓，`order_flow` ✗，`orderFlow` ✗
- **跨文件引用 PRD 用相对路径**：`../../prd/{date}/{topic}.md`
- **多仓项目 PRD 仍可写**：`Out of Scope` 段注明"前端 / 后端边界"，为后续 TD/Plan 留接口

## Examples

### Simple

```
User: 把 2026-07-03 的原始素材加工成 PRD
Agent: phase: reading
Agent: 📂 读取 prd/2026-07-03/login-raw.md（1 个原始文件）
Agent: 📋 读取 schema/prd.md + schema/criteria.json
Agent: 🔧 读取 AGENTS.md §1（关联 client + server）
Agent: phase: extracting
Agent: 提炼 Why：用户登录是基础必备功能，当前无统一入口...
Agent: 提炼 Goal：手机号+验证码登录，2s 内完成...（AC-1 / AC-2）
Agent: 提炼 Scenarios：S-1 正常路径（**覆盖**: AC-1）+ S-2 验证码错误（**覆盖**: AC-1, AC-2）+ S-3 网络异常
Agent: 提炼 Out of Scope：第三方登录（仅手机号）
Agent: phase: writing
Agent: ✅ 写入 prd/2026-07-03/login.md（状态块 Draft; 复审自评 agent:sddctl / 自动判据）
Agent: phase: validating
Agent: 🟢 ssdctl criteria 返回 0（passed=true）
Agent: phase: advancing
Agent: 🟢 ssdctl advance --to Ready 返回 0（状态块 + 复审块由机器代写; 证据链已追加）
Agent: ✅ 已推进到 Ready（人工复核可选: ssdctl queue → ssdctl decide → advance --decision）
```

### Complex (1:N 拆分)

```
User: 把 2026-07-03 的原始素材加工成 PRD
Agent: 原始素材包含 3 个独立功能：登录、注册、找回密码
Agent: 建议拆分：login.md / register.md / password-reset.md
Agent: 产出 3 个 PRD，每个走完整流程
```

## 安装 (Installation)

用 `.codex/skills/install.sh` 把本 skill 注册到 agent 的 skills 目录：

```bash
bash <repo>/.codex/skills/install.sh
```

默认注册到：

- `~/.codex/skills/` （Codex）

注册到其它 agent 用 `--target <dir>`；`--unregister` 注销。

## Related Skills

- `.codex/skills/to-tech-design/SKILL.md`：PRD → Tech Design（默认 v4 四子文件; v3 存量六子文件需显式 opt-in）
- `.codex/skills/to-plan/SKILL.md`：Tech Design → Plan（强制按仓分组 Change）
- `.codex/skills/validate-spec/SKILL.md`：跑全量判据与门禁

## Cross-References

- <repo>/AGENTS.md §1（多仓上下文）
- <repo>/AGENTS.md §3.1（工作流 Step 1）
- <repo>/schema/prd.md（PRD 模板：状态块与复审块的权威形状）
- <repo>/schema/criteria.json（判据唯一权威）
- <repo>/scripts/ssdctl.py（判据与门禁的唯一入口）
- `schema/criteria.json`（判据唯一权威）
- <repo>/WORKFLOW.md（完整工作流）