#!/usr/bin/env python3
"""基线门禁的**来源校验** (check-baseline-provenance.py)

Stdlib only.

## 它守的是什么

`check-baseline-invariance.py` 守的是**自洽**: 基线快照 == 基线日志重解析。
但自洽**不证明来源**。一份快照和一份日志可以互相吻合, 同时**都来自错误的代码状态**。

这正是 v3 基线出过的真实事故:

| 基线 | 自洽 | 来源正确 |
|------|------|---------|
| v3 (HEAD 已提交版) | **否** —— 快照用 surefire XML 的 `classname` 显示名, 日志用 FQN, 7 条双向不一致 | **否** —— 采于**移动后的工作区 HEAD** (`fc0ed6161` / `1d4cead0`), 却标着冻结 SHA (`688154d7` / `59fdb760`) |
| v4 (当前工作区) | 是 —— 零新增零消失 | 是 —— 在冻结 SHA 的**独立 worktree** 里采集 |

后果很严重: v3 基线里 C 仓覆盖 608 个 spec 文件, 而冻结 SHA 上只有 430 个。
多出的 178 个文件**根本不存在于冻结基线**。用 v3 基线做差集,
**冻结基线上根本不存在的测试**会被算进 `D` (新增门禁失败), 系统性高估两臂的伤害。

所以这里要守一条独立的、更硬的不变量:

> **基线日志里引用的每一个测试文件 / 测试类, 都必须真实存在于冻结 SHA 的树里。**

## 为什么这条能自动抓住

- 前端: 日志里出现的 `src/xxx.spec.ts` / `src/xxx.test.tsx` 逐个拿去冻结 SHA 的树里查。缺失即违规。
- 后端: 日志里出现的 `io.busyming...XxxTest` 逐个去冻结 SHA 的树里查 (嵌套类
  用外层类判存在, 因为 surefire 的 `TEST-<FQN>$Nested.xml` 对应的源文件是外层类)。

不需要人肉判断某次采集"是不是在正确的 SHA 上跑"。

## 命名约定的坑

三个前端仓的测试文件命名**不统一**:

| 仓 | 命名 | 冻结 SHA 上的文件数 |
|----|------|-------------------|
| C (Vue PC) | `*.spec.ts` / `*.spec.tsx` | 430 |
| H5 (移动端) | `*.test.ts` / `*.test.tsx` | 100 |
| PCOLD (legacy PC) | `*.test.ts` / `*.test.tsx` | 4 |

只认 `.spec.` 会让 H5 和 PCOLD 的引用数变成 **0**, 来源校验**静默失效**。
所以这里同时认 `.spec.` 和 `.test.`, 且二者都必须在冻结 SHA 上存在。

## 用法

    python3 scripts/check-baseline-provenance.py
    python3 scripts/check-baseline-provenance.py --repo B
    python3 scripts/check-baseline-provenance.py --repo-path-root <dir>

退出码 0 = 每条基线日志的来源都与其标注的冻结 SHA 一致。1 = 有违规。
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EFF = os.path.join(ROOT, "docs", "efficacy")

# 后端日志里的测试类 FQN (含嵌套类 `$`)
RE_JAVA_TEST = re.compile(
    r"\bio\.busyming\.product\.merchandising\.[A-Za-z0-9_.$]*Test\b")
# 前端日志里的测试文件路径 (`.spec.` 与 `.test.` 两种命名都认)
# 路径前缀**不限定**在 `src/` 下: legacy PC 仓有 `scripts/vite/proxy.test.ts`,
# 它也是 vitest 会跑的测试文件。限定 `src/` 会把它漏掉。
#
# 但必须**认仓库相对路径**。日志里可能出现绝对路径
# (`/abs/path/to/repo/src/x.spec.ts`), 直接拿去比对冻结 SHA 的树会误报。
# 所以先抓「一段可能含 `/` 的路径」, 再把绝对路径剥成相对路径。
RE_SPEC_FILE = re.compile(r"[A-Za-z0-9_./@-]*[A-Za-z0-9_-]\.(?:spec|test)\.[jt]sx?")
# 日志里可能夹带 ANSI 颜色码, 会把路径切断, 解析前先剥掉
RE_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# 各仓: 日志文件, 解析类型
REPO_SPECS = {
    "B": {"log": "baseline-B-full.txt", "kind": "surefire"},
    "C": {"log": "baseline-C-full.txt", "kind": "vitest"},
    "H5": {"log": "baseline-H5-full.txt", "kind": "vitest"},
    "PCOLD": {"log": "baseline-PCOLD-full.txt", "kind": "vitest"},
}


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def java_test_fqns_at(repo, sha):
    """冻结 SHA 的树里存在的后端测试类 FQN 集合。

    源文件路径 `mod/src/test/java/pkg/A/B.java` -> `pkg.A.B`。
    嵌套类 (`pkg.A.B$Inner`) 归到**外层类** `pkg.A.B`, 因为 surefire 报的
    `TEST-pkg.A.B$Inner.xml` 来自外层类的源文件。
    """
    out = set()
    tree = git(repo, "ls-tree", "-r", "--name-only", sha)
    for p in tree.splitlines():
        if "/src/test/java/" not in p or not p.endswith(".java"):
            continue
        fqn = p.split("/src/test/java/", 1)[1][:-5].replace("/", ".")
        out.add(fqn)
        out.add(fqn + "$")  # 允许 `fqn$Nested` 前缀匹配
    return out


def spec_files_at(repo, sha):
    """冻结 SHA 的树里存在的测试文件路径集合。"""
    tree = git(repo, "ls-tree", "-r", "--name-only", sha)
    return {p for p in tree.splitlines() if RE_SPEC_FILE.search(p)}


def test_files_at(repo, sha):
    """冻结 SHA 的树里存在的**全部**测试文件路径集合 (不限 `src/` 前缀)。

    与 `spec_files_at` 的区别: 这里的正则只要看到 `.spec.` / `.test.` 后缀
    就认, 不要求路径以 `src/` 开头。用来算「覆盖率分母」。
    """
    tree = git(repo, "ls-tree", "-r", "--name-only", sha)
    return {p for p in tree.splitlines()
            if re.search(r"\.(?:spec|test)\.[jt]sx?$", p)}


def outer(fqn):
    """嵌套类 FQN -> 外层类 FQN。"""
    return fqn.split("$", 1)[0]


def to_repo_relative(path, present):
    """把日志里的路径归一成**仓库相对路径**。

    日志里同一份测试文件可能以两种形态出现:

    - 相对路径 `src/foo/bar.spec.ts` (vitest 的默认输出)
    - 绝对路径 `/abs/path/to/repo/src/foo/bar.spec.ts`

    绝对路径的前缀**不固定**: 采集时可能在业务仓工作区, 也可能在
    冻结 SHA 的临时 worktree (如 `/…/scratch/gate-recapture/C/`),
    还可能是符号链接形式。所以不能靠「已知仓库路径前缀」去剥。

    改成**按树里的真实路径反查**: 从最长的后缀开始试, 取第一个在
    冻结 SHA 的树里存在的那个。冻结 SHA 的树存的是完整相对路径,
    所以最长匹配后缀就是正确的仓库相对路径。

    找不到任何匹配时原样返回, 后续会被报成「不存在」。
    """
    if not path.startswith("/"):
        return path
    parts = path.split("/")
    # parts[0] 是空串 (前导 /), 从 i=1 起逐级缩短后缀。
    for i in range(1, len(parts)):
        suffix = "/".join(parts[i:])
        if suffix in present:
            return suffix
    return path


def check_repo(alias, spec, commits, repo_root_override=None):
    problems = []
    log_path = os.path.join(EFF, "gates", spec["log"])
    if not os.path.isfile(log_path):
        return False, [f"{alias}: 基线日志不存在: {log_path}"], {}

    base = ((commits.get("baselines", {}) or {}).get(alias, {}) or {})
    sha = base.get("commit")
    repo = base.get("path")
    if repo_root_override:
        repo = os.path.join(repo_root_override, base.get("repo", ""))
    if not sha or not repo:
        return False, [f"{alias}: baseline-commits.json 里缺少 commit/path"], {}

    if not os.path.isdir(os.path.join(repo, ".git")) and \
       not os.path.isdir(os.path.join(repo, ".git")):
        # worktree 的 .git 是文件, 两种都接受
        if not os.path.exists(os.path.join(repo, ".git")):
            return False, [f"{alias}: 业务仓不存在: {repo}"], {}

    text = read(log_path)
    # 剥掉 ANSI 颜色码再解析, 否则路径会被转义序列切断。
    text = RE_ANSI.sub("", text)
    if spec["kind"] == "surefire":
        refs = set(RE_JAVA_TEST.findall(text))
        present = java_test_fqns_at(repo, sha)
        def exists(f):
            base_fqn = outer(f)
            return (base_fqn in present or f in present
                    or any(p.startswith(base_fqn + "$") for p in present))
        unit = "测试类"
    else:
        present = spec_files_at(repo, sha)
        refs = {to_repo_relative(r, present) for r in RE_SPEC_FILE.findall(text)}
        def exists(f):
            return f in present
        unit = "spec 文件"

    missing = sorted(r for r in refs if not exists(r))
    for m in missing[:20]:
        problems.append(
            f"{alias}: 基线日志引用了冻结 SHA {sha[:8]} 上**不存在**的{unit}: {m}")
    if len(missing) > 20:
        problems.append(f"{alias}: ... 还有 {len(missing) - 20} 个未列出")

    stats = {
        "referenced": len(refs),
        "present_at_frozen": len(refs) - len(missing),
        "violations": len(missing),
        "sha": sha,
    }
    # **零引用 = 校验静默失效**。这正是 H5 / PCOLD 曾经的真实状态:
    # 日志里写的是 `.test.tsx`, 而解析器只认 `.spec.`, 于是 refs 为空,
    # 「没有违规」被当成了「来源正确」。这种假绿必须显式失败。
    if not refs:
        problems.append(
            f"{alias}: 基线日志里**一个测试单元都没解析出来** (引用数 = 0)。"
            f"这说明解析规则与该仓的日志格式不匹配, 来源校验等于没跑。"
            f"不能据此判定「来源正确」。")

    # **覆盖率分母**: 冻结 SHA 上到底有多少个测试文件。
    # 本检查证明的是「日志引用的每个单元都真实存在于冻结 SHA」,
    # 它**不**证明「基线跑遍了冻结 SHA 上的每个测试文件」——
    # vitest 的点状 reporter 只给**产生了输出**的文件打名字,
    # 沉默通过的文件根本不出现在日志里。
    # 所以分母必须单独算, 并且明确报出来, 不能让「引用数」被读成「覆盖数」。
    if spec["kind"] != "surefire":
        universe = test_files_at(repo, sha)
        covered = universe & refs
        stats["universe_at_frozen"] = len(universe)
        stats["covered"] = len(covered)
        stats["coverage_pct"] = (
            round(100.0 * len(covered) / len(universe), 1) if universe else None)
        uncovered = sorted(universe - refs)
        if uncovered:
            # 这是**说明性**的, 不是违规: 沉默通过的文件不在日志里。
            # 但必须报出来, 否则覆盖率会被高估。
            stats["uncovered_examples"] = uncovered[:3]
            stats["uncovered_count"] = len(uncovered)
    else:
        universe = java_test_fqns_at(repo, sha)
        # `java_test_fqns_at` 为了匹配嵌套类, 每个外层类同时登记了
        # `fqn` 与 `fqn$` 两条, 所以直接用它当分母会把数量翻倍。
        # 分母要用**真实的外层类数**。
        universe = {p.split("$", 1)[0] for p in universe}
        covered = {f for f in refs if exists(f)}
        stats["universe_at_frozen"] = len(universe)
        stats["covered"] = len(covered)
        stats["coverage_pct"] = (
            round(100.0 * len(covered) / len(universe), 1) if universe else None)
        stats["uncovered_count"] = len(universe - covered)
        stats["uncovered_examples"] = sorted(universe - covered)[:3]
    return (not problems), problems, stats


def main():
    ap = argparse.ArgumentParser(description="基线门禁来源校验")
    ap.add_argument("--repo", action="append", default=[],
                    help="只校验指定仓 (可重复), 默认全部")
    ap.add_argument("--repo-path-root", default=None,
                    help="业务仓根目录 (默认用 baseline-commits.json 里的绝对路径)")
    args = ap.parse_args()

    commits_path = os.path.join(EFF, "baseline-commits.json")
    if not os.path.isfile(commits_path):
        print(f"[fatal] 找不到 {commits_path}", file=sys.stderr)
        return 2
    with open(commits_path, encoding="utf-8") as fh:
        commits = json.load(fh)

    aliases = args.repo or list(REPO_SPECS)
    all_problems = []
    print("== 基线门禁来源校验 ==")
    for alias in aliases:
        spec = REPO_SPECS.get(alias)
        if not spec:
            print(f"  {alias}: 未知仓")
            all_problems.append(f"未知仓: {alias}")
            continue
        ok, problems, stats = check_repo(alias, spec, commits, args.repo_path_root)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {alias}: 日志引用 {stats.get('referenced')} 个测试单元, "
              f"冻结 SHA {str(stats.get('sha'))[:8]} 上存在 "
              f"{stats.get('present_at_frozen')} 个, 违规 {stats.get('violations')} 个")
        # 覆盖率单独一行报。**引用数 != 覆盖数**:
        # vitest 只给产生输出的文件打名字, 沉默通过的文件不在日志里。
        cov = stats.get("coverage_pct")
        if cov is not None:
            unc = stats.get("uncovered_count", 0)
            extra = ""
            if unc:
                ex = stats.get("uncovered_examples") or []
                extra = (f" (未在日志中出现的 {unc} 个, 例如 "
                         f"{', '.join(ex)}{' ...' if unc > len(ex) else ''})")
            print(f"         覆盖: 冻结 SHA 上共 {stats.get('universe_at_frozen')} 个测试文件, "
                  f"日志点名 {stats.get('covered')} 个 ({cov}%){extra}")
        all_problems.extend(problems)

    if all_problems:
        print("\n问题明细:", file=sys.stderr)
        for p in all_problems:
            print(f"  - {p}", file=sys.stderr)
        print("\n[FAIL] 基线门禁来源与冻结 SHA 不一致, **不要冻结**", file=sys.stderr)
        return 1
    print("\n[OK] 每条基线日志的来源都与其标注的冻结 SHA 一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
