---
name: commit
description: >-
  产出符合仓库约定的 commit message 并给出待执行的 git 命令 (辅助工具, 不属于规格流水线, v2.0)。
  Use when 需要把本次产出的规格文件提交进版本控制, 或需要一条带 Reviewed-by trailer 的规范提交信息。
  格式为 <type>(<scope>) 加一句摘要, 正文写 改了什么 / 为什么 / 门禁实际结果, 末尾可选 Reviewed-by 与 Issue。
  Reviewed-by 的值取自产物文件 ## 复审 (Review) 段里 评审人 的实际值（可能是 agent:<id> 或人写的 handle, 原样照抄）;
  复审块未签署时整行不写该 trailer。
  agent 不得自行执行 git commit / git push / 切换分支, 也不得编造评审人 handle; 只产出 message 与命令, 由人执行。
---

# commit

把**本次产出的规格文件**提交进版本控制, 并产出一条可被第三方核验的 commit message。

> **本 skill 是辅助工具, 不是规格流水线的一环**。规格流水线是 PRD → Tech Design → Plan（+ 可选 Test Cases）; 本 skill 只负责「怎么提交」。
> **它不做的事**: 不评审、不翻状态、不建 PR、不合并 PR。

## 执行阶段 (内部 phase 标识)

agent 按下列 phase 顺序推进。每个 phase 开始时在汇报里写明 `phase: <name>`。

> phase 是 agent 的**内部工作分段**, 不依赖任何 UI 模式指示器, 也不假设运行环境会显示模式。

| Phase | agent 做什么 |
|-------|--------------|
| `collect` | 看 `git status --short` + `git diff --stat`, 确定本次提交**只包含哪些产物路径** |
| `compose` | 按下面的格式写 commit message（正文写「改了什么 / 为什么 / 门禁实际结果」）|
| `trailer` | 处理 `Reviewed-by:` trailer（见下方硬规则）|
| `handoff` | 把 message 全文 + **待人执行的命令**交给人; agent **不执行** git 写操作 |

## 调用输入

| 输入 | 必填 | 说明 |
|------|------|------|
| 提交范围 | 否 | 显式列出要加入版本控制的路径; 省略时由 agent 从 `git status` 判断本次产出文件 |
| 工作项标识 | 否 | 有则写进 `Issue:` trailer; 没有就省略该行 |
| 提交分支 | 否 | **由人指定**; agent 不自行创建或切换分支 |

示例: 把 `prd/2026-07-03/login.md` 与 `tech_design/2026-07-03-login/` 作为一次提交, 工作项标识 `SSD-42`。

## 前置条件

| 依赖 | 说明 |
|------|------|
| 工作目录 | 仓根目录 |
| 待提交文件 | 本次产出文件已落盘, 且已跑过判据与门禁（实际结果写进正文）|
| 判据与门禁入口 | `scripts/ssdctl.py`（`criteria` / `gate` / `verify`）; 结果取自它的真实退出码 |
| 人工许可 | 执行 git 写操作由**人**做; 本 skill 只产出 message 与命令 |

## 提交信息格式

```text
<type>(<scope>): <一句话摘要>

<正文: 改了什么 / 为什么 / 门禁实际结果>

Reviewed-by: <评审人 handle>
Issue: <工作项标识>
```

| 字段 | 规则 |
|------|------|
| `type` | `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `build` / `ci` |
| `scope` | 本次提交的层或目录, 如 `prd` / `tech_design` / `plan` / `test_cases` |
| 摘要 | 一句话, 祈使句, 不加句号, 描述「改了什么」而不是「做了什么」|
| 正文 | 三件事: 改了什么 / 为什么 / **门禁的实际输出结果**（贴真实结论, 不写「已通过」这种空话）|
| `Reviewed-by:` | 见下节硬规则; 产物复审块未签署时**整行不写** |
| `Issue:` | 工作项标识; 没有就整行省略 |

**只提交本层产物**: 显式列出要加入版本控制的路径, **不要 `git add -A`**（工作区里可能有临时文件）。

## `Reviewed-by:` trailer 的硬规则

`Reviewed-by:` 记录的是**本次产出的复审动作**; 取值 = 产物文件 `## 复审 (Review)` 段里 `> **评审人**` 的**实际值**。它**不是**门禁依据。

1. **值的唯一来源**: 本次提交涉及的产物文件, 其 `## 复审 (Review)` 段里 `> **评审人**` 的**实际值**。
2. **值的形态**: 可能是 `agent:<id>`（判据驱动的自动推进, 复审由 agent 起草自评）, 也可能是人写的裸 handle; **原样照抄, 不加工、不改写、不补前缀、不删前缀**。
3. **产物复审块未签署时**（评审人行为空或缺失）:
   - **`Reviewed-by:` 整行不写**; commit message 里连这一行都不出现;
   - **不得**写 `Reviewed-by: 待人工回写` / `Reviewed-by: TBD` / `Reviewed-by: 无` / `Reviewed-by: N/A` 之类占位或占位变体; 整行缺失本身就是正确写法。
