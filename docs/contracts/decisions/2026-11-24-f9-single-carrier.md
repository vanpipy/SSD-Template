# 决策记录 · 2026-11-24 · F9 单载体流水线(删除仓内控制平面)

> 用户指令 (m04558, verbatim):「./control 也是不需要的 人工接入 会以新增素材的方式 ，所以其实流程对人类开发者还是agent 其实都是一致的」
> 本文件是 **F9 裁决真源**;需求条目见 `.swarm/requirements/f9-single-carrier.md`(R-1..R-13),实施细节见
> `docs/contracts/agent-first-implementation.md` §5 / §6。
> 上一份决策记录:`docs/contracts/decisions/2026-11-22-agent-primary.md`(历史,部分条款被本文件取代)。

## 0. 一句话

**唯一载体 = 制品本身**;人的接入 = **新增素材 / 在制品里写内容**;推进 = **同一条 `ssdctl advance`**。

被取代的旧模型:状态推进有两个入口(机器判据 / 人工决定文件),状态与留痕存在制品之外的 `control/`
(`decisions/` / `evidence/` / `state.json`)。删除后**同一事实只剩一个权威载体 = 制品**。

## 1. 被本裁决取代的历史条款

| 历史 ID | 原内容 | 现状 |
|---|---|---|
| **D-02** | 控制平面位置 = 仓内 `control/`(独立仓方案作废) | **作废** —— 仓内不再有控制平面目录 |
| **D-10** | 人类介入载体 = `control/decisions/*.md` + `ssdctl decide` | **作废** —— 人工接入 = 新增素材 / 在制品 `## 复审 (Review)` 段署名 |
| **D-11** | 证据链 = `control/evidence/**/*.jsonl` append-only | **作废** —— 留痕 = 状态块 + 复审段 + git 历史 |

其余条款(D-01 / D-03..D-09 / D-12..D-20)**继续有效**,除非与本文件冲突。

## 2. 本轮裁决

| ID | 裁决 | 取值 | 理由 / 约束 |
|---|---|---|---|
| **F9-01** | 仓内控制平面 | **整体删除**(`decisions/` / `evidence/` / `state.json` / `README.md`) | 同一事实不允许有第二个权威源;人工通道也是「写进制品」,不需要专属载体 |
| **F9-02** | 人工接入的形态 | 只有两种:(a) 仓内**新增素材**;(b) 在**制品内写内容**(正文 / 复审块 / `已知问题` 行) | 「以新增素材的方式」是用户原话;不存在第三种专属人工通道 |
| **F9-03** | 推进命令 | **同一条** `bash scripts/ssdctl.sh advance <artifact> --to <状态>` | 人与 agent 流程一致 ⇒ 命令面不得分叉 |
| **F9-04** | 署名来源 | agent:`--actor agent:<id>`(默认 `agent:ssdctl`),机器写复审块;人:**先**在复审段自己写署名,再跑同一条 `advance` | 机器**永不代填人名**,也**永不覆盖**已有复审块(复审块非空 ⇒ 原样保留,只写状态块) |
| **F9-05** | `--actor` 取值 | **只允许 `agent:<id>`**;`--actor human:x` ⇒ exit 1,提示「人工署名请写在制品的 `## 复审 (Review)` 段内」 | 保留 INV-3 的不变量(agent 不得冒充人),把人的入口从「参数」移到「内容」 |
| **F9-06** | 状态依据前缀 | **只剩** `criteria:` 与 `external:`(`decision:` 删除) | `decision:` 的载体已不存在,留着就是悬空引用 |
| **F9-07** | 非阻断判据失败 | 必须在**复审段点名该判据 id**(`> **已知问题**: <criterion-id> — <说明>`)才放行 | 人工「有条件通过」的记录落回制品内,不再外挂决定文件 |
| **F9-08** | 终态依据 | `Implemented` / `Deprecated` 必须有 `external:` 依据(`--external <ref>` 或制品正文里的 `external:<ref>` token);`Deprecated` 不允许 `criteria:` | 终态靠**外部事实**,不靠内部决定文件 |
| **F9-09** | 留痕 | **状态块 + 复审段 + git 历史**;`scan` 只打印派生视图,不落盘 | 派生数据落盘会重新长出第二个事实源 |
| **F9-10** | `scan --check` | 改为**跨制品一致性检查**:(a) 上游闸门;(b) 三件套原子性;(c) 字段自洽 | 补上「上游必须 Ready 才准写下游」此前**零机器覆盖**的缺口(只读侧) |
| **F9-11** | CLI 表面 | `scan` / `criteria` / `gate` / `advance`(`--to` / `--actor` / `--external` / `--dry-run`)/ `queue` / `verify`;**删** `decide` / `evidence` / `advance --decision` | 退出码仍只有 0 / 1 / 2;`scan --json` 的 JSON **形状不变**(编排侧依赖) |
| **F9-12** | 历史决策保全 | `control/decisions/2026-11-22-agent-primary.md` → `docs/contracts/decisions/2026-11-22-agent-primary.md`,**正文逐字保留**,顶部加取代注 | 历史可回读,但不再是指令 |
| **F9-13** | 复审块「评审人」取值 | `agent:<id>` 或**裸 handle**(`human:` 前缀**被拒绝**) | 权威判据 `PRD-REVIEWER` 的正则只允许这两种形态;`状态主体` 行才允许 `human:<handle>`。需求集 R-3 原写法与判据冲突 ⇒ **以判据为准**,订正文字而非放宽门禁 |
| **F9-14** | `advance` 的判据求值 | **两遍**:第 1 遍按现状算 `criteria:` 依据;第 2 遍按「机器写完复审块 + 状态块之后」的**模拟制品**复算,复算结果是闸门依据 | 单遍求值时,复审段若只有标题(4 行都没有),5 条阻断判据(REVIEW-BLOCK/REVIEWER/REVIEW-DATE/REVIEW-CONCLUSION/REVIEW-METHOD)会**先**失败 ⇒ 机器永远走不到写复审块那一步(**真死锁**)。两遍求值只在内存里模拟,失败仍**零文件改动** |
| **F9-15** | 状态块与内容 id 扫描 | 状态块的 4 个字段行(状态 / 状态主体 / 状态时间 / 状态依据)**不参与**内容 id 扫描 | 状态块的「状态依据」行装的是**判据 id**(如 `PRD-AC-FORMAT`);不跳过的话机器自己写的这一行会被当成内容 id ⇒ id 形态判据被自己的状态块打挂(**写一次状态块,该制品再也过不了自己的判据**)。声明位 / 覆盖位 / 其它正文一字不动 ⇒ 门禁强度不变 |

