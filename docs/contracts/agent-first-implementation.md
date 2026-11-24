# 实施契约 · SDD 流程「agent 为主」改造

> 真源:决策 = `D:\project\SSD-Template\control\decisions\2026-11-22-agent-primary.md`(D-01..D-20)。
> 本文件是**实现规范**:所有 lane 按本文件的字段名、命令名、退出码、目录布局实现;**字段名一经本文件规定不得各自发明**。
> 方向分析依据 = `D:\project\SSD-Template\docs\agent-first-direction.md`(§5 目标架构 / §6 缺口映射 / §7 分期)。

---

## §1 目标与非目标

**目标**:SSD-Template 的 SDD 流程成为「agent 自主推进、人类可手动介入」的自动化系统。仓内全部数据(台账、索引、状态、判据快照、决策记录、证据链)由 agent 生成与维护;人类不再充当流水线节拍器,只在需要时落一条介入记录。

**非目标**:不引入外部编排器/外部 tracker;不引入 `Implementing` 中间态;不做自动 merge;不改 `Draft/Ready/Implemented/Deprecated` 四值枚举。

---

## §2. 不变式(任何实现不得违反)

| # | 不变式 |
|---|---|
| INV-1 | 制品内**状态块**是状态的唯一权威;台账状态列、`control/state.json` 全部是派生 |
| INV-2 | `Ready` 的语义不变:**内容完备且可被下游依赖**。不得为了并发而弱化 |
| INV-3 | agent **不得冒充人工**:任何署名 `human:` 的人名/handle 只有人类自己写入;agent 只能用 `agent:<id>`。**机器可保证的部分**:复审块里的人工署名**必须来自 `control/decisions/` 中人写的决定记录**,不得由 `--actor` 直接填入;**机器不可保证的部分**:无法证明「确实是人写的」——人工署名只做到**有据可查**,不做到**确系本人**(见 §6.3) |
| INV-4 | 每次状态转换必须留下可回读证据(`control/evidence/**`),否则转换视为非法 |
| INV-5 | 判据只能**加严**,不得放松既有门禁判定 |
| INV-6 | 派生数据(台账状态列/索引/证据快照)必须**可再生成**,且生成过程不手写 |
| INV-7 | 退出码全仓统一:0=通过,1=不通过,2=用法/内部错误 |

---

## §3. 制品元数据契约

### 3.1 状态块(4 行,替换现单行 `> **状态**: X`)

出现在制品头部(front matter 区),顺序固定:

```
> **状态**: Draft
> **状态主体**: agent:sddctl
> **状态时间**: 2026-11-22T23:30:00+08:00
> **状态依据**: criteria:PRD-READY-01,PRD-READY-02
```

| 行 | 取值 | 解析规则 |
|---|---|---|
| `状态` | `Draft`\|`Ready`\|`Implemented`\|`Deprecated` | 4 值枚举 |
| `状态主体` | `agent:<id>` \| `human:<handle>` | `human:` 前缀**只允许人工写入**(INV-3) |
| `状态时间` | ISO-8601 带时区 | `YYYY-MM-DDTHH:MM:SS±HH:MM` |
| `状态依据` | `criteria:<id>[,<id>…]` \| `decision:<path>#<anchor>` \| `external:<ref>` | 逗号分隔,至少一项 |

**兼容**:`状态主体`/`状态时间`/`状态依据` 三行在 `Draft` 态**允许缺省**(此时为空值);一旦状态为 `Ready`/`Implemented`,三行**必填且非空**。

### 3.2 复审块(4 行,现为 3 行)

```
> **评审人**: agent:sddctl
> **评审日期**: 2026-11-22
> **评审结论**: 通过
> **评审方式**: 自动判据
```

| 行 | 取值 |
|---|---|
| `评审人` | `agent:<id>` \| `<human-handle>`(裸值即人工) |
| `评审日期` | `YYYY-MM-DD` |
| `评审结论` | `通过` \| `有条件通过` \| `需返工` |
| `评审方式` | `自动判据` \| `人工介入` \| `外部事实` |

