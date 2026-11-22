---
name: commit
description: >-
  产出符合仓库约定的 commit message 并执行提交 (辅助工具, 不属于规格流水线)。Use when 需要把本次产出的规格文件提交进版本控制,
  或需要写一条带 Reviewed-by: trailer 的规范提交信息。格式为 <type>(<scope>): <摘要> + 正文 + Reviewed-by: + Issue:;
  Reviewed-by 的值只能取自产物文件 ## 复审 (Review) 段里人工填写的 > **评审人**, 产物仍是 Draft 时不写该 trailer。
  agent 不得自行编造评审人 handle, 不得自行 push, 不做 PR 合并。
---

# commit

把**本次产出的规格文件**提交进版本控制, 并产出一条可被第三方核验的 commit message。

> **本 skill 是辅助工具, 不是规格流水线的一环**。规格流水线是 PRD → Tech Design → Plan（+ 可选 Test Cases）; 本 skill 只负责「怎么提交」。
> **它不做的事**: 不评审、不翻状态、不建 PR、不合并 PR、不 push。

## 执行阶段 (内部 phase 标识)

agent 按下列 phase 顺序推进。每个 phase 开始时在汇报里写明 `phase: <name>`。

> phase 是 agent 的**内部工作分段**, 不依赖任何 UI 模式指示器, 也不假设运行环境会显示模式。

| Phase | agent 做什么 |
|-------|--------------|
| `collect` | 看 `git status --short` + `git diff --stat`, 确定本次提交**只包含哪些产物路径** |
| `compose` | 按下面的格式写 commit message（正文写「改了什么 / 为什么 / 门禁实际结果」）|
| `trailer` | 处理 `Reviewed-by:` trailer（见下方硬规则）|
| `commit` | 把 message 写进临时文件, `git commit -F <file>` |

## 调用输入

| 输入 | 必填 | 说明 |
|------|------|------|
| 提交范围 | 否 | 显式列出要加入版本控制的路径; 省略时由 agent 从 `git status` 判断本次产出文件 |
| issue 标识 | 否 | 有则写进 `Issue:` trailer; 交互式会话没有就省略该行 |
| 分支名 | 否 | 需要新建分支时用 `spec/{issue-identifier}-{topic}` |

示例: 把 `prd/2026-07-03/login.md` 与 `tech_design/2026-07-03-login/` 作为一次提交, issue 标识 `SSD-42`。

## 前置条件

| 依赖 | 说明 |
|------|------|
| 工作目录 | 仓根目录 |
| 待提交文件 | 本次产出文件已落盘, 且已跑过 `validate-spec`（门禁结果写进正文）|
| 人工许可 | 提交动作本身由人授权; 本 skill 不自行 push |

## 提交信息格式

```text
<type>(<scope>): <一句话摘要>

<正文: 改了什么 / 为什么 / 门禁实际结果>

Reviewed-by: <评审人 handle>
Issue: <issue 标识>
```

| 字段 | 规则 |
|------|------|
| `type` | `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `build` / `ci` |
| `scope` | 本次提交的层或目录, 如 `prd` / `tech_design` / `plan` / `test_cases` |
| 摘要 | 一句话, 祈使句, 不加句号, 描述「改了什么」而不是「做了什么」|
| 正文 | 三件事: 改了什么 / 为什么 / **门禁的实际输出结果**（贴真实结论, 不写「已通过」这种空话）|
| `Reviewed-by:` | 见下节硬规则 |
| `Issue:` | 当前 issue 标识; 交互式会话没有就整行省略 |

**只提交本层产物**: 显式列出要加入版本控制的路径, **不要 `git add -A`**（工作区里可能有临时文件）。

## `Reviewed-by:` trailer 的硬规则

`Reviewed-by:` 是**评审动作的记录**, 取值只能来自产物文件里**人工填写的**评审人; 它**不是**门禁依据。

1. **值的唯一来源**: 本次提交涉及的产物文件, 其 `## 复审 (Review)` 段里**人工填写**的 `> **评审人**`。
2. **产物仍是 `Draft`（评审三行未由人工签署）时**:
   - **不写 `Reviewed-by:` trailer**;
   - 在 trailer 的位置写明「评审未签署, Reviewed-by 待人工回写」;
   - 并在 workpad（`.symphony/workpad.md`）里记一条, 说明该提交尚无评审签署。
