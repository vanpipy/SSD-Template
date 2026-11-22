"""8 个子命令的实现(契约 §5)。

退出码全仓统一(契约 INV-7):
    0 = 通过 / 成功
    1 = 违规 / 校验失败 / 状态不一致
    2 = 用法错误 / 内部错误(如判据文件缺失)

「半写」防护:`advance` 先做完全部校验,再一次性写目标文件;
任何失败路径都不写目标文件,`--dry-run` 连控制平面都不碰。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from . import control
from .artifacts import (
    Artifact,
    apply_review_block,
    apply_status_block,
    discover_artifacts,
    parse_basis,
    parse_review,
    parse_status,
    render_review_block,
    render_status_block,
)
from .criteria import (
    CriteriaError,
    CriteriaResult,
    Criterion,
    Document,
    RepoDocument,
    evaluate,
    evaluate_layer,
    evaluate_repo,
    load_criteria,
)
from .dispatch import Dispatch, evaluate_dispatch, resolve_upstream
from .paths import criteria_path, find_repo_root, relative_to_root

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

# 仓内既有门禁(契约 §8:8 个门禁全部保留,`ssdctl gate` 把它们一起跑)
GATE_SCRIPTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("scripts/check-line-endings.sh", ()),
    ("scripts/check-naming.sh", ()),
    ("scripts/check-md-schema.sh", ()),
    ("scripts/check-traceability.sh", ()),
    ("scripts/check-repo-baseline.sh", ()),
    ("scripts/check-doc-links.py", ()),
    ("scripts/sync-prd.sh", ("--check",)),
    ("scripts/sync-test-index.sh", ("--check",)),
)

# `sync-*.sh --check` 的退出码 1 表示「台账有待办行」,属工作状态而非违规(与 CI 一致)
SOFT_FAIL_CODES = {"scripts/sync-prd.sh": 1, "scripts/sync-test-index.sh": 1}

REVIEW_METHODS = ("自动判据", "人工介入", "外部事实")
REVIEW_CONCLUSIONS = ("通过", "有条件通过", "需返工")
AUTHORIZING_ACTIONS = ("approve", "override")

# 状态块取值格式(契约 §3.1)—— 与 scripts/check-md-schema.sh 的常量同口径
_STATE_SUBJECT_RE = re.compile(r"^(agent|human):[A-Za-z0-9._-]+$")
_STATE_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2}|Z)$"
)


class UsageError(Exception):
    """用法错误 —— 调用方转成退出码 2。"""


# ------------------------------------------------------------------ 公共小工具


_LAYER_BY_DIR = {"prd": "prd", "tech_design": "td", "plan": "plan", "test_cases": "test-case"}


def _infer_layer(rel: str, text: str) -> str:
    """从路径或内容推断一个制品的层。

    路径优先;路径不在层目录里时按内容特征推断 —— 反证样例
    (`.swarm/evidence/**` 下的历史 PRD)就是这种情况。
    """
    head = rel.split("/")[0]
    if head in _LAYER_BY_DIR:
        return _LAYER_BY_DIR[head]
    if "## 变更清单" in text or "## 跨文件引用对账" in text:
        return "plan"
    if "## 门禁清单" in text or "## 关键决策" in text:
        return "td"
    if "| **状态** |" in text:
        return "test-case"
    if "## 场景 (Scenarios)" in text or "## 目标 (Goal)" in text:
        return "prd"
    return "repo"


def _resolve_artifact(root: Path, raw: str) -> Artifact:
    """把命令行里的制品路径解析成一个已发现制品。

    找不到已发现制品时,只要它是一个 Markdown 文件,就按「散装制品」处理
    (层由路径/内容推断)—— 反证用例要对仓外的历史样例跑判据。
    """
    cleaned = raw.replace("\\", "/").strip()
    candidates = [Path(cleaned)]
    if not Path(cleaned).is_absolute():
        candidates.append(root / cleaned)
    for candidate in candidates:
        if not candidate.exists():
            continue
        rel = relative_to_root(candidate, root)
        for artifact in discover_artifacts(root):
            if artifact.rel == rel:
                return artifact
        # 允许直接指定 Tech Design 目录下的 README.md
        for artifact in discover_artifacts(root):
            if artifact.entry.resolve() == candidate.resolve():
                return artifact
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix.lower() == ".md":
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            rel = relative_to_root(candidate, root)
            layer = _infer_layer(rel, text)
            return Artifact(layer, candidate.stem, "", rel, candidate, (candidate,))
    raise UsageError(f"找不到制品: {raw}")


def _artifact_document(root: Path, artifact: Artifact) -> Document:
    return Document.from_paths(root, artifact.entry, artifact.files)


def _repo_documents(root: Path) -> list[RepoDocument]:
    """全仓制品按层/主题收集 —— 跨层(scope=repo)判据的求值上下文。"""
    docs: list[RepoDocument] = []
    for artifact in discover_artifacts(root):
        docs.append(RepoDocument(artifact.layer, artifact.topic, _artifact_document(root, artifact)))
    return docs


def _scoped_repo_documents(root: Path, topic: str) -> list[RepoDocument]:
    """单制品视角的跨层求值上下文:只取同 topic 的制品。

    跨层覆盖是「同 topic 成对」的(目录约定 §3.2:同 topic 同日期前缀)。
    求值单个制品时若把别的 topic 也拉进来,一个 topic 的缺口会挡住
    另一个无关 topic 的推进 —— 那是误伤,不是不变式。
    """
    docs = _repo_documents(root)
    if not topic:
        return docs
    return [item for item in docs if item.topic == topic]


def _repo_scope_layers(criteria: list[Criterion]) -> list[str]:
    """有跨层(scope=repo)判据的层,按层名排序去重。"""
    layers = {
        item.layer
        for item in criteria
        if str(item.params.get("scope") or "doc").strip().lower() == "repo"
    }
    return sorted(layers)


def _criteria_for_layer(criteria: list[Criterion], layer: str) -> list[Criterion]:
    return [item for item in criteria if item.layer == layer]


def _now() -> datetime:
    return datetime.now().astimezone()


# --------------------------------------------------------------------- scan


def build_state(root: Path, layer_filter: str | None = None) -> tuple[dict, list[Dispatch]]:
    """算派生状态(契约 §5.3)。只读制品状态行,不写任何文件。"""
    artifacts = discover_artifacts(root)
    if layer_filter:
        artifacts = [item for item in artifacts if item.layer == layer_filter]
    dispatches = [evaluate_dispatch(root, item, artifacts) for item in artifacts]
    payload = {
        "generated_at": control.now_iso(),
        "artifacts": [item.as_dict() for item in dispatches],
    }
    return payload, dispatches


def cmd_scan(root: Path, args) -> int:
    layer_filter = getattr(args, "layer", None)
    if layer_filter and layer_filter not in ("prd", "td", "plan", "test-case"):
        raise UsageError(f"--layer 取值非法: {layer_filter}")
    try:
        payload, dispatches = build_state(root, layer_filter)
    except OSError as exc:
        print(f"扫描失败: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if getattr(args, "check", False):
        stored = control.read_state(root)
        if stored is None:
            print(
                "✗ 控制面未初始化: control/state.json 不存在或不可读 —— "
                "派生状态缺失,拒绝放行;先跑 `ssdctl.py gate`(或 `ssdctl.py scan`)重建",
                file=sys.stderr,
            )
            return EXIT_FAIL
        expected = json.dumps(payload["artifacts"], ensure_ascii=False, sort_keys=True)
        actual = json.dumps(stored.get("artifacts"), ensure_ascii=False, sort_keys=True)
        if expected != actual:
            print("✗ 派生状态与磁盘不一致 —— 跑 `ssdctl.py scan` 重建 control/state.json", file=sys.stderr)
            for item in payload["artifacts"]:
                print(f"  - {item['path']}", file=sys.stderr)
            return EXIT_FAIL
        print(f"✓ 派生状态与磁盘一致(制品 {len(payload['artifacts'])} 个)")
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_OK

    control.write_state(root, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for item in dispatches:
            flag = "✓" if item.dispatchable else "○"
            print(
                f"{flag} {item.path} 状态={item.state or '未声明'} "
                f"许可={item.dependency_permission} 可调度={'是' if item.dispatchable else '否'}"
            )
            if item.missing:
                for reason in item.missing:
                    print(f"    缺: {reason}")
        print(f"✓ 派生状态已写入 control/state.json(制品 {len(dispatches)} 个)")
    return EXIT_OK


# ----------------------------------------------------------------- criteria


def cmd_criteria(root: Path, args) -> int:
    artifact = _resolve_artifact(root, args.artifact)
    criteria_path_ = criteria_path(root)
    try:
        criteria = load_criteria(criteria_path_)
    except CriteriaError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE

    document = _artifact_document(root, artifact)
    try:
        result = evaluate_layer(
            criteria, document, artifact.layer, _scoped_repo_documents(root, artifact.topic)
        )
    except CriteriaError as exc:
        # 判据参数非法(契约 §4.1.1)—— 显式失败,退出码 2,绝不静默放行。
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"制品: {artifact.rel}(层 {artifact.layer})")
        for claim in result.claims:
            print(f"  {'✓' if claim['passed'] else '✗'} {claim['id']} {claim['title']}")
        for item in result.failures:
            print(f"  ✗ 阻断失败 {item.criterion_id} @ {item.locate()}: {item.message}")
        for item in result.warnings:
            print(f"  ! 警告 {item.criterion_id} @ {item.locate()}: {item.message}")
        print("结论: " + ("通过" if result.passed else "不通过"))
    return EXIT_OK if result.passed else EXIT_FAIL


# --------------------------------------------------------------------- gate


def _bash_command() -> list[str]:
    """挑一个能用的 bash。

    Windows 上 PATH 里的 `bash` 可能是 WSL 转发器(看不见 Windows 路径),
    因此优先用 Git 自带的 Git Bash;POSIX 上直接用 PATH 里的 bash。
    """
    if os.name == "nt":
        git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        if git_bash.is_file():
            return [str(git_bash)]
    found = shutil.which("bash")
    if found:
        return [found]
    return ["bash"]


def _to_posix(path: Path) -> str:
    """把 Windows 路径转成 Git Bash 能吃的 `/c/...` 形式。"""
    text = str(path)
    drive, _, tail = text.partition(":")
    if len(drive) == 1 and tail.startswith("\\"):
        return "/" + drive.lower() + tail.replace("\\", "/")
    return text.replace("\\", "/")


def _run_gate(root: Path, script: str, args: tuple[str, ...]) -> tuple[int, str]:
    """跑一个仓内门禁,返回 (退出码, 合并输出)。"""
    target = root / script
    if not target.is_file():
        return EXIT_USAGE, f"门禁脚本缺失: {script}"
    if script.endswith(".py"):
        command = [sys.executable, str(target), *args]
    else:
        command = [*_bash_command(), _to_posix(target), *args]
    completed = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output.strip()


REPO_TEXT_SUFFIXES = (".md", ".sh", ".py", ".json", ".yml", ".yaml", ".txt", ".cfg", ".ini")
# 仓库级判据不扫这些目录:版本控制内部目录、测试夹具(它们**故意**含缺陷样本)、运行缓存
REPO_TEXT_SKIP_PARTS = {".git", ".swarm", "__pycache__", "tests", "node_modules", "workspace"}


def _repo_text_files(root: Path) -> list[Path]:
    """仓库级判据的输入文件清单。

    优先 `git ls-files`(与 CI 一致,只看受版本控制的文件);
    不在 git 工作树里时退化为目录遍历。测试夹具被排除 ——
    夹具里**故意**留着缺陷样本(占位符、非法状态),不该算成仓库缺陷。
    """
    listed: list[str] = []
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "-c", "core.quotePath=false", "ls-files"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode == 0:
            listed = [line for line in completed.stdout.splitlines() if line.strip()]
    except OSError:
        listed = []

    candidates: list[Path] = []
    if listed:
        candidates = [root / rel for rel in listed]
    else:
        candidates = sorted(path for path in root.rglob("*") if path.is_file())

    files: list[Path] = []
    for path in candidates:
        if path.suffix.lower() not in REPO_TEXT_SUFFIXES:
            continue
        try:
            parts = path.resolve().relative_to(root.resolve()).parts
        except ValueError:
            parts = path.parts
        if any(part in REPO_TEXT_SKIP_PARTS for part in parts[:-1]):
            continue
        if path.is_file():
            files.append(path)
    return files


def cmd_gate(root: Path, args) -> int:
    failures = 0
    print("— 仓内门禁 —")
    for script, gate_args in GATE_SCRIPTS:
        code, output = _run_gate(root, script, gate_args)
        soft = SOFT_FAIL_CODES.get(script)
        label = "✓" if code == 0 else ("!" if soft is not None and code == soft else "✗")
        print(f"{label} {script} {' '.join(gate_args)} → exit {code}")
        if output:
            for line in output.splitlines():
                print(f"    {line}")
        if code != 0 and not (soft is not None and code == soft):
            failures += 1

    print("— 判据 —")
    criteria_file = criteria_path(root)
    try:
        criteria = load_criteria(criteria_file)
    except CriteriaError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        print("✗ 判据文件缺失或非法 —— 门禁 fail-closed(不放行)", file=sys.stderr)
        return EXIT_USAGE

    artifacts = discover_artifacts(root)
    repo_docs = _repo_documents(root)
    try:
        for artifact in artifacts:
            document = _artifact_document(root, artifact)
            result = evaluate(criteria, document, artifact.layer)
            state = "✓" if result.passed else "✗"
            print(f"{state} {artifact.rel}: {len(result.failures)} 阻断失败 / {len(result.warnings)} 警告")
            for item in result.failures:
                print(f"    ✗ {item.criterion_id} @ {item.locate()}: {item.message}")
            for item in result.warnings:
                print(f"    ! {item.criterion_id} @ {item.locate()}: {item.message}")
            if not result.passed:
                failures += 1

        # 跨层判据(scope=repo):按层求值一次,不是按制品 —— 它是层不变式
        for layer in _repo_scope_layers(criteria):
            result = evaluate_repo(criteria, layer, repo_docs)
            state = "✓" if result.passed else "✗"
            print(f"{state} <跨层 {layer}>: {len(result.failures)} 阻断失败 / {len(result.warnings)} 警告")
            for item in result.failures:
                print(f"    ✗ {item.criterion_id} @ {item.locate()}: {item.message}")
            for item in result.warnings:
                print(f"    ! {item.criterion_id} @ {item.locate()}: {item.message}")
            if not result.passed:
                failures += 1

        # 仓库层判据(layer=repo)对整个仓求值,不对单个制品求值
        if any(item.layer == "repo" for item in criteria):
            document = Document.from_repo(root, _repo_text_files(root))
            result = evaluate(criteria, document, "repo")
            state = "✓" if result.passed else "✗"
            print(f"{state} <repo>: {len(result.failures)} 阻断失败 / {len(result.warnings)} 警告")
            for item in result.failures:
                print(f"    ✗ {item.criterion_id} @ {item.locate()}: {item.message}")
            for item in result.warnings:
                print(f"    ! {item.criterion_id} @ {item.locate()}: {item.message}")
            if not result.passed:
                failures += 1
    except CriteriaError as exc:
        # 判据参数非法(契约 §4.1.1)—— 显式失败,退出码 2,绝不静默放行。
        print(f"✗ {exc}", file=sys.stderr)
        print("✗ 判据参数非法 —— 门禁 fail-closed(不放行)", file=sys.stderr)
        return EXIT_USAGE

    # 制品自洽性: 状态块 + 复审块(与 verify 共用 _field_problems)。
    # 契约里的规则如果只写在 verify 里, CI 跑的却是 gate —— 那就是假绿。
    print("— 制品自洽性 —")
    for artifact in artifacts:
        text = _entry_text(root, artifact)
        problems = _field_problems(
            parse_status(text, artifact.rel), parse_review(text, artifact.rel)
        )
        state = "✓" if not problems else "✗"
        print(f"{state} {artifact.rel}: {len(problems)} 处不自洽")
        for problem in problems:
            print(f"    ✗ {problem}")
        if problems:
            failures += 1

    payload, _dispatches = build_state(root)
    control.write_state(root, payload)
    print(f"✓ 派生状态已写入 control/state.json(制品 {len(payload['artifacts'])} 个)")
    if failures:
        print(f"✗ 门禁未通过: {failures} 项")
        return EXIT_FAIL
    print("✓ 全部门禁通过")
    return EXIT_OK


# ------------------------------------------------------------------ advance


def _basis_from_criteria(criteria: list[Criterion], layer: str, result: CriteriaResult) -> str | None:
    """判据授权来源:该层通过的全部 blocking 判据 id。"""
    passed = {claim["id"] for claim in result.claims if claim["passed"]}
    ids = [
        item.id
        for item in criteria
        if item.layer == layer and item.blocking and item.id in passed
    ]
    if not ids:
        return None
    return "criteria:" + ",".join(ids)


def cmd_advance(root: Path, args) -> int:
    target_state = args.to
    if target_state not in ("Ready", "Implemented", "Deprecated"):
        raise UsageError(f"--to 取值非法: {target_state}(允许 Ready/Implemented/Deprecated)")

    artifact = _resolve_artifact(root, args.artifact)
    try:
        criteria = load_criteria(criteria_path(root))
    except CriteriaError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE

    document = _artifact_document(root, artifact)
    try:
        result = evaluate_layer(
            criteria, document, artifact.layer, _scoped_repo_documents(root, artifact.topic)
        )
    except CriteriaError as exc:
        # 判据参数非法(契约 §4.1.1)—— 显式失败,退出码 2,绝不静默放行。
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE
    decision = None
    if args.decision:
        decision = control.find_decision(root, args.decision)
        if decision is None:
            print(f"✗ 找不到决定记录: {args.decision}", file=sys.stderr)
            return EXIT_USAGE

    actor = (args.actor or "agent:sddctl").strip()
    problems: list[str] = []

    # 复审块的「评审人」取值:人写的决定文件里的操作人 = 人类署名;否则用 actor。
    # 契约 §5.2 规则 5:非 agent: 形态的署名必须来自决定记录 —— agent 不能靠
    # `--actor alice` 冒充人工(INV-3),否则复审三问又变成 agent 自填。
    reviewer = actor
    if decision is not None and decision.actor:
        reviewer = decision.actor
    if not reviewer.startswith("agent:") and not (decision is not None and decision.actor):
        problems.append(
            "人工署名必须来自 control/decisions/ 的决定记录"
            f"(评审人={reviewer!r} 不是 agent:<id> 形态,且没有可引用的决定记录)"
        )

    # §5.2 规则 1 + 2:blocking 判据必须全绿;blocking:false 的失败必须有决定记录
    if target_state in ("Ready", "Implemented"):
        for item in result.failures:
            problems.append(f"阻断判据未通过 {item.criterion_id} @ {item.locate()}: {item.message}")
        for item in result.warnings:
            covered = (
                decision is not None
                and decision.action in AUTHORIZING_ACTIONS
                and decision.covers(item.criterion_id)
            )
            if not covered:
                problems.append(
                    f"警告判据 {item.criterion_id} @ {item.locate()} 没有人工决定记录 —— "
                    f"需先 `ssdctl.py decide` 记录已知问题({item.message})"
                )

    # §5.2 规则 3:跨层推进时上游必须 Ready
    artifacts = discover_artifacts(root)
    upstreams = resolve_upstream(root, artifact, artifacts)
    if target_state in ("Ready", "Implemented"):
        for item in upstreams:
            if item.artifact is None:
                problems.append(f"上游未解析:{item.reason}")
                continue
            state = parse_status(item.artifact.entry.read_text(encoding="utf-8"), item.artifact.rel).state
            if state not in ("Ready", "Implemented"):
                problems.append(
                    f"上游未 Ready:{item.artifact.rel} 状态={state or '未声明'}"
                )

    # §5.2 规则 4:授权来源 = --decision 或判据全绿
    criteria_basis = _basis_from_criteria(criteria, artifact.layer, result)
    basis_items: list[str] = []
    external_ref = None
    if decision is not None:
        basis_items.append(f"decision:{decision.rel}#{decision.id}")
        if decision.external_ref:
            external_ref = decision.external_ref
    if target_state in ("Ready", "Implemented") and criteria_basis:
        basis_items.append(criteria_basis)

    # Implemented 额外要求 external: 依据(§5.2)
    if target_state == "Implemented":
        chain_refs = control.external_refs(control.read_evidence(root, artifact.rel))
        if external_ref:
            chain_refs = list(chain_refs) + [f"external:{external_ref}"]
        if not chain_refs:
            problems.append("进入 Implemented 需要 `external:` 依据(证据链或决定记录里的外部事实)")
        else:
            basis_items.append(chain_refs[0])

    # Deprecated 的状态依据必须是 decision: 或 external:(§5.2)
    if target_state == "Deprecated":
        if not any(item.startswith("decision:") or item.startswith("external:") for item in basis_items):
            problems.append("进入 Deprecated 的状态依据必须是 `decision:` 或 `external:`,不能用 `criteria:`")

    if not basis_items:
        problems.append("没有可用授权来源(既无 --decision,判据也没有可引用的授权)")

    if problems:
        print(f"✗ 不允许推进 {artifact.rel} → {target_state}:", file=sys.stderr)
        for problem in problems:
            print(f"    - {problem}", file=sys.stderr)
        print("  (目标文件未做任何修改)", file=sys.stderr)
        return EXIT_FAIL

    # 复审块取值:reviewer 已在上面按 §5.2 规则 5 定好(决定记录的操作人优先)
    method = "自动判据"
    if decision is not None and decision.actor:
        method = "人工介入"
    if any(item.startswith("external:") for item in basis_items):
        method = "外部事实"
    if reviewer.startswith("agent:") and method == "人工介入":
        method = "自动判据"
    if reviewer.startswith("agent:") and method not in REVIEW_METHODS:
        method = "自动判据"
    conclusion = "有条件通过" if result.warnings else "通过"
    review_date = _now().strftime("%Y-%m-%d")
    timestamp = control.now_iso()
    subject = "agent:sddctl"  # INV-3:agent 永不署名 human:

    new_text = apply_review_block(
        apply_status_block(
            _entry_text(root, artifact),
            render_status_block(target_state, subject, timestamp, ",".join(basis_items)),
        ),
        render_review_block(reviewer, review_date, conclusion, method),
    )

    plan = [
        f"制品: {artifact.rel}",
        f"目标状态: {target_state}",
        f"状态主体: {subject}",
        f"状态依据: {','.join(basis_items)}",
        f"复审块: 评审人={reviewer} 日期={review_date} 结论={conclusion} 方式={method}",
    ]
    if args.dry_run:
        print("— 计划(未写任何文件) —")
        for line in plan:
            print(f"  {line}")
        return EXIT_OK

    # INV-4:先落证据再落制品;证据写失败 ⇒ 目标文件零改动
    original = _entry_text(root, artifact)
    record = {
        "ts": timestamp,
        "actor": actor,
        "from": parse_status(original, artifact.rel).state or "未声明",
        "to": target_state,
        "artifact": artifact.rel,
        "artifact_hash": control.sha256_text(original),
        "criteria": [
            {"id": claim["id"], "passed": claim["passed"]} for claim in result.claims
        ],
        "decisions": [f"decision:{decision.rel}#{decision.id}"] if decision else [],
        "reason": f"推进到 {target_state}:{'; '.join(basis_items)}",
    }
    try:
        evidence_file = control.append_evidence(root, record)
    except OSError as exc:
        print(f"✗ 证据链写入失败,目标文件未修改: {exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        artifact.entry.write_text(new_text, encoding="utf-8", newline="\n")
    except OSError as exc:
        print(f"✗ 目标文件写入失败: {exc}", file=sys.stderr)
        print(f"    证据已记录于 {evidence_file.relative_to(root).as_posix()}(请人工核对)", file=sys.stderr)
        return EXIT_USAGE

    print("— 已推进 —")
    for line in plan:
        print(f"  {line}")
    print(f"  证据: {evidence_file.relative_to(root).as_posix()}")
    return EXIT_OK


def _entry_text(root: Path, artifact: Artifact) -> str:
    try:
        return artifact.entry.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# -------------------------------------------------------------------- queue


def cmd_queue(root: Path, args) -> int:
    artifact = _resolve_artifact(root, args.artifact)
    try:
        criteria = load_criteria(criteria_path(root))
    except CriteriaError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE
    document = _artifact_document(root, artifact)
    try:
        result = evaluate_layer(
            criteria, document, artifact.layer, _scoped_repo_documents(root, artifact.topic)
        )
    except CriteriaError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE
    items = result.failures + result.warnings
    if not items:
        print(f"✓ {artifact.rel}:没有待裁决项")
        return EXIT_FAIL
    if args.json:
        print(
            json.dumps(
                {
                    "artifact": artifact.rel,
                    "items": [item.as_dict() for item in items],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"{artifact.rel}:待裁决 {len(items)} 项")
        for item in items:
            tag = "阻断" if item.blocking else "警告"
            print(f"  [{tag}] {item.criterion_id} @ {item.locate()}: {item.message}")
    return EXIT_OK


# ------------------------------------------------------------------- decide


def cmd_decide(root: Path, args) -> int:
    if args.action not in ("approve", "reject", "hold", "override"):
        raise UsageError(f"--action 取值非法: {args.action}")
    artifact = _resolve_artifact(root, args.artifact)
    topic = artifact.topic
    path, decision = control.write_decision(
        root,
        topic=topic,
        action=args.action,
        actor=args.actor,
        reason=args.reason,
        artifact=artifact.rel,
        criterion=args.criterion,
    )
    print(f"✓ 决定已写入 {path.relative_to(root).as_posix()}({decision.id})")
    print(f"  目标制品: {artifact.rel}")
    print(f"  动作: {args.action}  范围: {decision.scope}")
    print(f"  理由: {args.reason}")
    return EXIT_OK


# ------------------------------------------------------------------ evidence


def cmd_evidence(root: Path, args) -> int:
    # 绝对路径 / 带 ./ 的路径 / 仓内相对路径, 都要归一到同一个制品键,
    # 否则「advance 写的是 rel, evidence 查的是绝对路径」会查空 —— 看起来
    # 像「没有证据」, 其实是路径写法不同。
    target = args.artifact
    if target:
        target = _resolve_artifact(root, target).rel
    records = control.read_evidence(root, target)
    if not records:
        print("✗ 没有证据记录", file=sys.stderr)
        return EXIT_FAIL
    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"证据链记录 {len(records)} 条")
        for record in records:
            print(
                f"  {record.get('ts', '?')} {record.get('artifact', '?')} "
                f"{record.get('from', '?')} → {record.get('to', '?')} "
                f"by {record.get('actor', '?')}"
            )
            for decision in record.get("decisions") or []:
                print(f"      依据: {decision}")
            print(f"      哈希: {record.get('artifact_hash', '?')}")
    return EXIT_OK


# -------------------------------------------------------------------- verify


def _field_problems(status, review) -> list[str]:
    """制品自身的字段自洽性(状态块 §3.1 + 复审块 §3.2)。

    `cmd_verify` 与 `cmd_gate` 共用这一份判定 —— 两处说同一件事,
    免得出现「verify 说没问题、gate 说有问题」的门禁空洞。

    判定口径与 `scripts/check-md-schema.sh` 的 `check_status_meta` /
    `check_review_block` 一致。
    """
    problems: list[str] = []

    if status.state is None:
        problems.append("制品没有状态行")
    elif status.state not in ("Draft", "Ready", "Implemented", "Deprecated"):
        problems.append(f"状态值非法: {status.state}")

    # 状态块: Draft / Deprecated 可缺省后三行, 但写了就必须合法
    if status.subject and not _STATE_SUBJECT_RE.match(status.subject):
        problems.append(f"`状态主体` 非法: {status.subject} (应为 agent:<id> 或 human:<handle>)")
    if status.timestamp and not _STATE_TIME_RE.match(status.timestamp):
        problems.append(f"`状态时间` 不是带时区的 ISO-8601: {status.timestamp}")
    if status.basis:
        valid, invalid = parse_basis(status.basis)
        for item in invalid:
            problems.append(f"`状态依据` 项 `{item}` 不在 criteria:/decision:/external: 之中")
        if status.state == "Deprecated" and any(item.startswith("criteria:") for item in valid):
            problems.append("`状态依据` 在 Deprecated 态只能是 decision: 或 external:,不能用 criteria:")

    if status.state in ("Ready", "Implemented"):
        for name, value in (
            ("状态主体", status.subject),
            ("状态时间", status.timestamp),
            ("状态依据", status.basis),
        ):
            if not value:
                problems.append(f"状态 ≥ Ready 时 `{name}` 必须非空")
        for name, value in (
            ("评审人", review.reviewer),
            ("评审日期", review.review_date),
            ("评审结论", review.conclusion),
            ("评审方式", review.method),
        ):
            if not value:
                problems.append(f"状态 ≥ Ready 时 `{name}` 必须非空")
        if review.conclusion and review.conclusion not in REVIEW_CONCLUSIONS:
            problems.append(f"`评审结论` 取值非法: {review.conclusion}")
        if review.method and review.method not in REVIEW_METHODS:
            problems.append(f"`评审方式` 取值非法: {review.method}")
        if review.reviewer and review.reviewer.startswith("agent:") and review.method == "人工介入":
            problems.append("`评审人` 是 agent:* 时 `评审方式` 不能是 人工介入")
    return problems


def cmd_verify(root: Path, args) -> int:
    artifact = _resolve_artifact(root, args.artifact)
    text = _entry_text(root, artifact)
    status = parse_status(text, artifact.rel)
    review = parse_review(text, artifact.rel)
    problems: list[str] = _field_problems(status, review)

    records = control.read_evidence(root, artifact.rel)
    if status.state in ("Ready", "Implemented", "Deprecated"):
        matching = [item for item in records if item.get("to") == status.state]
        if not matching:
            problems.append(f"证据链里没有 `{status.state}` 的转换记录")

    if problems:
        print(f"✗ {artifact.rel} 不一致:", file=sys.stderr)
        for problem in problems:
            print(f"    - {problem}", file=sys.stderr)
        return EXIT_FAIL
    print(f"✓ {artifact.rel} 一致(状态 {status.state},证据 {len(records)} 条)")
    return EXIT_OK