`评审方式` 是**新增必填行**(状态 ≥ `Ready` 时)。`评审人` 为 `agent:*` 时 `评审方式` 不得为 `人工介入`。

### 3.3 稳定 ID 体系(D-16)

| ID | 载体 | 格式 | 示例位置 |
|---|---|---|---|
| `AC-n` | PRD 目标条 | `- [ ] AC-1 <验收标准文本>` | `schema/prd.md` `## 目标` |
| `S-n` | PRD 场景标题 | `### 场景: S-1 <名称>` | `schema/prd.md` `## 场景` |
| `AC↔S` | 场景内覆盖行 | `**覆盖**: AC-1, AC-2` | 场景块内,`Given` 之前 |
| `B-n` | 业务约束 | `- B-1 <约束>` | `schema/plan.md` `## 业务约束` |
| `KD-n` | 关键决策 | `- KD-1 <决策>` | `schema/tech_design/README.md` 决策段 |
| `V-n` | 验证用例 | `### V-1: <名称>` + `**场景**: S-1` | `schema/plan.md` `## 验证用例` |

**全局不变式**:每个 `AC-n` 至少被一个 `S-n` 的 `**覆盖**:` 行覆盖;每个 `S-n` 至少被一个 `V-n` 的 `**场景**:` 行覆盖;所有被引用的 ID 必须存在且在本文档所在文件内唯一。

### 3.4 跨文件引用对账表(Plan)

在既有 5 列(`引用类型|标识|来源|已对账|备注`)后**追加**一列 `覆盖` ⇒ **`覆盖` 是第 6 列(末列)**:

| 引用类型 | 标识 | 来源 | 已对账 | 备注 | 覆盖 |
|---|---|---|---|---|---|

`覆盖` 列填被引用条目所覆盖的 ID 集合(如 `AC-1,AC-2`);`已对账` 必须是 `[x]`(既有规则从「只查段存在」升级为「逐行校验」)。

---

## §4. 判据文件契约 `schema/criteria.json`

**唯一权威位置**(D-08)。`schema/*.md` 只定义模板形状;**判据逻辑只允许写在这个 JSON 里**。

```json
{
  "version": 1,
  "criteria": [
    {
      "id": "PRD-READY-01",
      "layer": "prd",
      "title": "5 个必填段齐全",
      "kind": "section_exists",
      "params": { "sections": ["为什么 (Why)", "目标 (Goal)", "场景 (Scenarios)", "不在范围内 (Out of Scope)", "复审 (Review)"] },
      "blocking": true,
      "source": "schema/prd.md:10"
    }
  ]
}
```

字段:`id`(唯一,`^[A-Z0-9-]+$`)、`layer`(`prd|td|plan|test-case|repo`)、`title`、`kind`、`params`、`blocking`(bool)、`source`(`file:line`)。

### 4.1 kind 词表(**封闭集合,只能用这 12 种**)

| kind | params | 语义 |
|---|---|---|
| `section_exists` | `sections[]` | 指定的 `## 标题` 段存在 |
| `line_present` | `regex` | 文件内存在匹配行 |
| `line_absent` | `regex` | 文件内不存在匹配行 |
| `enum_field` | `field`, `values[]` | `> **field**: v` 的 v ∈ values |
| `date_format` | `field` | `> **field**: v` 匹配 `YYYY-MM-DD` |
| `checkbox_present` | `min_count` | `- [ ]` / `- [x]` 条目数 ≥ min_count |
| `id_format` | `prefix`, `pattern` | 指定前缀的 ID 全部匹配 pattern |
| `id_unique` | `prefix` | 同前缀 ID 不重复 |
| `id_refs_resolve` | `from_prefix`, `to_prefix`, `via_field` | `via_field` 行里引用的 `to_prefix` ID 必须已定义 |
| `count_min` | `regex`, `min_count` | 匹配行数 ≥ min_count |
| `no_placeholder` | `regex`(默认 `\{[^}]+\}`) | 不得残留占位符 |
| `coverage_complete` | `from_prefix`, `to_prefix`, `via_field`, 可选 `scope`(`doc` 默认 / `repo`)、`from_layer`, `to_layer` | 每个 `from` 至少被一个 `to` 覆盖;`scope=repo` 时声明位与引用位可分处不同层 |