3. **不得伪造**: agent 不得自行编造任何评审人 handle, 不得用 agent 自己的 handle 冒充评审, 也**不得从别的 issue 的产物里抄**评审人。
4. **只出现在 commit message 里**: trailer **不得**写进产物文件的 `## 复审 (Review)` 段; 那会伪造评审痕迹, 使未签署的产物看起来已评审。
5. **多个产物**各自评审人不同 ⇒ 逐行列出 (`Reviewed-by: a` / `Reviewed-by: b`), 每个值都来自各自产物的 Review 段。
6. **拿不准就不写**: 读不到人工填写的评审人时, 按第 2 条处理, 不要猜。

## 提交步骤

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
- 提交后用 `git log -1 --format=%B` 复核实际落盘的 message 与预期一致。

## 禁止行为 (Agent 权限边界)

| ❌ Don't | ✅ Do |
|----------|-------|
| 编造 / 猜 `Reviewed-by:` 的 handle | 只取自产物 Review 段人工填写的 `> **评审人**`; 读不到就不写 |
| 从别的 issue 的产物抄评审人 | 每个产物各取各的评审人 |
| 把 `Reviewed-by:` 写进产物的 Review 段 | trailer 只出现在 commit message |
| 产物仍是 `Draft` 时照写 trailer | 按硬规则第 2 条: 不写 trailer + workpad 记一条 |
| `git add -A` | 显式列出本次产出的路径 |
| `git push` | 只提交; 是否推送由人决定 |
| 建 PR / 合并 PR | 评审与合并由人完成 |
| 自行翻 `Ready` / `Implemented` | 只写 `Draft` |
| 留下 `{...}` 占位符 | 填真实值, 不适用就删整行 |

## Verification

- `git log -1 --format=%B` 的实际输出与预期的 message 一致。
- `git show --stat --oneline HEAD` 列出的文件**只有**本次产出的路径。
- 产物若仍是 `Draft`, message 里没有 `Reviewed-by:` 行, 且 workpad 有对应说明。
- 产物若已由人工签署, `Reviewed-by:` 的值与产物 `## 复审 (Review)` 段的 `> **评审人**` **逐字一致**。
- 没有 push、没有 PR、没有合并。

## 安装 (Installation)

skill 定义随仓库分发, agent 直接读 `.codex/skills/commit/SKILL.md` 即可, **无需注册**。

需要把 skill 装进宿主 agent 的 skills 根目录时, 用仓内安装脚本：

```bash
bash <repo>/.codex/skills/install.sh                     # 默认 ~/.codex/skills/
bash <repo>/.codex/skills/install.sh --target <dir>      # 指定目标
bash <repo>/.codex/skills/install.sh --unregister        # 注销
```

## Related Skills

- `.codex/skills/validate-spec/SKILL.md`：提交前跑门禁, 把**实际输出**写进 commit 正文
- `.codex/skills/to-prd/SKILL.md` / `.codex/skills/to-tech-design/SKILL.md` / `.codex/skills/to-plan/SKILL.md`：产出被提交的文件
- `.codex/skills/sync-status/SKILL.md`：状态回写（评审签署后才会出现 `Ready`）

## Cross-References

- <repo>/WORKFLOW.md §8（提交与证据: message 格式 + `Reviewed-by:` 规则 + 禁止合并 PR）
- <repo>/AGENTS.md §1.7（证据锚点 `{标识}@{短SHA}:{路径}#L{行号}`）
- <repo>/AGENTS.md §3.3（状态流转: agent 写入上限是 `Draft`）
