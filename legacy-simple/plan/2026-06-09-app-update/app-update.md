# Plan: 版本更新

> **状态**: Ready
> **来源 Tech Design**: [tech_design/2026-06-09-app-update/app-update.md](../../tech_design/2026-06-09-app-update/app-update.md)
> **来源 PRD**: [prd/2026-06-09-processed/app-update.md](../../prd/2026-06-09-processed/app-update.md)
> **创建日期**: 2026-06-09

---

## 变更清单 (Changes)

### Change #1: app/src/main/java/com/pos/startup/StartupCheckManager.kt

**遵循决策**: KD-1 — 冷启动更新检测时机

**变更描述**:
- **新增**: 冷启动入口协调器，按顺序执行：读取 UpdateConfig.pendingUpdate → 若 true 则跳转更新就绪页；若 false 则调版本接口 → 有新版本则跳转新版本页；无新版本则继续登录页

**策略约束**:
- 必须在任何业务页面（登录、主页）加载之前执行，通过 `SplashActivity` 或 `Application.onCreate` 调起
- 读取本地标记优先，避免在有预下载包时产生额外网络请求（KD-1）
- 版本接口超时设置为 3s，超时后降级直接进入登录页，不阻塞启动
- **不做**: 不在此处处理下载或安装逻辑，职责仅限于检测和路由

**验证**: V1、V2、V8

---

### Change #2: app/src/main/java/com/pos/update/UpdateConfig.kt

**遵循决策**: KD-1、KD-2 — 本地标记持久化

**变更描述**:
- **新增**: UpdateConfig 数据类及其读写封装，使用 EncryptedSharedPreferences 持久化 `pendingUpdate`、`pendingApkPath`、`pendingApkMd5`、`pendingVersion` 四个字段

**策略约束**:
- 使用 EncryptedSharedPreferences，不可使用明文 SharedPreferences
- `pendingUpdate=true` 时写入操作必须同时设置 path/md5/version，保持一致性（不允许部分写入）
- 重置操作（`clear()`）必须原子性地将所有字段恢复初始值
- **不做**: 不在此类中做 MD5 校验或文件操作，职责仅限于数据存储

**验证**: V1、V5、V6

---

### Change #3: app/src/main/java/com/pos/update/UpdateValidator.kt

**遵循决策**: KD-2、KD-3 — MD5 校验逻辑

**变更描述**:
- **新增**: APK 文件 MD5 校验器，接收文件路径和期望 MD5 值，返回校验结果；校验失败时触发删除文件并重置 UpdateConfig

**策略约束**:
- MD5 计算在 IO 线程执行，不在主线程调用
- 校验失败（E-2001）：删除本地 APK 文件 + 重置 UpdateConfig 所有字段为初始值（KD-3）
- **不做**: 不做安装逻辑，不做 UI 交互

**验证**: V6、V7

---

### Change #4: app/src/main/java/com/pos/update/UpdateReadyActivity.kt

**遵循决策**: KD-4 — 3 秒倒计时自动触发

**变更描述**:
- **新增**: "更新就绪"页面，展示待安装版本信息；`onResume` 时启动 3s CountDownTimer，每秒更新按钮文字（如"立即更新(3)"）；倒计时结束或手动点击均触发同一安装方法；`onPause` 时取消计时器

**策略约束**:
- CountDownTimer 在 `onResume` 启动、`onPause` 取消，避免后台计时器泄漏（KD-4）
- 手动点击后立即取消计时器，防止重复触发
- 期间禁用返回键，不可跳过（PRD: 不可跳过强制更新）
- **不做**: 不在此 Activity 中执行实际安装，委托给 UpdateInstaller

**验证**: V1、V9

---

### Change #5: app/src/main/java/com/pos/update/NewVersionActivity.kt

**遵循决策**: KD-4 — 3 秒倒计时自动触发

**变更描述**:
- **新增**: "发现新版本"页面，展示版本号和更新说明；逻辑与 UpdateReadyActivity 相同（3s CountDownTimer），点击或倒计时结束后启动 ApkDownloadService 并展示下载进度

**策略约束**:
- 与 UpdateReadyActivity 共用同一倒计时策略（KD-4），逻辑一致
- 下载期间展示进度条，禁用返回键
- **不做**: 不在此 Activity 中执行下载逻辑，只负责启动 Service 和展示进度

**验证**: V2、V9

---

### Change #6: app/src/main/java/com/pos/update/ApkDownloadService.kt

**遵循决策**: KD-2 — 静默下载与状态隔离

**变更描述**:
- **新增**: 后台 Foreground Service，负责 APK 文件下载；下载成功后执行 MD5 校验，校验通过则写入 UpdateConfig（pendingUpdate=true）；网络断开或存储不足时清除未完成文件、重置 UpdateConfig（pendingUpdate=false）
- **新增**: 静默下载入口，由系统定期触发（或版本检测有新版本时触发），在后台下载不阻断 UI

