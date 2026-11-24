# scripts/ —— 脚本清单的唯一真源

本文件是仓内**脚本清单的唯一真源**:每个脚本的职责、调用形态、退出码、谁调用它、改了它要同步改哪里,只在这里写一份。
其它文档只保留自己角色需要的视图 + 一个指针,不再复制明细:

| 文档 | 保留什么 | 不保留什么 |
|------|---------|-----------|
| `WORKFLOW.md` §6 | **什么时候跑**(动作契约) | 职责 / 调用形态 / 退出码明细 |
| `README.md` | **入口指路**(最常用的几条命令) | 完整脚本清单 |
| `AGENTS.md` §3.8 | **症状 → 文件**导航 | 职责描述 |
| 本文件 | **全部明细** | —— |

> 机器可判定:`scripts/tests/test_scripts_index.py` 守着「索引覆盖磁盘实况」+「三份文档提到的**每一个** `scripts/...` 路径都真实存在、且都被本索引覆盖」。

## 1. 目录结构

```
scripts/
├── README.md                  ← 本文件:脚本清单唯一真源
├── ssdctl.sh                  ← 顶层入口:解释器解析包装器
├── ssdctl.py                  ← 顶层入口:状态 / 调度 / 判据 CLI(唯一真入口)
├── check-line-endings.sh      ← 门禁:行尾统一 LF
├── check-md-schema.sh         ← 门禁:必填段 + 状态枚举 + 阶段感知
├── check-naming.sh            ← 门禁:命名与层结构形状
├── check-repo-baseline.sh     ← 门禁:实现基线 6 列快照
├── check-traceability.sh      ← 门禁:跨文件引用闭环
├── check-doc-links.py         ← 门禁:Markdown 相对链接死链
├── sync-prd.sh                ← 同步:PRD 台账 + 根 README 统计块
├── sync-test-index.sh         ← 同步:test_cases/_index.md 再生
├── deep-scan.py               ← 可选层:deep/ 理解底座台账扫描
├── lib/                       ← 库(被 ssdctl.py 与单测 import,自身不单独执行)
│   ├── __init__.py  artifacts.py  commands.py  criteria.py
│   └── dispatch.py  paths.py     util.py
├── acceptance/                ← 验收(run-all-gates.sh 是 CI 的门禁入口)
│   ├── a17-e2e.sh  agent-first-acceptance.py  clone-verify.sh
│   └── recheck.sh  run-all-gates.sh
└── tests/                     ← unittest 单测 + 夹具
    ├── _support.py  test_*.py
    └── fixtures/              ← 夹具(1 组,见 §2.7)
```

树里是相对 `scripts/` 的短名;**完整仓库相对路径**(`scripts/...`)见下方分组清单。

**谁负责谁**:`scripts/ssdctl.sh` → `scripts/ssdctl.py` → `scripts/lib/*` 是**唯一一条调用链**(命令 → CLI → 库);
`scripts/check-*.sh` 与 `scripts/sync-*.sh` 是**独立门禁**,只被 `GATE_SCRIPTS` 聚合,不反向依赖库;
`scripts/acceptance/*` 与 `scripts/tests/*` 是**验证层**:其中 `scripts/acceptance/run-all-gates.sh` 是 **CI 的门禁入口**(CI 与本地跑同一条命令 ⇒ 门禁清单不可能在两边漂移),其余只验证上面三层。

## 2. 脚本清单

「必跑」列:**是** = 每次提交必跑;**条件** = 按层 / 按条件启用;**—** = 不直接参与门禁。

### 2.1 顶层入口(2)

