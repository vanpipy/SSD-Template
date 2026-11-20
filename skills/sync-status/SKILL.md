---
name: sync-status
description: SSD-Template 四层文档生命周期编排。Implemented 人工回写、Deprecated 跨层级联、复审回退 Draft。Use when 外部代码仓 PR merged 需要回写三件套 Implemented；或上游 PRD/TD 标 Deprecated 需要级联降级下游 TD/Plan/Test Cases；或上游复审变更需要下游回退 Draft 标「需重审」。
skill-type: spec
version: 1.1
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
| 状态枚举口径 | `AGENTS.md` §3.3 | 四层统一枚举 + 级联规则 |
| 追溯校验 | `scripts/check-traceability.sh` | T8（supersede↔Deprecated）/ T12（漏级联兜底） |
| 统计回写 | `scripts/sync-prd.sh` | README 统计块状态分布刷新 |
| 用例索引 | `scripts/sync-test-index.sh` | test_cases 状态变化后再生成 `_index.md` |
| 关联矩阵 | 根 `README.md`「PRD关联矩阵」 | Deprecated（被取代）时登记 supersede 边 |

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
3. 被取代场景：同步在根 README「PRD关联矩阵」登记 `supersede` 边（T8 双向校验）
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

T12 报「上游已 Deprecated 但本文档仍 Ready/Implemented」即漏级联。回到 cascading 阶段补齐。

### `scripts/sync-prd.sh` 接口

该脚本负责**机械刷新根 README 的统计块**, 是确定性脚本（幂等, 无 LLM, 无网络）。

| 项 | 约定 |
|----|------|
| 调用方式 | `./scripts/sync-prd.sh`（在仓根目录执行）|
| 作用范围 | 只重写根 `README.md` 里 `<!-- prd-stats:begin -->` 与 `<!-- prd-stats:end -->` 两个标记之间的内容; 标记外的内容**永不触碰** |
| 标记缺失 | 跳过统计块重写并告警, **不报错**（不阻断本 skill 的状态回写）|
| 退出码 0 | 无待办, 统计块已刷新 |
| 退出码 1 | 存在待办项（台账里仍有 `待分析` / `待抓取` 行）。**这是台账待办信号, 不是状态回写失败** |
| 退出码 2 | 环境错误（脚本无法正常工作, 例如缺少必要工具或台账文件结构不可解析）|

**退出码 1 的处置**（操作者要做什么）:

1. 读脚本输出里被点名的台账行（`待分析` / `待抓取`）。
2. 对 `待分析` 行: 读该行「关联素材」指向的素材原文, 补齐 `优先级` / `验收要点` / `提出人` 三列。
3. 对 `待抓取` 行: 该行 `来源=external` 且有 URL 但 `创建时间` 为空。需要**项目自定义的外部来源抓取 skill** 去取内容并回填 `创建时间`。模板**不内置任何抓取器**。
4. 补完后重跑 `./scripts/sync-prd.sh`, 退出码回到 0 才算收尾完成。

> **退出码 1 不阻塞状态回写本身**。Deprecated 级联 / Implemented 回写的正确性由 `check-traceability.sh` 的退出码判定; `sync-prd.sh` 的退出码只反映台账待办。
> **退出码 2 需要人工介入**: 修好环境后重跑, 不要跳过。

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 只改上游状态不管下游 | 级联是全量义务，T12 会兜底暴露漏级联 |
| 三件套分批回写 Implemented | 三层同时回写（一致性规则） |
| 级联时删除/改写下游内容 | 只改状态行与备注，内容保留待重审 |
| Deprecated 不登记矩阵 supersede 边 | 被取代场景必须登记（T8 校验） |
| test_cases 跟着三件套联动 | Test Cases 独立生命周期，只响应上游 Deprecated/回退级联 |
| 手改 `test_cases/_index.md` 状态列 | 跑 `scripts/sync-test-index.sh` 再生成 |
| 手改 README 统计块里的数字 | 跑 `scripts/sync-prd.sh` 再生成, 只改标记之间 |
| 把 `sync-prd.sh` 退出码 1 当成回写失败 | 退出码 1 = 台账有待办行, 补齐标记行即可, 不影响状态回写 |
| 因为统计块标记缺失就中断回写 | 标记缺失时脚本告警跳过, 不报错 |

## Tips

- 级联前先 `grep -rl <key> tech_design/ plan/ test_cases/` 拿全清单，避免漏文件
- TD 目录内子文件**普遍自带状态行**（`> **状态**:`）。级联时全目录处理（README + 各子文件状态行一并降级，备注写在 README）
- 备注行写清「级联来源 + 日期」，便于审计与未来复活
- `check-traceability.sh` 的 T12 是**兜底**不是替代：先人工/skill 级联，T12 只负责发现遗漏
- `sync-prd.sh` 的退出码 1 是**台账待办**, 不是状态回写失败; 补齐被点名的台账行再重跑
- `sync-prd.sh` 只重写统计块标记之间的内容, 标记外不动; 标记缺失时告警跳过

## Related Skills

- `to-test-cases`：Test Cases 状态机定义（本 skill 编排其 Deprecated/Implemented 转换）
- `validate-spec`：收尾复核
- `sync-prd`：PRD 台账同步（可选层; 本 skill 收尾调用其 `scripts/sync-prd.sh` 刷新统计块）

## Cross-References

- <repo>/AGENTS.md §3.3（状态流转与级联规则）
- <repo>/AGENTS.md §1.1（仓库清单）
- <repo>/HOW_TO_USE.md 状态机详解（跨层协调规则）
- <repo>/scripts/check-traceability.sh（T8 / T12）
- <repo>/scripts/sync-prd.sh（README 统计块刷新 + 台账巡检）
- <repo>/schema/prd-ledger.md（台账模板与哨兵定义）
- <repo>/schema/prd-matrix.md（8 类关系枚举）
- <repo>/AGENTS.md §3.3（Test Cases 状态由 /sync-status 编排）
