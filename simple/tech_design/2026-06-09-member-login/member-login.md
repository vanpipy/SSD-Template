# Tech Design: 会员登录

> **状态**: Ready
> **来源 PRD**: [prd/2026-06-09-processed/member-login.md](../../prd/2026-06-09-processed/member-login.md)
> **创建日期**: 2026-06-09

---

## 关键决策 (Key Decisions)

### KD-1: 会员信息绑定到会话还是订单

**背景 (Context)**: 会员登录后需要将会员信息关联至当前收银操作，使会员价和积分生效。需要决定会员信息维护在前端会话还是绑定到服务端草稿订单。

**决定 (Decision)**: 会员信息同时维护前端会话状态和服务端草稿订单绑定：前端 ViewModel 持有当前会员信息用于 UI 展示；加购商品时同步将会员 ID 传入订单，服务端基于会员 ID 计算会员价。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 仅前端会话持有 | 简单，无需额外接口 | 服务端无法基于会员计算价格，会员价无法生效 |
| 前端 + 服务端订单绑定 | 会员权益由服务端统一计算，保证一致性 | 需要额外的订单绑定接口 |

**理由 (Rationale)**: 会员价由服务端促销引擎计算，前端无法独立完成；草稿订单需要知道会员身份才能返回正确价格，因此必须同步到服务端。

**如何强制 (Enforced by)**: code review 确认加购接口携带会员 ID；测试用例验证会员绑定后价格变化。

---

### KD-2: 扫码识别的超时与取消处理

**背景 (Context)**: PDA 调起摄像头扫描会员码，超时 5s 需提示并允许取消。需要决定超时计时和取消的实现方式。

**决定 (Decision)**: 调起扫码时启动 5s 倒计时协程；扫码成功或超时均取消计时器；超时时 Toast 提示"扫码超时"并关闭扫码界面，返回会员登录页。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 协程 + delay(5000) | Kotlin 原生，与生命周期绑定 | 需在 onDestroy 中取消 |
| CountDownTimer | 有 onTick 回调 | 无需倒计时 UI，略重 |

**理由 (Rationale)**: 扫码超时无需展示倒计时 UI，协程 `delay` 更简洁；绑定 viewLifecycleOwner.lifecycleScope 可自动随页面销毁取消。

**如何强制 (Enforced by)**: 单元测试验证 5s 超时触发；UI 测试验证取消后返回登录页。

---

### KD-3: 已绑定会员时的解绑确认时机

**背景 (Context)**: 当前会话已绑定会员 A 时，发起新的会员登录需要先解绑再绑定新会员。需要决定确认弹窗在何时触发——在查询前还是查询后。

**决定 (Decision)**: 在查询新会员信息后、绑定前展示解绑确认弹窗，弹窗中可展示新会员信息，让店员确认是否切换。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 查询前弹窗确认 | 先确认再查询，减少无效查询 | 弹窗时店员尚不知道新会员是谁 |
| 查询后弹窗确认 | 弹窗可展示新旧会员信息，决策更明确 | 多一次查询请求 |

**理由 (Rationale)**: 收银场景下，店员扫码后能看到"即将切换到 XXX 会员"比盲目确认体验更好；会员查询频率低，多一次请求可接受。

**如何强制 (Enforced by)**: UI 测试验证弹窗在查询成功后出现；已绑定时不先弹窗直接查询的测试用例。

---

## 数据模型 (Data Models)

### MemberSession（前端会话，ViewModel 持有）

| 字段 | 类型 | 说明 |
|------|------|------|
| memberId | string | 会员唯一标识 |
| nickname | string | 会员昵称 |
| phone | string | 手机号（脱敏展示） |
| memberLevel | string? | 会员等级，可空 |

**约束**:
- 会员未登录时为 null
- 解绑后清除为 null
- 不持久化，会话级生命周期

**关联场景**: 场景1-4（所有会员登录/解绑场景）

---

### MemberQueryResult（接口返回）

| 字段 | 类型 | 说明 |
|------|------|------|
| memberId | string | 会员唯一标识 |
| nickname | string | 会员昵称 |
| phone | string | 手机号 |
| memberLevel | string? | 会员等级 |

**关联场景**: 场景1（手机号查询）、场景2（扫码识别）

---

## API 契约 (API Contracts)

### 手机号查询会员

- **端点**: `GET /api/v1/member/query`
- **用途**: 通过手机号查询会员信息
- **来源**: PRD 场景1（手机号查询登录）

