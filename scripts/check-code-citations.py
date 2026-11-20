#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对文档里的代码引用。

对 RUBRIC.md / CANDIDATES.md 里的每一处代码引用, 检查:
  1. 引用的文件在冻结 SHA 下存在;
  2. 行号落在文件范围内;
  3. 引用附近给出的**逐字引文**确实出现在被引的那几行里。

## 引文绑定规则 (按行内位置判定)

一行先切成有序 token, 再切成「引用组」:
  - **锚点** (anchor): 带行号的代码引用 (`X.vue:161`)、裸行号 (`:182`)、
    规格引用 (`xx.md:44`)、以及不带行号的文件路径 (`api/.../VO.java`)。
  - **证据** (evidence): 逐字引文 (`「...」`) 与行内代码片段 (`` `...` ``)。

每个锚点的**区段** = 它自己到下一个锚点之间的那段文字。区段里的证据
属于这个锚点。裸行号继承它前面那处带文件名的代码引用 (规格引用会切断继承)。

## 引文的三种判定

引文分两类:
  - **代码引文**: 不含中日韩字符 (`onClick`、`{"a":1}`、`tc >= total - 1`)。
  - **文本引文**: 含中日韩字符 (`「最小合格率不能大于最大合格率」`)。

代码引文**必须**逐字出现在被引的行里。若它没出现在被引行, 但出现在
该文件的**其它行**, 说明**行号指错了** —— 这是硬错误。若它在该文件里
根本不出现, 则它本来就不是这个文件的引文 (可能是规格原文或行内标识符),
不做判定。

文本引文常是**转述**而非逐字。判定放宽:
  - 出现在被引行 → 通过;
  - 出现在该文件其它行且长度 >= 6 字 → **行号指错**, 硬错误;
  - 否则 (短词或根本没出现) → 视为转述, 不判定, 只记一条提示。

## 明确排除的「证据」

  - **shell 命令** (`git grep ...`、`rg 'cellClassName'`): 是查证手段,
    不是被引文件的代码, 不参与引文判定。
  - **规格引用后的引文**: `「...」` 属于规格原文, 不算代码引文。

