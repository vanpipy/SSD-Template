#!/usr/bin/env python3
"""检查 docs/efficacy/ 下的 Markdown 链接与锚点是否可达。

只做**链接可达性**这一件事, 不检查内容正确性。

- 文件链接: 目标文件必须存在 (相对本文件所在目录)。
- 锚点链接: 目标文件里必须有对应标题, 且锚点 slug 按 GitHub 的规则计算。

GitHub 锚点规则:
    标题转小写 -> 去掉行内代码的反引号与强调星号 -> 删掉标点
    (保留字母数字、下划线、连字符、CJK) -> 空格换成连字符。

    注意: 连字符本身**保留**, 所以标题里的 ` - ` (空格-连字符-空格)
    会变成 `--` (两个连字符), 而不是 `-`。这是本脚本存在的理由:
    之前人工拼的锚点在这个细节上错了三处。

用法:
    python3 scripts/check-doc-links.py           # 全部检查
    python3 scripts/check-doc-links.py --quiet   # 只在失败时输出

退出码: 0 = 全部可达, 1 = 有断链, 2 = 用法错误。
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_DIR = os.path.join(ROOT, "docs", "efficacy")

# Markdown 行内链接: [文本](目标) 或 [文本](目标#锚点)
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)


def gh_slug(heading):
    """按 GitHub 的规则算标题锚点。"""
    s = heading.strip().lower()
    # 去掉行内代码的反引号与强调星号
    s = s.replace("`", "").replace("*", "").replace("_", "_")
    # 删掉标点, 保留字母数字、下划线、连字符、CJK
    s = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", s, flags=re.UNICODE)
    # 空格换成连字符 (连字符本身保留, 所以 " - " 会变成 "--")
    return s.replace(" ", "-")


def collect_anchors(path):
    """收集一个文件里所有标题的锚点。"""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return {gh_slug(m.group(1)) for m in HEADING_RE.finditer(text)}


def main():
    quiet = "--quiet" in sys.argv
    docs = sorted(glob.glob(os.path.join(DOC_DIR, "*.md")))
    if not docs:
        print(f"没有找到文档: {DOC_DIR}", file=sys.stderr)
        return 2

    anchors_by_file = {os.path.basename(p): collect_anchors(p) for p in docs}

    broken = []
    n_links = 0
    for p in docs:
        with open(p, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        rel = os.path.relpath(p, ROOT)
        for lineno, line in enumerate(lines, 1):
            # 跳过围栏代码块里的内容
            if line.lstrip().startswith("```"):
                continue
            for m in LINK_RE.finditer(line):
                target = m.group(2)
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                n_links += 1
                if "#" in target:
                    rel_path, frag = target.split("#", 1)
                else:
                    rel_path, frag = target, None
                base = os.path.basename(rel_path)
                if not rel_path:
                    # 纯锚点链接, 指向本文件
                    if frag and frag not in anchors_by_file[os.path.basename(p)]:
                        broken.append((rel, lineno, target,
                                      f"本文件的锚点 '{frag}' 不存在"))
                    continue
                if base not in anchors_by_file:
                    full = os.path.join(os.path.dirname(p), rel_path)
                    if not os.path.isfile(full):
                        broken.append((rel, lineno, target, "目标文件不存在"))
                    continue
                if frag and frag not in anchors_by_file[base]:
                    broken.append((rel, lineno, target,
                                  f"锚点 '{frag}' 不在 {base} 里"))

    if broken:
        print(f"[FAIL] {len(broken)} 处断链 (共检查 {n_links} 条链接):",
              file=sys.stderr)
        for rel, lineno, target, why in broken:
            print(f"  - {rel}:{lineno}", file=sys.stderr)
            print(f"      {target}", file=sys.stderr)
            print(f"      <- {why}", file=sys.stderr)
        return 1

    if not quiet:
        print(f"[OK] {len(docs)} 个文档, {n_links} 条链接全部可达")
    return 0


if __name__ == "__main__":
    sys.exit(main())
