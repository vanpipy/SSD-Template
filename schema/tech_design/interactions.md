# Interactions: {topic}

> **状态**: Draft | Ready
> **来源**: [./README.md](./README.md)
> **创建日期**: {YYYY-MM-DD}
> **最后更新**: {YYYY-MM-DD}
> **格式**: Mermaid `sequenceDiagram`

---

## 系统级交互 (System-Level)

> 描述与外部系统/服务/用户的交互流程

### SYS-1: {流程名}

**Reference**: PRD 场景 {n}
**Trigger**: {触发条件}
**引用决策**: KD-{n}

```mermaid
sequenceDiagram
    actor U as User
    participant App as 客户端
    participant API as 后端服务
    participant Ext as 外部 API

    U->>App: 触发操作
    activate App
    App->>API: 请求
    activate API
    API->>Ext: 远程调用
    activate Ext
    Ext-->>API: 响应
    deactivate Ext
    API-->>App: 返回结果
    deactivate API
    App-->>U: 展示结果
    deactivate App
```

**Notes**:
- 超时设置: {外部 API 调用 N 秒}
- 重试策略: {最多 N 次, 退避策略}
- 降级行为: {失败时降级为 ...}
- 幂等性: {请求是否幂等, 如何保证}

---

## 模块级交互 (Module-Level)

> 描述内部模块/组件的交互流程

### MOD-1: {流程名}

**Reference**: PRD 场景 {n}
**Trigger**: {触发条件}
**引用决策**: KD-{n}

```mermaid
sequenceDiagram
    participant C as Controller
    participant S as Service
    participant R as Repository
    participant Cache
    participant DB

    C->>S: 业务方法
    activate S
    S->>R: 查询
    activate R
    R->>Cache: 读缓存
    alt 缓存命中
        Cache-->>R: 数据
    else 缓存未命中
        R->>DB: 查询
        DB-->>R: 数据
        R->>Cache: 写回
    end
    R-->>S: 返回
    deactivate R
    S-->>C: 响应
    deactivate S
```

**Notes**:
- 事务边界: {哪个组件开启 / 提交事务}
- 幂等性: {写操作如何保证幂等}
- 缓存策略: {缓存粒度, 失效时间}
- 错误处理: {异常路径}

---

## Mermaid 语法参考

| 场景 | 写法 |
|------|------|
| 同步调用 | `A->>B: msg` |
| 返回 | `B-->>A: result` |
| 异步消息 | `A-)B: msg` (无激活线) |
| 条件分支 | `alt 条件A ... else 条件B ... end` |
| 可选分支 | `opt 条件 ... end` |
| 循环 | `loop 描述 ... end` |
| 关键区 | `critical 操作 ... option 超时 ... end` |
| 注释 | `Note over A,B: 说明文字` |
| 激活 | `activate A` / `deactivate A` |
| 参与者类型 | `actor` (用户) / `participant` (组件) / `database` (DB) |

---

## 检查清单 (Completion Checklist)

- [ ] 每个时序图有 **Reference** (PRD 场景或 FR-XXX)
- [ ] 每个时序图有 **Trigger** (触发条件)
- [ ] 每个时序图有 **Notes** (超时 / 重试 / 降级 / 事务 / 幂等 中至少 2 项)
- [ ] 系统级图覆盖所有外部系统调用
- [ ] 模块级图覆盖所有内部跨组件调用
- [ ] Mermaid 语法可在 GitHub 渲染
- [ ] 编号唯一 (SYS-1, SYS-2, MOD-1, MOD-2 ...)

---

## 变更记录 (Change Log)

| 日期 | 变更 |
|------|------|
| {YYYY-MM-DD} | 初始 |