实现要求:引擎必须实现**全部 12 种**;新增 kind 需同时改本文件与引擎,并在 `.github/workflows/spec-check.yml` 之外补单元测试。

**跨层覆盖不变式(`coverage_complete` 的 `scope=repo`)**:§3.3 全局不变式第 2 条「每个 S-n 至少被一个 V-n 的 `**场景**:` 行覆盖」是**跨层**的 —— PRD 声明 S、Plan 声明 V。用法:

```json
{ "id": "PLAN-COVERAGE-S", "layer": "plan", "kind": "coverage_complete",
  "params": { "from_prefix": "S", "to_prefix": "V", "via_field": "场景",
              "scope": "repo", "from_layer": "prd", "to_layer": "plan" },
  "blocking": true }
```

- `scope=doc`(默认)时行为不变(单文档求值)。
- `scope=repo` 时:`from_prefix` 的**声明位**在 `from_layer` 的制品里,`to_prefix` 的**声明位**在 `to_layer` 的制品里,`via_field` 行出现在 `to` 一侧。
- 引擎**若不支持该参数必须显式失败**(报「不支持的 scope」并把该判据判为失败),**不得静默通过**。
- **12 kind 词表保持封闭** —— 这是同一 kind 的参数扩展,不是新增 kind;不采用「在 Plan 里复制一份 S-n 列表当声明位」的方案(那会制造新的自报产物,重蹈 G-9「对账表是自报产物」的覆辙)。

### 4.1.1 参数契约(必填 / 可选 / 未知即失败)

判据引擎**必须**在加载期(`load_criteria`)逐条校验 params,不能等到求值时才发现参数缺失 —— 参数拼错或漏写的判据如果被放行,会变成**永远通过的假绿**,比缺这条判据更危险(依据 §4.1「引擎若不支持该参数必须显式失败,不得静默通过」)。

| kind | 必填 params | 可选 params |
|---|---|---|
| `section_exists` | `sections`(非空 list[str]) | — |
| `line_present` | `regex`(非空 str,合法正则) | — |
| `line_absent` | `regex`(非空 str,合法正则) | — |
| `enum_field` | `field`(非空 str), `values`(非空 list[str]) | — |
| `date_format` | `field`(非空 str) | — |
| `checkbox_present` | `min_count`(int ≥ 1;**必填** —— 缺它会让「有多少个勾选项」无从判定) | — |
| `id_format` | `prefix`(非空 str), `pattern`(非空 str,合法正则) | — |
| `id_unique` | `prefix`(非空 str) | — |
| `id_refs_resolve` | `from_prefix`, `to_prefix`, `via_field`(均非空 str) | — |
| `count_min` | `regex`(非空 str,合法正则), `min_count`(int ≥ 1) | — |
| `no_placeholder` | — | `regex`(合法正则,默认 `\{[^}]+\}`) |
| `coverage_complete` | `from_prefix`, `to_prefix`, `via_field`(均非空 str) | `scope`, `from_layer`, `to_layer` |

- **全局可选 params**:`scope`(`doc` 默认 / `repo`);`from_layer` / `to_layer` 仅在 `scope=repo` 时必填。
- **缺必填 params ⇒ 加载期失败**,报「判据 X 缺少必填参数 Y」,CLI 退出码 2。
- **出现未知 params ⇒ 加载期失败**,报「判据 X 含未知参数 Y」。
- **非法正则 ⇒ 加载期失败**。引擎不得把「正则编译失败」降级成「无违规」。
- 引擎必须为每个 kind 补一条「缺必填参数 ⇒ 抛错」的单元测试(证明该判据**不能**无声通过)。

### 4.2 判据分层

- `blocking: true` 的判据不通过 ⇒ 该层不能进 `Ready`。
- `blocking: false` ⇒ 只记 warning,进 `Ready` 前必须由人类或 agent 显式记录「已知问题」(落 `control/decisions/` 或制品备注),否则阻断。

