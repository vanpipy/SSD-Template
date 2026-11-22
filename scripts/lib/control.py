"""控制平面(契约 §6):人工介入决定、证据链、派生状态文件。

- `control/decisions/<YYYY-MM-DD>-<topic>.md` : 人工介入记录(§6.1)
- `control/evidence/<YYYY-MM>/<YYYY-MM-DDTHHMMSS>-<topic>.jsonl` : 只追加的证据链(§6.2)
- `control/state.json` : 由 `scan`/`gate` 生成的派生状态(§5.3)

证据链**只追加**:任何命令都不重写已有记录。派生状态可被完整重建(契约 INV-6)。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .paths import decisions_dir, evidence_dir, state_path

_DECISION_ID_RE = re.compile(r"^D\d+$")
_DECISION_FIELD_RE = re.compile(r"^\s*>\s*\*\*(?P<key>[^*]+)\*\*\s*[:：]\s*(?P<value>.*?)\s*$")
_TABLE_ROW_RE = re.compile(r"^\s*\|(?P<cells>.+)\|\s*$")
_EXTERNAL_REF_RE = re.compile(r"external:[^\s|,]+")


@dataclass(frozen=True)
class Decision:
    """一条人工介入决定(§6.1)。

    `writer` 是契约 §6.1 新增的「记录写入者」行 —— 谁**写下了这份文件**。
    它与 `actor`(决定里的**操作人**)是两件事:操作人是署名,写入者是留痕。
    人手工写的文件可以不写这一行,解析时容忍缺失(§6.1)。
    """

    id: str
    ts: str
    actor: str
    artifact: str
    action: str
    scope: str
    reason: str
    rel: str
    external_ref: str | None = None
    writer: str | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "ts": self.ts,
            "actor": self.actor,
            "artifact": self.artifact,
            "action": self.action,
            "scope": self.scope,
            "reason": self.reason,
            "file": self.rel,
            "external_ref": self.external_ref,
            "writer": self.writer,
        }

    def covers(self, criterion_id: str) -> bool:
        """范围=all 时覆盖任何判据;否则只覆盖点名的判据。"""
        if self.scope.strip().lower() == "all":
            return True
        return criterion_id.strip().lower() == self.scope.strip().lower()


def sha256_text(text: str) -> str:
    """契约 §6.2 要求的 `sha256:...`。"""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    """带时区的 ISO-8601 时间戳(契约 §3.1 要求带时区)。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ------------------------------------------------------------------ 决定文件读写


def decision_file(root: Path, topic: str, day: str | None = None) -> Path:
    """决定文件路径 `control/decisions/<YYYY-MM-DD>-<topic>.md`。"""
    stamp = day or datetime.now().astimezone().strftime("%Y-%m-%d")
    return decisions_dir(root) / f"{stamp}-{topic}.md"


def write_decision(
    root: Path,
    topic: str,
    action: str,
    actor: str,
    reason: str,
    artifact: str,
    criterion: str | None = None,
    external_ref: str | None = None,
    writer: str = "agent:ssdctl",
) -> tuple[Path, Decision]:
    """写一条决定(§6.1)。已存在同名文件时追加新决定块,不改写旧决定。"""
    target = decision_file(root, topic)
    target.parent.mkdir(parents=True, exist_ok=True)
    scope = criterion if criterion else "all"
    ts = now_iso()

    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    if existing:
        ident = _next_decision_id(existing)
    else:
        ident = "D1"

    block = [
        "",
        f"## 决定 {ident}",
        "",
        f"> **决定 ID**: {ident}",
        f"> **时间**: {ts}",
        f"> **操作人**: {actor}",
        f"> **记录写入者**: {writer}",
        f"> **目标制品**: {artifact}",
        f"> **动作**: {action}",
        f"> **范围**: {scope}",
        f"> **理由**: {reason}",
    ]
    if external_ref:
        block.append(f"> **外部事实**: {external_ref}")
    block += [
        "",
        "| ID | 决定 | 理由 |",
        "|----|------|------|",
        f"| {scope} | {action} | {reason} |",
        "",
    ]

    if not existing:
        header = [
            f"# 人工介入记录 · {topic}",
            "",
            f"> **决定 ID**: {ident}",
            f"> **时间**: {ts}",
            f"> **操作人**: {actor}",
            f"> **记录写入者**: {writer}",
            f"> **目标制品**: {artifact}",
            f"> **动作**: {action}",
            f"> **范围**: {scope}",
            f"> **理由**: {reason}",
        ]
        if external_ref:
            header.append(f"> **外部事实**: {external_ref}")
        header += [
            "",
            "| ID | 决定 | 理由 |",
            "|----|------|------|",
            f"| {scope} | {action} | {reason} |",
            "",
        ]
        content = "\n".join(header)
    else:
        content = existing.rstrip("\n") + "\n" + "\n".join(block)

    target.write_text(content, encoding="utf-8", newline="\n")
    decision = Decision(
        id=ident,
        ts=ts,
        actor=actor,
        artifact=artifact,
        action=action,
        scope=scope,
        reason=reason,
        rel=target.relative_to(root).as_posix(),
        external_ref=external_ref,
        writer=writer,
    )
    return target, decision


