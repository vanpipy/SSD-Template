# Tech Design: 订单全流程

> **状态**: Ready
> **来源 PRD**: [prd/2026-06-09-processed/order-flow.md](../../prd/2026-06-09-processed/order-flow.md)
> **创建日期**: 2026-06-09

---

## 关键决策 (Key Decisions)

### KD-1: 草稿订单的创建时机

**背景 (Context)**: 首次加购商品时需要自动创建草稿订单，并关联门店/款台/设备/收银员。需要决定草稿订单由前端主动创建还是加购商品接口自动创建。

**决定 (Decision)**: 加购商品接口（Add Item）在服务端自动创建草稿订单：若 `draftOrderId` 为空则创建新草稿并返回 `draftOrderId`；若已存在则直接更新。前端首次加购时传空 `draftOrderId`，后续携带返回的 ID。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 前端先调"创建草稿"接口再加购 | 前端流程显式清晰 | 两次网络请求，首次加购延迟增加 |
| 加购接口自动创建（服务端幂等） | 一次请求，延迟最低 | 服务端需要幂等处理并返回 draftOrderId |

**理由 (Rationale)**: PRD 要求"首次加购时自动创建草稿订单"，加购和创建合并为一次请求性能最优；服务端幂等创建是标准模式，逻辑清晰。

**如何强制 (Enforced by)**: 接口文档约定 `draftOrderId` 可选；服务端加购接口单元测试覆盖首次和后续两种情况。

---

### KD-2: 实时取价与促销计算的触发策略

**背景 (Context)**: 每次商品变动后需要重新取价并计算促销。需要决定计算逻辑在前端还是服务端，以及触发频率（每次变动实时触发 vs 防抖）。

**决定 (Decision)**: 取价和促销计算完全由服务端在加购/修改接口中同步完成并返回最新订单明细；前端不做本地计算，直接展示服务端返回结果。商品数量输入采用 300ms 防抖后触发接口，避免频繁请求。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 服务端同步计算，前端展示 | 计算逻辑集中，前端无需维护促销规则 | 每次变动都有网络请求 |
| 前端本地计算，定期同步服务端 | 减少请求数 | 前端需维护完整促销规则，容易与服务端不一致 |

**理由 (Rationale)**: 促销规则复杂（满减/折扣/会员价）且频繁变更，前端本地计算难以维护一致性；300ms 防抖在收银场景下用户体验可接受。

**如何强制 (Enforced by)**: code review 确认前端不存在本地价格计算逻辑；接口测试验证会员价和促销正确返回。

---

### KD-3: 结算锁价的一致性保障

**背景 (Context)**: 点击结算时需要重新拉取最新价格并锁定，保存订单快照，防止结算后价格变动。需要决定快照的内容和存储位置。

**决定 (Decision)**: 结算接口在服务端原子性地完成：重新取价 → 重算促销 → 保存快照（含流程/基础/会员/商品信息，包括单价和优惠金额）→ 订单状态变为"已制单"。快照保存在订单服务，不可变更。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 服务端原子操作，保存完整快照 | 一致性强，支持对账 | 实现复杂，需事务支持 |
| 前端在结算时把当前价格提交服务端 | 前端主导，简单 | 前端数据可能被篡改，价格不可信 |

**理由 (Rationale)**: 订单金额涉及资金，必须由服务端最终取价和计算，不信任前端提交的价格；原子操作保证快照完整性。

**如何强制 (Enforced by)**: 服务端结算接口使用数据库事务；code review 确认前端不传入价格字段。

---

### KD-4: 库存异步扣减的解耦设计

**背景 (Context)**: 订单完成后需要异步扣减库存，但库存扣减失败不影响订单完成状态。需要决定异步解耦方式。

**决定 (Decision)**: 订单状态变为"已完成"后，订单服务发送领域事件（MQ 消息）通知库存服务；库存服务消费消息后扣减库存，失败时记录异常日志并告警，不回调订单服务。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| MQ 异步解耦 | 完全解耦，订单服务不感知库存失败 | 需要引入 MQ 组件 |
| 订单服务直接异步 HTTP 调用库存服务 | 无需 MQ | 服务强耦合，库存服务故障影响订单服务 |
| 定时任务补偿 | 无实时性要求时简单 | 延迟高，库存不实时 |

**理由 (Rationale)**: PRD 明确"库存扣减失败不影响订单完成"，MQ 是最彻底的解耦方案；收银场景库存实时性要求高，MQ 消费延迟通常 < 1s 可接受。

**如何强制 (Enforced by)**: 架构评审确认 MQ 选型；库存服务消费失败的告警配置；集成测试验证库存失败不影响订单状态。

---

## 数据模型 (Data Models)

### DraftOrder（草稿订单）

