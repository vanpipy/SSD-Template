---
name: validate-spec
description: 跑 SSD-Template 全部 spec 校验脚本 (check-md-schema / check-traceability / check-naming), 输出统一报告。支持 v4/v3 双模式 TD + 可选层 (test_cases/ 台账/ 关联矩阵/ deep/ 按存在与否条件启用) + 证据锚点人工抽查 (只报 ⚠, 不改退出码)。Use when 完成 PRD / Tech Design / Plan 产出后, 需要快速验证是否符合规范; 或修改存量 spec 文件后, 需要确认无新违规。
skill-type: spec
version: 1.2
type: skill
skill-role: tool
---

# validate-spec

跑 SSD-Template 全部 spec 校验脚本, 输出统一报告。

## Mode Indicator

```
[MODE: validate-spec] (running | spot-checking | reporting)
```

| Phase | 做什么 |
|-------|--------|
| `running` | 跑 check-md-schema.sh / check-traceability.sh / check-naming.sh |
| `spot-checking` | 人工抽查 Tech Design「现状结论」的证据锚点（**只报 ⚠, 不改任何脚本退出码**）|
| `reporting` | 输出统一报告（pass / skip / violation / 锚点警告）|

## When to Use

- 完成 PRD / Tech Design / Plan 产出后，验证是否符合规范
- 修改存量 spec 文件后，确认无新违规
- 提交 PR 前，做最终验证
- 想知道当前仓库 spec 健康度

## Slash Command

```
/validate-spec                # 验证整个仓库
/validate-spec prd/2026-07-03/login.md   # 验证单个文件
/validate-spec tech_design/2026-07-03-login/       # 验证单个目录
```

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| Scripts | `scripts/check-md-schema.sh` / `check-traceability.sh` / `check-naming.sh` | 3 个基础校验脚本 |
| 基线脚本 | `scripts/check-repo-baseline.sh` | TD「实现基线」段核对（**仅项目关联代码仓时启用**）|
| 工作目录 | SSD-Template 仓根目录 | scripts 假设此位置 |

## Core Concept

### 校验维度

| 脚本 | 检查项 | 兼容策略 |
|------|--------|----------|
| `check-md-schema.sh` | 必填段（Why / Goal / Scenarios / Review 等）| 容忍旧格式文件 |
| `check-traceability.sh` | KD / V 闭环、引用一致性 | 不误报业务值 |
| `check-naming.sh` | 目录/文件命名规范（`{date}-{topic}`）| 容忍旧命名 |
| `check-repo-baseline.sh` | TD「实现基线」段（仓库 / 分支 / SHA / 核对日期 / 核对项 / 状态）| 0 代码仓项目按「不适用」跳过 |

### 可选层与条件启用

以下层是**可选的**, 默认不启用。**校验脚本按「目录 / 文件是否存在」决定是否启用对应检查**; 产物不存在时, 对应检查**跳过, 不是失败**。

| 可选层 | 启用条件 | 不存在时的行为 |
|--------|----------|----------------|
| Layer 4 测试用例 | `test_cases/` 目录存在 | 跳过 T9 / T11 / T12 用例相关检查 |
| PRD 台账 | `material/{date}/PRDS.md` 存在（`schema/prd-ledger.md` 模板）| 跳过台账一致性检查 |
| PRD 关联矩阵 | 根 `README.md` 含「PRD关联矩阵」章节 | 跳过关系边检查 |
| 理解层 `deep/` | `deep/` 目录存在 | **本 skill 完全不校验 `deep/` 内容**（见下）|
| 实现基线 | 项目关联代码仓（AGENTS.md §1.1 登记了非 A 标识）且 TD 目录存在 | 0 代码仓项目跳过基线核对 |

> **理解层 `deep/` 明确不在校验范围**。`deep/` 是可选知识层, `/validate-spec` 不校验它的内容与结构。需要检查 `deep/` 时用 `scripts/deep-scan.py` 的台账输出, 不走本 skill。

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

依次跑脚本：

