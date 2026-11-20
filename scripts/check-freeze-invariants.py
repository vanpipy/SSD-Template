#!/usr/bin/env python3
"""实验**冻结前**的总门禁: 一次性跑完所有不变量检查。

Stdlib only.

## 它守的是什么

实验在**观察任何结果之前**冻结。冻结的前提是: 评分表 (RUBRIC.md)
里每一条 AC 都有**可复核的证据** —— 规格引用指向规格仓的正确行,
代码引用指向冻结基线的正确行, 基线快照与基线日志自洽,
评分表与检查表模板一致。

任何一个不变量破了, 后面两臂拿到的分数就没有可比性。

## 跑哪些检查

| 检查 | 脚本 | 守什么 |
|------|------|--------|
| 规格引用 | `check-spec-citations.py` | `merchandising-spec/...:N` 的路径、行号、引文都对得上 |
| 代码引用 | `check-code-citations.py` | `Foo.java:N` 在**冻结 SHA** 上指向那一行 |
| 基线自洽 | `check-baseline-invariance.py` | 基线快照 == 基线日志重解析 (差集法的前提) |
| 基线来源 | `check-baseline-provenance.py` | 基线日志引用的每个测试单元都**真实存在于冻结 SHA 的树里** |
| flake 隔离自洽 | `check-flaky-quarantine.py` | 隔离清单与 12 次重复跑的证据一致 (哈希、出现次数、集合不多不少) |
| 检查表一致 | `gen-checklists.py --check` | `docs/efficacy/checklists/` 与 RUBRIC 同步 |
| 文档链接 | `check-doc-links.py` | `docs/efficacy/*.md` 里的文件链接与锚点都可达 |
| AC 数一致 | (本脚本) | RUBRIC / FORMULA / JSON 里的 AC 数都是同一个数 |

## 自洽不等于来源

「基线自洽」与「基线来源正确」是**两条独立的不变量**, 不能互相替代:

- 自洽: 快照 == 日志重解析。防的是**标识口径不一致** (例如快照用 surefire
  XML 的 `classname` 显示名、日志用 FQN, 差集恒不为空)。
- 来源: 日志里的每个测试文件 / 测试类都存在于冻结 SHA 的树里。防的是
  **采集跑在了错误的代码状态上**。

v3 基线同时踩中两条: 快照与日志用了两套标识 (7 条双向不一致), 且日志采于
**移动后的工作区 HEAD** (`fc0ed6161` / `1d4cead0`) 却标着冻结 SHA
(`688154d7` / `59fdb760`)。C 仓因此覆盖了 608 个 spec 文件, 而冻结 SHA 上
只有 430 个 —— 多出的 178 个文件**根本不存在于冻结基线**。

用这种基线做差集, 冻结基线上根本不存在的测试会被算进 `D` (新增门禁失败),
**系统性高估两臂的伤害**。所以来源校验必须与自洽校验并列, 不能省。

## 用法

    python3 scripts/check-freeze-invariants.py
    python3 scripts/check-freeze-invariants.py --verbose

退出码 0 = 全部通过, 可以冻结; 1 = 有不变量破了, **不要冻结**。
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
EFF = os.path.join(ROOT, "docs", "efficacy")
sys.path.insert(0, SCRIPTS)

# 冻结提交 SHA。由 main() 从命令行/环境变量填入。
_FREEZE_COMMIT = [os.environ.get("SSD_FREEZE_COMMIT", "")]

# 明确**不**属于本实验、因此不进冻结集的文件 (相对仓库根)。
# 用途: 修正 glob 的误收。见 frozen_file_set() 的说明。
EXCLUDED_FROM_FROZEN = {
    # 校验的是 SSD-Template 自身的机制契约 (docs/mechanism-contract.md),
    # 与本实验无关。它被 `check-*.py` 这个 glob 误收进来了。
    os.path.join("scripts", "check-acceptance.py"),
}


def run(name, args):
    """跑一个子检查, 返回 (是否通过, 输出)。"""
    cmd = [sys.executable, os.path.join(SCRIPTS, name)] + args
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return r.returncode == 0, (r.stdout + r.stderr)


def ac_count_from_rubric():
    """用**规范解析器**数 RUBRIC.md 里的 AC 条数。"""
    import rubric as R  # noqa: E402
    parsed = R.parse_rubric(os.path.join(EFF, "RUBRIC.md"))
    acs = parsed["acs"] if isinstance(parsed, dict) and "acs" in parsed else parsed
    return len(acs), acs


def ac_ids(acs):
    """从解析结果里取出 AC id 集合。"""
    ids = set()
    for a in acs:
        if isinstance(a, dict):
            for k in ("id", "ac_id", "ac"):
                if k in a:
                    ids.add(a[k])
                    break
        else:
            ids.add(str(a))
    return ids


def check_mentioned_counts(n_acs, verbose):
    """所有文档里提到的「AC 合计」数字必须等于 n_acs。

    只查**明确声称合计**的地方, 不查历史中间态的叙述
    (那是留档, 允许出现 37 / 47)。

    ## 为什么用「标签 → 数字」的成对匹配

    早期版本用单条正则 `(?:AC 合计|合计|分母)\\s*[*\\`]*\\s*(\\d+)`,
    遇到 `**AC 合计**: 28 条` 这种 **粗体标签 + 冒号** 的写法就**匹配不上**,
    于是那一行根本没进检查, 产生**假绿** (看上去通过, 实际没查)。

    现在改成: 先在行里找「声称合计」的**标签**, 再从**标签之后**取数字。
    标签与数字之间允许 `**` / `` ` `` / `:` / `=` / 空格。
    数字必须紧跟在标签之后, 否则这一行**不产生任何断言**。
    """
    problems = []
    targets = [
        os.path.join(EFF, "FORMULA.md"),
        os.path.join(EFF, "CANDIDATES.md"),
        os.path.join(EFF, "RUBRIC.md"),
        os.path.join(EFF, "DELTA-AC-VERIFICATION.md"),
    ]
    # 「声称合计」的标签。顺序敏感: 长标签在前, 避免 "AC 合计" 被 "合计" 抢先匹配。
    LABEL = re.compile(
        r"(?P<label>"
        r"AC\s*合计"
        r"|最终\s*分母"
        r"|当前\s*分母"
        r"|分母"
        r"|合计"
        r")"
        # 标签与数字之间允许的填充
        r"(?P<gap>[\s:*`=（(]*?)"
        r"(?P<num>\d+)"
        r"(?P<unit>\s*(?:条|个)?)")
    # 历史中间态的标记词。出现在**同一行**即视为留档叙述, 不计入断言。
    HISTORY = ("历史", "第一轮", "第二轮", "第三轮", "第四轮",
               "v3", "v4", "v5", "中间态", "降幅", "初版", "轨迹")
    for path in targets:
        if not os.path.isfile(path):
            continue
        rel = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh.read().splitlines(), 1):
                for m in LABEL.finditer(line):
                    n = int(m.group("num"))
                    if n == n_acs:
                        continue
                    # 允许历史中间态: 该行必须显式标注为历史
                    if any(k in line for k in HISTORY):
                        continue
                    problems.append(
                        f"{rel}:{i}: 声称的 AC 合计 {n} != 实际 {n_acs}: "
                        f"{line.strip()[:100]}")
    if verbose:
        print(f"[count] 核对 {len(targets)} 个文档里的 AC 合计声明")
    return problems


def split_md_row(line):
    """把一行 Markdown 表格切成单元格。

    `\\|` 是**转义竖线**, 属于单元格内容, 不能当分隔符。
    直接 `split("|")` 会把转义竖线当成列边界, 导致列号错位。
    """
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    cells = []
    cur = []
    i = 0
    while i < len(row):
        ch = row[i]
        if ch == "\\" and i + 1 < len(row) and row[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def check_candidate_counts(acs, verbose):
    """逐候选的 AC 数必须与 RUBRIC.md 解析结果一致。

    逐候选的条数散落在三个地方, 任何一个漏改都会让分母与分布对不上:
      - `CANDIDATES.md` §2 表格的「AC 数」列;
      - `RUBRIC.md` §6 冻结声明的「冻结 AC 数」表;
      - `candidate-verification.json` 每项的 `ac_count`。

    三处都必须等于**规范解析器**从 RUBRIC.md 算出的分布。
    """
    problems = []
    from collections import Counter
    dist = Counter(a["candidate"] for a in acs)

    # --- JSON: candidate-verification.json ---
    path = os.path.join(EFF, "candidate-verification.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        items = data if isinstance(data, list) else data.get("candidates", [])
        if isinstance(items, dict):
            items = list(items.values())
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("id") or item.get("candidate") or "?"
            if name not in dist:
                problems.append(
                    f"candidate-verification.json: 未知候选 {name} "
                    f"(RUBRIC.md 里有 {', '.join(sorted(dist))})")
                continue
            got = item.get("ac_count")
            if got is not None and got != dist[name]:
                problems.append(
                    f"candidate-verification.json: {name}.ac_count = {got} "
                    f"!= RUBRIC.md 的 {dist[name]}")

    # --- CANDIDATES.md §2 表格 ---
    cand_path = os.path.join(EFF, "CANDIDATES.md")
    if os.path.isfile(cand_path):
        with open(cand_path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for i, line in enumerate(lines, 1):
            if not re.match(r"^\|\s*`?(?:F|B|R)-\d+`?\s*\|", line):
                continue
            cells = split_md_row(line)
            if len(cells) < 6:
                continue
            cid = cells[0].strip("`").strip()
            if cid not in dist:
                continue
            cell = cells[5].strip("`").strip().strip("*")
            if not cell.isdigit():
                continue
            if int(cell) != dist[cid]:
                problems.append(
                    f"CANDIDATES.md:{i}: {cid} 的 AC 数 = {cell} "
                    f"!= RUBRIC.md 的 {dist[cid]}")

    # --- RUBRIC.md §6 冻结声明表 ---
    rub_path = os.path.join(EFF, "RUBRIC.md")
    if os.path.isfile(rub_path):
        with open(rub_path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for i, line in enumerate(lines, 1):
            if "冻结 AC 数" not in line:
                continue
            cells = [c.strip().strip("*").strip() for c in split_md_row(line)]
            # 表头行: | 候选 | F-02 | F-08 | ... | 合计 |
            header = None
            for j in range(max(0, i - 4), i):
                if "候选" in lines[j] and "F-02" in lines[j]:
                    header = [c.strip().strip("*").strip()
                              for c in split_md_row(lines[j])]
                    break
            if header is None:
                continue
            for idx, cell in enumerate(cells):
                if idx == 0 or idx >= len(header):
                    continue
                cid = header[idx]
                if cid not in dist:
                    continue
                if not cell.isdigit():
                    continue
                if int(cell) != dist[cid]:
                    problems.append(
                        f"RUBRIC.md:{i}: 冻结声明里 {cid} 的 AC 数 = {cell} "
                        f"!= 实际的 {dist[cid]}")
            # 合计列
            if "合计" in header:
                ti = header.index("合计")
                if ti < len(cells) and cells[ti].isdigit():
                    total = int(cells[ti])
                    if total != sum(dist.values()):
                        problems.append(
                            f"RUBRIC.md:{i}: 冻结声明的合计 = {total} "
                            f"!= 实际的 {sum(dist.values())}")

    if verbose:
        print(f"[count] 核对 {len(dist)} 个候选的 AC 数分布")
    return problems


def check_json_counts(n_acs, verbose):
    """JSON 元数据里的 AC 数必须等于 n_acs。

    `candidate-verification.json` 顶层是**列表** (每个候选一项),
    每项里有 `ac_count`。逐个核对。
    """
    problems = []
    path = os.path.join(EFF, "candidate-verification.json")
    if not os.path.isfile(path):
        return problems
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    items = data if isinstance(data, list) else data.get("candidates", [])
    if isinstance(items, dict):
        items = list(items.values())
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("id") or item.get("candidate") or "?"
        if "ac_count" in item and item["ac_count"] != n_acs:
            # 每个候选的 ac_count 本来就各不相同, 只有**总计**才该等于 n_acs
            if name in ("total", "all", "summary"):
                problems.append(
                    f"candidate-verification.json: {name}.ac_count = "
                    f"{item['ac_count']} != {n_acs}")
    # 若有显式的合计字段, 必须等于 n_acs
    if isinstance(data, dict):
        for k in ("ac_total", "total_ac_count", "ac_count"):
            if k in data and data[k] != n_acs:
                problems.append(
                    f"candidate-verification.json: {k} = {data[k]} != {n_acs}")
    if verbose:
        print(f"[count] 核对 candidate-verification.json ({len(items)} 项)")
    return problems


def check_frozen_files_clean(verbose):
    """冻结文件在**工作区**里必须与冻结提交一致。

    `baseline-commits.json` 是**冻结文件**: 第一轮实施开始前定死, 之后只读。
    之前 `run-round.sh init` 会往它写 `rounds` 键, 把冻结产物弄脏了。
    现在可变状态落在 `round-state.json`, 所以这个检查能守住冻结文件。

    ## 为什么只在 `--post-freeze` 下跑

    冻结**之前**, 这几个文件本来就在改 (这轮收敛就是改它们), 对 HEAD 比对
    必然报差异, 那不是不变量破了, 是还没冻结。
    所以本检查只在 `--post-freeze` 下启用, 并且要求知道**冻结提交的 SHA**。

    对比基准用 `--freeze-commit` 指定的 SHA (或 `SSD_FREEZE_COMMIT` 环境变量)。
    没有这个 SHA 时**直接失败**而不是跳过 —— 静默跳过会变成假绿。
    """
    problems = []
    base = args_freeze_commit()
    if not base:
        return ["未提供冻结提交 SHA (--freeze-commit 或 SSD_FREEZE_COMMIT), "
                "无法核对冻结文件是否被改动"]

    frozen = frozen_file_set()
    for rel in frozen:
        if not os.path.isfile(rel):
            problems.append(f"冻结文件不存在: {rel}")
            continue
        r = subprocess.run(
            ["git", "-C", ROOT, "diff", "--exit-code", base, "--", rel],
            capture_output=True, text=True)
        if r.returncode != 0:
            problems.append(
                f"冻结文件在冻结后被改动: "
                f"{os.path.relpath(rel, ROOT)} (对比 {base[:8]})")
            if verbose and r.stdout:
                for line in r.stdout.splitlines()[:20]:
                    problems.append(f"    {line}")
    if verbose:
        print(f"[frozen] 核对 {len(frozen)} 个冻结文件与 {base[:8]} 一致")
    return problems


def frozen_file_set():
    """冻结提交里**必须不可变**的文件全集。

    ## 为什么不止四个文档

    早期版本只查 `baseline-commits.json` / `RUBRIC.md` / `FORMULA.md` /
    `CANDIDATES.md` 四个。但实验的可信度不只压在评分表上:

    - **基线快照与基线日志**: 改了就等于改了「差集法」的参照系, `D` 被操纵;
    - **检查表模板**: 改了就等于改了人工评分的口径, 两臂不再同表;
    - **测量脚本** (`measure.py` / `rubric.py` / `gate_ids.py`): 改了就等于改了尺子;
    - **轮次编排** (`run-round.sh`): 改了就等于改了实验流程本身。

    这些都在冻结提交里定死, 之后只读。任何一项被改动, 两臂分数就不可比,
    而**结果一旦被观察到就不可回退** —— 所以必须由机器守住, 不能靠自觉。

    ## 为什么用 glob 而不是逐个列举

    检查表模板有 10 份、基线日志有 4 份、脚本有若干个, 逐个列举容易漏。
    这里用 glob 收集, 漏了会直接表现为「文件不存在」或「未进入冻结集」,
    不会静默放行。

    ## 选入标准: **能写出冻结产物**的脚本

    不是所有脚本都进冻结集。判据一条: 这个脚本**能不能写出一个冻结产物**。
    能, 就进; 不能, 就不进。

    - `capture-vitest-baseline.py`: 写 `baseline-gates.json` 的前端部分 -> 进。
    - `verify-candidates.py`: 写 `candidate-verification.json` -> 进。
    - `show-frozen-lines.py`: 读冻结 SHA 的源码, 是引用校验的底座 -> 进。
    - `deep-scan.py` / `scan-candidate-pool.py` / `spec-*-probe.py`: 选候选阶段的
      **探索工具**, 产物不参与评分 -> 不进。
    - `check-acceptance.py` / `check-md-schema.sh` / `check-naming.sh` /
      `check-traceability.sh` / `sync-prd.sh` / `sync-test-index.sh`:
      **SSD-Template 自身**的流程校验, 与本实验无关 -> 不进。
      (但 `check-*.py` 这个 glob 会把 `check-acceptance.py` 收进来, 所以
      下面用显式排除把它剔出去。)

    ## 故意排除的

    - `docs/efficacy/round-state.json`: 可变运行态, 已 gitignore。
    - `docs/efficacy/rounds/` 与 `summary.json`: 轮次产物, 已 gitignore。
    - `docs/efficacy/gates/` 之外的新增产物: 不在冻结集内, 由 .gitignore 管。
    """
    patterns = [
        # 评分与候选定义
        os.path.join(EFF, "RUBRIC.md"),
        os.path.join(EFF, "FORMULA.md"),
        os.path.join(EFF, "CANDIDATES.md"),
        os.path.join(EFF, "baseline-commits.json"),
        os.path.join(EFF, "baseline-gates.json"),
        os.path.join(EFF, "candidate-verification.json"),
        os.path.join(EFF, "DELTA-AC-VERIFICATION.md"),
        os.path.join(EFF, "AC-AUDIT-v5.md"),
        # 基线 flake 隔离清单 (决定哪些失败**不算**任何一臂的 D)
        #
        # 它是尺子的一部分: 清单里多一个条目, `D` 就少算一个。
        # 所以必须冻结。看到真实配对结果后不得增删 (FORMULA.md §3.4.9)。
        os.path.join(EFF, "flaky-tests.json"),
        # 隔离清单的**原始证据** (12 次重复跑的逐条分类表)。
        #
        # 清单里每一条都必须有重复跑证据 (FORMULA.md §3.4.9.4)。
        # 证据本身也要冻结, 否则事后无法核对「这个标识真的是 flake」。
        os.path.join(EFF, "evidence", "flake-study-result.tsv"),
        # 检查表模板 (人工评分口径)
        os.path.join(EFF, "checklists", "*.checklist.md"),
        # 基线日志 (差集法的参照系)
        os.path.join(EFF, "gates", "baseline-*.txt"),
        # 测量与校验脚本 (尺子)
        os.path.join(SCRIPTS, "measure.py"),
        os.path.join(SCRIPTS, "rubric.py"),
        os.path.join(SCRIPTS, "gate_ids.py"),
        os.path.join(SCRIPTS, "gen-checklists.py"),
        os.path.join(SCRIPTS, "run-round.sh"),
        os.path.join(SCRIPTS, "check-*.py"),
        # 采集与候选验证 (能写出冻结产物的脚本)
        os.path.join(SCRIPTS, "capture-vitest-baseline.py"),
        os.path.join(SCRIPTS, "verify-candidates.py"),
        os.path.join(SCRIPTS, "show-frozen-lines.py"),
        os.path.join(SCRIPTS, "test_measure.py"),
        # 门禁归档器 (写出门禁归档, 是尺子的一部分)
        #
        # `gate_archive.py` 决定「门禁产物怎么归档、归属怎么记录、完整性怎么校验」。
        # 改它 = 改「哪些失败算哪一臂的」的口径, 与改 `measure.py` 同等严重。
        # 所以它进冻结集 (归档产物本身不进, 归档产物是实验期产物)。
        os.path.join(SCRIPTS, "gate_archive.py"),
        os.path.join(SCRIPTS, "test_gate_archive.py"),
    ]
    out = []
    for pat in patterns:
        if "*" in pat:
            import glob as _glob
            out.extend(sorted(_glob.glob(pat)))
        else:
            out.append(pat)
    # 去重, 保持稳定顺序
    seen = set()
    uniq = []
    for p in out:
        rp = os.path.relpath(p, ROOT)
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    # 显式剔除不属于本实验的脚本 (被上面的 glob 误收进来的)。
    # `check-acceptance.py` 校验的是 SSD-Template 自身的机制契约
    # (docs/mechanism-contract.md), 与本实验无关, 改动它不该被报成
    # 「冻结文件被改动」。
    uniq = [p for p in uniq
            if os.path.relpath(p, ROOT) not in EXCLUDED_FROM_FROZEN]
    return uniq


def args_freeze_commit():
    """取冻结提交 SHA。由 main() 填入命令行/环境变量的值。"""
    return _FREEZE_COMMIT[0]


def main():
    ap = argparse.ArgumentParser(description="冻结前后的总门禁")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--post-freeze", action="store_true",
                    help="冻结**之后**运行。启用「冻结文件未被改动」检查, "
                         "该检查需要一个已知的冻结提交 SHA")
    ap.add_argument("--freeze-commit", default="",
                    help="冻结提交的 SHA。--post-freeze 时必填 "
                         "(或用环境变量 SSD_FREEZE_COMMIT)")
    args = ap.parse_args()

    if args.freeze_commit:
        _FREEZE_COMMIT[0] = args.freeze_commit
    if args.post_freeze and not _FREEZE_COMMIT[0]:
        print("[fatal] --post-freeze 需要 --freeze-commit 或 "
              "SSD_FREEZE_COMMIT", file=sys.stderr)
        return 2

    print("== 冻结前总门禁 ==")
    failures = []

    # --- 1. 规范解析器数 AC ---
    try:
        n_acs, acs = ac_count_from_rubric()
    except Exception as exc:  # noqa: BLE001
        print(f"[fatal] RUBRIC.md 解析失败: {exc}", file=sys.stderr)
        return 2
    print(f"  [OK] RUBRIC.md 解析出 {n_acs} 条 AC")
    ids = ac_ids(acs)
    print(f"        AC id: {', '.join(sorted(ids))}")

    # --- 2. 子检查 ---
    checks = [
        ("规格引用", "check-spec-citations.py", []),
        ("代码引用", "check-code-citations.py", []),
        ("基线自洽", "check-baseline-invariance.py", []),
        ("基线来源", "check-baseline-provenance.py", []),
        ("flake 隔离自洽", "check-flaky-quarantine.py", []),
        ("检查表一致", "gen-checklists.py", ["--check"]),
        ("文档链接", "check-doc-links.py", []),
    ]
    for label, script, extra in checks:
        ok, out = run(script, extra)
        if ok:
            print(f"  [OK] {label} ({script})")
            if args.verbose:
                print("        " + out.strip().replace("\n", "\n        "))
        else:
            print(f"  [!!] {label} ({script}) 失败")
            failures.append((label, out))

    # --- 3. 数字一致性 ---
    count_checks = [
        ("文档 AC 合计", check_mentioned_counts(n_acs, args.verbose)),
        ("逐候选 AC 数", check_candidate_counts(acs, args.verbose)),
        ("JSON AC 合计", check_json_counts(n_acs, args.verbose)),
    ]
    if args.post_freeze:
        count_checks.append(
            ("冻结文件未改动", check_frozen_files_clean(args.verbose)))
    for label, probs in count_checks:
        if probs:
            print(f"  [!!] {label} 不一致")
            failures.append((label, "\n".join(probs)))
        else:
            print(f"  [OK] {label} 一致 ({n_acs})")

    print()
    if failures:
        print(f"[fatal] {len(failures)} 项不变量破了, **不要冻结**:", file=sys.stderr)
        for label, out in failures:
            print(f"\n--- {label} ---\n{out}", file=sys.stderr)
        return 1
    print(f"[OK] 全部冻结前不变量通过 (AC = {n_acs})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
