#!/usr/bin/env python3
"""SSD 效能测量工具 (measure.py)

从 git 与门禁日志**确定性**计算单轮观测量, 供 docs/efficacy/FORMULA.md 使用。
Stdlib only. Run from the spec repo root.

用法:
  # 单轮测量
  python3 scripts/measure.py round --round-id F-01 --arm ssd \
      --repo B --repo-path ../merchandising-workspace/busyming-merchandising \
      --baseline <sha> --head <sha> \
      --checklist docs/efficacy/rounds/F-01-ssd.checklist.md \
      --repo-paths B=/path/to/backend,C=/path/to/frontend \
      --gate-log docs/efficacy/gates/F-01-ssd.txt

  # 基线门禁快照
  python3 scripts/measure.py baseline --repo B --repo-path <path> \
      --gate-log <file> --out docs/efficacy/baseline-gates.json

  # 聚合
  python3 scripts/measure.py aggregate --rounds docs/efficacy/rounds \
      --out docs/efficacy/summary.json

## v5 的三处修正 (相对 v4)

1. **AC 解析**: 旧的 `parse_prd_acs` 只认 Markdown 复选框 (`- [x] ...`),
   而 RUBRIC.md 用**表格行**列 AC, 于是解析出 0 条 AC, `A_spec` 恒为 0,
   `CE` 恒为 0。现在改用 `scripts/rubric.py` 解析共享检查表。
   **解析出 0 条 AC 时直接报错**, 不再静默产出 `CE=0`。
2. **门禁失败标识**: 旧的 `parse_gate_log` 直接把原始日志行当标识, 且
   surefire XML 用 `classname` 属性 (那是 `@DisplayName` **显示名**, 不是 FQN),
   导致基线与本轮的标识口径不一致, 差集恒不为空。
   现在统一走 `scripts/gate_ids.py` 的规范化标识。
3. **基线自洽**: 新增 `scripts/check-baseline-invariance.py`, 证明
   基线快照 == 基线日志重解析, 零新增零消失。差集法的前提。
"""
import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_archive as GA  # noqa: E402
import gate_ids as G  # noqa: E402
import rubric as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- 冻结基线快照的内容哈希 -----------------------------------------------
#
# `docs/efficacy/baseline-gates.json` 是**差集法的参照系**: `D` 由
# 「本臂门禁失败集 - 基线失败集」算出来。如果两臂的参照系不是同一份
# 字节, DR / CE 就是拿两把不同的尺子量出来的, 比出来的差值没有意义。
#
# 危险场景不是理论上的: `run-round.sh baseline` 正好写这个路径。所以
# 有人 (或某个脚本) 在两臂之间重跑一次 baseline, 两臂就会对着**不同的**
# 基线, 而 `aggregate` 只按 `round_id` + `arm` 配对, 照样出数, 不报错。
#
# 所以这里把哈希**写死**在测量脚本里 (脚本本身也在冻结集内), 测量时
# 逐字节核对, 不一致直接拒绝测量。
#
# 这个常量对应 `docs/efficacy/baseline-gates.json` 在冻结提交中的字节。
FROZEN_BASELINE_GATES_SHA256 = (
    "8cf5005930af988c4674c8c4f42b4da5ce588fe6fad965271c94e993d4d95fe1"
)

# --- 证据锚点格式: {标识}@{SHA}:{路径}#L{行号} ------------------------------
# 标识允许多字符 (B / C / H5 / PC / PCOLD), 不能只限单个大写字母。
ANCHOR_RE = re.compile(r"\{([A-Z][A-Z0-9]{0,7})\}@([0-9a-f]{7,40}):([^\s#]+)#L(\d+)")

# --- 基线 flake 隔离清单 ----------------------------------------------------
#
# 冻结基线自身就有**间歇性失败**的用例。它们在基线快照里**不出现**
# (快照只采了一次), 所以某一臂恰好触发时, 差集法会把它算成「新失败」。
#
# 隔离在**分子侧**做: 把这些标识从本臂失败集里减掉, 再做差集。
# 分母 (基线快照) **不动**。它是「基线曾经是什么样」的历史事实。
#
# 口径见 FORMULA.md §3.4.9。清单逐条列名、冻结、只能增不能删、两臂对称。
FLAKY_LIST_REL = os.path.join("docs", "efficacy", "flaky-tests.json")

# 纯文档/配置/依赖类提交不计入返工
REWORK_EXCLUDE_PATTERNS = [
    r"^docs?/", r"^README", r"\.md$", r"^\.gitignore$",
    r"^pom\.xml$", r"package\.json$", r"pnpm-lock\.yaml$",
    r"^yarn\.lock$", r"package-lock\.json$",
]
REWORK_EXCLUDE_MSG = re.compile(
    r"^(chore\(deps\)|chore\(docs\)|docs:|style:|format:|chore: bump)", re.I)

# 仓标识 → 门禁日志解析类型
GATE_KIND = {"B": "surefire", "C": "vitest", "H5": "vitest", "PCOLD": "vitest"}

# --- 构建失败记为 delta 的口径 ---------------------------------------------
#
# 编译失败时 surefire **不产出** XML, 于是「失败集」比基线**更小**,
# 差集法算出的 `D` 会**变小** —— 方向完全相反, 比不算还糟。
#
# 所以构建/编译失败必须**显式**记成一个 delta, 哪怕一个测试用例都没跑。
# 口径: 每个**构建失败**的仓记 1 个 delta (不是每个模块 1 个,
# 因为一次构建失败通常就是一处的编译错误)。
BUILD_FAILURE_DELTA = 1


def run(cmd, cwd=None):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_argv(argv, cwd=None):
    """不经 shell 执行, 避免路径里的特殊字符被解释。"""
    p = subprocess.run(argv, capture_output=True, text=True, cwd=cwd)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def git(repo_path, *args):
    rc, out = run("git " + " ".join(args), cwd=repo_path)
    return rc, out.strip()


def read(path, base=None):
    """读文件。相对路径优先按 base (默认 cwd) 解析, 再回退到仓根。"""
    if os.path.isabs(path):
        candidates = [path]
    else:
        candidates = [os.path.join(base or os.getcwd(), path),
                      os.path.join(ROOT, path)]
    for fp in candidates:
        try:
            with open(fp, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            continue
    return ""


def file_sha256(path, base=None):
    """文件的 sha256 (读原始字节)。文件不存在或读不到时返回 None。

    用于把**基线快照**的内容钉进测量结果。差集法的参照系就是那个
    文件, 所以必须按**字节**算哈希, 不能用解析后的集合 —— 集合相等
    但字节不同 (比如键顺序变了) 也是不同的基线。
    """
    if not path:
        return None
    if os.path.isabs(path):
        candidates = [path]
    else:
        candidates = [os.path.join(base or os.getcwd(), path),
                      os.path.join(ROOT, path)]
    for fp in candidates:
        try:
            with open(fp, "rb") as fh:
                return hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            continue
    return None


def verify_frozen_baseline(path, base=None):
    """核对基线快照是否就是冻结的那一份。返回 (ok, actual_sha, detail)。

    三种结果:

    - `ok=True`  : 哈希等于冻结值, 可以测量。
    - `ok=False` : 哈希对不上。**拒绝测量**。
    - `ok=False` : 文件根本读不到。同样拒绝, 因为「没有参照系」和
      「参照系不对」在差集法里是同一种灾难: 算出来的 D 没有意义。

    为什么不「只警告不拒绝」: 静默的错基线比硬失败危险得多。硬失败会
    被人看到并去查, 静默的错基线只会变成一个偏低的 DR 被写进报告。
    """
    if not path:
        return False, None, "未提供 --baseline-gates, 缺少差集法的参照系"
    actual = file_sha256(path, base)
    if actual is None:
        return False, None, f"读不到基线快照文件: {path}"
    if actual != FROZEN_BASELINE_GATES_SHA256:
        return (False, actual,
                f"基线快照与冻结版不一致, 拒绝测量。\n"
                f"  文件:   {path}\n"
                f"  实际:   {actual}\n"
                f"  冻结值: {FROZEN_BASELINE_GATES_SHA256}\n"
                f"  两臂若对着不同基线, DR/CE 无意义。请恢复冻结版本。")
    return True, actual, "基线快照与冻结版一致"


# ---------------------------------------------------------------------------
# 观测量采集
# ---------------------------------------------------------------------------

def changed_files(repo_path, baseline, head):
    """该范围内改动的文件集合 (仓内相对路径)。"""
    rc, out = git(repo_path, "diff", "--name-only", f"{baseline}..{head}")
    if rc != 0:
        return set()
    return {l.strip() for l in out.splitlines() if l.strip()}


def commits(repo_path, baseline, head):
    """返回 [(sha, subject, iso_time, files_set), ...], 按时间升序。"""
    rc, out = git(
        repo_path, "log", "--reverse", "--format=%H%x1f%s%x1f%aI",
        f"{baseline}..{head}")
    if rc != 0:
        return []
    result = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) < 3:
            continue
        sha, subject, ts = parts[0], parts[1], parts[2]
        rc2, files_out = git(repo_path, "show", "--name-only", "--format=",
                             sha)
        files = {f.strip() for f in files_out.splitlines() if f.strip()}
        result.append((sha, subject, ts, files))
    return result


