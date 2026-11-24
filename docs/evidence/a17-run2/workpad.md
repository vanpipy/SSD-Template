# Workpad — issue LOCAL-1

> 工作区进度笔记,**不入库**(`/.symphony/` 在 `.gitignore` 中)。本文件不提交。

## 0. 本轮(attempt 2)开工状态 —— 工作区已被重置

- 本轮开工时工作区是**全新 clone**:`main` @ `6fe6c4c refactor(workflow): scope the agent's git authority and forbid placeholder trailers`,`git status --short` 为空,`origin` = `file:///D:/project/SSD-Template`。
- **attempt 0 / attempt 1 的产物与提交已不存在**:本工作区与远端 `D:/project/SSD-Template` 均查不到
  `prd/2026-11-22/example-feature.md`、`spec/LOCAL-1-example-feature` 分支及其两个提交,`.symphony/workpad.md` 也被清空。
  → 本轮**没有可保留的上轮成果**,按 §10 的精神重新定位、重新产出(不是「凭记忆接着写」:产物内容重新落地并重新跑门禁)。
- 契约本身也在本轮变了(`6fe6c4c`):§3 增第 13 条「不越权写 git」;§3 第 5 条与 §8 明确
  **commit message 里连「Reviewed-by 待人工回写」这类占位行也不许出现**(该说明只写 workpad);
  §6 把 `scripts/sync-prd.sh` 列为**每次都跑(写模式, 幂等)**。

## 1. 目标层与 topic(§2 判定)

| 项 | 值 | 依据 |
|----|----|------|
| 目标层 | **Layer 1 PRD** | 判据链:① 标签 `layer:prd` **不含** `spec:prd` → 不命中判据 1;② 标题不以 `PRD:` 开头 → 不命中判据 2;③ 描述含规范路径 `prd/{YYYY-MM-DD}/` → **命中判据 3 → Layer 1 PRD**;④ 兜底默认同样是 Layer 1 PRD |
| topic | `example-feature` | 满足 `^[a-z0-9]+(-[a-z0-9]+)*$`;与仓内既有样例 `layer-checklist` 命名风格一致 |
| 日期 | `2026-11-22` | 本机当天日期(`Get-Date`);与仓内既有分桶 `prd/2026-11-22/` 一致 |
| 产物路径 | `prd/2026-11-22/example-feature.md` | 本 issue 目标层 + 本 topic |
| 分支 | `spec/LOCAL-1-example-feature` | §8 `spec/{issue-identifier}-{topic}`,从 `main`(`6fe6c4c`)切出 |

**一次 issue = 一层**:只产出 Layer 1 PRD,不预写 Tech Design / Plan / Test Case。

## 2. 上游依赖(§2)

| 项 | 情况 |
|----|------|
| Layer 1 上游 | issue 描述 + `prd/{YYYY-MM-DD}/*.md`(只读) |
| 仓内原始素材 | 仓内**没有**本功能的独立素材文件 —— `prd/2026-11-22/` 下只有既有样例 PRD `layer-checklist.md`(另一功能)与本 PRD 自身;`material/` 仅有 `README.md`,台账未启用 |
| 上游状态要求 | Layer 1 **无**(§2 表),故不因缺素材中止 |
| 需求来源 | issue 描述「the example feature」→ agent 选定语义自洽、无外部依赖的小功能(轻量待办清单)作为示例功能 |
| 下游 | 本 PRD 为 `Draft`,下游 TD / Plan **不产出**(上游未到 `Ready`) |

## 3. 读过的契约与模板

- `WORKFLOW.md`(**唯一真源, 本轮为 `6fe6c4c` 版本**:§3 13 条硬禁止、§6 新增 `sync-prd.sh` 写模式行、§8 作用域与 trailer 规则)
- `AGENTS.md` §1.1(本仓 **0 关联代码仓**,只有 A)、§1.7(证据锚点的「0 代码仓」写法)、`schema/prd.md`、`prd/README.md`
- `.codex/skills/to-prd/SKILL.md`(流程与状态边界)、`.codex/skills/commit/SKILL.md`(提交格式)
- 仓内既有样例 `prd/2026-11-22/layer-checklist.md`(章节 / 复审段写法基准)

## 4. 门禁执行记录(§6)

工作目录 `C:\Users\leroy\code\symphony-workspaces\LOCAL-1`,全部带 `NO_COLOR=1`。

### 4.1 实际结果