## 3. 已知代价(明确接受,不得隐藏)

删除决定文件后,机器**不再能证明**「`human:` 署名确系本人所写」。
它只能证明三件事:署名**写在制品里**、形态**合法**、机器**没有代填**。

这是「人与 agent 同一条流水线」的既定取舍 —— 用「署名的真实性不可机器验证」换掉「同一事实两个权威载体」。
任何声称能机器证明人工署名真实性的方案,都与 F9-01 冲突。

## 4. 验收口径

| 检查 | 期望 |
|---|---|
| `git ls-files control/` | 0 行 |
| `Test-Path control/` | False |
| `ssdctl.sh --help` | 无 `decide` / `evidence` |
| `advance --help` | 有 `--external`,无 `--decision` |
| `advance --actor human:x` | exit 1,零文件改动 |
| 复审块已有裸 handle 署名时 advance | 该署名逐字保留 |
| 复审块为空时 advance | 出现 `评审人: agent:ssdctl` |
| 非阻断判据失败且复审段无该 id | exit 1,零文件改动 |
| `scan --check`(真实仓) | exit 0 |
| `scan --json` | 形状不变(`generated_at` + `artifacts[]`) |
| `bash scripts/ssdctl.sh gate` | exit 0 |
| `python -m unittest discover -s scripts/tests -t scripts/tests` | 全绿 |
| `bash .codex/skills/validate-spec/skills-integrity.sh` | PASS(0 项警告) |

## 5. 影响面(改了什么)

- **删除**:`control/`(含 `decisions/` / `evidence/` / `state.json` / `README.md`)、`scripts/lib/control.py`、
  `ssdctl decide` / `ssdctl evidence` 子命令、`advance --decision`。
- **新增**:`scripts/lib/util.py`(`now_iso` / `sha256_text` / `external_refs`)、`advance --external`、
  `scan --check` 的跨制品一致性检查、复审段的「已知问题」行(`scripts/lib/artifacts.py` +
  `scripts/check-md-schema.sh`)。
- **改写**:`scripts/lib/commands.py`、`scripts/lib/artifacts.py`、`scripts/lib/paths.py`、
  `scripts/lib/__init__.py`、`scripts/ssdctl.py`、`scripts/check-md-schema.sh`、`schema/criteria.json`
  与 `schema/*.md` 模板、`WORKFLOW.md` / `README.md` / `AGENTS.md`、
  `docs/contracts/agent-first-implementation.md`、`docs/agent-first-direction.md`、`.codex/skills/**`。

## 6. 本轮实现期裁定与验收证据(Lead)

### 6.1 三条口径订正

- **评审人形态(权威判据优先)**:需求集 R-3 原写「评审人: human:<handle>」,与 `PRD-REVIEWER`
  的正则冲突 ⇒ 订正为**裸 handle**;`状态主体` 行仍允许 `human:<handle>`(INV-3 不变)。
  判据**未改**(改判据 = 削弱门禁)。
- **死锁修复(F9-14)**:`advance` 改为两遍求值,机器写复审块这条路才走得通。
  判别性验证:同一份制品(复审段只有标题),修复前 exit 1(5 条阻断判据失败)、
  修复后 exit 0(复审块被机器写入)。
- **状态块污染内容 id 扫描(F9-15)**:状态块的 4 个字段行不再参与内容 id 扫描。

### 6.2 实测验收(本轮真实输出)

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s scripts/tests -t scripts/tests` | **Ran 89 tests, OK**(exit 0) |
| `bash scripts/ssdctl.sh gate` | exit 0(9 门禁全 0) |
| `bash scripts/ssdctl.sh scan --check` | exit 0(✓ 跨制品一致性检查通过) |
| `bash scripts/acceptance/run-all-gates.sh` | exit 0(RESULT: PASS) |
| `python scripts/acceptance/agent-first-acceptance.py` | exit 0(RESULT: PASS,13/13) |
| `bash .codex/skills/validate-spec/skills-integrity.sh` | PASS(0 项警告) |
| `advance --actor human:alice` | exit 1 + 零文件改动(复审段留给人写署名) |
| `scan --check`(上游 Draft 而下游 Ready) | exit 1,逐条报「上游未 Ready」/「三件套未同时就绪」 |

### 6.3 已知代价(补充)

F9-14 的两遍求值意味着 `advance` 会**多算一遍判据**(成本:一次求值);
换来的是「机器写复审块」这条路可用,且失败仍然**零文件改动**。
