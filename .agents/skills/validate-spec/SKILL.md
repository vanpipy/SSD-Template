---
name: validate-spec
description: >-
  跑仓内判据与门禁, 输出统一报告 (v2.0)。判据与门禁一律经 scripts/ssdctl.py (gate / criteria / scan --check / verify),
  不再逐个手拼校验脚本。支持 v4/v3 双模式 TD + 可选层 (test_cases/ 台账/ 关联矩阵/ deep/ 按存在与否条件启用)
  + 证据锚点人工抽查 (只报 ⚠, 不改退出码) + skill 目录自检 (skills-integrity.sh)。
  Use when 完成 PRD / Tech Design / Plan 产出后, 需要验证是否符合判据; 或修改存量 spec 文件后, 需要确认无新违规。
---

# validate-spec

跑 SSD-Template 仓内判据与门禁, 输出统一报告。

## 执行阶段 (内部 phase 标识)

agent 按下列 phase 顺序推进。每个 phase 开始时在汇报里写明 `phase: <name>`。

> phase 是 agent 的**内部工作分段**, 不依赖任何 UI 模式指示器, 也不假设运行环境会显示模式。

| Phase | agent 做什么 |
|-------|--------------|
| `running` | 跑 `bash scripts/ssdctl.sh gate` (全仓门禁 + 判据引擎 + 派生数据再生) 与 `bash scripts/ssdctl.sh scan --check` (调度一致性), 逐个记录退出码 |
| `integrity` | 跑 `skills-integrity.sh` 自检 `.agents/skills/` 目录的一致性 |
| `spot-checking` | 人工抽查 Tech Design「现状结论」的证据锚点（**只报 ⚠, 不改任何脚本退出码**）|
| `reporting` | 输出统一报告（pass / skip / violation / 锚点警告）|

## When to Use

- 完成 PRD / Tech Design / Plan 产出后，验证是否符合规范
- 修改存量 spec 文件后，确认无新违规
- 提交前，做最终验证
- 想知道当前仓库 spec 健康度

## 调用输入

| 输入 | 必填 | 说明 |
|------|------|------|
| 目标路径 | 否 | 省略 = 校验整个仓库; 也可给单文件 (`prd/2026-07-03/login.md`) 或单目录 (`tech_design/2026-07-03-login/`) |

示例: 校验整个仓库的 spec 规范。

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| 判据与门禁入口 | `scripts/ssdctl.py` | **唯一入口**: `gate` / `criteria` / `scan --check` / `verify` |
| 判据权威 | `schema/criteria.json` | 机器判据（`blocking` / `kind` / `params`）|
| 自检脚本 | `.agents/skills/validate-spec/skills-integrity.sh` | `.agents/skills/` 目录内部一致性自检 |
| 工作目录 | SSD-Template 仓根目录 | scripts 假设此位置 |

## Core Concept

### 校验维度

| 命令 | 检查项 | 兼容策略 |
|------|--------|----------|
| `ssdctl.py criteria <artifact>` | 单制品逐条判据（必填段 / 状态块 / 复审块 / 稳定 ID / 引用闭环 / 无占位符）| 容忍旧格式文件 |
| `ssdctl.py gate` | 全仓门禁: 既有门禁脚本 + 判据引擎 + 派生数据再生 | 逐条记录退出码 |
| `ssdctl.py scan --check` | 跨制品一致性检查（上游闸门 / 三件套原子性 / 字段自洽）| 只回读, 不落盘 |
| `ssdctl.py verify <artifact>` | 状态块与复审段自洽 | 只回读, 不写 |
| `skills-integrity.sh` | `.agents/skills/` 目录一致性（front matter 键集合 / 悬空引用 / 代际口径 / 占位符 / 旧表述 / ssdctl 子命令名）| 只查 skill 目录, 不查 spec 产物 |

### 可选层与条件启用

以下层是**可选的**, 默认不启用。**校验脚本按「目录 / 文件是否存在」决定是否启用对应检查**; 产物不存在时, 对应检查**跳过, 不是失败**。