| 路径 | 职责 | 调用形态 | 退出码 | 谁调用它 | 改了要同步改哪里 | 必跑 |
|------|------|---------|--------|---------|-----------------|------|
| `scripts/ssdctl.sh` | 跨平台入口:把 `scripts/ssdctl.py` 交给一个**真实存在**的 Python 解释器(Windows 的 `python` 可能是 Microsoft Store 占位符,会命中 exit 9009) | `bash scripts/ssdctl.sh <子命令> [参数]`<br>`bash scripts/ssdctl.sh --python`(只打印解析出的解释器路径) | 透传 `scripts/ssdctl.py` 的 0 / 1 / 2;**找不到任何可用解释器 → 2**(并列出试过的候选,不静默继续) | `.github/workflows/spec-check.yml` 的「门禁」与「判据引擎单元测试」两个步骤、`.codex/skills/to-prd/SKILL.md`、`.codex/skills/validate-spec/SKILL.md`、`scripts/acceptance/recheck.sh`、`scripts/acceptance/clone-verify.sh`、`scripts/tests/test_acceptance_rules.py` | `scripts/ssdctl.py`(被包装的命令)、`AGENTS.md` §3.6 命令形态、`WORKFLOW.md` §6 与 §11.7、`.codex/skills/*`(全部按 `bash scripts/ssdctl.sh` 写) | — |
| `scripts/ssdctl.py` | 仓内机器能力的唯一入口:状态推进 / 调度扫描 / 判据评估 / 门禁聚合 | **首选**`bash scripts/ssdctl.sh <子命令> [参数]`(解释器解析由包装器负责);本文件是实现,直接调用需自己先解析解释器(见 `scripts/ssdctl.sh --python`)。子命令清单见 `AGENTS.md` §3.6(**只在那里写一份**) | 0 = 通过 / 成功,1 = 违规 / 校验失败,2 = 用法或内部错误(判据文件缺失一律退 2,**绝不静默放行**) | `scripts/ssdctl.sh`(包装)、`scripts/lib/commands.py`(实现)、`.codex/skills/validate-spec/SKILL.md`、`AGENTS.md` §3.6、`WORKFLOW.md` §6 与 §11.7、`scripts/acceptance/agent-first-acceptance.py`、`scripts/tests/_support.py` | 实施契约 §5(CLI 表面)、`scripts/lib/commands.py`、`AGENTS.md` §3.6、`WORKFLOW.md` §6 与 §11.7、`.codex/skills/*`、`scripts/tests/test_acceptance_rules.py`(旧命令形态残留检查) | — |

### 2.2 门禁(8 —— `scripts/lib/commands.py` 的 `GATE_SCRIPTS` 全集)

这 8 个 = `scripts/lib/commands.py:64-73` 的 `GATE_SCRIPTS` 全集。运行顺序:`check-line-endings` → `check-naming` → `check-md-schema` → `check-traceability` → `check-repo-baseline` → `check-doc-links` → `sync-prd --check` → `sync-test-index --check`。

