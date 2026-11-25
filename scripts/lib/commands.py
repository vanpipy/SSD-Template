"""6 个子命令的实现(契约 §5)。

退出码全仓统一(契约 INV-7):
    0 = 通过 / 成功
    1 = 违规 / 校验失败 / 状态不一致
    2 = 用法错误 / 内部错误(如判据文件缺失)

「半写」防护:`advance` 先做完全部校验,再一次性写目标文件;
任何失败路径都不写目标文件,`--dry-run` 连目标文件都不碰。

F9(单载体):仓内**没有控制平面**。状态与评审的唯一权威载体 = 制品本身;
`advance` 对人与 agent 是**同一条命令**,差异只在署名来源:
- agent:`--actor agent:<id>`(默认 `agent:ssdctl`)⇒ 机器写复审块;
- 人:**先**在制品 `## 复审 (Review)` 段自己写好署名,再跑同一条 `advance`
  ⇒ 机器**永不覆盖**已有复审块。
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

from . import util
from .artifacts import (
    REVIEW_HEADING_KEY,
    Artifact,
    apply_review_block,
    apply_status_block,
    discover_artifacts,
    known_issue_ids,
    known_issue_shape_problems,
    parse_basis,
    parse_review,
    parse_status,
    render_review_block,
    render_status_block,
    section_span,
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

# 仓内既有门禁(契约 §8:7 个门禁全部保留,`ssdctl gate` 把它们一起跑)
# 门禁清单的**唯一真源** —— 验收脚本、测试、文档都从这里派生,不再各抄一份。
GATE_SCRIPTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("scripts/check-naming.py", ()),
    ("scripts/check-md-schema.py", ()),
    ("scripts/check-traceability.py", ()),
    ("scripts/check-repo-baseline.sh", ()),
    ("scripts/check-doc-links.py", ()),
    ("scripts/sync-prd.sh", ("--check",)),
    ("scripts/sync-test-index.sh", ("--check",)),
)

# `sync-*.sh --check` 的退出码 1 表示「台账有待办行」,属工作状态而非违规(与 CI 一致)
SOFT_FAIL_CODES = {"scripts/sync-prd.sh": 1, "scripts/sync-test-index.sh": 1}

REVIEW_METHODS = ("自动判据", "人工介入", "外部事实")
REVIEW_CONCLUSIONS = ("通过", "有条件通过", "需返工")

# 三件套(WORKFLOW.md §5「三件套一致性规则」):
# PRD / Tech Design / Plan 三个状态**必须同时**进入 Implemented —— 不允许单层先 Implemented。
# test-case 独立于三件套生命周期(AGENTS.md §3.3),不参与这条规则。
TRIO_LAYERS = ("prd", "td", "plan")

# 状态块取值格式(契约 §3.1)—— 与 scripts/check-md-schema.py 的常量同口径
_STATE_SUBJECT_RE = re.compile(r"^(agent|human):[A-Za-z0-9._-]+$")
# F9:`--actor` 只允许 agent 署名 —— 人工署名写在制品的复审段里,机器不代填(INV-3)。
_AGENT_ACTOR_RE = re.compile(r"^agent:[A-Za-z0-9._-]+$")
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
    (仓内反证夹具 `scripts/tests/fixtures/artifacts/uncovered-ac5-prd.md`)就是这种情况。
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


def _scoped_repo_documents(
    root: Path,
    topic: str,
    simulated: tuple[Artifact, Document] | None = None,
) -> list[RepoDocument]:
    """单制品视角的跨层求值上下文:只取同 topic 的制品。

    跨层覆盖是「同 topic 成对」的(目录约定 §3.2:同 topic 同日期前缀)。
    求值单个制品时若把别的 topic 也拉进来,一个 topic 的缺口会挡住
    另一个无关 topic 的推进 —— 那是误伤,不是不变式。

    `simulated` = (目标制品, 模拟文本重建的 Document) ⇒ 跨层求值看到的是
    「这次推进写完之后」的制品,而不是磁盘上的旧文本(F9 死锁修复用)。
    """
    docs = _repo_documents(root)
    if simulated is not None:
        target, simulated_doc = simulated
        docs = [
            RepoDocument(
                item.layer,
                item.topic,
                simulated_doc if _is_artifact_document(item.doc, target) else item.doc,
            )
            for item in docs
        ]
    if not topic:
        return docs
    return [item for item in docs if item.topic == topic]


def _is_artifact_document(doc: Document, artifact: Artifact) -> bool:
    """这个 `Document` 是不是某个具体制品的文档(按仓库相对路径认,不按文件名)。"""
    return any(rel == artifact.rel for rel, _lines in doc.files)


def _simulated_document(root: Path, artifact: Artifact, text: str) -> Document:
    """用模拟文本替换制品正文后的 `Document`(只用于判据求值,不落盘)。"""
    document = _artifact_document(root, artifact)
    files: list[tuple[str, list[str]]] = []
    replaced = False
    for rel, lines in document.files:
        if not replaced and rel == artifact.rel:
            files.append((rel, text.split("\n")))
            replaced = True
        else:
            files.append((rel, lines))
    if not replaced:
        files.append((artifact.rel, text.split("\n")))
    return Document(rel=document.rel, files=files)


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
    """算派生视图(契约 §5.3)。只读制品状态行,不写任何文件。

    F9:派生视图**只打印**,不再落盘 —— 留痕 = 制品 + git 历史。
    JSON 形状(`generated_at` + `artifacts[]`)保持不变,编排层依赖它。
    """
    artifacts = discover_artifacts(root)
    if layer_filter:
        artifacts = [item for item in artifacts if item.layer == layer_filter]
    dispatches = [evaluate_dispatch(root, item, artifacts) for item in artifacts]
    payload = {
        "generated_at": util.now_iso(),
        "artifacts": [item.as_dict() for item in dispatches],
    }
    return payload, dispatches


def _consistency_problems(root: Path) -> list[str]:
    """跨制品一致性检查(F9 R-6)—— `scan --check` 的唯一判定口径。

    (a) **上游闸门**:状态 ∈ {Ready, Implemented} 的制品,其上游必须也 ∈ {Ready, Implemented};
    (b) **三件套原子性**:同 topic 的 PRD / Tech Design / Plan 中,任一为 Implemented 时,
        其余**已存在**者必须也是 Implemented;
    (c) **字段自洽**:状态块 + 复审块(复用 `_field_problems`)。

    这一段补上了旧模型里「上游必须 Ready 才准写下游」的**只读**机器覆盖
    (旧模型只靠 `WORKFLOW.md` 的文字义务,没有任何机器判据)。
    """
    problems: list[str] = []
    artifacts = discover_artifacts(root)

    # (a) 上游闸门
    for artifact in artifacts:
        state = parse_status(_entry_text(root, artifact), artifact.rel).state
        if state not in ("Ready", "Implemented"):
            continue
        for upstream in resolve_upstream(root, artifact, artifacts):
            if upstream.artifact is None:
                problems.append(f"上游未解析: {artifact.rel} ← {upstream.reason}")
                continue
            upstream_state = parse_status(
                _entry_text(root, upstream.artifact), upstream.artifact.rel
            ).state
            if upstream_state not in ("Ready", "Implemented"):
                problems.append(
                    f"上游未 Ready: {artifact.rel} ← {upstream.artifact.rel} "
                    f"状态={upstream_state or '未声明'}"
                )

    # (b) 三件套原子性
    topics: dict[str, list[Artifact]] = {}
    for artifact in artifacts:
        if artifact.layer in TRIO_LAYERS:
            topics.setdefault(artifact.topic, []).append(artifact)
    for topic in sorted(topics):
        members = topics[topic]
        states = {
            member.rel: parse_status(_entry_text(root, member), member.rel).state
            for member in members
        }
        if not any(value == "Implemented" for value in states.values()):
            continue
        for rel in sorted(states):
            if states[rel] != "Implemented":
                problems.append(
                    f"三件套未同时就绪: {rel} 状态={states[rel] or '未声明'}"
                    f"(同 topic「{topic}」的 PRD / Tech Design / Plan 必须同时 Implemented)"
                )

    # (c) 字段自洽
    for artifact in artifacts:
        text = _entry_text(root, artifact)
        for problem in _field_problems(parse_status(text, artifact.rel), parse_review(text, artifact.rel)):
            problems.append(f"{artifact.rel}: {problem}")

    return problems


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
        problems = _consistency_problems(root)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        if problems:
            print("✗ 跨制品一致性检查未通过:", file=sys.stderr)
            for problem in problems:
                print(f"    - {problem}", file=sys.stderr)
            return EXIT_FAIL
        print(f"✓ 跨制品一致性检查通过(制品 {len(dispatches)} 个)")
        return EXIT_OK

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
        print(f"✓ 扫描完成(制品 {len(dispatches)} 个;派生视图不落盘 —— 留痕 = 制品 + git 历史)")
    return EXIT_OK


# ----------------------------------------------------------------- criteria


def cmd_criteria(root: Path, args) -> int:
    repo_mode = bool(getattr(args, "repo", False))
    artifact_arg = getattr(args, "artifact", None)
    if repo_mode and artifact_arg:
        raise UsageError("`--repo` 与制品参数互斥:二选一(只跑仓库层判据 / 跑单个制品)")
    if not repo_mode and not artifact_arg:
        raise UsageError("需要一个制品参数,或用 `--repo` 只跑仓库层判据")

    criteria_path_ = criteria_path(root)
    try:
        criteria = load_criteria(criteria_path_)
    except CriteriaError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE

    if repo_mode:
        return _cmd_criteria_repo(root, criteria, args)

    artifact = _resolve_artifact(root, artifact_arg)
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


def _cmd_criteria_repo(root: Path, criteria: list[Criterion], args) -> int:
    """只跑仓库层判据 —— 与 `gate` 的仓库层同源(同一批判据、同一份受检集合)。

    退出码(与被删掉的行尾检查脚本一致):0=无违规 / 1=有仓库层违规 /
    2=判据缺失、判据非法,或判据里根本没有仓库层判据(那种情况**不放行**)。
    """
    try:
        files = _repo_text_files(root)
        row, lines, count = _repo_criteria_row(root, criteria, files)
    except CriteriaError as exc:
        # 判据参数非法(契约 §4.1.1)—— 显式失败,退出码 2,绝不静默放行。
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE
    if row is None:
        print("✗ 判据文件里没有仓库层判据(layer=repo)—— 无法执行仓库层检查", file=sys.stderr)
        return EXIT_USAGE
    passed = bool(row["passed"])
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "ok": passed,
                    "scope": "repo",
                    "target": "repo",
                    "passed": passed,
                    "failures": row["failures"],
                    "warnings": row["warnings"],
                    "files": count,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for line in lines:
            print(line)
        print(f"受检文件: {count}")
        print("结论: " + ("通过" if passed else "不通过"))
    return EXIT_OK if passed else EXIT_FAIL


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


def _run_gate(root: Path, script: str, args: tuple[str, ...]) -> tuple[int, str, str]:
    """跑一个仓内门禁,返回 (退出码, stdout, stderr)。

    stdout 与 stderr **分开**返回:JSON 契约里的 `stdout_bytes` 要的是 stdout 自己的字节数。
    文本报告仍把两股合起来看(与历史输出一致),但那只是报告口径。
    """
    target = root / script
    if not target.is_file():
        return EXIT_USAGE, "", f"门禁脚本缺失: {script}"
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
    return completed.returncode, (completed.stdout or ""), (completed.stderr or "")



# 仓库级判据不扫这些目录:版本控制内部目录、编排目录、运行缓存。
#
# 这里**不含 "tests"** —— 受检集合必须与被删掉的行尾检查脚本逐项对齐:
# 全部受版本控制的文件都进集合(含 `.gitattributes`、`.gitignore`、`scripts/tests/**`),
# 只按 NUL 字节嗅探跳过二进制。常量名保持不变 —— `scripts/acceptance/clone-verify.sh`
# 的白名单按这个名字引用。
REPO_TEXT_SKIP_PARTS = {".git", ".swarm", "__pycache__", "node_modules", "workspace"}


def _contains_nul(path: Path) -> bool:
    """文件里有没有 NUL 字节 —— 二进制嗅探,与被删的行尾脚本同口径。

    读不动(权限/IO 错误)的文件按二进制处理:跳过,不当作文本去套规则。
    """
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    return False
                if b"\x00" in chunk:
                    return True
    except OSError:
        return True


def _repo_text_files(root: Path) -> list[Path]:
    """仓库层判据的输入文件清单。

    优先 `git ls-files`(与 CI 一致,只看受版本控制的文件);
    不在 git 工作树里时退化为目录遍历。

    覆盖面与被删掉的行尾检查脚本逐项对齐:
    **全部**受版本控制的文件都进集合(含 `.gitattributes`、`.gitignore`、
    `scripts/tests/**`),只按 NUL 字节嗅探跳过二进制 —— 不按后缀白名单,
    也不排除测试目录(那会漏掉 31 个受版本控制的文件)。
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
        try:
            parts = path.resolve().relative_to(root.resolve()).parts
        except ValueError:
            parts = path.parts
        if any(part in REPO_TEXT_SKIP_PARTS for part in parts[:-1]):
            continue
        if not path.is_file():
            continue
        if _contains_nul(path):
            continue
        files.append(path)
    return files