### 4.3 判据总量要求

四层合计 **≥ 30 条**(`prd` ≥ 10 / `td` ≥ 6 / `plan` ≥ 8 / `test-case` ≥ 6),其中必须包含:

- `PRD-READY-*`:覆盖 §3.3 的 AC↔S 覆盖完整性(反证用例 D-20 依赖它);
- 每个 `layer` 至少 1 条 `no_placeholder`;
- `PLAN-*-IDREF`:对账表逐行「已对账=[x]」+ `覆盖` 列非空。

---

## §5. CLI 契约 `scripts/ssdctl.py`

**唯一入口**。Python 3.11+,**仅标准库**。退出码严格遵守 INV-7。

**调用形态(Lead 集成裁定,2026-11-22)**:文档 / skill / CI **一律**用 `bash scripts/ssdctl.sh <子命令>`。
`scripts/ssdctl.sh` 是 `scripts/ssdctl.py` 的**解释器解析包装器**:不同机器上 `python` 未必可用
(Windows 的 Microsoft Store 占位符会命中 exit 9009 —— 命令存在但不是解释器),`python3` 只在 POSIX 机器上有;
包装器依次尝试 `$SSDCTL_PYTHON` / `python3` / `python` / `py -3` /
`~/.dsh/dsh-runtimes/*/dependencies/python/python.exe`,每个候选都须通过 `-c 'import sys'` 自检,
全都不行时 exit 2 并列出试过的候选,**不静默继续**。写 `python scripts/ssdctl.py` 会让 agent 在本机
第一步就失败,进而退回去手改状态行(本轮要禁止的行为)。

```
bash scripts/ssdctl.sh scan [--json] [--layer L] [--check]
bash scripts/ssdctl.sh criteria <artifact> [--json]
bash scripts/ssdctl.sh gate [--json]
bash scripts/ssdctl.sh advance <artifact> --to <Ready|Implemented|Deprecated> [--actor A] [--decision <path>#<anchor>] [--dry-run]
bash scripts/ssdctl.sh queue <artifact> [--json]
bash scripts/ssdctl.sh decide --artifact <path> --action <approve|reject|hold|override> --actor <name> --reason <text> [--criterion <id>]
bash scripts/ssdctl.sh evidence [--artifact <path>] [--json]
bash scripts/ssdctl.sh verify <artifact>
```

### 5.1 各子命令行为

| 子命令 | 输入 | 输出 | 退出码 |
|---|---|---|---|
| `scan` | 仓内制品 | 写 `control/state.json`;stdout 摘要(每制品一行) | 0 成功;1 有制品解析失败;2 用法错 |
| `scan --check` | 仓内制品 | 只比对 `control/state.json` 是否与现盘一致 | 0 一致;1 不一致;2 |
| `criteria <artifact>` | 单制品 | `{passed, failures[], warnings[], claims[]}`;`claims[]` 每项含 `id,title,passed` | 0 全过;1 有 blocking 失败;2 |
| `gate` | 全仓 | 跑**全部**仓内门禁(既有 8 个 + 本 CLI 自身判据)+ 写派生数据 | 0 全过;1 任一失败;2 |
| `advance` | 制品 + 目标状态 | 校验判据 → 写状态块/复审块 → 追加证据 | 0 成功;1 校验失败(未写任何文件);2 |
| `queue` | 制品 | 行级待裁决清单(人类可选介入的输入) | 0;1 无可裁决项;2 |
| `decide` | 人工输入 | 写 `control/decisions/<date>-<topic>.md` | 0;2 |
| `evidence` | 仓/制品 | 回读证据链 | 0;1 无证据;2 |
| `verify` | 制品 | 校验状态块/复审块/证据链三者一致 | 0;1 不一致;2 |

### 5.2 `advance` 的判定规则(关键)

目标 `Ready` 时,必须同时满足:

