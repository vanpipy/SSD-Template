---
name: to-deep-understand
description: >-
  可选层 · 深度理解层 (v2.0)。scripts/deep-scan.py 机械扫描语料并计算文件指纹 (只更新 deep/INDEX.md),
  agent 读扫描输出并撰写 deep/topics/*.md 主题模型, 向 deep/disambiguation.md 追加消歧记录, 向 deep/timeline.md 追加时间线。
  Use when 需要建立或维护 deep/ 理解底座, 在写 Tech Design / Plan / 测试用例前做跨文档理解对账。
  默认不启用, 且 validate-spec 不校验 deep/ 内容; agent 不得代答 Q-{n}, 不得编造 SHA 或行号;
  本 skill 不写任何制品的状态行, 也不做 git 写操作。
---

# to-deep-understand

可选的**理解层**: 把仓内规格文档转化为**带出处、可追溯、冲突可见**的理解底座（`deep/`）。

> **本 skill 是可选层, 默认关闭**。5 步主流程（PRD → Tech Design → Plan → TDD → Layer 4）**不依赖** `deep/`。
> **`.agents/skills/validate-spec/SKILL.md` 不校验 `deep/` 的内容与结构**。需要看 `deep/` 的新鲜度, 读 `scripts/deep-scan.py` 的台账输出, 不走 validate-spec。
> 本 skill 只写 `deep/`, **不改** `prd/` / `tech_design/` / `plan/` / `test_cases/` 的内容。

## 执行阶段 (内部 phase 标识)

agent 按下列 phase 顺序推进。每个 phase 开始时在汇报里写明 `phase: <name>`。

> phase 是 agent 的**内部工作分段**, 不依赖任何 UI 模式指示器, 也不假设运行环境会显示模式。

| Phase | agent 做什么 |
|-------|--------------|
| `scanning` | 跑 `scripts/deep-scan.py`（机械部分）：扫描语料、计算指纹、更新 `deep/INDEX.md` 台账 |
| `modeling` | 读扫描输出与一手语料, 写 `deep/topics/*.md` 主题模型 |
| `reconciling` | 向 `deep/disambiguation.md` 追加消歧记录, 向 `deep/timeline.md` 追加时间线条目 |
| `reporting` | 输出本轮周期摘要（新增 G/Q/C、待更新余量、落盘清单）|

## When to Use

- 项目启用了 `deep/` 理解层, 需要建立或维护理解底座
- 写 Tech Design / Plan / 测试用例**之前**, 需要先对涉及主题做理解对账, 防止理解偏差传导到下游
- 需要把散落在多份文档里的同一概念归并到一个主题模型
- 需要记录跨文档的概念冲突, 避免后写的内容静默覆盖先写的

> **不适用**: 项目没启用 `deep/` 时, 直接跳过。

## 调用输入

| 输入 | 必填 | 说明 |
|------|------|------|
| 范围 | 否 | 主题 / PRD 路径 / 日期批次; 缺省按台账策略选目标 |

示例: 跑一个理解周期, 维护 `deep/` 理解底座。

## Prerequisites

| 依赖 | 路径 | 用途 |
|------|------|------|
| 理解底座 | `deep/`（INDEX.md + topics/ + disambiguation.md + timeline.md + reports/）| 学习成果的持久载体 |
| 台账扫描器 | `scripts/deep-scan.py` | 语料指纹扫描 + `deep/INDEX.md` 清单段更新 |
| 规格语料 | `prd/` / `tech_design/` / `plan/` / `test_cases/` / `material/` / `schema/` | 深读的一手来源 |
| 仓库清单 | `AGENTS.md` §1.1 | 仓库标识 → 本地路径, 证据锚点与代码核对依据 |
| 证据锚点约定 | `AGENTS.md` §1.7 | 代码引用格式 `{标识}@{短SHA}:{路径}#L{行号}` |

## Core Concept

### 理解层结构

```text
deep/
├── README.md            # 层说明 + 使用方式
├── INDEX.md             # 学习台账 (按主题/文件指纹登记)
├── disambiguation.md    # 消歧记录
├── timeline.md          # 时间线
├── topics/              # 主题模型 (每主题一文件)
└── reports/             # 周期报告
```

### 机械部分与 agent 部分的分工

| 部分 | 承担者 | 职责 | 不做什么 |
|------|--------|------|----------|
| **扫描** | `scripts/deep-scan.py` | 扫描已登记仓 → 计算指纹 → 更新 `deep/INDEX.md` 台账行 | **不生成 `topics/` 内容**（需 LLM 归纳）; **不改动其他任何文件** |
| **建模** | agent | 读扫描输出 + 一手语料 → 写 `deep/topics/*.md` | 不做机械计数（统计以扫描脚本 stdout 为准）|
| **对账** | agent | 追加 `deep/disambiguation.md` + `deep/timeline.md` | 不静默覆盖既有结论 |

> **指纹算法**: 优先 `git rev-parse HEAD:<path>` 的 blob sha1; 非 git 文件回退 `mtime + size`。
> **幂等**: 同一份语料重复扫描, 指纹不变, 台账状态不变。

### 台账状态语义

| 状态 | 含义 |
|------|------|
| 未学习 | 语料已登记, 尚未建模 |
| 已学习 | 已建模, 指纹与最近学习时一致 |
| 部分 | 已建模但未覆盖全部文档 |
| 待更新 | 指纹变了, 源文档已变更, 需重学 |

### 证据与出处纪律

模型里的每条断言必须带出处, 分四类:

| 出处类型 | 用于 | 格式 |
|----------|------|------|
| 规格出处 | 「规格说了什么」| `@{仓内路径}#{节标题}` |
| 代码出处 | 「系统做了什么」| `{标识}@{短SHA}:{路径}#L{行号}`（§1.7）|
| 推断 | 未被语料直接支持 | 必须登记 `Q-{n}`, 否则不入模型 |
| 先验 | 底座内的既有假设 | `@deep/{文件}` |

规则:

1. **仓库标识取自 AGENTS.md §1.1 的「标识」列**, 不写目录名, 不写具体仓库专有名词。
2. **代码锚必须真实可解析**: 短 SHA 存在, 路径在该标识对应的仓库内, 行号落在文件范围内。
3. **代码尚未落地**的行为断言标 `[code:未落地]`, 不核对, 不登记漂移。
4. **底座是二次学习资料**: `deep/*` 不得当作规格出处或代码出处, 否则底座错误会自我印证。
5. **规格说法与代码事实不一致**时, 两条**分开写**, 并登记 `D-{n}` 漂移待裁决, 不合并成一句模糊表述。

### 冲突不覆盖

新学到的内容与底座已有内容矛盾时:

1. 在 `deep/INDEX.md` 的「待裁决冲突」段登记 `C-{n}`（描述 + 涉及出处）。
2. **双方内容都保留**, 不静默覆盖。
3. 人工裁决后才把一条标为已闭合, 并在 `timeline.md` 记一条裁决事件。

### 缺口与开放问题

| 编号 | 含义 | 闭合条件 |
|------|------|----------|
| `G-{n}` | 缺口（规格没答但下游需要知道）| 人工/产品确认后闭合, 注明落点 |
| `Q-{n}` | 开放问题（需要外部答案）| 只能由人工/产品确认, **agent 不得代答** |
| `C-{n}` | 冲突（两份语料互相矛盾）| 人工裁决 |
| `D-{n}` | 规格-代码漂移 | 人工裁决, 注明去向（修 spec / 提缺陷 / 修订模型）|

## Execution Steps

### 1. Scanning Phase (机械部分)

```bash
# 在仓根目录执行
python3 scripts/deep-scan.py
```

- 脚本枚举语料, 计算每个文件的指纹, 更新 `deep/INDEX.md` 的「文档清单 × 状态」段。
- 新文档 → 标「未学习」; 指纹变化 → 标「待更新」; 已学且未变 → 保持「已学习」。
- stdout 给出台账统计（scanned / new / 转待更新 / 各状态计数）。**统计数字一律以 stdout 为准**, 手工 grep 只作核验手段。
- `deep/` 不存在时脚本自动初始化骨架。清单段由脚本托管, 冲突段与周期日志段由 agent 维护。

### 2. Modeling Phase (agent 部分)

1. **选靶**: 优先级 = 用户指定 > `C-{n}` 待裁决涉及文档 > `D-{n}` 待核对的代码 > 未闭合 `G-{n}` 中最硬的问题 > 业务语料待更新 > 未学习语料聚簇。**一周期一主题**; 巨型主题可拆多周期, 台账标「部分」。
2. **读一手语料**: 目标主题相关的 PRD / Tech Design / Plan / 测试用例 / 素材 / 文档。台账覆盖不完备, 关键结论要在**全仓广域**复核后再写入模型。
3. **写主题模型** `deep/topics/{topic}.md`:

```markdown
# 主题: {topic}
> 学习来源: {文档清单 + 指纹} · 最近周期: {date} · 状态: 已学习 / 部分

## 1 一句话本质
## 2 边界指纹
| 对象 | 标识 / 端点前缀 | 角色 | 本主题范围 |
## 3 角色 × 场景矩阵
## 4 实体与状态机
| 实体 | 当前状态 | 事件 | 次态 | 触发者 | 出处 |
## 5 规则清单
| # | 规则 | 类型 | 置信 | 出处 |
## 6 异常路径清单
| 调用 / 状态点 | 失败方式 | 规格答案 | 出处 | 缺口 |
## 7 缺口清单 G-{n}
## 8 开放问题 Q-{n}
## 9 与其他主题的连接
## 10 代码证据锚
| 断言 | 代码位置 {标识}@{短SHA}:{路径}#L{行号} | 核对日期 | 结论 |
```

4. **代码核对**（仅核对本轮新写/修订的行为类断言）:
   - 相符 → 置信标「代码」, 在模型模板第 10 段（代码证据锚）记锚;
   - 不符 → 登记 `D-{n}`（规格与代码双出处）;
   - 代码未落地 → 标 `[code:未落地]`, 不核对, 不入 `D-{n}`。
   - 代码仓按 AGENTS.md §1.1 的本地路径**只读**访问。
5. **缺口提问**: 逐项过一遍追问维度（外部依赖失败 / 离线 / 并发幂等 / 部分成功 / 权限 / 数据边界 / 生命周期 / 时效）。规格没答的记 `G-{n}`, 注明触发维度。

### 3. Reconciling Phase (agent 部分)

1. **消歧** `deep/disambiguation.md`: 追加行, 格式:

```markdown
| 概念 | 含义 A (来源) | 含义 B (来源) | 判别标志 |
```

只**追加**, 不改写既有行（除非人工裁决后标注）。

2. **时间线** `deep/timeline.md`: 追加条目, append-only, 不改写旧条目:

```markdown
| 日期 | 周期 | 事件 | 对象 | 变更内容 | 依据/出处 |
```

事件类型 ∈ 主题建立 / 模型修订 / 冲突裁决 / G 闭合 / Q 应答 / 消歧新增 / 重学 / 机制演进 / 问题回答 / 漂移登记。

3. **台账**: 更新 `deep/INDEX.md` 的指纹/状态与周期日志。

### 4. Reporting Phase

会话摘要 = 本轮主题 × 新增 G/Q/C 数量 × 待更新余量（数字引扫描脚本 stdout）× 落盘清单。

> 如项目要求持久化周期报告, 写到 `deep/reports/{YYYY-MM-DD}-{topic}.md`, 内容为本轮事实陈述（周期元信息 / 边界指纹 / 知识增量 / G-Q-C 增量 / 台账统计 / 落盘清单 / 下轮建议）。报告**不回改旧报告**。

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| 把 `deep/` 当成主流程的一环 | `deep/` 是可选层, 主流程不依赖 |
| 跑 `validate-spec` 去校验 `deep/` | `validate-spec` 不覆盖 `deep/`; 用扫描脚本的台账输出 |
| 让扫描脚本生成主题正文 | 脚本只算指纹 + 更新 INDEX, 主题模型由 agent 写 |
| 手工重算台账计数并与脚本输出争论 | 以 `scripts/deep-scan.py` stdout 为准 |
| 无出处的结论写进模型 | 每条断言带出处; 推断必须登记 `Q-{n}` |
| 引用 `deep/*` 当规格出处 | 底座只作先验假设, 结论回一手语料落定 |
| 新学内容直接覆盖旧模型 | 矛盾登记 `C-{n}`, 双方保留 |
| 为闭合 `Q-{n}` 编造答案 | `Q-{n}` 只能由人工/产品确认 |
| 规格说法与代码事实合并成一句 | 分开写, 不一致登记 `D-{n}` |
| 凭记忆写 SHA 或行号 | 锚点必须真实可解析; 拿不准就不写锚点 |
| 写具体仓库目录名或专有系统名 | 用 AGENTS.md §1.1 的通用标识 |
| 在本轮改 `prd/` / `tech_design/` / `plan/` 内容 | 本 skill 只写 `deep/` |
| 跑 git commit/push | 产物何时提交由用户决定, 本 skill 不落 commit; git 写操作由人执行 (见 `.agents/skills/commit/SKILL.md`) |

## 禁止行为 (Agent 权限边界)

| ❌ Don't | ✅ Do |
|----------|-------|
| 自行 `git commit` / `git push` / 切换或创建分支 | 只改工作区文件; git 写操作由人执行 (见 `.agents/skills/commit/SKILL.md`) |
| 代答 `Q-{n}` 开放问题 | 登记问题, 等人工/产品确认 |
| 编造 SHA / 行号 / handle / 专有系统名 | 锚点必须真实可解析; 拿不准就不写 |
| 静默覆盖旧模型结论 | 登记 `C-{n}`, 双方保留 |
| 修改 `schema/**` 下的模板 | 只读 `schema/` |
| 在 `deep/` 之外改产物文件 | 本 skill 只写 `deep/` |
| 留下 `{...}` 占位符 | 填真实值, 不适用就删整行 |

## Verification

- `deep/INDEX.md` 的状态与指纹与当前语料一致（以扫描脚本 stdout 为准）
- 新增 `G-{n}` / `Q-{n}` / `C-{n}` / `D-{n}` 全部有编号与出处
- 新增的代码锚全部真实可解析（标识在 §1.1 登记过, 路径与行号可核对）
- `deep/` 以外没有任何文件被本轮修改
- 本轮没有写任何制品的状态行（状态推进只走 `ssdctl advance`）
- 本轮知识变化在 `deep/timeline.md` 有对应条目
- `deep/topics/*.md` 的每条断言都能追到出处或 `Q-{n}`

## Examples

### 一个周期

```
User: 跑一个理解周期, 维护 deep/ 理解底座
Agent: phase: scanning
Agent: 扫描完成: scanned=42 · 台账 已学习=18 / 部分=3 / 未学习=19 / 待更新=2
Agent: 选靶: 未学习聚簇 {topic-k}, 3 份文档
Agent: phase: modeling
Agent: 写 deep/topics/topic-k.md 第 1-10 段, 规则 6 条 (全部带出处), 新增 G-1 (幂等键缺失)
Agent: 代码核对: 断言「写入前先查重」与代码相符 → 模型第 10 段记锚 B@a1b2c3d:src/service.ts#L42
Agent: phase: reconciling
Agent: disambiguation.md 追加 1 行 (同名概念在两个 PRD 里含义不同)
Agent: timeline.md 追加 1 条 (主题建立)
Agent: phase: reporting
Agent: 主题 topic-k · 新增 G=1 Q=0 C=0 · 待更新余量 2 · 落盘 3 个文件
```

### 冲突不覆盖

```
Agent: 读到 spec 说 A, 另一份 spec 说 B (结论矛盾)
Agent: 在 deep/INDEX.md 登记 C-1 (双方出处都列出)
Agent: 两份内容都保留在模型里, 不合并
Agent: timeline.md 追加 1 条 (冲突登记)
```

## 安装 (Installation)

skill 定义随仓库分发, agent 直接读 `.agents/skills/to-deep-understand/SKILL.md` 即可, **无需注册**。

需要把 skill 装进宿主 agent 的 skills 根目录时, 用仓内安装脚本：

```bash
bash <repo>/.agents/skills/install.sh                     # 默认 ~/.codex/skills/
bash <repo>/.agents/skills/install.sh --target <dir>      # 指定目标
bash <repo>/.agents/skills/install.sh --unregister        # 注销
```

## Related Skills

- `.agents/skills/to-prd/SKILL.md` / `.agents/skills/to-tech-design/SKILL.md` / `.agents/skills/to-plan/SKILL.md` / `.agents/skills/to-test-cases/SKILL.md`：主要学习素材的来源层
- `.agents/skills/validate-spec/SKILL.md`：**不校验** `deep/`; 修改 spec 层后用它复核
- `.agents/skills/sync-prd/SKILL.md`：可选层, 提供素材侧的批次台账视角

## Cross-References

- <repo>/deep/README.md（理解层说明）
- <repo>/scripts/deep-scan.py（机械扫描器: 指纹 + INDEX 台账）
- <repo>/AGENTS.md §1.1（仓库清单: 标识 → 本地路径）
- <repo>/AGENTS.md §1.7（证据锚点格式）
- <repo>/schema/tech_design/（v4 TD 模板目录）
