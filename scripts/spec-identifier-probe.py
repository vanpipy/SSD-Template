#!/usr/bin/env python3
"""规格标识符反查器 (spec-identifier-probe.py)

**为什么需要这个脚本**: v2 候选池靠人工逐条读规格, 漏检严重, 且常把「已实现」误判为缺失。
本脚本做**机械化、大批量**的反查: 从规格正文里抽取**具体的标识符**
(字段名 / 端点路径 / 枚举值 / 类名 / 方法名), 逐个到各代码仓里查。

**它不是判决器**, 但它把「候选缺口」的**发现成本**从人工几小时降到几分钟, 并且
天然规避了「泛词误判」(只查具体标识符, 不查「数量」「失败原因」这类词)。

用法:
    python3 scripts/spec-identifier-probe.py                    # 全量扫描
    python3 scripts/spec-identifier-probe.py --spec <relpath>    # 只扫某份规格
    python3 scripts/spec-identifier-probe.py --json out.json
    python3 scripts/spec-identifier-probe.py --min-hits 0        # 报出零命中标识符

判定:
    一个标识符在**所有**代码仓都零命中 → 该标识符对应的规格要求**无承载点** → 候选缺口信号。
    命中 → 该能力已有实现点, 排除。
"""
import argparse
import json
import os
import re
import subprocess
import sys

WORKSPACE = "/home/leroy/Project/merchandising-workspace"
SPEC_ROOT = os.path.join(WORKSPACE, "merchandising-spec", "产品真源")

REPOS = {
    "B": os.path.join(WORKSPACE, "busyming-merchandising"),
    "C": os.path.join(WORKSPACE, "busyming-merchandising-vue-pc"),
    "H5": os.path.join(WORKSPACE, "busyming-merchandising-h5"),
    "PC": os.path.join(WORKSPACE, "busyming-merchandising-pc"),
}

SOURCE_GLOBS = [
    "-g", "*.java", "-g", "*.ts", "-g", "*.tsx", "-g", "*.vue", "-g", "*.js",
    "-g", "*.jsx", "-g", "*.kt", "-g", "*.sql", "-g", "*.xml", "-g", "*.yml",
]

# 规格正文中值得反查的标识符形态
IDENT_PATTERNS = [
    # 反引号包裹的代码标识符: `fooBar` / `foo_bar()` / `/path/to/api`
    re.compile(r"`([A-Za-z_][A-Za-z0-9_./()\-]{2,60})`"),
    # 形如 xxx.yyy 的驼峰/下划线复合标识符
    re.compile(r"\b([a-z][A-Za-z0-9]{2,30}[A-Z][A-Za-z0-9]{0,30})\b"),
    # 形如 XxxYyy 的 PascalCase
    re.compile(r"\b([A-Z][a-z]+[A-Z][A-Za-z0-9]{2,40})\b"),
]

# 明显不是标识符的词 (泛词 / 中文 / 常见技术词)
STOPWORDS = {
    "API", "URL", "HTTP", "JSON", "MQ", "RPC", "SQL", "UI", "UX", "PDF", "Excel",
    "React", "Vue", "Java", "TypeScript", "Spring", "MyBatis", "Redis", "MQTT",
    "Prisma", "TODO", "PM", "QA", "PRD", "UI", "ID", "OK", "P0", "P1", "P2",
    "GET", "POST", "PUT", "DELETE", "PUSH", "MOM", "YAML", "CSV", "PNG", "SVG",
}

# 只保留这些「有反查价值」的标识符 (小写开头驼峰 / 下划线 / 全大写常量 / 路径)
VALUABLE = re.compile(
    r"^(?:[a-z][A-Za-z0-9]{3,40}|[A-Za-z]+_[A-Za-z_]+|[A-Z][A-Z0-9_]{3,40}|/[a-zA-Z0-9_/{}.\-]+)$"
)


def is_comment(text):
    t = text.strip()
    return (t.startswith("//") or t.startswith("*") or t.startswith("/*")
            or t.startswith("<!--") or t.startswith("--")
            or t.startswith("|") or t.startswith(">"))