1. 该层全部 `blocking:true` 判据通过;
2. 若存在 `blocking:false` 失败项,必须有 `control/decisions/` 中的对应决定记录(`decision:` 引用);
3. 上游 `upstream_ready` 成立(跨层推进时);
4. `--decision` 或判据全绿二者之一提供授权来源。
5. **人工署名的来源约束(INV-3)**:复审块 `评审人` 若不是 `agent:<id>` 形态(即人工 handle),则**必须**来自 `--decision` 所指记录里的 `操作人`;**只给 `--actor <人名>` 而没有 `--decision` ⇒ exit 1**(报错「人工署名必须来自 control/decisions/ 的决定记录」)。`--actor` 只允许填 `agent:<id>` 形态。

**注意**:`blocking:true` 判据**永远不能**被决定记录豁免(规则 1 是绝对的)——人工署名只影响 `blocking:false` 的失败项、`Implemented` 的外部事实与 `Deprecated` 的依据,因此冒充人工所能撬动的面是**受限**的。

目标 `Implemented` 时,额外要求:证据链中存在 `external:` 依据(或 `--decision` 指定了外部事实的介入记录)。

目标 `Deprecated` 时:允许直接执行,但必须写 `状态依据: decision:<path>#<anchor>` 或 `external:<ref>`,**不允许** `criteria:`。

`--dry-run` 只做校验与输出计划,**不写任何文件**(负用例测试依赖它)。

### 5.3 `scan` 输出 JSON 结构

```json
{
  "generated_at": "2026-11-22T23:30:00+08:00",
  "artifacts": [
    {
      "layer": "prd",
      "topic": "layer-checklist",
      "path": "prd/2026-11-22/layer-checklist.md",
      "state": "Draft",
      "state_subject": null,
      "upstream": [],
      "upstream_states": [],
      "dependency_permission": "committable",
      "dispatchable": true,
      "reason": "no upstream required",
      "missing": []
    }
  ]
}
```

---

## §6. 控制平面契约 `control/`

```
control/
  README.md                     # 人类可读说明:如何手动介入
  decisions/
    <YYYY-MM-DD>-<topic>.md     # 人工介入记录(人类手写或 `ssdctl decide` 生成)
  state.json                    # 派生索引(scan 生成,可再生成)
  evidence/
    <YYYY-MM>/
      <YYYY-MM-DDTHHMMSS>-<topic>.jsonl   # append-only 证据记录
```

### 6.1 决定文件格式

```markdown
# 人工介入记录 · <topic>

> **决定 ID**: D1
> **时间**: 2026-11-22T23:30:00+08:00
> **操作人**: <name>                        # 授权人(人写的 handle)
> **记录写入者**: <agent-id | human-handle> # 谁把这行写进文件(`ssdctl decide` 生成时写 `agent:ssdctl`)
> **目标制品**: prd/2026-11-22/layer-checklist.md
> **动作**: approve | reject | hold | override
> **范围**: all | <criterion-id>
> **理由**: <文本>

| ID | 决定 | 理由 |
|----|------|------|
| AC-1 | approve | <理由> |
```

### 6.2 证据记录(每行一个 JSON)

```json
{"ts":"2026-11-22T23:30:00+08:00","actor":"agent:sddctl","from":"Draft","to":"Ready","artifact":"prd/2026-11-22/layer-checklist.md","artifact_hash":"sha256:...","criteria":[{"id":"PRD-READY-01","passed":true}],"decisions":[],"reason":"all blocking criteria passed"}
```

`artifact_hash` 为转换前制品内容的 `sha256`(实现可取文件字节 sha256)。证据**只追加,不修改既有行**。

### 6.3 人工署名的可验证边界(诚实声明)

- **可验证**:任何进入复审块的人工 handle,都必须能回溯到一条 `control/decisions/` 记录(`decision:<path>#<id>`);该记录同时写明**授权人**(`操作人`)与**记录写入者**(`记录写入者`),并随 git 入仓留痕。
- **不可验证**:仓库**无法证明**这条决定记录确实由某个人类写下。agent 若伪造决定文件,机器看不出来。
- **因此**:契约只能保证「**有据可查 + 全程留痕**」,不能保证「**确系本人**」。真正的兜底是流程约束(`AGENTS.md` §3.5 禁止冒充人工、`commit` skill 不得自行提交)+ 人工抽审。**不要把「机器判据全绿」当成「人已授权」。**

