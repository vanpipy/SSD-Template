---
name: validate-spec
description: 跑 SSD-Template 全部 spec 校验脚本 (check-md-schema / check-traceability / check-naming), 输出统一报告。支持 v4/v3 双模式 TD + Test Case 可选层 (test_cases/ 目录存在才校验)。Use when 完成 PRD / Tech Design / Plan 产出后, 需要快速验证是否符合规范; 或修改存量 spec 文件后, 需要确认无新违规。
skill-type: spec
version: 1.1
type: skill
skill-role: tool
---

# validate-spec

跑 SSD-Template 全部 3 个 spec 校验脚本，输出统一报告。

## Mode Indicator

```
[MODE: validate-spec] (running | reporting)
```

| Phase | 做什么 |
|-------|--------|
| `running` | 跑 check-md-schema.sh / check-traceability.sh / check-naming.sh |
| `reporting` | 输出统一报告（pass / v2 skip / violation） |

## When to Use

- 完成 PRD / Tech Design / Plan 产出后，验证是否符合规范
- 修改存量 spec 文件后，确认无新违规
- 提交 PR 前，做最终验证
- 想知道当前仓库 spec 健康度

## Slash Command

```
/validate-spec                # 验证整个仓库
/validate-spec prd/2026-07-03-processed/login.md   # 验证单个文件
/validate-spec tech_design/2026-07-03-login/       # 验证单个目录
```

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| Scripts | `scripts/check-md-schema.sh` / `check-traceability.sh` / `check-naming.sh` | 3 个校验脚本 |
| 工作目录 | pos-wiki 仓根目录 | scripts 假设此位置 |

## Core Concept

### 校验维度

| 脚本 | 检查项 | v3 双模式 |
|------|--------|----------|
| `check-md-schema.sh` | 必填段（Why / Goal / Scenarios / Review 等）| ✓ 容忍 v2 旧文件 |
| `check-traceability.sh` | KD / V 闭环、引用一致性 | ✓ 不误报业务值 |
| `check-naming.sh` | 目录/文件命名规范（`{date}-{topic}`）| ✓ 修复 DATE_RE bash bug |

### 输出符号

| 符号 | 含义 | 严重度 |
|------|------|--------|
| `✓` | 通过 | — |
| `○` (黄色) | v2 旧文件跳过 v3 校验 | 信息 |
| `⚠` (黄色) | 警告（如缺 interactions.md）| 警告 |
| `✗` (红色) | 违规 | 错误 |

## Execution Steps

### 1. Running Phase

依次跑 3 个脚本：

```bash
echo "=== check-naming.sh ==="
./scripts/check-naming.sh

echo ""
echo "=== check-md-schema.sh ==="
./scripts/check-md-schema.sh

echo ""
echo "=== check-traceability.sh ==="
./scripts/check-traceability.sh
```

### 2. Reporting Phase

按以下结构汇总：

```markdown
## Validate-Spec Report

### 总体状态
- check-naming.sh: ✓ pass / ✗ N violations
- check-md-schema.sh: ✓ pass (含 X 项 v2 跳过) / ✗ N violations
- check-traceability.sh: ✓ pass / ✗ N violations

### 详细报告
[各脚本完整输出]

### 违规清单（如有）
[按脚本分类列出]

### 下一步
- 若 0 violations: ✅ 所有新文件符合 v3 规范
- 若有 violations: 按 "Anti-Patterns" 段修复
- 若有 v2 跳过: 旧文件保持现状，无须处理
```

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 跳过验证直接提交 | 提交前必跑 validate-spec |
| 忽略 `⚠` 警告 | 检查警告是否影响功能 |
| 看到 `✗` 不修复就提交 | 先修复再提交 |
| 修改存量 v2 文件触发违规 | 用双模式 `○` 跳过即可 |
| 误以为 `v2 format` 是错误 | 这是双模式保护历史文件，**不是错误** |

## Troubleshooting

### Q1：check-naming.sh 报"文件名应为 `{date}-{topic}.md`,实为 `{topic}.md`"

**症状**：Plan 文件名不带日期前缀

**原因**：v2 Plan 文件命名（`{topic}.md`）不符合 v3（`{date}-{topic}.md`）

**排查**：
```bash
ls plan/{date}-{topic}/
```