def is_doc_or_config(path):
    for pat in REWORK_EXCLUDE_PATTERNS:
        if re.search(pat, path):
            return True
    return False


def count_rework(repo_path, baseline, head, touched_files):
    """返工提交数 R。

    口径 (FORMULA.md §3.2):
      - 排除首个实施提交
      - 其余提交若改动文件与本需求触及的文件集有交集, 且不是纯文档/配置/依赖 → 计 1
    """
    cs = commits(repo_path, baseline, head)
    if len(cs) <= 1:
        return 0
    r = 0
    for _sha, subject, _ts, files in cs[1:]:
        if not (files & touched_files):
            continue
        relevant = [f for f in files if f in touched_files]
        if all(is_doc_or_config(f) for f in relevant):
            continue
        if REWORK_EXCLUDE_MSG.match(subject):
            continue
        r += 1
    return r


def elapsed_minutes(repo_path, baseline, head):
    """实施耗时 T: 首提交 → 末提交 的墙钟分钟。"""
    cs = commits(repo_path, baseline, head)
    if len(cs) < 2:
        return 0.0
    from datetime import datetime
    def parse(ts):
        return datetime.fromisoformat(ts)
    try:
        start = parse(cs[0][2])
        end = parse(cs[-1][2])
    except ValueError:
        return 0.0
    return round((end - start).total_seconds() / 60.0, 2)


# --- 规格流程耗时 (T 的 SSD 臂部分) ---------------------------------------
#
# **口径缺陷**: 旧的 `T` 只取**业务仓**的首末提交跨度。SSD 臂的核心成本
# (PRD / TD / Plan 的产出) 落在**规格仓**, 完全不计入 `T`。
# 于是 SSD 臂的 `T` 被系统性低估, `TR = T_ssd / T_control` 被压低,
# `SI = 1.5 - 0.5 * TR` 被**抬高** —— 速度子指数**系统性偏袒 SSD**。
#
# 这不是理论风险: SSD 臂跑完整流程 (`/to-prd` → `/to-tech-design` →
# `/to-plan` → 实施), 时间成本比对照臂高一个量级, 而旧口径把它抹掉了。
#
# 修法: SSD 臂额外计入**规格仓**里该臂的产出耗时。对照臂不产规格,
# 这一项自然为 0 —— 口径对称, 不是给对照臂加罚。
#
# 规格产出的定位: 规格仓里按臂分目录, 路径形如
#   <spec-repo>/<spec-rel-dir>/<round-id>/<arm>/
#
# **读的是该臂的分支**, 不是工作区 HEAD。与业务仓同一条规矩
# (`exp/<round-id>/<arm>`): 读了 HEAD 就等于读了「谁最后 checkout 过」,
# 两臂的规格耗时就会互相覆盖 —— 和这次修的门禁污染是同一类错误。
# 分支不存在 → 0.0 (该臂还没产出规格)。
def spec_work_minutes(spec_repo_path, rel_dir, branch=None):
    """规格仓里某个臂目录的产出耗时 (分钟)。

    `rel_dir` 形如 `docs/efficacy/spec-output/F-06/ssd`。
    `branch` 形如 `exp/F-06/ssd`。目录不存在 / 分支不存在 / 提交不足 2 个
    → 0.0。
    """
    if not spec_repo_path or not os.path.isdir(spec_repo_path):
        return 0.0
    if not rel_dir:
        return 0.0
    argv = ["git", "-C", spec_repo_path, "log", "--reverse",
            "--format=%aI"]
    if branch:
        argv.append(branch)
    argv.extend(["--", rel_dir])
    rc, out = run_argv(argv, cwd=spec_repo_path)
    if rc != 0:
        return 0.0
    stamps = [l.strip() for l in out.splitlines() if l.strip()]
    if len(stamps) < 2:
        # 只有一个提交时, 用「提交时刻 - 最早提交时刻」无从谈起。
        # 取 0 而不是猜一个时长: 少算 SSD 的成本会抬高 SI, 方向危险。
        #
        # 0 个提交更危险: 那说明该臂**根本没产规格**。这在正式实验里
        # 不该发生, 必须显式报出来 (调用方检查 `spec_commits`)。
        return 0.0
    from datetime import datetime
    try:
        start = datetime.fromisoformat(stamps[0])
        end = datetime.fromisoformat(stamps[-1])
    except ValueError:
        return 0.0
    return round((end - start).total_seconds() / 60.0, 2)


def spec_work_commits(spec_repo_path, rel_dir, branch=None):
    """规格仓里某个臂目录的提交数 (用于判断「该臂到底产没产规格」)。

    与 `spec_work_minutes` 同口径, 但返回**提交数**而不是时长。
    """
    if not spec_repo_path or not os.path.isdir(spec_repo_path):
        return 0
    if not rel_dir:
        return 0
    argv = ["git", "-C", spec_repo_path, "rev-list", "--count"]
    if branch:
        argv.append(branch)
    argv.extend(["--", rel_dir])
    rc, out = run_argv(argv, cwd=spec_repo_path)
    if rc != 0:
        return 0
    try:
        return int(out.strip() or "0")
    except ValueError:
        return 0


def _sha_exists(repo_path, sha):
    """该 SHA 是否是本仓的真实 commit。"""
    rc, _ = run_argv(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                     cwd=repo_path)
    return rc == 0


def _sha_in_range(repo_path, sha, baseline, head):
    """该 SHA 是否落在本臂的提交区间 baseline..head 内 (即确属本臂产出)。

    RUBRIC.md §2.1 要求「<sha> 是**本臂分支上的**真实 commit」。
    只用 `cat-file -e` 校验存在性是不够的: 任何历史 commit (包括基线之前的)
    都能通过, 那样两臂就可以互相引用对方的提交, 配对失效。

    判定:
      1. SHA 必须是本仓真实 commit;
      2. baseline..head 的提交集合里必须包含它 (本臂产出);
      3. 它必须是 head 的祖先 (即在分支上, 不是别的分支的游离 commit)。
    """
    if not _sha_exists(repo_path, sha):
        return False, "sha-not-found"
    rc, out = run_argv(
        ["git", "rev-list", f"{baseline}..{head}"], cwd=repo_path)
    if rc != 0:
        return False, "range-unresolvable"
    if sha not in {l.strip() for l in out.splitlines() if l.strip()}:
        # 不在区间内: 区分「根本不是本臂产出」与「SHA 不存在」两种原因
        return False, "sha-out-of-arm-range"
    rc2, _ = run_argv(["git", "merge-base", "--is-ancestor", sha, head],
                      cwd=repo_path)
    if rc2 != 0:
        return False, "sha-not-on-branch"
    return True, "ok"