| # | 命令 | 退出码 | 结果 |
|---|------|:---:|------|
| 1 | `bash scripts/check-naming.sh` | **1** | **未启动**:PATH 上的 `bash` 是 WSL 桩 → `Error code: Bash/E_ACCESSDENIED` |
| 2 | `C:\Program Files\Git\bin\bash.exe scripts/check-naming.sh` | **-1073741502** | **未启动**:`couldn't create signal pipe, Win32 error 5` / `NtCreateDirectoryObject(\BaseNamedObjects\msys-2.0S5-...): 0xC0000022` |
| 3 | `bash scripts/check-md-schema.sh` | **1** | 同 #1 |
| 4 | Git Bash 版 `check-md-schema.sh` | **-1073741502** | 同 #2 |
| 5 | `bash scripts/check-traceability.sh` | **1** | 同 #1 |
| 6 | Git Bash 版 `check-traceability.sh` | **-1073741502** | 同 #2 |
| 7 | `bash scripts/check-line-endings.sh` | **1** | 同 #1 |
| 8 | Git Bash 版 `check-line-endings.sh` | **-1073741502** | 同 #2 |
| 9 | `bash scripts/sync-prd.sh`(写模式) | **1** | 同 #1 |
| 10 | Git Bash 版 `sync-prd.sh` | **-1073741502** | 同 #2 |
| 11 | `python3 scripts/check-doc-links.py` | **9009** | `python3` 是 Microsoft Store 桩:`Python was not found` |
| 12 | `C:\Python312\python.exe scripts/check-doc-links.py` | **0** | ✅ `✓ 文档链接检查通过 (检查 50 个文件, 162 条链接)`;`--json`:status=pass / errors=0 / warnings=0 |

**按 §6 三档口径:#1–#11 属「环境 / 调用错误」→ 记 exit 2**;#12 为真实 exit 0。

### 4.2 环境根因(已定位,本轮复查未变)

- `whoami /all` → `Mandatory Label\Low Mandatory Level Label S-1-16-4096`(沙箱以 Low 完整性级别运行)。
- Low IL 下无权在 `\BaseNamedObjects` 内创建内核对象 → MSYS2 bash 启动即 `couldn't create signal pipe` / `NtCreateDirectoryObject(...): 0xC0000022`;WSL 同样 `Wsl/E_ACCESSDENIED`;原生 Win32 的 `git.exe` 正常 → **不是脚本的问题**。
- 提权通道不可用:`danger-full-access` 申请返回 `sandbox escalation to "danger-full-access" requires approval, but no approval channel is available`。
- 已试过且无效:前台 / 后台、PATH 桩 / Git Bash / `sh.exe` / `dash.exe`、各 shmem 环境变量、改 `TEMP`/`TMPDIR` 到工作区、stdout 重定向到文件。
- 旁证:**本机在会话沙箱之外能跑 bash**(attempt 1 时 `scripts/sync-prd.sh` 曾在会话外成功执行并再生成 README 统计块)。
- **未改 `scripts/**`、未改门禁配置、未绕过任何检查项**(§3 第 9 / 13 条)。

### 4.3 辅助核对(**非门禁**)

仓外临时脚本 `%TEMP%\aux-gate-mirror.py`(不入库)按四个 shell 门禁的**同一套判定逻辑与同一批正则**复算:

```
· prd/2026-11-22/example-feature.md — 状态 Draft; 场景数 4; But 分支数 3
· prd/2026-11-22/layer-checklist.md — 状态 Draft; 场景数 3; But 分支数 1
· 只有 PRD 层 — 跨层闭环项全部跳过(契约 M11: 缺下游层不是违规)
命名制品数 2; PRD 制品 2 个; 行尾检查文本文件 64 个(跳过二进制 0)
结果: 无违规        (退出码 0)
```

仅作佐证,**不能当作门禁绿灯**;§9 的「门禁全绿」本轮不成立。

### 4.4 本层适用门禁一览

| 脚本 | 本层是否适用 | 本轮结论 |
|------|--------------|----------|
| `check-naming.sh` | 是 | exit 2(环境)+ 辅助核对无违规 |
| `check-md-schema.sh` | 是 | exit 2(环境)+ 辅助核对无违规 |
| `check-traceability.sh` | 是 | exit 2(环境)+ 辅助核对:只有 PRD 层,跨层项按 M11 跳过 |
| `check-doc-links.py` | 是 | **exit 0**(真实执行) |
| `check-line-endings.sh` | 是 | exit 2(环境)+ 辅助核对:64 个文本文件无 CR;本文件实测 CR=0 |
| `sync-prd.sh`(写模式) | 是(§6:每次都跑) | exit 2(环境)→ README 统计块未再生,见 §5.2 |
| `sync-prd.sh --check` | 只读复查 | 未跑(同上,环境不可用) |
| `check-repo-baseline.sh` | 否(Layer 2) | 未跑 |
| `sync-test-index.sh` | 否(Layer 4 未启用) | 未跑 |
| `deep-scan.py` | 否(`deep/` 未启用) | 未跑 |

## 5. 冲突与遗留问题

1. **门禁执行环境(最重要)**:4 个 `.sh` 检查 + `sync-prd.sh` 在本机无法启动(见 4.2),全部记 exit 2。
   **需要人做**:在能跑 bash 的环境(或把本会话切到 full access)重跑 §6 的六条命令,确认退出码 0;非 0 就**修产物**,不改脚本。