---

## §7. 调度谓词(5 合取)

`scan` 为每个制品计算:

```
dispatchable = state ∈ {Draft, Ready, Implemented}          # ① active
            ∧ state ∉ {Deprecated}                            # ② 非终态
            ∧ required_labels ⊆ labels                        # ③ 标签(无标签体系时记 "not_configured" 并恒真)
            ∧ upstream_ready                                   # ④ 上游制品状态行 ∈ {Ready, Implemented}
            ∧ layer_resolved                                   # ⑤ layer/topic/upstream 可解析
```

`upstream_ready` **必须读制品状态行**(INV-1),不得读任何外部工单状态。

### 7.1 依赖许可(轴 B,派生)

| 值 | 条件 | 允许 |
|---|---|---|
| `blocked` | 上游缺失或无状态行 | 什么都不许做 |
| `draftable` | 上游存在但未 `Ready` | 允许**起草**下游,不允许实现 |
| `committable` | 上游 ∈ {Ready, Implemented} | 允许实现 |

### 7.2 层间上游关系

| 层 | 上游 |
|---|---|
| `prd` | 无 |
| `td` | 同 topic 的 `prd` |
| `plan` | 同 topic 的 `td`(无 TD 时回退 `prd`) |
| `test-case` | 同 topic 的 `prd` + `td` |

上游解析顺序:制品 `## 链接 (Links)` 段的显式路径 → 目录约定 `tech_design/{YYYY-MM-DD}-{topic}/` / `plan/{YYYY-MM-DD}-{topic}/{topic}.md` → 均无 ⇒ `layer_resolved=false`,`missing` 记录原因。

---

## §8. 门禁与 CI 接线

既有 8 个门禁**保留全部**,在其后新增两步(`spec-check.yml` 顺序固定):

```yaml
- name: SDD criteria + derived data
  run: bash scripts/ssdctl.sh gate
- name: Derived state freshness
  run: bash scripts/ssdctl.sh scan --check
```

要求:`gate` 与 `scan --check` 都必须**有非空 stdout**(防空转断言沿用既有约定)。
CI 也走 `scripts/ssdctl.sh` 包装器(与文档/skill 同一形态),使包装器本身在 CI 上被持续验证。

**第三步(Lead 集成裁定,2026-11-23):判据引擎的单元测试也进 CI。**

```yaml
- name: 判据引擎单元测试(每种 kind 至少一个能失败用例)
  run: |
    PY="$(bash scripts/ssdctl.sh --python)"
    "$PY" -m unittest discover -s scripts/tests -t scripts/tests
```

理由:本轮抓到两类「假绿」—— 判据引擎的参数缺失时**永远通过**(`scripts/lib/criteria.py` 的 kind 分支),
以及 `check-md-schema.sh` 里**写了却从未被调用**的 `check_status_meta()`(死代码)+ 一条 `grep -Eq ""` 恒真路径。
没有这层回归网,有人把引擎改回「永远通过」CI 仍然是绿的。断言:退出码 0 **且**输出里必须匹配
`Ran [1-9][0-9]* tests`(0 个用例 = 空转 = 失败)。
包装器新增 `--python` 参数:只打印解析出来的解释器路径(不跑 `ssdctl.py`),让 CI 与本地用同一条解释器解析规则。

`scripts/check-doc-links.py` 继续用 `git ls-files`(G-7 已知缺陷,**本轮不修**,但新文件不得引入死链)。

---

## §9. 文件所有权(lane 划分,互不重叠)

