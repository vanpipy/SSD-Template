---
name: sync-status
description: >-
  四层文档生命周期编排 (v2.1), 调度依据全部在仓内。agent 按判据自主推进: scan 给出可调度集合与依赖许可, criteria 判定, advance 代写状态块与复审块。
  Use when 需要按仓内调度谓词推进状态 (Draft 到 Ready 由判据驱动, Implemented 需外部事实, Deprecated 需外部事实依据),
  需要把上游 Deprecated 级联到下游, 或需要把上游重大变更回退给下游重审。人工接入与 agent 同一条流水线: 在仓内新增素材, 或在制品复审段自己写署名, 然后跑同一条 advance。
---

# sync-status

四层文档（PRD / Tech Design / Plan / Test Cases）的状态机**操作编排**。状态枚举统一为 `Draft / Ready / Implemented / Deprecated`；本 skill 不新增状态，只编排转换，并在收尾跑校验兜底。

> **调度依据在仓内, 不是外部编排器**: 可调度集合与依赖许可全部由 `bash scripts/ssdctl.sh scan` 从**制品状态块**推导。没有工单系统、没有 tracker、没有外部编排器参与判断。
> **推进主体是 agent**: 判据全绿即可由 `ssdctl advance` 代写状态块; 人工接入**走同一条流水线**; 在仓内新增素材, 或自己在制品的 `## 复审 (Review)` 段写署名, 然后跑**同一条** `advance`。

## 执行阶段 (内部 phase 标识)

agent 按下列 phase 顺序推进。每个 phase 开始时在汇报里写明 `phase: <name>`。

> phase 是 agent 的**内部工作分段**, 不依赖任何 UI 模式指示器, 也不假设运行环境会显示模式。

| Phase | agent 做什么 |
|-------|--------------|
| `scanning` | 跑 `bash scripts/ssdctl.sh scan --json` 拿到仓内可调度集合与依赖许可（轴 B）|
| `locating` | 依据 scan 给的 `upstream` / `missing` 定位目标文档与其上下游引用链 |
| `advancing` | 用 `bash scripts/ssdctl.sh advance` 代写状态块 + 复审块（**不手改状态行**）|
| `cascading` | 按级联规则处理所有下游文档（同样走 `advance`）|
| `validating` | 跑 `bash scripts/ssdctl.sh gate` + `scan --check` + `verify`, 汇报退出码 |

## When to Use

- 判据全绿, 需要把某个制品从 `Draft` 推进到 `Ready`（agent 自主推进的主路径）
- 外部代码仓 PR merged，需要把三件套推进到 `Implemented`（三件套必须同时转换）
- 某 PRD / TD 被标 `Deprecated`，需要级联降级所有引用它的下游文档
- 上游复审决定重大变更（回退 `Draft`），下游需要回退并标「需重审」
- Test Cases 冒烟/全量执行通过，需要推进到 `Implemented`（独立于三件套）
- 需要查「现在哪些制品可以推进」⇒ 直接跑 `scan`, 不必自己判断

## 调用输入

| 输入 | 必填 | 说明 |
|------|------|------|
| 目标路径 | 否 | 指定单个制品时只处理它; 省略时按 `scan` 的可调度集合逐个处理 |
| 目标状态 | 否 | `Ready` / `Implemented` / `Deprecated` / `Draft`; 省略时按判据与外部事实自动判断 |
| 人工接入 | 否 | 人在制品 `## 复审 (Review)` 段自己写 `评审人` / `评审日期` / `评审结论` / `评审方式`; 或在仓内新增素材; 机器永不覆盖已有复审块 |

示例: 外部 PR merged 后, 把 `plan/2026-07-03-login/login.md` 对应的三件套推进到 `Implemented`。

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| 状态枚举口径 | `AGENTS.md` §3.3 | 四层统一枚举 + 级联规则 |
| 判据权威 | `schema/criteria.json` | 每条判据的 id / kind / blocking 标记 |
| 唯一入口 | `scripts/ssdctl.py` | `scan` / `criteria` / `gate` / `advance` / `queue` / `verify` |
| 状态权威 | 制品的状态块 + `## 复审 (Review)` 段 | 唯一权威; 由 `advance` 代写 |
| 留痕 | 状态块 + 复审段 + git 历史 | 三者合起来就是完整留痕, 仓内没有别的载体 |

