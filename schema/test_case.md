# Test Case: {topic}

> **本文件是 Layer 4 测试用例模板**. SSD-Template 默认**不启用** Layer 4, 仅当项目需要独立测试用例管理时创建 `test_cases/` 目录并按本模板产出文件.
> 创建 test_cases/ 后, `scripts/check-md-schema.sh` 自动启用 Test Case 校验 (元信息 7 必填行 + 状态枚举 + 用例总览 + 要点伴生).
>
> **状态块 (4 行, 机器校验)**: 下面这 4 行是本文件状态的**唯一权威**;元信息表里的「状态」行是 `scripts/check-md-schema.sh` 读的镜像值, 两者必须一致。

> **状态**: Draft | Ready | Implemented | Deprecated
> **状态主体**: agent:{id} | human:{handle}
> **状态时间**: {YYYY-MM-DDTHH:MM:SS±HH:MM}
> **状态依据**: criteria:{id}[,{id}…] | external:{ref}

---

## 元信息 (Metadata)

> 字段名**严格统一**, 校验脚本按这些字段名抓取值(取「字段」列的下一个单元格作为「值」)。顺序不限, 但建议按本模板顺序排列.
> 「必填」列: ✓ = `scripts/check-md-schema.sh` 的元信息 7 必填行(主题 / 业务产品 / 目标平台 / 来源 / 生成日期 / 状态 / 用例总数);可选 = 不参与门禁, 有则填, 无则留空或删除整行.

| 字段 | 值 | 必填 | 说明 |
|------|-----|------|------|
| **主题** | `{topic}` | ✓ | 测试用例主题, 与目录/文件名一致 |
| **业务产品** | `[产品名]` | ✓ | 哪个业务产品 (POS / ERP / CRM / ...) |
| **目标平台** | `[Web / iOS / Android / 服务端 / 跨端]` | ✓ | 测试运行平台 |
| **来源** | `[prd/{date}/{topic}.md]` | ✓ | 上游 PRD 路径 (仓内) 或 URL (仓外, 如 wiki/doc 系统) |
| **来源 Tech Design** | `[tech_design/{date}-{topic}/README.md]` | 可选 | 上游 Tech Design 路径 |
| **来源 Plan** | `[plan/{date}-{topic}/{topic}.md]` | 可选 | 上游 Plan 路径 |
| **生成日期** | {YYYY-MM-DD} | ✓ | 首次生成日期 |
| **最后更新** | {YYYY-MM-DD} | 可选 | 最近一次更新日期 |
| **状态** | Draft | ✓ | Draft / Ready / Implemented / Deprecated |
| **用例总数** | {n} | ✓ | 本文件包含的用例总数 (主+冒烟合计) |

**关联 PRD 场景**: [../../prd/{YYYY-MM-DD}/{topic}.md](../../prd/{YYYY-MM-DD}/{topic}.md)
**关联 Tech Design**: [../../tech_design/{YYYY-MM-DD}-{topic}/README.md](../../tech_design/{YYYY-MM-DD}-{topic}/README.md)
**关联 Plan**: [../../plan/{YYYY-MM-DD}-{topic}/{topic}.md](../../plan/{YYYY-MM-DD}-{topic}/{topic}.md)

---

## 状态机约定

> **状态取值**: 只能是 `Draft` / `Ready` / `Implemented` / `Deprecated` 四者之一, 不得自造状态名。
> **主体口径**: `agent:<id>` = 机器写入, `human:<handle}` = 人工写入。**agent 不得填 `human:` 前缀、不得代填人名**(INV-3);`--actor` 只接受 `agent:<id>`,**机器不代填人名**。**已知代价**:机器只能证明「人工署名写在本制品的 `## 复审 (Review)` 段内、形态合法、机器没有代填」,**无法证明**「确系本人所写」(实施契约 §5.2 / §6.3)。
> **状态推进**: agent 按 `schema/criteria.json` 的判据推进 —— 判据全绿即可由机器代写 `Ready`;`Implemented` 需外部事实依据(`external:`, 如用例已实际执行通过);**人可新增素材,或在本制品的 `## 复审 (Review)` 段写署名,然后跑同一条 `bash scripts/ssdctl.sh advance` 推进 —— 人与 agent 走同一条流水线**;上游转 `Deprecated` 时, 本文件一并 `Deprecated`(级联)。
> **依据形式**: `criteria:<id>[,{id}…]` = 判据 id 列表, `external:<ref>` = 外部事实。人工介入的载体是本文 `## 复审 (Review)` 段的 `评审人` / `评审方式`,**不写进 `状态依据`**。**状态块 4 行都要写** —— `Draft` 态写当次生成的 `状态主体` / `状态时间` / `状态依据`;升 `Ready` / `Implemented` 时后三行必填且非空。
> **复审块 (4 行, 机器校验)**: `评审人` / `评审日期` / `评审结论` / `评审方式` 4 行都要写(`Draft` 态值可留空, 升 `Ready` 前 4 行必填非空)。取值: 评审人 = `agent:<id>` | 裸 handle(人工), 评审日期 = `YYYY-MM-DD`, 评审结论 = 通过 | 有条件通过 | 需返工, 评审方式 = 自动判据 | 人工介入 | 外部事实。`评审人` 为 `agent:*` 时 `评审方式` 不得为 `人工介入`。

