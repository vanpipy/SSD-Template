#!/usr/bin/env python3
"""Lead 自用验收脚本(已入库于 scripts/acceptance/,随仓分发)。

按实施契约 §10 的 A-1..A-10 逐条验收「agent 为主」改造。
用法:
    python scripts/acceptance/agent-first-acceptance.py [--write] [--keep]

    --write  额外执行 sync-prd 写模式并检查 README/material 漂移(会改文件,仅在所有 lane 结束后跑)
    --keep   保留临时副本(调试用)

退出码:0 全部通过 / 1 有失败项 / 2 用法错。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows GBK 控制台会吃掉中文与 ✓ —— 入口一律重配为 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable


def _pick_bash() -> str:
    """优先 Git Bash。PATH 上的 C:\\Windows\\System32\\bash.exe 是 WSL 转发器,不可用。"""
    for cand in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ):
        if Path(cand).exists():
            return cand
    which = shutil.which("bash")
    if which and "system32" not in which.lower():
        return which
    raise SystemExit("找不到可用的 Git Bash")


BASH = _pick_bash()
GIT = shutil.which("git") or "git"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

RESULTS: list[tuple[str, bool, str]] = []


def record(check_id: str, ok: bool, detail: str) -> None:
    RESULTS.append((check_id, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {check_id}: {detail}")


def sh(script: str, cwd: Path, timeout: int = 300) -> tuple[int, str]:
    p = subprocess.run(
        [BASH, "-c", script],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ENV,
        timeout=timeout,
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def py_run(args: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str]:
    p = subprocess.run(
        [PY, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ENV,
        timeout=timeout,
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- A-1 既有门禁
GATES = [
    ("check-line-endings.sh", "bash scripts/check-line-endings.sh"),
    ("check-naming.sh", "bash scripts/check-naming.sh"),
    ("check-md-schema.sh", "bash scripts/check-md-schema.sh"),
    ("check-traceability.sh", "bash scripts/check-traceability.sh"),
    ("check-repo-baseline.sh", "bash scripts/check-repo-baseline.sh"),
    ("check-doc-links.py", f'"{PY}" scripts/check-doc-links.py'),
    ("sync-prd.sh --check", "bash scripts/sync-prd.sh --check"),
    ("sync-test-index.sh --check", "bash scripts/sync-test-index.sh --check"),
]


def a1_gates(cwd: Path) -> None:
    bad = []
    for name, cmd in GATES:
        rc, out = sh(cmd, cwd)
        if rc != 0 or not out.strip():
            bad.append(f"{name}(rc={rc},stdout={len(out.strip())}B)")
    if bad:
        record("A-1", False, "既有门禁异常: " + "; ".join(bad))
    else:
        record("A-1", True, f"既有 {len(GATES)} 个门禁全 exit 0 且 stdout 非空")


# ---------------------------------------------------------------- A-2/A-3 新能力
def a2_new_cli(cwd: Path) -> None:
    rc, out = py_run(["scripts/ssdctl.py", "gate"], cwd)
    if rc != 0 or not out.strip():
        record("A-2", False, f"ssdctl gate 异常(rc={rc},stdout={len(out.strip())}B): {out.strip()[:200]}")
        return
    rc2, out2 = py_run(["scripts/ssdctl.py", "scan", "--check"], cwd)
    if rc2 != 0 or not out2.strip():
        record("A-2", False, f"ssdctl scan --check 异常(rc={rc2}): {out2.strip()[:200]}")
        return
    record("A-2", True, "ssdctl gate + scan --check 均 exit 0 且 stdout 非空")


def a3_unit_tests(cwd: Path) -> None:
    rc, out = py_run(
        ["-m", "unittest", "discover", "-s", "scripts/tests", "-t", "scripts/tests"], cwd
    )
    tail = out.strip().splitlines()[-3:] if out.strip() else []
    record("A-3", rc == 0, f"判据引擎单测 rc={rc}: {' | '.join(tail)}")


# ---------------------------------------------------------------- A-4 反证
def a4_counterexample(cwd: Path) -> None:
    fixture = cwd / "docs/evidence/a17-run2/example-feature.migrated.md"
    if not fixture.exists():
        record("A-4", False, "迁移件 example-feature.migrated.md 不存在")
        return
    rc, out = py_run(["scripts/ssdctl.py", "criteria", str(fixture)], cwd)
    hit = "AC-5" in out
    if rc == 1 and hit:
        record("A-4", True, "迁移件被判失败并点名 AC-5(rc=1)")
    else:
        record("A-4", False, f"迁移件未按预期报错(rc={rc}, 含AC-5={hit}): {out.strip()[:300]}")


# ---------------------------------------------------------------- 临时副本上的写路径测试
def copy_repo(dst: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="sddfirst-"))
    clone = tmp / "repo"
    shutil.copytree(
        ROOT, clone, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc")
    )
    return clone


def a5_negative(cwd: Path) -> None:
    """负用例:判据不全绿 ⇒ advance 退出 1 且目标文件零改动。"""
    target = cwd / "prd/2026-11-22/zz-negative-case.md"
    src = cwd / "docs/evidence/a17-run2/example-feature.migrated.md"
    if not src.exists():
        record("A-5", False, "缺迁移件,无法构造负用例")
        return
    shutil.copyfile(src, target)
    before = sha(target)
    rc, out = py_run(["scripts/ssdctl.py", "advance", str(target), "--to", "Ready"], cwd)
    after = sha(target)
    if rc == 1 and before == after:
        record("A-5", True, "无授权 advance rc=1 且目标文件零改动")
    else:
        record("A-5", False, f"负用例异常(rc={rc}, 文件被改={before != after}): {out.strip()[:200]}")


def a5b_human_actor_guard(cwd: Path) -> None:
    """规则 5:人工 handle 无决定记录 ⇒ advance 必须拒绝且零改动(防 agent 冒充人工)。"""
    target = cwd / "prd/2026-11-22/layer-checklist.md"
    if not target.exists():
        record("A-5b", False, "仓内唯一制品不存在")
        return
    before = sha(target)
    rc, out = py_run(
        ["scripts/ssdctl.py", "advance", str(target), "--to", "Ready", "--actor", "alice"], cwd
    )
    after = sha(target)
    ok = rc == 1 and before == after
    record(
        "A-5b",
        ok,
        f"人工署名无决定记录 rc={rc}(期望 1), 文件零改动={before == after}, 输出={out.strip()[:120]}",
    )


def a6_evidence(cwd: Path) -> None:
    """正例:判据全绿的制品 advance 成功 ⇒ 证据链可回读。"""
    target = cwd / "prd/2026-11-22/layer-checklist.md"
    if not target.exists():
        record("A-6", False, "仓内唯一制品不存在")
        return
    rc, out = py_run(
        ["scripts/ssdctl.py", "advance", str(target), "--to", "Ready", "--actor", "agent:acceptance-bot"], cwd
    )
    if rc != 0:
        record("A-6", False, f"advance 未成功(rc={rc}): {out.strip()[:300]}")
        return
    rc2, out2 = py_run(["scripts/ssdctl.py", "evidence", "--artifact", "prd/2026-11-22/layer-checklist.md"], cwd)
    ok = rc2 == 0 and ("Ready" in out2)
    record("A-6", ok, f"证据链可回读(rc={rc2}): {out2.strip()[:160]}")


def a7_human_loop(cwd: Path) -> None:
    """人工介入回路:手写决定文件 ⇒ advance 消费 ⇒ 证据链含 decision 引用。"""
    dec_dir = cwd / "control/decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)
    dec = dec_dir / "2026-11-22-acceptance.md"
    dec.write_text(
        "# 人工介入记录 · acceptance\n\n"
        "> **决定 ID**: D1\n"
        "> **时间**: 2026-11-22T23:30:00+08:00\n"
        "> **操作人**: acceptance-bot\n"
        "> **目标制品**: prd/2026-11-22/layer-checklist.md\n"
        "> **动作**: approve\n"
        "> **范围**: all\n"
        "> **理由**: 验收用例:人工介入通道可用\n",
        encoding="utf-8",
    )
    target = cwd / "prd/2026-11-22/layer-checklist.md"
    rc, out = py_run(
        [
            "scripts/ssdctl.py", "advance", str(target), "--to", "Ready",
            "--actor", "acceptance-bot",
            "--decision", "control/decisions/2026-11-22-acceptance.md#D1",
        ],
        cwd,
    )
    rc2, out2 = py_run(["scripts/ssdctl.py", "evidence", "--artifact", "prd/2026-11-22/layer-checklist.md"], cwd)
    ok = rc == 0 and "decision" in out2
    record(
        "A-7",
        ok,
        f"人工介入回路 rc={rc}, 证据含 decision 引用={'decision' in out2}",
    )


def a8_dispatch(cwd: Path) -> None:
    """调度谓词:上游 Draft ⇒ 下游不可派发;上游 Ready ⇒ 可派发。"""
    td_dir = cwd / "tech_design/2026-11-22-acceptance"
    td_dir.mkdir(parents=True, exist_ok=True)
    (td_dir / "README.md").write_text(
        "# TD: acceptance\n\n> **状态**: Draft\n\n"
        "## 链接 (Links)\n\n"
        "| 类型 | 标识 | 说明 |\n|---|---|---|\n"
        "| 来源 PRD | `prd/2026-11-22/layer-checklist.md` | 上游 |\n",
        encoding="utf-8",
    )
    rc, out = py_run(["scripts/ssdctl.py", "scan", "--json"], cwd)
    if rc not in (0, 1):
        record("A-8", False, f"scan --json 异常 rc={rc}: {out[:200]}")
        return
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        record("A-8", False, f"scan --json 输出非 JSON: {out[:200]}")
        return
    # 前序用例(A-6/A-7)可能已把上游 PRD 推到 Ready;本用例的前提是「上游 Draft」⇒ 先复位
    prd_path = cwd / "prd/2026-11-22/layer-checklist.md"
    text = prd_path.read_text(encoding="utf-8")
    text = re.sub(r"^> \*\*状态\*\*: .*$", "> **状态**: Draft", text, count=1, flags=re.M)
    prd_path.write_text(text, encoding="utf-8")
    rc, out = py_run(["scripts/ssdctl.py", "scan", "--json"], cwd)
    data = json.loads(out)
    arts = {a.get("path"): a for a in data.get("artifacts", [])}
    td = arts.get("tech_design/2026-11-22-acceptance")
    prd = arts.get("prd/2026-11-22/layer-checklist.md")
    if td is None:
        record("A-8", False, f"scan 未收录 TD 制品: {list(arts)[:6]}")
        return
    prd_ok = prd is not None and prd.get("dispatchable") is True
    blocked_ok = td.get("dispatchable") is False and bool(td.get("missing"))
    # 把上游 PRD 推到 Ready 再扫
    text = prd_path.read_text(encoding="utf-8")
    prd_path.write_text(re.sub(r"^> \*\*状态\*\*: .*$", "> **状态**: Ready", text, count=1, flags=re.M), encoding="utf-8")
    rc, out = py_run(["scripts/ssdctl.py", "scan", "--json"], cwd)
    data2 = json.loads(out)
    arts2 = {a.get("path"): a for a in data2.get("artifacts", [])}
    td2 = arts2.get("tech_design/2026-11-22-acceptance")
    released_ok = td2 is not None and td2.get("dispatchable") is True
    record(
        "A-8",
        prd_ok and blocked_ok and released_ok,
        f"PRD dispatchable={prd_ok}; 上游 Draft⇒下游 blocked={blocked_ok}(missing={td.get('missing')}); 上游 Ready⇒可派发={released_ok}",
    )


def a12_artifact_gate_counterexamples(cwd: Path) -> None:
    """制品级门禁反例:Ready 态的状态块/复审块规则必须「能失败」(契约 §3.1/§3.2)。"""
    prd = cwd / "prd/2026-11-22/layer-checklist.md"
    if not prd.exists():
        record("A-12", False, "仓内唯一制品不存在")
        return
    original = prd.read_text(encoding="utf-8")
    ready = original.replace("> **状态**: Draft", "> **状态**: Ready")
    ready = re.sub(r"^> \*\*状态主体\*\*:.*$", "> **状态主体**: agent:sddctl", ready, count=1, flags=re.M)
    ready = re.sub(r"^> \*\*状态时间\*\*:.*$", "> **状态时间**: 2026-11-22T00:00:00+08:00", ready, count=1, flags=re.M)
    ready = re.sub(r"^> \*\*状态依据\*\*:.*$", "> **状态依据**: criteria:PRD-READY-01", ready, count=1, flags=re.M)
    ready = re.sub(r"^> \*\*评审人\*\*:.*$", "> **评审人**: agent:sddctl", ready, count=1, flags=re.M)
    ready = re.sub(r"^> \*\*评审日期\*\*:.*$", "> **评审日期**: 2026-11-22", ready, count=1, flags=re.M)
    ready = re.sub(r"^> \*\*评审结论\*\*:.*$", "> **评审结论**: 通过", ready, count=1, flags=re.M)
    ready = re.sub(r"^> \*\*评审方式\*\*:.*$", "> **评审方式**: 自动判据", ready, count=1, flags=re.M)

    prd.write_text(ready, encoding="utf-8")
    rc, out = sh("bash scripts/check-md-schema.sh prd/2026-11-22/layer-checklist.md", cwd)
    if rc != 0:
        prd.write_text(original, encoding="utf-8")
        record("A-12", False, f"Ready 且四行齐全却 rc={rc}: {out.strip()[:200]}")
        return

    cases: list[tuple[str, str, str]] = [
        ("Ready 缺『状态依据』", r"^> \*\*状态依据\*\*: .*\n", "状态依据"),
        ("Ready 缺『状态主体』", r"^> \*\*状态主体\*\*: .*\n", "状态主体"),
        ("Ready 缺『评审方式』", r"^> \*\*评审方式\*\*: .*\n", "评审方式"),
    ]
    misses: list[str] = []
    for name, pattern, keyword in cases:
        prd.write_text(re.sub(pattern, "", ready, count=1, flags=re.M), encoding="utf-8")
        rc, out = sh("bash scripts/check-md-schema.sh prd/2026-11-22/layer-checklist.md", cwd)
        if rc == 1 and keyword in out:
            continue
        misses.append(f"{name}(rc={rc},输出含关键字={keyword in out})")

    # 取值域反例:状态依据 / 评审方式
    for name, text, keyword in [
        ("agent 署名 + 『人工介入』",
         re.sub(r"^> \*\*评审方式\*\*: .*$", "> **评审方式**: 人工介入", ready, count=1, flags=re.M),
         "评审方式"),
        ("状态依据取值非法",
         re.sub(r"^> \*\*状态依据\*\*: .*$", "> **状态依据**: 我觉得可以", ready, count=1, flags=re.M),
         "状态依据"),
        ("评审方式取值非法",
         re.sub(r"^> \*\*评审方式\*\*: .*$", "> **评审方式**: 随便", ready, count=1, flags=re.M),
         "评审方式"),
    ]:
        prd.write_text(text, encoding="utf-8")
        rc, out = sh("bash scripts/check-md-schema.sh prd/2026-11-22/layer-checklist.md", cwd)
        if rc == 1 and keyword in out:
            continue
        misses.append(f"{name}(rc={rc},输出含关键字={keyword in out})")

    prd.write_text(original, encoding="utf-8")
    if misses:
        record("A-12", False, "制品级门禁未拦截: " + "; ".join(misses))
    else:
        record("A-12", True, "6 个 Ready 态反例全部被 check-md-schema 拦截(rc=1 且点名)")


# ---------------------------------------------------------------- A-9 文本卫生
def a9_text_hygiene(cwd: Path) -> None:
    exts = {".md", ".sh", ".py", ".json", ".yml", ".yaml"}
    bad = []
    n = 0
    for p in cwd.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        if any(part in {".git", "__pycache__", ".swarm"} for part in p.parts):
            continue
        n += 1
        if b"\r" in p.read_bytes():
            bad.append(str(p.relative_to(cwd)))
    # 占位符残留:只查「制品文件」;层概览 README 与 _index 里的 {占位符} 是模板说明,不算残留
    ph = re.compile(r"\{[^}\n]+\}")
    ph_hits = []
    overview = {"prd/README.md", "tech_design/README.md", "plan/README.md",
                "test_cases/README.md", "material/README.md"}
    for d in ("prd", "tech_design", "plan", "test_cases"):
        base = cwd / d
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            rel = p.relative_to(cwd).as_posix()
            if ".git" in p.parts or rel in overview or p.name == "_index.md":
                continue
            for m in ph.finditer(p.read_text(encoding="utf-8", errors="replace")):
                ph_hits.append(f"{rel}:{m.group(0)[:24]}")
    if bad:
        record("A-9", False, f"{len(bad)} 个文件含 CR 字节: {bad[:5]}")
    elif ph_hits:
        record("A-9", False, f"{len(ph_hits)} 处占位符残留: {ph_hits[:5]}")
    else:
        record("A-9", True, f"{n} 个文本文件全部 LF;制品目录无占位符残留")


# ---------------------------------------------------------------- A-10 契约一致性
FORBIDDEN = [
    "权限天花板 = `Draft`",
    "权限天花板 = Draft",
    "agent 不得自行签署",
    "不得自行填写或翻转",
    "状态转换只由人工发起",
    "状态转换命令只由人工发起",
    "状态判定权归人",
    "只能由人工 reviewer 签署",
]
CONTRACT_FILES = [
    "WORKFLOW.md",
    "AGENTS.md",
    "README.md",
    "schema/prd.md",
    "schema/plan.md",
    "schema/test_case.md",
    "schema/tech_design/README.md",
    ".codex/skills/sync-status/SKILL.md",
    ".codex/skills/to-prd/SKILL.md",
    ".codex/skills/to-tech-design/SKILL.md",
    ".codex/skills/to-plan/SKILL.md",
]


NEGATIONS = ("不再", "不存在", "禁止", "不得", "不能", "没有", "取消", "废止", "移除", "已删", "勿", "一律不得")


def a10_contract_consistency(cwd: Path) -> None:
    hits = []
    for rel in CONTRACT_FILES:
        p = cwd / rel
        if not p.exists():
            hits.append(f"{rel}(缺失)")
            continue
        text = p.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            for phrase in FORBIDDEN:
                if phrase not in line:
                    continue
                # 「否定句里提到旧表述」不算残留(例如「不再存在「X」这种单边授权」)
                if any(n in line for n in NEGATIONS):
                    continue
                hits.append(f"{rel}:{i}:{phrase}")
    if hits:
        record("A-10", False, "旧表述残留: " + "; ".join(hits[:8]))
    else:
        record("A-10", True, f"{len(CONTRACT_FILES)} 个契约文件无旧表述残留")


# ---------------------------------------------------------------- main
def a13_wrapper(cwd: Path) -> None:
    """A-13: `scripts/ssdctl.sh` 解释器解析包装器。

    断言两件事:
      1. 包装器能在本机(`python` 是 Microsoft Store 桩、`python3` 不存在)解析出可用解释器,
         并真的把命令跑起来 —— stdout 必须含 ssdctl 的 argparse 用法行。
      2. 全仓文档与 skill 不得再出现 `python scripts/ssdctl.py` 这种命令形态
         (否则 agent 在本机跑第一步就会失败, 然后退回去手改状态行)。
    """
    wrapper = cwd / "scripts/ssdctl.sh"
    if not wrapper.exists():
        record("A-13", False, "scripts/ssdctl.sh 不存在")
        return
    rc, out = sh("bash scripts/ssdctl.sh --help", cwd)
    head = out.strip().splitlines()[0] if out.strip() else "(空)"
    ok = rc == 0 and "usage:" in out
    detail = f"rc={rc}; stdout={len(out.strip())}B; 首行: {head}"

    leftovers: list[str] = []
    for path in cwd.rglob("*.md"):
        rel = path.relative_to(cwd)
        if any(part in {".git", ".swarm", "__pycache__", "node_modules"} for part in rel.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "python scripts/ssdctl.py" in text:
            leftovers.append(str(rel))
    if leftovers:
        ok = False
        detail += f"; 残留旧命令形态: {leftovers}"
    record("A-13", ok, detail)


def main() -> int:
    args = set(sys.argv[1:])
    if not (ROOT / "scripts/ssdctl.py").exists():
        print("FATAL: scripts/ssdctl.py 尚未存在 —— L-ENG lane 未落地?", file=sys.stderr)
        return 2

    print(f"=== 验收根目录: {ROOT}")
    print(f"=== python: {PY}")
    print(f"=== bash:   {BASH}\n")

    a1_gates(ROOT)
    a2_new_cli(ROOT)
    a3_unit_tests(ROOT)
    a4_counterexample(ROOT)
    a9_text_hygiene(ROOT)
    a10_contract_consistency(ROOT)
    a13_wrapper(ROOT)

    print("\n=== 临时副本上的写路径/调度测试(不触碰工作树)")
    clone = copy_repo(ROOT)
    try:
        a5_negative(clone)
        a5b_human_actor_guard(clone)
        a6_evidence(clone)
        a7_human_loop(clone)
        a8_dispatch(clone)
        # A-8 自建的临时 TD 制品用完即删(不留残件给后续用例,尤其制品级门禁整仓扫描)
        shutil.rmtree(clone / "tech_design/2026-11-22-acceptance", ignore_errors=True)
        a12_artifact_gate_counterexamples(clone)
    finally:
        if "--keep" not in args:
            shutil.rmtree(clone.parent, ignore_errors=True)
        else:
            print(f"(kept: {clone})")

    if "--write" in args:
        rc, out = sh("bash scripts/sync-prd.sh", ROOT)
        rc2, out2 = sh(f'"{GIT}" status --porcelain -- README.md material/', ROOT)
        record(
            "A-1w",
            rc2 == 0 and not out2.strip(),
            f"sync-prd 写模式 rc={rc}; 漂移条目: {out2.strip() or '无'}",
        )

    print("\n" + "=" * 62)
    failed = [r for r in RESULTS if not r[1]]
    for cid, ok, detail in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {cid}  {detail}")
    print("=" * 62)
    print(f"RESULT: {'PASS' if not failed else 'FAIL'}  ({len(RESULTS) - len(failed)}/{len(RESULTS)})")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
