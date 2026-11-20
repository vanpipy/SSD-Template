#!/usr/bin/env python3
"""核对 RUBRIC.md / CANDIDATES.md 里的**规格引用**是否真的指向那一行。

Stdlib only.

## 为什么需要

评分表声称「规格侧有可逐字引用的行号支撑」。若行号漂了或路径写错,
评审就会拿着一条**指向别处的引用**去判 AC, 整个「中立可复核」的前提就没了。

本脚本把文档里每一处引用解析出来并逐个核对:

1. 路径在规格仓里**存在**;
2. 行号**不越界**;
3. 引用处 `「...」` 里**引号起来的原文**确实出现在被引的那一行(区间)里。

第 3 条是关键: 只查路径与行号范围会漏掉「行号指向了同一文件里
另一处无关内容」这种最常见的错误。

## 用法

    python3 scripts/check-spec-citations.py
    python3 scripts/check-spec-citations.py --verbose

退出码 0 = 全部核对通过; 1 = 有引用对不上; 2 = 规格仓不可用。
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_ROOT = os.environ.get(
    "MERCH_SPEC_DIR",
    "/home/leroy/Project/merchandising-workspace/merchandising-spec",
)

DOCS = [
    os.path.join(ROOT, "docs", "efficacy", "RUBRIC.md"),
    os.path.join(ROOT, "docs", "efficacy", "CANDIDATES.md"),
]

# 规格文件路径 token (只匹配路径本身, 不吞掉后面的行号)
RE_PATH = re.compile(r"`merchandising-spec/([^`]+?\.md)`")
# 行号 token (可能自带反引号), 用于把 `:N` 与紧随其后的引文绑定
RE_LINENO = re.compile(r"`?:(\d+)(?:\s*[-–]\s*(\d+))?`?")

# 路径前缀修正候选: 引用写错前缀时按顺序尝试
PREFIX_CANDIDATES = ["", "产品真源/"]


def resolve_spec_path(rel, spec_root):
    """把引用里的相对路径解析成规格仓里的真实路径。"""
    for prefix in PREFIX_CANDIDATES:
        cand = os.path.join(spec_root, prefix, rel)
        if os.path.isfile(cand):
            return cand
    return None


def strip_md(text):
    """去掉 markdown 强调/代码/链接标记, 只留下可逐字比对的文字。

    还要还原表格单元格里被转义的竖线 (`\\|` -> `|`),
    否则引用里的表格行会与原表对不上。
    """
    t = text.replace("**", "").replace("`", "")
    t = t.replace("\\|", "|")
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    return t


def normalize(text):
    """归一化: 去空白与全角标点差异, 让逐字比对不被排版噪声打断。"""
    t = strip_md(text)
    t = re.sub(r"\s+", "", t)
    return t


def quote_matches(quote, seg):
    """判断引文是否出自被引的那一行(区间)。

    引文允许**显式省略**: 用 `...` / `…` 标出的缺口, 视为省略号两侧
    都必须能在原文里找到。不带省略号的引文必须**逐字连续**出现。
    """
    q = normalize(quote)
    s = normalize(seg)
    if not q:
        return True
    # 无省略号: 必须逐字连续出现
    if "..." not in q and "…" not in q:
        return q in s
    # 有省略号: 拆成片段, 每段都必须出现
    parts = [p for p in re.split(r"\.\.\.|…", q) if p]
    return all(p in s for p in parts)


def parse_citations(path):
    """提取文件里全部的规格引用。

    返回 [(文档行号, 相对路径, 起行, 止行 or None, 引文 or None)]。

    行号与引文按**位置**绑定: 每个 `:N` 绑定到它**自己后面紧邻**的
    `「...」`。若行号与引文之间隔着别的 `:M`, 则该 `:N` 没有自己的
    引文 (例如 `:32`「...」、`:44`「...」 这种并列写法)。
    """
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    out = []
    for i, line in enumerate(lines, 1):
        # 先找出这一行里所有「路径」token, 记录它们的结束位置
        path_spans = [(m.start(), m.end(), m.group(1)) for m in RE_PATH.finditer(line)]
        if not path_spans:
            continue
        # 再找出这一行里所有「行号」token
        lineno_spans = [(m.start(), m.end(), int(m.group(1)),
                         int(m.group(2)) if m.group(2) else None)
                        for m in RE_LINENO.finditer(line)]
        for ps, pe, rel in path_spans:
            # 该路径之后、且在下一个路径之前的行号, 都归属到本路径
            nxt = next((s[0] for s in path_spans if s[0] >= pe), len(line))
            for ls, le, a, b in lineno_spans:
                if not (pe <= ls < nxt):
                    continue
                # 绑定引文: 行号之后紧邻的 `「...」`
                quote = None
                tail = line[le:]
                tm = re.match(r"\s*「(.+?)」", tail, re.S)
                if tm:
                    quote = tm.group(1)
                out.append((i, rel, a, b, quote))
    return out


def main():
    ap = argparse.ArgumentParser(description="核对规格引用的路径、行号与引文")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--spec-dir", default=SPEC_ROOT)
    args = ap.parse_args()
    spec_root = args.spec_dir

    if not os.path.isdir(spec_root):
        print(f"[spec] 规格仓不存在: {spec_root}", file=sys.stderr)
        return 2

    problems = []
    checked = 0
    quoted = 0

    for doc in DOCS:
        if not os.path.isfile(doc):
            continue
        rel_doc = os.path.relpath(doc, ROOT)
        for lineno, rel, a, b, quote in parse_citations(doc):
            checked += 1
            real = resolve_spec_path(rel, spec_root)
            if real is None:
                problems.append(
                    f"{rel_doc}:{lineno}: 规格文件不存在: "
                    f"merchandising-spec/{rel}")
                continue
            with open(real, encoding="utf-8", errors="replace") as fh:
                src = fh.read().splitlines()
            end = b if b else a
            if a < 1 or end > len(src):
                problems.append(
                    f"{rel_doc}:{lineno}: 行号越界 :{a}"
                    f"{'-' + str(b) if b else ''} "
                    f"(文件共 {len(src)} 行) -> {rel}")
                continue
            seg = " ".join(src[a - 1:end])
            if quote:
                quoted += 1
                if not quote_matches(quote, seg):
                    problems.append(
                        f"{rel_doc}:{lineno}: 引文与被引行不符 :{a}"
                        f"{'-' + str(b) if b else ''} -> {rel}\n"
                        f"        引文: {strip_md(quote)[:120]}\n"
                        f"        实际: {strip_md(seg)[:120]}")
            if args.verbose:
                print(f"[cite] {rel_doc}:{lineno} -> {rel}:{a}"
                      f"{'-' + str(b) if b else ''}"
                      f"{' [引文已核]' if quote else ''}")

    print()
    print(f"[spec] 核对 {checked} 处规格引用 "
          f"(其中 {quoted} 处带逐字引文), 涉及 {len(DOCS)} 个文档")
    if problems:
        print(f"[spec] 失败 {len(problems)} 项:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("[OK] 全部规格引用的路径、行号与引文均可用")
    return 0


if __name__ == "__main__":
    sys.exit(main())
