# Tech Design: 用户登录

> **状态**: Ready
> **来源 PRD**: [prd/2026-06-09-processed/user-login.md](../../prd/2026-06-09-processed/user-login.md)
> **创建日期**: 2026-06-09

---

## 关键决策 (Key Decisions)

### KD-1: "记住账号密码"的存储与有效期管理

**背景 (Context)**: 店员勾选"记住账号密码"后，下次打开 APP 自动填充账号和密码，有效期默认 7 天；过期后需清除。需要决定凭据存储方式和过期清除时机。

**决定 (Decision)**: 使用 EncryptedSharedPreferences 存储账号、密码（加密）和记录时间戳；每次进入登录页时检查时间戳，超过 7 天则清除并不填充。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| EncryptedSharedPreferences + 时间戳 | 加密安全，轻量 | 时间戳依赖本地时钟，可被篡改 |
| Android Keystore + 带过期的 Token | 系统级密钥保护 | 复杂度高，过度设计 |
| 明文 SharedPreferences | 最简单 | 明文存储密码有安全风险 |

**理由 (Rationale)**: 收银 PDA 为受控设备，EncryptedSharedPreferences 提供足够的安全保护；本地时钟篡改风险在受控设备场景下可接受；实现简单，维护成本低。

**如何强制 (Enforced by)**: code review 禁止明文存储密码；单元测试验证 7 天过期清除逻辑。

---

### KD-2: 登录失败锁定的实现方式

**背景 (Context)**: 连续登录失败 5 次后需锁定登录按钮 30s，防止暴力破解。需要决定失败计数和锁定状态维护在前端还是后端。

**决定 (Decision)**: 前端本地维护失败计数和锁定时间戳（存于内存，不持久化）；锁定期间按钮置灰，展示倒计时；后端同样可独立实施账号级锁定策略（两者互不依赖）。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 前端本地计数 | 即时响应，无网络依赖 | APP 重启后计数重置，可绕过 |
| 后端计数 + 返回锁定状态 | 无法绕过，跨设备生效 | 增加接口复杂度 |
| 前后端双重 | 最安全 | 实现复杂 |

**理由 (Rationale)**: PRD 明确"防止暴力破解"，收银 PDA 为受控设备，重启绕过风险可接受；前端本地实现可即时锁定无需等待网络响应，用户体验更好；后端可独立加账号锁定，不需前端感知。

**如何强制 (Enforced by)**: 单元测试验证连续 5 次失败后锁定逻辑和 30s 倒计时解锁。

---

### KD-3: 登录态 Token 管理

**背景 (Context)**: 登录成功后需要维护登录态（Token），供后续收银接口使用。需要决定 Token 存储位置和刷新策略。

**决定 (Decision)**: 登录成功后将 Token（AccessToken + 过期时间）存储于 EncryptedSharedPreferences；Token 过期时在下次 API 请求拦截器中自动跳转登录页，不做静默刷新。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 存 EncryptedSharedPreferences，过期跳登录 | 简单可控 | 过期时打断收银操作 |
| RefreshToken 静默续期 | 用户无感知 | 增加复杂度，收银场景使用时长可控 |

**理由 (Rationale)**: 收银班次通常在 8-12 小时内，Token 有效期设置足够长（如 12h）可避免班次中过期；PRD 无静默续期需求，保持简单。

**如何强制 (Enforced by)**: HTTP 拦截器统一处理 401 响应，跳转登录页；code review 确认无直接 Token 操作绕过拦截器的代码。

---

## 数据模型 (Data Models)

### SavedCredentials（本地持久化）

| 字段 | 类型 | 说明 |
|------|------|------|
| username | string | 保存的账号（11 位手机号） |
| password | string | 加密存储的密码 |
| savedAt | long | 保存时间戳（ms），用于 7 天过期检查 |
| rememberMe | boolean | 是否勾选了记住密码 |

**约束**:
- `rememberMe=true` 时其余字段不可为空
- `rememberMe=false` 时清除所有字段
- 存储于 EncryptedSharedPreferences

**关联场景**: 场景2（记住密码自动填充）

---

### LoginSession（内存 + 本地持久化）

| 字段 | 类型 | 说明 |
|------|------|------|
| accessToken | string | 登录令牌 |
| expireAt | long | 过期时间戳（ms） |
| userId | string | 用户 ID |
| username | string | 账号 |
| role | string | 角色：CASHIER / MANAGER |
| storeId | string | 所属门店 ID |