**策略约束**:
- 下载任务在子线程执行，不在主线程（KD-2，code review 强制）
- 下载完成后必须 MD5 校验，校验失败不写入 UpdateConfig
- 中断时清除未完成文件（不保留部分文件），重置 UpdateConfig.pendingUpdate=false（KD-2）
- **不做**: 不在此 Service 中触发安装，仅负责下载和标记

**验证**: V4、V5

---

### Change #7: app/src/main/java/com/pos/update/UpdateInstaller.kt

**遵循决策**: KD-3 — 安装失败的标记与上报策略

**变更描述**:
- **新增**: APK 安装器，触发系统安装流程并监听安装结果；成功则清除 UpdateConfig；失败则根据错误类型区分处理：E-2001（MD5 失败，删除文件+重置标记）vs E-2002/E-2003（保留标记和文件，允许重试）

**策略约束**:
- 安装失败后必须异步调用 ErrorReporter 上报，上报失败静默忽略（KD-3）
- MD5 失败 vs 非 MD5 失败的标记处理逻辑必须通过单元测试覆盖（KD-3）
- **不做**: 不在此处展示 UI，安装结果通过回调通知 Activity

**验证**: V6、V7

---

### Change #8: app/src/main/java/com/pos/update/UpdateFailActivity.kt

**遵循决策**: KD-3 — 更新失败 UI

**变更描述**:
- **新增**: "更新失败"页面，展示错误码（E-XXXX 格式）和错误原因；提供"重试更新"和"取消"两个操作；取消后保留 pendingUpdate 标记，返回时重新进入启动链路

**策略约束**:
- 错误码必须以 E-XXXX 格式展示，不可展示技术栈 stacktrace
- "取消"不清除 pendingUpdate，下次启动仍触发（PRD 强制要求）
- **不做**: 不允许通过此页面进入任何业务页面

**验证**: V6、V7

---

### Change #9: app/src/main/java/com/pos/update/ErrorReporter.kt

**遵循决策**: KD-3 — 错误上报

**变更描述**:
- **新增**: 错误上报工具类，封装 `POST /api/v1/app/update-error` 调用；在子线程异步执行；失败时静默忽略，不抛出异常

**策略约束**:
- 必须在子线程执行，不可阻塞调用方（KD-3）
- 上报失败只记录本地日志，不向上传递异常
- **不做**: 不重试上报（一次性操作）

**验证**: V6

---

### Change #10: app/src/main/java/com/pos/update/UpdateCompleteActivity.kt

**遵循决策**: KD-4

**变更描述**:
- **新增**: "更新完成"页面，展示 3 秒后自动跳转登录页的倒计时提示；3 秒后自动跳转 LoginActivity，清除自身任务栈

**策略约束**:
- 3 秒后自动跳转，不需要手动点击（PRD 要求）
- 跳转时清除更新相关 Activity 栈，不可返回
- **不做**: 不在此处处理任何业务逻辑

**验证**: V1、V2

---

### Change #11: app/src/main/java/com/pos/update/VersionApiService.kt

**遵循决策**: KD-1 — 版本检测接口

**变更描述**:
- **新增**: Retrofit 接口声明 `GET /api/v1/app/version`，携带 `currentVersion` 和 `deviceId` 参数；响应映射为 VersionInfo 数据类

**策略约束**:
- 超时配置为 3s（连接超时 + 读取超时），在 OkHttpClient 中单独配置
- **不做**: 不在此层处理超时降级逻辑，由 StartupCheckManager 处理

**验证**: V2、V3、V8

---

## 验证用例 (Verification)

### V1: 有预下载包 — 冷启动正常更新完成

- **Given**: `pendingUpdate=true`，本地 APK 文件存在，MD5 校验通过
- **When**: 店员冷启动 APP
- **Then**: 展示 UpdateReadyActivity → 3s 后（或手动点击）触发安装 → 安装成功 → 展示 UpdateCompleteActivity 3s → 自动跳转 LoginActivity；UpdateConfig 所有字段被清除

---

### V2: 无预下载包 — 接口返回新版本，下载安装完成

- **Given**: `pendingUpdate=false`，版本接口返回 `hasUpdate=true`
- **When**: 店员冷启动 APP
- **Then**: StartupCheckManager 调版本接口 → 展示 NewVersionActivity → 3s 后启动下载 → 下载完成 MD5 校验通过 → 触发安装 → 安装成功 → 跳转 LoginActivity

---

### V3: 无新版本 — 直接进入登录页

- **Given**: `pendingUpdate=false`，版本接口返回 `hasUpdate=false`
- **When**: 店员冷启动 APP
- **Then**: StartupCheckManager 调版本接口 → 不展示任何更新页面 → 直接跳转 LoginActivity