def _repo_criteria_row(
    root: Path, criteria: list[Criterion], files: list[Path] | None = None
) -> tuple[dict | None, list[str], int]:
    """仓库层判据(layer=repo)求值 —— `gate` 与 `criteria --repo` 共用这一段。

    返回 (载荷行, 文本行, 受检文件数)。判据里没有仓库层判据时载荷行为 None,
    调用方据此跳过 —— 不产生多余输出,也不把「没有这条规则」当成通过。
    载荷行形状与 `gate --json` 的 criteria 行完全一致:
    {"scope": "repo", "target": "repo", "passed": bool, "failures": [...], "warnings": [...]}
    """
    if not any(item.layer == "repo" for item in criteria):
        return None, [], 0
    if files is None:
        files = _repo_text_files(root)
    document = Document.from_repo(root, files)
    result = evaluate(criteria, document, "repo")
    failures: list[str] = []
    warnings: list[str] = []
    lines: list[str] = []
    for item in result.failures:
        text = f"{item.criterion_id} @ {item.locate()}: {item.message}"
        failures.append(text)
        lines.append(f"    ✗ {text}")
    for item in result.warnings:
        text = f"{item.criterion_id} @ {item.locate()}: {item.message}"
        warnings.append(text)
        lines.append(f"    ! {text}")
    state = "✓" if result.passed else "✗"
    summary = f"{state} <repo>: {len(result.failures)} 阻断失败 / {len(result.warnings)} 警告"
    row = {
        "scope": "repo",
        "target": "repo",
        "passed": result.passed,
        "failures": failures,
        "warnings": warnings,
    }
    return row, [summary] + lines, len(files)


