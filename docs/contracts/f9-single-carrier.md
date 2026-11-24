# F9 · 单载体流水线(删除仓内控制平面)

> 需求集载体:本文件(**仓内权威版本**)。引用格式 `<task id>`;task 板条目见编排板同名 task。
> 来源:用户 m04558 —— 「./control 也是不需要的 人工接入 会以新增素材的方式 所以其实流程对人类开发者还是agent 其实都是一致的」。
> 裁决记录:**仓内入库版本 `docs/contracts/decisions/2026-11-24-f9-single-carrier.md`**(编排侧另留一份过程留档,内容不重复)。

## 0. 目标与一句话

**目标**:把「仓内控制平面」整体删掉,让**人**与**agent**走**同一条**流水线。

一句话:**唯一载体 = 制品本身**;人的接入 = **新增素材 / 在制品里写内容**;推进 = **同一条 `ssdctl advance`**。

被取代的旧模型:状态推进有两个入口(机器判据 / 人工决定文件),状态与留痕存在制品之外的
`control/`(decisions / evidence / state.json)。删除后**同一事实只剩一个权威载体 = 制品**。

## 1. 需求块(每条 = requirement + check + source)

### R-1 单载体
- requirement:状态块(`状态` / `状态主体` / `状态时间` / `状态依据`)与复审块(`评审人` / `评审日期` / `评审结论` / `评审方式` / 可选 `已知问题` 行)写在**制品内**,是状态与评审的唯一权威载体。`control/` 目录**整体删除**(`decisions/`、`evidence/`、`state.json`、`README.md`)。
- check:`git ls-files control/` = 0 行;`Test-Path control/` = False;仓内任何**受控文件**不得再出现 `control/` 路径(历史引用须显式标注「历史」)。
- source:用户 m04558;实施契约 INV-1。

### R-2 人工接入 = 新增素材
- requirement:人的输入只有两种形态 —— (a) 在仓内**新增素材**(`material/**` 等);(b) 直接在**制品内写内容**(正文 / 复审块 / `已知问题` 行)。**不存在**「决定文件」「`ssdctl decide`」这类专属人工通道。
- check:`ssdctl decide` / `ssdctl evidence` 子命令不存在;`advance --decision` 不存在;`control/decisions/` 不存在。
- source:用户 m04558;旧 D-10(被本轮取代)。

### R-3 同一条命令,机器不代填人名
- requirement:`bash scripts/ssdctl.sh advance <artifact> --to <状态>` 对人与 agent **完全一致**。差异只在署名来源:
  - agent:`--actor agent:<id>`(默认 `agent:ssdctl`)⇒ 机器写复审块。
  - 人:**先**在制品 `## 复审 (Review)` 段自己写好署名(`评审人: <裸 handle>`、`评审日期`、`评审结论`、`评审方式: 人工介入`、必要时 `已知问题` 行),**再**跑同一条 `advance`。
  - **`advance` 永不覆盖已有复审块**:复审块为空 ⇒ 由机器写(评审人 = `--actor`,评审日期 = 今天,评审结论 = `通过`,评审方式 = `自动判据` / `外部事实`);复审块非空 ⇒ 原样保留,机器只写状态块。
  - `--actor` **只允许 `agent:<id>` 形态**;`--actor human:x` ⇒ exit 1 并提示「人工署名请写在制品的 `## 复审 (Review)` 段内」。
- check:`advance --actor human:x` → exit 1;复审块已有裸 handle 署名时 advance 后该署名逐字保留;复审块为空时 advance 后出现 `评审人: agent:ssdctl`。
- source:用户 m04558;schema/prd.md:12(INV-3)。**口径订正(Lead 裁定)**:复审块的 `评审人` 行只接受 `agent:<id>` 或**裸 handle** —— `human:` 前缀被权威判据 `PRD-REVIEWER` 拒绝(`schema/criteria.json`);只有 `状态主体` 行允许 `human:<handle>`。**以权威判据为准**,不改判据。

### R-4 授权来源只剩两种
- requirement:状态依据的合法前缀**只剩** `criteria:` 与 `external:`(`decision:` 删除)。
  - `Ready`:全部 **blocking** 判据通过;**非阻断**判据失败时,必须在**制品的 `## 复审 (Review)` 段内出现该判据 id**(形如 `> **已知问题**: <criterion-id> — <说明>`)才放行;未出现 ⇒ 阻断并给出该指引。
  - `Implemented`:必须有一条 `external:` 依据 —— 来自 `--external <ref>`,或制品正文里出现的 `external:<ref>` token(取第一个)。
  - `Deprecated`:同样需要 `external:` 依据(取代原 `decision:`);`criteria:` 在 Deprecated 态**不合法**。
