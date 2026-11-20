#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deep-scan.py · deep 理解层学习台账扫描器

扫描本仓的规格层语料, 更新 deep/INDEX.md 的「文档清单 × 状态」段。

职责边界 (契约 docs/mechanism-contract.md I-6):
  只做三件事: 扫描语料 → 计算指纹 → 更新 deep/INDEX.md 清单段。
  **不**生成 deep/topics/ 正文 (需 agent 归纳), **不**改动 deep/ 以外的任何文件。

指纹算法:
  默认 `head` 模式: 取 HEAD 提交树里的 blob sha1 (等价 `git rev-parse HEAD:<path>`)。
    文件尚未进入 HEAD (新文件 / 未提交) 时回退工作区内容的 blob sha1, 同属 git blob sha1
    家族, 保证「未提交 → 已提交」切换时指纹不变。
  `--fingerprint-mode worktree`: 一律取工作区内容的 blob sha1, 能发现未提交的本地改动。
  非 git 工作树内: 回退 mtime + size 摘要 (前缀 m, 与 git 指纹区分)。
  指纹一律取 sha1 前 12 位十六进制。

台账合并规则 (幂等):
  - 已有行且指纹未变  → 保留原 归属主题 / 最近学习 / 状态
  - 已有行但指纹变化  → 状态改为「待更新」(保留 归属主题 与 最近学习)
  - 新文档            → 「未学习」
  - 0 字节空占位      → 自动登记「已学习」(归属主题 = 空占位, 不占学习周期)
  - 语料中已消失的文档 → 移出清单 (stdout 报告, 由学习流程记录)

语料范围 (通用, 与业务无关):
  - 目录: material/ prd/ tech_design/ plan/ test_cases/ docs/ schema/ (存在才收录, 递归 *.md)
  - 根级: 全部 *.md (README.md / AGENTS.md / HOW_TO_USE.md 等入口文档)
  - 不收录: deep/ (本层自身), skills/ scripts/ (流程资产), legacy/ (历史归档)

只重写 <!-- inventory-begin --> 与 <!-- inventory-end --> 之间的内容,
标记之外的 agent 维护段保持不动。INDEX.md 不存在则初始化骨架。

用法:
  python3 scripts/deep-scan.py
  python3 scripts/deep-scan.py --fingerprint-mode worktree
  python3 scripts/deep-scan.py --root <repo> --index <path> --quiet

退出码:
  0 = 成功 (含空语料)
  1 = 真实错误 (台账无法写入 / 清单标记缺失或错序 / 参数错误)
"""
import argparse
import datetime
import hashlib
import os
import re
import subprocess
import sys

BEGIN = "<!-- inventory-begin -->"
END = "<!-- inventory-end -->"
EMPTY_FP = "e69de29bb2d1"  # 0 字节文件的 git blob 指纹 (空 blob sha1 前 12 位)

# 清单标记必须**独占一行**才算定位点。
# 否则文档正文里提到 `<!-- inventory-begin -->` 这串字 (例如说明本文件怎么被维护)
# 会被误判为标记本身, 导致扫描器把说明段落当成清单段整段覆盖。
BEGIN_RE = re.compile(r"^[ \t]*<!--[ \t]*inventory-begin[ \t]*-->[ \t]*$", re.M)
END_RE = re.compile(r"^[ \t]*<!--[ \t]*inventory-end[ \t]*-->[ \t]*$", re.M)

# 语料目录: 与业务无关的规格层目录, 存在才收录
CORPUS_DIRS = ("material", "prd", "tech_design", "plan", "test_cases", "docs", "schema")

MD_SUFFIX = ".md"

# 文档类型 (取自层名, 与业务无关)
DOC_TYPE_BY_DIR = {
    "material": "素材",
    "prd": "PRD",
    "tech_design": "TD",
    "plan": "Plan",
    "test_cases": "用例",
    "docs": "文档",
    "schema": "Schema",
}
DOC_TYPE_ROOT = "入口"
DOC_TYPE_LAYER = "层入口"

# 台账状态
S_UNLEARNED = "未学习"
S_LEARNED = "已学习"
S_PARTIAL = "部分"
S_PENDING = "待更新"
S_DEPRECATED = "Deprecated"
STATUS_ORDER = (S_UNLEARNED, S_LEARNED, S_PARTIAL, S_PENDING, S_DEPRECATED)

BLANK = "-"  # 空单元格占位 (不用破折号, 避免与禁用字符冲突)

TABLE_HEADER = (
    "| 文档 | 类型 | 指纹 | 归属主题 | 最近学习 | 状态 |\n"
    "|------|------|------|----------|----------|------|"
)

SKELETON = """# 学习台账 (deep/INDEX.md)