## 调度依据 (仓内谓词, 不是外部编排器)

### 可调度谓词 (5 合取)

`bash scripts/ssdctl.sh scan --json` 对每个制品算这 5 个条件, **全部为真**才算 `dispatchable`:

| # | 条件 | 含义 |
|---|------|------|
| 1 | `state ∈ {Draft, Ready, Implemented}` | 状态合法 |
| 2 | `state ∉ {Deprecated}` | 废弃品不再推进 |
| 3 | `required_labels ⊆ labels` | 标签准入; 本仓无标签体系时记 `not_configured`, 恒真 |
| 4 | `upstream_ready` | **上游制品的状态块**已达 `Ready`; 读的是制品, 不是任何外部工单 |
| 5 | `layer_resolved` | 上游路径能解析出来（`## 链接 (Links)` 段 → 目录约定 → 都无则记 `missing`）|

### 依赖许可 (轴 B, 派生, 不落制品状态行)

| permission | 条件 | agent 能做什么 |
|------------|------|--------------|
| `blocked` | 上游缺失, 或上游没有状态行 | **什么都不许做**: 不起草下游, 不推进下游 |
| `draftable` | 上游存在但未到 `Ready` | 允许**起草**下游（写 `Draft`）, 不允许把下游推进到 `Ready` |
| `committable` | 上游 ∈ {`Ready`, `Implemented`} | 允许起草, 也允许推进到 `Ready` |

> 轴 B 是**派生**的, 不写进制品状态行: 状态行只表达「这个制品自己是什么状态」, 依赖许可由 scan 现算。两者不会互相打架。

### 上下游解析顺序

| 上游层 | 解析顺序 |
|--------|---------|
| prd | 无上游 |
| td | 同 topic 的 prd |
| plan | 同 topic 的 td; 没有 td 时回退到 prd |
| test-case | 同 topic 的 prd + td |

解析顺序: 制品 `## 链接 (Links)` 段的显式路径 → 目录约定 `tech_design/{YYYY-MM-DD}-{topic}/` / `plan/{YYYY-MM-DD}-{topic}/{topic}.md` → 都找不到则 `layer_resolved=false`, `missing` 记录原因。

## Core Concept

### 转换一: 推进到 `Ready`（判据驱动, agent 自主）

| 条件 | 要求 |
|------|------|
| 判据 | 该层全部 `blocking: true` 的判据通过 |
| 非阻断失败项 | `blocking: false` 的失败项必须在**制品复审段**点名该判据 id（`> **已知问题**: <criterion-id> - <说明>`）|
| 上游 | `upstream_ready` 成立（轴 B = `committable`）|
| 授权来源 | 判据全绿; 非阻断失败项由制品复审段点名该判据 id |

```bash
# 先干跑, 看它打算写什么（不写任何文件）
bash scripts/ssdctl.sh advance prd/2026-07-03/login.md --to Ready --dry-run

# 确认后真的推进（写状态块 + 复审块 + 追加证据）
bash scripts/ssdctl.sh advance prd/2026-07-03/login.md --to Ready --actor agent:sddctl
```

**有 `blocking: false` 失败项时**: 先 `bash scripts/ssdctl.sh queue <artifact>` 列出待裁决项; 人在制品的 `## 复审 (Review)` 段补一行 `> **已知问题**: <criterion-id> - <说明>` 点名该判据 id, 再跑**同一条** `advance`。机器永不覆盖已有复审块, 也不会代填人名。

### 转换二: 推进到 `Implemented`（需外部事实）

| 场景 | 规则 |
|------|------|
| 三件套 | PRD / TD / Plan **必须同时**推进到 `Implemented`（不允许单层先转）; `状态依据` 写 `external:<ref>`（如 `external:codeup/repo/pr/42`）|
| Test Cases | **独立生命周期**: 用例实际执行通过后单独推进, 不与三件套联动 |
| 0 关联代码仓 | 停留在 `Ready`, 不做转换 |
| 依据来源 | 必须是**真实外部事实**（PR 号 / merge 记录）; agent 不得编造, 也不得从别的产物抄 |
| 人工授权 | 人在制品复审段写署名 / 点名已知问题; `advance` 原样保留该复审块 |

