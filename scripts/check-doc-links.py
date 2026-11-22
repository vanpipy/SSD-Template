#!/usr/bin/env python3
"""check-doc-links.py — 仓内 Markdown 相对链接检查（死链门禁）

职责(契约 M1 / M8):
  - 扫描**全仓**受版本控制的 Markdown 文件, 解析相对链接, 报告**死链**(目标文件不存在)。
  - 模板占位路径(`{topic}` / `{YYYY-MM-DD}` / `{仓库标识}` 等任何含 `{}` 的路径)**不是错误**。
  - 行号锚点(`#L12`)**不是错误**(只校验文件部分存在)。
  - 段内锚点(`#小节标题`)解析不到时只报 ⚠ 警告, 不改退出码(避免中文标题 slug 误报)。
  - 外部链接(http/https/mailto/协议相对)**不检查**(无网络, 契约 M12 禁止网络访问)。

退出码(契约 M1): 0=无死链 1=存在死链 2=调用错误 / 环境错误

用法:
    scripts/check-doc-links.py [--json] [--root DIR]

依赖: 仅 Python 3 标准库(契约 M9: shell 门禁不得依赖 python; 本脚本是独立程序,
      由 CI 的 python3 直接执行)。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata

# Markdown 链接: [text](target) / [text](<target>) / [text](target "title")
LINK_RE = re.compile(r"\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
# 标题行: # / ## / ### ...
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$", re.MULTILINE)
# 占位符: 路径任意一段含 {..}
PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")
# 行号锚点: #L12 / #L12-L20
LINE_ANCHOR_RE = re.compile(r"^L\d+(-L?\d+)?$")
EXTERNAL_RE = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//)")


def git_tracked_md(root: str) -> list[str] | None:
    """返回受版本控制的 .md 文件相对路径; 不是 git 仓库时返回 None。"""
    try:
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "-z", "--", "*.md"],
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if out.returncode != 0:
        return None
    files = [p.decode("utf-8", "replace") for p in out.stdout.split(b"\0") if p]
    return files or []


def walk_md(root: str) -> list[str]:
    """非 git 场景: 遍历目录树收集 .md。"""
    skip_dirs = {".git", ".swarm", "node_modules", ".venv", "venv", "__pycache__"}
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in filenames:
            if name.lower().endswith(".md"):
                full = os.path.join(dirpath, name)
                found.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return found


def gh_slug(text: str) -> str:
    """GitHub 风格标题 slug(小写、去标点、空格转连字符、保留 CJK)。"""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.strip().lower()
    out = []
    for ch in text:
        if ch.isalnum() or ch in "-_" or ord(ch) > 0x7F:
            out.append(ch)
        elif ch in " \t":
            out.append("-")
        elif unicodedata.category(ch).startswith("P") or unicodedata.category(ch).startswith("S"):
            continue
        else:
            out.append(ch)
    slug = "".join(out)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def collect_anchors(text: str) -> set[str]:
    anchors = set()
    for _, title in HEADING_RE.findall(text):
        anchors.add(gh_slug(title))
    for m in re.finditer(r"<a\s+(?:id|name)=\"([^\"]+)\"", text):
        anchors.add(m.group(1).lower())
    return anchors


def is_placeholder(path: str) -> bool:
    return bool(PLACEHOLDER_RE.search(path))


def check_file(root: str, rel: str, errors: list[str], warnings: list[str], stats: dict) -> None:
    full = os.path.join(root, rel.replace("/", os.sep))
    if not os.path.isfile(full):
        return
    text = read_text(full)
    anchors_cache: dict[str, set[str]] = {}
    base_dir = os.path.dirname(full)
    for match in LINK_RE.finditer(text):
        raw = match.group(1).strip()
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1]
        if not raw:
            continue
        if EXTERNAL_RE.match(raw):
            continue
        stats["links"] += 1
        line_no = text.count("\n", 0, match.start()) + 1

        target, _, fragment = raw.partition("#")
        fragment = fragment.strip()

        if not target:
            # 同文件锚点
            if fragment and not LINE_ANCHOR_RE.match(fragment):
                if rel not in anchors_cache:
                    anchors_cache[rel] = collect_anchors(text)
                if gh_slug(fragment) not in anchors_cache[rel]:
                    warnings.append(f"{rel}:{line_no} — 段内锚点在本文件找不到: #{fragment}")
            continue

        # 绝对路径 / Windows 盘符 → 不检查
        if target.startswith("/") or re.match(r"^[a-zA-Z]:[\\/]", target):
            continue

        # 模板占位路径 → 不是错误
        if is_placeholder(target):
            continue

        decoded = target.split("?", 1)[0].split("#", 1)[0]
        decoded = decoded.replace("%20", " ")
        resolved = os.path.normpath(os.path.join(base_dir, decoded.replace("/", os.sep)))
        if not os.path.exists(resolved):
            errors.append(f"{rel}:{line_no} — 死链: {raw} (目标不存在)")
            continue
        # 行号锚点 → 只校验文件存在
        if fragment and LINE_ANCHOR_RE.match(fragment):
            continue
        if fragment:
            tgt_rel = os.path.relpath(resolved, root).replace(os.sep, "/")
            if tgt_rel not in anchors_cache:
                try:
                    anchors_cache[tgt_rel] = collect_anchors(read_text(resolved))
                except OSError:
                    anchors_cache[tgt_rel] = set()
            if gh_slug(fragment) not in anchors_cache[tgt_rel]:
                warnings.append(f"{rel}:{line_no} — 段内锚点在目标文件中找不到: {raw}")


def main(argv: list[str]) -> int:
    # Windows 控制台默认 GBK, 直接打印 ✓/✗/中文会抛 UnicodeEncodeError; 强制 UTF-8 输出
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        prog="check-doc-links.py",
        description="检查仓内 Markdown 相对链接(死链)",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--root", default=None, help="仓库根目录(默认: 脚本所在目录的父目录)")
    args = parser.parse_args(argv)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = args.root or os.path.dirname(script_dir)
    if not os.path.isdir(root):
        sys.stderr.write(f"✗ --root 目录不存在: {root}\n")
        return 2
    root = os.path.abspath(root)

    files = git_tracked_md(root)
    tracked = files is not None
    if files is None:
        files = walk_md(root)

    errors: list[str] = []
    warnings: list[str] = []
    stats = {"links": 0}
    for rel in sorted(files):
        check_file(root, rel, errors, warnings, stats)

    status = "violation" if errors else "pass"
    exit_code = 1 if errors else 0

    if args.json:
        print(json.dumps({
            "script": "check-doc-links.py",
            "root": root,
            "status": status,
            "exit_code": exit_code,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "checked_files": len(files),
            "links": stats["links"],
            "tracked_files": tracked,
            "errors": errors,
            "warnings": warnings,
        }, ensure_ascii=False))
    else:
        for w in warnings:
            print(f"⚠ {w}")
        for e in errors:
            print(f"✗ {e}")
        if errors:
            print(f"✗ 发现 {len(errors)} 条死链 (检查 {len(files)} 个文件, {stats['links']} 条链接)")
        else:
            print(f"✓ 文档链接检查通过 (检查 {len(files)} 个文件, {stats['links']} 条链接)")

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