def _next_decision_id(text: str) -> str:
    ids = [int(m.group(1)) for m in re.finditer(r"\*\*决定 ID\*\*:\s*D(\d+)", text)]
    return f"D{max(ids) + 1 if ids else 1}"


def read_decisions(root: Path, artifact: str | None = None) -> list[Decision]:
    """读出全部决定(可按目标制品过滤)。"""
    directory = decisions_dir(root)
    if not directory.is_dir():
        return []
    out: list[Decision] = []
    for path in sorted(directory.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for decision in _parse_decision_text(text, path.relative_to(root).as_posix()):
            if artifact is None or _same_artifact(decision.artifact, artifact):
                out.append(decision)
    return out


def _same_artifact(left: str, right: str) -> bool:
    def norm(value: str) -> str:
        return value.strip().replace("\\", "/").lstrip("./")

    return norm(left) == norm(right)


def _parse_decision_text(text: str, rel: str) -> list[Decision]:
    decisions: list[Decision] = []
    current: dict[str, str] = {}
    ident: str | None = None
    external: str | None = None

    def flush() -> None:
        nonlocal current, ident, external
        if ident is None:
            return
        decisions.append(
            Decision(
                id=ident,
                ts=current.get("时间", ""),
                actor=current.get("操作人", ""),
                artifact=current.get("目标制品", ""),
                action=current.get("动作", ""),
                scope=current.get("范围", "all"),
                reason=current.get("理由", ""),
                rel=rel,
                external_ref=external,
                # 契约 §6.1:「记录写入者」缺失(人手写的旧文件)时留空,不得报错。
                writer=current.get("记录写入者") or None,
            )
        )
        current = {}
        ident = None
        external = None

    for line in text.split("\n"):
        match = _DECISION_FIELD_RE.match(line)
        if match:
            key = match.group("key").strip()
            value = match.group("value").strip()
            if key == "决定 ID":
                flush()
                ident = value
                current[key] = value
                continue
            if key == "外部事实":
                external = value
                current[key] = value
                continue
            if ident is not None:
                current[key] = value
            continue
        row = _TABLE_ROW_RE.match(line)
        if row and ident is not None:
            cells = [cell.strip() for cell in row.group("cells").split("|")]
            if len(cells) >= 3 and cells[0] not in ("ID", "----") and not set(cells[0]) <= {"-"}:
                if not current.get("范围"):
                    current["范围"] = cells[0]
                if not current.get("动作"):
                    current["动作"] = cells[1]
                if not current.get("理由"):
                    current["理由"] = cells[2]
    flush()
    return [item for item in decisions if _DECISION_ID_RE.match(item.id)]


def find_decision(root: Path, ref: str) -> Decision | None:
    """按 `path#anchor` 或纯 path 找一条决定。"""
    path_part, _, anchor = ref.partition("#")
    candidates = read_decisions(root)
    for decision in candidates:
        if decision.rel == path_part.replace("\\", "/") and (not anchor or decision.id == anchor):
            return decision
    return None


# ------------------------------------------------------------------ 证据链读写


def evidence_path(root: Path, timestamp: datetime, topic: str) -> Path:
    """证据文件路径 `control/evidence/<YYYY-MM>/<YYYY-MM-DDTHHMMSS>-<topic>.jsonl`。"""
    month = timestamp.astimezone().strftime("%Y-%m")
    stamp = timestamp.astimezone().strftime("%Y-%m-%dT%H%M%S")
    return evidence_dir(root) / month / f"{stamp}-{topic}.jsonl"


def append_evidence(root: Path, record: dict, timestamp: datetime | None = None) -> Path:
    """追加一条证据记录(§6.2)。只追加,永不重写。"""
    moment = timestamp or datetime.now().astimezone()
    topic = str(record.get("artifact") or "unknown").rsplit("/", 1)[-1].replace(".md", "")
    target = evidence_path(root, moment, topic)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
    return target


def read_evidence(root: Path, artifact: str | None = None) -> list[dict]:
    """读回证据链(可按制品过滤),按时间排序。"""
    directory = evidence_dir(root)
    if not directory.is_dir():
        return []
    records: list[dict] = []
    for path in sorted(directory.rglob("*.jsonl")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            record.setdefault("_file", path.relative_to(root).as_posix())
            if artifact is None or _same_artifact(str(record.get("artifact", "")), artifact):
                records.append(record)
    records.sort(key=lambda item: str(item.get("ts", "")))
    return records


def external_refs(records: list[dict]) -> list[str]:
    """从证据链里摘出所有 `external:` 依据(契约 §5.2 的 Implemented 前提)。"""
    refs: list[str] = []
    for record in records:
        for value in list(record.get("decisions") or []) + [str(record.get("reason") or "")]:
            for found in _EXTERNAL_REF_RE.findall(str(value)):
                if found not in refs:
                    refs.append(found)
    return refs


# ------------------------------------------------------------------ 派生状态文件


def write_state(root: Path, payload: dict) -> Path:
    """写 `control/state.json`(派生数据,可整体重建)。"""
    target = state_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


def read_state(root: Path) -> dict | None:
    target = state_path(root)
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