```bash
echo "=== check-naming.sh ==="
./scripts/check-naming.sh

echo ""
echo "=== check-md-schema.sh ==="
./scripts/check-md-schema.sh

echo ""
echo "=== check-traceability.sh ==="
./scripts/check-traceability.sh

echo ""
echo "=== check-repo-baseline.sh ==="
# 仅项目关联代码仓时才有意义; 0 代码仓项目脚本自身按「不适用」跳过
[[ -f scripts/check-repo-baseline.sh ]] && ./scripts/check-repo-baseline.sh
```

**记录每个脚本的退出码**。退出码是脚本层面的唯一判定依据, 本 skill 不改写它。

### 2. Spot-Checking Phase (证据锚点抽查)

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

### 3. Reporting Phase

按以下结构汇总：

```markdown
## Validate-Spec Report

### 总体状态
- check-naming.sh: ✓ pass / ✗ N violations
- check-md-schema.sh: ✓ pass (含 X 项跳过) / ✗ N violations
- check-traceability.sh: ✓ pass / ✗ N violations
- check-repo-baseline.sh: ✓ pass / ○ 跳过 (0 代码仓) / ✗ N violations

### 总体判定
以脚本退出码为准: 全部 0 → ✅ 通过; 任一非 0 → ❌ 未通过。

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

> **判定原则**: 只有脚本退出码决定 pass/fail。锚点 ⚠ 是建议项, 不阻塞。

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

## Troubleshooting

### Q1：check-naming.sh 报"文件名应为 `{date}-{topic}.md`,实为 `{topic}.md`"

**症状**：Plan 文件名不带日期前缀

**原因**：旧 Plan 文件命名（`{topic}.md`）不符合当前规范（`{date}-{topic}.md`）

**排查**：
```bash
ls plan/{date}-{topic}/
```

**处理**：
- **新 Plan**：用 `{date}-{topic}.md` 命名
- **旧 Plan**：脚本已做双模式容忍

### Q2：check-md-schema.sh 报"缺少必填子文件"（tech_design）

**症状**：tech_design 目录缺 README.md / ards.md 等

**原因**：目录不满足当前 TD 结构（默认 v4 四子文件 / v3 存量六子文件）

**处理**：
- **新 tech_design**：按默认 v4 四子文件写（README + ards + apis + data-model）
- **存量 v3 tech_design**：按 v3 六子文件写, 校验脚本按目录内是否有 `ards.md` / `apis.md` 自动分流
- **极旧单文件目录**：脚本走 `○ v2 跳过`

### Q3：check-md-schema.sh 报"非法引用类型"（误报）

**症状**：报 `AES-256` / `SHA-256` / `EAN-13` 等业务值为非法引用

**原因**：check-traceability.sh T5 已简化（只扫描白名单引用）

**处理**：确认 scripts/check-traceability.sh 是否更新到当前版本。如果是旧的，重新复制。

### Q4：check-traceability.sh 报"引用 KD-N 但不存在"

**症状**：Plan 引用 KD-3，但 TD 的决策文件里没有 `## KD-3:`

**处理**（按 TD 代际定位文件）:
1. v4（默认）→ 在 `tech_design/{date}-{topic}/ards.md` 补 `## KD-3: {name}` 段
2. v3 存量 → 在 `tech_design/{date}-{topic}/decisions.md` 补 `## KD-3: {name}` 段
3. 或从 Plan 删除 KD-3 引用

> 判定代际: 目录内有 `ards.md` 或 `apis.md` → v4; 否则 → v3 存量。

### Q5：跑脚本报"路径不存在"

**症状**：`./scripts/check-md-schema.sh: line N: ... No such file`

**原因**：当前工作目录不是 SSD-Template 仓根目录

