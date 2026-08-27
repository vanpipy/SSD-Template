# Step 2: Resolving Business Phase

定位或创建业务产品目录，加载已有业务模板。

## 执行逻辑

### 目录已存在

```
test-business/{product}/ 已存在
  → 读取目录下所有文件
  → 提取已有业务规则（YAML 模板中的 tags、preconditions、业务约束）
  → 列出已有用例文件供参考
```

### 目录不存在

```
test-business/{product}/ 不存在
  → 创建目录
  → 写入 README.md
```

README.md 模板：

```markdown
# {product-name}

- Business: {用户描述的业务产品}
- Created: YYYY-MM-DD
- Platform: {首次生成的平台}
- Description: {一句话描述该业务产品的测试侧重点}
```

## 知识库结构

业务目录下按以下结构积累知识：

```
test-business/{product}/
├── README.md                    ← 产品概览
├── _rules.md                    ← 业务规则积累（每次生成后回写）
├── {date}-{topic}/              ← 按需求分目录
│   └── {topic}.yaml             ← 测试用例
└── {date}-{topic}/
    └── {topic}.yaml
```

## 模板读取规则

- 目录下已有的 YAML 文件视为业务测试模板
- `_rules.md` 中积累的业务规则在 Step 4 生成时自动应用
- 每次生成后将新用例写入对应 `{date}-{topic}/` 子目录

## 输出

```
✅ 业务目录就绪：test-business/{product}/
- 状态：{已有 N 个用例文件 / 新建}
- 已有业务规则：{N 条 / 无}

→ 进入 Step 3: Analyzing
```