| 路径 | 职责 | 调用形态 | 退出码 | 谁调用它 | 改了要同步改哪里 | 必跑 |
|------|------|---------|--------|---------|-----------------|------|
| `scripts/check-line-endings.sh` | 受版本控制的文本文件不得含 CR(行尾统一 LF);含 NUL 的二进制自动跳过;非 git 目录退化为目录内全部文件 | `bash scripts/check-line-endings.sh [--json] [--root DIR] [TARGET]` | 0 = 通过,1 = 存在 CR 字节,2 = 调用 / 环境错误 | `scripts/lib/commands.py`(`GATE_SCRIPTS`)、`.github/workflows/spec-check.yml`「门禁」步骤、`scripts/acceptance/agent-first-acceptance.py` | `.gitattributes`(`* text=auto eol=lf`)、`scripts/lib/commands.py` 的 `GATE_SCRIPTS` | **是** |
| `scripts/check-md-schema.sh` | 必填段 / 状态枚举 / 阶段感知(M3 状态枚举 4 值、M4 阶段感知、M5 必填段);**唯一支持 `--stage` 语义**的门禁(只能收紧,不能放宽) | `bash scripts/check-md-schema.sh [--json] [--root DIR] [--stage draft\|ready\|implemented\|deprecated] [TARGET]` | 0 = 通过,1 = 存在违规,2 = 调用 / 环境错误(单文件模式有违规即退 1,不把违规条数当退出码) | `scripts/lib/commands.py`(`GATE_SCRIPTS`)、`.github/workflows/spec-check.yml`「门禁」步骤、`scripts/sync-prd.sh`、`scripts/check-naming.sh`、`scripts/check-line-endings.sh`、`scripts/lib/artifacts.py`、`scripts/tests/test_md_schema_gate.py` | `schema/*.md`(必填段 / 状态枚举)、`schema/criteria.json`(状态枚举同口径)、`scripts/lib/artifacts.py`、`scripts/lib/commands.py` | **是** |
| `scripts/check-naming.sh` | 目录 / 文件命名与层结构形状(M2):`prd/{YYYY-MM-DD}/{topic}.md` 等形状 + 日期与 topic 正则;层目录存在但无制品 → ⚠ 且退 0;全仓零制品 → 退 1 | `bash scripts/check-naming.sh [--json] [--root DIR] [TARGET]` | 0 = 通过,1 = 形状违规 / 全仓零制品,2 = 调用 / 环境错误 | `scripts/lib/commands.py`(`GATE_SCRIPTS`)、`.github/workflows/spec-check.yml`「门禁」步骤、`prd/README.md` | `schema/*` 的路径形状约定、`scripts/lib/commands.py` 的 `GATE_SCRIPTS`、`prd/README.md` | **是** |
| `scripts/check-repo-baseline.sh` | Tech Design `## 实现基线` 6 列表(仓库 / 分支 / SHA / 核对日期 / 核对项 / 状态)与实际仓状态一致;SHA 必须本地可解析;核对日期超 `--max-age-days`(默认 7)→ ⚠;状态含 `待补` / `TODO` / `✗` / `❌` → ✗;0 关联代码仓写 `> 不适用:` → ○ 跳过 | `bash scripts/check-repo-baseline.sh [--json] [--root DIR] [--max-age-days N] [TARGET]` | 0 = 通过(可含 ⚠),1 = 违规,2 = 调用错误 / 环境错误 | `scripts/lib/commands.py`、`.github/workflows/spec-check.yml`「门禁」步骤、`.codex/skills/validate-spec/SKILL.md`、`AGENTS.md` | `schema/tech_design/README.md` 的「## 实现基线」段、`AGENTS.md` §1.6 实现基线 | 条件 |
| `scripts/check-traceability.sh` | 跨文件引用闭环(T1 PRD 场景 ⊆ TD 场景映射、T2/T3 `V-` / `KD-` 定义、T4 Plan 必须引用 TD、T6 台账 ID、T7/T8 关系边与 supersede ↔ Deprecated 一致、T9 上游存在性);**只有 PRD 的仓库必须 exit 0** | `bash scripts/check-traceability.sh [--json] [--root DIR] [TARGET]` | 0 = 通过,1 = 违规,2 = 调用错误 / 环境错误 | `scripts/lib/commands.py`(`GATE_SCRIPTS`)、`.github/workflows/spec-check.yml`「门禁」步骤、`scripts/acceptance/agent-first-acceptance.py` | `schema/criteria.json`、`scripts/lib/criteria.py`、`AGENTS.md` §1.7 证据锚点与关系边约定 | **是** |
| `scripts/check-doc-links.py` | 仓内受版本控制的 Markdown 相对链接死链;含 `{}` 的占位路径不算错;`#L12` 行号锚点不算错;段内锚点只 ⚠;外链不检查(禁网络) | `"$PY" scripts/check-doc-links.py [--json] [--root DIR]` | 0 = 无死链,1 = 有死链,2 = 调用错误 / 环境错误 | `scripts/lib/commands.py`、`.github/workflows/spec-check.yml`「门禁」步骤、`scripts/acceptance/a17-e2e.sh`、`scripts/acceptance/agent-first-acceptance.py`、`scripts/acceptance/clone-verify.sh` | 各 `.md` 里的相对链接、`scripts/check-doc-links.py` 的 `skip_dirs` 与 `scripts/lib/commands.py` 的 `REPO_TEXT_SKIP_PARTS` 白名单(克隆自足断言共用) | **是** |
| `scripts/sync-prd.sh` | PRD 台账机械登记(可选层 `material/{YYYY-MM-DD}/PRDS.md`)+ 根 README 统计块再生成;**只写这两处**,统计块标记外的内容永不触碰;不做任何 git 写操作;写模式幂等 | `bash scripts/sync-prd.sh [--json] [--root DIR] [--check]`<br>写模式 = 不带 `--check` | 0 = 通过 / 已更新,1 = 违规(`--check` 下表示统计块或台账与实际制品漂移),2 = 调用 / 环境错误 | `scripts/lib/commands.py`、`.github/workflows/spec-check.yml` 的「PRD 台账登记」与「门禁」两步、`.codex/skills/sync-prd/SKILL.md` | `schema/prd-ledger.md`(台账模板)、根 README 的 `<!-- prd-stats:begin -->` … `<!-- prd-stats:end -->` 标记、`.codex/skills/sync-prd/SKILL.md` | 条件 |
| `scripts/sync-test-index.sh` | 再生成 `test_cases/_index.md`;**只写这一个文件**;数据真源 = 用例文档的元信息表;写模式幂等 | `bash scripts/sync-test-index.sh [--json] [--root DIR] [--check]`<br>写模式 = 不带 `--check` | 0 = 通过 / 已更新,1 = 违规(`--check` 发现差异),2 = 调用错误 / 环境错误;`test_cases/` 不存在 → 该层未启用 → 跳过并退 0 | `scripts/lib/commands.py`、`.github/workflows/spec-check.yml`「门禁」步骤、`.codex/skills/to-test-cases/prompts/step6-writing.md` | `schema/test_case.md`(元信息表)、`test_cases/_index.md` 的 `<!-- test-index:begin -->` … `<!-- test-index:end -->` 标记、`.codex/skills/to-test-cases/prompts/step6-writing.md` | 条件 |

