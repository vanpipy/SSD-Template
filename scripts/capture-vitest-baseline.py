#!/usr/bin/env python3
"""从 vitest 日志提取失败测试集, 写入 baseline-gates.json。

vitest 2/3 与 vitest >=4 的日志格式不同, 本脚本兼容两者:
  - vitest 2/3: "FAIL  src/path/file.test.ts > suite > name"
  - vitest >=4: "FAIL  src/path/file.test.ts [ src/path/file.test.ts ]"

用法:
    python3 scripts/capture-vitest-baseline.py <log> <repo_path> <repo_alias>
    python3 scripts/capture-vitest-baseline.py --print <log>
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "docs", "efficacy", "baseline-gates.json")

# 汇总行, 形如:
#   Test Files  6 failed | 94 passed (100)
#   Tests  2 failed | 1856 passed (1858)
RE_FILES = re.compile(r"^\s*Test Files\s+(.*)$", re.M)
RE_TESTS = re.compile(r"^\s*Tests\s+(.*)$", re.M)
RE_DURATION = re.compile(r"^\s*Duration\s+(.*)$", re.M)

# "FAIL  src/x.test.ts > suite > name"  或  "FAIL  src/x.test.ts [ src/x.test.ts ]"
RE_FAIL = re.compile(r"^\s*FAIL\s+(\S+)(?:\s*\[.*\])?\s*$", re.M)
# "FAIL  src/x.test.ts > suite > name" (带用例名)
RE_FAIL_CASE = re.compile(r"^\s*FAIL\s+(\S+)\s*>\s*(.+)$", re.M)


# ANSI 转义序列 (vitest 彩色输出)
RE_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _counts(pattern, text, groups):
    m = pattern.search(text)
    if not m:
        return {g: 0 for g in groups}
    out = {}
    for g in groups:
        mm = re.search(r"(\d+)\s+" + g, m.group(1))
        out[g] = int(mm.group(1)) if mm else 0
    return out


def parse_log(text):
    """返回 (失败文件集合, 失败用例标识集合, 汇总数字)。"""
    text = RE_ANSI.sub("", text)
    failed_files = set()
    failed_cases = set()

    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("FAIL"):
            continue
        # vitest >=4: FAIL  src/x.test.ts [ src/x.test.ts ]
        m = re.match(r"^FAIL\s+(\S+)\s*\[", s)
        if m:
            failed_files.add(m.group(1))
            continue
        # vitest 2/3: FAIL  src/x.test.ts > suite > name
        m = re.match(r"^FAIL\s+(\S+)\s*>\s*(.+)$", s)
        if m:
            failed_cases.add(f"{m.group(1)} > {m.group(2).strip()}")
            failed_files.add(m.group(1))
            continue
        # 裸文件
        m = re.match(r"^FAIL\s+(\S+)\s*$", s)
        if m:
            failed_files.add(m.group(1))

    files = _counts(RE_FILES, text, ["failed", "passed", "skipped"])
    tests = _counts(RE_TESTS, text, ["failed", "passed", "skipped"])
    dur = ""
    m = RE_DURATION.search(text)
    if m:
        dur = m.group(1).strip()
    # vitest 4 在全是通过时只报 "35 passed (35)", 不带 failed 数字
    if not files["passed"] and not files["failed"]:
        m2 = re.search(r"^\s*Test Files\s+(\d+)\s+passed", text, re.M)
        if m2:
            files["passed"] = int(m2.group(1))
            files["total"] = files["passed"]
    if not tests["passed"] and not tests["failed"]:
        m2 = re.search(r"^\s*Tests\s+(\d+)\s+passed", text, re.M)
        if m2:
            tests["passed"] = int(m2.group(1))

    return failed_files, failed_cases, {
        "test_files_failed": files["failed"],
        "test_files_passed": files["passed"],
        "test_files_skipped": files["skipped"],
        "test_files_total": files["failed"] + files["passed"] + files["skipped"],
        "tests_failed": tests["failed"],
        "tests_passed": tests["passed"],
        "tests_skipped": tests["skipped"],
        "tests_total": tests["failed"] + tests["passed"] + tests["skipped"],
        "duration": dur,
    }


def head_of(repo_path):
    import subprocess
    try:
        return subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2

    if args[0] == "--print":
        with open(args[1], encoding="utf-8", errors="replace") as fh:
            ff, fc, totals = parse_log(fh.read())
        print(json.dumps({
            "failing_test_files": sorted(ff),
            "failing_test_cases": sorted(fc),
            "totals": totals,
        }, ensure_ascii=False, indent=2))
        return 0

    log_path, repo_path, alias = args[0], args[1], args[2]
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    ff, fc, totals = parse_log(text)

    data = {}
    if os.path.isfile(BASELINE):
        with open(BASELINE, encoding="utf-8") as fh:
            data = json.load(fh)

    key = alias  # 例如 H5 / PCOLD
    data[f"repo_{key}"] = {
        "path": repo_path,
        "head": head_of(repo_path),
    }
    data[f"totals_{key}"] = totals
    data[f"failing_test_files_{key}"] = sorted(ff)
    data[f"failing_test_cases_{key}"] = sorted(fc)
    data[f"failing_test_count_{key}"] = len(ff) + len(fc)
    data[f"log_{key}"] = os.path.relpath(log_path, ROOT)
    data["captured_at"] = data.get("captured_at")

    with open(BASELINE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"{alias}: 文件失败 {len(ff)}, 用例失败 {len(fc)} -> {BASELINE}")
    for f in sorted(ff):
        print(f"  FAIL {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
