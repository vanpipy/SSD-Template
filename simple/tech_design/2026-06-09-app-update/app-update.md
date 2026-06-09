# Tech Design: 版本更新

> **状态**: Ready
> **来源 PRD**: [prd/2026-06-09-processed/app-update.md](../../prd/2026-06-09-processed/app-update.md)
> **创建日期**: 2026-06-09

---

## 关键决策 (Key Decisions)

### KD-1: 冷启动更新检测时机

**背景 (Context)**: APP 冷启动时需要在进入业务页面之前完成版本检测，决定检测逻辑在启动链路中的位置及与门店注册、登录流程的顺序关系。

**决定 (Decision)**: 冷启动后第一步检查本地 `pendingUpdate` 标记，有则直接进入更新流程；无则调用版本接口，有新版本也进入更新流程；两者均无则继续启动链路。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 本地标记优先，无标记再请求接口 | 有预下载包时零网络延迟 | 逻辑分两段，需维护标记一致性 |
| 每次冷启动都请求接口 | 逻辑统一，无本地标记 | 增加启动延迟，浪费带宽 |

**理由 (Rationale)**: 静默下载场景是主路径，预下载后直接用本地包可避免重复下载；无预下载包时再请求接口，逻辑清晰，启动延迟可控。

**如何强制 (Enforced by)**: 启动链路单元测试，覆盖 `pendingUpdate=true` 和 `pendingUpdate=false` 两个分支。

---

### KD-2: 静默下载与前台更新的状态隔离

**背景 (Context)**: 静默下载在 APP 运行期间后台进行，不能阻断收银操作；下载完成后通过 `pendingUpdate` 标记通知下次启动时触发更新。

**决定 (Decision)**: 静默下载使用独立后台 Service，下载成功且 MD5 校验通过后设置 `pendingUpdate=true`；下载中断（网络断开/存储不足）时清除未完成文件并重置标记为 false。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 后台 Service + 本地标记 | 不阻断 UI，状态持久化 | 需处理 Service 被杀死的情况 |
| WorkManager 任务 | 系统级调度，可靠性高 | 下载进度回调复杂 |

**理由 (Rationale)**: 收银 PDA 设备常驻运行，后台 Service 可被可靠维持；WorkManager 适合定期任务，对实时性要求不高的场景，此处选 Service 更直接。

**如何强制 (Enforced by)**: code review 确认下载任务不在主线程；集成测试模拟网络断开场景验证文件清理逻辑。

---

### KD-3: 更新失败上报与重试策略

**背景 (Context)**: APK 安装失败时（MD5 校验失败/存储空间不足/系统拦截）需上报运维中台，同时保留 `pendingUpdate` 标记让下次启动仍触发更新。

**决定 (Decision)**: 安装失败时展示错误码（格式：E-XXXX），异步上报错误信息至运维中台，保留 `pendingUpdate=true` 和本地 APK 文件（MD5 失败则删除并重置）。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| 保留标记，下次启动重试 | 用户无感知，自动恢复 | 若 APK 损坏会反复失败 |
| 清除标记，等待下次静默下载 | 避免损坏包反复触发 | 可能长时间处于旧版本 |

**理由 (Rationale)**: MD5 校验失败时删除文件并重置标记，避免损坏包循环；存储不足/系统拦截属于环境问题，保留标记让用户手动清理后重试更合理。

**如何强制 (Enforced by)**: 单元测试分别验证 MD5 失败和非 MD5 失败两种路径的标记和文件状态。

---

### KD-4: 3 秒自动触发倒计时的实现

**背景 (Context)**: 两个更新入口页面（有预下载包/发现新版本）都需要 3 秒倒计时后自动触发，期间店员也可手动点击提前触发。

**决定 (Decision)**: 使用 `CountDownTimer`（Android）在页面 `onResume` 时启动，倒计时结束触发与手动点击相同的触发逻辑；页面 `onPause` 时取消计时器。

**备选方案 (Alternatives)**:

| 选项 | 优点 | 缺点 |
|------|------|------|
| CountDownTimer | 简单，与页面生命周期绑定 | 需注意 onPause 时取消 |
| Handler.postDelayed | 轻量 | 无内置进度回调 |

**理由 (Rationale)**: `CountDownTimer` 提供 `onTick` 回调便于更新按钮文字显示剩余秒数，实现最直接。

**如何强制 (Enforced by)**: UI 测试验证 3 秒后自动触发；手动点击后计时器取消。

---

## 数据模型 (Data Models)

### UpdateConfig（本地持久化）

| 字段 | 类型 | 说明 |
|------|------|------|
| pendingUpdate | boolean | 是否有待安装的预下载包 |
| pendingApkPath | string? | 预下载 APK 文件路径，null 表示无 |
| pendingApkMd5 | string? | 预下载 APK 的 MD5 值，用于校验 |
| pendingVersion | string? | 待安装版本号 |

**约束**:
- `pendingUpdate=true` 时 `pendingApkPath`、`pendingApkMd5`、`pendingVersion` 不可为空
- 存储于 SharedPreferences / 加密本地存储

**关联场景**: 场景1（有预下载包）、场景2（无预下载包）、场景4（更新失败）、场景5（静默下载中断）

---

### VersionInfo（接口返回）

| 字段 | 类型 | 说明 |
|------|------|------|
| hasUpdate | boolean | 是否有新版本 |
| latestVersion | string | 最新版本号 |
| downloadUrl | string? | APK 下载地址 |
| md5 | string? | APK MD5 值 |
| forceUpdate | boolean | 是否强制更新（本期始终为 true） |
| releaseNote | string? | 更新说明 |

**约束**:
- `hasUpdate=true` 时 `downloadUrl`、`md5` 不可为空
- `forceUpdate` 本期固定为 true

