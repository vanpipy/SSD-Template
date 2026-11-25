# Tech Design(技术设计)

> Layer 2。关键决策、方案对比、数据模型、接口契约、场景映射、时序图。
> **默认代际 v4**(4 子文件),v3 为存量 / 显式 opt-in。

## 文件夹结构(v4 默认)

```text
tech_design/
├── README.md
└── {YYYY-MM-DD}-{topic}/      ← 按功能组织的子文件夹
    ├── README.md              ← 综合描述 + 场景映射 + 实现基线(必填)
    ├── ards.md                ← 架构决策 + 方案对比 + 探索机制 + Gap(必填)
    ├── apis.md                ← 接口契约 + 枚举速查 + 时序图(必填)
    └── data-model.md          ← ER 图 + 数据结构明细(必填)
```

**子文件夹命名**: `{YYYY-MM-DD}-{简短主题}`,日期 `^[0-9]{4}-[0-9]{2}-[0-9]{2}$` + topic `^[a-z0-9]+(-[a-z0-9]+)*$`,小写字母与数字、中划线分隔。

## v4 子文件职责

| 文件 | 职责 | 必填 |
|------|------|------|
| README.md | 摘要 + Context(现状边界 / 硬约束 / 软约束) + **场景映射** + 质量保证 + 关联验证用例(V 预分配) | 是 |
| ards.md | 探索深度声明 + 方向选择与方案对比 + OQ / Spikes / Pivot + KD-{n} 锚点 + 现状 Gap + 风险 | 是 |
| apis.md | 接口契约(全响应变体) + 枚举速查 + 组装规则 + 时序图(SYS-{n} / MOD-{n}) | 是 |
| data-model.md | ER 图(`erDiagram`)+ 数据结构明细 | 是 |

**`data-model.md`**:无数据模型变更时须**显式声明**(写「无数据模型变更」或「不涉及数据模型」),不能留空。

## v3 子文件职责(存量 / 显式 opt-in)

```text
tech_design/
└── {YYYY-MM-DD}-{topic}/
    ├── README.md              ← 入口/索引(必填)
    ├── decisions.md           ← 关键决策(必填)
    ├── data-model.md          ← 数据模型(必填)
    ├── api-contracts.md       ← API 契约(必填)
    ├── scenario-mapping.md    ← 场景映射(必填)
    ├── interactions.md        ← 时序图(视情况)
    └── quality.md             ← 指标 + 降级 + 错误(必填)
```

**`interactions.md` 必填条件**(任一满足):
- 场景映射表行数 ≥ 5
- 涉及外部接口调用
- 涉及 ≥ 2 个内部模块协作
- 包含异步流程、状态机或重试逻辑

> 校验脚本按 `ards.md` / `apis.md` 是否存在识别代际。存量 v3 目录**不迁移**,新建目录按 v4 产出。

## 实现基线

Tech Design 的 `## 实现基线` 段记录设计所基于的代码现状快照。格式固定 6 列:

```markdown
## 实现基线

| 仓库 | 分支 | SHA | 核对日期 | 核对项 | 状态 |
|------|------|-----|----------|--------|------|
| {标识} | {分支} | {短SHA} | {YYYY-MM-DD} | {核对内容} | ✓ |
```

- **仓库**列填 [AGENTS.md](../AGENTS.md) §1.1 登记的标识。脚本据此解析本地路径
- **状态**列 `✓` 一致 / `⚠` 不一致或未登记 / `○` 不适用或跳过
- 0 代码仓项目写单行 `> 不适用: 本项目无关联代码仓` 即可,脚本按 `○` 跳过
- 校验脚本: `scripts/check-repo-baseline.py`

## 证据锚点

现状断言(已实现 / 已修复 / 当前不存在)须带证据锚点,格式 `{仓库标识}@{短SHA}:{路径}#L{行号}`。规则见 [AGENTS.md](../AGENTS.md) §1.7。

## 模板

- v4:见 [schema/tech_design/](../schema/tech_design/) 下的 4 个子模板
- v3:见 `schema/tech_design/v3/` 下的 7 个子模板(存量兼容用)

## 下一步

基于 Ready Tech Design,产出 `plan/{YYYY-MM-DD}-{topic}/{topic}.md`(见 [plan/README.md](../plan/README.md))。