**处理**：
```bash
cd 仓库根
./scripts/check-md-schema.sh
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

- **3 个基础脚本都要跑**：单一脚本不能覆盖所有检查项; 有代码仓时再加跑 `check-repo-baseline.sh`
- **顺序建议**：先 check-naming（最快），再 check-md-schema（最广），最后 check-traceability（最严）
- **判定只看退出码**：锚点 ⚠ 和可选层跳过都不改变判定
- **`○` 跳过不是错误**：保护历史文件与未启用的可选层, 新文件不会触发
- **修改存量前先跑 baseline**：记录修改前的 violation 数，避免误以为修改引入新问题
- **CI 集成**：可在 `.github/workflows/ci.yml` 加 `./scripts/check-md-schema.sh && ./scripts/check-traceability.sh && ./scripts/check-naming.sh`
- **PR 前必跑**：避免把违规带入主分支

## Examples

### Pass (新文件符合规范)

```
User: /validate-spec
Agent: [MODE: validate-spec] (running)
Agent: === check-naming.sh ===
Agent: ✓ 命名规范: 64 项全部通过 (新增 1 项)
Agent: === check-md-schema.sh ===
Agent: ✓ 字段校验: 51 项全部通过 (新增 1 项)
Agent: === check-traceability.sh ===
Agent: ✓ 追溯校验: 1 项全部通过
Agent: [MODE: validate-spec] (spot-checking)
Agent: 抽查 tech_design/2026-07-03-login/README.md 现状结论 2 条
Agent: ✓ B@a1b2c3d:src/service.ts#L42 锚点可解析
Agent: ⚠ tech_design/2026-07-03-login/ards.md 现状 Gap 表 1 条缺锚点 (建议补, 不阻塞)
Agent: [MODE: validate-spec] (reporting)
Agent: ✅ 所有新文件符合规范 (锚点 ⚠ 1 条, 不影响判定)
```

### Violation

```
User: /validate-spec
Agent: [MODE: validate-spec] (running)
Agent: ✗ check-md-schema.sh: 缺 V-1 验证用例
Agent: [MODE: validate-spec] (reporting)
Agent: ## Validate-Spec Report
Agent: ### 违规清单
Agent: - plan/2026-07-03-login/login.md 缺少 `### V-1:`(验证用例)
Agent: ### 下一步
Agent: 在 `## 验证用例` 段补 `### V-1: {场景名}`
```

### Optional Layers Disabled (默认形态)

```
User: /validate-spec
Agent: ✓ check-md-schema.sh: 50 项全部通过 (含 13 项旧 Plan 跳过)
Agent: ✓ check-naming.sh: 63 项全部通过
Agent: ✓ check-traceability.sh: 0 项全部通过
Agent: ### 可选层状态
Agent: | test_cases/ | ○ 未启用 | 目录不存在则跳过 |
Agent: | PRD 台账 | ○ 未启用 | 无 PRDS.md 则跳过 |
Agent: | PRD 关联矩阵 | ○ 未启用 | README 无该章节则跳过 |
Agent: | deep/ 理解层 | 不校验 | 本 skill 不覆盖 |
Agent: ✅ 校验通过
```

## Slash Command Registration

通过 `<repo>/skills/setup.sh` 注册到 agent skills 目录：

```bash
bash <repo>/skills/setup.sh
```

## Related Skills

- `to-prd`：原始需求 → PRD（产生新文件）
- `to-tech-design`：PRD → Tech Design（产生新目录）
- `to-plan`：Tech Design → Plan（产生新文件）
- `to-deep-understand`：可选理解层（`deep/`），**不走本 skill 校验**

## Cross-References

- <repo>/AGENTS.md §1（多仓上下文，如需明确仓库清单）
- <repo>/AGENTS.md §1.6（实现基线约定）
- <repo>/AGENTS.md §1.7（证据锚点约定）
- <repo>/scripts/check-md-schema.sh（v4 / v3 双模式）
- <repo>/scripts/check-traceability.sh（双模式）
- <repo>/scripts/check-naming.sh（双模式 + DATE_RE 修复）
- <repo>/scripts/check-repo-baseline.sh（TD 实现基线段核对）
- <repo>/AGENTS.md §3.4（门禁清单）
- <repo>/HOW_TO_USE.md（脚本使用方式）