4. **不得伪造**: agent 不得自行编造任何评审人 handle, 不得用 agent 自己的 handle 冒充人的评审, 也**不得从别的产物的 Review 段抄**评审人。
5. **只出现在 commit message 里**: trailer **不得**写进产物文件的 `## 复审 (Review)` 段; 那会伪造评审痕迹。
6. **多个产物**各自评审人不同 ⇒ 逐行列出 (`Reviewed-by: a` / `Reviewed-by: b`), 每个值都来自各自产物的 Review 段。
7. **拿不准就不写**: 读不到产物的 `> **评审人**` 时, 按第 3 条处理, 不要猜。

## git 写操作的硬禁止

> **agent 不得自行执行任何 git 写操作**。

**禁止 agent 自己执行**: `git add` / `git commit` / `git push` / `git checkout` / `git switch` / `git merge` / `git rebase` / `git stash` 等一切改变索引、分支或远端状态的动作。

**理由**（真实运行观察）: agent 曾自行在工作区 commit, 并把分支从 `main` 切到自造分支, 绕过了人的提交与分支授权。

**agent 的交付物只有两样**:
1. commit message 全文;
2. **待人执行的命令**（原样可粘贴）:

```bash
# 1. 确认范围
git status --short
git diff --stat

# 2. 显式加入本次产物（不要 git add -A）
git add prd/2026-07-03/login.md tech_design/2026-07-03-login/

# 3. 写 message 文件并提交
git commit -F .git/COMMIT_EDITMSG.tmp
```

- message 文件写在 `.git/` 下（不污染工作区, 也不会被 `git add` 误收）。
- **分支由人决定**: agent 不创建分支、不切换分支; 若产物需要落在非当前分支上, 由人先切好, agent 在该分支上产出 message。
- **推送、建 PR、合并 PR 同样由人执行**; agent 不发起任何远端写操作。

## 禁止行为 (Agent 权限边界)

| ❌ Don't | ✅ Do |
|----------|-------|
| 自行 `git commit` / `git push` / `git add` / 切换或创建分支 | 只产出 message 与待执行命令; git 写操作由人做 |
| 编造 / 猜 `Reviewed-by:` 的 handle | 只取自产物 Review 段 `> **评审人**` 的实际值; 读不到就不写 |
| 伪造人工署名 | agent 只能署 `agent:<id>`; 不得填 `human:` 前缀, 不得代填人名 |
| 未签署时写 `Reviewed-by: 待人工回写` 之类占位 | 整行不写; 整行缺失就是正确形态 |
| 把 `agent:<id>` 改写成裸 handle（或反过来）| 原样照抄产物的 `> **评审人**` |
| 从别的产物的 Review 段抄评审人 | 每个产物各取各的评审人 |
| 把 `Reviewed-by:` 写进产物的 Review 段 | trailer 只出现在 commit message |
| `git add -A` | 显式列出本次产出的路径 |
| 建 PR / 合并 PR / 推主分支 | 远端写操作由人执行 |
| 自行翻 `Ready` / `Implemented` | 状态由 `scripts/ssdctl.py advance` 按判据写; agent 不手改状态行 |
| 留下 `{...}` 占位符 | 填真实值, 不适用就删整行 |

## Verification

- 产出的 message 全文与预期一致（agent 自查文本, 不靠 `git log` 验证）。
- message 里列出的路径集合 == 本次产出路径集合（不多不少）。
- 产物复审块未签署时, message 里**没有** `Reviewed-by:` 行, 也没有任何占位变体。
- 产物复审块已签署时, `Reviewed-by:` 的值与产物 `## 复审 (Review)` 段的 `> **评审人**` **逐字一致**（`agent:<id>` 也照抄）。
- agent 没有执行任何 git 写操作: 工作区的分支名、`git status --short` 的索引状态与执行前一致。

## 安装 (Installation)

skill 定义随仓库分发, agent 直接读 `.agents/skills/commit/SKILL.md` 即可, **无需注册**。

需要把 skill 装进宿主 agent 的 skills 根目录时, 用仓内安装脚本：

```bash
bash <repo>/.agents/skills/install.sh                     # 默认 ~/.codex/skills/
bash <repo>/.agents/skills/install.sh --target <dir>      # 指定目标
bash <repo>/.agents/skills/install.sh --unregister        # 注销
```

## Related Skills

- `.agents/skills/validate-spec/SKILL.md`：提交前跑判据与门禁, 把**实际输出**写进 commit 正文
- `.agents/skills/to-prd/SKILL.md` / `.agents/skills/to-tech-design/SKILL.md` / `.agents/skills/to-plan/SKILL.md`：产出被提交的文件
- `.agents/skills/sync-status/SKILL.md`：状态编排（状态块由 `ssdctl advance` 代写）

## Cross-References

- <repo>/WORKFLOW.md §8（提交与证据: message 格式 + `Reviewed-by:` 规则 + 禁止合并 PR）
- <repo>/AGENTS.md §1.7（证据锚点 `{标识}@{短SHA}:{路径}#L{行号}`）
- <repo>/AGENTS.md §3.3（状态流转: 状态块由 `ssdctl advance` 写, agent 不手改状态行）
- `schema/criteria.json`（判据唯一权威）
- <repo>/scripts/ssdctl.py（判据与门禁的唯一入口）