| 状态 | 含义 | 校验约束 |
|------|------|----------|
| **Draft** | 初稿, 内容可能不全 | 无(评审四行可留空) |
| **Ready** | 内容完整, 评审通过 | 必须伴生 `{topic}-key-points.md`; `## 复审 (Review)` 四行已签署 |
| **Implemented** | 用例已实际执行过 | 必须伴生 `{topic}-key-points.md`; 需外部事实依据 |
| **Deprecated** | 已废弃, 不再维护 | 无; 上游 `Deprecated` 时**级联**转入 |

---

## 复审 (Review)

> 本段是**机器必填段**。四行(`评审人` / `评审日期` / `评审结论` / `评审方式`)是**评审签署**载体 —— `Draft` 阶段清空, 升 `Ready` 前由 agent 按 `schema/criteria.json` 的判据填写真值并翻转状态。
> `评审人` 取值: `agent:<id>` = 机器签署, 裸 handle = 人工签署。**agent 不得填 `human:` 前缀、不得代填人名**(INV-3)。
> `评审方式` 取值: `自动判据` / `人工介入` / `外部事实`;`评审人` 为 `agent:*` 时 `评审方式` 不得为 `人工介入`。

> **评审人**: agent:{id} | {github-handle}
> **评审日期**: {YYYY-MM-DD}
> **评审结论**: {通过 / 有条件通过 / 需返工}
> **评审方式**: {自动判据 / 人工介入 / 外部事实}

---

## 用例总览 (Test Suite Overview)

> 概述本测试集覆盖范围, 列出 P0/P1/P2 用例分布与执行策略.

| 等级 | 数量 | 描述 |
|------|------|------|
| **P0 (核心)** | {n} | 主流程/异常路径, 必须通过 |
| **P1 (重要)** | {n} | 边界条件, 应通过 |
| **P2 (辅助)** | {n} | 兼容性/性能, 建议通过 |
| **合计** | {n} | — |

**执行策略**:
- **冒烟 (smoke)**: 每次构建跑 P0 全集 + 关键 P1
- **全量**: 发布前跑全集

---

## 用例正文 (Test Cases)

### TC-001: {用例名}

**前置条件**:
- [条件 1]
- [条件 2]

**测试步骤**:

| # | 步骤 | 预期 |
|---|------|------|
| 1 | [操作] | [预期结果] |
| 2 | [操作] | [预期结果] |

**关联**: S-1(上游 PRD 场景) / V-1 / KD-1

**等级**: P0 / P1 / P2

---

### TC-002: ...

---

## 冒烟子集 (Smoke Subset)

> **文件名后缀**: `{topic}-smoke.md`. 仅含 P0 + 关键 P1, 用于快速验证.

> 如果不需要单独冒烟子集, 可省略此段; 主文件的 P0 部分即可充当冒烟.

---

## 要点伴生文件 (Key Points Companion)

> **文件名约定**: `{topic}-key-points.md`. **必须**在 Ready/Implemented 状态时存在.
> 用于记录测试集的业务背景 + 核心测试点 (陷阱/已知问题/执行顺序), 帮助执行者快速理解.

### 必填段:

```markdown
# Key Points: {topic}

## 业务背景

[用 2-3 段说明业务上下文, 帮助执行者理解为什么测]

## 核心测试点

[列出 5-10 条关键陷阱/已知问题/特殊处理:
- P0 用例必须执行的前置环境
- 容易踩的坑 (如某接口超时配置)
- 数据准备特殊要求
- 执行顺序依赖]
```

---

## 门禁清单 (Completion Gate)

- [ ] 元信息 7 必填行填写完整 (主题/业务产品/目标平台/来源/生成日期/状态/用例总数); 3 个可选项 (来源 Tech Design / 来源 Plan / 最后更新) 有则填、无则留空
- [ ] 状态枚举值合法 (Draft/Ready/Implemented/Deprecated 四值之一, 不自造状态名)
- [ ] `## 复审 (Review)` 四行(评审人 / 评审日期 / 评审结论 / 评审方式)已由 agent 按 `schema/criteria.json` 判据填写, 状态从 `Draft` 改为 `Ready`; `评审人` 写 `agent:<id>`, 人工复核时改填人名
- [ ] `## 用例总览` 段存在, 含 P0/P1/P2 数量统计
- [ ] 每个 TC 有 完整 5 段 (用例名/前置条件/测试步骤/关联/等级)
- [ ] 关联 PRD 场景 + V-{n} + KD-{n} 编号
- [ ] Ready/Implemented 时伴生 `{topic}-key-points.md` (含 业务背景 + 核心测试点 段)
- [ ] 所有 P0 用例步骤可观察/可验证 (禁止"完成 XX"等模糊描述)

---

## 变更记录 (Change Log)

| 日期 | 变更 |
|------|------|
| {YYYY-MM-DD} | 初始: 测试用例模板 (Layer 4, 2026-08-06 机制建设) |