---

### V4: 静默下载中断 — 文件清除，标记重置

- **Given**: APP 运行中 ApkDownloadService 正在后台下载
- **When**: 网络断开（或存储空间不足）
- **Then**: ApkDownloadService 删除未完成的下载文件 → UpdateConfig.pendingUpdate 重置为 false → 下次冷启动时重新检测版本

---

### V5: 静默下载成功 — 标记写入

- **Given**: APP 运行中 ApkDownloadService 完成下载，MD5 校验通过
- **When**: 下载完成回调触发
- **Then**: UpdateConfig 写入 pendingUpdate=true、pendingApkPath、pendingApkMd5、pendingVersion，四个字段同时写入（原子操作）

---

### V6: 更新失败（MD5 校验失败）— 文件删除，标记重置，上报

- **Given**: pendingUpdate=true，本地 APK 文件存在但 MD5 不匹配
- **When**: UpdateValidator 执行 MD5 校验
- **Then**: 本地 APK 文件被删除 → UpdateConfig 所有字段重置为初始值（pendingUpdate=false）→ 展示 UpdateFailActivity（错误码 E-2001）→ ErrorReporter 异步上报错误

---

### V7: 更新失败（存储空间不足）— 标记保留，可重试

- **Given**: 触发 APK 安装，系统返回存储空间不足错误
- **When**: UpdateInstaller 捕获安装错误
- **Then**: UpdateConfig.pendingUpdate 保持 true（不清除）→ 展示 UpdateFailActivity（错误码 E-2002）→ ErrorReporter 异步上报 → 店员点击"重试"可重新触发安装

---

### V8: 版本接口超时 — 降级进入登录页

- **Given**: `pendingUpdate=false`，版本接口响应超时（> 3s）
- **When**: 店员冷启动 APP
- **Then**: StartupCheckManager 捕获超时异常 → 跳过版本检测 → 直接跳转 LoginActivity，不展示任何更新页面

---

### V9: 3 秒倒计时期间手动点击 — 立即触发，计时器取消

- **Given**: UpdateReadyActivity 或 NewVersionActivity 已展示，倒计时进行中（剩余 > 0s）
- **When**: 店员点击"立即更新"按钮
- **Then**: CountDownTimer 立即取消 → 触发安装/下载流程 → 不会因计时器到期再次触发

---

### V10: 错误上报失败 — 静默忽略

- **Given**: 安装失败，ErrorReporter 调用上报接口，接口返回 5xx
- **When**: 上报请求完成
- **Then**: ErrorReporter 仅记录本地日志，不抛出异常 → 前台 UpdateFailActivity 正常展示，不受上报结果影响

---

## 业务约束 (Business Constraints)

**前置条件**:
1. 设备已完成门店绑定（门店注册流程在版本更新之前）
2. APP 具有存储读写权限和安装 APK 权限

**不变量**:
- 更新流程进行中，任何 Activity 禁用返回键，不可跳过进入业务页面
- `pendingUpdate=true` 时，`pendingApkPath`、`pendingApkMd5`、`pendingVersion` 必须同时有值（不允许部分设置）

**后置条件**:
1. 更新成功：UpdateConfig 所有字段清除，APP 重启后运行最新版本，跳转 LoginActivity
2. 更新失败（MD5）：本地 APK 删除，UpdateConfig 重置，运维中台收到错误上报
3. 更新失败（非 MD5）：UpdateConfig.pendingUpdate 保留，运维中台收到错误上报

**副作用**:
1. 安装失败时异步触发 `POST /api/v1/app/update-error`，失败静默忽略
2. 静默下载完成写入本地文件系统，占用存储空间

---

## 开发约束 (Development Constraints)

| 约束 | 值 |
|------|-----|
| 并发 | ApkDownloadService 单实例，防止重复下载；UpdateConfig 写操作加锁保证一致性 |
| 事务边界 | UpdateConfig 四字段写入必须原子（SharedPreferences.apply() 单次提交） |
| 幂等性 | 版本接口为 GET，天然幂等；安装触发去重：安装进行中不重复触发 |
| 重试 | 错误上报不重试（一次性）；APK 安装失败后用户主动点击重试，不自动重试 |
| 超时 | 版本检测接口：连接超时 3s / 读取超时 3s；错误上报接口：连接超时 5s / 读取超时 5s |

---

## 完成检查 (Completion Checklist)

- [ ] **代码实现** — 所有 Change 已完成
- [ ] **决策遵循** — KD-1 至 KD-4 已遵守
- [ ] **类型检查** — 类型检查通过
- [ ] **规范检查** — Lint 通过
- [ ] **测试通过** — V1 至 V10 用例通过
- [ ] **无遗留** — 无未解决的 TODO/FIXME
- [ ] **PR 已创建** — 如适用

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-09 | 初始 |