| 字段 | 类型 | 说明 |
|------|------|------|
| draftOrderId | string | 草稿订单唯一标识 |
| storeId | string | 门店 ID |
| posId | string | 款台 ID |
| deviceId | string | 设备 ID |
| cashierId | string | 收银员 ID |
| memberId | string? | 会员 ID，可空 |
| status | string | CREATED / SETTLED / PAID / COMPLETED |
| items | OrderItem[] | 商品明细列表 |
| totalAmount | number | 商品总金额（分） |
| discountAmount | number | 优惠金额（分） |
| payableAmount | number | 应付金额（分） |
| createdAt | string | 创建时间（ISO 8601） |
| updatedAt | string | 最后更新时间 |

**约束**:
- `storeId`、`posId`、`deviceId`、`cashierId` 不可为空
- `payableAmount >= 0`
- `status` 状态流转：CREATED → SETTLED → PAID → COMPLETED

**关联场景**: 场景1（创建）、场景2（更新）、场景3（结算）、场景4（支付完成）

---

### OrderItem（商品明细）

| 字段 | 类型 | 说明 |
|------|------|------|
| skuId | string | 商品规格 ID |
| productId | string | 商品 ID |
| productName | string | 商品名称快照 |
| quantity | int | 数量 |
| unitPrice | number | 单价快照（分） |
| memberPrice | number? | 会员价快照（分），可空 |
| discountAmount | number | 该商品优惠金额（分） |
| subtotal | number | 小计（分） |

**约束**:
- `quantity > 0`
- `unitPrice > 0`
- 结算后商品快照不可变更

**关联场景**: 场景1-3

---

### InventoryDeductEvent（MQ 消息）

| 字段 | 类型 | 说明 |
|------|------|------|
| orderId | string | 正式订单号 |
| storeId | string | 门店 ID |
| items | InventoryItem[] | 扣减明细 |
| occurredAt | string | 事件发生时间 |

### InventoryItem

| 字段 | 类型 | 说明 |
|------|------|------|
| productId | string | 商品 ID |
| skuId | string | 规格 ID |
| quantity | int | 扣减数量 |

**关联场景**: 场景6（库存异步扣减）

---

## API 契约 (API Contracts)

### 加购/修改商品

- **端点**: `POST /api/v1/order/items`
- **用途**: 加购商品或修改数量，首次调用自动创建草稿订单
- **来源**: PRD 场景1（首次加购）、场景2（加购/修改商品实时重算）

**请求**:
```json
{
  "draftOrderId": "string, optional — 草稿订单 ID，首次加购时为空",
  "storeId": "string, required — 门店 ID",
  "posId": "string, required — 款台 ID",
  "deviceId": "string, required — 设备 ID",
  "cashierId": "string, required — 收银员 ID",
  "memberId": "string, optional — 会员 ID",
  "skuId": "string, required — 商品规格 ID",
  "quantity": "number, required — 数量（0 表示删除该商品）"
}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "draftOrderId": "draft_001",
    "items": [],
    "totalAmount": 10000,
    "discountAmount": 1000,
    "payableAmount": 9000
  }
}
```

**前置条件**: 店员已登录
**后置条件**: 草稿订单创建或更新，价格和促销重新计算
**副作用**: 无

---

### 结算（锁价）

- **端点**: `POST /api/v1/order/{draftOrderId}/settle`
- **用途**: 重新取价、重算促销、保存快照，订单状态变为"已制单"
- **来源**: PRD 场景3（结算锁价）

**请求**:
```json
{}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "orderId": "order_001",
    "payableAmount": 9000,
    "items": []
  }
}
```

**前置条件**: 草稿订单存在且状态为 CREATED，商品数量 > 0
**后置条件**: 订单状态变为 SETTLED，快照保存，生成正式订单号
**副作用**: 无

---

### 支付结果回调

- **端点**: `POST /api/v1/order/{orderId}/payment-result`
- **用途**: 支付中心回调，更新订单支付状态
- **来源**: PRD 场景4（支付成功）、场景5（支付失败）

**请求**:
```json
{
  "success": "boolean, required — 支付是否成功",
  "transactionId": "string, optional — 支付流水号（成功时）",
  "failReason": "string, optional — 失败原因（失败时）"
}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "orderId": "order_001",
    "status": "PAID"
  }
}
```

**前置条件**: 订单状态为 SETTLED
**后置条件**: 成功时状态变为 PAID；失败时状态回退为 SETTLED（可重试支付）
**副作用**: 无

---

### 完成订单

- **端点**: `POST /api/v1/order/{orderId}/complete`
- **用途**: 收银员点击"完成订单"，状态变为 COMPLETED，触发库存扣减
- **来源**: PRD 场景4（支付成功并完成订单）

**请求**:
```json
{}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "orderId": "order_001",
    "status": "COMPLETED"
  }
}
```

