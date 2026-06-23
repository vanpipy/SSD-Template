# API Contracts: {topic}

> **状态**: Draft | Ready
> **来源**: [./README.md](./README.md)
> **创建日期**: {YYYY-MM-DD}
> **最后更新**: {YYYY-MM-DD}
>
> **升级条件**: 如果 API 数 > 5 或跨服务,改用 `contracts/` 子目录,每个 API 一个文件 (`contracts/{module}.md`)

---

## {接口名 1}

- **端点**: `METHOD /path`
- **用途**: {一句话}
- **来源**: PRD 场景 {n}
- **引用决策**: KD-{n}
- **时序图**: SYS-{n} / MOD-{n}

**请求**:

```json
{
  "fieldA": "string, required — 说明",
  "fieldB": "number, optional — 说明, 默认 X"
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
  "code": {error_code},
  "message": "错误说明"
}
```

**前置条件**: 调用前必须满足的条件
**后置条件**: 调用后系统状态变化
**副作用**: 触发的异步操作或事件

---

## {接口名 2}

...

---

## 检查清单 (Completion Checklist)

- [ ] 每个 API 有端点 + 请求 + 响应(成功 / 失败) + 前置 / 后置 / 副作用
- [ ] 字段类型明确(**不用 `any`**)
- [ ] 错误码有具体值(**不用 `4xx` 泛指**)
- [ ] 关联场景、决策、时序图编号已填写

---

## 变更记录 (Change Log)

| 日期 | 变更 |
|------|------|
| {YYYY-MM-DD} | 初始 |