### 2.3 可选层(1)

| 路径 | 职责 | 调用形态 | 退出码 | 谁调用它 | 改了要同步改哪里 | 必跑 |
|------|------|---------|--------|---------|-----------------|------|
| `scripts/deep-scan.py` | `deep/` 理解底座的学习台账扫描器:扫描语料 → 算指纹 → 更新 `deep/INDEX.md` 的清单段;**不生成 `deep/topics/` 正文**,不改 `deep/` 以外的文件;指纹默认 head 模式(HEAD 提交树 blob sha1) | `"$PY" scripts/deep-scan.py --root <repo> --index <path> --quiet` | 0 = 通过,1 = 真实错误(台账无法写入 / 清单标记缺失或错序 / 参数错误),2 = 用法错误 | `.codex/skills/to-deep-understand/SKILL.md`、`.codex/skills/validate-spec/SKILL.md`、`WORKFLOW.md` | `deep/` 可选层的目录形状、`.codex/skills/to-deep-understand/SKILL.md` | 条件(只在启用 `deep/` 时) |

### 2.4 库(7 —— 自身不单独执行,退出码由 `scripts/ssdctl.py` 统一成 0 / 1 / 2)

| 路径 | 职责 | 谁调用它 | 改了要同步改哪里 |
|------|------|---------|-----------------|
| `scripts/lib/__init__.py` | 库包说明(模块清单),不导出符号 | `scripts/ssdctl.py` 的 import | 新增 / 删除 `scripts/lib/*.py` 模块时 |
| `scripts/lib/artifacts.py` | 制品发现 + 状态块 / 复审块读写 + 稳定 ID(写入幂等替换) | `scripts/lib/commands.py`、`scripts/lib/dispatch.py`、`scripts/tests/*` | 实施契约 §3(状态块 / 复审块字段)、`schema/*.md` 的制品模板、`scripts/lib/commands.py` |
| `scripts/lib/commands.py` | 6 个子命令的实现 + 常量 `GATE_SCRIPTS` / `SOFT_FAIL_CODES` / `TRIO_LAYERS` / 状态正则(1101 行,**本轮不拆分**,见 §6) | `scripts/ssdctl.py`、`scripts/tests/*` | 实施契约 §5(CLI 表面)、`scripts/ssdctl.py` 的参数定义、`scripts/tests/test_acceptance_rules.py`(旧形态残留检查) |
| `scripts/lib/criteria.py` | 判据引擎:加载 `schema/criteria.json` 并实现 12 种 kind(kind 词表是封闭集合;加载失败抛 `CriteriaError` → 退出码 2) | `scripts/lib/commands.py`、`scripts/tests/test_kinds.py`、`scripts/tests/test_param_contract.py` | `schema/criteria.json`(数据)、`scripts/lib/commands.py` |
| `scripts/lib/dispatch.py` | 调度谓词:上游解析 + 5 合取(`state_ok` ∧ `not_deprecated` ∧ `labels_ok` ∧ `upstream_ready` ∧ `layer_resolved`)+ 依赖许可三态;`upstream_ready` **只读制品内状态行** | `scripts/lib/commands.py`、`scripts/tests/test_dispatch.py` | 实施契约 §7(调度谓词)、`WORKFLOW.md` §13.2 |
| `scripts/lib/paths.py` | 仓库根与判据文件路径解析(唯一环境变量例外:`SSDCTL_CRITERIA`) | `scripts/lib/commands.py`、`scripts/lib/criteria.py`、`scripts/lib/artifacts.py` | 仓根探测规则、`schema/criteria.json` 的位置约定 |
| `scripts/lib/util.py` | 纯函数工具(时间戳 / 内容哈希 / `external:` 提取) | `scripts/lib/artifacts.py`、`scripts/lib/commands.py` | —— |

### 2.5 验收(5 —— 其中 run-all-gates.sh 是 CI 的门禁入口)