def _resolve_blob(repo_path, sha, path):
    """取该 SHA 下该文件的文本。路径可能带仓库顶层模块前缀。

    返回 (文本, None) 或 (None, 原因)。找不到时原因取:
      `file-not-found` (仓/SHA 不可用) 或 `line-not-found` (文件太短)。

    **路径解析必须唯一**: `_line_exists` 与 `_anchor_line_kind` 都要用
    它。两者口径不一致的后果: `_line_exists` 说「第 line 行存在」而
    `_anchor_line_kind` 说「文件找不到」→ 锚点被误判为无效, 或者反过来
    (更糟: 拿别的文件的内容去判锚点行)。
    """
    rc, out = run_argv(["git", "show", f"{sha}:{path}"], cwd=repo_path)
    if rc == 0:
        return out, None
    # 路径可能带仓库顶层模块前缀, 逐个后缀尝试
    rc2, out2 = run_argv(["git", "ls-tree", "-r", "--name-only", sha],
                         cwd=repo_path)
    if rc2 != 0:
        return None, "file-not-found"
    for cand in out2.splitlines():
        if cand.endswith("/" + path) or path.endswith("/" + cand):
            rc3, out3 = run_argv(["git", "show", f"{sha}:{cand}"],
                                 cwd=repo_path)
            if rc3 == 0:
                return out3, None
    return None, "file-not-found"


def _line_exists(repo_path, sha, path, line):
    """该 SHA 下的该文件是否真的有第 line 行。

    用 `git show <sha>:<path>` 读取该 commit 时刻的文件内容,
    这样锚点指向的是**提交时**的行, 而不是工作区的当前行。
    """
    text, _reason = _resolve_blob(repo_path, sha, path)
    if text is None:
        return False
    return len(text.splitlines()) >= line


# --- 锚点行的**机械**有效性 -----------------------------------------------
#
# RUBRIC.md §2.1 要求「锚点指向的**那一行确实承载该行为** (不是文件里随便一行)」。
# 「是否承载该行为」最终要靠人工复核, 但**一部分是可以机器判的**:
# 空行、纯注释行、纯 import / package 行**不可能**承载任何行为。
# 机器先把这三类挡掉, 剩下的交给人工 —— 人工不必再逐条排查明显无效的锚点。
#
# 这不是「语义校验」的完整实现。FORMULA.md §3.3 的「语义复核」仍然必须做,
# 机器只负责拦掉**机械可判**的那一部分。
RE_JAVA_PACKAGE = re.compile(r"^\s*package\s+[\w.]+\s*;?\s*$")
RE_JAVA_IMPORT = re.compile(r"^\s*import\s+[\w.*]+\s*;?\s*$")
RE_COMMENT_ONLY = re.compile(r"^\s*(//|/\*|\*|\*/)")
RE_TS_IMPORT = re.compile(r"^\s*import\s+[\w{*]")
RE_TS_COMMENT = re.compile(r"^\s*(//|/\*|\*)")


def _anchor_line_kind(repo_path, sha, path, line):
    """取该 SHA 下该文件第 line 行的**类别**。

    返回 ("ok", 行文本) 或 ("<原因>", None)。原因取值:
      `line-not-found` / `blank` / `comment` / `package` / `import`。
    """
    text, reason = _resolve_blob(repo_path, sha, path)
    if text is None:
        return reason or "line-not-found", None
    lines = text.splitlines()
    if line < 1 or line > len(lines):
        return "line-not-found", None
    line_text = lines[line - 1]
    stripped = line_text.strip()
    if not stripped:
        return "blank", None
    if RE_COMMENT_ONLY.match(line_text) or RE_TS_COMMENT.match(line_text):
        return "comment", None
    if RE_JAVA_PACKAGE.match(line_text) or RE_JAVA_IMPORT.match(line_text):
        return "package" if "package" in stripped[:8] else "import", None
    if RE_TS_IMPORT.match(line_text):
        return "import", None
    return "ok", text


def parse_repo_map(spec, default_alias=None, default_path=None):
    """解析 `B=/path,C=/path` 形式的仓库标识 → 路径映射。

    `default_alias` / `default_path` 提供的仓库优先 (标识优先于 spec 里的同名项)。
    """
    mapping = {}
    for chunk in (spec or "").split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        alias, path = chunk.split("=", 1)
        alias, path = alias.strip(), path.strip()
        if alias and path:
            mapping[alias] = path
    if default_alias and default_path:
        mapping.setdefault(default_alias, default_path)
    return mapping


def count_delivered_acs(checklist_text, touched_files, repo_aliases,
                        repo_paths=None, baseline=None, head=None,
                        per_repo_ranges=None):
    """交付验收标准数 A_del (FORMULA.md §3.3 + RUBRIC.md §2.1)。

    输入是**共享检查表** (`scripts/gen-checklists.py` 生成的模板 + 本臂填写的
    勾选与锚点)。`A_spec` = 检查表里的 AC 总数, **扣除** 标记为 `不适用` 的条目
    (RUBRIC.md §2.2: `不适用` 不计入 `A_spec` 与 `A_del` 的任何一方)。

    六条全满足才计入 A_del:
      1. 判定为 `交付` (复选框已勾选)
      2. 证据锚点可解析
      3. <sha> 是本仓真实 commit
      4. <sha> 落在本臂区间 baseline..head 内 (本臂产出, 非他人 commit)
      5. 锚点指向的文件确实出现在该需求的改动文件集里
      6. <path>#L<line> 在该 SHA 下确实存在

    `baseline` / `head` 为 None 时跳过第 4 条 (仅用于自检的宽松模式)。
    `per_repo_ranges`: {标识: (baseline, head)}。多仓轮次里每个仓有各自的
    起点与终点, 缺该键时回退到全局 `baseline` / `head`。
    """
    verdicts = R.parse_verdicts(checklist_text)
    if not verdicts:
        raise ValueError(
            "检查表里没有解析出任何 AC 行 —— 检查表格式不对, 或 AC 全被删除。\n"
            "检查表必须是 `scripts/gen-checklists.py` 生成的模板 + 本臂填写。\n"
            "(旧版 measure.py 只认 Markdown 复选框, 会静默得到 A_spec=0; "
            "这里改为硬失败, 避免整条评分链路静默失效。)")
    a_spec_raw = len(verdicts)
    na_count = sum(1 for (_id, _c, _a, na) in verdicts if na)
    a_spec = a_spec_raw - na_count
    delivered = 0
    detail = []
    for ac_id, checked, anchor, na_reason in verdicts:
        if na_reason:
            detail.append({"ac_id": ac_id, "text": "", "checked": False,
                           "reason": "not-applicable", "na_reason": na_reason,
                           "anchor": None})
            continue
        ok = False
        reason = "not-checked"
        if checked:
            if anchor is None:
                reason = "no-anchor"
            else:
                ident, sha, path, line = anchor
                # 路径可能带仓库顶层模块前缀, 取后缀匹配。
                # `touched_files` 里的元素形如 `<仓标识>:<仓内相对路径>`,
                # 匹配时需先剥离标识前缀, 再比对仓内路径。
                matched = None
                for tf in touched_files:
                    tf_path = tf
                    if ":" in tf:
                        tf_ident, tf_path = tf.split(":", 1)
                        if tf_ident != ident:
                            continue
                    if tf_path == path or tf_path.endswith("/" + path) or path.endswith("/" + tf_path):
                        matched = tf_path
                        break
                if matched is None:
                    reason = "anchor-file-not-changed"
                else:
                    repo_path = (repo_paths or {}).get(ident)
                    if repo_path is None:
                        reason = "unknown-repo"
                    else:
                        r_base, r_head = baseline, head
                        if per_repo_ranges and ident in per_repo_ranges:
                            r_base, r_head = per_repo_ranges[ident]
                        if r_base and r_head:
                            in_range, range_reason = _sha_in_range(
                                repo_path, sha, r_base, r_head)
                            if not in_range:
                                reason = range_reason
                            elif not _line_exists(repo_path, sha, matched, line):
                                reason = "line-not-found"
                            else:
                                # 锚点行的**机械**有效性: 空行 / 纯注释 /
                                # package / import 行不可能承载行为。
                                kind, _text = _anchor_line_kind(
                                    repo_path, sha, matched, line)
                                if kind != "ok":
                                    reason = f"anchor-line-{kind}"
                                else:
                                    ok = True
                                    reason = "delivered"
                        elif not _sha_exists(repo_path, sha):
                            reason = "sha-not-found"
                        elif not _line_exists(repo_path, sha, matched, line):
                            reason = "line-not-found"
                        else:
                            kind, _text = _anchor_line_kind(
                                repo_path, sha, matched, line)
                            if kind != "ok":
                                reason = f"anchor-line-{kind}"
                            else:
                                ok = True
                                reason = "delivered"
        if ok:
            delivered += 1
        detail.append({"ac_id": ac_id, "text": "", "checked": checked,
                       "reason": reason,
                       "anchor": (f"{{{anchor[0]}}}@{anchor[1]}:{anchor[2]}#L{anchor[3]}"
                                  if anchor else None)})
    return a_spec, delivered, detail