| 可选层 | 启用条件 | 不存在时的行为 |
|--------|----------|----------------|
| Layer 4 测试用例 | `test_cases/` 目录存在 | 跳过 T9 / T11 / T12 用例相关检查 |
| PRD 台账 | `material/{date}/PRDS.md` 存在（`schema/prd-ledger.md` 模板）| 跳过台账一致性检查 |
| PRD 关联矩阵 | 根 `README.md` 含「PRD关联矩阵」章节 | 跳过关系边检查 |
| 理解层 `deep/` | `deep/` 目录存在 | **本 skill 完全不校验 `deep/` 内容**（见下）|
| 实现基线 | 项目关联代码仓（AGENTS.md §1.1 登记了非 A 标识）且 TD 目录存在 | 0 代码仓项目跳过基线核对 |

> **理解层 `deep/` 明确不在校验范围**。`deep/` 是可选知识层, `.agents/skills/validate-spec/SKILL.md` 不校验它的内容与结构。需要检查 `deep/` 时用 `scripts/deep-scan.py` 的台账输出, 不走本 skill。

> **0 实例 → 0 违规**。模板自身仓库零实例, 所有校验器应全绿。

### 输出符号

| 符号 | 含义 | 严重度 |
|------|------|--------|
| `✓` | 通过 | 无 |
| `○` (黄色) | 旧格式文件跳过校验 / 可选层未启用 | 信息 |
| `⚠` (黄色) | 警告（如缺 interactions.md / 现状结论缺证据锚点）| 警告 |
| `✗` (红色) | 违规 | 错误 |

## Execution Steps

### 1. Running Phase

依次跑**唯一入口** `scripts/ssdctl.py`（不要再手拼 `scripts/check-*.sh`）：

```bash
echo "=== ssdctl.py gate ==="
bash scripts/ssdctl.sh gate

echo ""
echo "=== ssdctl.py scan --check ==="
bash scripts/ssdctl.sh scan --check
```

> `gate` 内部会跑既有门禁脚本 + 判据引擎 + 派生数据再生; 需要单制品逐条判定时用 `bash scripts/ssdctl.sh criteria <artifact>`。

**记录每个命令的退出码**。退出码是唯一的判定依据（`0` = 通过 / `1` = 不通过 / `2` = 用法或内部错误）, 本 skill 不改写它。

### 2. Integrity Phase (skill 目录自检)

```bash
bash .agents/skills/validate-spec/skills-integrity.sh
```

自检 `.agents/skills/` 目录的内部一致性: front matter 键集合、悬空脚本引用、AGENTS.md 章节引用、v4 默认代际口径、模板占位符、em dash、**旧表述残留**、**ssdctl 子命令名封闭**。退出码同样记录在报告里。

> 该脚本只检查 skill 目录自身, **不检查 spec 产物**。它不替代前一个 phase 的门禁脚本。

### 3. Spot-Checking Phase (证据锚点抽查)

> **性质**: 人工抽查步骤, **不是门禁**。脚本无法判定「已实现」是否有证据, 强行门禁会误报。
> **硬约束**: 本步骤**不改变任何脚本的退出码**, 命中问题只报 `⚠`。

**抽查对象**: Tech Design 目录中「当前实现状态 / 现状边界 / 现状 Gap」一类的**现状结论**（不是设计决策, 不是未来计划）。

**锚点格式**（AGENTS.md §1.7）:

```
{仓库标识}@{短SHA}:{路径}#L{行号}
```

例: `B@a1b2c3d:src/service.ts#L42`。仓库标识取自 AGENTS.md §1.1 的「标识」列。

**抽查步骤**:

1. 列出待抽查的 Tech Design 目录（`tech_design/*/`），每目录取 1 到 3 条现状结论。
2. 对每条结论, 找它引用的代码位置（文件路径 + 行号）。
3. 核对是否满足:
   - 锚点字符串存在, 且格式为 `{标识}@{短SHA}:{路径}#L{行号}`;
   - `{标识}` 是 AGENTS.md §1.1 登记过的标识;
   - `{路径}` 在该标识对应的仓库内可解析;
   - `{行号}` 落在该路径的文件内。
