# Lane A — 人工介入点全量清单 (agent-first-direction)

- 仓库: `D:\project\SSD-Template` (只读调查, 未改动任何文件; 未执行 `scripts/` 任何脚本; 未动 git)
- 需求来源: `docs/contracts/agent-first-direction.md` R2 (人工介入清单) / R7 (证据纪律) / R8 (复用既有分析)
- 标签约定: `[既有]` = 已在 `docs/process-analysis.md` / `docs/operation-flow.md` 出现, 本次**复核**了锚点; `[新增]` = 既有分析未覆盖, 本次新发现
- 行数口径: 全仓文件为 LF 换行 (`scripts/check-line-endings.sh` 门禁项), 下文所有「行数」= 按 LF 切分且不计末尾空行的真实行数, 用 `[System.IO.File]::ReadAllText` 实测

---

## 1. Headline

`SSD-Template` 的 SDD 主干共有 **28 个**人工介入点, 其中 **15 个是流水线序列化器** (人的动作不完成, 下游一步都开不了), **13 个是决策点** (人判断一件已成品, 不挡下一层)。机器覆盖情况: **完全可机检 = 0 个**, 部分可机检 = 10 个, 不可机检 = 18 个; 人的动作被仓库留痕 = 12 个, 部分留痕 = 8 个, 完全不留痕 = 8 个。主干代价最高的是 **PRD/TD/Plan 三次评审签署 + 三件套回写** = 4 道人工闸门 (`WORKFLOW.md:167` / `HOW_TO_USE.md:321-324`), 与 `docs/process-analysis.md` §2.1 的「主干 4 道人工闸门」结论一致; 再加上 PR 合并这一道 = 5, 开 Layer 4 再 +1 = **6 道串联闸门**才能让一个特性走完。这 9 个点里有 4 个是既有分析已覆盖的, 本次**新增 19 个**点, 集中在**可选层、台账/矩阵、deep/ 底座、to-test-cases 交互确认、提交与 PR 环节**——它们不是主干的必经瓶颈, 但每一处都是「人做了、机器看不见」的黑洞。

---

## 2. 全量清单

### 2.1 主干状态闸门 (Layer 1 → 4 → Implemented)