| 路径 | 职责 | 调用形态 | 退出码 | 谁调用它 | 改了要同步改哪里 |
|------|------|---------|--------|---------|-----------------|
| `scripts/acceptance/run-all-gates.sh` | 门禁验收的**渲染层**:消费 `bash scripts/ssdctl.sh gate --json` 的载荷并渲染成表格;**自带清单已删除**,门禁清单的唯一真源是 `GATE_SCRIPTS` | `bash scripts/acceptance/run-all-gates.sh [repo_root]` | 0 = 全绿,1 = 有门禁未过,2 = 用法 / 环境错误(解释器解析失败等) | `scripts/acceptance/recheck.sh`、`.github/workflows/spec-check.yml`「门禁」步骤 | `scripts/lib/commands.py` 的 `GATE_SCRIPTS`、`.github/workflows/spec-check.yml` 的步骤顺序 |
| `scripts/acceptance/clone-verify.sh` | 对已提交 HEAD 做干净克隆验证;断言 A1 **脚本自足**(克隆内的 py / sh / yml 不得引用编排目录 `.swarm` 与已迁出的过程文档目录;白名单 2 条:`scripts/check-doc-links.py` 的 `skip_dirs`、`scripts/lib/commands.py` 的 `REPO_TEXT_SKIP_PARTS`) | `bash scripts/acceptance/clone-verify.sh` | 0 = 通过,1 = 有断言失败,2 = 用法 / 环境错误 | 仓内无调用方(人工 / CI 外挂) | `scripts/check-doc-links.py` 与 `scripts/lib/commands.py` 的白名单 |
| `scripts/acceptance/recheck.sh` | 合并 / amend 前的全量复跑(门禁 + 扫描一致性 + 单测 + 验收);**门禁只跑一遍**(消费 `run-all-gates.sh`,不再单独再跑 `ssdctl gate`) | `bash scripts/acceptance/recheck.sh` | 0 = 全绿,1 = 有失败,2 = 用法 / 环境错误 | 仓内无调用方(人工 / 合并前手动跑) | ① 复跑步骤清单(4 步:gates → `scan --check` → 单测 → 验收);② 解释器口径统一 `bash scripts/ssdctl.sh --python`(机器绑定路径已去掉,仓根由脚本自身位置推导) |
| `scripts/acceptance/a17-e2e.sh` | A17 端到端验收:用 Symphony runner + DSH 后端跑一次真实 `WORKFLOW.md`,再对产物跑仓内门禁 | `bash scripts/acceptance/a17-e2e.sh [--dry-run-only]` | 0 = 通过,1 = 有失败,2 = 用法 / 环境错误 | 仓内无调用方(人工 / 端到端手动跑);`scripts/acceptance/clone-verify.sh` 只把它列进**排除清单**,不是调用 | ① 端到端步骤清单;② runner 位置口径(`$SYMPHONY_RUNNER` 覆盖,默认取本仓同级目录 `symphony-runner`;机器绑定路径已去掉) |
| `scripts/acceptance/agent-first-acceptance.py` | 按实施契约 §10 的 A-1..A-10 逐条验收(Lead 自用) | `"$PY" scripts/acceptance/agent-first-acceptance.py [--write] [--keep]`<br>`--write` 会额外跑 `sync-prd` 写模式并检查 README / material 漂移(**会改文件,只应在所有 lane 结束后跑**) | 0 = 全部通过,1 = 有失败项,2 = 用法错误 | `scripts/acceptance/recheck.sh`、`scripts/tests/test_acceptance_rules.py` | 实施契约 §10 的 A-1..A-10 清单 |

### 2.6 单测(13 —— unittest,`python -m unittest discover -s scripts/tests -t scripts/tests`)

| 路径 | 职责 | 谁调用它 |
|------|------|---------|
| `scripts/tests/_support.py` | 公共支撑:把 `scripts/` 放进 `sys.path`、搭临时仓、判据夹具(`fixtures/criteria.fixture.json`)、用 `sys.executable` 调 CLI | 全部 `scripts/tests/test_*.py` |
| `scripts/tests/test_acceptance_rules.py` | 「旧命令形态残留」规则的判别性测试(旧 `decide` / `evidence` / `--decision` / `control/` 不得复活) | unittest discovery |
| `scripts/tests/test_dispatch.py` | 调度谓词 5 合取的正反两半用例 | unittest discovery |
| `scripts/tests/test_gate_json.py` | `gate --json` 的 JSON 契约测试(输出结构 + 退出码)—— **Lane A 本轮新增** | unittest discovery |
| `scripts/tests/test_human_signature.py` | F9 R-2 / R-3:人工接入 = 制品内署名 + 同一条 `advance` | unittest discovery |
| `scripts/tests/test_implemented_trio.py` | F6:三件套必须同时进入 `Implemented` | unittest discovery |
| `scripts/tests/test_kinds.py` | 判据 12 种 kind 的正反两向 | unittest discovery |
| `scripts/tests/test_md_schema_gate.py` | `scripts/check-md-schema.sh` 的反证测试(需 bash,可用 `SSDCTL_BASH` 指定解释器) | unittest discovery |
| `scripts/tests/test_param_contract.py` | 判据参数契约反证(非法参数一律抛 `CriteriaError` → 退出码 2) | unittest discovery |
| `scripts/tests/test_repo_scope.py` | `scope=repo` 的跨层判据 | unittest discovery |
| `scripts/tests/test_scripts_hygiene.py` | 脚本卫生检查(行尾 / 可执行位 / 引用完整性)—— **Lane A 本轮新增** | unittest discovery |
| `scripts/tests/test_scripts_index.py` | **本索引**与三份入口文档的路径一致性断言(索引覆盖磁盘实况 / 索引无死路径 / 三处文档提到的每个路径都被索引覆盖) | unittest discovery |
| `scripts/tests/test_single_carrier.py` | F9 单载体:授权来源 / 控制平面消失 / CLI 表面 / 跨制品一致性 | unittest discovery |

