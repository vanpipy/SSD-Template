#!/usr/bin/env python3
"""Acceptance checker for the SSD-Template v4 refactor.

Implements the executable acceptance criteria from docs/mechanism-contract.md
section 6 (AC1..AC12). Stdlib only. Run from the repo root.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def grep_result(pattern, paths, regex=False):
    """Return matching lines across paths."""
    hits = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in files:
                    if f.endswith((".md", ".sh", ".py", ".toml")):
                        fp = os.path.join(root, f)
                        for i, line in enumerate(read(fp).splitlines(), 1):
                            if re.search(pattern, line) if regex else (pattern in line):
                                hits.append(f"{fp}:{i}: {line.strip()[:150]}")
        elif os.path.isfile(p):
            for i, line in enumerate(read(p).splitlines(), 1):
                if re.search(pattern, line) if regex else (pattern in line):
                    hits.append(f"{p}:{i}: {line.strip()[:150]}")
    return hits


BUSINESS_TERMS = [
    "busyming", "yuque", "store-order-h5", "requirement-center",
    "神策", "ARMS", "陈列域", "门店订货", "订货草稿", "品牌切换", "门店切换",
]

SKIP_DIRS = {".git", "legacy", "legacy-simple", "node_modules", ".venv"}


def walk_files():
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            yield os.path.join(root, f)


# --- AC1: v4 schema self-consistent -----------------------------------------
td_tmp = "/tmp/ssd-verify/td"
os.makedirs(td_tmp, exist_ok=True)
for sub in ("README.md", "ards.md", "apis.md", "data-model.md"):
    src = os.path.join(ROOT, "schema/tech_design", sub)
    if os.path.isfile(src):
        with open(src, encoding="utf-8") as fin, open(os.path.join(td_tmp, sub), "w", encoding="utf-8") as fout:
            fout.write(fin.read())
rc, out = run(f"./scripts/check-md-schema.sh {td_tmp}")
check("AC1 v4 schema self-consistent", rc == 0, f"exit={rc}\n{out[-600:]}")

# --- AC2: plan paths resolve -------------------------------------------------
plan = read("schema/plan.md")
links = re.findall(r"\]\((\.\./[^)#]+)\)", plan)
broken = []
for l in links:
    # plan.md lives at plan/{date}-{topic}/{topic}.md -> two levels up
    if l.startswith("../../"):
        target = os.path.normpath(os.path.join("plan/_probe_", l))
    elif l.startswith("../"):
        target = os.path.normpath(os.path.join("plan/_probe_/x", l))
    else:
        target = l
    if "{" in target or "}" in target:
        # placeholder: strip the placeholder segment and check the dir exists
        seg = [s for s in target.split("/") if "{" not in s]
        target = os.path.join(*seg) if seg else target
    if not os.path.exists(target):
        broken.append(f"{l} -> {target}")
check("AC2 plan TD paths resolve", not broken, "; ".join(broken) or "all resolve")

# --- AC3: no dangling script references -------------------------------------
refs = set()
for f in walk_files():
    if not f.endswith((".md", ".sh", ".py")):
        continue
    rel = os.path.relpath(f, ROOT)
    if rel.split(os.sep)[0] in ("legacy", "legacy-simple"):
        continue
    for m in re.finditer(r"scripts/([A-Za-z0-9_.-]+\.sh)", read(f)):
        refs.add((rel, m.group(1)))
missing = sorted({f"{r} -> scripts/{s}" for r, s in refs if not os.path.isfile(os.path.join(ROOT, "scripts", s))})
check("AC3 no dangling script references", not missing, "; ".join(missing) or f"{len(refs)} refs ok")

# --- AC4: no dangling section references ------------------------------------
agents = read("AGENTS.md")
heads = set(re.findall(r"^#{2,4}\s+(\d+(?:\.\d+)*)", agents, re.M))
sec_refs = set()
for f in walk_files():
    rel = os.path.relpath(f, ROOT)
    if not rel.startswith("skills" + os.sep):
        continue
    for m in re.finditer(r"§(\d+(?:\.\d+)*)", read(f)):
        sec_refs.add((rel, m.group(1)))
bad_sec = sorted({f"{r} -> §{s}" for r, s in sec_refs if s not in heads})
check("AC4 no dangling section references", not bad_sec, "; ".join(bad_sec) or f"{len(sec_refs)} refs ok")

# --- AC5: baseline script has no hardcoded repo names ------------------------
bl = read("scripts/check-repo-baseline.sh")
hardcoded = [t for t in ["busyming", "store-order", "merchandising", "requirement-center", "pos-wiki"] if t in bl]
check("AC5 baseline script not hardcoded", not hardcoded, "; ".join(hardcoded) or "clean")

# --- AC6: ledger script not business-coupled --------------------------------
sp = read("scripts/sync-prd.sh")
bad_src = [t for t in ["yuque", "busyming"] if t in sp]
has_11 = sp.count("|") >= 0
check("AC6 ledger script no business coupling", not bad_src, "; ".join(bad_src) or "clean")

# --- AC7: all validators pass -----------------------------------------------
for script in ["check-md-schema.sh", "check-naming.sh", "check-traceability.sh",
               "check-repo-baseline.sh", "sync-prd.sh"]:
    path = os.path.join(ROOT, "scripts", script)
    if not os.path.isfile(path):
        check(f"AC7 {script} exists", False, "missing")
        continue
    rc, out = run(f"./scripts/{script}")
    check(f"AC7 {script} exit 0", rc == 0, f"exit={rc}\n{out[-500:]}")

# --- AC8: zero business terms ------------------------------------------------
# docs/mechanism-contract.md is exempt: it is the meta-document that NAMES the
# excluded terms in order to forbid them. Exempting it explicitly (not silently)
# keeps AC8 meaningful for every template asset.
#
# This checker is exempt too: it must NAME the terms to search for them.
# Without the list, AC8 could not be implemented.
EXEMPT_AC8 = {"docs/mechanism-contract.md", "scripts/check-acceptance.py"}

# --- AC8 扫描范围 ---------------------------------------------------------
# AC8 的目的是「可复用资产不得泄漏特定项目的业务词汇」。fork 后需要区分两类文件:
#   可复用资产  -> 必须零业务词 (schema/ skills/ scripts/ + 层 README 模板 + 根文档)
#   项目自有内容 -> 允许业务词 (spec 正文、仓库绑定信息)
# 若不区分, fork 的 AGENTS.md §1.1 必须写出真实仓名, 会被误判为「模板残留」。
AC8_ASSET_DIRS = ("schema", "skills", "scripts", "docs")
# 这些目录下的 README 是模板随仓分发的样板, 属于可复用资产
AC8_LAYER_READMES = (
    "README.md",
    "HOW_TO_USE.md",
    "new-factors.md",
    "prd/README.md",
    "tech_design/README.md",
    "plan/README.md",
    "test_cases/README.md",
    "material/README.md",
    "deep/README.md",
)
# AGENTS.md 中与真实仓库绑定的小节 (§1.1 清单 / §1.2 引用 / §1.3 AGENTS 路径 / §1.4 clone URL)
# 按项目实际填写, 允许出现真实仓名。其余部分仍需零业务词。
AC8_AGENTS_EXEMPT_HEADINGS = ("### 1.1", "### 1.2", "### 1.3", "### 1.4")


def ac8_agents_lines(path):
    """Yield (lineno, line) for AGENTS.md, skipping repo-binding sections.

    豁免区从 "### 1.x" 标题开始, 到下一个**同级或更高级**的 "### " 标题结束。
    区内的 "####" 子标题属于区的一部分, 不结束豁免。

    注意: 围栏代码块内的 "# 注释" 不是标题, 需跟踪 ``` 状态。
    """
    in_exempt = False
    exempt_level = 0
    in_fence = False
    for i, line in enumerate(read(path).splitlines(), 1):
        stripped = line.lstrip()
        # 跟踪围栏代码块: 块内的 "# xxx" 是 shell 注释, 不是 markdown 标题
        if stripped.startswith("```"):
            in_fence = not in_fence
            if in_exempt:
                continue
            yield i, line
            continue
        if in_fence:
            if in_exempt:
                continue
            yield i, line
            continue
        if stripped.startswith("#"):
            parts = stripped.split(None, 2)
            head = parts[0]
            num = parts[1] if len(parts) > 1 else ""
            ident = f"{head} {num}".strip()
            level = len(head)
            if ident in AC8_AGENTS_EXEMPT_HEADINGS:
                in_exempt = True
                exempt_level = level
                continue
            # 只有 "###" 及更高级标题才结束豁免区; "####" 子标题留在区内
            if in_exempt and level <= exempt_level and level <= 3:
                in_exempt = False
        if in_exempt:
            continue
        yield i, line