- check:`parse_basis` 不再接受 `decision:`;`check-md-schema.sh` 拒绝 `decision:` 依据;非阻断判据失败且复审段无该 id ⇒ advance exit 1 且零文件改动。
- source:实施契约 §5.2(改造);`scripts/check-md-schema.sh:155/160`。

### R-5 留痕 = 制品 + git
- requirement:转换留痕 = 状态块 + 复审块 + git 历史。删除 `control/evidence/**` 与 `control/state.json`;`scan` 只**打印**派生视图(stdout / `--json`),不再落盘。
- check:`git ls-files control/` = 0;`scan` 运行后仓内无新增状态文件;`verify` 不再读证据链。
- source:用户 m04558;旧 D-11(被本轮取代)。

### R-6 `scan --check` 改为跨制品一致性检查(新增只读机器覆盖)
- requirement:`scan --check` 不再比对快照文件,改为:
  - (a) **上游闸门**:任何状态 ∈ {`Ready`,`Implemented`} 的制品,其上游必须状态 ∈ {`Ready`,`Implemented`};
  - (b) **三件套原子性**:同 topic 的 PRD / Tech Design / Plan 中,若任一为 `Implemented`,其余**已存在**者必须也是 `Implemented`;
  - (c) 制品字段自洽(复用 `_field_problems`)。
  不满足 ⇒ exit 1 并逐条打印问题。
- check:构造「上游 Draft / 下游 Ready」的仓 ⇒ `scan --check` exit 1 且打印「上游未 Ready:…」;当前真实仓 ⇒ exit 0。
- source:本轮新增(补 G-1「Ready 闸门无机器覆盖」的**只读**侧)。

### R-7 CLI 表面
- requirement:最终 CLI = `scan`(`--json` / `--layer` / `--check`)、`criteria`、`gate`、`advance`(`--to` / `--actor` / `--external` / `--dry-run`)、`queue`、`verify`。**删** `decide`、`evidence`、`advance --decision`。退出码仍只有 0 / 1 / 2。
- check:`ssdctl.sh --help` 无 `decide` / `evidence`;`advance --help` 有 `--external` 无 `--decision`;`scan --json` 的 JSON **形状不变**(`generated_at` + `artifacts[]`,每个含 `path` / `state` / `dispatchable` / `dependency_permission` / `upstream` / `missing`)—— 编排侧(`scan --json`)依赖这个形状。
- source:实施契约 §5 命令表;`scripts/lib/dispatch.py`。

### R-8 历史决策记录迁移
- requirement:`control/decisions/2026-11-22-agent-primary.md` → `docs/contracts/decisions/2026-11-22-agent-primary.md`,**正文逐字保留**,仅在文件顶部加一行注:本文件是 2026-11-22 的历史决策记录,D-02 / D-10 / D-11 已被 2026-11-24 的 F9 裁决取代(控制平面整体删除)。
- check:`git ls-files docs/contracts/decisions/` = 1 行;文件内 D-01..D-20 全在;顶部有取代注。
- source:用户 m04558 + 历史决策保全。

### R-9 判据 / 门禁 / 模板三处同口径
- requirement:`schema/criteria.json` 的 4 条 `*-STATE-BASIS` 判据(title + regex)去掉 `decision:` 分支;`scripts/check-md-schema.sh` 的 `STATE_BASIS_ITEM_RE` → `^(criteria|external):[^[:space:],]+$`,`STATE_BASIS_DECISION_RE` → `^external:[^[:space:],]+$`,相关报错文案与模板说明同步;`scripts/lib/artifacts.py` 的 `BASIS_PREFIXES` 去掉 `"decision"`;`schema/{prd,plan,test_case}.md`、`schema/tech_design/README.md`、`schema/tech_design/v3/README.md` 的「状态依据 / 依据形式 / 状态推进」三行同步。
- check:`grep -rn 'decision:' scripts/ schema/` 仅剩 TD v3 的 `decisions.md` 文件名用法(与状态依据无关);门禁对 `decision:` 依据报错。
- source:实施契约 INV-1/§4.1。