def _gate_payload(
    gates: list[dict],
    criteria_rows: list[dict],
    artifact_rows: list[dict],
    failures: int,
    fatal: bool,
) -> dict:
    """`gate --json` 的载荷 —— 顶层只有这 5 个键(契约 §8)。"""
    return {
        "ok": not fatal and failures == 0,
        "failures": failures,
        "gates": gates,
        "criteria": criteria_rows,
        "artifacts": artifact_rows,
    }


def _collect_gate_report(root: Path) -> tuple[dict, list[str], list[str]]:
    """跑完全部门禁 + 判据 + 制品自洽性。

    返回 (JSON 载荷, 文本输出行, 致命错误行)。**收集与打印分离**:
    `gate` 打印文本行,`gate --json` 打印同一个载荷 —— 两种呈现来自同一次运行,
    所以判定与退出码不可能分叉。
    """
    lines: list[str] = []
    gates: list[dict] = []
    criteria_rows: list[dict] = []
    artifact_rows: list[dict] = []
    failures = 0

    lines.append("— 仓内门禁 —")
    for script, gate_args in GATE_SCRIPTS:
        code, stdout, stderr = _run_gate(root, script, gate_args)
        merged = (stdout + stderr).strip()  # 文本渲染口径:两股合起来(与历史输出一致)
        soft = SOFT_FAIL_CODES.get(script)
        soft_hit = soft is not None and code == soft
        label = "✓" if code == 0 else ("!" if soft_hit else "✗")
        lines.append(f"{label} {script} {' '.join(gate_args)} → exit {code}")
        if merged:
            for line in merged.splitlines():
                lines.append(f"    {line}")
        if code != 0 and not soft_hit:
            failures += 1
        gates.append(
            {
                "script": script,
                "args": list(gate_args),
                "exit_code": code,
                "stdout_bytes": len(stdout.encode("utf-8")),
                "soft_fail": soft is not None,
                # output = stdout 原文(契约 §A1);stderr 单列,因为 check-doc-links.py
                # 把整份报告写在 stderr(stdout=0)—— 少一栏就等于丢掉它的输出。
                "output": stdout,
                "stderr": stderr,
            }
        )

    lines.append("— 判据 —")
    criteria_file = criteria_path(root)
    try:
        criteria = load_criteria(criteria_file)
    except CriteriaError as exc:
        fatal = [f"✗ {exc}", "✗ 判据文件缺失或非法 —— 门禁 fail-closed(不放行)"]
        return _gate_payload(gates, [], [], failures + 1, True), lines, fatal

    artifacts = discover_artifacts(root)
    repo_docs = _repo_documents(root)
    try:
        for artifact in artifacts:
            document = _artifact_document(root, artifact)
            result = evaluate(criteria, document, artifact.layer)
            state = "✓" if result.passed else "✗"
            lines.append(
                f"{state} {artifact.rel}: {len(result.failures)} 阻断失败 / {len(result.warnings)} 警告"
            )
            row_failures: list[str] = []
            for item in result.failures:
                text = f"{item.criterion_id} @ {item.locate()}: {item.message}"
                lines.append(f"    ✗ {text}")
                row_failures.append(text)
            row_warnings: list[str] = []
            for item in result.warnings:
                text = f"{item.criterion_id} @ {item.locate()}: {item.message}"
                lines.append(f"    ! {text}")
                row_warnings.append(text)
            if not result.passed:
                failures += 1
            criteria_rows.append(
                {
                    "scope": "artifact",
                    "target": artifact.rel,
                    "passed": result.passed,
                    "failures": row_failures,
                    "warnings": row_warnings,
                }
            )

        # 跨层判据(scope=repo):按层求值一次,不是按制品 —— 它是层不变式
        for layer in _repo_scope_layers(criteria):
            result = evaluate_repo(criteria, layer, repo_docs)
            state = "✓" if result.passed else "✗"
            lines.append(
                f"{state} <跨层 {layer}>: {len(result.failures)} 阻断失败 / {len(result.warnings)} 警告"
            )
            row_failures = []
            for item in result.failures:
                text = f"{item.criterion_id} @ {item.locate()}: {item.message}"
                lines.append(f"    ✗ {text}")
                row_failures.append(text)
            row_warnings = []
            for item in result.warnings:
                text = f"{item.criterion_id} @ {item.locate()}: {item.message}"
                lines.append(f"    ! {text}")
                row_warnings.append(text)
            if not result.passed:
                failures += 1
            criteria_rows.append(
                {
                    "scope": "layer",
                    "target": layer,
                    "passed": result.passed,
                    "failures": row_failures,
                    "warnings": row_warnings,
                }
            )

        # 仓库层判据(layer=repo)对整个仓求值,不对单个制品求值。
        # 与 `criteria --repo` 共用 `_repo_criteria_row` —— 同一批判据、同一份受检集合。
        repo_row, repo_lines, _repo_count = _repo_criteria_row(root, criteria)
        if repo_row is not None:
            lines.extend(repo_lines)
            if not repo_row["passed"]:
                failures += 1
            criteria_rows.append(repo_row)
    except CriteriaError as exc:
        # 判据参数非法(契约 §4.1.1)—— 显式失败,退出码 2,绝不静默放行。
        fatal = [f"✗ {exc}", "✗ 判据参数非法 —— 门禁 fail-closed(不放行)"]
        return _gate_payload(gates, criteria_rows, artifact_rows, failures + 1, True), lines, fatal

    # 制品自洽性: 状态块 + 复审块(与 verify 共用 _field_problems)。
    # 契约里的规则如果只写在 verify 里, CI 跑的却是 gate —— 那就是假绿。
    lines.append("— 制品自洽性 —")
    for artifact in artifacts:
        text = _entry_text(root, artifact)
        problems = _field_problems(
            parse_status(text, artifact.rel), parse_review(text, artifact.rel)
        )
        state = "✓" if not problems else "✗"
        lines.append(f"{state} {artifact.rel}: {len(problems)} 处不自洽")
        for problem in problems:
            lines.append(f"    ✗ {problem}")
        if problems:
            failures += 1
        artifact_rows.append({"artifact": artifact.rel, "problems": list(problems)})

    # F9:派生视图**不落盘** —— 留痕 = 制品 + git 历史(不再写 control/state.json)。
    return _gate_payload(gates, criteria_rows, artifact_rows, failures, False), lines, []