**请求**:
```json
{
  "phone": "string, required — 11 位手机号"
}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "memberId": "member_001",
    "nickname": "张三",
    "phone": "138****0000",
    "memberLevel": "gold"
  }
}
```

**响应（失败）**:
```json
{
  "code": 4001,
  "message": "会员不存在"
}
```

**前置条件**: 店员已完成用户登录
**后置条件**: 无状态变更
**副作用**: 无

---

### 会员码查询会员

- **端点**: `POST /api/v1/member/query-by-code`
- **用途**: 通过扫描到的会员码查询会员信息
- **来源**: PRD 场景2（被扫会员码登录）

**请求**:
```json
{
  "memberCode": "string, required — 扫描到的会员码内容"
}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "memberId": "member_001",
    "nickname": "张三",
    "phone": "138****0000",
    "memberLevel": "gold"
  }
}
```

**响应（失败）**:
```json
{
  "code": 4003,
  "message": "会员码无效"
}
```

**前置条件**: 扫码成功，已获取到会员码内容
**后置条件**: 无状态变更
**副作用**: 无

---

## 场景映射 (Scenario Mapping)

| PRD 场景 | 步骤 | 动作 | 组件 | 数据模型 |
|----------|------|------|------|----------|
| 场景1: 手机号查询登录 | 1 | 输入手机号，点击"登录" | MemberLoginActivity | — |
|  | 2 | 调用手机号查询接口 | MemberRepository | MemberQueryResult |
|  | 3a | 查询成功，检查是否已绑定会员 | MemberLoginViewModel | MemberSession |
|  | 3b | 无已绑定，存储 MemberSession，Toast"会员已登录"，返回首页 | MemberLoginViewModel | MemberSession |
|  | 3c | 已有绑定，展示解绑确认弹窗 | MemberLoginActivity | MemberSession |
|  | 4 | 查询失败 code=4001，弹窗"会员不存在，是否立即注册？" | MemberLoginActivity | — |
| 场景2: 被扫会员码登录 | 1 | 选择扫码，调起 PDA 摄像头，启动 5s 超时计时 | MemberLoginActivity | — |
|  | 2 | 扫码成功，调用会员码查询接口 | MemberRepository | MemberQueryResult |
|  | 3 | 查询成功，存储 MemberSession，Toast"会员已登录"，返回首页 | MemberLoginViewModel | MemberSession |
|  | 4a | 超时 5s，Toast"扫码超时"，返回登录页 | MemberLoginActivity | — |
|  | 4b | code=4003，Toast"会员码无效"，停留登录页 | MemberLoginActivity | — |
| 场景3: 已绑定时再次登录 | 1 | 查询新会员成功后，检测到已绑定 MemberSession | MemberLoginViewModel | MemberSession |
|  | 2 | 展示弹窗"已绑定会员，是否解绑并更换？" | MemberLoginActivity | — |
|  | 3 | 确认：清除旧 MemberSession，绑定新会员，返回首页 | MemberLoginViewModel | MemberSession |
|  | 4 | 取消：终止，不做任何变更 | MemberLoginActivity | — |
| 场景4: 会员解绑 | 1 | 首页点击"切换会员"，弹窗确认 | HomeActivity | — |
|  | 2 | 确认后清除 MemberSession，会员栏恢复"未登录" | MemberLoginViewModel | MemberSession |
|  | 3 | 跳转会员登录页 | HomeActivity | — |

---

## 指标 (Metrics)

| 维度 | 指标 | 目标 | 测量方法 |
|------|------|------|----------|
| 性能 | 手机号查询接口延迟 P99 | < 2000ms | APM 监控 |
| 性能 | 会员码查询接口延迟 P99 | < 2000ms | APM 监控 |
| 质量 | 扫码识别成功率 | ≥ 95% | 客户端日志统计 |

---

## 降级策略 (Fallback Strategy)

### 降级场景: 会员查询接口不可用

- **触发条件**: 接口返回 5xx 或超时（3s）
- **降级行为**: Toast 提示"会员服务暂不可用，请稍后重试"，停留登录页
- **业务影响**: 店员可选择不绑定会员直接结算（PRD 明确：不绑定也可正常结算）
- **恢复条件**: 服务恢复后手动重试

---

## 错误处理 (Error Handling)

| 错误码 | 含义 | HTTP 状态 | 处理 |
|--------|------|-----------|------|
| 4001 | 会员不存在 | 404 | 弹窗"会员不存在，是否立即注册？" |
| 4003 | 会员码无效 | 400 | Toast"会员码无效"，停留登录页 |
| 5001 | 服务不可用 | 5xx | Toast"会员服务暂不可用" |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-09 | 初始 |
