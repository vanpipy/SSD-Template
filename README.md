# SSD-Template

> Spec-Driven Development(SSD)工作流模板。一套固定 harness,把「需求」到「设计」到「计划」拆成可校验的分层规格,并把执行流程封装成 AI agent 可直接调用的 skills。

SSD-Template 是**文档/规格仓库**,不是代码仓库。它提供 3 层规格架构 + 可选质量层,每层有独立 schema 模板、命名约定、状态机与机器可跑的校验脚本。所有执行流程以 skill 为执行单元,agent 按 skill 定义的流程驱动,不手写 schema。

> **流程以 agent 为主**:agent 依仓内判据自动产出制品、跑门禁、推进状态并留痕;人类需要介入时**新增素材**、或在制品的 `## 复审 (Review)` 段**写署名**,然后跑**同一条**推进命令即可,不必逐条盯流程(见「状态推进」一节)。
> **契约唯一真源** = [WORKFLOW.md](WORKFLOW.md)(编排配置 + agent 工作契约)。
> 仓内 README / AGENTS / schema 全部以 `WORKFLOW.md` 为准;冲突时以它为准并记录冲突,不自行调和。

## 分层模型

| 层 | 位置 | 产物 | 默认 |
|----|------|------|------|
| Layer 0(可选) | `material/{YYYY-MM-DD}/` | 原始素材 + PRD 台账 | 关闭 |
| Layer 1 | `prd/{YYYY-MM-DD}/{topic}.md` | PRD | 开启 |
| Layer 2 | `tech_design/{YYYY-MM-DD}-{topic}/` | Tech Design(v4 4 子文件) | 开启 |
| Layer 3 | `plan/{YYYY-MM-DD}-{topic}/{topic}.md` | Plan | 开启 |
| Layer 4(可选) | `test_cases/{YYYY-MM-DD}/{topic}.md` | 黑盒测试用例 | 关闭 |

> Layer 0 是素材区,**不是**独立 Layer。架构层只有 Layer 1 / 2 / 3。

## 快速开始

```bash
# 1. 读仓内 skill 定义(.agents/skills/<name>/SKILL.md,随仓库分发)
#    8 个 skill:to-prd / to-tech-design / to-plan / validate-spec
#                to-test-cases / sync-status / sync-prd / to-deep-understand

# 2. 走 5 步工作流(每个 skill 的调用签名见其 SKILL.md)
/to-prd <date>                              # 原始素材 → PRD
/to-tech-design <prd-path>                  # PRD → Tech Design
/to-plan <tech-design-dir>                  # Tech Design → Plan
/validate-spec                              # 跑全部校验脚本
```

> **状态由 agent 推进**:skill 产出制品即 `Draft`;该层判据全绿后 agent 自动推进到 `Ready`。
> 人类需要介入时,**新增素材**或在制品的 `## 复审 (Review)` 段写署名,然后跑**同一条** `bash scripts/ssdctl.sh advance <artifact> --to <状态>` —— **没有实时交互通道**。

完整说明见 [WORKFLOW.md](WORKFLOW.md) §11 使用指南(状态机见 §5)。仓库操作契约见 [AGENTS.md](AGENTS.md)。编排配置与 agent 工作契约见 [WORKFLOW.md](WORKFLOW.md)。

| 需求 | 去哪里找 |
|------|----------|
| 工作流全貌与状态机 | [WORKFLOW.md](WORKFLOW.md) §11 使用指南 / §5 状态推进规则 |
| 仓库契约(多仓 / 基线 / 证据锚点) | [AGENTS.md](AGENTS.md) |
| 编排配置 + agent 工作契约(唯一真源) | [WORKFLOW.md](WORKFLOW.md) |
| 模板定义 | [schema/](schema/) |
| Skill 定义 | [.agents/skills/](.agents/skills/) |
| 校验脚本 | [scripts/](scripts/) |
| 历史代际 | `git log --all -- <path>`(仓内不再保留归档目录) |

## 状态推进

状态枚举固定 4 值:`Draft` / `Ready` / `Implemented` / `Deprecated`(不得自造状态名)。

| 当前 → 下一 | 触发条件 | 谁推进 |
|------------|---------|--------|
| — → Draft | 产物写完 + 该层门禁全绿 | **agent** |
| Draft → Ready | 该层全部 `blocking:true` 判据通过 | **agent**(人类可介入) |
| Ready → Implemented | 外部 PR merged 事实(`external:` 依据) | **agent**(依据外部事实);人类可介入 |
| * → Deprecated | 需求废弃 / 复审决定废弃(必须有 `external:` 依据) | **agent**(执行);判定来自外部事实 |

