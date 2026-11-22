"""调度谓词(契约 §7):上游解析 + 5 合取判定 + 依赖许可三态。

硬规则(契约 INV-1 / §7):`upstream_ready` **只读制品内的状态行**,
绝不读任何外部工单状态 —— 制品状态块是唯一权威。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .artifacts import Artifact, parse_status, referenced_ids, section_span

# 上游关系(契约 §7.2):prd 无上游;td 依赖同 topic 的 prd;plan 依赖同 topic 的 td
# (无 TD 时回退 prd);test-case 依赖同 topic 的 prd + td。
UPSTREAM_LAYERS: dict[str, tuple[str, ...]] = {
    "prd": (),
    "td": ("prd",),
    "plan": ("td", "prd"),
    "test-case": ("prd", "td"),
}

PERMISSION_BLOCKED = "blocked"
PERMISSION_DRAFTABLE = "draftable"
PERMISSION_COMMITTABLE = "committable"

ACTIVE_STATES = ("Draft", "Ready", "Implemented")

_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./\-]+\.md|[A-Za-z0-9_./\-]+/")


@dataclass
class Upstream:
    """一个上游制品的解析结果。"""

    layer: str
    artifact: Artifact | None
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return self.artifact is not None


@dataclass
class Dispatch:
    """一个制品的调度判定结果(契约 §5.3 的 artifact 条目)。"""

    layer: str
    topic: str
    path: str
    state: str | None
    state_subject: str | None
    upstream: list[str] = field(default_factory=list)
    upstream_states: list[str] = field(default_factory=list)
    dependency_permission: str = PERMISSION_BLOCKED
    dispatchable: bool = False
    reason: str = ""
    missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "layer": self.layer,
            "topic": self.topic,
            "path": self.path,
            "state": self.state,
            "state_subject": self.state_subject,
            "upstream": list(self.upstream),
            "upstream_states": list(self.upstream_states),
            "dependency_permission": self.dependency_permission,
            "dispatchable": self.dispatchable,
            "reason": self.reason,
            "missing": list(self.missing),
        }


def _links_paths(entry_text: str) -> list[str]:
    """取 `## 链接 (Links)` 段里出现的仓库内路径。"""
    lines = entry_text.split("\n")
    span = section_span(lines, "链接")
    if span is None:
        return []
    body = "\n".join(lines[span[0] : span[1]])
    found: list[str] = []
    for token in _PATH_TOKEN_RE.findall(body):
        cleaned = token.strip().strip("`")
        if not cleaned:
            continue
        if cleaned in found:
            continue
        found.append(cleaned)
    return found


def _convention_candidates(layer: str, topic: str, date: str) -> list[str]:
    """目录约定下的候选路径(同日期优先)。"""
    if layer == "prd":
        return [f"prd/{date}/{topic}.md"]
    if layer == "td":
        return [f"tech_design/{date}-{topic}/"]
    if layer == "plan":
        return [f"plan/{date}-{topic}/{topic}.md"]
    if layer == "test-case":
        return [f"test_cases/{date}/{topic}.md"]
    return []


def resolve_upstream(
    root: Path,
    artifact: Artifact,
    artifacts: list[Artifact],
) -> list[Upstream]:
    """解析制品的上游(契约 §7.2)。

    顺序:制品 `## 链接 (Links)` 里的显式路径 → 目录约定(同日期 → 同 topic 任意日期)。
    两者都找不到 ⇒ 该上游记入 `missing`,layer_resolved=false。
    """
    expected = UPSTREAM_LAYERS.get(artifact.layer, ())
    if not expected:
        return []

    entry_text = ""
    try:
        entry_text = artifact.entry.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        entry_text = ""
    explicit = _links_paths(entry_text)

    resolved: list[Upstream] = []
    for layer in expected:
        hit: Artifact | None = None
        reason = ""

        for candidate in explicit:
            normalized = candidate.replace("\\", "/").rstrip("/")
            for art in artifacts:
                if art.layer != layer:
                    continue
                if art.rel == normalized or art.rel.rstrip("/") == normalized:
                    hit = art
                    break
                # 目录式引用:`tech_design/2026-11-22-x/` 指向该目录下的 README.md
                if art.rel.rstrip("/") == normalized and art.rel.endswith("/README.md"):
                    hit = art
                    break
            if hit is not None:
                reason = f"经 `## 链接 (Links)` 显式路径 `{candidate}` 解析"
                break

        if hit is None:
            for candidate in _convention_candidates(layer, artifact.topic, artifact.date):
                for art in artifacts:
                    if art.layer != layer:
                        continue
                    if art.rel == candidate or art.rel.rstrip("/") == candidate.rstrip("/"):
                        hit = art
                        reason = f"经目录约定 `{candidate}` 解析"
                        break
                if hit is not None:
                    break

        if hit is None:
            for art in artifacts:
                if art.layer == layer and art.topic == artifact.topic:
                    hit = art
                    reason = f"经同 topic 目录 `{art.rel}` 解析"
                    break

        if hit is None:
            resolved.append(
                Upstream(
                    layer=layer,
                    artifact=None,
                    reason=(
                        f"上游 {layer} 未找到:既无 `## 链接 (Links)` 显式路径, "
                        f"也无目录约定命中(topic={artifact.topic})"
                    ),
                )
            )
        else:
            resolved.append(Upstream(layer=layer, artifact=hit, reason=reason))
    return resolved


def upstream_state(root: Path, artifact: Artifact) -> str | None:
    """读上游制品自己的状态行(状态块是唯一权威,契约 INV-1)。"""
    try:
        text = artifact.entry.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return parse_status(text, artifact.rel).state


def evaluate_dispatch(
    root: Path,
    artifact: Artifact,
    artifacts: list[Artifact],
    upstreams: list[Upstream] | None = None,
) -> Dispatch:
    """5 合取调度谓词(契约 §7)。

    1. 状态 ∈ {Draft, Ready, Implemented}
    2. 状态 ∉ {Deprecated}
    3. required_labels ⊆ labels —— 本仓没有标签体系 ⇒ 记 `not_configured`,恒真
    4. upstream_ready —— 上游制品状态 ∈ {Ready, Implemented}
    5. layer_resolved —— 上游全部解析成功
    """
    resolved = upstreams if upstreams is not None else resolve_upstream(root, artifact, artifacts)
    try:
        text = artifact.entry.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    status = parse_status(text, artifact.rel)

    upstream_paths: list[str] = []
    upstream_states: list[str] = []
    # `unresolved` = 上游**没解析出来**(缺失 / 没有状态行)⇒ 依赖许可 blocked;
    # `missing` = 派发还差什么(未解析 + 上游未就绪 + 自身状态不合格)。
    unresolved: list[str] = []
    missing: list[str] = []
    upstream_ready = True

    for item in resolved:
        if item.artifact is None:
            unresolved.append(item.reason)
            upstream_ready = False
            continue
        upstream_paths.append(item.artifact.rel)
        state = upstream_state(root, item.artifact)
        upstream_states.append(state or "未声明")
        if state is None:
            unresolved.append(f"上游 {item.artifact.rel} 没有状态行")
            upstream_ready = False
        elif state not in ("Ready", "Implemented"):
            upstream_ready = False
            missing.append(
                f"上游 {item.artifact.rel} 状态为 {state}, 尚未 Ready(依赖许可=draftable)"
            )

    state = status.state
    state_ok = state in ACTIVE_STATES
    not_deprecated = state != "Deprecated"
    labels_ok = True  # 本仓无标签体系 ⇒ not_configured,恒真
    layer_resolved = not unresolved
    missing = unresolved + missing

    if state is None:
        missing.append("制品没有状态行")
    elif not state_ok:
        missing.append(f"状态 `{state}` 不在可调度集合 {list(ACTIVE_STATES)}")

    if not resolved:
        permission = PERMISSION_COMMITTABLE
    elif not layer_resolved:
        permission = PERMISSION_BLOCKED
    elif upstream_ready:
        permission = PERMISSION_COMMITTABLE
    else:
        permission = PERMISSION_DRAFTABLE

    dispatchable = bool(state_ok and not_deprecated and labels_ok and upstream_ready and layer_resolved)

    reasons: list[str] = []
    if state is None:
        reasons.append("制品没有状态行")
    elif not state_ok:
        reasons.append(f"状态 `{state}` 不在可调度集合 {list(ACTIVE_STATES)}")
    if not_deprecated is False:  # pragma: no cover - 状态已 Deprecated 时 state_ok 同时为假
        reasons.append("状态为 Deprecated")
    if not upstream_ready:
        reasons.append("上游未全部 Ready")
    if not layer_resolved:
        reasons.append("上游未解析成功")
    reasons.append("labels=not_configured(本仓无标签体系,恒真)")

    return Dispatch(
        layer=artifact.layer,
        topic=artifact.topic,
        path=artifact.rel,
        state=state,
        state_subject=status.subject,
        upstream=upstream_paths,
        upstream_states=upstream_states,
        dependency_permission=permission,
        dispatchable=dispatchable,
        reason="; ".join(reasons),
        missing=missing,
    )
