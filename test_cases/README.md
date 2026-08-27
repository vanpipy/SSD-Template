# Test Cases(测试用例)

> **Layer 4**(可选质量层)— 黑盒测试用例,来源 = `PRD + Tech Design`,作为 Plan V 用例的参考比照对象。
>
> 本层**默认不启用**——仅当项目需要独立测试用例管理时创建 `test_cases/` 目录并按本指南产出文件。
> 目录创建后,`scripts/check-md-schema.sh` 自动启用 Test Case 校验(元信息 7 必填行 + 状态枚举 + 用例总览 + 要点伴生)。

## 文件夹结构

```text
test_cases/
├── README.md                   ← 本文件(手动维护的层概览)
├── _index.md                   ← 由 scripts/sync-test-index.sh 自动生成(勿手改)
└── {YYYY-MM-DD}/               ← 按生成日期分桶(可与来源 PRD 批次日期不同)
    ├── {topic}.md              ← 主用例集
    ├── {topic}-smoke.md        ← 冒烟子集(仅 P0 + 关键 P1;可选)
    └── {topic}-key-points.md   ← 要点伴生(Ready/Implemented 状态必填)
```

**目录命名**: `{YYYY-MM-DD}` 为**生成日期**(可与来源 PRD 批次日期不同)
**文件命名**: `{简短主题}.md` / `{topic}-smoke.md` / `{topic}-key-points.md`

## 文件职责

| 文件 | 职责 | 必填 |
|------|------|------|
| `README.md` | 层概览(本文件)+ 结构 + 命名约定 + 状态机 | 是 |
| `_index.md` | 机器再生成的用例文件清单(由 `sync-test-index.sh` 维护) | 自动 |
| `{topic}.md` | 主用例集(按优先级 P0/P1/P2 分层) | 是 |
| `{topic}-smoke.md` | 冒烟子集(仅 P0 主路径) | 可选 |
| `{topic}-key-points.md` | 业务背景 + 核心测试点 + 已知陷阱(Ready 起必填) | Ready/Implemented 时 |

## 放什么(Layer 4 Test Cases)

- 黑盒用例:每个 TC 含 **前置条件 / 测试步骤 / 预期 / 关联 / 等级**
- **PRD 每个 But 分支 ≥1 条用例**(先 `grep -c '\*\*But\*\*'` 数出)
- **环境边界 Checklist**:网络 / 系统声道 / 生命周期 / 权限角色 / 数据边界——逐维对照
- **默认值用例**:PRD Goal 显式默认值必须有初始状态验证
- **OQ 收敛用例**:TD `exploration.md`(v3) / `ards.md`(v4)「探索记录」OQ 收敛方式点名 TC 的必须生成

## 状态机(独立生命周期)

| 状态 | 含义 | 触发 |
|------|------|------|
| **Draft** | 初稿,内容可能不全 | `/to-test-cases` Step 5 完成 |
| **Ready** | 内容完整,评审通过 | Draft + `{topic}-key-points.md` 伴生就位 |
| **Implemented** | 已实际执行过 | 冒烟/全量通过 + 人工回写(由 `/sync-status test-done` 编排) |
| **Deprecated** | 已废弃,不再维护 | 上游 PRD/TD Deprecated 级联(由 `/sync-status deprecate` 编排) |

> Test Cases **独立于三件套生命周期**——不与 PRD/TD/Plan 联动,只响应上游 Deprecated / 复审回退级联。

## 与 `_index.md` 的关系

| 文件 | 类型 | 来源 | 何时改 |
|------|------|------|--------|
| `README.md` | **手动维护**的层概览 | 人工编辑 | 命名约定 / 状态机变更时 |
| `_index.md` | **自动生成**的文件清单 | `scripts/sync-test-index.sh` 扫描元信息表 | 任何用例文档元信息变化时跑一次 |

> 标记块 `<!-- test-index:begin --> ... <!-- test-index:end -->` 内的内容由 `sync-test-index.sh` 覆盖生成,**勿手改**。

## 模板

见 [schema/test_case.md](../schema/test_case.md)

## 下一步

- **启用本层**:运行 `/to-test-cases <prd-path> <tech-design-dir>` 生成 Draft
- **维护索引**:用例文档元信息变化后,跑 `bash scripts/sync-test-index.sh`
- **校验门禁**:Ready 前跑 `/validate-spec`(自动启用 Test Case 校验)
- **生命周期编排**:`/sync-status implement / deprecate / rollback / test-done`
- **Plan 引用**:Plan 元信息「参考 Test Cases」行填入用例路径(check-traceability T11 校验)

## 快速命令

```bash
# 生成用例(PRD + TD 都需 Ready)
bash scripts/sync-test-index.sh           # 再生成 _index.md
bash scripts/sync-test-index.sh --check   # 仅校验不写文件
bash scripts/check-md-schema.sh test_cases/  # 单独跑 Test Case 校验
```