hits = []
for d in AC8_ASSET_DIRS:
    dpath = os.path.join(ROOT, d)
    if not os.path.isdir(dpath):
        continue
    for root, dirs, files in os.walk(dpath):
        dirs[:] = [x for x in dirs if x not in {".git", "node_modules"}]
        for f in files:
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, ROOT)
            if rel in EXEMPT_AC8 or not f.endswith((".md", ".sh", ".py")):
                continue
            for term in BUSINESS_TERMS:
                for i, line in enumerate(read(fp).splitlines(), 1):
                    if term in line:
                        hits.append(f"{rel}:{i}: {term}")

for rel in AC8_LAYER_READMES:
    fp = os.path.join(ROOT, rel)
    if not os.path.isfile(fp):
        continue
    for term in BUSINESS_TERMS:
        for i, line in enumerate(read(fp).splitlines(), 1):
            if term in line:
                hits.append(f"{rel}:{i}: {term}")

agents_fp = os.path.join(ROOT, "AGENTS.md")
if os.path.isfile(agents_fp):
    for term in BUSINESS_TERMS:
        for i, line in ac8_agents_lines(agents_fp):
            if term in line:
                hits.append(f"AGENTS.md:{i}: {term}")
check("AC8 zero business terms", not hits, "; ".join(hits[:10]) or "clean (contract + checker exempt)")

