#!/usr/bin/env python3
"""门禁失败标识的**规范化**提取与比较 (gate_ids.py)

Stdlib only. 供 scripts/measure.py 与 scripts/check-baseline-invariance.py 共用。

## 为什么需要规范化

同一份失败在不同日志里有多种写法, 直接 diff 原始行会产生**假新失败**:

| 场景 | 原始形态 | 规范化标识 |
|------|---------|-----------|
| 后端 surefire | `[ERROR] io.busyming...FooTest.bar -- Time elapsed: 0.003 s <<< FAILURE!` | `io.busyming...FooTest#bar` |
| 后端 surefire (参数化) | `...FooTest.bar(int)[1] -- ...` | `io.busyming...FooTest#bar(int)[1]` |
| 后端 surefire XML | `<testcase classname="pkg.FooTest" name="bar">` | `pkg.FooTest#bar` |
| 前端 vitest >=4 | `FAIL  src/x.spec.ts [ src/x.spec.ts ]` | `src/x.spec.ts` (文件级) |
| 前端 vitest 2/3 | `FAIL  src/x.spec.ts > suite > name` | `src/x.spec.ts > suite > name` (用例级) |

**后端 XML 的坑**: surefire XML 的 `classname` 属性写的是**显示名**
(测试类上的 `@DisplayName("小改V2 · ...")`), 不是 Java 类的全限定名。
必须用**文件名** (`TEST-<FQN>.xml`) 反推 FQN, 否则同一个失败在 XML 侧与日志侧
会得到两个不同的标识, 差集恒不为空。

前端侧同理: vitest 的文件级失败与用例级失败是**两个粒度**。
统一口径为: **文件级失败 + 用例级失败都算**, 但文件级失败**不蕴含**用例级失败,
反之亦然。基线与本轮必须用同一粒度集合。
"""
import os
import re

# --- 后端 surefire 日志行 -------------------------------------------------
# [ERROR] <FQN>.<method> -- Time elapsed: ...
# method 可含参数化后缀: bar(int)[1]
RE_SUREFIRE_FAIL = re.compile(
    r"^\[ERROR\]\s+([A-Za-z0-9_][A-Za-z0-9_.$]*Test)\.([^\s]+)\s+--")

# --- 前端 vitest ----------------------------------------------------------
# vitest 2/3: "FAIL  src/x.spec.ts > suite > name"
RE_VITEST_FAIL_CASE = re.compile(r"^\s*FAIL\s+(\S+)\s*>\s*(.+?)\s*$")
# vitest >=4: "FAIL  src/x.spec.ts [ src/x.spec.ts ]"
RE_VITEST_FAIL_FILE = re.compile(r"^\s*FAIL\s+(\S+)\s*\[\s*\S+\s*\]\s*$")
# vitest >=4 用例级: "FAIL  src/x.spec.ts > suite > name [ src/x.spec.ts ]"
RE_VITEST_FAIL_CASE_BRACKET = re.compile(
    r"^\s*FAIL\s+(\S+)\s*>\s*(.+?)\s*\[\s*\S+\s*\]\s*$")

RE_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# 通用失败标记 (check-md-schema / lint 等非 vitest 门禁)
RE_MARK_FAIL = re.compile(r"^(?:✗|❌|×)\s*(.+)$")


def strip_ansi(text):
    return RE_ANSI.sub("", text)


def parse_surefire_log_ids(text):
    """从 maven surefire 日志提取失败测试标识。

    返回 `pkg.Class#method` 集合。参数化用例保留 `method(int)[1]` 后缀,
    因为「同一方法的第 1 个参数」与「第 2 个参数」是**不同的失败**。
    """
    out = set()
    for line in strip_ansi(text).splitlines():
        m = RE_SUREFIRE_FAIL.match(line.strip())
        if m:
            out.add(f"{m.group(1)}#{m.group(2)}")
    return out


def parse_vitest_log_ids(text):
    """从 vitest 日志提取失败标识。

    返回 (files, cases) 二元组:
      - files: 失败**文件**集合。含 vitest >=4 的文件级 FAIL 行,
        以及用例级 FAIL 行里出现的文件路径 (一个文件只要有用例失败,
        该文件就是失败文件)。
      - cases: 失败**用例**集合, 形如 `src/x.spec.ts > suite > name`。

    两个粒度**分开返回**, 不合并: 基线快照 (baseline-gates.json) 也是分开存的
    (`failing_test_files_*` / `failing_test_ids_*`), 差分必须同粒度对同粒度。
    """
    files = set()
    cases = set()
    for line in strip_ansi(text).splitlines():
        m = RE_VITEST_FAIL_CASE_BRACKET.match(line)
        if m:
            cases.add(f"{m.group(1)} > {m.group(2).strip()}")
            files.add(m.group(1))
            continue
        m = RE_VITEST_FAIL_FILE.match(line)
        if m:
            files.add(m.group(1))
            continue
        m = RE_VITEST_FAIL_CASE.match(line)
        if m:
            cases.add(f"{m.group(1)} > {m.group(2).strip()}")
            files.add(m.group(1))
    return files, cases