**前置条件**: 订单状态为 PAID
**后置条件**: 订单状态变为 COMPLETED
**副作用**: 发送 InventoryDeductEvent 至 MQ，异步触发库存扣减

---

## 场景映射 (Scenario Mapping)

| PRD 场景 | 步骤 | 动作 | 组件 | 数据模型 |
|----------|------|------|------|----------|
| 场景1: 首次加购创建草稿 | 1 | 扫描商品条码 | CartActivity | — |
|  | 2 | 调加购接口（draftOrderId 为空） | OrderRepository | DraftOrder |
|  | 3 | 服务端创建草稿订单，返回 draftOrderId 和购物车 | OrderRepository | DraftOrder |
|  | 4 | 前端存储 draftOrderId，展示购物车 | CartViewModel | DraftOrder |
| 场景2: 商品变动实时重算 | 1 | 扫码/修改数量，300ms 防抖 | CartActivity | — |
|  | 2 | 调加购接口（携带 draftOrderId） | OrderRepository | DraftOrder |
|  | 3 | 服务端重新取价和促销，返回最新购物车 | CartViewModel | DraftOrder |
| 场景3: 结算锁价 | 1 | 点击"结算" | CartActivity | — |
|  | 2 | 调结算接口，服务端原子操作锁价 | OrderRepository | DraftOrder |
|  | 3 | 返回正式订单号和应付金额，跳转支付页 | PaymentActivity | DraftOrder |
| 场景4: 支付成功并完成订单 | 1 | 扫取付款码，发起支付（含支付即会员流程） | PaymentActivity | — |
|  | 2 | 支付中心回调支付成功 | OrderRepository | — |
|  | 3 | 订单状态变为 PAID，展示支付成功 | PaymentActivity | — |
|  | 4 | 收银员点击"完成订单"，调完成接口 | OrderRepository | — |
|  | 5 | 状态变为 COMPLETED，发送 MQ 消息 | OrderService | InventoryDeductEvent |
| 场景5: 支付失败 | 1 | 支付中心回调支付失败 | OrderRepository | — |
|  | 2 | 订单状态回退至 SETTLED，展示失败原因 | PaymentActivity | — |
|  | 3 | 收银员可重新发起支付 | PaymentActivity | — |
| 场景6: 库存异步扣减 | 1 | 消费 InventoryDeductEvent | InventoryConsumer | InventoryDeductEvent |
|  | 2 | 扣减库存（门店+商品+规格+数量） | InventoryService | — |
|  | 3a | 扣减成功，记录库存调整日志 | InventoryService | — |
|  | 3b | 扣减失败，记录异常日志，触发告警，不影响订单 | InventoryService | — |

---

## 指标 (Metrics)

| 维度 | 指标 | 目标 | 测量方法 |
|------|------|------|----------|
| 性能 | 加购接口延迟 P99 | < 500ms | APM 监控 |
| 性能 | 结算接口延迟 P99 | < 1000ms | APM 监控 |
| 性能 | 支付结果回调处理延迟 P99 | < 500ms | APM 监控 |
| 性能 | 库存扣减 MQ 消费延迟 P99 | < 2000ms | MQ 监控 |
| 质量 | 结算成功率 | ≥ 99.9% | 接口监控 |
| 质量 | 库存扣减成功率 | ≥ 99% | 库存服务日志统计 |

---

## 降级策略 (Fallback Strategy)

### 降级场景: 加购/结算接口超时

- **触发条件**: 接口超时（5s）或返回 5xx
- **降级行为**: Toast 提示"网络异常，请重试"，购物车保持当前展示状态
- **业务影响**: 店员需手动重试，无数据丢失
- **恢复条件**: 网络恢复后手动重试

### 降级场景: 库存服务不可用

- **触发条件**: 库存消费者处理 MQ 消息失败
- **降级行为**: 消息重试（指数退避，最多 3 次），超过重试次数后转入死信队列并告警
- **业务影响**: 库存数据可能暂时不准确，不影响订单完成状态
- **恢复条件**: 运维介入处理死信队列中的消息

---

## 错误处理 (Error Handling)

| 错误码 | 含义 | HTTP 状态 | 处理 |
|--------|------|-----------|------|
| 6001 | 商品已下架 | 400 | Toast 提示，不加购 |
| 6002 | 库存不足 | 400 | Toast 提示，不加购 |
| 6003 | 草稿订单不存在 | 404 | 清空购物车，重新开始 |
| 6004 | 订单状态不合法 | 400 | 刷新页面显示最新状态 |
| 6005 | 结算时商品已下架 | 400 | 提示移除下架商品后重新结算 |
| 5001 | 服务不可用 | 5xx | Toast 提示，提供重试 |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-09 | 初始 |
