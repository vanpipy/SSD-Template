# Step 6: Writing Phase

输出 Markdown 用例文档（模板 `schema/test_case.md`），回写知识库，再生成索引，跑校验，输出统计摘要。

## 输出路径

```
test_cases/
├── _index.md                     ← 全局索引（scripts/sync-test-index.sh 自动生成，勿手改）
├── 2026-07-22/
│   ├── login.md                  ← 主用例文档
│   ├── login-key-points.md       ← 测试要点（伴生）
│   └── payment.md
└── 2026-07-23/
    └── member-search.md
```

- `{YYYY-MM-DD}` 为生成日期（如 `2026-07-22`），可与来源 PRD 批次日期不同
- `{topic}` 从 PRD 文件名或用户指定提取
- 同一天多个需求则同目录下多组文件
- 冒烟范围（`--smoke`）输出 `{topic}-smoke.md`

## Markdown 结构（权威模板 schema/test_case.md）

主/冒烟文档 = 元信息表 + 用例总览 + S-NNN 场景段：

- 元信息 7 必填行：主题 / 业务产品 / 目标平台 / 来源 / 生成日期 / 状态 / 用例总数
- 来源方向 = 上游 **PRD + Tech Design**：优先 `prd/{date}/{topic}.md` 与 `tech_design/{date}-{topic}/`（反引号 + 仓库根路径，check-traceability T9 校验存在性）
- 已建立配对的 Plan 记入可选 `Plan` 行（本文档作为其参考比照对象）
- 状态枚举与三件套统一：**Draft / Ready / Implemented / Deprecated**（新生成 = Draft）

## 索引维护（强制，机器再生成）

写入用例后，**必须**运行：

```bash
./scripts/sync-test-index.sh
```

脚本扫描全部主/冒烟文档元信息，在 `test_cases/_index.md` 标记块内再生成索引表（幂等）。**禁止手工增删索引行**——v2.0 的手工追加模式已废弃（曾导致幽灵批次与死链）。

## 收尾校验（强制）

```bash
./scripts/check-md-schema.sh test_cases/{date}/{topic}.md   # 元信息 + 状态枚举 + 用例总览 + 伴生
./scripts/check-naming.sh                                    # 命名规范
```

两个脚本对该文件返回 0 方可交付；随后按 Step 5 评审结论把状态从 Draft 升 Ready（评审通过 + 要点伴生就位）。

## 测试要点沉淀

与用例同级目录输出 `{topic}-key-points.md`（状态升 Ready 前必须就位），记录本次测试的核心要点：

```markdown
# {topic} 测试要点

## 业务背景
{从 PRD 提取的一句话业务背景}

## 核心测试点
- 【P0】{关键功能点 1}
- 【P0】{关键功能点 2}
- 【P1】{重要功能点}

## 前后端连接要点
- 前端传参：{关键参数及格式}
- 后端契约：{接口路径 + 关键返回码}
- 异常处理：{前端兜底策略}

## 平台特异要点
- {platform}: {平台特有注意事项}

## 风险与假设
- {信息缺口/假设/待确认项}

## 优先级分布
| P0 | P1 | P2 | P3 |
|----|----|----|----|  
| N | N | N | N |
```

**要点来源**：
- 业务背景 → PRD Why/Goal
- 核心测试点 → Step 3 功能点清单
- 前后端连接 → Step 4 连接点检查
- 平台特异 → Step 4 平台注入
- 风险假设 → Step 3 信息缺口

## 知识库回写（test-business）

写入用例后，将新发现的业务规则追加到 `test-business/{product}/_rules.md`：

```markdown
## {date} - {topic}

### 新发现规则
- {规则描述}（来源：{PRD/TD 段落}）

### 边界条件
- {边界描述}

### 平台特异约束
- {platform}: {约束描述}
```

**回写原则**：只追加，不删除已有内容。

## 统计摘要

写入完成后输出：

```
✅ 用例生成完成
📊 统计：
- 业务产品：{product}
- 目标平台：{platform}
- 总场景段（S-NNN）：N
- 总用例数：N
- P0: N | P1: N | P2: N | P3: N
- 平台特异用例：N
- 评审轮次：N

📁 输出：test_cases/{date}/{topic}.md（状态 Draft）
📝 测试要点：test_cases/{date}/{topic}-key-points.md
📝 知识库回写：test-business/{product}/_rules.md（+N 条规则）
🔄 索引：scripts/sync-test-index.sh 已再生成
```

## 版本管理

- 首次生成：`{topic}.md`（状态: Draft）
- Step 5 评审通过 + 要点就位：状态更新为 Ready（可带说明后缀，如「Ready（2 轮 4 角色评审）」）
- 执行验收通过：人工回写 Implemented（本 skill 不负责）
- 上游 PRD/TD Deprecated：级联 Deprecated；上游复审变更：回退 Draft 并备注「需重审」