**关联场景**: 场景2（无预下载包，调接口检测）

---

## API 契约 (API Contracts)

### 获取版本信息

- **端点**: `GET /api/v1/app/version`
- **用途**: 冷启动时检测是否有新版本
- **来源**: PRD 场景2（无预下载包）

**请求**:
```json
{
  "currentVersion": "string, required — 当前 APP 版本号，如 1.2.3",
  "deviceId": "string, required — 设备唯一标识"
}
```

**响应（成功）**:
```json
{
  "code": 0,
  "data": {
    "hasUpdate": true,
    "latestVersion": "1.3.0",
    "downloadUrl": "https://cdn.example.com/app-1.3.0.apk",
    "md5": "abc123def456",
    "forceUpdate": true,
    "releaseNote": "修复若干问题"
  }
}
```

**响应（失败）**:
```json
{
  "code": 5001,
  "message": "版本服务暂不可用"
}
```

**前置条件**: 设备已完成门店绑定（但版本检测在门店注册之后、登录之前）
**后置条件**: 无状态变更，仅返回版本信息
**副作用**: 无

---

### 上报更新错误

- **端点**: `POST /api/v1/app/update-error`
- **用途**: APK 安装失败时上报错误至运维中台
- **来源**: PRD 场景4（更新失败）

**请求**:
```json
{
  "deviceId": "string, required — 设备唯一标识",
  "version": "string, required — 尝试安装的版本号",
  "errorCode": "string, required — 错误码，如 E-2003",
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

**响应（失败）**:
```json
{
  "code": 5002,
  "message": "上报失败"
}
```

**前置条件**: 无
**后置条件**: 运维中台记录该错误事件
**副作用**: 无；上报失败不影响客户端逻辑，静默忽略

---

## 场景映射 (Scenario Mapping)

| PRD 场景 | 步骤 | 动作 | 组件 | 数据模型 |
|----------|------|------|------|----------|
| 场景1: 有预下载包 | 1 | 冷启动，读取 `pendingUpdate` 标记 | StartupCheckManager | UpdateConfig |
|  | 2 | MD5 校验本地 APK | UpdateValidator | UpdateConfig |
|  | 3 | 展示"更新就绪"页，3s 倒计时 | UpdateReadyActivity | — |
|  | 4 | 触发 APK 安装 | UpdateInstaller | — |
|  | 5 | 安装完成，展示"更新完成"页 3s，跳转登录 | UpdateCompleteActivity | — |
| 场景2: 无预下载包 | 1 | 冷启动，`pendingUpdate=false`，调版本接口 | StartupCheckManager | VersionInfo |
|  | 2 | 接口返回有新版本，展示"发现新版本"页，3s 倒计时 | NewVersionActivity | VersionInfo |
|  | 3 | 开始下载 APK，展示下载进度 | ApkDownloadService | UpdateConfig |
|  | 4 | 下载完成，自动触发安装 | UpdateInstaller | UpdateConfig |
|  | 5 | 安装完成，跳转登录页 | UpdateCompleteActivity | — |
| 场景3: 无新版本 | 1 | 冷启动，接口返回无新版本 | StartupCheckManager | VersionInfo |
|  | 2 | 直接进入登录页 | LoginActivity | — |
| 场景4: 更新失败 | 1 | APK 安装失败，捕获错误码 | UpdateInstaller | UpdateConfig |
|  | 2 | 展示"更新失败"页，含错误码 | UpdateFailActivity | — |
|  | 3 | 异步上报错误至运维中台 | ErrorReporter | — |
|  | 4 | 用户点击"重试"，重新触发安装 | UpdateInstaller | UpdateConfig |
| 场景5: 静默下载中断 | 1 | 网络断开或存储不足，下载中断 | ApkDownloadService | UpdateConfig |
|  | 2 | 清除未完成文件，重置 `pendingUpdate=false` | ApkDownloadService | UpdateConfig |

---

## 指标 (Metrics)

| 维度 | 指标 | 目标 | 测量方法 |
|------|------|------|----------|
| 性能 | 版本检测接口延迟 P99 | < 1000ms | APM 监控 |
| 性能 | APK 下载速度（4G 网络） | ≥ 500 KB/s | 下载耗时日志 |
| 质量 | 更新成功率 | ≥ 99% | 运维中台统计 |
| 质量 | 错误上报成功率 | ≥ 95% | 运维中台统计 |

---

## 降级策略 (Fallback Strategy)

### 降级场景: 版本接口不可用

- **触发条件**: `GET /api/v1/app/version` 返回 5xx 或超时（3s）
- **降级行为**: 跳过版本检测，直接进入登录页；本次冷启动不触发更新
- **业务影响**: 设备可能在接口故障期间以旧版本运行，不影响当前收银
- **恢复条件**: 下次冷启动版本接口恢复后重新检测

### 降级场景: 错误上报失败

- **触发条件**: `POST /api/v1/app/update-error` 失败或超时
- **降级行为**: 静默忽略，不影响前台更新失败页展示
- **业务影响**: 运维中台无此次错误记录，不影响用户操作
- **恢复条件**: N/A（一次性上报，不重试）

---

## 错误处理 (Error Handling)

| 错误码 | 含义 | HTTP 状态 | 处理 |
|--------|------|-----------|------|
| E-2001 | MD5 校验失败 | — | 删除本地 APK，重置标记，展示错误页 |
| E-2002 | 存储空间不足 | — | 展示错误页，提示清理空间后重试 |
| E-2003 | 系统拦截安装 | — | 展示错误页，提示检查安装权限 |
| 5001 | 版本服务不可用 | 5xx | 降级跳过，直接进入登录页 |
| 5002 | 上报失败 | 5xx | 静默忽略 |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-09 | 初始 |