> `advance --to Implemented` 在缺 `external:` 依据时会以退出码 1 失败且不写任何文件。

### 转换三: `Deprecated` 级联（强制）

上游标 Deprecated 时，**所有引用它的下游文档必须级联降级**:

| 上游 | 级联范围 | 动作 |
|------|---------|------|
| PRD Deprecated | 引用该 PRD 的 TD / Plan / Test Cases | 推进到 `Deprecated`，备注「级联自上游 {path}（{日期}）」 |
| TD Deprecated | 引用该 TD 的 Plan / Test Cases | 同上 |

`advance --to Deprecated` 的 `状态依据` **只允许** `external:<ref>`, **不允许** `criteria:<id>`（废弃不是判据能判出来的事）。

操作步骤:

1. `scanning`: 跑 `scan --json` 拿到全仓制品与依赖关系
2. `locating`: 以 `{date}/{topic}.md`（PRD）或 `tech_design/{date}-{topic}`（TD）为 key, 找出下游清单
3. `cascading`: 逐份 `advance --to Deprecated --external <ref>`, 备注写清级联来源与日期
4. `validating`: 跑 `gate` + `scan --check`, 确认级联一致

### 转换四: 复审回退（上游重大变更）

| 条件 | 动作 |
|------|------|
| 上游 PRD/TD 复审决定重大变更 | 下游 TD / Plan / Test Cases 回退到 `Draft`，备注「需重审（上游 {path} 于 {日期} 回退）」 |
| 仅轻微修订 | 不触发回退; 下游在备注记录「上游已更新，待复核」 |

### 收尾校验（必做）

```bash
bash scripts/ssdctl.sh gate                    # 仓内全部门禁 + 判据 + 派生数据再生
bash scripts/ssdctl.sh scan --check            # 派生索引与磁盘一致
bash scripts/ssdctl.sh verify <artifact>       # 状态块与复审段自洽
```

退出码口径全仓统一: `0` = 通过, `1` = 不通过, `2` = 用法或内部错误。

`gate` 报「上游已 Deprecated 但本文档仍 Ready/Implemented」即漏级联。回到 cascading 阶段补齐。

## 状态推进边界 (agent 主导, 人工可选手动介入)

| 转换 | 判定方 | 写入方 | agent 能做什么 |
|------|--------|--------|----------------|
| → `Draft` | agent | agent | 写产出文件本身; 状态块三行可留空 |
| → `Ready` | **判据** | agent（机器代写）| 判据全绿就 `advance`; 人工复核是可选兜底 |
| → `Implemented` | **外部事实** | agent（机器代写）| 拿到真实外部事实后 `advance --to Implemented`; 不得编造依据 |
| → `Deprecated` | **外部事实** | agent（机器代写）| 必须带 `external:` 依据; 不得用 `criteria:` |

- **判定权归判据, 写入权归 agent, 人工走同一条流水线**; 这三件事分开: agent 判「能不能进」, 机器代写「写成什么」, 人要改结果就在仓内新增素材, 或自己在制品复审段写署名, 再跑同一条 `advance`。
- **状态块 4 行永远由 `advance` 写**（`状态` / `状态主体` / `状态时间` / `状态依据`）。skill 与 agent 都**不教人手改状态行**, 也不手改。
- **复审块 4 行**（`评审人` / `评审日期` / `评审结论` / `评审方式`）由 agent 起草自评: `评审人` 写 `agent:<id>`, `评审方式` 写 `自动判据`。
- **agent 绝不写 `human:` 前缀, 也不代填人名**（实施契约 INV-3）。人工复核时由**人自己**填名字, 并把 `评审方式` 改成 `人工介入`。
- 每次状态转换都留下可回读记录: 状态块 + 复审段 + git 历史, 三者缺一不可。

## 禁止行为 (Agent 权限边界)

