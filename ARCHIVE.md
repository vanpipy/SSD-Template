# 归档说明 (ARCHIVE)

> 本文件说明**已移出本仓库**的历史内容放在哪里,以及如何查阅。
> 仓库内不再保留任何历史代际的样例 —— 仓内只保留**当前契约**(`WORKFLOW.md` + `schema/**` + `scripts/**`)。

## 归档位置

| 归档目录 | 内容 | 清单 |
|----------|------|------|
| `D:\project\_ssd-template-archive\legacy` | 上一代 7-schema 设计(旧 `schema/` 形态、旧的流程说明文档) | `D:\project\_ssd-template-archive\archived-files.txt` |
| `D:\project\_ssd-template-archive\legacy-simple` | 更早一代的极简版设计(旧 `prompt/` + 旧样例规格) | 同上 |

`archived-files.txt` 列出全部归档文件的相对路径与说明,逐条可核对。

## 为什么移出仓库

1. **不参与门禁** —— 校验脚本只扫 `prd/` `tech_design/` `plan/` `test_cases/` `material/`,归档目录不进任何检查,留在仓内只会让人误以为它是有效内容。
2. **避免口径漂移** —— 历史文档里的状态枚举、层路径、脚本清单与当前契约不一致,`grep` 到的命中数会失真。
3. **体积** —— 归档内容占原仓绝大部分字节,模板仓只需要当前契约。

## 查阅方式

归档目录**不是** git 仓库的一部分,不会被 `git clone` 拉到。需要查历史设计时:

```text
D:\project\_ssd-template-archive\
├── archived-files.txt        ← 清单(53 条)
├── legacy\                   ← 旧 7-schema 设计
└── legacy-simple\            ← 旧极简版设计
```

> 归档内容是**只读参考**,不是契约。发现当前 `schema/` / `scripts/` 与归档不一致时,**以当前契约为准**。

## 相关

- 当前契约入口:[WORKFLOW.md](WORKFLOW.md)
- 仓库入口:[README.md](README.md)