def rg_count(repo, pattern, timeout=60):
    """在仓库里搜索字面标识符, 返回命中数 (只计非注释行)。"""
    if not os.path.isdir(repo):
        return 0, []
    cmd = ["rg", "-n", "--no-messages", "--fixed-strings"] + SOURCE_GLOBS + [pattern]
    cmd.append(".")
    try:
        p = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return -1, []
    hits = []
    for line in p.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        if is_comment(parts[2]):
            continue
        hits.append(f"{parts[0]}:{parts[1]}")
    return len(hits), hits[:3]


def extract_identifiers(text):
    """从规格正文抽取候选标识符。"""
    found = {}
    for pat in IDENT_PATTERNS:
        for m in pat.finditer(text):
            raw = m.group(1)
            ident = raw.strip()
            if not ident or ident in STOPWORDS:
                continue
            if not VALUABLE.match(ident):
                continue
            # 去掉尾部标点与参数列表
            ident = ident.split("(")[0].rstrip(".,;:")
            if not ident or len(ident) < 4:
                continue
            # 纯中文或纯数字段不算
            if re.match(r"^[\u4e00-\u9fff]+$", ident):
                continue
            found.setdefault(ident, 0)
            found[ident] += 1
    return found


def scan_spec(relpath, min_freq=1):
    path = os.path.join(SPEC_ROOT, relpath)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    idents = extract_identifiers(text)
    idents = {k: v for k, v in idents.items() if v >= min_freq}
    results = []
    for ident, freq in sorted(idents.items()):
        hits_total = 0
        per_repo = {}
        samples = []
        for label, repo in REPOS.items():
            if not os.path.isdir(repo):
                continue
            n, s = rg_count(repo, ident)
            per_repo[label] = n
            hits_total += n
            samples.extend(f"{label}:{x}" for x in s[:2])
        results.append({
            "identifier": ident,
            "spec_freq": freq,
            "hits": hits_total,
            "per_repo": per_repo,
            "samples": samples[:4],
        })
    results.sort(key=lambda r: (r["hits"], -r["spec_freq"]))
    return {
        "spec": relpath,
        "total_identifiers": len(results),
        "zero_hit": [r for r in results if r["hits"] == 0],
        "all": results,
    }


def iter_specs():
    """遍历 产品真源 下所有 .md。"""
    out = []
    for root, dirs, files in os.walk(SPEC_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                out.append(os.path.relpath(os.path.join(root, f), SPEC_ROOT))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description="规格标识符反查器")
    ap.add_argument("--spec", help="只扫某份规格 (相对 产品真源 的路径)")
    ap.add_argument("--json", help="输出 JSON 到该文件")
    ap.add_argument("--min-hits", type=int, default=0,
                    help="只报出命中数 <= 该值的标识符 (默认 0 = 只报零命中)")
    ap.add_argument("--min-freq", type=int, default=1,
                    help="规格中出现次数下限")
    args = ap.parse_args()

    specs = [args.spec] if args.spec else iter_specs()
    all_out = []
    for rel in specs:
        res = scan_spec(rel, args.min_freq)
        if res is None:
            print(f"[skip] {rel}", file=sys.stderr)
            continue
        gaps = [r for r in res["all"] if r["hits"] <= args.min_hits]
        all_out.append(res)
        if gaps:
            print(f"\n=== {rel}  ({len(gaps)} 个标识符零命中 / 共 {res['total_identifiers']}) ===")
            for g in gaps[:40]:
                print(f"  {g['identifier']:<45} 规格出现 {g['spec_freq']} 次")

    total_gap = sum(len([r for r in o["all"] if r["hits"] <= args.min_hits]) for o in all_out)
    print(f"\n合计: {total_gap} 个零命中标识符 / {sum(o['total_identifiers'] for o in all_out)} 个标识符 "
          f"/ {len(all_out)} 份规格")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(all_out, fh, ensure_ascii=False, indent=2)
        print(f"已写入 {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