def parse_markdown_fail_ids(text):
    """从 markdown 门禁日志 (check-md-schema 等) 提取失败标识。"""
    out = set()
    for line in strip_ansi(text).splitlines():
        s = line.strip()
        m = RE_MARK_FAIL.match(s)
        if m:
            out.add(m.group(1).strip())
    return out


def parse_log_ids(text, kind):
    """按门禁类型分派到对应的解析器。

    kind 取值:
      - "surefire" (后端): 返回 `pkg.Class#method` 集合
      - "vitest"   (前端): 返回 (files, cases) 二元组
      - "markdown" (通用): 返回失败标记集合
    """
    if kind == "surefire":
        return parse_surefire_log_ids(text)
    if kind == "vitest":
        return parse_vitest_log_ids(text)
    if kind == "markdown":
        return parse_markdown_fail_ids(text)
    raise ValueError(f"unknown gate kind: {kind}")


# --- 后端 surefire XML ----------------------------------------------------

def _surefire_ids_from_files(paths):
    """从 surefire XML 文件列表提取失败标识集合。

    **必须**用 XML 文件名 (`TEST-<FQN>.xml`) 反推类的全限定名, 不能用
    `<testcase classname="...">`: 该属性是 `@DisplayName` 显示名,
    与 FQN 无关, 用它会导致同一失败在 XML 侧与日志侧标识不一致。

    返回 `pkg.Class#method` 集合; 参数化用例保留 `method(int)[1]` 后缀。

    这是**唯一**的实现。`parse_surefire_xml_ids` (扫业务仓目录) 与
    `parse_surefire_xml_files` (吃显式路径列表) 都调它 —— 两者口径
    必须**逐字一致**, 否则同一个失败在基线侧与归档侧得到两个不同标识,
    差集恒不为空 (基线自己的失败被误判成新失败)。
    """
    import xml.etree.ElementTree as ET

    out = set()
    for path in paths:
        base = os.path.basename(path)
        # TEST-io.busyming.x.FooTest.xml -> io.busyming.x.FooTest
        if not base.startswith("TEST-") or not base.endswith(".xml"):
            continue
        fqn = base[len("TEST-"):-len(".xml")]
        if "$" in fqn:
            # 嵌套类: io.busyming.x.FooTest$Inner -> FooTest$Inner
            pass
        try:
            root = ET.parse(path).getroot()
        except Exception:
            continue
        for tc in root.iter("testcase"):
            if tc.find("failure") is None and tc.find("error") is None:
                continue
            name = tc.get("name") or ""
            out.add(f"{fqn}#{name}")
    return out


def parse_surefire_xml_ids(repo_path, module_glob="busyming-merchandising-*"):
    """从业务仓的 surefire XML 报告提取失败标识集合。

    ⚠️ **只用于采集基线快照**。它扫的是业务仓工作区的
    `<module>/target/surefire-reports`, 那个目录**跨臂共享**。
    实验期的失败集必须从**归档**读 (`parse_surefire_xml_files`)。
    """
    import glob

    pattern = os.path.join(repo_path, module_glob,
                           "target", "surefire-reports", "TEST-*.xml")
    return _surefire_ids_from_files(sorted(glob.glob(pattern)))


def parse_surefire_xml_files(paths):
    """从**给定的** surefire XML 文件列表提取失败标识集合。

    与 `parse_surefire_xml_ids` 同口径 (用 XML 文件名反推 FQN),
    但接受**显式路径列表**而不是自己 glob 一个目录。

    为什么需要这个: 归档目录里的 XML 是**副本**, 路径与业务仓里的
    不同 (多了归档层级)。口径必须与基线快照 (`parse_surefire_xml_ids`)
    **完全一致**, 否则同一个失败在两侧得到两个标识, 差集恒不为空。
    所以这里复用同一段解析逻辑, 而不是再写一遍。
    """
    return _surefire_ids_from_files(paths)


# --- 规范化比较 ------------------------------------------------------------

def new_failures(current, baseline):
    """本轮相对基线**新增**的失败标识集合 (差集法)。"""
    return set(current) - set(baseline)


def fixed_failures(current, baseline):
    """本轮相对基线**消失**的失败标识集合 (基线失败被修好了)。"""
    return set(baseline) - set(current)


def diff_report(current, baseline):
    """返回 (新增, 消失, 新增数, 消失数)。"""
    cur, base = set(current), set(baseline)
    new = cur - base
    fixed = base - cur
    return new, fixed, len(new), len(fixed)