# ---------------------------------------------------------------------------
# 门禁失败 (规范化标识)
# ---------------------------------------------------------------------------

def parse_gate_log(text, kind):
    """兼容旧名: 按门禁类型解析失败标识。

    - kind == "surefire": 返回 `pkg.Class#method` 集合
    - kind == "vitest":   返回 (files, cases) 二元组
    """
    if kind == "surefire":
        return G.parse_surefire_log_ids(text), set()
    files, cases = G.parse_vitest_log_ids(text)
    return files, cases


def parse_surefire_failures(repo_path):
    """从 surefire XML 报告提取失败测试的全限定标识集合。

    ⚠️ **已停用**: 这个函数读的是**业务仓工作区**的
    `<module>/target/surefire-reports`, 那个目录是**四仓共享且跨臂共享**的。
    读它就是本次修复要根除的污染源。保留只为让「为什么不再用它」在
    代码里留个可见的痕迹, **不要调用**。

    现在的唯一数据源是**归档**:
      `gate_archive.archived_surefire_ids(root, round_id, arm)`
    它读的是每轮每臂专属的归档副本, 归属可自证。

    标识用 **XML 文件名** 反推的 FQN (`pkg.Class#method`), 不用
    `<testcase classname="...">`: 后者是 `@DisplayName` 显示名, 不是类名,
    用它会让同一个失败在 XML 侧与日志侧得到两个不同标识, 差集恒不为空。
    """
    raise RuntimeError(
        "parse_surefire_failures 读的是共享工作区 surefire 目录, "
        "跨臂污染的根因。改用 gate_archive.archived_surefire_ids(...)")


def _canonical_list_file(path):
    """把隔离清单路径归一成**可跨机器比较**的写法。

    聚合时要逐轮核对两臂的清单是否相同 (FORMULA.md §3.4.9.3)。如果直接
    存绝对路径, 同一份清单在两臂上是同一个字符串, 但换个机器跑一遍
    就会变成不同的绝对路径, 对称性检查就成了摆设。

    所以这里: 路径在本仓内就存**仓相对路径**, 否则存绝对路径。
    """
    if not path:
        return path
    try:
        return os.path.relpath(os.path.abspath(path), ROOT)
    except ValueError:
        # Windows 上跨盘符 relpath 会抛错, 那就存绝对路径。
        return os.path.abspath(path)


def load_quarantined_flaky(path=None):
    """读基线 flake 隔离清单。

    返回 {仓标识: {测试标识, ...}}。

    清单格式 (docs/efficacy/flaky-tests.json):
        {"quarantined": [{"alias": "B", "test_id": "pkg.Class#method", ...}]}

    **清单缺失 → 硬失败**。隔离清单是尺子的一部分 (§3.4.9.4「必须冻结」),
    缺了它就等于悄悄把口径放宽成「不隔离任何东西」, 那对 SSD 有利,
    方向危险。所以这里必须报错, 而不是当成空清单。

    **清单坏掉**同样硬失败: 读不出来却静默当成空清单, 后果一样。
    """
    p = path or os.path.join(ROOT, FLAKY_LIST_REL)
    if not os.path.isfile(p):
        raise ValueError(
            f"flake 隔离清单不存在: {p}\n"
            "它是尺子的一部分 (FORMULA.md §3.4.9.4), 必须存在。\n"
            "确实不需要隔离任何东西时, 写一个空清单 "
            '{"quarantined": []}, 不要删文件。')
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError(f"flake 隔离清单不可解析: {p} ({exc})")
    out = {}
    for item in data.get("quarantined", []):
        alias = item.get("alias", "B")
        tid = item.get("test_id", "")
        if not tid:
            raise ValueError(f"flake 隔离清单有条目没有 test_id: {p}")
        out.setdefault(alias, set()).add(tid)
    return out


def count_new_gate_failures(gate_failures, baseline_failures):
    """新出现的门禁失败数 (差集法, FORMULA.md §3.4)。"""
    return len(set(gate_failures) - set(baseline_failures))


def _load_baseline_failures(path, aliases):
    """从 baseline-gates.json 读各仓的基线失败集合。

    `aliases` 为本轮涉及的仓标识 (B / C / H5 / PCOLD)。
    后端用 `pkg.Class#method` 标识, 前端用 vitest 的
    `file > suite > name` 标识, 两者命名空间不同, 因此**分仓存放**,
    差分时按仓取对应集合。

    前端分**文件级**与**用例级**两个粒度, 与本轮门禁解析出的粒度**对齐**:
      - 用例级: `failing_test_ids_C` / `failing_test_cases_H5` / ...
      - 文件级: `failing_test_files_C` / `failing_test_files_H5` / ...
    """
    out = {}
    if not path or not os.path.isfile(path):
        return out
    bdata = json.loads(read(path))
    for alias in aliases:
        if alias == "B":
            case_keys = ["failing_test_ids"]
            file_keys = []
        elif alias == "C":
            case_keys = ["failing_test_ids_C"]
            file_keys = ["failing_test_files_C"]
        elif alias == "H5":
            case_keys = ["failing_test_cases_H5"]
            file_keys = ["failing_test_files_H5"]
        elif alias == "PCOLD":
            case_keys = ["failing_test_cases_PCOLD"]
            file_keys = ["failing_test_files_PCOLD"]
        else:
            case_keys, file_keys = [], []
        cases = set()
        for k in case_keys:
            cases |= set(bdata.get(k, []))
        files = set()
        for k in file_keys:
            files |= set(bdata.get(k, []))
        out[alias] = {"cases": cases, "files": files}
    return out


