# SSD-Template

> Spec-Driven Development(SSD)工作流模板。一套固定 harness,把「需求」到「设计」到「计划」拆成可校验的分层规格,并把执行流程封装成 AI agent 可直接调用的 skills。

SSD-Template 是**文档/规格仓库**,不是代码仓库。它提供 3 层规格架构 + 可选质量层,每层有独立 schema 模板、命名约定、状态机与机器可跑的校验脚本。所有执行流程以 skill 为执行单元,agent 按 skill 定义的流程驱动,不手写 schema。

> **契约唯一真源** = [WORKFLOW.md](WORKFLOW.md)(编排配置 + agent 工作契约)。
> 仓内 README / HOW_TO_USE / AGENTS / schema 全部以 `WORKFLOW.md` 为准;冲突时以它为准并记录冲突,不自行调和。

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
# 1. 读仓内 skill 定义(.codex/skills/<name>/SKILL.md,随仓库分发)
#    8 个 skill:to-prd / to-tech-design / to-plan / validate-spec
#                to-test-cases / sync-status / sync-prd / to-deep-understand

# 2. 走 5 步工作流(每个 skill 的调用签名见其 SKILL.md)
/to-prd <date>                              # 原始素材 → PRD
/to-tech-design <prd-path>                  # PRD → Tech Design
/to-plan <tech-design-dir>                  # Tech Design → Plan
/validate-spec                              # 跑全部校验脚本
```

完整说明见 [HOW_TO_USE.md](HOW_TO_USE.md)。仓库操作契约见 [AGENTS.md](AGENTS.md)。编排配置与 agent 工作契约见 [WORKFLOW.md](WORKFLOW.md)。

| 需求 | 去哪里找 |
|------|----------|
| 工作流全貌与状态机 | [HOW_TO_USE.md](HOW_TO_USE.md) |
| 仓库契约(多仓 / 基线 / 证据锚点) | [AGENTS.md](AGENTS.md) |
| 编排配置 + agent 工作契约(唯一真源) | [WORKFLOW.md](WORKFLOW.md) |
| 模板定义 | [schema/](schema/) |
| Skill 定义 | [.codex/skills/](.codex/skills/) |
| 校验脚本 | [scripts/](scripts/) |
| 历史目录归档位置 | [ARCHIVE.md](ARCHIVE.md) |

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

| 脚本 | 检查 | 什么时候跑 |
|------|------|------------|
| `scripts/check-naming.sh` | 目录 / 文件命名规范与层结构形状 | 每次都跑 |
| `scripts/check-md-schema.sh` | PRD / TD / Plan / Test Case 必填字段、状态枚举、阶段感知 | 每次都跑 |
| `scripts/check-traceability.sh` | KD / V 闭环、跨层级联一致性 | 每次都跑 |
| `scripts/check-doc-links.py` | 仓内 Markdown 相对链接死链 | 每次都跑 |
| `scripts/check-line-endings.sh` | 文本文件行尾统一 LF(不含 CR) | 每次都跑 |
| `scripts/check-repo-baseline.sh` | 实现基线表与实际仓状态一致性 | 有关联代码仓时 |
| `scripts/sync-prd.sh` | PRD 台账机械登记 + 根 README 统计块再生成 | 启用了台账时 |
| `scripts/sync-test-index.sh` | `test_cases/_index.md` 再生成 | 仅 Layer 4 |

> 一次性跑全部检查:用 `validate-spec` skill(交互式 agent),或按 `WORKFLOW.md` §6 的脚本表逐个跑(Symphony 编排下没有 slash 命令)。
> **脚本只强制格式与追溯,不强制状态判定**:`Ready` / `Implemented` / `Deprecated` 由人决定(见 [HOW_TO_USE.md](HOW_TO_USE.md) 状态机详解)。

## 相关文件

| 文件 | 用途 |
|------|------|
| [WORKFLOW.md](WORKFLOW.md) | 契约唯一真源:编排配置 + agent 工作契约 |
| [AGENTS.md](AGENTS.md) | 仓库操作契约(仓库清单 / 跨仓引用 / 多仓 Plan / 基线 / 证据锚点) |
| [HOW_TO_USE.md](HOW_TO_USE.md) | 工作流指南与状态机 |
| [ARCHIVE.md](ARCHIVE.md) | 已移出仓内的历史目录(`legacy/` / `legacy-simple/`)的归档位置 |
| [new-factors.md](new-factors.md) | 概念参考 |