4. 缺锚点或锚点解析不了的, 在报告里列 `⚠`, **不计入违规数, 不改退出码**。

**0 代码仓项目**: 没有可引用的代码现状, 现状结论写「不适用」即可, 本步骤跳过, 不产生 ⚠。

**只读命令**（抽查只用这些, 不改动工作区）:

```bash
git -C <仓库本地路径> rev-parse --short HEAD
git -C <仓库本地路径> show <短SHA>:<路径> | wc -l
```

### 4. Reporting Phase

按以下结构汇总：

```markdown
## Validate-Spec Report

### 总体状态
- ssdctl.py gate: ✓ pass / ✗ N violations
- ssdctl.py scan --check: ✓ pass / ✗ N violations
- skills-integrity.sh: ✓ pass / ✗ N violations

### 总体判定
以命令退出码为准: 全部 0 → ✅ 通过; 任一非 0 → ❌ 未通过。

### 详细报告
[各脚本完整输出]

### 违规清单（如有）
[按脚本分类列出]

### 可选层状态
| 层 | 状态 | 说明 |
|----|------|------|
| test_cases/ | ○ 未启用 / ✓ 已启用 | 目录不存在则跳过 |
| PRD 台账 | ○ 未启用 / ✓ 已启用 | 无 PRDS.md 则跳过 |
| PRD 关联矩阵 | ○ 未启用 / ✓ 已启用 | README 无该章节则跳过 |
| deep/ 理解层 | 不校验 | 本 skill 不覆盖 |
| 实现基线 | ○ 跳过 / ✓ 已核对 | 0 代码仓则跳过 |

### 证据锚点抽查（⚠ 警告, 不影响判定）
| 位置 | 现状结论 | 锚点 | 状态 |
|------|----------|------|------|
| tech_design/{date}-{topic}/README.md | {结论摘要} | {标识}@{短SHA}:{路径}#L{行号} | ✓ / ⚠ 缺锚点 |

### 下一步
- 若 0 violations: ✅ 所有新文件符合规范
- 若有 violations: 按 "Anti-Patterns" 段修复
- 若有跳过项: 对应可选层未启用, 无须处理
- 若有锚点 ⚠: 建议补锚点, 但不阻塞交付
```

> **判定原则**: 只有命令退出码决定 pass/fail。锚点 ⚠ 是建议项, 不阻塞。

## 禁止行为 (Agent 权限边界)

本 skill 是**只读校验**: 它不产出制品, 也不改状态。

| ❌ Don't | ✅ Do |
|----------|-------|
| 校验过程中 `git commit` / `git push` | 只读; 不改工作区文件 |
| 校验过程中手改状态行 / 复审块 | 只读; 状态推进一律走 `bash scripts/ssdctl.sh advance` |
| 改写脚本退出码或把 `⚠` 记成 `✗` | 退出码是唯一判定依据; 符号语义照输出符号表 |
| 修改 `schema/**` 下的模板 | 只读 `schema/` |
| 某个脚本失败就静默跳过 | 逐个记录退出码, 失败如实写进报告 |
| 为凑锚点编造 SHA / 行号 | 锚点必须真实可解析; 拿不准就不写锚点 |

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 跳过验证直接提交 | 提交前必跑 validate-spec |
| 忽略 `⚠` 警告 | 检查警告是否影响功能 |
| 看到 `✗` 不修复就提交 | 先修复再提交 |
| 修改存量旧格式文件触发违规 | 用双模式 `○` 跳过即可 |
| 误以为 `v2 format` 是错误 | 这是双模式保护历史文件，**不是错误** |
| 把可选层缺失当失败 | 可选层不存在 = 跳过, 不是违规 |
| 因为缺锚点就把报告判成失败 | 锚点只报 ⚠, 判定只看脚本退出码 |
| 为凑锚点编造 SHA 或行号 | 锚点必须真实可解析; 拿不准就不写锚点 |
| 把 `deep/` 内容纳入本 skill 校验 | `deep/` 不在本 skill 校验范围 |
| 手拼 `scripts/check-*.sh` 代替 `ssdctl.py` | 判据与门禁只走 `scripts/ssdctl.py`; 底层脚本由 `gate` 统一调用 |

