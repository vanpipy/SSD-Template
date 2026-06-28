# Tech Design: 门店注册

> **状态**: Ready
> **来源 PRD**: [prd/2026-06-09-processed/store-register.md](../../prd/2026-06-09-processed/store-register.md)
> **创建日期**: 2026-06-09

---

## 关键决策 (Key Decisions)

### KD-1: 门店绑定信息的本地持久化方式

**背景 (Context)**: 绑定成功的门店信息需要持久化至本地，下次冷启动跳过注册流程。需要决定存储位置及加密策略。

**决定 (Decision)**: 使用加密 SharedPreferences（EncryptedSharedPreferences）持久化门店绑定信息，App 卸载时自动清除，无需额外管理。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| EncryptedSharedPreferences | 系统级加密，简单可靠 | 卸载即清除（符合需求） |
| 本地 SQLite / Room | 结构化，可扩展 | 门店绑定信息字段少，过度设计 |
| 明文 SharedPreferences | 最简单 | 明文存储敏感门店信息有安全风险 |

**理由 (Rationale)**: 门店绑定信息属于配置类数据，字段少，EncryptedSharedPreferences 安全且维护成本低；卸载清除行为也是预期的（新设备重新安装需重新注册）。

**如何强制 (Enforced by)**: code review 禁止使用明文 SharedPreferences 存储门店信息；单元测试验证冷启动读取逻辑。

---

### KD-2: 注册码校验时机

**背景 (Context)**: 店员输入注册码后点击"查询门店"，需要决定是前端本地格式校验后再请求接口，还是直接请求接口由后端校验。

**决定 (Decision)**: 前端仅做非空校验，不做格式正则校验；点击后直接请求后端接口，由后端返回具体错误（无效/已过期/已被绑定）。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 前端格式校验 + 后端校验 | 减少无效请求 | 注册码格式可能变更，前端需同步更新 |
| 仅后端校验 | 逻辑集中，前端无需维护校验规则 | 多一次网络请求 |

**理由 (Rationale)**: 注册码由后台生成，格式规则可能变化；前端强绑定格式会增加维护成本，且注册场景频率极低，多一次网络请求无性能影响。

**如何强制 (Enforced by)**: 约定前端注册码输入框仅做非空校验；code review 检查。

---

## 数据模型 (Data Models)

### StoreBinding（本地持久化）

| 字段 | 类型 | 说明 |
|------|------|------|
| storeId | string | 门店唯一标识 |
| storeName | string | 门店名称 |
| storeAddress | string | 门店地址 |
| storePhone | string | 门店联系电话 |
| deviceId | string | 本设备唯一标识 |
| boundAt | string | 绑定时间（ISO 8601） |

**约束**:
- 所有字段不可为空
- `storeId` 唯一，一台设备只绑定一个门店
- 存储于 EncryptedSharedPreferences

**关联场景**: 场景1（首次安装检测）、场景2（绑定成功持久化）、场景4（已绑定跳过注册）

---

### StoreQueryResult（接口返回）

| 字段 | 类型 | 说明 |
|------|------|------|
| storeId | string | 门店唯一标识 |
| storeName | string | 门店名称 |
| storeAddress | string | 门店地址 |
| storePhone | string | 门店联系电话 |

**约束**:
- 仅在注册码有效时返回

**关联场景**: 场景2（注册码查询成功，展示门店信息）

---

## API 契约 (API Contracts)

### 查询注册码对应门店

- **端点**: `POST /api/v1/device/query-store`
- **用途**: 根据注册码查询门店信息
- **来源**: PRD 场景2

**请求**:
```json
{
  "registerCode": "string, required — 店员输入的注册码",
  "deviceId": "string, required — 设备唯一标识"
}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "storeId": "store_001",
    "storeName": "北京朝阳旗舰店",
    "storeAddress": "北京市朝阳区xxx路xxx号",
    "storePhone": "010-12345678"
  }
}
```

**响应（失败）**:
```json
{
  "code": 3001,
  "message": "注册码无效"
}
```

**前置条件**: 无（注册流程在登录之前）
**后置条件**: 无状态变更，仅返回门店信息
**副作用**: 无

---

### 确认绑定门店

- **端点**: `POST /api/v1/device/bind-store`
- **用途**: 店员确认后提交绑定请求
- **来源**: PRD 场景2（确认绑定）、场景3（绑定失败）