def _gate_failures_by_repo(gate_log_text, aliases):
    """从门禁日志按仓切分失败项。

    门禁日志里每个仓的段落以 `### [<标识>]` 开头, 本函数按段落归属
    把失败项分到各仓, 避免不同仓的同名文件互相抵消。

    返回 {标识: {"cases": set, "files": set}}。
    """
    per_repo = {a: {"cases": set(), "files": set()} for a in aliases}
    current = None
    for line in gate_log_text.splitlines():
        s = line.strip()
        m = re.match(r"^###\s*\[(\w+)\]", s)
        if m:
            current = m.group(1)
            continue
        if current is None or current not in per_repo:
            continue
        kind = GATE_KIND.get(current, "markdown")
        if kind == "surefire":
            ids = G.parse_surefire_log_ids(s)
            per_repo[current]["cases"] |= ids
        elif kind == "vitest":
            files, cases = G.parse_vitest_log_ids(s)
            per_repo[current]["files"] |= files
            per_repo[current]["cases"] |= cases
        else:
            per_repo[current]["cases"] |= G.parse_markdown_fail_ids(s)
    return per_repo


def _build_status_of(manifest, alias):
    """取某仓在归档 manifest 里的构建状态。"""
    for repo in (manifest or {}).get("repos", []):
        if repo.get("alias") == alias:
            return repo.get("build_status", "UNKNOWN")
    return "NOT_GATED"


def _archive_has_surefire(manifest, alias):
    """某仓的归档里是否**有** surefire XML 文件。"""
    for repo in (manifest or {}).get("repos", []):
        if repo.get("alias") == alias:
            return repo.get("file_count", 0) > 0
    return False