### R-10 `已知问题` 行格式
- requirement:复审段内可写 `> **已知问题**: <criterion-id> — <说明>`(可多行)。机器判定只看「复审段内是否出现该判据 id」;`check-md-schema.sh` 对**已出现**的该行做**形状**校验(id 形如 `[A-Z0-9-]+`),不校验语义。
- check:复审段出现合法 `已知问题` 行 ⇒ 门禁不报;写成 `> **已知问题**: 随便写` ⇒ 门禁报形状错。
- source:本轮新增(R-4 的落地载体)。

### R-11 已知代价(必须写进契约,不得隐藏)
- requirement:删除决定文件后,机器**不再**能证明「`human:` 署名确系本人所写」—— 它只能证明「署名写在制品里、形态合法、机器没有代填」。这是**明确接受**的代价,写进实施契约 §5/§6 与决策记录。
- check:实施契约与决策记录里都能找到这句取舍说明。
- source:INV-3 的诚实化改写。

### R-12 文档同步口径
- requirement:`WORKFLOW.md`(§5 / §6 / §11.9 / §12 / §13 等约 20 处)、`README.md`(约 4 处)、`AGENTS.md`(约 6 处)、`docs/contracts/agent-first-implementation.md`(§5 / §6 / §7 + INV-1/3/4 + A-7 + 命令表 + 写权限表)、`docs/agent-first-direction.md`(Q-5 / Q-7 + D-10 / D-11 描述)、`docs/contracts/phase2-task-flow.md`(如引用)全部同步:不再把 `control/` 描述为「控制面」,不再把「人工介入 = 落决定记录」当口径,改为「人工接入 = 新增素材 / 在制品里署名」;历史引用须标注「历史」。
- check:`grep -rn 'control/' --include=*.md` 的剩余命中**全部**带「历史」或落在历史决策文件内;`grep -rn '落一条决定记录'` = 0。
- source:实施契约 §5/§6/§7。

### R-13 不回归
- requirement:`bash scripts/ssdctl.sh gate` = 0;`scan --check` = 0;`python -m unittest discover -s scripts/tests -t scripts/tests` 全绿;`bash scripts/acceptance/run-all-gates.sh` 全绿;`bash scripts/acceptance/clone-verify.sh` fail=0(需在提交后跑);`bash .codex/skills/validate-spec/skills-integrity.sh` = PASS。
- check:见验收命令与实际退出码。
- source:本轮验收。

## 2. Lane 划分与文件所有权(互不重叠)

| Lane | 文件所有权 | 需求 |
|---|---|---|
| **C(Lead)** | `scripts/lib/**`、`scripts/ssdctl.py`、`scripts/check-md-schema.sh`、`.gitignore`、`control/**`(删除)、`docs/contracts/decisions/**`(迁移) | R-1 R-3 R-4 R-5 R-6 R-7 R-9 R-10 |
| **D1** | `WORKFLOW.md`、`README.md`、`AGENTS.md` | R-1 R-2 R-12 |
| **D2** | `docs/contracts/**`(除 `decisions/`)、`docs/agent-first-direction.md`、`schema/**` | R-8 R-9 R-11 R-12 |
| **D3** | `scripts/tests/**`、`scripts/acceptance/**` | R-3 R-4 R-6 R-7 R-13 |
| **D4** | `.codex/skills/**` | R-2 R-4 R-5 R-7 R-12 |

依赖:C 先落(D3 才能跑测试);D1/D2/D4 与 C 并行;D3 在 C 之后启动。

> 追加说明:D4(skills lane)由 Lead 于集成期补派 —— `.codex/skills/**` 原本不在任何 lane 的所有权里,但仓内 skill 文本大量引用已删除的 `control/decisions/` / `ssdctl decide` / `advance --decision`,属 R-2 / R-12 的必改项,故立 D4 专责。

## 3. 未证实 / 风险

- 「新增素材」是否特指 `material/` 层:本轮**按广义**处理(仓内任何新增内容),`material/` 只是其中一种形态;不新增 `material/` 专属机制。
- 人工署名的真实性无法机器证明(R-11),是已知代价。
- `scan --check` 语义变更会影响任何依赖「比对 state.json」的调用方:仓内只有 `WORKFLOW.md` §6 表与 `AGENTS.md` 提到它,随 R-12 同步。