| Lane | 拥有 | 禁止触碰 |
|---|---|---|
| **L-ENG** | `scripts/**`(新增 `ssdctl.py` + `lib/**` + `tests/**`;可改既有 8 个门禁中与新字段相关的部分)、`.github/workflows/spec-check.yml` | `schema/**`、`WORKFLOW.md`、`AGENTS.md`、`HOW_TO_USE.md`、`README.md`、`prd/**`、`.codex/**` |
| **L-SCHEMA** | `schema/**`(含 `schema/criteria.json`)、`prd/2026-11-22/layer-checklist.md`(迁移) | `scripts/**`、`.github/**`、`WORKFLOW.md`、`AGENTS.md`、`HOW_TO_USE.md`、`README.md`、`.codex/**` |
| **L-CONTRACT** | `WORKFLOW.md`、`AGENTS.md`、`HOW_TO_USE.md`、`README.md` | `scripts/**`、`schema/**`、`prd/**`、`.codex/**`、`.github/**` |
| **L-SKILLS**(Round 2) | `.codex/skills/**` | 其他全部 |
| **Lead** | `docs/**`、`control/**`、`.swarm`(编排目录,不入库)、git 提交 | — |

**依赖**:L-SKILLS 依赖 L-CONTRACT + L-SCHEMA 落地 → Round 2。L-ENG 与 L-SCHEMA 可并行(字段名由本文件 §3 固定)。

**所有 lane 禁止执行 `git add/commit/checkout/reset`**;提交由 Lead 统一执行。

---

## §10. 验收清单(Lead 执行)

| ID | 验收项 | 命令/方法 |
|---|---|---|
| A-1 | 既有 8 门禁仍全 exit 0 | `scripts/acceptance/run-all-gates.sh` |
| A-2 | 新判据引擎可用且派生数据新鲜 | `bash scripts/ssdctl.sh gate` + `bash scripts/ssdctl.sh scan --check` 均 exit 0、stdout 非空 |
| A-3 | 判据引擎单元测试通过 | `PY="$(bash scripts/ssdctl.sh --python)"; "$PY" -m unittest discover -s scripts/tests -t scripts/tests` |
| A-4 | **反证**:新判据必须抓到已知缺陷 | (i) **迁移件**(Lead 已备好,保留原缺陷):`docs/evidence/a17-run2/example-feature.migrated.md` —— 5 条 AC / 4 条场景 / **AC-5 无场景覆盖** ⇒ 跑 `criteria` 必须报出该失败;(ii) **历史原件不得篡改**:`docs/evidence/a17-run2/example-feature.md` 保持不动(它是历史证据,且为旧格式无 ID);(iii) L-ENG 须在 `scripts/tests/` 内提供一个**同等缺陷的 fixture**,证明该判据**能失败**(D-20) |
| A-5 | **负用例**:无授权不得写 `Ready` | `advance ... --to Ready` 在无判据全绿/无决定记录时 exit 1 且**文件零改动** |
| A-6 | 证据链可回读 | `ssdctl evidence --artifact prd/2026-11-22/layer-checklist.md` 打印出转换记录 |
| A-7 | 人工介入回路可用 | 写一个 `control/decisions/*.md` → `advance` 能消费 → 证据链含 `decision:` 引用 |
| A-8 | 调度谓词可判 | `scan` 输出中 PRD 的 `dispatchable=true`;人为把上游置 `Draft` 时下游 `dispatchable=false` 且 `missing` 非空 |
| A-9 | 文本卫生 | 全仓 `.md/.sh/.py/.json` CR 字节 = 0;无残留 `{占位符}` |
| A-10 | 契约一致性 | `AGENTS.md` / `WORKFLOW.md` / `HOW_TO_USE.md` / `schema/*.md` / `.codex/skills/**` 中**不再存在**「agent 天花板 = Draft」「状态只能人工回写」等旧表述(逐条 grep 证明) |
| A-11 | 入 git | `docs/**` + 本轮全部改动提交;`git status` 干净 |

---

## §11. 本轮边界

- 不做:外部编排器集成、Symphony 调度、自动 merge、`Implementing` 中间态、人类实时交互通道、`check-doc-links.py` 的 G-7 修复。
- `WORKFLOW.md` front matter 的 Symphony 配置块**保留原样**(搁置,不删),但正文必须写明「调度依据 = 仓内 `ssdctl scan`,不是外部编排器」。