### 2.7 夹具(1 组)

| 路径 | 职责 | 谁调用它 |
|------|------|---------|
| `scripts/tests/fixtures/**` | 夹具组:`fixtures/artifacts/`(17 个样例制品:好 / 坏 PRD、TD README、Plan、用例、三件套等)+ `fixtures/criteria.fixture.json`(判据夹具)。**按组登记,不逐个列**;存在性断言对本组整体豁免 | `scripts/tests/_support.py`、`scripts/tests/test_md_schema_gate.py` 等 |

### 2.8 索引自身(1)

| 路径 | 职责 | 谁调用它 |
|------|------|---------|
| `scripts/README.md` | **本文件**:仓内脚本清单的唯一真源(职责 / 调用形态 / 退出码 / 谁调用它 / 改了要同步改哪里) | `scripts/tests/test_scripts_index.py`(断言覆盖度与一致性)、三份入口文档的指针 |

## 3. 命令速查

```bash
# 1. 全量门禁(CI 同款):8 个既有门禁 + 判据引擎
bash scripts/ssdctl.sh gate

# 2. 全量门禁 + JSON 输出(已落地:顶层 5 个键 ok / failures / gates / criteria / artifacts)
bash scripts/ssdctl.sh gate --json

# 3. 调度扫描:本层是否可推进(唯一机器资格源)
bash scripts/ssdctl.sh scan --json

# 4. 跨制品一致性:上游闸门 + 三件套原子性 + 字段自洽(只读)
bash scripts/ssdctl.sh scan --check

# 5. 单制品判据评估
bash scripts/ssdctl.sh criteria prd/2026-11-22/layer-checklist.md --json

# 6. 状态推进(唯一写入路径;--to 不含 Draft)
bash scripts/ssdctl.sh advance <artifact> --to Ready --actor agent:ssdctl

# 7. 状态推进只做校验、不写文件(试跑)
bash scripts/ssdctl.sh advance <artifact> --to Ready --dry-run

# 8. 待裁决清单 / 复核:状态块与复审块是否自洽
bash scripts/ssdctl.sh queue <artifact> --json
bash scripts/ssdctl.sh verify <artifact>

# 9. 单测(解释器由包装器解析,CI 与本地同一条规则)
PY="$(bash scripts/ssdctl.sh --python)"; "$PY" -m unittest discover -s scripts/tests -t scripts/tests

# 10. 门禁验收渲染层(消费第 2 条的 JSON,自带清单已删)
bash scripts/acceptance/run-all-gates.sh
```

## 4. 退出码约定

| 码 | 含义 | 处理 |
|----|------|------|
| 0 | 通过 / 成功 | —— |
| 1 | 不通过(内容或门禁问题) | **修产物 / 修命令后重跑**;禁止绕过(不改门禁、不改 `scripts/**`、不删检查项、不把 `--root` 指向别处) |
| 2 | 用法或环境错误(路径写错、参数不对、目录不存在、找不到解释器) | **修命令**,不要当通过 |

补充口径:

- **门禁脚本的 1 与 `ssdctl.py` 的 1 含义不同**:门禁脚本的 1 = 脚本自己发现的违规(命名 / 字段 / 追溯 / 死链 …);`ssdctl.py` 的 1 = **判据或状态校验不通过**(判据数据在 `schema/criteria.json`),它把门禁退出码与判据结果合并汇总。两者都是「不通过」,排查方向不同。
- `--stage` **只对 `scripts/check-md-schema.sh` 有效**(且只能收紧、不能放宽);其余门禁收到 `--stage` 会 `exit 2`(本轮已落地;机器断言见 `scripts/tests/test_scripts_hygiene.py`)。
- `scripts/sync-prd.sh` 与 `scripts/sync-test-index.sh` 的退出码 1 属于**软失败**:在 `--check` 模式下表示「统计块 / 台账 / 索引与实际制品漂移」,台账里有「待分析」待办行也是常态 —— CI 因此**不按这两个脚本的退出码单独判红**,改为写模式 + 比对差异(见 `scripts/lib/commands.py` 的 `SOFT_FAIL_CODES`)。
- 层目录不存在 → 该层**跳过**(不是失败);层目录存在但没有制品 → ⚠ 且退 0;**全仓所有层都没有制品** → 退 1。
- 跑门禁时带 `NO_COLOR=1`;需要机器消费时加 `--json`。
- 本文件里的 `$PY` = `bash scripts/ssdctl.sh --python` 解析出的**真实解释器路径**(Windows 的 `python` 可能是 Microsoft Store 占位符,会命中 exit 9009);**所有 Python 脚本一律用它调用**,不自己再探测一套候选。
- **`gate --json` 的载荷契约**(机器读它,别猜字段):顶层恰好 5 个键 —— `ok`(是否全绿)/ `failures`(阻断失败计数)/ `gates` / `criteria` / `artifacts`;`gates[]` 每项 7 个键:`script` / `args` / `exit_code` / `stdout_bytes`(**该门禁 stdout 的字节数**)/ `soft_fail`(软失败标记)/ `output`(stdout 原文)/ `stderr`(stderr 原文)—— **stdout 与 stderr 分开给**,因为 `check-doc-links.py` 把整份报告写在 stderr,合成一串就分不清输出来自哪里;`criteria[]` 每项 `scope` / `target` / `passed` / `failures[]` / `warnings[]`;`artifacts[]` 每项 `artifact` / `problems[]`。退出码:0 = 全绿,1 = 有阻断失败,2 = 用法 / 环境错误(判据文件缺失或非法也是 2 —— 此时仍会吐出一个 `ok=false` 的载荷,渲染层按 2 原样透传,不降级)。

## 5. 新增脚本的规矩

1. **必须登记**:新脚本要在本文件 §2 的对应分组里写一行(路径 / 职责 / 调用形态 / 退出码 / 谁调用它 / 改了要同步改哪里),并同步在 `WORKFLOW.md` §6 的动作表里写「什么时候跑」。新加的**测试文件**也要登记(在 §2.6),但**不算工具**——工具数只算顶层 / 库 / 验收三类。
2. **进门禁还是明确不进**:要参与 CI 门禁的,加进 `scripts/lib/commands.py` 的 `GATE_SCRIPTS` —— CI 与本地都从它渲染(`ssdctl gate --json` → `run-all-gates.sh` → CI 的「门禁」步骤),**不需要改任何其他文件**;不进的,在本文件里**写明「不进 `GATE_SCRIPTS`,理由是 …」**。
3. **退出码只有 0 / 1 / 2**:0 = 通过,1 = 内容或门禁问题,2 = 用法 / 环境错误;脚本不能因为控制台编码或缺依赖而崩。
4. **不许硬编码机器路径**:仓根 / 解释器路径一律从 `scripts/lib/paths.py` 取或用 `bash scripts/ssdctl.sh --python`;不许自带第二套解释器探测。
5. **新增门禁必须同时可见**:`scripts/lib/commands.py` 的 `GATE_SCRIPTS` 是**单一真源** —— 新门禁加进它之后,
   `bash scripts/ssdctl.sh gate` 与 `scripts/acceptance/run-all-gates.sh` 必须同时看得到它
   (后者只消费 `gate --json` 的结果,不再自带清单)。
6. **被 skill 正文引用的脚本必须真实存在**:`.codex/skills/validate-spec/skills-integrity.sh` 的 Sweep A 会扫
   skill 正文里出现的脚本路径(`.sh` / `.py` 结尾),路径不存在即判失败 —— 新脚本被 skill 引用前先确认它在磁盘上。
7. **不许改判据与状态机语义**:判据数据在 `schema/criteria.json`,状态语义在实施契约 §3;脚本只实现,不重新定义。
8. **不许在脚本里做 git 写操作**:不 commit / push / checkout;写操作只写制品与再生块。
9. **写完加测试**:新增逻辑要在 `scripts/tests/` 里有一条能红的用例。
10. **打印非 ASCII 字符前先固定 stdout 编码**:Windows 上默认编码可能是 GBK,打印 `✗` / `✓` 这类字符会让整个脚本崩掉(不是乱码,是抛异常)。Python 里先 `sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="\n")`(Python < 3.7 没有 `reconfigure`,包一层 `try/except AttributeError`);bash 里先 `export LC_ALL=C.UTF-8`。

## 6. 已知结构债(如实登记,本轮不处理)