def cmd_gate(root: Path, args) -> int:
    """全仓门禁。`--json` 只改变**呈现**,不改判定。

    文本模式的输出与历史版本逐字节一致;`--json` 时 stdout 只有**一个** JSON 对象。
    """
    as_json = bool(getattr(args, "json", False))
    payload, lines, fatal = _collect_gate_report(root)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
        for message in fatal:
            print(message, file=sys.stderr)
        if fatal:
            return EXIT_USAGE
        return EXIT_FAIL if payload["failures"] else EXIT_OK
    for line in lines:
        print(line)
    for message in fatal:
        print(message, file=sys.stderr)
    if fatal:
        return EXIT_USAGE
    if payload["failures"]:
        print(f"✗ 门禁未通过: {payload['failures']} 项")
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


def _trio_siblings(artifacts: list[Artifact], target: Artifact) -> list[Artifact]:
    """同 topic、不同层(prd / td / plan)的兄弟制品。

    只认**已经存在**的兄弟:缺失的层不是阻塞项(一个仓库可能只有 PRD 一层)。
    同 topic 的多个实例(不同日期的同名 topic)都算兄弟 —— 任一未就位即整组不就位。
    排序固定 prd → td → plan,保证提示与证据顺序稳定。
    """
    order = {layer: index for index, layer in enumerate(TRIO_LAYERS)}
    siblings = [
        art
        for art in artifacts
        if art.topic == target.topic
        and art.layer in TRIO_LAYERS
        and art.layer != target.layer
    ]
    return sorted(siblings, key=lambda art: (order[art.layer], art.rel))


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
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE

    actor = (args.actor or "agent:ssdctl").strip()
    problems: list[str] = []

    # R-3 / INV-3:`--actor` 只接受 `agent:<id>` 形态 —— 人工署名写在制品的
    # `## 复审 (Review)` 段内,机器既不代填、也不覆盖。人与 agent 跑的是同一条命令。
    if not _AGENT_ACTOR_RE.match(actor):
        problems.append(
            f"`--actor` 只接受 `agent:<id>` 形态: {actor!r}"
            " —— 人工署名请先写在制品的 `## 复审 (Review)` 段内,再跑同一条 advance"
        )

    original_text = _entry_text(root, artifact)
    existing_review = parse_review(original_text, artifact.rel)
    waived_ids = known_issue_ids(existing_review)
    has_review_section = section_span(original_text.split("\n"), REVIEW_HEADING_KEY) is not None
    # 机器写复审块的条件:段在、但没有署名(人工写了署名 ⇒ 机器不覆盖)。
    machine_writes_review = has_review_section and not existing_review.reviewer
    if not has_review_section and not existing_review.reviewer:
        problems.append(f"制品 {artifact.rel} 缺少 `## 复审 (Review)` 段 —— 无法写入复审块")

    # Implemented / Deprecated 需要一条 `external:` 依据:
    # 来自 `--external <ref>`,或制品正文里出现的 `external:<ref>` token(取第一个)。
    shared_external: str | None = None
    if target_state in ("Implemented", "Deprecated"):
        refs: list[str] = []
        flag = (getattr(args, "external", None) or "").strip()
        if flag:
            refs.append(flag if flag.startswith("external:") else f"external:{flag}")
        refs.extend(util.external_refs(original_text))
        if not refs:
            problems.append(
                f"进入 {target_state} 需要 `external:` 依据 —— "
                "用 `--external <ref>` 或在制品正文写 `external:<ref>`"
            )
        else:
            shared_external = refs[0]

    # 复审块取值(F9):机器只在复审块**为空**时写 —— 已有署名(人工写的)原样保留。
    reviewer = actor
    method = "外部事实" if shared_external else "自动判据"
    if method not in REVIEW_METHODS:
        method = "自动判据"
    conclusion = "通过"
    review_date = _now().strftime("%Y-%m-%d")
    timestamp = util.now_iso()
    subject = actor  # INV-3:状态主体永远是 agent:<id>,机器不写 human:

    # 判据求值分两遍(F9 死锁修复):
    # 第 1 遍按**现状**求值 —— 用来算 `criteria:` 授权依据。
    document = _artifact_document(root, artifact)
    try:
        result = evaluate_layer(
            criteria, document, artifact.layer, _scoped_repo_documents(root, artifact.topic)
        )
    except CriteriaError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE
    criteria_basis = _basis_from_criteria(criteria, artifact.layer, result)

    # 第 2 遍按**机器写完之后**的模拟文本复算 —— 阻断/警告闸门以这一遍为准。
    # 少了这一遍,「复审段只有标题、4 行都没有」时复审块那几条阻断判据会在
    # 机器写复审块之前就失败 ⇒ 机器永远走不到写复审块那一步(死锁)。
    # 复算只改内存里的文本,失败仍然是零文件改动。
    if machine_writes_review:
        simulated_text = apply_status_block(
            original_text,
            render_status_block(target_state, subject, timestamp, criteria_basis or ""),
        )
        simulated_text = apply_review_block(
            simulated_text, render_review_block(reviewer, review_date, conclusion, method)
        )
        simulated_doc = _simulated_document(root, artifact, simulated_text)
        try:
            result = evaluate_layer(
                criteria,
                simulated_doc,
                artifact.layer,
                _scoped_repo_documents(
                    root, artifact.topic, simulated=(artifact, simulated_doc)
                ),
            )
        except CriteriaError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            return EXIT_USAGE
        criteria_basis = _basis_from_criteria(criteria, artifact.layer, result) or criteria_basis

    # §5.2 规则 1 + 2:blocking 判据必须全绿;非阻断失败必须被复审段的「已知问题」行点名。
    if target_state in ("Ready", "Implemented"):
        for item in result.failures:
            problems.append(f"阻断判据未通过 {item.criterion_id} @ {item.locate()}: {item.message}")
        for item in result.warnings:
            if item.criterion_id in waived_ids:
                continue
            problems.append(
                f"警告判据 {item.criterion_id} @ {item.locate()} 未被复审段点名 —— "
                f"请在 `## 复审 (Review)` 段内写 "
                f"`> **已知问题**: {item.criterion_id} — <说明>` 后重跑({item.message})"
            )

    # §5.2 规则 3:跨层推进时上游必须 Ready
    artifacts = discover_artifacts(root)
    upstreams = resolve_upstream(root, artifact, artifacts)
    if target_state in ("Ready", "Implemented"):
        for item in upstreams:
            if item.artifact is None:
                problems.append(f"上游未解析:{item.reason}")
                continue
            state = parse_status(_entry_text(root, item.artifact), item.artifact.rel).state
            if state not in ("Ready", "Implemented"):
                problems.append(
                    f"上游未 Ready:{item.artifact.rel} 状态={state or '未声明'}"
                )

    # §5.2 规则 5(WORKFLOW.md §5「三件套一致性规则」):
    # PRD / Tech Design / Plan 必须**同时**进入 Implemented —— 不允许单层先 Implemented。
    # 只对**已存在**的兄弟生效:缺失的层不是阻塞项(仓库可能只有 PRD 一层)。
    # test-case 独立于三件套生命周期(AGENTS.md §3.3),不参与这条规则。
    trio_siblings: list[Artifact] = []
    if target_state == "Implemented" and artifact.layer in TRIO_LAYERS:
        for sibling in _trio_siblings(artifacts, artifact):
            sibling_state = parse_status(_entry_text(root, sibling), sibling.rel).state
            if sibling_state == "Ready":
                trio_siblings.append(sibling)
            elif sibling_state == "Implemented":
                continue  # 已经就位,不动它
            else:
                problems.append(
                    f"三件套未同时就绪:兄弟制品 {sibling.rel} 状态={sibling_state or '未声明'}"
                    f"(PRD / Tech Design / Plan 必须同时进入 Implemented)"
                )

    # §5.2 规则 4(F9):授权来源只剩两种 —— `criteria:`(判据全绿)与 `external:`(外部事实)。
    basis_items: list[str] = []
    if target_state in ("Ready", "Implemented") and criteria_basis:
        basis_items.append(criteria_basis)

    if shared_external:
        basis_items.append(shared_external)

    # 兄弟制品的状态依据:同一份外部事实依据(一次外部实现、三层规格),
    # 不替兄弟编造 criteria 依据 —— 那是目标层自己的判据。
    sibling_basis: list[str] = []
    if shared_external:
        sibling_basis.append(shared_external)
    for sibling in trio_siblings:
        if not sibling_basis:
            problems.append(f"兄弟制品 {sibling.rel} 没有可用的状态依据(缺 external: 依据)")
        elif section_span(_entry_text(root, sibling).split("\n"), REVIEW_HEADING_KEY) is None:
            problems.append(f"兄弟制品 {sibling.rel} 缺少 `## 复审 (Review)` 段 —— 无法写入复审块")

    # Deprecated 的状态依据必须是 external:(F9 取代原 decision:)
    if target_state == "Deprecated":
        if not any(item.startswith("external:") for item in basis_items):
            problems.append("进入 Deprecated 的状态依据必须是 `external:`,不能用 `criteria:`")

    if not basis_items:
        problems.append("没有可用授权来源(判据没有可引用的授权,也没有 external: 依据)")

    if problems:
        print(f"✗ 不允许推进 {artifact.rel} → {target_state}:", file=sys.stderr)
        for problem in problems:
            print(f"    - {problem}", file=sys.stderr)
        print("  (目标文件未做任何修改)", file=sys.stderr)
        return EXIT_FAIL

    # 本次转换要写的制品:目标 + 已在 Ready 的兄弟(三件套同时进入 Implemented)。
    # 每个制品各自算自己的正文与依据 —— 兄弟用同一份外部事实依据。
    writes: list[tuple[Artifact, str, list[str], str]] = []
    for art, basis in [(artifact, basis_items)] + [(sib, sibling_basis) for sib in trio_siblings]:
        text = apply_status_block(
            _entry_text(root, art),
            render_status_block(target_state, subject, timestamp, ",".join(basis)),
        )
        if parse_review(text, art.rel).reviewer:
            review_note = "原样保留(复审块已有署名,机器不覆盖)"
        else:
            text = apply_review_block(
                text, render_review_block(reviewer, review_date, conclusion, method)
            )
            review_note = (
                f"机器写入 评审人={reviewer} 日期={review_date} 结论={conclusion} 方式={method}"
            )
        writes.append((art, text, basis, review_note))

    plan: list[list[str]] = []
    for art, _text, basis, review_note in writes:
        plan.append(
            [
                f"制品: {art.rel}",
                f"目标状态: {target_state}",
                f"状态主体: {subject}",
                f"状态依据: {','.join(basis)}",
                f"复审块: {review_note}",
            ]
        )
    if args.dry_run:
        print("— 计划(未写任何文件) —")
        for block in plan:
            for line in block:
                print(f"  {line}")
        return EXIT_OK

    # F9 留痕:状态块 + 复审块 + git 历史 —— 不再写 `control/evidence/**`。
    # 半写防护:目标文件写失败 ⇒ 报出已写入的清单,请人工核对(不再有证据链兜底)。
    written: list[Artifact] = []
    for art, new_text, _basis, _note in writes:
        try:
            art.entry.write_text(new_text, encoding="utf-8", newline="\n")
        except OSError as exc:
            print(f"✗ 目标文件写入失败: {exc}", file=sys.stderr)
            if written:
                print(
                    "    已写入: " + ", ".join(item.rel for item in written) + "(请人工核对)",
                    file=sys.stderr,
                )
            else:
                print("    (目标文件未做任何修改)", file=sys.stderr)
            return EXIT_USAGE
        written.append(art)

    print("— 已推进 —")
    for block in plan:
        for line in block:
            print(f"  {line}")
    print("  留痕: 制品状态块 + 复审块 + git 历史")
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