**约束**:
- 所有字段不可为空
- Token 过期后清除，跳转登录页

**关联场景**: 场景1（正常登录后存储）

---

### LoginAttemptState（内存，不持久化）

| 字段 | 类型 | 说明 |
|------|------|------|
| failCount | int | 当前连续失败次数，初始 0 |
| lockedUntil | long? | 锁定解除时间戳（ms），null 表示未锁定 |

**约束**:
- APP 重启后重置为初始值
- `failCount >= 5` 时设置 `lockedUntil = now + 30000ms`

**关联场景**: 场景3（账号或密码错误，连续失败锁定）

---

## API 契约 (API Contracts)

### 账号密码登录

- **端点**: `POST /api/v1/auth/login`
- **用途**: 店员账号密码身份验证
- **来源**: PRD 场景1（正常登录）、场景3（登录失败）

**请求**:
```json
{
  "username": "string, required — 11 位手机号",
  "password": "string, required — 密码（MD5 或明文，由接口约定）",
  "deviceId": "string, required — 设备唯一标识"
}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "accessToken": "eyJ...",
    "expireAt": 1718000000000,
    "userId": "user_001",
    "username": "13800138000",
    "role": "CASHIER",
    "storeId": "store_001"
  }
}
```

**响应（失败）**:
```json
{
  "code": 2001,
  "message": "账号不存在"
}
```

**前置条件**: 设备已完成门店绑定和版本更新检测
**后置条件**: 服务端记录登录时间和设备信息
**副作用**: 无

---

## 场景映射 (Scenario Mapping)

| PRD 场景 | 步骤 | 动作 | 组件 | 数据模型 |
|----------|------|------|------|----------|
| 场景1: 正常登录 | 1 | 输入账号密码，点击"登录" | LoginActivity | — |
|  | 2 | 前端非空校验通过，调用登录接口 | AuthRepository | — |
|  | 3 | 接口返回成功，存储 LoginSession | AuthManager | LoginSession |
|  | 4 | 跳转收银主页 | MainActivity | — |
| 场景2: 记住密码自动填充 | 1 | 进入登录页，读取 SavedCredentials | LoginActivity | SavedCredentials |
|  | 2 | 检查 savedAt，未超 7 天则自动填充账号密码 | LoginActivity | SavedCredentials |
|  | 3 | 勾选框默认勾选，店员点击"登录" | LoginActivity | — |
| 场景3: 账号或密码错误 | 1 | 登录接口返回失败 | AuthRepository | LoginAttemptState |
|  | 2 | failCount+1，Toast 展示错误原因 | LoginActivity | LoginAttemptState |
|  | 3 | failCount>=5，锁定按钮 30s，展示倒计时 | LoginActivity | LoginAttemptState |
| 场景4: 账号或密码为空 | 1 | 点击"登录"，前端非空校验失败 | LoginActivity | — |
|  | 2 | Toast 提示"请输入账号"或"请输入密码"，不发起请求 | LoginActivity | — |

---

## 指标 (Metrics)

| 维度 | 指标 | 目标 | 测量方法 |
|------|------|------|----------|
| 性能 | 登录接口延迟 P99 | < 3000ms | APM 监控 |
| 性能 | 登录页自动填充耗时 | < 100ms | 本地性能日志 |
| 质量 | 登录成功率（账号密码正确时） | ≥ 99.9% | 接口监控 |

---

## 降级策略 (Fallback Strategy)

### 降级场景: 登录接口不可用

- **触发条件**: 登录接口返回 5xx 或超时（5s）
- **降级行为**: Toast 提示"网络异常，请检查网络后重试"，停留登录页，不计入失败次数
- **业务影响**: 店员无法登录，阻断收银操作
- **恢复条件**: 网络恢复后手动重试

---

## 错误处理 (Error Handling)

| 错误码 | 含义 | HTTP 状态 | 处理 |
|--------|------|-----------|------|
| 2001 | 账号不存在 | 400 | Toast 提示"账号不存在"，failCount+1 |
| 2002 | 密码错误 | 400 | Toast 提示"密码错误"，failCount+1 |
| 2003 | 账号已停用 | 400 | Toast 提示"账号已停用，请联系管理员"，不计入 failCount |
| 5001 | 服务不可用 | 5xx | Toast 提示"网络异常"，不计入 failCount |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-09 | 初始 |