## Troubleshooting

### Q1：`ssdctl gate` 报"文件名应为 `{date}-{topic}.md`,实为 `{topic}.md`"

**症状**：Plan 文件名不带日期前缀

**原因**：旧 Plan 文件命名（`{topic}.md`）不符合当前规范（`{date}-{topic}.md`）

**排查**：
```bash
ls plan/{date}-{topic}/
```

**处理**：
- **新 Plan**：用 `{date}-{topic}.md` 命名
- **旧 Plan**：脚本已做双模式容忍

### Q2：`ssdctl gate` 报"缺少必填子文件"（tech_design）

**症状**：tech_design 目录缺 README.md / ards.md 等

**原因**：目录不满足当前 TD 结构（默认 v4 四子文件 / v3 存量六子文件）

**处理**：
- **新 tech_design**：按默认 v4 四子文件写（README + ards + apis + data-model）
- **存量 v3 tech_design**：按 v3 六子文件写, 校验脚本按目录内是否有 `ards.md` / `apis.md` 自动分流
- **极旧单文件目录**：脚本走 `○ v2 跳过`

### Q3：`ssdctl gate` 报"非法引用类型"（误报）

**症状**：报 `AES-256` / `SHA-256` / `EAN-13` 等业务值为非法引用

**原因**：底层追溯校验 T5 已简化（只扫描白名单引用）

**处理**：确认仓内追溯校验是否更新到当前版本。如果是旧的，重新同步。

### Q4：`ssdctl gate` 报"引用 KD-N 但不存在"

**症状**：Plan 引用 KD-3，但 TD 的决策文件里没有 `## KD-3:`

**处理**（按 TD 代际定位文件）:
1. v4（默认）→ 在 `tech_design/{date}-{topic}/ards.md` 补 `## KD-3: {name}` 段
2. v3 存量 → 在 `tech_design/{date}-{topic}/decisions.md` 补 `## KD-3: {name}` 段
3. 或从 Plan 删除 KD-3 引用

> 判定代际: 目录内有 `ards.md` 或 `apis.md` → v4; 否则 → v3 存量。

### Q5：跑命令报"路径不存在"

**症状**：`bash scripts/ssdctl.sh: line N: ... No such file`

**原因**：当前工作目录不是 SSD-Template 仓根目录

**处理**：
```bash
cd 仓库根
bash scripts/ssdctl.sh gate
```

### Q6：锚点抽查报"路径解析不了"

**症状**：`⚠ tech_design/.../README.md 现状结论缺锚点` 或锚点里的路径找不到

**排查**：
```bash
# 核对 §1.1 登记的标识与本地路径
sed -n '/^### 1\.1/,/^### 1\.2/p' AGENTS.md
```

**处理**:
- 标识写错 → 改成 §1.1 登记的标识
- 路径写错 → 改成仓库内相对路径
- 该结论确实不需要引代码 → 保留现状, 不强凑锚点（⚠ 不阻塞交付）

## Tips

- **只走唯一入口**：`bash scripts/ssdctl.sh gate` 覆盖全部门禁; 不要手拼 `scripts/check-*.sh`
- **顺序建议**：先 `scan --check`（调度一致性，最快），再 `gate`（全仓门禁，最严）
- **判定只看退出码**：锚点 ⚠ 和可选层跳过都不改变判定
- **`○` 跳过不是错误**：保护历史文件与未启用的可选层, 新文件不会触发
- **修改存量前先跑 baseline**：记录修改前的 violation 数，避免误以为修改引入新问题
- **CI 集成**：CI 的「门禁」步骤跑 `bash scripts/acceptance/run-all-gates.sh`（内部消费 `bash scripts/ssdctl.sh gate --json`，门禁清单真源 = `scripts/lib/commands.py` 的 `GATE_SCRIPTS`），派生数据一致性跑 `bash scripts/ssdctl.sh scan --check`
- **PR 前必跑**：避免把违规带入主分支

## Examples

### Pass (新文件符合规范)