| ❌ Don't | ✅ Do |
|----------|-------|
| 自行 `git commit` / `git push` / `git add` / 切换或创建分支 | 只改工作区文件; git 写操作由人执行（见 `.agents/skills/commit/SKILL.md`）|
| 手改制品里的状态行 / 状态块 4 行 | 一律走 `ssdctl advance` |
| 在复审块写 `human:` 前缀或代填人名 | 写 `agent:<id>`; `human:` 前缀**只能由人自己填**, agent 不得代填 |
| 编造 PR 号 / 外部依据 / 评审人 handle | 依据必须来自真实外部事实; 拿不准就不写 |
| 用 `criteria:` 依据推进到 `Deprecated` | 用 `external:` |
| 三件套分批推进到 `Implemented` | 三层同时推进（一致性规则）|
| 级联时删除/改写下游内容 | 只改状态与备注, 内容保留待重审 |
| 手改 `test_cases/_index.md` / README 统计块 | 跑 `gate` 再生成 |
| 修改 `schema/**` 下的模板 | 只读 `schema/` |

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 只改上游状态不管下游 | 级联是全量义务, `gate` 会暴露漏级联 |
| 三件套分批推进到 `Implemented` | 三层同时推进（一致性规则）|
| 级联时删除/改写下游内容 | 只改状态与备注，内容保留待重审 |
| Deprecated 不登记矩阵 supersede 边 | 被取代场景必须登记 |
| test_cases 跟着三件套联动 | Test Cases 独立生命周期，只响应上游 Deprecated/回退级联 |
| 手改派生索引 / 统计块里的数字 | 跑 `scan` / `gate` 再生成, 不手改 |
| 拿「检测到 PR merged」当成可以写 `Implemented` 的全部依据 | 必须把**真实外部事实**写进 `external:` 依据 |
| 把 `advance` 的退出码 1 当成「已经写了一半」 | 退出码 1 = 校验失败且**一个文件都没写**, 修完判据或在复审段点名该判据 id 再跑 |
| 因为没有外部编排器就认为没人能推进 | 调度依据在仓内 `scan`, 不依赖任何外部系统 |

## Tips

- 先跑 `scan --json` 再决定做什么, 不要凭印象判断哪些制品可以推进
- 级联前先 `grep -rl <key> tech_design/ plan/ test_cases/` 拿全清单，避免漏文件
- TD 目录内子文件**普遍自带状态行**（`> **状态**:`）。级联时全目录处理（README + 各子文件状态行一并降级，备注写在 README）
- 备注行写清「级联来源 + 日期」，便于审计与未来复活
- `advance --dry-run` 不写任何文件, 是安全预览; 确认计划再实跑
- 每次推进后跑 `verify <artifact>` 回读, 确认状态块与复审段自洽

## 安装 (Installation)

skill 定义随仓库分发, agent 直接读 `.agents/skills/sync-status/SKILL.md` 即可, **无需注册**。

需要把 skill 装进宿主 agent 的 skills 根目录时, 用仓内安装脚本：

```bash
bash <repo>/.agents/skills/install.sh                     # 默认 ~/.codex/skills/
bash <repo>/.agents/skills/install.sh --target <dir>      # 指定目标
bash <repo>/.agents/skills/install.sh --unregister        # 注销
```

## Related Skills

- `.agents/skills/to-test-cases/SKILL.md`：Test Cases 产出（本 skill 编排其生命周期转换）
- `.agents/skills/validate-spec/SKILL.md`：全量校验与门禁复核
- `.agents/skills/sync-prd/SKILL.md`：PRD 台账同步（可选层）

## Cross-References

- <repo>/AGENTS.md §3.3（状态流转与级联规则）
- <repo>/AGENTS.md §3.1（工作流 Step 1-4）
- <repo>/AGENTS.md §1.1（仓库清单）
- `schema/criteria.json`（判据唯一权威）
- <repo>/scripts/ssdctl.py（判据与门禁的唯一入口）
- <repo>/WORKFLOW.md §5（单载体契约: 状态唯一权威 = 制品状态块 + 复审段 + git 历史）
- <repo>/WORKFLOW.md（完整工作流）
