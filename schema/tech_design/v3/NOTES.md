# Tech Design v3 模板 (存量 / 显式 opt-in)

> **代际**: Legacy — 保留供存量项目与 fork 项目取模板, **不是默认代际**。
> **默认代际**: v4 — 见 [../README.md](../README.md) / [../ards.md](../ards.md) / [../apis.md](../apis.md) / [../data-model.md](../data-model.md)。
>
> **本文件是说明文档, 不是模板**。模板文件是同目录下除 `NOTES.md` 外的 7 个 `.md`。
> **本文件不使用层生命周期状态**: 它不是层产物, 因此不写 `> **状态**:` 行(层状态只有 Draft / Ready / Implemented / Deprecated 四值, 见 [../README.md](../README.md))。

## 本目录是什么

v3 是 Tech Design 的**上一代**结构: 把同一份设计内容摊薄到 6 个必填子文件 + 1 个条件子文件。
v4 收敛为 4 个子文件(README 综合描述 / ards 架构决策 / apis 接口契约 / data-model 数据模型),
把 v3 的 decisions / api-contracts / scenario-mapping / quality / interactions 内容**合并**进 4 个文件。

本目录**保留**这些模板, 因为:

- 存量 TD 目录仍是 v3 结构, `scripts/check-md-schema.sh` 的 **v3 分支保留**(校验存量实例, 不强制迁移);
- fork 项目可能仍在 v3 上维护增量 TD, 需要一份可复制的模板。

## 子文件清单

> 本目录是**可复制的模板集**。复制时把模板文件改名或整体拷入目标 TD 目录即可。
> `README.md` 是**入口 / 索引模板**, 不是说明文档。

| 文件 | 必填 | 关注点 | v4 中的对应落点 |
|------|------|--------|-----------------|
| `README.md` | 是 | 入口 / 索引 + 摘要 + 子文件导航 | [../README.md](../README.md) |
| `decisions.md` | 是 | KD-{n}(Context / Decision / Alternatives / Rationale / Enforced by) | [../ards.md](../ards.md) |
| `data-model.md` | 是 | 实体 / 字段 / 约束 | [../data-model.md](../data-model.md) |
| `api-contracts.md` | 是 | 端点 + 请求 / 响应 + 错误码 | [../apis.md](../apis.md) |
| `scenario-mapping.md` | 是 | PRD 场景 → 实现路径 | [../README.md](../README.md) 的 `## 场景映射` 段 |
| `quality.md` | 是 | 指标 + 降级 + 错误处理 | [../README.md](../README.md) 的 `## 质量保证` 段 |
| `interactions.md` | 条件 | 系统级 (SYS-{n}) + 模块级 (MOD-{n}) 时序图 | [../apis.md](../apis.md) 的 `## 时序交互` 段 |

> `interactions.md` 条件必填规则(任一满足即必填): 场景映射表行数 ≥ 5 / 涉及外部接口调用 /
> 涉及 ≥ 2 个内部模块协作 / 包含异步流程、状态机或重试逻辑。不满足时在 `README.md` 显式声明跳过。

> `NOTES.md` 是**本目录的说明文档**, 不是模板, 不参与 TD 目录结构。

## 何时用 v3 而不是 v4

| 场景 | 建议 |
|------|------|
| 维护**存量** v3 TD 目录 | 用本目录模板, 保持目录结构不变 |
| fork 项目仍在 v3 流程上 | 用本目录模板, 或显式迁移到 v4 |
| **新建** TD 目录 | 用 v4([../README.md](../README.md) 起), 不再新建 v3 |

## 与校验脚本的关系

`scripts/check-md-schema.sh` 按**子文件存在性**判定代际, 与本目录位置无关:

- TD 目录内存在 `ards.md` **或** `apis.md` → 按 **v4** 校验(4 子文件必填);
- 否则 → 按 **v3** 校验(6 子文件必填 + `interactions.md` 条件必填)。

> 本目录位于 `schema/` 下, **不是**一个合法的 TD 实例目录。校验脚本只扫描仓根的 `tech_design/*/`,
> 不会把本目录当作实例校验。

## 变更记录 (Change Log)

| 日期 | 变更 |
|------|------|
| {YYYY-MM-DD} | 初始: v3 模板移入 `schema/tech_design/v3/`, 默认代际改为 v4 |