def cmd_round(args):
    """单轮测量。"""
    repo_map = parse_repo_map(args.repo_paths, args.repo, args.repo_path)
    aliases = [a for a in ("B", "C", "H5", "PCOLD") if a in repo_map]

    # 多仓轮次: 每仓各自的起点/终点。`--repo-ranges` 形如
    #   B=baseline:head,C=baseline:head
    per_repo_ranges = {}
    if args.repo_ranges:
        for chunk in args.repo_ranges.split(","):
            chunk = chunk.strip()
            if "=" not in chunk:
                continue
            ident, span = chunk.split("=", 1)
            ident = ident.strip()
            if ":" not in span:
                continue
            base, head = span.split(":", 1)
            per_repo_ranges[ident] = (base.strip(), head.strip())

    # 改动文件集合: 各仓并集 (带仓前缀, 避免同名文件冲突)
    touched = set()
    per_repo_touched = {}
    for alias in aliases:
        rp = repo_map[alias]
        base, head = per_repo_ranges.get(alias, (args.baseline, args.head))
        if not (base and head):
            continue
        tf = changed_files(rp, base, head)
        per_repo_touched[alias] = tf
        for f in tf:
            touched.add(f"{alias}:{f}")

    # R 与 T: 各仓分别算后相加
    r = 0
    for alias in aliases:
        rp = repo_map[alias]
        base, head = per_repo_ranges.get(alias, (args.baseline, args.head))
        if not (base and head):
            continue
        r += count_rework(rp, base, head, per_repo_touched.get(alias, set()))
    t = 0.0
    for alias in aliases:
        rp = repo_map[alias]
        base, head = per_repo_ranges.get(alias, (args.baseline, args.head))
        if not (base and head):
            continue
        t += elapsed_minutes(rp, base, head)

    # **规格流程耗时** (SSD 臂的 PRD / TD / Plan 产出)。
    # 对照臂不产规格 → 这一项为 0。口径对称。
    #
    # 读的是该臂的**分支** (`exp/<round-id>/<arm>`), 不是工作区 HEAD。
    # 读 HEAD 等于读「谁最后 checkout 过」, 两臂互相覆盖 —— 与这次修的
    # 门禁污染同一类错误, 不能重犯。
    t_spec = 0.0
    spec_commits = 0
    spec_branch = ""
    if args.spec_repo:
        rel = os.path.join(args.spec_rel_dir, args.round_id, args.arm)
        spec_branch = f"exp/{args.round_id}/{args.arm}"
        t_spec = spec_work_minutes(args.spec_repo, rel, branch=spec_branch)
        spec_commits = spec_work_commits(args.spec_repo, rel, branch=spec_branch)
        if spec_commits == 0:
            # SSD 臂没产规格 = 流程没跑完, 或者产出没落到约定目录。
            # 这会让 SSD 的 `T` 偏小、`SI` 偏高 —— 方向不利, 必须显式报。
            print(f"[警告] 规格仓里该臂没有产出: "
                  f"{args.spec_repo}/{rel} (分支 {spec_branch}) 无提交, "
                  f"T_spec_minutes = 0", file=sys.stderr)
        elif t_spec == 0.0 and spec_commits == 1:
            # 只有 1 个提交 → 跨度算不出来 → 取 0。同样偏袒 SSD, 要报。
            print(f"[警告] 规格产出只有 1 个提交, 无法算跨度, "
                  f"T_spec_minutes = 0 (分支 {spec_branch})", file=sys.stderr)
    t_total = round(t + t_spec, 2)

    checklist_text = read(args.checklist)
    a_spec, a_del, ac_detail = count_delivered_acs(
        checklist_text, touched, args.repo, repo_map,
        baseline=args.baseline, head=args.head,
        per_repo_ranges=per_repo_ranges or None)

    # **基线参照系校验 (硬失败)**。
    # 必须放在 `_load_baseline_failures` 之前: 一旦开始用错的基线算,
    # 后面的一切都建立在错的前提上, 报错也已经太晚。
    ok, actual_sha, detail = verify_frozen_baseline(args.baseline_gates)
    if not ok:
        print(f"[FAIL] {detail}", file=sys.stderr)
        return 2
    print(f"[OK] {detail} ({actual_sha[:12]})")

    # 门禁失败: 按仓切分 → 减去对应仓的基线
    baseline_by_repo = _load_baseline_failures(args.baseline_gates, aliases)

    # **门禁产物必须从归档读, 不得读业务仓工作区**。
    #
    # 业务仓的 `<module>/target/surefire-reports` 是**四仓共享**且**跨臂共享**
    # 的目录。旧的实现在这里直接读它, 于是:
    #
    #   12:23  B-01/ssd      门禁跑完 -> 留下 XML (全过)
    #   12:45  F-06/control  门禁跑完 -> 留下 XML (含 1 个失败)
    #   12:49  全部 20 次 measure 开始 -> 读到的全是 F-06 的 XML
    #
    # B-01 / F-03 / F-04 三臂的 `D_gate_new` 全被记成 1,
    # 而它们自己的门禁日志里明明是**通过**的。
    #
    # 归档是**每轮每臂专属**的, 且带 manifest + 逐文件 sha256,
    # 归属可自证。归档缺失 / 损坏 / 与本次门禁日志对不上 → **硬失败**。
    archive_root = os.path.abspath(
        args.archive_root or os.path.join(ROOT, GA.ARCHIVE_SUBDIR))
    ok, errors = GA.verify_archive(ROOT, args.round_id, args.arm,
                                    expected_gate_log=args.gate_log,
                                    archive_root=archive_root)
    if not ok:
        print(f"[FAIL] 门禁归档校验未通过, 测量中止:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(f"  提示: 先跑 bash scripts/run-round.sh gate "
              f"{args.round_id} {args.arm} 生成归档", file=sys.stderr)
        return 2
    manifest = GA.load_manifest(ROOT, args.round_id, args.arm,
                                archive_root=archive_root)
    print(f"[OK] 门禁归档校验通过 "
          f"({GA.archive_dir(ROOT, args.round_id, args.arm, archive_root)})")

    gate_by_repo = _gate_failures_by_repo(read(args.gate_log), aliases)

    # 后端 surefire XML 更精确 (用 FQN 而非日志正则), 用**归档里的**副本覆盖。
    # 注意覆盖源是归档, 不是业务仓工作区 —— 这是本次修复的核心。
    #
    # 归档是**权威**源: 基线的 `failing_test_ids` 也是 XML 口径采的,
    # 差分必须 XML 对 XML。日志正则抓不到 `@DisplayName` 类, 口径不一致
    # 会让差集恒不为空 (基线自己的失败被误判成新失败)。
    #
    # 所以只要归档里**有** surefire XML, 就以它为准 —— 即使失败集为空
    # (那是「确实没失败」, 不是「没读到」)。
    if "B" in gate_by_repo and _archive_has_surefire(manifest, "B"):
        gate_by_repo["B"]["cases"] = GA.archived_surefire_ids(
            ROOT, args.round_id, args.arm, archive_root=archive_root)

    # **构建失败显式记为 delta**。
    # 编译失败 → surefire 不产 XML → 失败集变小 → 差集法算出的 D 变小,
    # 方向相反。必须在差集之外显式补一个。
    build_failures = {}
    for repo in manifest.get("repos", []):
        alias = repo.get("alias")
        if alias in aliases and repo.get("build_status") == "BUILD_FAILURE":
            build_failures[alias] = BUILD_FAILURE_DELTA
    if build_failures:
        print(f"[警告] 检测到构建失败, 按每个仓 {BUILD_FAILURE_DELTA} 个 delta "
              f"计入: {build_failures}", file=sys.stderr)

    # **基线 flake 隔离** (FORMULA.md §3.4.9)。
    #
    # 冻结基线自身有间歇性失败的用例, 它们不在基线快照里 (快照只采了一次),
    # 所以某一臂恰好触发时会被差集法算成「新失败」。隔离在**分子侧**做:
    # 先从本臂失败集里剔除, 再做差集。基线快照 (分母) 不动。
    #
    # 隔离清单对**两臂对称**, 所以它只降低两臂共同的噪声, 不改变相对比较。
    try:
        quarantined = load_quarantined_flaky(args.flaky_list or None)
    except ValueError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2

    new_failures = 0
    new_failures_before_quarantine = 0
    gate_detail = {}
    quarantine_detail = {}
    for alias in aliases:
        gf = gate_by_repo.get(alias, {"cases": set(), "files": set()})
        bf = baseline_by_repo.get(alias, {"cases": set(), "files": set()})
        # 本轮**实际触发**的隔离项 (只有真的失败了才算, 清单里没触发的
        # 不计数。报告要说的是「这一轮隔离掉了什么」。
        hit = gf["cases"] & quarantined.get(alias, set())
        # 先剔除隔离项, 再做差集。
        new_cases = (gf["cases"] - quarantined.get(alias, set())) - bf["cases"]
        new_files = gf["files"] - bf["files"]
        # 文件级与用例级是**不同粒度**, 分开计数后相加:
        # 一个文件里的用例失败会同时体现在两个粒度上, 这是有意的 ——
        # 基线快照也是这两个粒度分开存的, 差分必须同粒度对同粒度。
        n = len(new_cases) + len(new_files)
        n += build_failures.get(alias, 0)
        new_failures += n
        # 隔离**前**的同一口径数字, 用于报告隔离动了多少 (只供核对,
        # 不进公式)。
        raw_cases = gf["cases"] - bf["cases"]
        new_failures_before_quarantine += (len(raw_cases) + len(new_files)
                                           + build_failures.get(alias, 0))
        quarantine_detail[alias] = sorted(hit)
        gate_detail[alias] = {
            "gate_failures": len(gf["cases"]),
            "gate_files": len(gf["files"]),
            "baseline_failures": len(bf["cases"]),
            "baseline_files": len(bf["files"]),
            "new_failures": n,
            "new_case_ids": sorted(new_cases),
            "new_file_ids": sorted(new_files),
            "build_status": _build_status_of(manifest, alias),
            "build_failure_delta": build_failures.get(alias, 0),
            "quarantined_ids": sorted(hit),
        }

    # **隔离必须显式报告** (FORMULA.md §3.4.9.5)。
    # 隔离不是「悄悄修数字」, 它是一个事先声明的口径, 必须可复核。
    total_quarantined = sum(len(v) for v in quarantine_detail.values())
    if total_quarantined:
        print(f"[隔离] 本轮剔除了 {total_quarantined} 个基线 flake 标识 "
              f"(FORMULA.md §3.4.9):", file=sys.stderr)
        for alias, ids in sorted(quarantine_detail.items()):
            for tid in ids:
                print(f"  - [{alias}] {tid}", file=sys.stderr)
    else:
        print("[隔离] 本轮没有触发任何基线 flake", file=sys.stderr)

    # D = 新门禁失败 + 人工评审记录的功能性缺陷
    d_review = 0
    if args.review_findings and os.path.isfile(args.review_findings):
        d_review = len([
            l for l in read(args.review_findings).splitlines()
            if l.strip() and not l.strip().startswith("#")
        ])
    d = new_failures + d_review

    dr = None if a_del == 0 else round((d + r) / a_del, 4)
    ce = 0.0 if a_spec == 0 else round(a_del / a_spec, 4)

    out = {
        "round_id": args.round_id,
        "arm": args.arm,
        "repo": args.repo,
        "repos": aliases,
        "baseline": args.baseline,
        "head": args.head,
        "repo_ranges": per_repo_ranges,
        "checklist_file": args.checklist,
        # **基线快照的哈希**。差集法的参照系就是这个文件, 所以每次测量
        # 必须记下它当时的字节哈希。少了这一行, 事后无法证明这一轮
        # 用的是哪一版基线 (冻结版 vs 工作区改过的版本)。
        "baseline_gates_file": args.baseline_gates,
        "baseline_gates_sha256": file_sha256(args.baseline_gates),
        "observations": {
            "D": d,
            "D_gate_new": new_failures,
            "D_review": d_review,
            "R": r,
            "A_del": a_del,
            "A_spec": a_spec,
            "T_minutes": round(t_total, 2),
            "T_code_minutes": round(t, 2),
            "T_spec_minutes": round(t_spec, 2),
            # 规格产出的提交数。0 = 该臂没产规格 (会让 SI 偏高, 方向不利),
            # 1 = 跨度算不出来。报告里必须能一眼看出这两种情况。
            "T_spec_commits": spec_commits,
            # **隔离前**的 D_gate_new (未经 flake 隔离)。与 D_gate_new 并列,
            # 便于事后核对隔离到底动了几个 (FORMULA.md §3.4.9.5)。
            "D_gate_new_before_quarantine": new_failures_before_quarantine,
            "quarantined_count": total_quarantined,
        },
        "spec": {
            # 规格仓与产出定位。留档, 便于事后核对该轮的 `T_spec` 怎么来的。
            "repo": args.spec_repo,
            "rel_dir": os.path.join(args.spec_rel_dir, args.round_id, args.arm)
                      if args.spec_repo else "",
            "branch": spec_branch,
        },
        "derived": {
            "DR": dr,
            "CE": ce,
        },
        "gate_detail": gate_detail,
        # **隔离明细**。逐条列出本轮剔除的标识 (FORMULA.md §3.4.9.5)。
        "quarantine": {
            "list_file": _canonical_list_file(args.flaky_list or FLAKY_LIST_REL),
            "by_repo": quarantine_detail,
        },
        "ac_detail": ac_detail,
        "touched_files": sorted(touched),
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"[round] {args.round_id}/{args.arm}: "
          f"D={d} R={r} A_del={a_del}/{a_spec} "
          f"T={t_total:.2f}min (代码 {t:.2f} + 规格 {t_spec:.2f}) "
          f"DR={dr} CE={ce}")
    return 0


def cmd_baseline(args):
    """基线门禁快照。"""
    log_text = read(args.gate_log)
    kind = GATE_KIND.get(args.repo, "markdown")
    if kind == "surefire":
        failures = sorted(G.parse_surefire_log_ids(log_text))
    else:
        files, cases = G.parse_vitest_log_ids(log_text)
        failures = sorted(files | cases)
    rc, head = git(args.repo_path, "rev-parse", "HEAD")
    data = {
        "repo": args.repo,
        "repo_path": args.repo_path,
        "head": head if rc == 0 else None,
        "captured_at": args.captured_at or "",
        "failure_count": len(failures),
        "failures": failures,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"[baseline] {args.repo}: {len(failures)} baseline failures -> {args.out}")
    return 0


