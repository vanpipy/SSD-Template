# control/ · 仓内控制平面

> 本目录是 SSD-Template 的**控制平面**:调度事实、人类介入记录、状态转换证据全部落在这里,随仓库一起版本化。
> 它替代「人工在对话里点头」这一环 —— 凡是发生过的事,仓里都查得到。

规范真源:`docs/contracts/agent-first-implementation.md`(实施契约 §5/§6/§7)与 `control/decisions/2026-11-22-agent-primary.md`(决策 D-01..D-20)。

---

## 1. 目录布局

```
control/
  README.md                       # 本文件
  state.json                      # 派生索引:每个制品的状态、上游、依赖许可、是否可派发
  decisions/                      # 人工介入记录(人类写,或由 ssdctl decide 生成)
    <YYYY-MM-DD>-<topic>.md
  evidence/                       # 状态转换证据链(append-only,只增不改)
    <YYYY-MM>/
      <YYYY-MM-DDTHHMMSS>-<topic>.jsonl
```

| 目录/文件 | 谁写 | 是不是权威 |
|---|---|---|
| 制品内状态块(`> **状态**:` 等 4 行) | agent(经 `ssdctl advance`) | **是** —— 状态的唯一权威 |
| `state.json` | agent(经 `ssdctl scan`) | 否,派生索引,可随时重建(**已 gitignore**:含 `generated_at`,提交只会引入抖动) |
| `decisions/*.md` | **人**(或 `ssdctl decide`) | 是 —— 人类介入的原始记录 |
| `evidence/*.jsonl` | agent(经 `ssdctl advance`) | 是 —— 转换历史的唯一记录 |

---

## 2. 人类怎么手动介入

**三种方式,任选其一。默认推荐第 1 种(命令),因为它会写标准格式并留痕。**

### 方式 1:用命令(推荐)

```bash
# 记一条介入决定(只写决定文件,不推进状态)
bash scripts/ssdctl.sh decide \
  --artifact prd/2026-11-22/layer-checklist.md \
  --action approve \
  --actor <你的名字> \
  --reason "第 2 条验收标准已与业务确认" \
  --criterion PRD-READY-03
```

### 方式 2:直接写决定文件

新建 `control/decisions/<YYYY-MM-DD>-<topic>.md`,格式固定:

```markdown
# 人工介入记录 · layer-checklist

> **决定 ID**: D1
> **时间**: 2026-11-22T23:30:00+08:00
> **操作人**: <你的名字>
> **目标制品**: prd/2026-11-22/layer-checklist.md
> **动作**: approve | reject | hold | override
> **范围**: all | <判据 ID>
> **理由**: <文本>

| ID | 决定 | 理由 |
|----|------|------|
| PRD-READY-03 | approve | 已与业务确认 |
```

### 方式 3:让人工介入直接驱动状态推进

```bash
# 人工决定 + 机器代写状态行(证据链会同时记下决定引用)
bash scripts/ssdctl.sh advance prd/2026-11-22/layer-checklist.md \
  --to Ready \
  --actor "<你的名字>" \
  --decision control/decisions/2026-11-22-layer-checklist.md#D1
```

> **不要手工编辑制品里的状态行。** 状态只能经 `ssdctl advance` 推进 —— 这是不变量 INV-4:每次转换都必须留下可回读证据。手改会让状态与证据链脱节。

---

## 3. agent 在没人介入时做什么

agent 不需要人类点头就能完成这些:

| 环节 | 谁触发 | 依据 |
|---|---|---|
| 起草下一层制品 | agent | 依赖许可为 `draftable` 即允许起草 |
| 跑判据、给出裁决清单 | agent | `ssdctl criteria <artifact>` |
| `Draft → Ready` | agent | 该层全部 blocking 判据通过 ⇒ 机器直接推进 |
| `Ready → Implemented` | agent | 需外部事实(PR merged)或人工介入记录 |
| 级联 `Deprecated` | agent | 上游废弃 ⇒ 下游一并废弃 |

**唯一需要人动手的**,是「机器判不了」的部分:判据全绿但内容不合业务意图时,人工落一条 `decisions/*.md`,把 `blocking:false` 的已知问题显式认领掉。

---

## 4. 查证

```bash
bash scripts/ssdctl.sh scan              # 重建并打印派生索引
bash scripts/ssdctl.sh scan --check      # 只校验 state.json 是否与现盘一致(CI 用)
bash scripts/ssdctl.sh criteria <file>   # 跑某制品的全部判据
bash scripts/ssdctl.sh queue <file>      # 行级待裁决清单(人工可选介入的输入)
bash scripts/ssdctl.sh evidence --artifact <file>   # 回读状态转换证据链
```

---

## 5. 不变量(改动本目录前先读)

| # | 不变量 |
|---|---|
| INV-1 | 制品内状态块是状态的**唯一权威**;`state.json` 是派生 |
| INV-2 | `Ready` 语义不变 = 内容完备且可被下游依赖 |
| INV-3 | **agent 不得冒充人工**:`human:` 前缀只能由人写入,agent 只能用 `agent:<id>` |
| INV-4 | 每次状态转换必须留下证据(`evidence/**`),否则转换非法 |
| INV-6 | 派生数据必须可再生成,不得手写 |
| INV-7 | 退出码统一:0 通过 / 1 不通过 / 2 用法或内部错误 |
