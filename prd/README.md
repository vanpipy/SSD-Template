# PRD(产品需求)

> **Layer 1**。收敛后的产品需求文档。产出路径为 `prd/{YYYY-MM-DD}/{topic}.md`。
> `prd/{YYYY-MM-DD}/` 同时可暂存原始素材(只读),素材区**不是**独立 Layer。

## 架构层(共 3 层)

| Layer | 位置 | 状态 |
|-------|------|------|
| Layer 1 | `prd/{YYYY-MM-DD}/{topic}.md` | Ready → Implemented |
| Layer 2 | `tech_design/{YYYY-MM-DD}-{topic}/` | Ready → Implemented |
| Layer 3 | `plan/{YYYY-MM-DD}-{topic}/{topic}.md` | Ready → Implemented |

> `prd/{YYYY-MM-DD}/` 是 Layer 1 的**素材存放区**,**不是**独立 Layer。
> Layer 0(可选素材区)在 [material/](../material/README.md),启用与否由项目决定。

## 文件夹结构

```text
prd/
├── README.md
└── {YYYY-MM-DD}/               ← 日期分桶(素材 + PRD 同目录)
    ├── {source-1}.md           ← 原始素材(只读,非 Layer 制品)
    ├── {source-2}.md
    └── {topic}.md              ← Layer 1: PRD(Step 1 产出)
```

**目录命名**: `{YYYY-MM-DD}`,必须是规范日期。
**PRD 命名**: `{简短主题}.md`,小写连字符(如 `login` / `checkout-flow`)。一个日期可有多个 PRD(1:N 关系)。
**素材命名**: `{来源描述}.md`,可多个,不强制 topic 格式。

> **目录内两类文件共存**:`{topic}.md` 是 Layer 1 制品;其余为暂存素材。`scripts/check-naming.sh` 对后者只报 `⚠` 提示,不报错。素材长期暂存时,建议迁到 [material/](../material/README.md)。

## 转换关系(素材 → Layer 1)

- **1:1**: 一份原始文档对应一个 PRD
- **1:N**: 一份原始文档(如 `history-apis.md`)拆成多个 PRD
- **N:1**: 多份原始文档合成一个 PRD
- **N:N**: 更复杂的 1→N→M 组合

## 放什么(Layer 1 PRD)

- 产品的「为什么」「目标」「场景」「不在范围」
- 元信息:状态 / 负责人 / 创建日期 / 最后更新
- 复审三问:still_matters / should_keep / can_delete(防止 feature rot)
- 状态机: Draft → Ready → Implemented | Deprecated

> 门禁清单 5 项:为什么 / 目标 / 场景 / 不在范围内 / 复审。权威定义见 [schema/prd.md](../schema/prd.md)。

## 模板

见 [schema/prd.md](../schema/prd.md)

## 可选关联层

| 层 | 位置 | 用途 |
|----|------|------|
| PRD 台账 | `material/{YYYY-MM-DD}/PRDS.md` | 11 列台账,追踪素材到 PRD 的流转。模板见 [schema/prd-ledger.md](../schema/prd-ledger.md) |
| PRD 关联矩阵 | 根 [README.md](../README.md) 的「PRD关联矩阵」章节 | 8 类 PRD 关系边。模板见 [schema/prd-matrix.md](../schema/prd-matrix.md) |

## 下一步

基于 Ready PRD,产出 `tech_design/{YYYY-MM-DD}-{topic}/`(多文件结构,见 [tech_design/README.md](../tech_design/README.md))。
