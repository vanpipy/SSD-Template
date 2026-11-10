---
name: sync-status
description: SSD-Template 四层文档生命周期编排——Implemented 人工回写、Deprecated 跨层级联、复审回退 Draft。Use when 外部代码仓 PR merged 需要回写三件套 Implemented；或上游 PRD/TD 标 Deprecated 需要级联降级下游 TD/Plan/Test Cases；或上游复审变更需要下游回退 Draft 标「需重审」。
skill-type: spec
version: 1.0
type: skill
skill-role: procedure
---

# sync-status

四层文档（PRD / Tech Design / Plan / Test Cases）的状态机**操作编排**。状态枚举统一为 `Draft / Ready / Implemented / Deprecated`；本 skill 不新增状态，只编排转换，并在收尾跑校验兜底。

## Mode Indicator

```
[MODE: sync-status] (locating | writing-back | cascading | validating)
```

| Phase | 做什么 |
|-------|--------|
| `locating` | 定位目标文档与其上下游引用链（grep 仓内路径引用） |
| `writing-back` | 回写状态行 + 备注（转换原因 / 级联来源 / 日期） |
| `cascading` | 按级联规则处理所有下游文档 |
| `validating` | 跑 check-traceability（T8/T12）+ sync-prd.sh 统计回写 + sync-test-index.sh（如涉及 test_cases） |

## When to Use

- 外部代码仓 PR merged，需要回写三件套 `Implemented`（三件套必须同时转换）
- 某 PRD / TD 被标 `Deprecated`，需要级联降级所有引用它的下游文档
- 上游复审决定重大变更（回退 Draft），下游需要回退并标「需重审」
- Test Cases 冒烟/全量执行通过，需要回写 `Implemented`（独立于三件套）

## Slash Command

```
/sync-status implement <plan-path>        # 三件套 Implemented 回写
/sync-status deprecate <prd-or-td-path>   # Deprecated 级联
/sync-status rollback <prd-path>          # 复审回退 Draft（下游标需重审）
/sync-status test-done <test-case-path>   # Test Cases Ready → Implemented
```

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| 状态枚举口径 | `AGENTS.md` §3.5 | 四层统一枚举 + 级联规则 |
| 追溯校验 | `scripts/check-traceability.sh` | T8（supersede↔Deprecated）/ T12（漏级联兜底） |
| 统计回写 | `scripts/sync-prd.sh` | README 统计块状态分布刷新 |
| 用例索引 | `scripts/sync-test-index.sh` | test_cases 状态变化后再生成 `_index.md` |
| 关联矩阵 | `README.md`「PRD关联矩阵」 | Deprecated（被取代）时登记 supersede 边 |

## 上下游链（机制一致性）

| 方向 | 对象 | 关系 |
|------|------|------|
| 服务对象 | `to-prd` / `to-tech-design` / `to-plan` / `to-test-cases` 的产出物 | 本 skill 只改状态与备注，不改内容结构 |
| 兜底校验 | `validate-spec` | 收尾复核，确认无新违规 |

## Core Concept

### 转换一：Implemented 回写（人工触发）

| 场景 | 规则 |
|------|------|
| 三件套 | PRD / TD / Plan **必须同时**回写 `Implemented`（不允许单层先转换）；状态行后缀注明回写依据（如「代码仓 PR #N merged」） |
| Test Cases | **独立生命周期**：冒烟/全量执行通过后单独回写 `Implemented`，不与三件套联动 |
| 0 关联代码仓 | 停留 Ready，备注「Awaiting TDD in external code repo」 |

### 转换二：Deprecated 级联（强制）

上游标 Deprecated 时，**所有引用它的下游文档必须级联降级**：

| 上游 | 级联范围 | 动作 |
|------|---------|------|
| PRD Deprecated | 引用该 PRD 的 TD / Plan / Test Cases | 状态 → `Deprecated`，备注「级联自上游 {path}（{日期}）」 |
| TD Deprecated | 引用该 TD 的 Plan / Test Cases | 同上 |

操作步骤：

1. `locating`：以 `{date}/{topic}.md`（PRD）或 `tech_design/{date}-{topic}`（TD）为 key，grep `tech_design/ plan/ test_cases/` 全部 `.md`，得到下游清单
2. `cascading`：逐份改状态行 + 备注行（quote 块文档改 `> **状态**:`；test_cases 改元信息表「状态」行）
3. 被取代场景：同步在 README「PRD关联矩阵」登记 `supersede` 边（T8 双向校验）
4. `validating`：跑 `check-traceability.sh`（T8 + T12 应通过）+ `sync-prd.sh`（统计分布刷新）；涉及 test_cases 时跑 `sync-test-index.sh` 再生成索引

### 转换三：复审回退（上游重大变更）

| 条件 | 动作 |
|------|------|
| 上游 PRD/TD 复审决定重大变更（回退 Draft） | 下游 TD / Plan / Test Cases 状态回退 `Draft`，备注「需重审（上游 {path} 于 {日期} 回退）」 |
| 仅轻微修订 | 不触发回退；下游在备注记录「上游已更新，待复核」 |

### 收尾校验（必做）

```bash
./scripts/check-traceability.sh   # T8 supersede↔Deprecated + T12 级联一致性
./scripts/sync-prd.sh             # README 统计块刷新（各层状态分布）
./scripts/sync-test-index.sh      # 仅当 test_cases 状态变化
```

T12 报「上游已 Deprecated 但本文档仍 Ready/Implemented」即漏级联——回到 cascading 阶段补齐。

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 只改上游状态不管下游 | 级联是全量义务，T12 会兜底暴露漏级联 |
| 三件套分批回写 Implemented | 三层同时回写（一致性规则） |
| 级联时删除/改写下游内容 | 只改状态行与备注，内容保留待重审 |
| Deprecated 不登记矩阵 supersede 边 | 被取代场景必须登记（T8 校验） |
| test_cases 跟着三件套联动 | Test Cases 独立生命周期，只响应上游 Deprecated/回退级联 |
| 手改 `test_cases/_index.md` 状态列 | 跑 `scripts/sync-test-index.sh` 再生成 |

## Tips

- 级联前先 `grep -rl <key> tech_design/ plan/ test_cases/` 拿全清单，避免漏文件
- TD 目录内子文件**普遍自带状态行**（`> **状态**:`）——级联时全目录处理（README + 各子文件状态行一并降级，备注写在 README）
- 备注行写清「级联来源 + 日期」，便于审计与未来复活
- `check-traceability.sh` 的 T12 是**兜底**不是替代：先人工/skill 级联，T12 只负责发现遗漏

## Related Skills

- `to-test-cases`：Test Cases 状态机定义（本 skill 编排其 Deprecated/Implemented 转换）
- `validate-spec`：收尾复核
- `sync-prd`：README 统计块回写（本 skill 收尾调用其脚本）

## Cross-References

- <repo>/AGENTS.md §3.5（状态流转与级联规则）
- <repo>/HOW_TO_USE.md 状态机详解（跨层协调规则）
- <repo>/scripts/check-traceability.sh（T8 / T12）
- <repo>/docs/2026-08-06-test-cases-mechanism.md（Layer 4 级联设计）