# --- AC9: layer READMEs consistent ------------------------------------------
prd_readme = read("prd/README.md")
check("AC9 prd README no -processed", "-processed" not in prd_readme,
      "still present" if "-processed" in prd_readme else "clean")

# --- AC10: root README has stats markers + matrix ---------------------------
root_readme = read("README.md")
check("AC10 root README exists", bool(root_readme), "" if root_readme else "missing")
check("AC10 stats begin marker", root_readme.count("<!-- prd-stats:begin -->") == 1,
      f"count={root_readme.count('<!-- prd-stats:begin -->')}")
check("AC10 stats end marker", root_readme.count("<!-- prd-stats:end -->") == 1,
      f"count={root_readme.count('<!-- prd-stats:end -->')}")
check("AC10 matrix chapter", "## PRD关联矩阵" in root_readme, "")
check("AC10 edge table subsection", "### 关系边表" in root_readme, "")

# --- AC11: traceability T numbers all implemented ---------------------------
tr = read("scripts/check-traceability.sh")
header = tr.split("set -uo pipefail")[0] if "set -uo pipefail" in tr else tr[:3000]
declared = set(re.findall(r"^\s*#\s*(T\d+)\.", header, re.M))
implemented = set(re.findall(r"^# --- ((?:T\d+)(?:\s*\+\s*T\d+)*)", tr, re.M))
# a block like "# --- T7 + T8:" contributes both T7 and T8
expanded = set()
for blk in implemented:
    expanded.update(re.findall(r"T\d+", blk))
implemented = expanded
unimpl = sorted(declared - implemented)
check("AC11 all declared T implemented", not unimpl, f"declared={sorted(declared)} missing={unimpl}")

# --- AC12: template repo itself has zero violations -------------------------
print()
print("=" * 78)
fails = 0
for name, ok, detail in results:
    mark = "PASS" if ok else "FAIL"
    if not ok:
        fails += 1
    print(f"[{mark}] {name}")
    if detail and (not ok or os.environ.get("VERBOSE")):
        for line in detail.rstrip().splitlines():
            print(f"       {line}")
print("=" * 78)
print(f"{len(results) - fails}/{len(results)} checks passed")
sys.exit(1 if fails else 0)