```
User: 校验整个仓库的 spec 规范
Agent: phase: running
Agent: === ssdctl.sh gate ===
Agent: ✓ 8 个仓内门禁全部通过 (exit 0)
Agent: ✓ 判据: 制品 / 跨层 / 仓库 三组全部通过 (0 阻断失败 / 0 警告)
Agent: ✓ 制品自洽性: 0 处不自洽
Agent: === ssdctl.sh scan --check ===
Agent: ✓ 调度一致性: 派生索引与状态块一致
Agent: phase: integrity
Agent: ✓ skills-integrity.sh: 8 个规格 skill 的 front matter 与引用一致
Agent: phase: spot-checking
Agent: 抽查 tech_design/2026-07-03-login/README.md 现状结论 2 条
Agent: ✓ B@a1b2c3d:src/service.ts#L42 锚点可解析
Agent: ⚠ tech_design/2026-07-03-login/ards.md 现状 Gap 表 1 条缺锚点 (建议补, 不阻塞)
Agent: phase: reporting
Agent: ✅ 所有新文件符合规范 (锚点 ⚠ 1 条, 不影响判定)
```

### Violation

```
User: 校验 plan/2026-07-03-login/login.md
Agent: phase: running
Agent: ✗ ssdctl gate: 缺 V-1 验证用例
Agent: phase: reporting
Agent: ## Validate-Spec Report
Agent: ### 违规清单
Agent: - plan/2026-07-03-login/login.md 缺少 `### V-1:`(验证用例)
Agent: ### 下一步
Agent: 在 `## 验证用例` 段补 `### V-1: {场景名}`
```

### Optional Layers Disabled (默认形态)

```
User: 校验整个仓库的 spec 规范
Agent: ✓ ssdctl gate: 8 个仓内门禁全部通过 (exit 0)
Agent: ✓ 命名与层结构: 制品 0 个 (可选层未启用, 跳过)
Agent: ✓ 追溯: 0 项全部通过
Agent: ### 可选层状态
Agent: | test_cases/ | ○ 未启用 | 目录不存在则跳过 |
Agent: | PRD 台账 | ○ 未启用 | 无 PRDS.md 则跳过 |
Agent: | PRD 关联矩阵 | ○ 未启用 | README 无该章节则跳过 |
Agent: | deep/ 理解层 | 不校验 | 本 skill 不覆盖 |
Agent: ✅ 校验通过
```

## 安装 (Installation)

skill 定义随仓库分发, agent 直接读 `.agents/skills/validate-spec/SKILL.md` 即可, **无需注册**。

需要把 skill 装进宿主 agent 的 skills 根目录时, 用仓内安装脚本：

```bash
bash <repo>/.agents/skills/install.sh                     # 默认 ~/.codex/skills/
bash <repo>/.agents/skills/install.sh --target <dir>      # 指定目标
bash <repo>/.agents/skills/install.sh --unregister        # 注销
```

## Related Skills

- `.agents/skills/to-prd/SKILL.md`：原始需求 → PRD（产生新文件）
- `.agents/skills/to-tech-design/SKILL.md`：PRD → Tech Design（产生新目录）
- `.agents/skills/to-plan/SKILL.md`：Tech Design → Plan（产生新文件）
- `.agents/skills/to-deep-understand/SKILL.md`：可选理解层（`deep/`），**不走本 skill 校验**

## Cross-References

- <repo>/AGENTS.md §1（多仓上下文，如需明确仓库清单）
- <repo>/AGENTS.md §1.6（实现基线约定）
- <repo>/AGENTS.md §1.7（证据锚点约定）
- <repo>/scripts/ssdctl.py（判据与门禁唯一入口）
- <repo>/schema/criteria.json（判据机器权威）
- <repo>/scripts/check-repo-baseline.sh（TD 实现基线段核对；由仓内门禁统一触发，skill 不单独手拼）
- <repo>/.agents/skills/validate-spec/skills-integrity.sh（skill 目录自检）
- <repo>/AGENTS.md §3.4（门禁清单）
- <repo>/WORKFLOW.md（脚本使用方式）
