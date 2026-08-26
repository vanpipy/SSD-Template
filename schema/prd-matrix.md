# PRD 关联矩阵模板 (PRD Relationship Matrix)

> **本模板是可选层**: 仅当项目存在多 PRD 协作/继承/替代关系时使用. SSD-Template 默认不启用 (单 PRD 项目不需要).

---

## 用途

当项目积累多个 PRD 之后, PRD 之间可能存在 8 类关系: supersede / inherit / depend / shared / conflict / relate / split-from / merge-into. 用本矩阵追踪这些关系, 避免下游引用过期 PRD.

**位置**: 仓库根 `README.md` 「PRD关联矩阵」章节 (或独立 `prd-matrix.md`)

---

## 关系类型枚举 (8 种)

| 关系 | 含义 | 示例 |
|------|------|------|
| **supersede** | A 替代 B (B 应标记 Deprecated) | `staff-login-v2 → staff-login-v1` |
| **inherit** | A 继承自 B (A 复用 B 的部分场景) | `order-flow → user-auth` |
| **depend** | A 依赖 B (B 不完成 A 不能完成) | `checkout-flow → cart` |
| **shared** | A 与 B 共享某子模块 | `mobile-cart ∩ desktop-cart` |
| **conflict** | A 与 B 互斥 (不能同时启用) | `payment-method-A ↔ payment-method-B` |
| **relate** | A 与 B 相关 (无强依赖, 仅供参考) | `notifications ↔ user-profile` |
| **split-from** | A 从 B 拆分出来 (B 太大被拆分) | `user-profile-sso + user-profile-avatar ← user-profile` |
| **merge-into** | A 合并入 B (A 太小被合并) | `user-profile-avatar → user-profile-sso` |

---

## 关系边表模板

```markdown
### 关系边表

| # | 节点 A | 关系 | 节点 B | 备注 |
|---|--------|------|--------|------|
| 1 | PRD-20260819-01 | inherit | PRD-20260805-03 | 复用了 SSO 设计 |
| 2 | PRD-20260820-04 | supersede | PRD-20260810-01 | 新版替代旧版 |
| 3 | PRD-20260821-02 | depend | PRD-20260819-05 | 依赖订单模块 |
```

---

## 关系边校验 (用于自动化)

| 校验项 | 说明 |
|--------|------|
| 节点标识存在性 | 节点 A/B 必须在 PRDS.md 台账登记或 prd/{date}/{topic}.md 存在 |
| 关系类型枚举 | 关系值必须 ∈ {supersede, inherit, depend, shared, conflict, relate, split-from, merge-into} |
| supersede 一致性 | 关系=supersede 时, 被替代者 (节点 B) 状态必须为 Deprecated |
| 双向一致性 | 已 Deprecated 的 PRD 必须有 supersede 边指向它 (反向) |

---

## 何时更新

| 触发 | 动作 |
|------|------|
| 新 PRD 收敛到 Ready | 评估与现有 PRD 的关系, 登记边 |
| PRD 状态变 Deprecated | 确认有 supersede 边指向替代者 |
| PRD 大修改 (场景/范围变更) | 重审关系边, 删除/新增 |
| 跨周期复审 (季度) | 全量巡检, 清理过期边 |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| {YYYY-MM-DD} | 初始: PRD 关联矩阵模板 (8 类关系, 默认不启用) |