#!/usr/bin/env python3
"""在冻结态取某文件某几行的精确内容 (带真实行号)。

Stdlib only。用法:

    python3 scripts/show-frozen-lines.py <repo_key> <path> <start> <end>
    python3 scripts/show-frozen-lines.py <repo_key> <path> <start> <end> --grep <kw>

repo_key 取自 docs/efficacy/baseline-commits.json 的 baselines (B / C / H5 / PCOLD)。
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_JSON = os.path.join(ROOT, "docs", "efficacy", "baseline-commits.json")


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    repo_key, path = argv[1], argv[2]
    start = int(argv[3])
    end = int(argv[4]) if len(argv) > 4 else start
    grep_kw = None
    if "--grep" in argv:
        grep_kw = argv[argv.index("--grep") + 1]

    with open(BASE_JSON, encoding="utf-8") as fh:
        baselines = json.load(fh)["baselines"]
    if repo_key not in baselines:
        print(f"未知仓 {repo_key}, 可选: {list(baselines)}", file=sys.stderr)
        return 2
    meta = baselines[repo_key]
    r = subprocess.run(
        ["git", "-C", meta["path"], "show", f"{meta['commit']}:{path}"],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(f"读取失败: {path} @ {repo_key}", file=sys.stderr)
        print(r.stderr, file=sys.stderr)
        return 1
    src = r.stdout.splitlines()
    print(f"# {repo_key}@{meta['commit'][:7]} {path} (共 {len(src)} 行)")
    for i in range(start, min(end, len(src)) + 1):
        line = src[i - 1]
        mark = "  "
        if grep_kw and grep_kw in line:
            mark = ">>"
        print(f"{mark}{i:5d}: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