> 本文件由 `scripts/deep-scan.py` 维护。
> `<!-- inventory-begin -->` 与 `<!-- inventory-end -->` 之间的内容自动生成, 不要手改。
> 标记之外的内容由学习流程维护, 扫描器永不触碰。
> 状态取值: 未学习 / 已学习 / 部分 / 待更新 / Deprecated。

## 文档清单 × 状态

{BEGIN}
{END}

## 待裁决冲突

| ID | 冲突描述 | 涉及出处 | 裁决结果 |
|----|---------|---------|---------|
| (暂无) | (暂无) | (暂无) | (暂无) |

## 周期日志

| 周期 | 日期 | 目标 | 新增要点 | 备注 |
|------|------|------|---------|------|
""".replace("{BEGIN}", BEGIN).replace("{END}", END)


def log(msg):
    sys.stdout.write("[deep-scan] %s\n" % msg)


def rel_of(root, path):
    """仓内相对路径, 统一用 / 分隔。"""
    return os.path.relpath(path, root).replace(os.sep, "/")


def collect_corpus(root):
    """收集语料文件: 规格层目录 (*.md, 递归) + 根级 *.md。"""
    files = []
    used_dirs = []
    for name in CORPUS_DIRS:
        base = os.path.join(root, name)
        if not os.path.isdir(base):
            continue
        used_dirs.append(name)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames.sort()
            for fname in sorted(filenames):
                if fname.endswith(MD_SUFFIX):
                    files.append(rel_of(root, os.path.join(dirpath, fname)))
    try:
        root_entries = sorted(os.listdir(root))
    except OSError:
        root_entries = []
    for fname in root_entries:
        full = os.path.join(root, fname)
        if fname.endswith(MD_SUFFIX) and os.path.isfile(full):
            files.append(fname)
    return sorted(set(files)), used_dirs


def doc_type(rel):
    """按层归属判定文档类型。"""
    parts = rel.split("/")
    if len(parts) == 1:
        return DOC_TYPE_ROOT
    top = parts[0]
    if len(parts) == 2 and parts[1] == "README.md":
        return DOC_TYPE_LAYER
    return DOC_TYPE_BY_DIR.get(top, DOC_TYPE_ROOT)


def blob_sha12(data):
    """git blob sha1 前 12 位 (与 `git hash-object` 逐字节等价)。"""
    header = b"blob %d\0" % len(data)
    return hashlib.sha1(header + data).hexdigest()[:12]


def mtime_size_fp(path):
    """非 git 文件的兜底指纹: mtime + size 摘要 (12 位, 以 m 开头)。"""
    st = os.stat(path)
    raw = "%d:%d" % (st.st_mtime_ns, st.st_size)
    return "m" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:11]


def _git(args, cwd):
    """跑一条 git 命令, 返回 (rc, stdout_bytes)。失败返回 (非 0, b'')。"""
    try:
        proc = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
    except (OSError, ValueError):
        return 1, b""
    if proc.returncode != 0:
        return proc.returncode, b""
    return 0, proc.stdout


def git_prefix(root):
    """若 root 在 git 工作树内, 返回 (仓根绝对路径, root 相对仓根的前缀)。

    不在 git 工作树内时返回 (None, "")。
    """
    rc, out = _git(["git", "rev-parse", "--show-toplevel"], root)
    if rc != 0:
        return None, ""
    try:
        toplevel = out.decode("utf-8", "surrogateescape").strip()
    except Exception:
        return None, ""
    if not toplevel:
        return None, ""
    toplevel = os.path.abspath(toplevel)
    try:
        prefix = rel_of(toplevel, os.path.abspath(root))
    except ValueError:
        return None, ""
    if prefix == ".":
        prefix = ""
    return toplevel, prefix


def head_blob_map(toplevel):
    """HEAD 提交树里的 path → blob sha1 映射。"""
    if not toplevel:
        return {}
    rc, out = _git(["git", "ls-tree", "-r", "-z", "--full-tree", "HEAD"], toplevel)
    if rc != 0:
        return {}
    mapping = {}
    for entry in out.split(b"\x00"):
        if not entry:
            continue
        meta, _, path = entry.partition(b"\t")
        fields = meta.split()
        if len(fields) != 3 or fields[1] != b"blob":
            continue
        mapping[path.decode("utf-8", "surrogateescape")] = fields[2].decode("ascii")
    return mapping


def compute_fingerprints(root, rels, mode):
    """计算每个语料文件的指纹。

    返回 (fps, sizes, vanished):
      fps      : {rel: 指纹}
      sizes    : {rel: 字节数}
      vanished : 扫描期间消失的路径 (读不到时跳过, 不中断整轮)
    """
    fps = {}
    sizes = {}
    vanished = []
    toplevel, prefix = git_prefix(root)
    head_map = head_blob_map(toplevel) if toplevel else {}

    for rel in rels:
        full = os.path.join(root, rel)
        try:
            with open(full, "rb") as fh:
                data = fh.read()
        except OSError:
            vanished.append(rel)
            continue
        sizes[rel] = len(data)
        work_fp = blob_sha12(data)
        if toplevel is None:
            # 非 git 工作树: mtime + size 兜底
            try:
                fps[rel] = mtime_size_fp(full)
            except OSError:
                fps[rel] = work_fp
            continue
        if mode == "worktree":
            fps[rel] = work_fp
            continue
        # head 模式: 优先取 HEAD 里的 blob sha1
        repo_rel = (prefix + "/" + rel) if prefix else rel
        head_sha = head_map.get(repo_rel)
        if head_sha:
            fps[rel] = head_sha[:12]
        else:
            # 文件尚未进入 HEAD: 回退工作区 blob sha1 (同一家族, 提交前后指纹不变)
            fps[rel] = work_fp
    return fps, sizes, vanished


def inventory_span(text):
    """返回清单段 (BEGIN, END) 的下标。标记缺失或错序时返回 None。

    只认独占一行的标记 (见 BEGIN_RE / END_RE 的说明)。
    """
    m_begin = BEGIN_RE.search(text)
    if not m_begin:
        return None
    m_end = END_RE.search(text, m_begin.end())
    if not m_end:
        return None
    return m_begin.start(), m_end.start()


def parse_existing(text):
    """解析已有清单段 → {路径: (指纹, 归属主题, 最近学习, 状态)}"""
    rows = {}
    span = inventory_span(text)
    if span is None:
        return rows
    body = text[span[0] + len(BEGIN):span[1]]
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        if cells[0] in ("文档", ""):
            continue
        if set(cells[0]) <= set("-"):
            continue
        rows[cells[0]] = (cells[2], cells[3], cells[4], cells[5])
    return rows


def rewrite_inventory(text, inventory):
    """只替换标记之间的内容, 其余字节原样保留。"""
    span = inventory_span(text)
    if span is None:
        return None
    i, j = span
    return text[:i] + BEGIN + "\n" + inventory + "\n" + text[j:]


def learned_fp_of(prev):
    """取「学习时」的指纹。

    「最近学习」列格式为 {日期}@{指纹}。无 @ 时回退指纹列兜底。
    """
    if "@" in prev[2]:
        return prev[2].split("@")[-1]
    return prev[0]


def merge_rows(corpus, fps, sizes, old, today):
    """按合并规则产出台账行。

    返回 (rows, counts, n_new, n_changed, n_stub, pending)。
      n_changed : 本轮新转入「待更新」的行数 (已在待更新的行不重复计)
    """
    rows = []
    counts = dict((s, 0) for s in STATUS_ORDER)
    n_new = n_changed = n_stub = 0
    pending = []
    for rel in corpus:
        fp = fps[rel]
        prev = old.get(rel)
        is_stub = sizes.get(rel, 1) == 0
        if is_stub:
            # 0 字节空占位: 自动登记已学习, 不占学习周期
            if prev is not None and prev[3] == S_LEARNED:
                topic, learned, state = prev[1], prev[2], S_LEARNED
            else:
                topic = "空占位"
                learned = "%s@%s" % (today, EMPTY_FP)
                state = S_LEARNED
                n_stub += 1
        elif prev is None:
            topic, learned, state = BLANK, BLANK, S_UNLEARNED
            n_new += 1
        elif prev[3] in (S_UNLEARNED, S_PENDING):
            # 未学习 / 待更新的行无需再判漂移, 原样保留
            topic, learned, state = prev[1], prev[2], prev[3]
        else:
            # 已学习 / 部分 / Deprecated: 与「学习时的指纹」比对
            lfp = learned_fp_of(prev)
            topic, learned = prev[1], prev[2]
            if lfp and lfp != fp:
                state = S_PENDING
                n_changed += 1
            else:
                state = prev[3]
        if state == S_PENDING:
            pending.append((rel, learned_fp_of(prev) if prev else "", fp))
        counts[state] = counts.get(state, 0) + 1
        rows.append((rel, doc_type(rel), fp, topic, learned, state))
    return rows, counts, n_new, n_changed, n_stub, pending


def render(rows):
    lines = [TABLE_HEADER]
    for rel, dtype, fp, topic, learned, state in rows:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (rel, dtype, fp, topic, learned, state))
    return "\n".join(lines)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="deep 理解层学习台账扫描器 (只维护 deep/INDEX.md 的清单段)")
    parser.add_argument("--root", default=None,
                        help="仓根目录, 默认取脚本所在仓根")
    parser.add_argument("--index", default=None,
                        help="台账文件路径, 默认 <root>/deep/INDEX.md")
    parser.add_argument("--fingerprint-mode", choices=("head", "worktree"), default="head",
                        help="head: 取 HEAD 提交树的 blob sha1 (契约 I-6 默认)。"
                             "worktree: 取工作区内容 blob sha1 (能发现未提交改动)")
    parser.add_argument("--quiet", action="store_true", help="不输出统计摘要")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    default_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.abspath(args.root or default_root)
    if not os.path.isdir(root):
        sys.stderr.write("[deep-scan] 错误: 仓根目录不存在: %s\n" % root)
        return 1
    index_path = os.path.abspath(args.index) if args.index else os.path.join(root, "deep", "INDEX.md")

    try:
        corpus, used_dirs = collect_corpus(root)
    except OSError as exc:
        sys.stderr.write("[deep-scan] 错误: 收集语料失败: %s\n" % exc)
        return 1

    fps, sizes, vanished = compute_fingerprints(root, corpus, args.fingerprint_mode)

    if os.path.exists(index_path):
        try:
            with open(index_path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            sys.stderr.write("[deep-scan] 错误: 读取台账失败: %s\n" % exc)
            return 1
    else:
        text = SKELETON

    if inventory_span(text) is None:
        sys.stderr.write(
            "[deep-scan] 错误: 台账缺少清单标记, 请确认 %s 含 %s 与 %s\n"
            % (index_path, BEGIN, END))
        return 1

    old = parse_existing(text)
    today = datetime.date.today().isoformat()
    rows, counts, n_new, n_changed, n_stub, pending = merge_rows(corpus, fps, sizes, old, today)

    inventory = render(rows)
    new_text = rewrite_inventory(text, inventory)
    if new_text is None:
        sys.stderr.write("[deep-scan] 错误: 台账清单段定位失败\n")
        return 1

    if new_text != text:
        try:
            parent = os.path.dirname(index_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(index_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_text)
        except OSError as exc:
            sys.stderr.write("[deep-scan] 错误: 写入台账失败: %s\n" % exc)
            return 1

    removed = sorted(set(old) - set(corpus))

    if not args.quiet:
        if index_path.startswith(root + os.sep):
            shown = rel_of(root, index_path)
        else:
            shown = index_path
        log("index=%s" % shown)
        log("fingerprint_mode=%s" % args.fingerprint_mode)
        log("corpus_dirs=%s" % (",".join(used_dirs) if used_dirs else "(none)"))
        log("scanned=%d new=%d changed_to_pending=%d stub_auto=%d existing_rows=%d"
            % (len(rows), n_new, n_changed, n_stub, len(old)))
        log("ledger: learned=%d partial=%d unlearned=%d pending=%d deprecated=%d"
            % (counts.get(S_LEARNED, 0), counts.get(S_PARTIAL, 0), counts.get(S_UNLEARNED, 0),
               counts.get(S_PENDING, 0), counts.get(S_DEPRECATED, 0)))
        log("pending_count=%d" % len(pending))
        for rel, lfp, fp in pending:
            log("pending path=%s learned_fp=%s current_fp=%s" % (rel, lfp or BLANK, fp))
        log("removed_count=%d" % len(removed))
        for rel in removed:
            log("removed path=%s" % rel)
        if vanished:
            log("vanished_count=%d" % len(vanished))
            for rel in vanished:
                log("vanished path=%s" % rel)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
