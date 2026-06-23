# Legacy(历史参考)

> 本目录保存旧版设计文档,作为历史参考保留,不再用于新工作流。

## 内容

```
legacy/
├── HOW_TO_USE.md          # 旧英文工作流指南(基于 7 个 schema)
├── HOW_TO_USE-cn.md       # 旧中文工作流指南
└── schema/                # 旧 7 个 schema(11 个文件)
    ├── prd.md                          # 英文
    ├── tech-design.md                  # 英文
    ├── tech-design-cn.md               # 中文
    ├── implementation.md               # 英文
    ├── implementation-cn.md            # 中文
    ├── ard.md                          # 英文
    ├── bdd-spec.md                     # 英文
    ├── batch-overview.md               # 英文
    ├── batch-overview-cn.md            # 中文
    ├── collection.md                   # 英文
    └── collection-cn.md                # 中文
```

## 旧 → 新 映射

| 旧 schema | 新归宿 |
|----------|--------|
| `ard.md` | 内联到 `tech_design.md` 的"关键决策"段 (KD-1, KD-2...) |
| `bdd-spec.md` | 内联到 `prd.md`(场景)和 `plan.md`(验证用例) |
| `batch-overview.md` | 删除(多需求聚合是 v2 关注点) |
| `collection.md` | 简化为 `raw/` 文件夹(无模板) → v3 进一步合并到 `prd/{date}/` 子层 |
| `implementation.md` | 改名 `plan.md` |
| `prd.md` / `tech-design.md` | 重新设计 |

## 当前规范

请使用根目录的 4 个文件夹 + 3 个 schema,详见 [HOW_TO_USE-cn.md](../HOW_TO_USE-cn.md)。

## 演化日志

| 版本 | 变化 |
|------|------|
| v1 | 7 个 schema(ard / bdd-spec / collection / batch-overview / implementation / prd / tech-design) |
| v2 | 收敛到 3 个 schema(prd / tech_design / plan) + 独立 `raw/` 文件夹 |
| **v3** | **`raw/` 进一步合并到 `prd/{date}/` 子层(双层结构)**,目录数从 5 减到 4 |