| 债 | 事实 | 本轮处理 |
|----|------|---------|
| `scripts/lib/commands.py` 单文件承担 6 个子命令 | 1101 行;`GATE_SCRIPTS` / `SOFT_FAIL_CODES` / `TRIO_LAYERS` / 状态正则与 6 个子命令实现都在一个文件 | **不拆** —— 超出「整理」范围;拆分前需要先给子命令定契约测试 |
| `scripts/lib/criteria.py` 与 `schema/criteria.json` | 前者是**判据引擎**(983 行,实现 12 种 kind),后者是**判据数据** —— 是「引擎 + 数据」关系,**不是重复**,不合并 | 不动 |
| `scripts/deep-scan.py` 只服务可选层 `deep/` | `deep/` 默认关闭,模板自身零实例,故该脚本平时不跑 | 保留;启用 `deep/` 的项目再启用它 |
| 机器绑定路径 4 处 | 原先 `scripts/acceptance/a17-e2e.sh`(解释器)、`scripts/acceptance/clone-verify.sh`(克隆源与目标目录)、`scripts/acceptance/recheck.sh`(仓根)、`scripts/acceptance/run-all-gates.sh`(解释器候选)各写死本机路径 | **已清零**:仓根由脚本自身位置推导,runner 由环境变量或同级目录推导,解释器统一走 `bash scripts/ssdctl.sh --python` |
| 失效的字节码缓存 | `scripts/lib/` 的 `__pycache__` 里残留着 F9 已删除的 `control` 模块的 `.pyc` | **已清**:R-1 要求仓内不留 `__pycache__` 生成物(本地也已清空,且被 `.gitignore` 排除) |

## 7. 不做什么(防误用)

- **不负责状态写入**:状态的唯一写入路径是 `bash scripts/ssdctl.sh advance`(见 `WORKFLOW.md` §5 状态推进规则);
  任何脚本都**不得**手改制品里的状态行 / 复审块。
- **不负责判据内容**:判据的**数据**在 `schema/criteria.json`(唯一权威),**引擎**在 `scripts/lib/criteria.py`;
  脚本不新增、不改写判据语义。
- **不替代契约**:`WORKFLOW.md` 才是状态与调度契约(什么时候跑、谁写、什么算通过);本文件只回答「有哪些脚本、怎么调、退出码是什么」。
- **不引入新工具**:本目录的工具数本轮**零净增**(23 → 23);整理的目标是减少重复,不是增加一层。

## 8. 本轮整理的净变化

- **工具数 23 → 23(0 净增)**:基线 23 = 顶层 11 + 库 7 + 验收 5;本轮只搬信息,不新增工具。新增的两个 `.py` 是**测试**不是工具(单测不计入 23)。
- **脚本清单 3 份 → 1 份**:原先 `README.md` 10 行、`WORKFLOW.md` §6 13 行、`AGENTS.md` §3.8 7 行各抄一份 ⇒ 明细只留在本文件,三份文档各留一个角色的视图 + 指针。
- **机器侧门禁清单 2 份 → 1 份**:`GATE_SCRIPTS` 是唯一真源,`run-all-gates.sh` 与 CI 的「门禁」步骤都从它渲染。
- **解释器探测 3 套 → 1 套**:统一到 `bash scripts/ssdctl.sh --python`;不再有脚本自带候选探测。
- **机器绑定路径 4 处 → 0**:`scripts/acceptance/recheck.sh` 与 `scripts/acceptance/a17-e2e.sh` 的写死路径已改成「由脚本自身位置 / 环境变量推导」。
- **`recheck.sh` 里 8 个门禁跑两遍 → 1 遍**:它现在消费 `run-all-gates.sh`(即 `gate --json` 的渲染层),不再单独再跑一遍 `ssdctl gate`。
- **阶段参数语义收敛**:`--stage` 只对 `scripts/check-md-schema.sh` 有效,其余门禁收到即 `exit 2`。
- **`gate --json` 变成真 JSON**(顶层 5 个键:`ok` / `failures` / `gates` / `criteria` / `artifacts`),`scripts/acceptance/run-all-gates.sh` 改成 JSON 渲染层。
- **CI 里的门禁步骤 9 → 1**:原先 `.github/workflows/spec-check.yml` 逐个列出 8 个门禁、之后再跑一次 `ssdctl gate`(CI 里 8 个门禁实际跑了 16 次)⇒ 现在合并成一步「门禁(8 个既有门禁 + 判据引擎 + 制品自洽性)」,调 `scripts/acceptance/run-all-gates.sh`;**CI 里不再有第二份门禁清单**。