**处理**：
- **新 Plan**：用 v3 命名 `plan/{date}-{topic}/{date}-{topic}.md`
- **v2 旧 Plan**：脚本已修复 DATE_RE bash bug + 双模式容忍

### Q2：check-md-schema.sh 报"缺少必填子文件"（tech_design）

**症状**：tech_design 目录缺 README.md / decisions.md 等

**原因**：v2 单文件目录（只有 `{topic}.md`）不满足 v3 7 子文件结构

**处理**：
- **新 tech_design**：写 7 子文件结构
- **v2 旧 tech_design**：脚本已打双模式补丁（无 README.md → 走 `○ v2 跳过`）

### Q3：check-md-schema.sh 报"非法引用类型"（误报）

**症状**：报 `AES-256` / `SHA-256` / `EAN-13` 等业务值为非法引用

**原因**：v3 check-traceability.sh T5 已简化（只扫描白名单引用）

**处理**：确认 scripts/check-traceability.sh 是否更新到 v3 双模式补丁。如果是旧的，重新复制。

### Q4：check-traceability.sh 报"引用 KD-N 但不存在"

**症状**：Plan 引用 KD-3，但 tech_design/decisions.md 没有 `## KD-3:`

**处理**：
1. 在 `tech_design/{topic}/decisions.md` 补 `## KD-3: {name}` 段
2. 或从 Plan 删除 KD-3 引用

### Q5：跑脚本报"路径不存在"

**症状**：`./scripts/check-md-schema.sh: line N: ... No such file`

**原因**：当前工作目录不是 pos-wiki 仓根目录

**处理**：
```bash
cd /home/leroy/Project/pos-wiki
./scripts/check-md-schema.sh
```

## Tips

- **3 个脚本都要跑**：单一脚本不能覆盖所有检查项
- **顺序建议**：先 check-naming（最快），再 check-md-schema（最广），最后 check-traceability（最严）
- **`○ v2 跳过` 不是错误**：保护历史文件，新文件不会触发
- **修改存量前先跑 baseline**：记录修改前的 violation 数，避免误以为修改引入新问题
- **CI 集成**：可在 `.github/workflows/ci.yml` 加 `./scripts/check-md-schema.sh && ./scripts/check-traceability.sh && ./scripts/check-naming.sh`
- **PR 前必跑**：避免把违规带入主分支

## Examples

### Pass (新文件符合 v3)

```
User: /validate-spec
Agent: [MODE: validate-spec] (running)
Agent: === check-naming.sh ===
Agent: ✓ 命名规范: 64 项全部通过 (新增 1 项)
Agent: === check-md-schema.sh ===
Agent: ✓ 字段校验: 51 项全部通过 (新增 1 项)
Agent: === check-traceability.sh ===
Agent: ✓ 追溯校验: 1 项全部通过
Agent: [MODE: validate-spec] (reporting)
Agent: ✅ 所有新文件符合 v3 规范
```

### Violation

```
User: /validate-spec
Agent: [MODE: validate-spec] (running)
Agent: ✗ check-md-schema.sh: 缺 V-1 验证用例
Agent: [MODE: validate-spec] (reporting)
Agent: ## Validate-Spec Report
Agent: ### 违规清单
Agent: - plan/2026-07-03-login/login.md — 缺少 `### V-1:`(验证用例)
Agent: ### 下一步
Agent: 在 `## 验证用例` 段补 `### V-1: {场景名}`
```

### V2 Skip (历史文件保护)

```
User: /validate-spec
Agent: ✓ check-md-schema.sh: 50 项全部通过 (含 13 项 v2 Plan 跳过)
Agent: ✓ check-naming.sh: 63 项全部通过
Agent: ✓ check-traceability.sh: 0 项全部通过
Agent: ✅ 新文件符合 v3 规范,历史 v2 文件保护跳过
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

## Cross-References

- <repo>/AGENTS.md §1（多仓上下文，如需明确仓库清单）
- <repo>/scripts/check-md-schema.sh（v3 双模式）
- <repo>/scripts/check-traceability.sh（v3 双模式）
- <repo>/scripts/check-naming.sh（v3 双模式 + DATE_RE 修复）
- <repo>/AGENTS.md §3.4（门禁清单）
- <repo>/HOW_TO_USE.md（脚本使用方式）