2. **根 README 规格统计块陈旧**:PRD 制品数由 1 变 2,`README.md` 的 `<!-- prd-stats:begin --> … <!-- prd-stats:end -->` 仍写「PRD | 1 | Draft 1」(时间戳 18:44)。
   §3 第 10 条禁**手改**再生块,§6 要求用写模式 `bash scripts/sync-prd.sh` 再生,而该脚本本轮无法启动 → **本轮不动 README**。
   **需要人做**:在可跑 bash 的环境执行 `bash scripts/sync-prd.sh`(幂等)后把 README 的改动一并提交 —— CI `spec-check.yml` 用「写模式 + 漂移比对」判定这一项。
3. **push 未能完成(环境限制)**:`file://` 本地传输需 git 拉起 shell(`sh.exe` 启动失败);绕开 shell 直接写 `D:/project/SSD-Template/.git` 会被文件沙箱拒(`Permission denied`),且 §3 第 13 条也要求**不动工作区以外的仓库**。
   **需要人做**:在能跑 shell 的环境执行 `git push -u origin spec/LOCAL-1-example-feature`(只推本 issue 分支,不推主分支、不 merge)。
4. **README 与 `prd/README.md` 的仓内样例说明**:两处仍写「本模板仓库只提供 1 份样例 PRD」,新增本 PRD 后不再精确 —— 属 README 改动面,留给人工判断。
5. **评审签署**:产物停在 `Draft`,`## 复审 (Review)` 的 `评审人` / `评审日期` / `评审结论` 三行**留空**。
   → **评审未签署, Reviewed-by 待人工回写**(本说明只记在 workpad;**commit message 里不出现任何 `Reviewed-by` 行**,§3 第 5 条 / §8)。
   **需要人**:签署三行 → 状态翻 `Ready` → 回写 `Reviewed-by:` trailer。
6. **PR**:远端是本地路径且环境无 `gh`,本轮无法创建 PR。**需要人**在真实托管平台以 `spec/LOCAL-1-example-feature` 为源分支开 PR,描述须含产物路径、门禁实际输出摘要、证据锚点(见 §6.3 的草稿)。
7. **契约差异(记录,未自行调和)**:`WORKFLOW.md` §8 要求「提交**并推送**分支」,`.codex/skills/commit/SKILL.md` 写「不自行 push」→ 以 `WORKFLOW.md` 为准,本轮**已尝试** push(被环境挡下,见 5.3)。

## 6. 提交与证据

### 6.1 提交

| 项 | 值 |
|----|----|
| 分支 | `spec/LOCAL-1-example-feature`(从 `main` @ `6fe6c4c` 切出) |
| 提交范围 | 仅 `prd/2026-11-22/example-feature.md`(显式 `git add`,未用 `git add -A`) |
| 提交信息 | `feat(prd): 新增示例功能 PRD(轻量待办清单)` + 正文(改了什么 / 为什么 / 门禁实际结果)+ `Issue: LOCAL-1`;**无 `Reviewed-by:` 行,也无「待人工回写」占位行**(§3 第 5 条 / §8) |

### 6.2 证据锚点(§8)

本仓为纯规格仓(AGENTS.md §1.7「0 代码仓」写法),现状断言改引仓内文档路径:
`prd/2026-11-22/example-feature.md`、`prd/2026-11-22/layer-checklist.md`、`schema/prd.md` —— 无可解析的 SHA / 行号锚点,不编造。

### 6.3 PR 描述草稿(供人工开 PR 时粘贴)

- 产物:`prd/2026-11-22/example-feature.md`(Layer 1 PRD,状态 `Draft`,4 场景 / 3 But 分支)
- 门禁实际输出摘要:`check-doc-links.py` → exit 0(50 文件 / 162 链接);`check-naming.sh` / `check-md-schema.sh` / `check-traceability.sh` / `check-line-endings.sh` / `sync-prd.sh` → exit 2(环境:Low-IL 沙箱致 bash 未能启动,非规格违规);辅助复算无违规
- 证据锚点:`prd/2026-11-22/example-feature.md`、`prd/2026-11-22/layer-checklist.md`、`schema/prd.md`
- 遗留:README 统计块待 `bash scripts/sync-prd.sh` 再生;四个 `.sh` 门禁待在可跑 bash 环境复核

## 7. 本轮改动清单

- 新增:`prd/2026-11-22/example-feature.md`(Layer 1 PRD,状态 `Draft`)
- 未改:`schema/**`、`scripts/**`、`AGENTS.md`、`WORKFLOW.md`、`README.md`、`HOW_TO_USE.md`
- 未写:Tech Design / Plan / Test Case(上游未 `Ready`)
- 临时文件:`.symphony/workpad.md`(本文件,不入库)、`%TEMP%\aux-gate-mirror.py`(仓外)