| ID | file:line | Trigger | Information load | Decision granularity | Blocks | Machine-checkable? | Recorded? |
|---|---|---|---|---|---|---|---|
| **H1** | `HOW_TO_USE.md:321`, `HOW_TO_USE.md:462`, `WORKFLOW.md:166`, `AGENTS.md:284`, `schema/prd.md:73`, `schema/prd.md:9`, `.codex/skills/to-prd/SKILL.md:72-73` `[既有-复核]` | PRD 制品停在 `Draft` 且前 5 个门禁脚本全 exit 0 (`HOW_TO_USE.md:462`) | 整个 PRD 层: 5 个必填段 (`schema/prd.md:10` Why/Goal/Scenarios/Out of Scope/Review) — 模板 94 行, 仓内实例 `prd/2026-11-22/layer-checklist.md` 72 行; 外加 Layer 0 原始素材; 另需判断 Goal 是否可测量、Scenarios 是否覆盖需求、Out of Scope 是否正确 | 整层一次性签署 (一个 PRD 文件里所有场景一起过) | Layer 2 + Layer 4 (全部下游; `WORKFLOW.md:92`, `:94`) | **partly**: `scripts/check-md-schema.sh:308` `check_review_block()` 只校验复审段存在 + 评审日期格式 + 评审人/评审结论非占位符, 且只在该制品自身为 Ready 时校验; 内容质量 0 断言 | **yes** — 制品内 `## 复审 (Review)` 三行 |
| **H2** | `HOW_TO_USE.md:322`, `WORKFLOW.md:166`, `AGENTS.md:284`, `schema/tech_design/README.md:168`, `schema/tech_design/README.md:10`, `schema/tech_design/README.md:172-179`, `.codex/skills/to-tech-design/SKILL.md:130-131` `[既有-复核]` | TD 4 个子文件 (README/ards/apis/data-model) 停在 Draft | 整个 TD 目录: 4 文件模板合计 806 行 (README 187 + ards 262 + apis 250 + data-model 107) + 上游 PRD + 场景映射 6 列表 (`schema/tech_design/README.md:86-111`) + 实现基线 6 列表 + ards.md 的 KD 决策段; 需判断 KD 是否选对、指标是否合理、基线是否属实 | 整层一次性签署 (README.md 是唯一状态源, 4 个子文件跟随) | Layer 3 + Layer 4 (`WORKFLOW.md:93`, `:94`) | **partly**: 复审三行同 H1; 基线只查 SHA 存在/新鲜 (`scripts/check-repo-baseline.sh:299`, `:315`, `:326`), 不查基线断言是否为真 | **yes** — README.md 复审三行 |
| **H3** | `HOW_TO_USE.md:323`, `WORKFLOW.md:166`, `AGENTS.md:284`, `schema/plan.md:198`, `schema/plan.md:11`, `.codex/skills/to-plan/SKILL.md:249`, `.codex/skills/to-plan/SKILL.md:228` `[既有-复核]` | Plan 停在 Draft | 整个 Plan: 模板 211 行 / 10 个 h2 段 (`schema/plan.md`) — 变更索引 + 变更清单 + TDD 流程 + 跨文件引用对账 7 行 + 验证用例 V-1..V-3 + 完成检查 10 个勾选项; 外加上游 TD (806 行) + PRD | 整层一次性签署 (单文件) | Step 4 TDD 执行 (`schema/plan.md:86-90`, `WORKFLOW.md:302`) | **partly**: 复审三行 + `check-traceability.sh:460-486` 只做 Change↔V 编号闭环; 对账表的 `[x]` 无脚本读取 | **yes** — Plan 复审三行 |
| **H4** | `test_cases/README.md:46`, `schema/test_case.md:40`, `schema/test_case.md:48`, `schema/test_case.md:135`, `.codex/skills/to-test-cases/SKILL.md:71`, `:83`, `:112` `[既有-复核]` | Step 5 四角色评审结束 + `{topic}-key-points.md` 伴生文件就位 + 人签三行 | TC 制品 (模板 147 行, 每条用例 5 段) + key-points 文件 (业务背景 + 5-10 条核心测试点) + 四角色评审报告 (4 份 × 5 节, `.codex/skills/to-test-cases/prompts/step5-reviewing.md:11-52`, `:79-108`) + 上游 PRD/TD | 整层 + 一个伴生文件门槛 | Layer 4 执行与 Implemented | **partly**: `scripts/check-md-schema.sh:545-546` 查伴生文件存在 (仅 Ready/Implemented 阶段), `:551` 查 TC 复审段; 四角色评审循环本身无脚本 | **yes** — TC 复审三行 + 伴生文件 |
| **H5** | `HOW_TO_USE.md:324`, `HOW_TO_USE.md:341-343`, `HOW_TO_USE.md:390`, `WORKFLOW.md:167`, `AGENTS.md:285`, `AGENTS.md:289`, `schema/prd.md:9`, `schema/plan.md:11`, `schema/plan.md:199`, `.codex/skills/sync-status/SKILL.md:63`, `:67`, `:134`, `:137-138` `[既有-复核]` | 外部代码仓 TDD 全绿 **且** 外部 PR merged | 三件套当前状态 (PRD+TD+Plan = 94+806+211 = 1111 行模板) + **外部仓 PR 的完整 diff 与 CI 结果 (仓外)** + 必须给出回写依据 (如「代码仓 PR #N merged」); `HOW_TO_USE.md:324` 的「校验命令」栏原文就是「人工检查外部仓库(无脚本)」 | 一次合并动作 → 三个文件同时翻态 (三件套必须同时, `HOW_TO_USE.md:341-343`) | 整个特性的终态 | **no**: 仓内无任何脚本能判 PR 是否 merged; `sync-status/SKILL.md:63`, `:138` 明令 agent 不得代判 | **partly** — 状态行 + 依据后缀写进制品; 但「PR merged」这一外部事实本身在本仓不可验证 |
| **H6** | `test_cases/README.md:47`, `schema/test_case.md:41`, `.codex/skills/sync-status/SKILL.md:68`, `.codex/skills/to-test-cases/prompts/step6-writing.md:134`, `AGENTS.md:291` `[既有-复核]` | 用例实际执行通过 (冒烟/全量) | 执行结果 (仓外) + TC 制品状态行 | 单个 TC 制品 (独立于三件套, `AGENTS.md:291`) | Layer 4 终态 (不挡主线) | **no** | **partly** — 只写状态行, 执行结果不留痕 |
| **H7** | `HOW_TO_USE.md:326`, `HOW_TO_USE.md:358`, `WORKFLOW.md:168`, `AGENTS.md:286`, `AGENTS.md:290`, `schema/prd.md:9`, `.codex/skills/sync-status/SKILL.md:78-79`, `:85`, `:135`, `schema/prd-matrix.md:60` `[既有-复核]` | 人判定某层已作废 | 该层制品 + 其下游依赖 (PRD→TD/Plan/TC, TD→Plan/TC, `sync-status:78-79`) + 根 README 关系矩阵 (需登记 supersede 边, `sync-status:85`) | 一层 + 其下游扇出 (最多 3 个下游制品) | 被废弃链上的所有下游工作 | **partly**: `check-traceability.sh:376-397` (T8 双向 supersede) + `:542-543`, `:552-553`, `:570-571` 级联一致性 err — 只能验**级联结果**, 验不了「该不该废弃」这个决策 | **yes** — 状态行 + 备注「级联自上游 {path}({日期})」 + 根 README supersede 边 |
| **H8** | `HOW_TO_USE.md:355`, `HOW_TO_USE.md:363`, `AGENTS.md:291`, `.codex/skills/sync-status/SKILL.md:92-93` `[新增]` | 上游 PRD/TD 复审判定变更属「重大」 | 上游 diff + 全部下游制品 (最多 3 个); 还要做「重大 vs 轻微」二元判断 (`sync-status:92` vs `:93`) | 一个上游变更 × 整组下游 | 下游整层重做重审 | **no** — 无脚本读「需重审」备注, 无脚本比对上下游内容陈旧度 | **partly** — 只留「需重审（上游 {path} 于 {日期} 回退）」备注; 「重大/轻微」判断本身不可见 |

### 2.2 提交 / PR / 外部事实

| ID | file:line | Trigger | Information load | Decision granularity | Blocks | Machine-checkable? | Recorded? |
|---|---|---|---|---|---|---|---|
| **H23** | `.codex/skills/commit/SKILL.md:46`, `:15`, `:70-81`, `:114-120`, `WORKFLOW.md:240`, `WORKFLOW.md:253-256`, `.codex/skills/to-prd/SKILL.md:84`, `.codex/skills/to-plan/SKILL.md:260`, `.codex/skills/sync-status/SKILL.md:150`, `.codex/skills/to-deep-understand/SKILL.md:214`, `:220` `[新增]` | agent 完成一层想提交 | 全部变更 diff + commit message 正文; `Reviewed-by:` 的值只能取自人写的评审人 (`WORKFLOW.md:253`, `commit:72`), 未签署则整行不写 (`WORKFLOW.md:254-256`) | 一次 commit (一次分支推送) | PR 创建 (下游) | **partly**: `commit/SKILL.md:114-120` 的 verification 命令可查 message 形态; 但「人是否授权」与 trailer 来源合法性无脚本判定 | **yes** — git 历史 + commit message trailer |
| **H24** | `WORKFLOW.md:104`, `WORKFLOW.md:263`, `WORKFLOW.md:264`, `.codex/skills/commit/SKILL.md:15`, `.codex/skills/commit/SKILL.md:110`, `HOW_TO_USE.md:324` `[新增]` | Draft 制品完成 + 分支已推; PR 必须存在并被 merged 才能进 Implemented | 完整 PR diff + **门禁实际输出摘要 + 证据锚点** (`WORKFLOW.md:263` 规定 PR 描述三要素) + 人要对着规格判代码 diff | 一次 PR / 一次 merge 按钮; 另含「外部 reviewer 判代码质量」这一独立角色 (`HOW_TO_USE.md:324` 责任方栏 = 外部 reviewer + wiki 人工回写) | **H5 全部** — 没有 merge 就没有 Implemented | **no** — 无脚本触碰 PR 状态; merge 天然在仓外 | **no** (本仓内) — 本仓只事后留下「PR #N merged」字符串 (`AGENTS.md:285`); PR 本体与评审过程在外部仓 |

### 2.3 内容级人工裁决 (评审实质)

| ID | file:line | Trigger | Information load | Decision granularity | Blocks | Machine-checkable? | Recorded? |
|---|---|---|---|---|---|---|---|
| **H9** | `HOW_TO_USE.md:26-32`, `schema/prd.md:74`, `schema/prd.md:82-86`, `prd/README.md:47`, `.codex/skills/to-prd/SKILL.md:56`, `.codex/skills/to-prd/SKILL.md:78` `[既有-复核]` | 每个 PRD 的周期性复审 (防 feature rot) | 整个 PRD (72-94 行) + 仓外真实产品现状; 每份 PRD 回答 3 个具名问题: 仍然重要? / 应当保留? / 可以删除? | **一个 PRD × 3 个具名问题** — 全仓最细的人裁决单元 | 无机械阻塞; 但「可以删除」实际蕴含 H7 | **no** — 全仓无脚本读 `still_matters` / `should_keep` / `can_delete` (grep 仅 `check-md-schema.sh:381` 读 `## 目标` 的 `- [ ]`; 既有 `docs/process-analysis.md:110`, `:155` B-6) | **partly** — 答案写在制品表里 (实例 `prd/2026-11-22/layer-checklist.md:62-66` 已填 Yes/Yes/No), 但无机器读, 也无日期驱动的触发器 |
| **H10** | `AGENTS.md:180`, `AGENTS.md:209`, `.codex/skills/validate-spec/SKILL.md:20`, `:124-125`, `:139`, `:146`, `schema/tech_design/README.md:70` `[既有-复核]` | validate-spec 碰到一条「现状结论」 (当前实现状态/边界/Gap) | 每目录抽 1-3 条 (`validate-spec:139`); 每条要打开外部仓对应文件、定位到指定 SHA 的指定行, 判断该行是否真的支撑该结论 — 外部文件读取 N 次 | **一条断言 / 一个锚点** | 无 (`⚠` 不改退出码, `AGENTS.md:209`, `validate-spec:125`) | **no** — 设计上就是人工抽查; 脚本只查锚点存在与新鲜 (`check-repo-baseline.sh:299`, `:315`, `:326`) | **no** — `⚠` 只活在校验报告里, 不回写制品 |
| **H11** | `schema/plan.md:113-115`, `schema/plan.md:174-193`, `schema/tech_design/README.md:159-168`, `schema/tech_design/ards.md:242-254`, `schema/test_case.md:131-140` `[新增]` | 实施完成、准备勾完成检查 | Plan 10 项 (实现层 4 + 验证层 2 + 引用层 3 + 流程层 1「PR 已创建 — 如适用」) + TD 8 项 (`schema/tech_design/README.md:161-168`) + ards 11 项 (`schema/tech_design/ards.md:244-254`) + TC 8 项 (`schema/test_case.md:133-140`); 跨文件引用对账 7 行每行都要打开被引用文件核对 | **一个勾选项一个裁决** (合计 30+ 次二元判断) | 官方说法: 任一行对不上即「门禁清单不通过, 禁止进入 TDD 阶段」 (`schema/plan.md:115`) | **no** — 只校验段存在 (`check-md-schema.sh:482-483`); 所有 `[x]` 勾选状态无脚本读取 | **yes** — 勾选状态在文件里, 但机器盲 |

### 2.4 to-test-cases 交互确认 (唯一真正「同步等人」的通道)

| ID | file:line | Trigger | Information load | Decision granularity | Blocks | Machine-checkable? | Recorded? |
|---|---|---|---|---|---|---|---|
| **H12** | `.codex/skills/to-test-cases/prompts/step1-confirming.md:5`, `:11`, `:13-16`, `:17-22`, `:24-28`, `:30-33`, `:35-38`, `:40-48`, `.codex/skills/to-test-cases/SKILL.md:91-92` `[新增]` | `/to-test-cases` 被调用 | 5 组必答确认: PRD/TD 是否已经过研发审核 / 业务产品与目录名 / 目标平台 (每次只选一个) / 范围 / 优先级策略 + 执行范围 | 一个问题一个参数 (最细粒度) | 整个 Layer 4 运行 (`:11` 答「未审核」即**中止**) | **no** — 而「PRD/TD 是否已过研发审核」正是 Ready 闸门被散文重问一遍, 脚本无从校验 | **no** — 只存在于对话记录 |
| **H13** | `.codex/skills/to-test-cases/prompts/step3-analyzing.md:34-53`, `:70-75` `[新增]` | agent 从 PRD+TD 抽完功能点 | 功能点全表 (行 = 功能点 / 来源 / 关键程度 / 使用频率 / 建议用例数) — 行数 = 功能点数, 需与 PRD Scenarios + TD 场景映射 + 质量保证 + data-model 交叉核对; 展示后**必须等用户确认**才继续, 另问 4 问 (补充 / 调整关键程度与使用频率 / 删除 / 确认进入生成) | **一个功能点行一个裁决** (或 4 个全局问题之一) | Step 4 生成 | **no** | **no** — 表仅存于对话; `step3-analyzing.md:70-75` 允许把缺口标「待确认」而不阻塞 |
| **H14** | `.codex/skills/to-test-cases/prompts/step5-reviewing.md:3`, `:54-77`, `:110-126`, `.codex/skills/to-test-cases/SKILL.md:92`, `.codex/skills/to-test-cases/prompts/step6-writing.md:133` `[新增]` | 四角色评审循环终止 (≤3 轮) | 4 份评审报告 (业务分析师 / 测试架构师 / 系统工程师 / UX), 每份 5 节 → 约 20 节 + 被自动改写后的整份 TC 草案 | **一次「确认 / 需要修改」总决** (覆盖全部用例) | Step 6 落盘 → 直接挡 TC 转 Ready | **partly** — 3 轮上限是 prompt 约束非脚本; 仅状态后缀「Ready（2 轮 4 角色评审）」可能留痕 (`step6-writing:133`) | **partly** — 仅可能以状态后缀形式留下轮次 |

### 2.5 可选层 / deep 底座 / 台账矩阵

| ID | file:line | Trigger | Information load | Decision granularity | Blocks | Machine-checkable? | Recorded? |
|---|---|---|---|---|---|---|---|
| **H15** | `.codex/skills/to-prd/SKILL.md:88`, `.codex/skills/to-tech-design/SKILL.md:145`, `.codex/skills/to-plan/SKILL.md:264`, `.codex/skills/to-test-cases/SKILL.md:142`, `.codex/skills/to-deep-understand/SKILL.md:105`, `:111-113`, `:121-122` `[新增]` | 两份素材对同一功能描述不一致, 或规格与代码漂移 | 两份冲突源全文 (deep/ 场景还要加上代码文件在指定 SHA 的内容) | **一个冲突 (C-{n}) / 一个漂移 (D-{n})** | 被迫等待裁决的那一段制品 | **no** | **partly** — deep/ 有正式登记 (C-{n} 写进 `deep/INDEX.md` 待裁决冲突段, `to-deep-understand:111`, 双方都保留 `:112`); 但主干四个 skill 只说「登记冲突并报告人工裁决」, **登记到哪里未定义** |
| **H16** | `.codex/skills/to-deep-understand/SKILL.md:120`, `:119`, `:170`, `:209`, `:221`, `:10-12` `[新增]` | modeling 阶段撞到规格没有答案的问题 | 具体缺失的事实 + 周边规格段落 | **一个 Q-{n} / 一个 G-{n}** | 该条模型条目的闭合 (deep/ 可选且默认关闭, 故不挡主线) | **no** — validate-spec 根本不校验 `deep/` (`to-deep-understand:10-12`) | **yes** — `deep/INDEX.md` 的 Q/G/D/C 行 + `timeline.md` 事件 (但机器看不见) |
| **H17** | `.codex/skills/to-deep-understand/SKILL.md:140` `[新增]` | modeling 周期开始 | 候选清单 (未闭合的 C-{n} / D-{n} / G-{n}) | 一个周期一个主题 | 本周期建模哪个主题 | **no** | **no** — 选靶结果未记录 |
| **H18** | `.codex/skills/sync-prd/SKILL.md:131-137`, `:100`, `.codex/skills/sync-status/SKILL.md:121`, `schema/prd-ledger.md:33`, `:40`, `:57-62`, `material/README.md:41`, `scripts/sync-prd.sh:291`, `:304-305`, `:390` `[新增]` | `sync-prd.sh` exit 1, 出现「待分析」哨兵行 (优先级=待定 或 提出人=[待补]) | 被指向的原始素材全文 (为补 优先级/验收要点); **提出人身份无法从文件推断**, 必须来自人 (`material/README.md:41` 禁止编造) | 一行台账 (11 列) | 台账闭合; `sync-prd.sh` 持续 exit 1 (`scripts/sync-prd.sh:16`, `:19` 说明 CI 不按此判红) | **partly** — 哨兵本身机检得到 (`sync-prd.sh:304-305`, `:291`); 填入的值不被验证 | **yes** — 台账行本身 |
| **H19** | `.codex/skills/sync-prd/SKILL.md:145`, `:150`, `:122`, `.codex/skills/sync-status/SKILL.md:122`, `scripts/sync-prd.sh:299` `[新增]` | 台账行 来源=external 有 URL 但 创建时间为空 | 外部 URL + 抓回来的内容 (体量不可控) | 一行 / 一次抓取 | 该行永远停在「待抓取」; `sync-prd.sh` exit 1 长存 | **partly** — 哨兵机检得到 (`sync-prd.sh:299`); 但**模板不内置任何抓取器**, 人必须自己写一个外部来源 skill (`sync-prd:145`, `:150`) | **partly** — 只在报告里点名 (`:148`, `:150`) |
| **H20** | `.codex/skills/sync-prd/SKILL.md:100`, `:138-139`, `:172-173`, `schema/prd-matrix.md:15-26`, `:44-51`, `:55-62`, `README.md:64-91` `[新增]` | sync-prd 提议一条关系边 (新 PRD 收敛到 Ready / 变 Deprecated / 大改 / 季度巡检, `prd-matrix:59-62`) | 两端 PRD 全文 + 8 类关系枚举 (`prd-matrix:15-26`) + 现有边表 | **一条边 (两个 PRD)** | 未确认前不写入 (`sync-prd:139`) | **partly** — 写入后 `check-traceability` 可校验边合法性 (`prd-matrix:44-51`); 提议→确认这一步无机检 | **yes** — 根 README 关系边表一行 |
| **H21** | `schema/prd-matrix.md:62`, `HOW_TO_USE.md:358`, `HOW_TO_USE.md:366`, `HOW_TO_USE.md:26-32` `[新增]` | 季度 (跨周期复审) 或 复审超期 | 全部 PRD (N 份) + 全部边 + 全部复审日期 | 一个 PRD / 一条边逐个过, 覆盖全集 | 无机械阻塞 (但它是 H9/H1 的上游触发器) | **no** — E5→A5 只存在于 mermaid 图 (`HOW_TO_USE.md:351-374`), 无脚本; `复审日期` 无任何脚本读取 | **no** — 提醒是发出去的, 不是记下来的 |
| **H22** | `HOW_TO_USE.md:427-435` (L433), `AGENTS.md:447-456` (L449) `[新增]` | 决策影响 ≥3 个 PRD, 或涉及长期架构, 或上线前需独立审计 | ≥3 份 PRD + 该决策 + 系统级知识 — 整个受影响集合 | 一个决策 (跨 PRD) → 全局 | 无正式阻塞; `AGENTS.md:449` 现状 Evaluator 不启用, 启用本身是人决策 | **no** | **no** — 无制品记录「已升级」 |

### 2.6 输入侧与元信息 (人提供的东西)

| ID | file:line | Trigger | Information load | Decision granularity | Blocks | Machine-checkable? | Recorded? |
|---|---|---|---|---|---|---|---|
| **H26** | `HOW_TO_USE.md:195-200`, `.codex/skills/to-prd/SKILL.md:25`, `:44`, `:153-162`, `prd/README.md:16-17` `[新增]` | 项目启动 / 新需求到来 | 原始需求本体 (客户诉求、访谈记录…体量不可控) + 拆分成几个 PRD 的判断 (1:1 / 1:N / N:1 / N:N, `to-prd:59-65`) + topic slug 与日期桶选择 | 一个需求 → 一个 (或多个) topic | **一切** — 没有素材就没有 Layer 1 | **no** (仅间接: 素材目录缺失时 agent 须先创建, `to-prd:153-162`) | **partly** — 原始文件落在 `prd/{date}/` (只读 Layer 0); 但「人如何理解并拆分需求」不留痕 |
| **H25** | `AGENTS.md:215`, `AGENTS.md:222`, `AGENTS.md:225`, `AGENTS.md:411-415`, `schema/prd.md:4`, `schema/prd-ledger.md:40` `[新增]` | fork 项目 / 首个制品 | §2 项目信息 4 字段 (项目类型/描述/沟通语言/负责人) + §1.1 仓库清单 + 每个制品的负责人行 | 一个字段一个; 但仓库清单整表一次 | 基线校验找不到仓库 (仅 warn, `check-repo-baseline.sh:285`, `:287`); `material/README.md:41` 禁止编造 handle | **partly** — 占位符扫描 (`check-md-schema.sh:389-391`) 能抓 `{github-handle}`; `[待补]` 是已知哨兵 (`sync-prd.sh:260`) | **yes** — 字段就在 AGENTS.md / schema 里 |
| **H27** | `WORKFLOW.md:78-85`, `WORKFLOW.md:76`, `WORKFLOW.md:96-97`, `WORKFLOW.md:295-296`, `WORKFLOW.md:71-72` `[新增]` | Symphony 收到一个 issue | issue 标题/标签/描述 + 仓内已有产物状态 (小体量) | 一个 issue → 一层 (`WORKFLOW.md:76`) | 该 issue 的全部下游 | **no** — 4 条判据是 agent 启发式; 判不出时默认 Layer 1 PRD 并把假设写进 workpad (`WORKFLOW.md:85`) | **no** — workpad `.symphony/workpad.md` **明确不入库** (`WORKFLOW.md:71-72`), 假设随工作区消亡 |
| **H28** | `AGENTS.md:229-251`, `HOW_TO_USE.md:464-476`, `README.md:101`, `.codex/skills/sync-prd/SKILL.md:10`, `.codex/skills/to-deep-understand/SKILL.md:10-12` `[新增]` | 项目决定启用某可选层 (material/ / 关联矩阵 / deep/ / Layer 4) | 配置型决策, 无阅读负担 | 一个可选层 | 无 — 它只增加义务 | **partly** — 层目录不存在则跳过 (`check-md-schema.sh:31`) | **yes** — 目录存在与否 |

---

## 3. Silent human work (人做了、仓库看不见)

| # | 看不见的事 | 依据 | 因此无法做的机器判断 |
|---|---|---|---|
| S1 | **PR 合并本身** | `WORKFLOW.md:104`, `:264`; `commit/SKILL.md:15`, `:110` | 无法判「PR 是否真 merged」→ `HOW_TO_USE.md:324` 的校验命令栏只能写「人工检查外部仓库(无脚本)」 |
| S2 | **外部 reviewer 对代码质量的判断** | `HOW_TO_USE.md:324` 责任方栏 = 外部 reviewer + wiki 人工回写 | 无法判「代码是否满足规格」; Implemented 的唯一依据是人贴进来的一句字符串 |
| S3 | **回退到 Draft 的触发判定 (重大 vs 轻微)** | `sync-status/SKILL.md:92` vs `:93` | 无脚本读「需重审」备注, 也无比对上下游陈旧度 → 机器不知道某层是否已被上游作废 |
| S4 | **Deprecated 级联范围的决定** (哪几个下游一起废) | `sync-status/SKILL.md:78-79` | 机器只能验级联结果一致, 验不了「该不该废 / 废到哪」 |
| S5 | **选层/选题的判断** | `WORKFLOW.md:78-85` (判不出→默认 Layer 1) | 假设只写在 workpad, 而 workpad 不入库 (`WORKFLOW.md:71-72`) → 机器永远不知道这层是人要的还是 agent 猜的 |
| S6 | **原始素材的来源与人的理解** | `HOW_TO_USE.md:195-200`; `to-prd:44` | 只有原始文件在仓, 没有「人认为这个需求是什么」的记录 → 无法核对 PRD 是否忠于原意 |
| S7 | **「直接放弃这个功能」的决定** | 仓内唯一表达是 Deprecated + 级联备注 (`AGENTS.md:286`) | 一次性放弃且不产出任何制品的决策, 在仓库里零痕迹 |
| S8 | **复审超期提醒的发出** | `HOW_TO_USE.md:366` (只在 mermaid 里) | 无法判「哪份 PRD 已超期未复审」 |
| S9 | **deep/ 的回答与裁决** | `to-deep-understand:111`, `:113`, `:188` | 记录在 `deep/INDEX.md` + `timeline.md`, 但 validate-spec 不校验 deep/ (`to-deep-understand:10-12`) → 机器看得见文件, 看不见语义 |
| S10 | **to-test-cases 的三类交互确认** | `step1-confirming.md:5`; `step3-analyzing.md:34-53`; `step5-reviewing.md:110-126` | 全在对话里; 尤其「PRD 和技术设计是否已经过研发审核」(`step1:11`) 事后无法复核 |
| S11 | **外部抓取器是否存在 / 抓得对不对** | `sync-prd:145`, `:150` | 模板零抓取器, 抓不到只剩报告里一句「待抓取-环境未就绪」 |
| S12 | **量化指标是否合理 / 场景是否真覆盖** | `docs/operation-flow.md:184-186` §8 已列为人判项; 落点在 `schema/tech_design/README.md:70-71`, `:165` | 质量指标有具体数字 (机检得到) 但「数字对不对」「首笔/冷启动谁保护」无门禁 |

---

## 4. Counts

- **人工介入点总数: 28** — 状态闸门 8 (H1-H8) + 提交/PR 2 (H23-H24) + 内容裁决 3 (H9-H11) + to-test-cases 交互 3 (H12-H14) + 可选层/台账/deep 8 (H15-H22) + 输入与元信息 3 (H25-H28)
- **流水线序列化器: 15** — H1, H2, H3, H4, H5, H7, H8, H11, H12, H13, H14, H16, H23, H24, H26
  (H5/H7/H8 虽在链尾, 但它们各自挡着一整条支线; H11 官方说法即「禁止进入 TDD 阶段」)
- **决策点 (人不挡下一层): 13** — H6, H9, H10, H15, H17, H18, H19, H20, H21, H22, H25, H27, H28
- **完全机检: 0** / **部分机检: 10** (H1, H2, H3, H4, H7, H18, H19, H20, H23, H25) / **不可机检: 18**
- **留痕: 12** (H1, H2, H3, H4, H7, H11, H16, H18, H20, H23, H25, H28) / **部分留痕: 8** (H5, H6, H8, H9, H14, H15, H19, H26) / **不留痕: 8** (H10, H12, H13, H17, H21, H22, H24, H27)
- **新增 vs 既有**: `[既有-复核]` 9 (H1-H7, H9, H10) / `[新增]` 19 (H8, H11-H28) — 既有 `docs/process-analysis.md` §2.1 只覆盖主干 4 道闸门 (+TC 2 道), 本次新增的全部落在可选层、台账/矩阵、deep/、to-test-cases 交互、提交/PR、元信息六块
- **主干最小串行路径** (0 代码仓模板形态): Step 0 素材 (H26) → PRD 签署 (H1) → TD 签署 (H2) → Plan 签署 (H3) → (≥1 外部仓时) PR merge (H24) → 三件套回写 (H5) = **6 个人工动作串起一个特性**, 与 `docs/process-analysis.md` §2.1「主干 4 道人工闸门 + PR」一致; 开 Layer 4 再 +5 (H12, H13, H14 三次交互确认 + H4 签署 + H6 test-done)

---

## 5. 搜索过但零命中 / 未找到

| 搜索词 / 目标 | 结果 |
|---|---|
| `人工复审` | **全仓零命中** — 仓内词汇只有「复审」与「评审」, 没有第三个说法 |
| `手工` | **零命中** |
| `拍板` | **零命中** |
| `manual` / `human` (英文) | **零命中** — 全中文表述 |
| `人工签字` / `人工审核` | 仅 `AGENTS.md:285` 与 `HOW_TO_USE.md:324` 的等价表述, **无独立条款** |
| `pr create` / `gh pr` | **零命中** — 仓内从未给出建 PR 的具体命令; 只有 `WORKFLOW.md:263` 规定 PR 描述的内容 |
| 「谁可以当评审人」的名单 / 角色表 | **不存在** — `评审人` 只被要求填一个 github handle (`check-md-schema.sh:338`), 无任何 roster / 授权名单 / handle 白名单 |
| 脚本读 `复审日期` | **无** — grep `scripts/` 命中 26 处全在 `check-md-schema.sh`, 全部是复审三行与占位符判定, 无一处读复审日期 |
| 脚本读 `still_matters` / `should_keep` / `can_delete` | **无** — 与既有 `docs/process-analysis.md:110` 一致 |
| 脚本读 `跨文件引用对账` 里的 `[x]` | **无** — 只有 `check-md-schema.sh:482-483` 查段存在 |
| 脚本读完成检查的勾选状态 | **无** — grep `[x]\|勾选` 在 `scripts/` 只命中 `check-md-schema.sh:381` |
| 脚本比较上下游状态 (Ready 依赖) | **无** — 唯一的跨层状态比较是 Deprecated 级联 (`check-traceability.sh:543`, `:553`, `:571`) |
| 「复审超期」的实现 | **无** — 只在 `HOW_TO_USE.md:351-374` 的 mermaid 里 |
| 「复审周期」的时长定义 | **无** — `HOW_TO_USE.md:26-32` 只说「定期」; 唯一的「季度」出现在 `schema/prd-matrix.md:62` 且指矩阵巡检 |
| Evaluator / ARD 启用的记录位 | **无** — 只有启用条件, 无状态位 |

---

## 6. 未能判定的事项 (及原因)

1. **复审三问 (H9) 到底是 agent 在 Draft 阶段代答, 还是人在评审时答** — 模板两面都有话: `schema/prd.md:74` 说「两者都要填真日期」, `to-prd/SKILL.md:78` 说复审日期行不是签署行、Draft 也写真实日期; 而仓内唯一实例是三问已填 (Yes/Yes/No) 而三行签署全空 — 与「agent 填三问、人填签署」一致, 但仓内**没有明文规定三问的作者**, 不能确定。
2. **「创建 PR」归谁** — `WORKFLOW.md:263` 规定 PR 描述三要素 (像 agent 产出), `commit/SKILL.md:110` 又说「建 PR/合并 PR 评审与合并由人完成」。两者可以并存 (人开 PR、agent 备描述), 但**仓内没有任何一句明确谁点「Create PR」**。本报告按 `commit/SKILL.md:15`, `:110` 的显式表述把建 PR+合并都记在 H24 人侧, 并标注该冲突。
3. **「评审人」可以是谁** — 无名单、无角色、无权限约束; `check-md-schema.sh:338` 只要求非空且非占位符。无法判定「谁有资格签」。
4. **周期性复审的周期** — 未定义 (见上表)。
5. **`## 目标` 勾选项 (schema/prd.md:23-28) 由谁勾** — 仓内无明文; `docs/process-analysis.md:193` 的「agent 写 / 人应勾」是既有分析的推断, 不是仓内契约。
6. **规模类结论** — 仓内只有 1 份 PRD (`prd/2026-11-22/layer-checklist.md`), 所有 N 规模信息负载均为模板规模外推, 无法用实例验证。
7. **门禁脚本的实际退出码** — 本次**未执行** `scripts/` 任何脚本 (任务约束), 因此「Machine-checkable?」一列全部来自读源码 + grep, 不是实测; 唯一实测证据沿用既有 `docs/process-analysis.md:130-140` (Draft 全链 5 门禁 exit 0)。
8. **`AGENTS.md` §1.2 / §1.3 / §1.5 / §1.6 正文未逐行读** (只做了章节标题扫描 + grep) — 这四节不含人工义务词汇, 判定其不产生新增介入点; `schema/tech_design/v3/*` 5 个文件同样只经 grep (L8/L9 状态行与 v4 同文)。