- **判据唯一权威** = `schema/criteria.json`;推进命令 = `bash scripts/ssdctl.sh advance <artifact> --to <状态>`。
- **人类接入的形态只有两种** = **新增素材**,或在制品的 `## 复审 (Review)` 段**写署名**;然后跑**同一条** `bash scripts/ssdctl.sh advance <artifact> --to <状态>` —— **没有实时交互通道**。
- **署名区分**:`状态主体` 行写 `agent:<id>` = agent 起草自评、写 `human:<handle>` = 人工写入(该前缀**只允许人工自己写**,agent 不得冒充人工、不得代填人名);`评审人` 行只接受 `agent:<id>` 或**裸人名 handle**(= 人类复核),**不接受 `human:` 前缀**。
- **每次转换留痕**:留痕 = **制品本身**(状态块 + 复审段)+ git 历史;台账状态列与 `scan` 打印的派生视图是派生数据,机器再生成。

> 状态块与复审块的完整字段、转换触发表见 [WORKFLOW.md](WORKFLOW.md) §5 状态推进规则。
> **(历史)**:2026-11-24 之前仓内另有一个 `control/` 控制平面(决定记录 / 状态快照 / 证据链),F9 裁决已整体删除;历史事实见 git 历史。

## 规格统计

<!-- prd-stats:begin -->
> 统计时间: 2026-11-22 18:44 · 由 `scripts/sync-prd.sh` 自动生成

| 层 | 制品 | 数量 | 状态分布 |
|------|------|:---:|---------|
| Layer 1 | PRD | 1 | Draft 1 |
| Layer 2 | Tech Design | 0 |  |
| Layer 3 | Plan | 0 |  |
| Layer 4 | Test | 0 |  |
| 全局 | PRD关联矩阵 | 0 条边 | 演进链 0 条 |
<!-- prd-stats:end -->

> 标记块内的内容由 `scripts/sync-prd.sh` 幂等再生成,**勿手改**。标记外的内容永不触碰。

## PRD关联矩阵

> **可选层**。仅当项目存在多 PRD 协作 / 继承 / 替代关系时启用。单 PRD 项目不需要本章节。
> 模板见 [schema/prd-matrix.md](schema/prd-matrix.md),节点标识规范见 [schema/prd-ledger.md](schema/prd-ledger.md)。

### 关系边表

| # | 节点 A | 关系 | 节点 B | 备注 |
|---|--------|------|--------|------|

### 关系类型(8 类)

| 关系 | 含义 |
|------|------|
| `supersede` | A 替代 B(B 应标记 Deprecated) |
| `inherit` | A 继承自 B(A 复用 B 的部分场景) |
| `depend` | A 依赖 B(B 不完成 A 不能完成) |
| `shared` | A 与 B 共享某子模块 |
| `conflict` | A 与 B 互斥(不能同时启用) |
| `relate` | A 与 B 相关(无强依赖,仅供参考) |
| `split-from` | A 从 B 拆分出来(B 太大被拆分) |
| `merge-into` | A 合并入 B(A 太小被合并) |

### 节点标识

台账节点用 `PRD-{YYYYMMDD}-{NN}` / `TECH-...` / `TEST-...` / `PLAN-...`(4 前缀,与 [schema/prd-ledger.md](schema/prd-ledger.md) 一致);实体文件节点用仓内相对路径 `prd/{YYYY-MM-DD}/{topic}.md`。

> 本模板仓库只提供 1 份样例 PRD(见 `prd/2026-11-22/layer-checklist.md`),不存在多 PRD 关系,故上方「关系边表」**只保留表头**。项目启用本层后,每新增一条 PRD 关系就追加一行,节点标识必须能在台账或 `prd/` 下解析到实体文件。

## 可选层

全部**默认关闭**,按需启用。目录或文件不存在时,对应校验自动跳过。

