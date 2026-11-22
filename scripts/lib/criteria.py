"""判据引擎:加载 `schema/criteria.json` 并实现契约 §4.1 的 **12 种 kind**。

kind 词表是**封闭集合**。新增 kind 必须同时改实施契约 §4.1 与本模块,并补单元测试
(契约 §4.1 末句)。加载失败(文件缺失/非法)一律抛 `CriteriaError`,由调用方转成退出码 2,
**绝不静默放行**。

kind 速查:
    section_exists{sections[]}        line_present{regex}          line_absent{regex}
    enum_field{field,values[]}        date_format{field}           checkbox_present{min_count}
    id_format{prefix,pattern}         id_unique{prefix}            id_refs_resolve{from_prefix,to_prefix,via_field}
    count_min{regex,min_count}        no_placeholder{regex}        coverage_complete{from_prefix,to_prefix,via_field}

参数契约(契约 §4.1.1):每个 kind 有**必填参数集**与**可选参数集**
(见 `KIND_PARAMS`)。缺必填参数、含未知参数、类型或取值非法(空串/空列表/
`min_count` 非整数或 < 1/非法正则)——任何一种都抛 `CriteriaError`(退出码 2)。
**参数缺失的判据若被放行,就会变成「永远通过」的假绿**(例如 `regex` 缺失时
空正则匹配任意行、`sections` 缺失时遍历空列表),比缺这条判据更危险。

`coverage_complete` 支持可选参数 `scope`:
    scope="doc"(默认) —— 单文档求值,from/to 声明位与 via_field 行都在同一制品里。
    scope="repo"     —— 跨层求值:from_prefix 的声明位在 `from_layer` 制品里,
                        to_prefix 的声明位在 `to_layer` 制品里,via_field 行出现在 to 一侧。
                        需要 `from_layer` / `to_layer` 两个参数。
**不支持的 scope 一律判为失败**(报「不支持的 scope」),绝不静默通过 ——
静默通过会让跨层覆盖不变式变成假绿,比缺这条判据更危险。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .artifacts import (
    _HEADING_RE,
    _QUOTE_FIELD_RE,
    _TABLE_FIELD_RE,
    declared_ids,
    id_pattern_matches,
    read_quote_fields,
    read_table_fields,
    referenced_ids,
    section_span,
)

# `**覆盖**: AC-1` 这种无 `>` 的粗体字段(契约 §3.3 / §3.4 用的就是这种写法)
_BOLD_FIELD_RE = re.compile(r"^\s*\*\*(?P<key>[^*]+)\*\*\s*[:：]\s*(?P<value>.*?)\s*$")


def field_match(line: str) -> tuple[str, str] | None:
    """识别一行里的「字段: 值」。支持引用块、表格、粗体三种写法。"""
    match = _QUOTE_FIELD_RE.match(line)
    if match:
        return match.group("key").strip(), match.group("value").strip()
    match = _BOLD_FIELD_RE.match(line)
    if match:
        return match.group("key").strip(), match.group("value").strip()
    match = _TABLE_FIELD_RE.match(line)
    if match:
        return match.group("key").strip(), match.group("value").strip()
    return None

KINDS = frozenset(
    {
        "section_exists",
        "line_present",
        "line_absent",
        "enum_field",
        "date_format",
        "checkbox_present",
        "id_format",
        "id_unique",
        "id_refs_resolve",
        "count_min",
        "no_placeholder",
        "coverage_complete",
    }
)

# `coverage_complete` 的求值范围(契约 §4.1)。`scope` 是**参数**,不是 kind ——
# kind 词表仍是上面那 12 个,封闭不变。
SCOPE_DOC = "doc"
SCOPE_REPO = "repo"
SUPPORTED_SCOPES = (SCOPE_DOC, SCOPE_REPO)

LAYERS = ("prd", "td", "plan", "test-case", "repo")
ID_RE = re.compile(r"^[A-Z0-9-]+$")
DATE_VALUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLACEHOLDER_DEFAULT = r"\{[^}]+\}"
CHECKBOX_RE = re.compile(r"^\s*[-*+]\s*\[[ xX]\]")
MAX_REPORTED_LINES = 5

# 契约 §4.1.1:逐 kind 的参数契约 —— (必填集, 可选集)。
# 缺必填 / 未知参数 / 类型取值非法,一律在加载期拒绝(退出码 2)。
KIND_PARAMS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "section_exists": (frozenset({"sections"}), frozenset()),
    "line_present": (frozenset({"regex"}), frozenset()),
    "line_absent": (frozenset({"regex"}), frozenset()),
    "enum_field": (frozenset({"field", "values"}), frozenset()),
    "date_format": (frozenset({"field"}), frozenset()),
    "checkbox_present": (frozenset({"min_count"}), frozenset()),
    "id_format": (frozenset({"prefix", "pattern"}), frozenset()),
    "id_unique": (frozenset({"prefix"}), frozenset()),
    "id_refs_resolve": (frozenset({"from_prefix", "to_prefix", "via_field"}), frozenset()),
    "count_min": (frozenset({"regex", "min_count"}), frozenset()),
    "no_placeholder": (frozenset(), frozenset({"regex"})),
    "coverage_complete": (frozenset({"from_prefix", "to_prefix", "via_field"}), frozenset()),
}

# 全局可选参数(契约 §4.1.1):`scope` 对所有 kind 可用;
# `from_layer` / `to_layer` 仅在 `scope="repo"` 时必填。
GLOBAL_PARAMS = frozenset({"scope", "from_layer", "to_layer"})

# 需要校验为「非空字符串」的参数名
_STRING_PARAMS = (
    "field",
    "prefix",
    "pattern",
    "regex",
    "from_prefix",
    "to_prefix",
    "via_field",
    "from_layer",
    "to_layer",
)
# 需要校验为「非空字符串列表」的参数名
_STRING_LIST_PARAMS = ("sections", "values")


class CriteriaError(Exception):
    """判据文件缺失或非法 —— 调用方据此退出码 2。"""


@dataclass(frozen=True)
class Criterion:
    """一条判据。`blocking=True` 的失败会阻断该层进入 Ready(契约 §4.2)。"""

    id: str
    layer: str
    title: str
    kind: str
    params: dict
    blocking: bool
    source: str

    def as_claim(self, passed: bool) -> dict:
        return {"id": self.id, "title": self.title, "passed": passed}


@dataclass(frozen=True)
class Violation:
    """一条判据失败(阻断或警告)。"""

    criterion_id: str
    title: str
    kind: str
    blocking: bool
    message: str
    rel: str = ""
    line: int = 0

    def as_dict(self) -> dict:
        return {
            "id": self.criterion_id,
            "title": self.title,
            "kind": self.kind,
            "blocking": self.blocking,
            "message": self.message,
            "file": self.rel,
            "line": self.line,
        }

    def locate(self) -> str:
        if self.rel and self.line:
            return f"{self.rel}:{self.line}"
        return self.rel or "(全文)"


@dataclass
class CriteriaResult:
    """一次判据求值的结果(契约 §5.1 的 `criteria` 输出形状)。"""

    artifact: str
    layer: str
    failures: list[Violation] = field(default_factory=list)
    warnings: list[Violation] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """没有 blocking 失败即通过;警告不改变 passed(但会阻断 advance,见 §4.2)。"""
        return not self.failures

    def as_dict(self) -> dict:
        return {
            "artifact": self.artifact,
            "layer": self.layer,
            "passed": self.passed,
            "failures": [item.as_dict() for item in self.failures],
            "warnings": [item.as_dict() for item in self.warnings],
            "claims": list(self.claims),
        }


# ------------------------------------------------------------------ 判据文件加载


def _require_nonempty_string(criterion: Criterion, key: str, value: object) -> None:
    # 只判「空字符串」,不判 strip 后为空 —— 正则参数可以是单个 CR(`"\r"`),
    # 而 CR 是空白字符,strip 之后会变成空串,那会把一条合法判据误杀。
    if not isinstance(value, str) or value == "":
        raise CriteriaError(
            f"判据 {criterion.id} 的参数 {key} 必须是非空字符串: {value!r}"
        )


def _require_nonempty_str_list(criterion: Criterion, key: str, value: object) -> None:
    if not isinstance(value, list) or not value:
        raise CriteriaError(
            f"判据 {criterion.id} 的参数 {key} 必须是非空列表: {value!r}"
        )
    for item in value:
        if not isinstance(item, str) or item == "":
            raise CriteriaError(
                f"判据 {criterion.id} 的参数 {key} 的元素必须是非空字符串: {item!r}"
            )


def _require_valid_regex(criterion: Criterion, key: str, value: object) -> None:
    try:
        re.compile(value)  # type: ignore[arg-type]
    except (re.error, TypeError) as exc:
        raise CriteriaError(
            f"判据 {criterion.id} 的参数 {key} 不是合法正则: {value!r} ({exc})"
        ) from exc


def validate_params(criterion: Criterion) -> None:
    """逐 kind 校验判据参数(契约 §4.1.1)。

    校验失败一律抛 `CriteriaError` —— 调用方转成退出码 2。
    **绝不降级成「无违规」**:参数缺失或非法的判据一旦被放行,就会永远通过。
    """
    required, optional = KIND_PARAMS.get(criterion.kind, (frozenset(), frozenset()))
    params = criterion.params
    allowed = required | optional | GLOBAL_PARAMS

    for key in sorted(params):
        if key not in allowed:
            raise CriteriaError(f"判据 {criterion.id} 含未知参数 {key}")
    for key in sorted(required):
        if key not in params:
            raise CriteriaError(f"判据 {criterion.id} 缺少必填参数 {key}")

    scope = params.get("scope", SCOPE_DOC)
    if scope not in SUPPORTED_SCOPES:
        raise CriteriaError(
            f"判据 {criterion.id} 的 scope 不受支持: {scope!r} "
            f"(支持: {' / '.join(SUPPORTED_SCOPES)})"
        )
    if scope == SCOPE_REPO:
        for key in ("from_layer", "to_layer"):
            if key not in params:
                raise CriteriaError(
                    f"判据 {criterion.id} 使用 scope=repo,必须给出 {key} 参数"
                )

    for key in _STRING_PARAMS:
        if key in params:
            _require_nonempty_string(criterion, key, params[key])
    for key in _STRING_LIST_PARAMS:
        if key in params:
            _require_nonempty_str_list(criterion, key, params[key])
    if "min_count" in params:
        value = params["min_count"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise CriteriaError(
                f"判据 {criterion.id} 的参数 min_count 必须是整数: {value!r}"
            )
        if value < 1:
            raise CriteriaError(
                f"判据 {criterion.id} 的参数 min_count 必须 >= 1: {value!r}"
            )
    for key in ("regex", "pattern"):
        if key in params:
            _require_valid_regex(criterion, key, params[key])


def load_criteria(path: Path) -> list[Criterion]:
    """加载并校验判据文件。失败一律抛 `CriteriaError`。"""
    if not path.is_file():
        raise CriteriaError(f"判据文件不存在: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CriteriaError(f"判据文件不可读: {path} ({exc})") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CriteriaError(f"判据文件不是合法 JSON: {path} ({exc})") from exc

    if not isinstance(data, dict):
        raise CriteriaError(f"判据文件顶层必须是对象: {path}")
    if data.get("version") != 1:
        raise CriteriaError(f"判据文件 version 必须是 1: {path} (实际 {data.get('version')!r})")
    items = data.get("criteria")
    if not isinstance(items, list) or not items:
        raise CriteriaError(f"判据文件缺少非空 criteria 数组: {path}")

    criteria: list[Criterion] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CriteriaError(f"判据 #{index} 不是对象: {path}")
        missing = [
            key
            for key in ("id", "layer", "title", "kind", "params", "blocking", "source")
            if key not in item
        ]
        if missing:
            raise CriteriaError(f"判据 #{index} 缺少字段 {missing}: {path}")
        ident = str(item["id"])
        if not ID_RE.match(ident):
            raise CriteriaError(f"判据 id 不符合 ^[A-Z0-9-]+$: {ident!r} ({path})")
        if ident in seen:
            raise CriteriaError(f"判据 id 重复: {ident} ({path})")
        seen.add(ident)
        layer = str(item["layer"])
        if layer not in LAYERS:
            raise CriteriaError(f"判据 {ident} 的 layer 非法: {layer!r} (允许 {LAYERS})")
        kind = str(item["kind"])
        if kind not in KINDS:
            raise CriteriaError(f"判据 {ident} 的 kind 不在封闭词表内: {kind!r}")
        params = item["params"]
        if not isinstance(params, dict):
            raise CriteriaError(f"判据 {ident} 的 params 必须是对象")
        blocking = item["blocking"]
        if not isinstance(blocking, bool):
            raise CriteriaError(f"判据 {ident} 的 blocking 必须是布尔值")
        source = str(item["source"])
        if ":" not in source:
            raise CriteriaError(f"判据 {ident} 的 source 必须是 file:line 形式: {source!r}")
        scope = params.get("scope", SCOPE_DOC)
        if scope not in SUPPORTED_SCOPES:
            # 加载期就拒绝:一条 scope 写错的判据若被放行,会变成静默通过的假绿
            # —— 比缺这条判据更危险(契约 §4.1)。
            raise CriteriaError(
                f"判据 {ident} 的 scope 不受支持: {scope!r} (支持: {' / '.join(SUPPORTED_SCOPES)})"
            )
        if scope == SCOPE_REPO:
            for key in ("from_layer", "to_layer"):
                if key not in params:
                    raise CriteriaError(
                        f"判据 {ident} 使用 scope=repo,必须给出 {key} 参数"
                    )
        criterion = Criterion(
            id=ident,
            layer=layer,
            title=str(item["title"]),
            kind=kind,
            params=params,
            blocking=blocking,
            source=source,
        )
        # 逐 kind 校验参数(契约 §4.1.1):参数缺失/非法的判据必须在这里被拒,
        # 否则它会变成「永远通过」的假绿。
        validate_params(criterion)
        criteria.append(criterion)
    return criteria


# ---------------------------------------------------------------------- 求值上下文


@dataclass
class Document:
    """一次判据求值的输入:一个制品的若干文件。"""

    rel: str
    files: list[tuple[str, list[str]]]

    @classmethod
    def from_paths(cls, root: Path, entry: Path, files: tuple[Path, ...]) -> "Document":
        loaded: list[tuple[str, list[str]]] = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = path.resolve().relative_to(root.resolve()).as_posix() if _under(path, root) else path.name
            loaded.append((rel, text.split("\n")))
        return cls(rel=entry.name, files=loaded)

    @classmethod
    def from_repo(cls, root: Path, paths: list[Path]) -> "Document":
        """仓库级文档:按**字节**读,保留 CR。

        行尾类判据(`line_absent` 匹配 `\\r`)必须看见真实的 CR 字节;
        文本模式读会把 CRLF 归一成 LF,判据就会永远通过。
        """
        loaded: list[tuple[str, list[str]]] = []
        for path in paths:
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            text = raw.decode("utf-8", errors="replace")
            rel = path.resolve().relative_to(root.resolve()).as_posix() if _under(path, root) else path.name
            loaded.append((rel, text.split("\n")))
        return cls(rel="<repo>", files=loaded)

    def all_lines(self) -> list[tuple[str, int, str]]:
        """所有文件的行,带 (rel, 行号, 内容)。"""
        out: list[tuple[str, int, str]] = []
        for rel, lines in self.files:
            for number, line in enumerate(lines, 1):
                out.append((rel, number, line))
        return out

    def field(self, name: str) -> FieldHitValue | None:
        """按名取字段:引用块优先,其次表格块;命中第一个就返回。"""
        for rel, lines in self.files:
            hit = read_quote_fields(lines, rel).get(name)
            if hit is not None:
                return FieldHitValue(hit.value, hit.rel, hit.line)
        for rel, lines in self.files:
            hit = read_table_fields(lines, rel).get(name)
            if hit is not None:
                return FieldHitValue(hit.value, hit.rel, hit.line)
        return None

    def section_present(self, title: str) -> bool:
        for _rel, lines in self.files:
            for line in lines:
                match = _HEADING_RE.match(line)
                if match and title.strip() in match.group("title"):
                    return True
        return False

    def section_body(self, heading_key: str) -> list[tuple[str, int, str]]:
        """取 `## <heading_key>` 段的行(带 rel/行号)。"""
        for rel, lines in self.files:
            span = section_span(lines, heading_key)
            if span is None:
                continue
            return [(rel, number, lines[number - 1]) for number in range(span[0] + 1, span[1] + 1)]
        return []


@dataclass(frozen=True)
class FieldHitValue:
    value: str
    rel: str
    line: int


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


# ------------------------------------------------------------------------ kind 实现


def _violation(criterion: Criterion, message: str, rel: str = "", line: int = 0) -> Violation:
    return Violation(
        criterion_id=criterion.id,
        title=criterion.title,
        kind=criterion.kind,
        blocking=criterion.blocking,
        message=message,
        rel=rel,
        line=line,
    )


def _kind_section_exists(criterion: Criterion, doc: Document) -> list[Violation]:
    out: list[Violation] = []
    for title in criterion.params["sections"]:
        if not doc.section_present(str(title)):
            out.append(_violation(criterion, f"缺少必填段 `## {title}`"))
    return out


def _kind_line_present(criterion: Criterion, doc: Document) -> list[Violation]:
    pattern = str(criterion.params["regex"])
    regex = _compile(pattern, criterion)
    for rel, number, line in doc.all_lines():
        if regex.search(line):
            return []
    return [_violation(criterion, f"全文没有匹配 `{pattern}` 的行")]


def _kind_line_absent(criterion: Criterion, doc: Document) -> list[Violation]:
    pattern = str(criterion.params["regex"])
    regex = _compile(pattern, criterion)
    hits = [(rel, number, line) for rel, number, line in doc.all_lines() if regex.search(line)]
    if not hits:
        return []
    out = [
        _violation(criterion, f"出现禁止内容(匹配 `{pattern}`): {line.strip()}", rel, number)
        for rel, number, line in hits[:MAX_REPORTED_LINES]
    ]
    if len(hits) > MAX_REPORTED_LINES:
        out.append(_violation(criterion, f"另有 {len(hits) - MAX_REPORTED_LINES} 行匹配 `{pattern}`"))
    return out


def _kind_enum_field(criterion: Criterion, doc: Document) -> list[Violation]:
    field_name = str(criterion.params["field"])
    allowed = [str(value) for value in criterion.params["values"]]
    hit = doc.field(field_name)
    if hit is None or not hit.value:
        return [_violation(criterion, f"缺少字段 `{field_name}`")]
    token = hit.value.split()[0] if hit.value.split() else hit.value
    if token not in allowed:
        return [
            _violation(
                criterion,
                f"`{field_name}` 的值 `{hit.value}` 不在允许集合 {allowed}",
                hit.rel,
                hit.line,
            )
        ]
    return []


def _kind_date_format(criterion: Criterion, doc: Document) -> list[Violation]:
    field_name = str(criterion.params["field"])
    hit = doc.field(field_name)
    if hit is None or not hit.value:
        return [_violation(criterion, f"缺少字段 `{field_name}`")]
    if not DATE_VALUE_RE.match(hit.value):
        return [
            _violation(criterion, f"`{field_name}` 的值 `{hit.value}` 不是 YYYY-MM-DD", hit.rel, hit.line)
        ]
    return []


def _kind_checkbox_present(criterion: Criterion, doc: Document) -> list[Violation]:
    minimum = int(criterion.params["min_count"])
    count = sum(1 for _rel, _number, line in doc.all_lines() if CHECKBOX_RE.match(line))
    if count < minimum:
        return [_violation(criterion, f"复选框条目数 {count} < 要求的 {minimum}")]
    return []


def _kind_id_format(criterion: Criterion, doc: Document) -> list[Violation]:
    """ID 形态校验:凡是 `<prefix>-<后缀>` 的写法都要满足 pattern。

    这里扫描的是**全部** `<prefix>-xxx` 写法(含 `AC-1a` 这种非法形态),
    而不是只扫描「声明位」——否则形态非法的 ID 根本进不了检查,判据就成了永远通过。
    """
    prefix = str(criterion.params["prefix"])
    pattern = str(criterion.params["pattern"])
    out: list[Violation] = []
    seen: set[tuple[str, str, int]] = set()
    for ident, rel, number in _id_tokens(doc.files, prefix):
        key = (ident, rel, number)
        if key in seen:
            continue
        seen.add(key)
        if not id_pattern_matches(pattern, ident):
            out.append(_violation(criterion, f"ID `{ident}` 不符合 `{pattern}`", rel, number))
    return out


def _id_tokens(files: list[tuple[str, list[str]]], prefix: str) -> list[tuple[str, str, int]]:
    """扫描全部 `<prefix>-<后缀>` 写法(不限位置)。"""
    pattern = re.compile(r"\b" + re.escape(prefix) + r"-[0-9A-Za-z_]+\b")
    out: list[tuple[str, str, int]] = []
    for rel, lines in files:
        for number, line in enumerate(lines, 1):
            for token in pattern.findall(line):
                out.append((token, rel, number))
    return out


def _kind_id_unique(criterion: Criterion, doc: Document) -> list[Violation]:
    prefix = str(criterion.params["prefix"])
    seen: dict[str, list[tuple[str, int]]] = {}
    for ident, rel, number in declared_ids(doc.files, prefix):
        seen.setdefault(ident, []).append((rel, number))
    out: list[Violation] = []
    for ident, places in seen.items():
        if len(places) > 1:
            where = ", ".join(f"{rel}:{number}" for rel, number in places)
            out.append(_violation(criterion, f"ID `{ident}` 在文件内重复声明({where})", *places[0]))
    return out


def _kind_id_refs_resolve(criterion: Criterion, doc: Document) -> list[Violation]:
    """引用完整性:被引用的 ID 必须在本文件内被声明过。"""
    from_prefix = str(criterion.params["from_prefix"])
    to_prefix = str(criterion.params["to_prefix"])
    via_field = str(criterion.params["via_field"])

    declared_to = {ident for ident, _rel, _line in declared_ids(doc.files, to_prefix)}
    out: list[Violation] = []

    for rel, lines in doc.files:
        owner: str | None = None
        for number, line in enumerate(lines, 1):
            heading = _HEADING_RE.match(line)
            if heading:
                token = _ID_TOKEN_RE.search(heading.group("title"))
                owner = token.group(0) if token else None
                continue
            item = re.match(
                r"^\s*[-*+]\s*(?:\[[ xX]\]\s*)?(" + re.escape(from_prefix) + r"-\d+)\b", line
            )
            if item:
                owner = item.group(1)
                continue
            matched = field_match(line)
            if matched is None or matched[0] != via_field:
                continue
            if owner is None:
                out.append(
                    _violation(
                        criterion,
                        f"`**{via_field}**` 行没有对应的 `{from_prefix}-n` 声明",
                        rel,
                        number,
                    )
                )
            for token in referenced_ids(matched[1], to_prefix):
                if token not in declared_to:
                    out.append(
                        _violation(
                            criterion,
                            f"引用了不存在的 `{token}`(本文件未声明)",
                            rel,
                            number,
                        )
                    )
    return out


def _kind_count_min(criterion: Criterion, doc: Document) -> list[Violation]:
    pattern = str(criterion.params["regex"])
    minimum = int(criterion.params["min_count"])
    regex = _compile(pattern, criterion)
    count = sum(1 for _rel, _number, line in doc.all_lines() if regex.search(line))
    if count < minimum:
        return [_violation(criterion, f"匹配 `{pattern}` 的行数 {count} < 要求的 {minimum}")]
    return []


def _kind_no_placeholder(criterion: Criterion, doc: Document) -> list[Violation]:
    pattern = str(criterion.params.get("regex") or PLACEHOLDER_DEFAULT)
    regex = _compile(pattern, criterion)
    hits = [(rel, number, line) for rel, number, line in doc.all_lines() if regex.search(line)]
    if not hits:
        return []
    out = [
        _violation(criterion, f"残留模板占位符(匹配 `{pattern}`): {line.strip()}", rel, number)
        for rel, number, line in hits[:MAX_REPORTED_LINES]
    ]
    if len(hits) > MAX_REPORTED_LINES:
        out.append(_violation(criterion, f"另有 {len(hits) - MAX_REPORTED_LINES} 行残留占位符"))
    return out


def _kind_coverage_complete(criterion: Criterion, doc: Document) -> list[Violation]:
    """覆盖完整性:每个 `from_prefix` ID 至少被一个 `to_prefix` 经 `via_field` 声明覆盖。"""
    from_prefix = str(criterion.params["from_prefix"])
    to_prefix = str(criterion.params["to_prefix"])
    via_field = str(criterion.params["via_field"])

    declared_from = declared_ids(doc.files, from_prefix)
    if not declared_from:
        return [
            _violation(
                criterion,
                f"{from_prefix} 无场景覆盖: 未找到任何 `{from_prefix}-n` 定义, "
                f"无法证明任何 {from_prefix} 被 {to_prefix} 经 `**{via_field}**` 覆盖",
            )
        ]

    covered: dict[str, tuple[str, int]] = {}
    for rel, lines in doc.files:
        current: str | None = None
        for number, line in enumerate(lines, 1):
            heading = _HEADING_RE.match(line)
            if heading:
                token = _ID_TOKEN_RE.search(heading.group("title"))
                current = token.group(0) if token else None
                continue
            matched = field_match(line)
            if matched is None or matched[0] != via_field:
                continue
            owner = current
            if owner is None:
                owner = _nearest_declaration(lines, to_prefix, upto=number)
            if owner is None:
                continue
            for token in referenced_ids(matched[1], from_prefix):
                covered.setdefault(token, (rel, number))

    out: list[Violation] = []
    for ident, rel, number in declared_from:
        if ident not in covered:
            out.append(
                _violation(
                    criterion,
                    f"{ident} 无场景覆盖: 没有任何 {to_prefix} 经 `**{via_field}**` 声明覆盖它",
                    rel,
                    number,
                )
            )
    return out


_KIND_IMPL = {
    "section_exists": _kind_section_exists,
    "line_present": _kind_line_present,
    "line_absent": _kind_line_absent,
    "enum_field": _kind_enum_field,
    "date_format": _kind_date_format,
    "checkbox_present": _kind_checkbox_present,
    "id_format": _kind_id_format,
    "id_unique": _kind_id_unique,
    "id_refs_resolve": _kind_id_refs_resolve,
    "count_min": _kind_count_min,
    "no_placeholder": _kind_no_placeholder,
    "coverage_complete": _kind_coverage_complete,
}

_ID_TOKEN_RE = re.compile(r"\b[A-Z]{1,4}-\d+\b")


def _compile(pattern: str, criterion: Criterion) -> re.Pattern[str]:
    """编译判据里的正则。**非法正则一律抛 `CriteriaError`**。

    旧实现在这里吞掉 `re.error` 并返回 None,调用方再把 None 降级成「无违规」——
    那等于「一条正则写错的判据永远通过」。契约 §4.1.1 要求显式失败。
    """
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise CriteriaError(
            f"判据 {criterion.id} 的正则不是合法正则: {pattern!r} ({exc})"
        ) from exc


def _nearest_declaration(
    lines: list[str], prefix: str, upto: int | None = None
) -> str | None:
    """在 `lines` 中找最近(向上)的 `<prefix>-n` 声明。"""
    best: str | None = None
    limit = len(lines) if upto is None else upto
    for number in range(min(limit, len(lines))):
        line = lines[number]
        item = re.match(r"^\s*[-*+]\s*(?:\[[ xX]\]\s*)?(" + re.escape(prefix) + r"-\d+)\b", line)
        if item:
            best = item.group(1)
            continue
        if _HEADING_RE.match(line):
            token = _ID_TOKEN_RE.search(_HEADING_RE.match(line).group("title"))
            if token and token.group(0).startswith(prefix + "-"):
                best = token.group(0)
    return best


def evaluate(criteria: list[Criterion], doc: Document, layer: str) -> CriteriaResult:
    """对单个制品求值。`layer` 限定只跑该层的判据。

    只求值 **doc 范围**的判据。`scope="repo"` 的判据是跨层的,必须由
    `evaluate_repo()` 单独求值(见该函数与 `evaluate_layer()`)。
    """
    result = CriteriaResult(artifact=doc.rel, layer=layer)
    for criterion in criteria:
        if criterion.layer != layer:
            continue
        if _criterion_scope(criterion) == SCOPE_REPO:
            continue  # 跨层判据由 evaluate_repo() 求值
        violations = _evaluate_one(criterion, doc)
        _absorb(result, criterion, violations)
    return result


def _criterion_scope(criterion: Criterion) -> str:
    raw = criterion.params.get("scope")
    if raw is None:
        return SCOPE_DOC
    return str(raw).strip().lower()


def _evaluate_one(criterion: Criterion, doc: Document) -> list[Violation]:
    """求值单条 doc 范围判据。不支持的 scope 一律判失败(绝不静默通过)。"""
    # 先校验参数:参数缺失/非法的判据必须显式失败,不能因为「参数读不出来」
    # 就退化成「无违规」(契约 §4.1.1)。
    validate_params(criterion)
    scope = _criterion_scope(criterion)
    if scope != SCOPE_DOC:
        if scope == SCOPE_REPO:
            return [
                _violation(
                    criterion,
                    "缺少跨层求值上下文: scope=repo 的判据需要全仓制品集合",
                )
            ]
        return [
            _violation(
                criterion,
                f"不支持的 scope: {criterion.params.get('scope')!r}(支持: doc / repo)",
            )
        ]
    handler = _KIND_IMPL[criterion.kind]
    return handler(criterion, doc)


def _absorb(result: CriteriaResult, criterion: Criterion, violations: list[Violation]) -> None:
    if violations:
        result.claims.append(criterion.as_claim(False))
        for violation in violations:
            if violation.blocking:
                result.failures.append(violation)
            else:
                result.warnings.append(violation)
    else:
        result.claims.append(criterion.as_claim(True))


# ------------------------------------------------------------------- 跨层(scope=repo)


@dataclass(frozen=True)
class RepoDocument:
    """跨层求值用的一层制品:层名 + topic + 文档。"""

    layer: str
    topic: str
    doc: Document


def evaluate_repo(
    criteria: list[Criterion], layer: str, repo_docs: list[RepoDocument] | None
) -> CriteriaResult:
    """求值 `scope="repo"` 的判据(跨层覆盖不变式)。

    `repo_docs` 为 None ⇒ 无法求值 ⇒ 判为**失败**(fail-closed),绝不静默通过。
    """
    result = CriteriaResult(artifact="<repo>", layer=layer)
    for criterion in criteria:
        if criterion.layer != layer:
            continue
        scope = _criterion_scope(criterion)
        if scope == SCOPE_DOC:
            continue
        if scope != SCOPE_REPO:
            # 不支持的 scope 必须显式失败,不能因为「不是 repo 范围」就被跳过
            # —— 那会让一条写错参数的判据静默通过。
            _absorb(result, criterion, [_unsupported_scope(criterion)])
            continue
        violations = _evaluate_repo_one(criterion, repo_docs)
        _absorb(result, criterion, violations)
    return result


def _unsupported_scope(criterion: Criterion) -> Violation:
    return _violation(
        criterion,
        f"不支持的 scope: {criterion.params.get('scope')!r}(支持: doc / repo)",
    )



def _evaluate_repo_one(
    criterion: Criterion, repo_docs: list[RepoDocument] | None
) -> list[Violation]:
    validate_params(criterion)
    if repo_docs is None:
        return [_violation(criterion, "缺少跨层求值上下文: scope=repo 的判据需要全仓制品集合")]
    if criterion.kind != "coverage_complete":
        return [
            _violation(
                criterion,
                f"不支持的 scope: repo(只有 coverage_complete 支持跨层求值,当前 kind={criterion.kind})",
            )
        ]

    from_prefix = str(criterion.params["from_prefix"])
    to_prefix = str(criterion.params["to_prefix"])
    via_field = str(criterion.params["via_field"])
    from_layer = str(criterion.params.get("from_layer", ""))
    to_layer = str(criterion.params.get("to_layer", ""))
    if not from_layer or not to_layer:
        return [
            _violation(
                criterion,
                "scope=repo 的判据必须给出 from_layer 与 to_layer 参数",
            )
        ]

    from_docs = [item for item in repo_docs if item.layer == from_layer]
    to_docs = [item for item in repo_docs if item.layer == to_layer]

    if not to_docs:
        # 下游层还没有任何制品 ⇒ 这条跨层不变式还没有可求值的对象。
        # 按「缺下游层不算违规」的口径,空真通过(不产生违规,也不产生警告 ——
        # 警告会要求人工决定记录,那会把「还没建下游层」变成人工负担)。
        return []

    out: list[Violation] = []
    for item in from_docs:
        # 同一 topic 的下游制品才能覆盖上游的声明位(目录约定 §3.2:同 topic 同日期前缀)。
        candidates = [doc for doc in to_docs if doc.topic == item.topic]
        if not candidates and not item.topic:
            candidates = list(to_docs)
        covered = _repo_covered_ids(candidates, to_prefix, via_field, from_prefix)
        for ident, rel, line in declared_ids(item.doc.files, from_prefix):
            if ident in covered:
                continue
            message = (
                f"{ident} 无场景覆盖: 没有任何 {to_prefix} 经 `**{via_field}**` 声明覆盖它"
            )
            if not candidates:
                message += f"(同 topic 的 {to_layer} 制品不存在)"
            out.append(_violation(criterion, message, rel, line))
    return out


def _repo_covered_ids(
    to_docs: list[RepoDocument], to_prefix: str, via_field: str, from_prefix: str
) -> set[str]:
    """to 侧制品里经 `**via_field**` 声明覆盖的 from 侧 ID 集合。"""
    covered: set[str] = set()
    for item in to_docs:
        for rel, lines in item.doc.files:
            current: str | None = None
            for number, line in enumerate(lines, 1):
                heading = _HEADING_RE.match(line)
                if heading:
                    token = _ID_TOKEN_RE.search(heading.group("title"))
                    current = token.group(0) if token else None
                    continue
                matched = field_match(line)
                if matched is None or matched[0] != via_field:
                    continue
                owner = current
                if owner is None:
                    owner = _nearest_declaration(lines, to_prefix, upto=number)
                if owner is None:
                    continue
                for token in referenced_ids(matched[1], from_prefix):
                    covered.add(token)
    return covered


def evaluate_layer(
    criteria: list[Criterion],
    doc: Document,
    layer: str,
    repo_docs: list[RepoDocument] | None = None,
) -> CriteriaResult:
    """单制品求值 = doc 范围判据 + 该层的跨层判据(一次遍历,不重复报同一条)。"""
    result = CriteriaResult(artifact=doc.rel, layer=layer)
    for criterion in criteria:
        if criterion.layer != layer:
            continue
        scope = _criterion_scope(criterion)
        if scope == SCOPE_REPO:
            violations = _evaluate_repo_one(criterion, repo_docs)
        elif scope == SCOPE_DOC:
            violations = _evaluate_one(criterion, doc)
        else:
            violations = [_unsupported_scope(criterion)]
        _absorb(result, criterion, violations)
    return result