退出码 0 = 全部核对通过; 1 = 有引用对不上; 2 = 仓不可用。
"""

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_JSON = os.path.join(ROOT, "docs", "efficacy", "baseline-commits.json")

DOCS = [
    os.path.join(ROOT, "docs", "efficacy", "RUBRIC.md"),
    os.path.join(ROOT, "docs", "efficacy", "CANDIDATES.md"),
]

CODE_EXTS = "java|ts|tsx|vue|js|sql|xml"
# 带行号的代码引用: `Foo.java:12` / `dir/Foo.tsx:12-34` / `.../x/Foo.java:9`
RE_FILE_REF = re.compile(
    r"([A-Za-z0-9_./\-][A-Za-z0-9_./\-]*\.(?:" + CODE_EXTS + r"))"
    r":(\d+)(?:\s*[-–]\s*(\d+))?")
# 规格引用: `merchandising-spec/xx.md:12` / `移动端UI描述.md:385`
RE_SPEC_REF = re.compile(
    r"([A-Za-z0-9_./\-一-鿿][A-Za-z0-9_./\-一-鿿]*\.md)"
    r":(\d+)(?:\s*[-–]\s*(\d+))?")
# 裸行号 `:182`
RE_BARE_LINENO = re.compile(r"(?<![\w.])`:(\d+)(?:\s*[-–]\s*(\d+))?`")
# 逐字引文 「...」
RE_QUOTE = re.compile(r"「(.+?)」", re.S)
# 行内代码片段 `...`
RE_CODE_SPAN = re.compile(r"`([^`\n]+)`")
# 不带行号的文件路径 (只查存在性)
RE_FILE_PATH = re.compile(
    r"^[A-Za-z0-9_./\-][A-Za-z0-9_./\-]*\.(?:" + CODE_EXTS + r")$")
# shell 命令: 是查证手段, 不是被引文件的代码
RE_SHELL = re.compile(
    r"^\s*(git|rg|grep|ls|cat|cd|npm|pnpm|yarn|git\s+grep)\b")
# 短文件名 -> 候选仓 key 的优先级
REPO_HINTS = {
    ".java": ["B"],
    ".sql": ["B"],
    ".xml": ["B"],
    ".vue": ["C", "H5", "PCOLD"],
    ".tsx": ["H5", "C", "PCOLD"],
    ".ts": ["H5", "C", "PCOLD"],
}

# token 类型
T_FILE_REF = "file_ref"
T_SPEC_REF = "spec_ref"
T_BARE = "bare"
T_FILE_PATH = "file_path"
T_CODE = "code"
T_QUOTE = "quote"

# 文本引文长于此长度才算「有辨识度」(短词在文件里太常见)
DISTINCTIVE_LEN = 6


def load_baselines():
    with open(BASE_JSON, encoding="utf-8") as fh:
        return json.load(fh)["baselines"]


def git_show(repo_path, sha, path):
    """取冻结态某文件的内容。返回 (内容 or None, 错误信息 or None)。"""
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "show", f"{sha}:{path}"],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git 调用失败: {exc}"
    if r.returncode != 0:
        err = r.stderr.strip().splitlines()
        return None, err[-1] if err else "not found"
    return r.stdout, None


def list_files(repo_path, sha):
    """列出冻结态仓库里的全部文件路径。"""
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "ls-tree", "-r", "--name-only", sha],
            capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return r.stdout.splitlines()


def normalize_ref(ref):
    """把引用里的省略前缀去掉, 便于按后缀匹配仓内路径。"""
    r = ref
    while r.startswith("../"):
        r = r[3:]
    if r.startswith(".../"):
        r = r[4:]
    if r.startswith("-"):
        r = r.lstrip("-")
    return r


def find_candidates(files, ref):
    """在冻结态文件列表里定位引用到的文件, 返回**所有**候选。

    引用可能只给文件名 (`config.ts`), 也可能给相对路径
    (`CategoryTaskPanel/index.tsx`)。裸文件名往往在仓里不唯一
    (例如 C 仓有多个 `config.ts`), 此时返回全部候选,
    由调用方逐个尝试, 看哪个候选的行内容与引文相符。
    """
    norm = normalize_ref(ref)
    base = norm.rsplit("/", 1)[-1]
    exact = [f for f in files if f == norm or f.endswith("/" + norm)]
    if exact:
        return exact
    return [f for f in files if f.rsplit("/", 1)[-1] == base]


def strip_md(text):
    t = text.replace("**", "").replace("`", "")
    t = t.replace("\\|", "|")
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    return t


def normalize(text):
    return re.sub(r"\s+", "", strip_md(text))


def quote_matches(quote, seg):
    """引文允许显式省略 (`...` / `…`); 无省略号时必须逐字连续出现。"""
    q, s = normalize(quote), normalize(seg)
    if not q:
        return True
    if "..." not in q and "…" not in q:
        return q in s
    parts = [p for p in re.split(r"\.\.\.|…", q) if p]
    return all(p in s for p in parts)


def has_cjk(text):
    return bool(re.search(r"[一-鿿]", strip_md(text)))


def is_shell(text):
    return bool(RE_SHELL.match(strip_md(text)))


def build_tokens(line):
    """把一行拆成有序 token 列表。"""
    toks = []
    covered = []

    def overlaps(span):
        return any(span[0] < o[1] and o[0] < span[1] for o in covered)

    for m in RE_FILE_REF.finditer(line):
        toks.append((m.start(), m.end(), T_FILE_REF,
                     m.group(1), int(m.group(2)),
                     int(m.group(3)) if m.group(3) else None))
        covered.append((m.start(), m.end()))
    for m in RE_SPEC_REF.finditer(line):
        toks.append((m.start(), m.end(), T_SPEC_REF,
                     m.group(1), int(m.group(2)),
                     int(m.group(3)) if m.group(3) else None))
        covered.append((m.start(), m.end()))
    for m in RE_BARE_LINENO.finditer(line):
        if overlaps((m.start(), m.end())):
            continue
        toks.append((m.start(), m.end(), T_BARE, None,
                     int(m.group(1)),
                     int(m.group(2)) if m.group(2) else None))
        covered.append((m.start(), m.end()))
    for m in RE_CODE_SPAN.finditer(line):
        if overlaps((m.start(), m.end())):
            continue
        val = m.group(1)
        if RE_FILE_PATH.match(val):
            kind = T_FILE_PATH
        elif is_shell(val):
            continue          # shell 命令不是代码引文
        else:
            kind = T_CODE
        toks.append((m.start(), m.end(), kind, val, None, None))

    for m in RE_QUOTE.finditer(line):
        toks.append((m.start(), m.end(), T_QUOTE, m.group(1), None, None))

    toks.sort(key=lambda t: (t[0], -t[1]))
    return toks


def build_anchors(toks):
    """从 token 里抽出锚点。

    锚点 = 带行号的代码引用 / 裸行号 / 规格引用 / 不带行号的文件路径。
    裸行号继承它前面那处带文件名的代码引用; 规格引用会切断继承。
    """
    anchors = []
    owner = None
    for tok in toks:
        kind = tok[2]
        if kind == T_FILE_REF:
            owner = len(anchors)
            anchors.append({"kind": kind, "start": tok[0], "end": tok[1],
                            "file": tok[3], "a": tok[4], "b": tok[5],
                            "owner": owner})
        elif kind == T_SPEC_REF:
            owner = None
            anchors.append({"kind": kind, "start": tok[0], "end": tok[1],
                            "file": tok[3], "a": tok[4], "b": tok[5],
                            "owner": None})
        elif kind == T_BARE:
            anchors.append({"kind": kind, "start": tok[0], "end": tok[1],
                            "file": None, "a": tok[4], "b": tok[5],
                            "owner": owner})
        elif kind == T_FILE_PATH:
            owner = None
            anchors.append({"kind": kind, "start": tok[0], "end": tok[1],
                            "file": tok[3], "a": None, "b": None,
                            "owner": None})
    return anchors


def resolve_file(anchors, idx):
    """取锚点所引用的文件 (裸行号继承前面那处带文件名的引用)。"""
    anc = anchors[idx]
    if anc["file"]:
        return anc["file"]
    if anc["kind"] == T_BARE and anc["owner"] is not None:
        return anchors[anc["owner"]]["file"]
    return None


def collect_evidence(toks, anchors, idx):
    """取某锚点的证据 (区段内的 + 紧前方的)。"""
    anc = anchors[idx]
    end = anc["end"]
    if idx + 1 < len(anchors):
        seg_end = anchors[idx + 1]["start"]
    else:
        seg_end = 10 ** 9
    evidence = [t for t in toks
                if t[2] in (T_CODE, T_QUOTE) and end <= t[0] < seg_end]
    return evidence


def before_evidence(toks, anchors, idx):
    """取锚点**紧前方**的行内代码值。

    形如 `` `NO_OTHER_TEXT_TIP = '请填写纠正原因'`（`index.tsx:18`） ``。
    只有当它不属于上一个锚点的区段时才生效, 否则会张冠李戴。
    """
    anc = anchors[idx]
    limit = anc["start"]
    prev = None
    for t in toks:
        if t[1] > limit:
            break
        if t[2] in (T_FILE_REF, T_SPEC_REF, T_BARE, T_FILE_PATH):
            prev = t
    if prev is not None:
        return None
    best = None
    for t in toks:
        if t[1] > limit:
            break
        if t[2] in (T_CODE, T_QUOTE):
            best = t
    return best


def find_line_of(src, quote):
    """找出引文在文件里的行号 (1-based)。找不到返回 None。"""
    for i, line in enumerate(src, 1):
        if quote_matches(quote, line):
            return i
    return None


def verify_ref(candidates, a, b, evidence):
    """在候选文件里核对一处引用。

    返回 (结果, 错误描述)。结果为 dict:
      ok         True/False  是否通过
      matched    命中被引行的引文 (or None)
      note       转述 / 非逐字提示

    每条引文有三种状态:
      SATISFIED  逐字出现在被引行里 -> 引用正确
      WRONG_LINE 出现在该文件**其它行** -> **行号指错**, 硬错误
      NOT_IN_FILE 在该文件里根本不出现 -> 它不是这个文件的逐字引文
                 (可能是转述或归一化写法), 只记提示

    候选文件可能有多个 (裸文件名不唯一), 只要有一个同时满足
    「行号在范围内」且「没有引文指错行」就算通过。
    """
    code_ev = [e[3] for e in evidence if not has_cjk(e[3])]
    text_ev = [e[3] for e in evidence if has_cjk(e[3])]
    all_ev = code_ev + text_ev

    if not all_ev:
        # 没有引文可核, 只查行号范围
        best = None
        for rkey, meta, real in candidates:
            content, _ = git_show(meta["path"], meta["commit"], real)
            if content is None:
                continue
            n = len(content.splitlines())
            end = b if b else a
            if 1 <= a and end <= n:
                return ({"ok": True, "matched": None, "note": None,
                         "real": real, "rkey": rkey}, None)
            if best is None:
                best = f"({real} 共 {n} 行)"
        return ({"ok": False, "matched": None, "note": None,
                 "real": None, "rkey": None},
                f"行号越界 :{a}{'-' + str(b) if b else ''} {best or ''}")

    best_fail = None
    range_fail = None
    best_note = None
    any_in_range = False

    for rkey, meta, real in candidates:
        content, _ = git_show(meta["path"], meta["commit"], real)
        if content is None:
            continue
        src = content.splitlines()
        end = b if b else a
        if a < 1 or end > len(src):
            if range_fail is None:
                range_fail = (f"行号越界 :{a}{'-' + str(b) if b else ''} "
                              f"({real} 共 {len(src)} 行)")
            continue
        any_in_range = True

        seg = " ".join(src[a - 1:end])
        whole = "\n".join(src)

        satisfied = []
        wrong = []
        notin = []
        for q in all_ev:
            if quote_matches(q, seg):
                satisfied.append(q)
            elif quote_matches(q, whole) and (
                    not has_cjk(q)
                    or len(normalize(q)) >= DISTINCTIVE_LEN):
                wrong.append(q)
            else:
                notin.append(q)

        if satisfied:
            return ({"ok": True, "matched": satisfied[0],
                     "note": None, "real": real, "rkey": rkey}, None)

        # 没有一条引文命中被引行: 判断是不是「行号指错」
        wrong = []
        for q in all_ev:
            if quote_matches(q, whole) and (
                    not has_cjk(q)
                    or len(normalize(q)) >= DISTINCTIVE_LEN):
                wrong.append(q)
        if wrong:
            q = wrong[0]
            actual = find_line_of(src, q)
            where = f"实际在 :{actual}" if actual else "在该文件其它行"
            if best_fail is None:
                best_fail = (f"引文与被引行不符 :{a}{'-' + str(b) if b else ''} "
                             f"({real}) -> {where}\n"
                             f"        引文: {strip_md(q)[:120]}")
            continue

        # 引文都不在这个文件里逐字出现 -> 转述 / 归一化写法
        if best_note is None and notin:
            best_note = (f"引文非逐字 (转述或归一化写法), 未命中 "
                         f":{a}{'-' + str(b) if b else ''} ({real}) -> "
                         f"「{strip_md(notin[0])[:60]}」")

    # 优先报「引文与被引行不符」, 其次报「行号越界」
    if best_fail:
        return ({"ok": False, "matched": None, "note": best_note,
                 "real": None, "rkey": None}, best_fail)
    if range_fail and not any_in_range:
        return ({"ok": False, "matched": None, "note": best_note,
                 "real": None, "rkey": None}, range_fail)
    if best_note:
        return ({"ok": True, "matched": None, "note": best_note,
                 "real": None, "rkey": None}, None)
    return ({"ok": False, "matched": None, "note": None,
             "real": None, "rkey": None},
            f"无法定位引用 :{a}{'-' + str(b) if b else ''} "
            f"(所有 {len(candidates)} 个候选文件都不匹配)")


def repo_candidates(filelists, baselines, ref):
    """按扩展名提示排序, 在所有仓里找出该引用的候选文件。"""
    ext = "." + ref.rsplit(".", 1)[-1]
    hinted = [k for k in REPO_HINTS.get(ext, []) if k in baselines]
    rest = [k for k in baselines if k not in hinted]
    out = []
    seen = set()
    for rkey in hinted + rest:
        for real in find_candidates(filelists[rkey], ref):
            key = (rkey, real)
            if key in seen:
                continue
            seen.add(key)
            out.append((rkey, baselines[rkey], real))
    return out


def main():
    ap = argparse.ArgumentParser(description="核对代码引用的文件、行号与内容")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(BASE_JSON):
        print(f"[code] 缺少 {BASE_JSON}", file=sys.stderr)
        return 2
    baselines = load_baselines()

    filelists = {}
    for key, meta in baselines.items():
        path = meta["path"]
        if not os.path.isdir(path):
            print(f"[code] 仓不可用: {key} -> {path}", file=sys.stderr)
            return 2
        filelists[key] = list_files(path, meta["commit"])

    problems = []
    warnings = []
    checked = 0
    unresolved = []

    for doc in DOCS:
        if not os.path.isfile(doc):
            continue
        rel_doc = os.path.relpath(doc, ROOT)
        with open(doc, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for lineno, line in enumerate(lines, 1):
            toks = build_tokens(line)
            anchors = build_anchors(toks)

            for idx, anc in enumerate(anchors):
                if anc["kind"] == T_SPEC_REF:
                    continue
                ref = resolve_file(anchors, idx)
                if not ref:
                    continue
                checked += 1
                cands = repo_candidates(filelists, baselines, ref)
                if not cands:
                    unresolved.append(
                        f"{rel_doc}:{lineno}: 找不到文件: {ref}")
                    continue

                if anc["kind"] == T_FILE_PATH:
                    # 不带行号的文件路径: 只查存在性
                    if args.verbose:
                        print(f"[code] {rel_doc}:{lineno} -> 存在 {ref}")
                    continue

                a, b = anc["a"], anc["b"]
                evidence = collect_evidence(toks, anchors, idx)
                before = before_evidence(toks, anchors, idx)
                if before is not None and before not in evidence:
                    evidence.append(before)

                res, detail = verify_ref(cands, a, b, evidence)
                if not res["ok"]:
                    problems.append(f"{rel_doc}:{lineno}: {detail}")
                    continue
                if res["note"]:
                    warnings.append(f"{rel_doc}:{lineno}: {res['note']}")
                if args.verbose:
                    print(f"[code] {rel_doc}:{lineno} -> {res['rkey']}:"
                          f"{res['real']}:{a}{'-' + str(b) if b else ''}"
                          f"{' [引文已核]' if res['matched'] else ''}")

    print()
    print(f"[code] 核对 {checked} 处代码引用, 涉及 {len(DOCS)} 个文档")
    if unresolved:
        print(f"[code] 无法定位 {len(unresolved)} 处:", file=sys.stderr)
        for u in unresolved:
            print(f"  ? {u}", file=sys.stderr)
    if problems:
        print(f"[code] 失败 {len(problems)} 项:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
    if warnings:
        print(f"[code] 提示 {len(warnings)} 条 (引文为转述, 未逐字命中):",
              file=sys.stderr)
        for w in warnings:
            print(f"  ! {w}", file=sys.stderr)
    if problems or unresolved:
        return 1
    print("[OK] 全部代码引用的文件、行号与引文均可用")
    return 0


if __name__ == "__main__":
    sys.exit(main())