| 层 | 位置 | 用途 | 启用方式 |
|----|------|------|----------|
| 原始素材 | [material/](material/README.md) | 需求原文暂存 + 批次 PRD 台账 | 建 `material/` 目录 |
| PRD 台账 | `material/{YYYY-MM-DD}/PRDS.md` | 11 列台账,追踪素材到 PRD 的流转 | 建台账文件,跑 `scripts/sync-prd.sh` |
| 关联矩阵 | 根 [README.md](#prd关联矩阵) 章节 | 8 类 PRD 关系边 | 在本文件「关系边表」追加行 |
| 测试用例 | [test_cases/](test_cases/README.md) | Layer 4 黑盒用例 | 建 `test_cases/` 目录,用 `to-test-cases` skill |
| 理解底座 | `deep/` | 主题模型 / 消歧 / 时间线 | 建 `deep/` 目录,用 `to-deep-understand` skill |
| 实现基线 | Tech Design `## 实现基线` 段 | 设计所基于的代码现状快照 | 项目有关联代码仓时 |

> 校验脚本会按目录 / 文件是否存在决定是否启用对应检查。模板自身零实例,故全绿(零实例即零违规)。

## 校验脚本

退出码约定:`0` = 通过,`1` = 存在违规,`2` = 调用 / 环境错误。

| 命令 | 作用 | 什么时候跑 |
|------|------|------------|
| `bash scripts/ssdctl.sh gate` | 全仓门禁(既有 7 个)+ 判据引擎 | 每次都跑(CI) |
| `bash scripts/ssdctl.sh scan --check` | 跨制品一致性(上游闸门 + 三件套原子性 + 字段自洽) | 每次都跑(CI) |
| `bash scripts/ssdctl.sh advance <artifact> --to Ready --actor agent:<id>` | 状态推进(唯一写入路径;`--to` 不含 `Draft`) | 判据全绿后 |
| `bash scripts/ssdctl.sh criteria --repo` | 仓库层判据单项(行尾 CR / 冲突标记等) | 只查仓库层时单独跑(随 `gate` 执行时不必单独跑) |

> 完整脚本清单(每个脚本的职责 / 调用形态 / 退出码 / 谁调用它)见 `scripts/README.md`;每个脚本**什么时候跑**见 `WORKFLOW.md` §6 门禁执行。
> 一次性跑全部检查:用 `validate-spec` skill(交互式 agent),或按 `WORKFLOW.md` §6 的脚本表逐个跑(Symphony 编排下没有 slash 命令)。
> **脚本只强制格式与追溯;状态推进由判据引擎负责**:`Ready` 由 `bash scripts/ssdctl.sh advance` 在判据全绿后写入,`Implemented` 需要外部事实(外部 PR merged,状态依据 `external:`),`Deprecated` 同样需要 `external:` 依据(见 [WORKFLOW.md](WORKFLOW.md) §5 状态推进规则)。
> **仓内文本规则(行尾 CR / 冲突标记)由判据引擎仓库层判定,没有独立脚本** —— 规则只留一份实现(`schema/criteria.json` 的仓库层判据 `REPO-NO-CR` / `REPO-NO-PLACEHOLDER`),随 `bash scripts/ssdctl.sh gate` 执行;只查仓库层用 `bash scripts/ssdctl.sh criteria --repo`。

## 相关文件

| 文件 | 用途 |
|------|------|
| [WORKFLOW.md](WORKFLOW.md) | 契约唯一真源:编排配置 + agent 工作契约(§1–§10)+ 使用指南(§11)+ 概念参考(§12)+ 与编排层(DSH swarm)的协作分工(§13) |
| [AGENTS.md](AGENTS.md) | 仓库操作契约(仓库清单 / 跨仓引用 / 多仓 Plan / 基线 / 证据锚点) |
| 编排目录 `.swarm`(不入库) | 过程与契约补充文档(实施契约 / 需求集 / 决策记录 / 证据 / 报告)—— 2026-11-24 自 `docs/` 整体迁入;仓内不再留过程文档 |
| 历史代际(不再留档) | `git log --all -- <path>` / `git show <commit>:<path>`(历史代际仅存于 git 历史) |
| `schema/criteria.json` | **判据唯一权威**:每个判据的 id / kind / 阈值 / 是否 blocking |
| `scripts/ssdctl.py` | 判据与状态推进 CLI(`scan` / `criteria` / `criteria --repo` / `gate` / `advance` / `queue` / `verify`) |
| `scripts/README.md` | **仓内脚本清单唯一真源**:每个脚本的职责 / 调用形态 / 退出码 / 谁调用它 |
| **(历史)** `control/` 控制平面 | **(历史)** 决定记录 / 状态快照 / 证据链 —— 已于 2026-11-24 的 F9 裁决整体删除;现行载体是**制品本身**(状态块 + 复审段)+ git 历史 |