# -------------------------------------------------------------------- verify


def _field_problems(status, review) -> list[str]:
    """制品自身的字段自洽性(状态块 §3.1 + 复审块 §3.2)。

    `cmd_verify` 与 `cmd_gate` 共用这一份判定 —— 两处说同一件事,
    免得出现「verify 说没问题、gate 说有问题」的门禁空洞。

    判定口径与 `scripts/check-md-schema.py` 的 `check_status_meta` /
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
            problems.append(f"`状态依据` 项 `{item}` 不在 criteria:/external: 之中")
        if status.state == "Deprecated" and any(item.startswith("criteria:") for item in valid):
            problems.append("`状态依据` 在 Deprecated 态只能是 external:,不能用 criteria:")

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
    problems.extend(known_issue_shape_problems(review))

    return problems


def cmd_verify(root: Path, args) -> int:
    artifact = _resolve_artifact(root, args.artifact)
    text = _entry_text(root, artifact)
    status = parse_status(text, artifact.rel)
    review = parse_review(text, artifact.rel)
    problems: list[str] = _field_problems(status, review)

    if problems:
        print(f"✗ {artifact.rel} 不一致:", file=sys.stderr)
        for problem in problems:
            print(f"    - {problem}", file=sys.stderr)
        return EXIT_FAIL
    print(f"✓ {artifact.rel} 一致(状态 {status.state})")
    return EXIT_OK