def cmd_checklist(args):
    """校验一份填好的检查表相对共享模板是否只改了勾选/锚点/NA。"""
    acs = R.parse_rubric()
    templates = R.render_all_templates(acs)
    cand = args.candidate
    if cand not in templates:
        print(f"未知候选: {cand}; 可用: {sorted(templates)}", file=sys.stderr)
        return 1
    filled = read(args.checklist)
    ok, problems = R.checklist_diff(templates[cand], filled)
    if not ok:
        print("[checklist] 失败:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    verdicts = R.parse_verdicts(filled)
    n_delivered = sum(1 for (_i, c, _a, _na) in verdicts if c)
    n_na = sum(1 for (_i, _c, _a, na) in verdicts if na)
    print(f"[checklist] OK: {cand} 共 {len(verdicts)} 条 AC, "
          f"勾选 {n_delivered}, 不适用 {n_na}")
    return 0


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def cmd_aggregate(args):
    """聚合并计算 SEI。"""
    rounds = []
    if os.path.isdir(args.rounds):
        for f in sorted(os.listdir(args.rounds)):
            if f.endswith(".json"):
                rounds.append(json.loads(read(os.path.join(args.rounds, f))))

    # **聚合前的配对完整性校验**。
    #
    # `aggregate` 按 `arm` 把所有轮次分成两堆, 取中位数。所以它**不看**
    # 两臂是否对着同一份基线 —— 只要轮次号对得上就算配对成功。
    # 如果某轮的两臂是在基线漂移前后测的, 两边的 D 参照系不同,
    # 中位数就把两个不可比的量混在一起, 而且**不报错**。
    #
    # 所以这里在算中位数之前, 逐轮核对两臂记录的基线哈希是否一致。
    # 缺记录 (旧格式) 或不一致, 都拒绝聚合。
    pair_problems = []
    by_round = {}
    for r in rounds:
        by_round.setdefault(r.get("round_id"), {})[r.get("arm")] = r

    # **重复记录检测**。
    #
    # 同一个 (round_id, arm) 只应有一份 measure.json。若目录里出现两份
    # (例如重跑时写成了不同文件名), 之前的 `by_round[rid][arm] = r` 会
    # **静默保留最后一份**, 而 `by_arm` 仍把两份都算进去 —— 于是
    # `n_rounds` 虚高、同一轮被重复计入中位数。
    #
    # 这里在配对校验之前就把重复挑出来, 并且**拒绝聚合**: 重复记录
    # 说明轮次目录的状态是脏的, 此时任何聚合数字都不可信。
    dup_problems = []
    counts = {}
    for r in rounds:
        key = (r.get("round_id"), r.get("arm"))
        counts[key] = counts.get(key, 0) + 1
    for (rid, arm), c in sorted(counts.items(),
                                key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        if c > 1:
            dup_problems.append(
                f"轮次 {rid} 臂 {arm}: 有 {c} 份重复记录 (应为 1 份)")
    if dup_problems:
        print("[FAIL] 轮次目录存在重复记录, 拒绝聚合:", file=sys.stderr)
        for p in dup_problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    for rid, arms in sorted(by_round.items()):
        ssd_r = arms.get("ssd")
        ctrl_r = arms.get("control")
        if not ssd_r or not ctrl_r:
            # 缺臂不算错误 (实验可能还没跑完), 但要记下来供人看。
            missing = [a for a in ("ssd", "control") if a not in arms]
            pair_problems.append(f"轮次 {rid}: 缺少臂 {missing}")
            continue
        s_sha = ssd_r.get("baseline_gates_sha256")
        c_sha = ctrl_r.get("baseline_gates_sha256")
        if not s_sha or not c_sha:
            pair_problems.append(
                f"轮次 {rid}: 有臂未记录 baseline_gates_sha256 "
                f"(ssd={s_sha!r}, control={c_sha!r})")
            continue
        if s_sha != c_sha:
            pair_problems.append(
                f"轮次 {rid}: 两臂基线不一致 ssd={s_sha[:12]} "
                f"control={c_sha[:12]}")
        if s_sha != FROZEN_BASELINE_GATES_SHA256:
            pair_problems.append(
                f"轮次 {rid}: 基线不是冻结版 {s_sha[:12]} "
                f"(冻结值 {FROZEN_BASELINE_GATES_SHA256[:12]})")

    # **隔离清单必须两臂一致**。
    #
    # 隔离清单是**事前声明**的口径, 对两臂**对称** (§3.4.9.3)。如果某轮
    # 的两臂用了**不同的**隔离清单 (比如一臂传了 `--flaky-list`, 另一臂没传),
    # 那么这一轮两臂的 `D` 就**不可比**。方向性检查失效。
    #
    # 所以这里逐轮核对两臂记录的 `quarantine.list_file` 是否相同。
    for rid, arms in sorted(by_round.items()):
        ssd_r = arms.get("ssd")
        ctrl_r = arms.get("control")
        if not ssd_r or not ctrl_r:
            continue
        s_list = (ssd_r.get("quarantine") or {}).get("list_file")
        c_list = (ctrl_r.get("quarantine") or {}).get("list_file")
        if s_list != c_list:
            pair_problems.append(
                f"轮次 {rid}: 两臂的隔离清单不同 "
                f"ssd={s_list!r} control={c_list!r} (隔离必须对称)")

    hard = [p for p in pair_problems if "缺少臂" not in p]
    if hard:
        print("[FAIL] 配对校验失败, 拒绝聚合:", file=sys.stderr)
        for p in hard:
            print(f"  - {p}", file=sys.stderr)
        return 2
    for p in pair_problems:
        print(f"[WARN] {p}")

    by_arm = {"ssd": [], "control": []}
    for r in rounds:
        by_arm.setdefault(r.get("arm"), []).append(r)

    ssd, ctrl = by_arm.get("ssd", []), by_arm.get("control", [])

    # **只取配对完整的轮次**。
    #
    # 实验是配对设计 (§2.2: 第 i 轮的需求同时分配给两臂)。若某轮只跑
    # 了一臂 (实验中断、某臂失败), 那一臂的记录进了中位数, 而另一臂
    # 没有对应的记录 —— 中位数于是建立在**两臂轮次数不等**的集合上。
    #
    # 之前 `median_dr(ssd)` 用的是全部 ssd 记录, 所以一个未配对的极端值
    # 会污染中位数; 而 `n_rounds` 报的却是配对数, 两个数字口径不一致,
    # 读报告的人无法发现。
    #
    # 这里把参与中位数的集合限定为**两臂都在的轮次**。未配对的轮次不是
    # 被丢弃: 它在下面 `rounds_with_zero_delivery` 与 WARN 里单列。
    paired_ids = {rid for rid, arms in by_round.items()
                  if "ssd" in arms and "control" in arms}
    ssd_paired = [r for r in ssd if r.get("round_id") in paired_ids]
    ctrl_paired = [r for r in ctrl if r.get("round_id") in paired_ids]
    unpaired = sorted(
        (rid for rid in by_round if rid not in paired_ids), key=str)

    def median_dr(rs):
        vals = [r["derived"]["DR"] for r in rs
                if r["derived"].get("DR") is not None]
        return statistics.median(vals) if vals else None

    def median_ce(rs):
        vals = [r["derived"]["CE"] for r in rs]
        return statistics.median(vals) if vals else None

    def median_t(rs):
        vals = [r["observations"]["T_minutes"] for r in rs
                if r["observations"].get("T_minutes")]
        return statistics.median(vals) if vals else None

    dr_s, dr_c = median_dr(ssd_paired), median_dr(ctrl_paired)
    ce_s, ce_c = median_ce(ssd_paired), median_ce(ctrl_paired)
    t_s, t_c = median_t(ssd_paired), median_t(ctrl_paired)

    qi = ci = si = None
    if dr_s is not None and dr_c not in (None, 0):
        qi = clamp(0.5 + 0.5 * (1 - dr_s / dr_c))
    if ce_s is not None and ce_c is not None:
        ci = clamp(0.5 + (ce_s - ce_c))
    tr = None
    if t_s is not None and t_c:
        tr = t_s / t_c
        si = clamp(1.5 - 0.5 * tr)

    # 逐轮配对差值
    ctrl_by_round = {r["round_id"]: r for r in ctrl}
    pairs = []
    for r in ssd:
        c = ctrl_by_round.get(r["round_id"])
        if not c:
            continue
        d_dr = (r["derived"]["DR"] - c["derived"]["DR"]
                if r["derived"].get("DR") is not None
                and c["derived"].get("DR") is not None else None)
        pairs.append({
            "round_id": r["round_id"],
            "d_DR": d_dr,
            "d_CE": round(r["derived"]["CE"] - c["derived"]["CE"], 4),
            "d_T": round(r["observations"]["T_minutes"]
                         - c["observations"]["T_minutes"], 2),
        })

    # 权重敏感性: 15 组 (5 个 w_Q × 3 种剩余权重分配方式)
    # splits 的值是「剩余权重中分给覆盖 (C) 的比例」, 剩下的给速度 (S)
    splits = {
        "quality-leaning": 0.30,    # 偏质量: 覆盖 30% / 速度 70%
        "balanced": 0.50,           # 均衡:   覆盖 50% / 速度 50%
        "coverage-leaning": 0.70,   # 偏覆盖: 覆盖 70% / 速度 30%
    }
    sens = []
    for wq in (0.30, 0.40, 0.50, 0.60, 0.70):
        for sname, c_share in splits.items():
            rest = 1 - wq
            wc = round(rest * c_share, 6)
            ws = round(rest - wc, 6)
            if qi is None or ci is None or si is None:
                continue
            sei = wq * qi + wc * ci + ws * si
            sens.append({"w_Q": wq, "w_C": wc, "w_S": ws,
                         "split": sname, "SEI": round(sei, 4)})

    sei = None
    if qi is not None and ci is not None and si is not None:
        sei = round(0.50 * qi + 0.30 * ci + 0.20 * si, 4)

    summary = {
        "n_rounds": len(pairs),
        "n_ssd": len(ssd),
        "n_control": len(ctrl),
        "n_paired_rounds": len(paired_ids),
        "unpaired_rounds": unpaired,
        "medians": {
            "DR_ssd": dr_s, "DR_control": dr_c,
            "CE_ssd": ce_s, "CE_control": ce_c,
            "T_ssd_min": t_s, "T_control_min": t_c, "TR": round(tr, 4) if tr else None,
        },
        "sub_indices": {"QI": qi, "CI": ci, "SI": si},
        "SEI": sei,
        "sensitivity": sens,
        "sensitivity_all_above_half": (
            all(s["SEI"] > 0.5 for s in sens) if sens else None),
        "pairs": pairs,
        "rounds_with_zero_delivery": {
            "ssd": [r["round_id"] for r in ssd_paired
                    if r["derived"].get("DR") is None],
            "control": [r["round_id"] for r in ctrl_paired
                        if r["derived"].get("DR") is None],
        },
        # **隔离汇总** (FORMULA.md §3.4.9.5)。
        #
        # 聚合结果必须能一眼看出「这一整轮实验里隔离掉了多少东西」。
        # 逐轮逐臂的隔离数、隔离前后的 D_gate_new 都在这里, 便于事后核对。
        "quarantine": {
            "total_quarantined": sum(
                r.get("observations", {}).get("quarantined_count", 0) or 0
                for r in rounds),
            "rounds_with_quarantine": sorted({
                r.get("round_id") for r in rounds
                if r.get("observations", {}).get("quarantined_count", 0)}),
            "by_round": {
                rid: {
                    arm: {
                        "quarantined_count": rec.get(
                            "observations", {}).get("quarantined_count", 0),
                        "D_gate_new": rec.get(
                            "observations", {}).get("D_gate_new"),
                        "D_gate_new_before_quarantine": rec.get(
                            "observations", {}).get(
                                "D_gate_new_before_quarantine"),
                    }
                    for arm, rec in sorted(arms.items())
                }
                for rid, arms in sorted(by_round.items())
            },
        },
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(f"[aggregate] SEI={sei} QI={qi} CI={ci} SI={si} "
          f"n_pairs={len(pairs)} -> {args.out}")
    if unpaired:
        print(f"[WARN] {len(unpaired)} 个轮次未配对, 已排除在中位数之外: "
              f"{unpaired}")
    # **隔离汇总必须在 stdout 显式报出** (FORMULA.md §3.4.9.5)。
    # 只写在 JSON 里的话, 读报告的人看不到「这一整轮实验隔离掉了多少」。
    qsum = summary["quarantine"]
    if qsum["total_quarantined"]:
        print(f"[隔离] 全实验共剔除 {qsum['total_quarantined']} 个基线 flake 标识, "
              f"涉及轮次: {qsum['rounds_with_quarantine']}")
        for rid, arms in sorted(qsum["by_round"].items()):
            for arm, rec in sorted(arms.items()):
                if not rec["quarantined_count"]:
                    continue
                print(f"  - {rid}/{arm}: 隔离 {rec['quarantined_count']} 个, "
                      f"D_gate_new {rec['D_gate_new_before_quarantine']} "
                      f"-> {rec['D_gate_new']}")
    else:
        print("[隔离] 全实验没有触发任何基线 flake")
    return 0


def main():
    ap = argparse.ArgumentParser(description="SSD 效能测量工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("round", help="测量单轮")
    p.add_argument("--round-id", required=True)
    p.add_argument("--arm", required=True, choices=["ssd", "control"])
    p.add_argument("--repo", required=True)
    p.add_argument("--repo-path", required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--checklist", required=True,
                   help="本轮填好的共享检查表 (含 RUBRIC AC + 证据锚点)")
    p.add_argument("--repo-paths", default="",
                   help="仓库标识 → 路径映射, 形如 B=/path,C=/path")
    p.add_argument("--repo-ranges", default="",
                   help="多仓轮次的每仓起止, 形如 B=<base>:<head>,C=<base>:<head>")
    p.add_argument("--gate-log", required=True)
    p.add_argument("--baseline-gates", default="")
    p.add_argument("--review-findings", default="")
    p.add_argument("--spec-repo", default="",
                   help="规格仓路径。SSD 臂的规格产出耗时计入 T")
    p.add_argument("--spec-rel-dir", default="efficacy",
                   help="规格仓里存放各臂规格产出的相对目录 (默认 efficacy)")
    p.add_argument("--archive-root", default="",
                   help="门禁归档根目录 (默认取本仓的 docs/efficacy/gates/archives)")
    p.add_argument("--flaky-list", default="",
                   help="基线 flake 隔离清单 (默认取本仓的 docs/efficacy/flaky-tests.json)")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_round)

    p = sub.add_parser("baseline", help="采集基线门禁快照")
    p.add_argument("--repo", required=True)
    p.add_argument("--repo-path", required=True)
    p.add_argument("--gate-log", required=True)
    p.add_argument("--captured-at", default="")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_baseline)

    p = sub.add_parser("checklist", help="校验检查表与共享模板一致")
    p.add_argument("--candidate", required=True)
    p.add_argument("--checklist", required=True)
    p.set_defaults(func=cmd_checklist)

    p = sub.add_parser("aggregate", help="聚合并算 SEI")
    p.add_argument("--rounds", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_aggregate)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