**请求**:
```json
{
  "registerCode": "string, required — 注册码",
  "deviceId": "string, required — 设备唯一标识",
  "storeId": "string, required — 待绑定的门店 ID"
}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "storeId": "store_001",
    "storeName": "北京朝阳旗舰店",
    "storeAddress": "北京市朝阳区xxx路xxx号",
    "storePhone": "010-12345678",
    "boundAt": "2026-06-09T10:00:00Z"
  }
}
```

**响应（失败）**:
```json
{
  "code": 3002,
  "message": "注册码已失效"
}
```

**前置条件**: 注册码查询接口已成功返回对应门店信息
**后置条件**: 服务端记录该设备与门店的绑定关系
**副作用**: 无

---

### 上报绑定错误

- **端点**: `POST /api/v1/device/bind-error`
- **用途**: 绑定失败时上报错误至运维中台
- **来源**: PRD 场景3（绑定失败）

**请求**:
```json
{
  "deviceId": "string, required — 设备唯一标识",
  "registerCode": "string, required — 注册码",
  "errorCode": "string, required — 错误码",
  "errorMessage": "string, required — 错误详情",
  "timestamp": "number, required — 发生时间戳（ms）"
}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {}
}
```

**前置条件**: 无
**后置条件**: 运维中台记录绑定错误事件
**副作用**: 无；上报失败静默忽略

---

## 场景映射 (Scenario Mapping)

| PRD 场景 | 步骤 | 动作 | 组件 | 数据模型 |
|----------|------|------|------|----------|
| 场景1: 首次安装 | 1 | 冷启动，读取本地绑定信息 | StartupCheckManager | StoreBinding |
|  | 2 | 无绑定信息，展示注册引导页 | StoreRegisterGuideActivity | — |
| 场景2: 注册码查询并绑定 | 1 | 输入注册码，点击"查询门店" | StoreRegisterActivity | — |
|  | 2 | 调用查询接口，展示门店信息 | StoreRegisterActivity | StoreQueryResult |
|  | 3 | 店员点击"确认绑定"，调用绑定接口 | StoreRegisterActivity | StoreBinding |
|  | 4 | 绑定成功，持久化门店信息，进入版本更新检测 | StartupCheckManager | StoreBinding |
| 场景3: 绑定失败 | 1 | 绑定接口返回失败 | StoreRegisterActivity | — |
|  | 2 | 展示绑定失败页，含错误码 | StoreBindFailActivity | — |
|  | 3 | 异步上报错误 | ErrorReporter | — |
| 场景4: 已绑定正常启动 | 1 | 冷启动，读取本地绑定信息成功 | StartupCheckManager | StoreBinding |
|  | 2 | 跳过注册，直接进入版本更新检测 | StartupCheckManager | — |

---

## 指标 (Metrics)

| 维度 | 指标 | 目标 | 测量方法 |
|------|------|------|----------|
| 性能 | 注册码查询接口延迟 P99 | < 1000ms | APM 监控 |
| 性能 | 绑定接口延迟 P99 | < 1000ms | APM 监控 |
| 质量 | 绑定成功率 | ≥ 99% | 运维中台统计 |

---

## 降级策略 (Fallback Strategy)

### 降级场景: 查询/绑定接口不可用

- **触发条件**: 接口返回 5xx 或超时（5s）
- **降级行为**: 展示"网络异常，请检查网络后重试"，提供重试按钮；不自动跳过注册
- **业务影响**: 设备无法完成注册，阻断启动（符合强制注册要求）
- **恢复条件**: 网络恢复后用户点击重试

### 降级场景: 错误上报失败

- **触发条件**: 上报接口失败或超时
- **降级行为**: 静默忽略
- **业务影响**: 运维中台无此次错误记录
- **恢复条件**: N/A

---

## 错误处理 (Error Handling)

| 错误码 | 含义 | HTTP 状态 | 处理 |
|--------|------|-----------|------|
| 3001 | 注册码无效 | 400 | 输入框保留内容，展示红色错误提示 |
| 3002 | 注册码已失效 | 400 | 展示绑定失败页，提示重新获取注册码 |
| 3003 | 注册码已被绑定 | 400 | 展示绑定失败页，含错误码 |
| 3004 | 设备已绑定其他门店 | 400 | 展示绑定失败页，提示联系管理员解绑 |
| 3005 | 门店绑定数达上限 | 400 | 展示绑定失败页，提示联系管理员 |
| 5001 | 服务不可用 | 5xx | 展示网络异常提示，提供重试 |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-09 | 初始 |
