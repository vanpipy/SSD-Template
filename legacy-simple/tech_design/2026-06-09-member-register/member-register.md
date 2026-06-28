# Tech Design: 会员注册

> **状态**: Ready
> **来源 PRD**: [prd/2026-06-09-processed/member-register.md](../../prd/2026-06-09-processed/member-register.md)
> **创建日期**: 2026-06-09

---

## 关键决策 (Key Decisions)

### KD-1: 注册成功后自动绑定会话的实现方式

**背景 (Context)**: 注册成功后需要自动绑定会员至当前收银会话，无需再次调用会员登录流程。注册接口返回的会员信息需要直接写入 MemberSession。

**决定 (Decision)**: 注册接口成功后直接返回完整会员信息，前端将返回的会员信息写入 MemberSession（与会员登录流程共用同一 ViewModel 方法），无需再次调用查询接口。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 注册后直接写入 MemberSession | 零额外请求，最快 | 注册接口需返回完整会员信息 |
| 注册后再调查询接口获取会员信息 | 逻辑复用 | 多一次网络请求，延迟增加 |

**理由 (Rationale)**: PRD 要求"系统在 2s 内完成注册并自动绑定"，减少网络请求数是关键；注册接口返回会员信息是标准做法。

**如何强制 (Enforced by)**: code review 确认注册接口返回完整 MemberInfo；单元测试验证注册成功后 MemberSession 自动更新。

---

### KD-2: 已有绑定会员时注册的确认弹窗时机

**背景 (Context)**: 注册时若已绑定会员 A，需弹窗确认解绑后再注册新会员。与会员登录的 KD-3 场景类似，但注册时还无新会员信息可展示。

**决定 (Decision)**: 在前端检测到已有 MemberSession 时，点击"注册"按钮前先展示解绑确认弹窗；用户确认后再调用注册接口。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 注册前弹窗 | 减少不必要的注册请求 | 弹窗时无法展示新会员信息（因为还未注册） |
| 注册后弹窗 | 能展示新会员信息 | 注册已完成才弹窗，用户取消后需要额外处理已注册账号 |

**理由 (Rationale)**: 注册不可逆，用户确认解绑后才发起注册，避免误操作后产生孤立账号；注册场景下弹窗时不需要展示新会员信息，前置确认更合理。

**如何强制 (Enforced by)**: UI 测试验证已绑定时注册前展示弹窗；未绑定时直接注册。

---

## 数据模型 (Data Models)

### MemberRegisterRequest

| 字段 | 类型 | 说明 |
|------|------|------|
| phone | string | 11 位手机号 |
| storeId | string | 注册所在门店 ID |

**约束**:
- `phone` 不可为空，必须为 11 位数字

**关联场景**: 场景1（主动注册）、场景2（引导注册）、场景3（已有绑定会员时注册）

---

### MemberInfo（接口返回 + 复用 MemberSession）

与 `member-login` Tech Design 中的 `MemberQueryResult` 相同结构，注册接口直接返回此格式以便写入 MemberSession。

| 字段 | 类型 | 说明 |
|------|------|------|
| memberId | string | 会员唯一标识 |
| nickname | string | 系统自动生成的昵称 |
| phone | string | 手机号（脱敏） |
| memberLevel | string? | 初始等级 |

**关联场景**: 注册成功后直接写入 MemberSession

---

## API 契约 (API Contracts)

### 注册会员

- **端点**: `POST /api/v1/member/register`
- **用途**: 通过手机号注册新会员，成功后返回会员信息
- **来源**: PRD 场景1（主动注册）、场景2（引导注册）、场景3（已有绑定时注册）

**请求**:
```json
{
  "phone": "string, required — 11 位手机号",
  "storeId": "string, required — 注册门店 ID"
}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "memberId": "member_002",
    "nickname": "会员002",
    "phone": "138****0001",
    "memberLevel": "normal"
  }
}
```

**响应（失败）**:
```json
{
  "code": 4002,
  "message": "该手机号已注册"
}
```

**前置条件**: 店员已完成用户登录，可选有已绑定会员（注册前已完成解绑确认）
**后置条件**: 系统创建新会员账号
**副作用**: 无（积分/权益初始化由会员中心异步处理，不影响注册响应）

---

## 场景映射 (Scenario Mapping)

| PRD 场景 | 步骤 | 动作 | 组件 | 数据模型 |
|----------|------|------|------|----------|
| 场景1: 主动注册 | 1 | 点击"去注册会员"，进入注册页（空输入框） | MemberRegisterActivity | — |
|  | 2 | 输入手机号，点击"注册" | MemberRegisterActivity | — |
|  | 3 | 检测 MemberSession 无已绑定，直接调注册接口 | MemberRegisterViewModel | MemberRegisterRequest |
|  | 4a | 注册成功，写入 MemberSession，Toast"注册成功，会员已登录"，返回首页 | MemberRegisterViewModel | MemberInfo |
|  | 4b | code=4002，Toast"该手机号已注册，请直接登录"，停留注册页 | MemberRegisterActivity | — |
| 场景2: 引导注册 | 1 | 从"会员不存在"弹窗点击"确认注册"，跳转注册页，手机号预填 | MemberLoginActivity → MemberRegisterActivity | — |
|  | 2 | 店员确认/修改手机号，点击"注册" | MemberRegisterActivity | — |
|  | 3 | 调注册接口，成功后写入 MemberSession，返回首页 | MemberRegisterViewModel | MemberInfo |
| 场景3: 已有绑定会员时注册 | 1 | 点击"注册"，检测 MemberSession 已有绑定 | MemberRegisterViewModel | MemberSession |
|  | 2 | 展示弹窗"已绑定会员，是否解绑并更换？" | MemberRegisterActivity | — |
|  | 3 | 确认：清除旧 MemberSession，调注册接口，成功后写入新 MemberSession | MemberRegisterViewModel | MemberInfo |
|  | 4 | 取消：停留注册页，不做变更 | MemberRegisterActivity | — |

---

## 指标 (Metrics)

| 维度 | 指标 | 目标 | 测量方法 |
|------|------|------|----------|
| 性能 | 注册接口延迟 P99 | < 2000ms | APM 监控 |
| 质量 | 注册成功率（手机号未注册时） | ≥ 99% | 接口监控 |

---

## 降级策略 (Fallback Strategy)

### 降级场景: 注册接口不可用

- **触发条件**: 接口返回 5xx 或超时（3s）
- **降级行为**: Toast 提示"注册失败，请稍后重试"，停留注册页，MemberSession 不变
- **业务影响**: 店员可选择跳过会员注册直接结算（PRD 明确：会员登录不是强制步骤）
- **恢复条件**: 服务恢复后手动重试

---

## 错误处理 (Error Handling)

| 错误码 | 含义 | HTTP 状态 | 处理 |
|--------|------|-----------|------|
| 4002 | 手机号已注册 | 400 | Toast"该手机号已注册，请直接登录"，停留注册页 |
| 5001 | 服务不可用 | 5xx | Toast"注册失败，请稍后重试" |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-09 | 初始 |
