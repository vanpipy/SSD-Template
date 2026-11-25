#!/usr/bin/env python3
"""check-md-schema.py — M3 / M4 / M5: 规格制品的必填段、状态枚举与阶段感知门禁

这是 MD Schema 门禁的**单进程 Python 端口**(取代原 bash 实现):
  * stdout 与原实现逐字节相同, 退出码相同(0=通过 1=存在违规 2=调用/环境错误);
  * 运行期**不 fork 任何子进程** —— 原件里的 awk / grep / sed / tr / cut 由等价的
    Python 实现取代。逐条对应关系见 .swarm/reports/port-check-md-schema.md。

权威规则(契约 §1):
  M3 状态枚举统一 4 值 Draft | Ready | Implemented | Deprecated
     PRD / Tech Design(README.md) / Plan 读 `> **状态**: X`;
     Test Case 读元信息表 `| **状态** | X |`; 值可带说明后缀(前缀匹配);
     非法值 = 违规; 缺状态行 = 违规(否则阶段无法判定)。
  M4 阶段感知(Stage-aware):
     Draft      → 必须有 `## 复审 (Review)` 段; 评审日期/评审人豁免; 写入者 = agent
     Ready      → 复审段 + 复审日期(YYYY-MM-DD) + 评审人非空; 写入者 = 人类评审者
     Implemented → 同 Ready; 写入者 = 人类
     Deprecated → 复审段; 日期/评审人豁免
     agent 的权限天花板 = Draft。
  M5 必填段:
     PRD   → ## 为什么 / ## 目标 / ## 场景 / ## 不在范围内 / ## 复审
              (## 链接 与 ## 变更记录 属人工维护, 不做机器校验)
     TD v4 → README.md / ards.md / apis.md / data-model.md,
              每个子文件必须有 `## 门禁清单` 与 `## 变更记录`
     TD v3 → README/decisions/data-model/api-contracts/scenario-mapping/quality
              6 个必填 + interactions.md 条件必填
     Plan → ## 变更清单 + `### Change #1:`/`#### Change #1:` + `### V-1:`
             + ## 跨文件引用对账 + ## 复审
             (v2 单段 Plan 不再是豁免, 一律判违规 —— 决策 D4)
     TestCase → 元信息 7 必填行 + ## 用例总览 + 状态枚举
             + Ready/Implemented 时必须有 `{topic}-key-points.md` 伴生

退出码(M1/M6): 0=通过 1=存在违规 2=调用/环境错误
  - 单文件模式: 有违规即退出 1(绝不把违规条数当退出码)
  - 层目录不存在 → 跳过该层
  - 全仓没有任何规格产物 → 退出 1, 消息「本仓没有任何规格产物,门禁无从校验」
"""

import os
import re
import sys

SCRIPT_PATH = sys.argv[0]

USAGE = """用法: python scripts/check-md-schema.py [--json] [--root DIR] [--stage STAGE] [TARGET]

  --json         以 JSON 输出(供 CI 消费)
  --root DIR     仓根目录(默认: 本脚本所在目录的上一级)
  --stage STAGE  假定制品处于该阶段(draft|ready|implemented|deprecated)。
                 只允许**收紧**校验: 用比制品自身状态更宽松的阶段取值会报错,
                 不会变成绕过签署校验的开关。
                 不给该参数时按制品自身声明的状态判定(契约 M4 / A5)。
  TARGET         可选, 单个文件或目录(只校验它)
  --help         显示本帮助

退出码: 0=通过 1=存在违规 2=调用/环境错误
"""

# --- 常量(逐字对齐 bash 原件) ---
TOPIC_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
DATE_RE = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
DATETOPIC_RE = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$')
PLACEHOLDER_RE = re.compile(r'\{[A-Z][A-Z_-]+\}|\{[A-Z_-]+ [A-Z_-]+\}')
PLACEHOLDER_ANY_RE = re.compile(r'\{[a-zA-Z_-]+\}|\{[a-zA-Z_-]+ [a-zA-Z_-]+\}')
STATE_RE = re.compile(r'^(Draft|Ready|Implemented|Deprecated)')
# 状态块元数据的取值格式(实施契约 §3.1)
#   状态块 = 4 行固定顺序
#     > **状态**: Draft
#     > **状态主体**: agent:sddctl
#     > **状态时间**: 2026-11-22T23:30:00+08:00
#     > **状态依据**: criteria:PRD-READY-01,PRD-READY-02
#   Draft / Deprecated: 后三行可缺省(写了就必须合法)
#   Ready / Implemented: 后三行必填且非空(半写 = 违规)
STATE_SUBJECT_RE = re.compile(r'^(agent|human):[A-Za-z0-9._-]+$')
STATE_TIME_RE = re.compile(
    r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([+-][0-9]{2}:[0-9]{2}|Z)$'
)
STATE_BASIS_ITEM_RE = re.compile(r'^(criteria|external):[^ \t\n\v\f\r,]+$')
# criteria:<id>[,<id>…] 的延续项(省略前缀的裸 id)
STATE_BASIS_ID_RE = re.compile(r'^[A-Za-z0-9._-]+$')
# Deprecated 态的状态依据只允许 external:(实施契约 §5.2 —— 不允许 criteria:)
# 注意: 这个常量必须存在。未定义时 `grep -Eq ""` 匹配一切, 规则会静默变成 no-op。
STATE_BASIS_DECISION_RE = re.compile(r'^external:[^ \t\n\v\f\r,]+$')
# 复审方式的取值(实施契约 §3.2)
REVIEW_METHODS_RE = re.compile(r'^(自动判据|人工介入|外部事实)$')
# 复审结论的取值(实施契约 §3.2)
REVIEW_CONCLUSION_RE = re.compile(r'^(有条件通过|需返工|通过)$')

# --- 结构解析用的正则(对应 bash 里的 awk / grep 模式) ---
# [[:space:]] 在原件的 C.UTF-8 locale 下等价于 ASCII 空白集合。
WS = r' \t\n\v\f\r'
# `/^#+[[:space:]]/` —— 标题行
HEADING_RE = re.compile(r'^#+[' + WS + r']')
# `match($0, /^#+/); lvl = RLENGTH` —— 前导 '#' 的个数即标题层级
LEAD_HASH_RE = re.compile(r'^#+')
# `sub(/^#+[[:space:]]+/, "", line)` —— 去掉标记与空白后的标题文本
LEAD_HEADING_RE = re.compile(r'^#+[' + WS + r']+')
# `^[[:space:]]*>?[[:space:]]*\*\*状态\*\*[[:space:]]*[:：]`
STATE_LINE_RE = re.compile(
    r'^[' + WS + r']*>?[' + WS + r']*\*\*状态\*\*[' + WS + r']*[:：]'
)
# `sub(/^[^:：]*[:：][[:space:]]*/, "", val)` —— 取第一个冒号之后的值
VALUE_AFTER_COLON_RE = re.compile(r'^[^:：]*[:：][' + WS + r']*')
# `gsub(/^[[:space:]]*[|*`]+[[:space:]]*/, "", val)`
LEAD_JUNK_RE = re.compile(r'^[' + WS + r']*[|*`]+[' + WS + r']*')
# `gsub(/[[:space:]]*[|*`]+$/, "", val)`
TRAIL_JUNK_RE = re.compile(r'[' + WS + r']*[|*`]+$')
# `gsub(/^[[:space:]]*[|*`]+/, "", line)` / `gsub(/[[:space:]]*[|*`]+$/, "", line)`
LEAD_JUNK_NOSPACE_RE = re.compile(r'^[' + WS + r']*[|*`]+')
TRAIL_JUNK_NOSPACE_RE = re.compile(r'[' + WS + r']*[|*`]+$')
# `grep -q "^##[[:space:]]\{1,\}复审"` 等固定前缀的必填段
H2_PREFIX_RE = re.compile(r'^##[' + WS + r']+')

# --- 全局状态(对应 bash 里的全局变量) ---
JSON_MODE = False
ROOT = ''
ROOT_DISPLAY = ''
TARGET = ''
STAGE_OVERRIDE = ''
EFFECTIVE_STAGE = ''
STATE_TOKEN = ''
CHECKED = 0

ERRORS = []
WARNINGS = []
NOTES = []

C_OK = ''
C_ERR = ''
C_WARN = ''
C_DIM = ''
C_RESET = ''


# --- 输出 ---
def _write(stream, text):
    """按 UTF-8 字节写出(原件是 bash 的 printf, 字节流)。"""
    stream.write(text.encode('utf-8', 'surrogateescape'))


def _out(text):
    _write(sys.stdout.buffer, text)


def _err_out(text):
    _write(sys.stderr.buffer, text)


def err(msg):
    ERRORS.append(msg)
    if not JSON_MODE:
        _out('%s✗%s %s\n' % (C_ERR, C_RESET, msg))


def warn(msg):
    WARNINGS.append(msg)
    if not JSON_MODE:
        _out('%s⚠%s %s\n' % (C_WARN, C_RESET, msg))


def note(msg):
    NOTES.append(msg)
    if not JSON_MODE:
        _out('%s·%s %s\n' % (C_DIM, C_RESET, msg))


def ok(msg):
    if not JSON_MODE:
        _out('%s✓%s %s\n' % (C_OK, C_RESET, msg))


def json_escape(value):
    """对应 bash 的 json_escape: 反斜杠 → 双写, 引号/制表符/CR → 转义。"""
    return (value.replace('\\', '\\\\')
                 .replace('"', '\\"')
                 .replace('\t', '\\t')
                 .replace('\r', '\\r'))


def json_str_array(items):
    """对应 bash 的 json_str_array: ["a","b"], 空数组 → []。"""
    if not items:
        return '[]'
    return '[' + ','.join('"%s"' % json_escape(item) for item in items) + ']'


# --- 文件读取 ---
def strip_trailing_cr(line):
    """去掉行尾的 CR(等价于 bash 侧 MSYS awk 的文本模式读法)。

    bash 原件在 MSYS 下用 awk 以**文本模式**读文件,实际效果是**最多去掉 2 个
    行尾 CR**:C 运行时把 CRLF 翻成 LF(去掉 1 个 CR),awk 自身再去掉 1 个行尾
    CR。实测(bash 原件现场取值):
      行尾 1 个 CR → 剩 0;2 个 CR → 剩 0;3 个 CR → 剩 1。
    这里按同样的规则处理:行尾最多去掉 2 个 CR,行内其它位置的 CR 原样保留。
    """
    if line.endswith('\r\r'):
        return line[:-2]
    if line.endswith('\r'):
        return line[:-1]
    return line


def read_lines(path):
    """读文件并按 awk 的记录规则切分(末尾换行不产生空记录)。

    bash 的 awk 把 "a\\nb\\n" 切成 2 条记录("a" / "b"),把 "" 切成 0 条,
    把 "\\n" 切成 1 条空记录 —— 这里保持同样的语义。

    行尾 CRLF:按 `strip_trailing_cr` 的规则去掉行尾 CR(见该函数说明)。
    """
    with open(path, 'rb') as handle:
        data = handle.read()
    text = data.decode('utf-8', 'surrogateescape')
    if not text:
        return []
    if text.endswith('\n'):
        text = text[:-1]
    return [strip_trailing_cr(line) for line in text.split('\n')]


# --- 结构解析辅助(对应 bash 的 section_body / file_without_section / read_*) ---
def is_heading(line):
    return HEADING_RE.match(line) is not None


def heading_level(line):
    match = LEAD_HASH_RE.match(line)
    return match.end() if match else 0


def heading_text(line):
    return LEAD_HEADING_RE.sub('', line, count=1)


def section_body(lines, prefix):
    """取 `## <prefix>` 段的内容(到下一个同级或更高级标题为止)。

    对应 bash 的 section_body():段起始标题行本身不计入段体, 段内 lvl>2 的
    标题计入段体, 遇到 lvl<=2 的标题立即结束(该标题行不计入段体)。
    """
    body = []
    in_section = False
    section_level = 0
    for line in lines:
        if is_heading(line):
            if in_section:
                if heading_level(line) <= section_level:
                    break
                continue
            if heading_level(line) == 2 and heading_text(line).startswith(prefix):
                in_section = True
                section_level = 2
            continue
        if in_section:
            body.append(line)
    return body


def has_section_body(lines, prefix):
    """对应 bash 的 has_section_body():命令替换会去掉末尾换行, 空串即为空。"""
    return ''.join(line + '\n' for line in section_body(lines, prefix)).rstrip('\n') != ''


def file_without_section(lines, prefix):
    """去掉指定段体(用于占位符扫描: 复审段的占位符由阶段规则单独判定)。"""
    kept = []
    in_section = False
    section_level = 0
    for line in lines:
        if is_heading(line):
            if in_section:
                if heading_level(line) <= section_level:
                    in_section = False
                    kept.append(line)
                continue
            if heading_level(line) == 2 and heading_text(line).startswith(prefix):
                in_section = True
                section_level = 2
                continue
            kept.append(line)
            continue
        if not in_section:
            kept.append(line)
    return kept


def read_state(lines):
    """状态行取值(PRD / TD README / Plan): `> **状态**: X`。"""
    for line in lines:
        if STATE_LINE_RE.match(line):
            value = VALUE_AFTER_COLON_RE.sub('', line, count=1)
            value = LEAD_JUNK_RE.sub('', value, count=1)
            value = TRAIL_JUNK_RE.sub('', value, count=1)
            return value
    return ''


def read_meta(lines, key):
    """元信息表取值(TestCase): `| **字段** | 值 |`。"""
    for line in lines:
        if not line.startswith('|'):
            continue
        fields = line.split('|')
        field_key = fields[1].strip(' \t').replace('*', '') if len(fields) > 1 else ''
        value = fields[2].strip(' \t') if len(fields) > 2 else ''
        if field_key == key:
            return value
    return ''


def field_value(lines, key):
    """精确匹配 `**键名**` 取值(评审人 / 评审日期 / 评审结论 / 评审方式 …)。

    对应 bash 的 review_value / status_meta_value:行内没有 `**键名**` 跳过;
    没有冒号跳过;取值后仍含 `**键名**` 跳过;取第一条。
    """
    marker = '**%s**' % key
    for line in lines:
        if marker not in line:
            continue
        match = VALUE_AFTER_COLON_RE.match(line)
        if match is None:
            continue
        value = line[match.end():]
        value = LEAD_JUNK_NOSPACE_RE.sub('', value, count=1)
        value = TRAIL_JUNK_NOSPACE_RE.sub('', value, count=1)
        if marker in value:
            continue
        return value
    return ''


def is_placeholder_value(value):
    """对应 bash 的 is_placeholder_value:整串匹配 `^\\{.*\\}$`。"""
    return bool(re.match(r'^\{.*\}$', value))


def grep_any(lines, pattern):
    """对应 `grep -q <pattern>`:任一行匹配即真。"""
    return any(pattern.search(line) for line in lines)


# --- 阶段 ---
def stage_level(stage):
    """level 0 = draft / deprecated, level 1 = ready / implemented。"""
    lowered = stage.lower()
    if lowered in ('draft', 'deprecated'):
        return 0
    if lowered in ('ready', 'implemented'):
        return 1
    return -1


def canonical_stage(stage):
    lowered = stage.lower()
    if lowered == 'draft':
        return 'Draft'
    if lowered == 'deprecated':
        return 'Deprecated'
    if lowered == 'ready':
        return 'Ready'
    if lowered == 'implemented':
        return 'Implemented'
    return ''


def apply_stage_override(rel, declared):
    """--stage 覆盖(只允许收紧): 往下调会被报成违规。"""
    global EFFECTIVE_STAGE
    if not STAGE_OVERRIDE:
        EFFECTIVE_STAGE = declared
        return 0
    canon = canonical_stage(STAGE_OVERRIDE)
    declared_level = stage_level(declared)
    override_level = stage_level(canon)
    if override_level >= 0 and declared_level >= 0 and override_level < declared_level:
        err('%s — 用 --stage %s 放宽了已处于 %s 的制品(只允许收紧, 不允许放宽)'
            % (rel, STAGE_OVERRIDE, declared if declared else '未知'))
        EFFECTIVE_STAGE = declared
        return 1
    EFFECTIVE_STAGE = canon
    if canon != declared:
        note('%s — 按 --stage %s 假定阶段校验(制品自身声明: %s)'
             % (rel, STAGE_OVERRIDE, declared if declared else '未知'))
    return 0


# --- 状态校验 ---
def check_state_value(rel, raw):
    """状态枚举校验(M3): 结果写入全局 STATE_TOKEN; 非法时返回 1。"""
    global STATE_TOKEN
    STATE_TOKEN = ''
    if not raw:
        err('%s — 缺少状态行(应写 `> **状态**: Draft|Ready|Implemented|Deprecated`)' % rel)
        return 1
    if '|' in raw:
        err('%s — 状态值非法(仍是模板枚举, 未填写): %s' % (rel, raw))
        return 1
    token = raw.split()[0] if raw.split() else ''
    if not STATE_RE.match(token):
        err("%s — 状态值非法: '%s' (应为 Draft / Ready / Implemented / Deprecated)"
            % (rel, token))
        return 1
    STATE_TOKEN = token
    return 0


def check_status_meta(rel, lines, stage):
    """状态块元数据校验(契约 §3.1)。

    Draft / Deprecated → 状态主体 / 状态时间 / 状态依据 **可缺省**;
                       若写了就必须合法(半写的状态块是违规, 不是「没关系」)
    Ready / Implemented → 三行**必填且非空**。
    """
    stage = canonical_stage(stage)
    subject = field_value(lines, '状态主体')
    timestamp = field_value(lines, '状态时间')
    basis = field_value(lines, '状态依据')

    if subject and not STATE_SUBJECT_RE.match(subject):
        err("%s — 状态主体非法: '%s' (应为 agent:<id> 或 human:<handle>)" % (rel, subject))
    if timestamp and not STATE_TIME_RE.match(timestamp):
        err("%s — 状态时间不是带时区的 ISO-8601: '%s'" % (rel, timestamp))
    if basis:
        previous_prefix = ''
        for raw_item in basis.split(','):
            item = raw_item.strip(WS)
            if not item:
                continue
            if STATE_BASIS_ITEM_RE.match(item):
                previous_prefix = item.split(':', 1)[0]
                if stage == 'Deprecated' and previous_prefix == 'criteria':
                    err("%s — 状态为 Deprecated, 状态依据不允许 criteria: ('%s'), 只能用 external:<ref>"
                        % (rel, item))
            elif previous_prefix == 'criteria' and STATE_BASIS_ID_RE.match(item):
                # criteria:<id>[,<id>…] 的延续项 —— 前缀继承上一项(与判据正则一致)
                pass
            else:
                err("%s — 状态依据项非法: '%s' (应为 criteria:<id>[,<id>…] / external:<ref>)"
                    % (rel, item))

    if stage in ('Ready', 'Implemented'):
        if not subject:
            err('%s — 状态为 %s, 状态块缺少 `> **状态主体**: agent:<id>`' % (rel, stage))
        if not timestamp:
            err('%s — 状态为 %s, 状态块缺少 `> **状态时间**: <ISO-8601 带时区>`' % (rel, stage))
        if not basis:
            err('%s — 状态为 %s, 状态块缺少 `> **状态依据**: criteria:<id>[,external:<ref>]`'
                % (rel, stage))


def check_known_issues(rel, body):
    """「已知问题」行形状校验: 首个 token 必须是形如 PRD-XXX-01 的判据 id。"""
    issues = []
    marker = '**已知问题**'
    for line in body:
        if marker not in line:
            continue
        match = VALUE_AFTER_COLON_RE.match(line)
        if match is None:
            continue
        value = line[match.end():]
        value = LEAD_JUNK_NOSPACE_RE.sub('', value, count=1)
        value = TRAIL_JUNK_NOSPACE_RE.sub('', value, count=1)
        if marker in value:
            continue
        issues.append(value)
    for line in issues:
        if not line:
            continue
        token = line.split()[0] if line.split() else ''
        if not re.match(r'^[A-Z0-9-]+$', token):
            err("%s — `已知问题` 行的判据 id 非法: '%s' (应为形如 PRD-XXX-01 的大写字母/数字/连字符 id, 后接说明)"
                % (rel, line))


def check_review_block(rel, lines, stage):
    """阶段感知复审段校验(M4)。

    Draft / Deprecated : 复审段必须存在; 评审日期与评审人豁免; 签署行不应残留模板占位符
    Ready / Implemented : 复审段 + 评审日期(YYYY-MM-DD) + 评审人非空; 评审结论不得是占位符
    """
    stage = canonical_stage(stage)
    if not grep_any(lines, H2_PREFIX_RE.pattern and re.compile('^##[' + WS + r']+复审')):
        err('%s — 缺少必填段 `## 复审 (Review)`' % rel)
        return 1
    body = section_body(lines, '复审')
    sign_date = field_value(body, '评审日期')
    sign_reviewer = field_value(body, '评审人')
    if not sign_reviewer:
        sign_reviewer = field_value(body, '复审人')
    sign_conclusion = field_value(body, '评审结论')
    sign_method = field_value(body, '评审方式')

    if stage in ('Ready', 'Implemented'):
        date = sign_date
        if not date:
            alt_date = field_value(body, '复审日期')
            if re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$', alt_date):
                date = alt_date
        if not date:
            err('%s — 状态为 %s, 复审段缺少评审日期(应写 `> **评审日期**: YYYY-MM-DD`)'
                % (rel, stage))
        elif not re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$', date):
            err("%s — 状态为 %s, 评审日期不是 YYYY-MM-DD: '%s'" % (rel, stage, date))
        if not sign_reviewer:
            err('%s — 状态为 %s, 复审段缺少评审人(应写 `> **评审人**: {github-handle}`)'
                % (rel, stage))
        elif is_placeholder_value(sign_reviewer):
            err("%s — 状态为 %s, 评审人仍是占位符: '%s'" % (rel, stage, sign_reviewer))
        if not sign_conclusion:
            err('%s — 状态为 %s, 复审段缺少评审结论(应写 通过 / 有条件通过 / 需返工)'
                % (rel, stage))
        elif is_placeholder_value(sign_conclusion):
            err("%s — 状态为 %s, 评审结论仍是占位符: '%s'" % (rel, stage, sign_conclusion))
        elif not REVIEW_CONCLUSION_RE.match(sign_conclusion):
            err("%s — 状态为 %s, 评审结论取值非法: '%s' (应为 通过 / 有条件通过 / 需返工)"
                % (rel, stage, sign_conclusion))
        if not sign_method:
            err('%s — 状态为 %s, 复审段缺少评审方式(应写 `> **评审方式**: 自动判据 | 人工介入 | 外部事实`)'
                % (rel, stage))
        elif is_placeholder_value(sign_method):
            err("%s — 状态为 %s, 评审方式仍是占位符: '%s'" % (rel, stage, sign_method))
        elif not REVIEW_METHODS_RE.match(sign_method):
            err("%s — 状态为 %s, 评审方式取值非法: '%s' (应为 自动判据 / 人工介入 / 外部事实)"
                % (rel, stage, sign_method))
        # agent 署名不得配「人工介入」(实施契约 §3.2 / INV-3)
        if sign_reviewer.startswith('agent:') and sign_method == '人工介入':
            err("%s — 状态为 %s, 评审人为 agent 署名 ('%s') 时评审方式不得为「人工介入」"
                % (rel, stage, sign_reviewer))
    else:
        # Draft / Deprecated / 状态未知: 复审段存在即可, 日期与评审人豁免
        if is_placeholder_value(sign_date):
            warn('%s — 阶段 %s 下复审签署行 `评审日期` 仍是模板占位符(应为清空)'
                 % (rel, stage if stage else '未知'))
        if is_placeholder_value(sign_reviewer):
            warn('%s — 阶段 %s 下复审签署行 `评审人` 仍是模板占位符(应为清空)'
                 % (rel, stage if stage else '未知'))
        if is_placeholder_value(sign_conclusion):
            warn('%s — 阶段 %s 下复审签署行 `评审结论` 仍是模板占位符(应为清空)'
                 % (rel, stage if stage else '未知'))
    check_known_issues(rel, body)
    return 0


# --- 层校验 ---
def check_prd(lines, rel):
    """PRD 制品校验(M5 + M3 + M4)。"""
    global STATE_TOKEN
    raw = read_state(lines)
    if check_state_value(rel, raw):
        stage = ''
    else:
        stage = STATE_TOKEN
    apply_stage_override(rel, stage)
    check_status_meta(rel, lines, EFFECTIVE_STAGE)

    for sec in ('为什么', '目标', '场景', '不在范围内'):
        if not grep_any(lines, re.compile('^##[' + WS + r']+' + sec)):
            err('%s — 缺少必填段 `## %s`' % (rel, sec))

    body = section_body(lines, '目标')
    if has_section_body(lines, '目标') and not grep_any(body, re.compile(r'^- \[ \]')):
        err('%s — `## 目标` 段没有验证标准(`- [ ]` 勾选项)' % rel)

    body = section_body(lines, '场景')
    if has_section_body(lines, '场景') and not grep_any(body, re.compile(r'\*\*Given\*\*')):
        err('%s — `## 场景` 段没有 Given/When/Then(`**Given**`)' % rel)

    # 占位符(复审段除外: 那里的占位符由阶段规则判定)
    placeholders = [(index + 1, line)
                    for index, line in enumerate(file_without_section(lines, '复审'))
                    if PLACEHOLDER_RE.search(line)]
    if placeholders:
        err('%s — 仍含模板占位符:' % rel)
        for number, line in placeholders:
            _out('    %d:%s\n' % (number, line))

    check_review_block(rel, lines, EFFECTIVE_STAGE)


def check_td_dir(directory, rel):
    """Tech Design 目录校验(v4 / v3 两代)。"""
    global STATE_TOKEN
    if os.path.isfile(directory + '/ards.md') or os.path.isfile(directory + '/apis.md'):
        generation = 'v4'
    elif (os.path.isfile(directory + '/decisions.md')
          or os.path.isfile(directory + '/api-contracts.md')
          or os.path.isfile(directory + '/scenario-mapping.md')
          or os.path.isfile(directory + '/quality.md')):
        generation = 'v3'
    else:
        err('%s — 无法判定代际(既无 v4 的 ards.md/apis.md, 也无 v3 的 decisions.md 等)' % rel)
        return 1

    readme_path = directory + '/README.md'
    if not os.path.isfile(readme_path):
        err('%s — 缺少必填子文件: README.md' % rel)
        return 1

    readme_lines = read_lines(readme_path)
    raw = read_state(readme_lines)
    if check_state_value(rel + '/README.md', raw):
        stage = ''
    else:
        stage = STATE_TOKEN
    apply_stage_override(rel + '/README.md', stage)
    check_status_meta(rel + '/README.md', readme_lines, EFFECTIVE_STAGE)

    if generation == 'v4':
        for sub in ('README.md', 'ards.md', 'apis.md', 'data-model.md'):
            if not os.path.isfile(directory + '/' + sub):
                err('%s — v4 缺少必填子文件: %s' % (rel, sub))
    else:
        for sub in ('README.md', 'decisions.md', 'data-model.md',
                    'api-contracts.md', 'scenario-mapping.md', 'quality.md'):
            if not os.path.isfile(directory + '/' + sub):
                err('%s — v3 缺少必填子文件: %s' % (rel, sub))
        if not os.path.isfile(directory + '/interactions.md'):
            if not grep_any(readme_lines,
                            re.compile(r'interactions\.md.*(跳过|不适用|N/A)')):
                warn('%s — 缺少 interactions.md 且 README.md 未声明跳过(条件必填)' % rel)

    # 每个必填子文件都要有门禁清单与变更记录(M5)
    if generation == 'v4':
        required = ('README.md', 'ards.md', 'apis.md', 'data-model.md')
    else:
        required = ('README.md', 'decisions.md', 'data-model.md',
                    'api-contracts.md', 'scenario-mapping.md', 'quality.md')
    for sub in required:
        sub_path = directory + '/' + sub
        if not os.path.isfile(sub_path):
            continue
        sub_lines = read_lines(sub_path)
        if not grep_any(sub_lines, re.compile('^##[' + WS + r']+门禁清单')):
            err('%s/%s — 缺少 `## 门禁清单 (Completion Gate)` 段' % (rel, sub))
        if not grep_any(sub_lines, re.compile('^##[' + WS + r']+变更记录')):
            err('%s/%s — 缺少 `## 变更记录 (Change Log)` 段' % (rel, sub))

    if generation == 'v4':
        if not grep_any(readme_lines, re.compile('^##[' + WS + r']+场景映射')):
            err('%s/README.md — 缺少 `## 场景映射` 段' % rel)
        data_model_path = directory + '/data-model.md'
        if os.path.isfile(data_model_path):
            data_model_lines = read_lines(data_model_path)
            if (not grep_any(data_model_lines, re.compile('erDiagram'))
                    and not grep_any(data_model_lines,
                                     re.compile('无数据模型变更|不涉及数据模型'))):
                err('%s/data-model.md — 既无 ER 图(erDiagram)也无「无数据模型变更」声明' % rel)

    check_review_block(rel + '/README.md', readme_lines, EFFECTIVE_STAGE)


def check_plan(lines, rel):
    """Plan 制品校验(M5 + M3 + M4)。"""
    global STATE_TOKEN
    raw = read_state(lines)
    if check_state_value(rel, raw):
        stage = ''
    else:
        stage = STATE_TOKEN
    apply_stage_override(rel, stage)
    check_status_meta(rel, lines, EFFECTIVE_STAGE)

    if not grep_any(lines, re.compile('^##[' + WS + r']+变更清单')):
        err('%s — 缺少必填段 `## 变更清单 (Changes)`' % rel)
    if not grep_any(lines, re.compile('^##[' + WS + r']+跨文件引用对账')):
        err('%s — 缺少必填段 `## 跨文件引用对账`' % rel)

    if grep_any(lines, re.compile(r'^### Change #1:|^#### Change #1:')):
        pass
    elif grep_any(lines, re.compile(r'^### Change #[0-9]+:|^#### Change #[0-9]+:')):
        err('%s — 变更条目必须从 `### Change #1:` 开始编号' % rel)
    else:
        err('%s — v2 单段 Plan 不再被接受(决策 D4): 缺少 `### Change #1:` / `#### Change #1:`' % rel)

    if not grep_any(lines, re.compile(r'^### V-1:')):
        err('%s — 缺少 `### V-1:`(验证用例定义)' % rel)

    check_review_block(rel, lines, EFFECTIVE_STAGE)


def check_testcase(lines, rel, file_path):
    """Test Case 制品校验(M5 + M3 + M4)。"""
    global STATE_TOKEN
    base = os.path.basename(file_path)
    if base.endswith('.md'):
        base = base[:-len('.md')]
    directory = file_path.rsplit('/', 1)[0] if '/' in file_path else ''

    if base.endswith('-key-points'):
        for sec in ('业务背景', '核心测试点'):
            if not grep_any(lines, re.compile('^##[' + WS + r']+' + sec)):
                err('%s — 要点文档缺少 `## %s` 段' % (rel, sec))
        return 0

    topic = base[:-len('-smoke')] if base.endswith('-smoke') else base

    for field in ('主题', '业务产品', '目标平台', '来源', '生成日期', '状态', '用例总数'):
        value = read_meta(lines, field)
        if not value:
            err('%s — 元信息缺少必填行 `%s`' % (rel, field))
        elif PLACEHOLDER_ANY_RE.search(value):
            err('%s — 元信息 `%s` 仍为占位符: %s' % (rel, field, value))

    state_value = read_meta(lines, '状态')
    stage = ''
    if state_value:
        token = state_value.split()[0] if state_value.split() else ''
        if STATE_RE.match(token):
            stage = token
        else:
            err("%s — 状态非合法枚举前缀: '%s' (应为 Draft/Ready/Implemented/Deprecated)"
                % (rel, token))
    apply_stage_override(rel, stage)
    check_status_meta(rel, lines, EFFECTIVE_STAGE)

    if not grep_any(lines, re.compile('^##[' + WS + r']+用例总览')):
        err('%s — 缺少 `## 用例总览` 段' % rel)

    if EFFECTIVE_STAGE in ('Ready', 'Implemented'):
        if not os.path.isfile(directory + '/' + topic + '-key-points.md'):
            err('%s — 状态为 %s 但缺少伴生要点 `%s-key-points.md`'
                % (rel, EFFECTIVE_STAGE, topic))

    # 复审段(M4): schema/test_case.md 明确标注该段为机器必填段
    check_review_block(rel, lines, EFFECTIVE_STAGE)


# --- 制品发现 ---
def list_dirs(parent):
    """列出子目录并按 bash glob 的顺序排序(带尾斜杠的完整路径)。"""
    try:
        names = os.listdir(parent)
    except OSError:
        return []
    dirs = [parent.rstrip('/') + '/' + name + '/' for name in names
            if os.path.isdir(parent.rstrip('/') + '/' + name)]
    return sorted(dirs)


def list_md_files(parent):
    """列出 *.md 并按 bash glob 的顺序排序(路径前缀相同, 按名字比较)。"""
    try:
        names = os.listdir(parent)
    except OSError:
        return []
    files = [parent.rstrip('/') + '/' + name for name in names if name.endswith('.md')
             and os.path.isfile(parent.rstrip('/') + '/' + name)]
    return sorted(files)


def rel_path(path):
    """对应 bash 的 `${f#$ROOT/}`: 去掉 ROOT 前缀(不匹配时保留原样)。

    比较在「呈现层」上做(Windows 上是 MSYS 风格), 与原件的 POSIX 路径一致。
    """
    display = display_path(path)
    prefix = ROOT_DISPLAY.rstrip('/') + '/'
    if display.startswith(prefix):
        return display[len(prefix):]
    return display


def discover():
    """返回四层的制品列表(顺序与 bash 的 discover() 一致)。"""
    prd_artifacts = []
    td_artifacts = []
    plan_artifacts = []
    tc_artifacts = []

    if os.path.isdir(ROOT + '/prd'):
        for directory in list_dirs(ROOT + '/prd'):
            name = os.path.basename(directory.rstrip('/'))
            if not DATE_RE.match(name):
                continue
            for path in list_md_files(directory):
                base = os.path.basename(path)
                if base.endswith('.md'):
                    base = base[:-len('.md')]
                if not TOPIC_RE.match(base):
                    continue
                prd_artifacts.append(path)

    if os.path.isdir(ROOT + '/tech_design'):
        for directory in list_dirs(ROOT + '/tech_design'):
            name = os.path.basename(directory.rstrip('/'))
            if not DATETOPIC_RE.match(name):
                continue
            td_artifacts.append(directory)

    if os.path.isdir(ROOT + '/plan'):
        for directory in list_dirs(ROOT + '/plan'):
            name = os.path.basename(directory.rstrip('/'))
            if not DATETOPIC_RE.match(name):
                continue
            topic = '-'.join(name.split('-')[3:])
            path = directory + topic + '.md'
            if not os.path.isfile(path):
                continue
            plan_artifacts.append(path)

    if os.path.isdir(ROOT + '/test_cases'):
        for directory in list_dirs(ROOT + '/test_cases'):
            name = os.path.basename(directory.rstrip('/'))
            if not DATE_RE.match(name):
                continue
            for path in list_md_files(directory):
                stem = os.path.basename(path)
                if stem.endswith('.md'):
                    stem = stem[:-len('.md')]
                if stem.endswith('-key-points'):
                    stem = stem[:-len('-key-points')]
                elif stem.endswith('-smoke'):
                    stem = stem[:-len('-smoke')]
                if not TOPIC_RE.match(stem):
                    continue
                tc_artifacts.append(path)

    return prd_artifacts, td_artifacts, plan_artifacts, tc_artifacts


# --- 主流程 ---
def run_whole_repo():
    global CHECKED
    prd_artifacts, td_artifacts, plan_artifacts, tc_artifacts = discover()

    if prd_artifacts:
        for path in prd_artifacts:
            check_prd(read_lines(path), rel_path(path))
            CHECKED += 1
    else:
        note('层未启用或无制品(跳过 PRD 校验): prd/')

    if td_artifacts:
        for path in td_artifacts:
            rel = rel_path(path).rstrip('/')
            check_td_dir(path, rel)
            CHECKED += 1
    else:
        note('层未启用或无制品(跳过 Tech Design 校验): tech_design/')

    if plan_artifacts:
        for path in plan_artifacts:
            check_plan(read_lines(path), rel_path(path))
            CHECKED += 1
    else:
        note('层未启用或无制品(跳过 Plan 校验): plan/')

    if tc_artifacts:
        for path in tc_artifacts:
            check_testcase(read_lines(path), rel_path(path), path)
            CHECKED += 1
    else:
        note('层未启用或无制品(跳过 Test Case 校验): test_cases/')


def run_single_target(target):
    global CHECKED
    if os.path.isdir(target):
        rel = rel_path(target).rstrip('/')
        if rel.startswith('tech_design/'):
            check_td_dir(target, rel)
            CHECKED += 1
        elif rel in ('prd', 'tech_design', 'plan', 'test_cases', 'material'):
            _err_out('%s: 层根目录不能作为单文件校验目标: %s\n' % (SCRIPT_PATH, rel))
            return 2
        else:
            _err_out('%s: 无法识别的目录目标: %s\n' % (SCRIPT_PATH, rel))
            return 2
        return 0

    rel = rel_path(target)
    parts = rel.split('/')
    if len(parts) == 3 and parts[0] == 'prd':
        check_prd(read_lines(target), rel)
    elif len(parts) == 3 and parts[0] == 'tech_design':
        directory = target.rsplit('/', 1)[0]
        check_td_dir(directory, '/'.join(parts[:-1]))
    elif len(parts) == 3 and parts[0] == 'plan':
        check_plan(read_lines(target), rel)
    elif len(parts) == 3 and parts[0] == 'test_cases':
        check_testcase(read_lines(target), rel, target)
    else:
        _err_out('%s: 无法识别的文件类型(只支持 prd/ tech_design/ plan/ test_cases/ 下的制品): %s\n'
                 % (SCRIPT_PATH, rel))
        return 2
    CHECKED += 1
    return 0


def to_slash(path):
    """内部路径统一用 '/' 分隔(与 bash 的相对路径输出一致)。"""
    if os.sep != '/':
        path = path.replace(os.sep, '/')
    return path


def display_path(path):
    """路径呈现层: 复刻 bash 原件在同一环境下给出的路径形态。

    原件用 `cd -P ... && pwd -P` 取绝对路径, 在 Git Bash(MSYS)下的呈现规则是:
      - Windows 临时目录(环境变量 TEMP/TMP 指向的目录)→ /tmp
      - 盘符目录 → /<小写盘符>/<其余路径>
      - POSIX 环境 → 原样的绝对路径
    这里保持同一呈现, 使 stdout 与原件逐字节一致; 文件操作仍用原生路径。
    """
    path = to_slash(path)
    if os.sep != '/' and len(path) > 2 and path[1] == ':' and path[0].isalpha():
        temp = os.environ.get('TEMP') or os.environ.get('TMP')
        if temp:
            temp = to_slash(os.path.normpath(temp)).rstrip('/')
            if path.lower() == temp.lower():
                return '/tmp'
            if path.lower().startswith(temp.lower() + '/'):
                return '/tmp/' + path[len(temp) + 1:]
        path = '/' + path[0].lower() + path[2:]
    return path


def lower_ascii(value):
    """对应 bash 的 `tr 'A-Z' 'a-z'`(只处理 ASCII 字母)。"""
    return ''.join(chr(ord(char) + 32) if 'A' <= char <= 'Z' else char for char in value)


def default_root():
    """对应 bash 的 DEFAULT_ROOT=$(dirname -- "$SCRIPT_DIR")。"""
    script_dir = os.path.dirname(os.path.realpath(os.path.abspath(SCRIPT_PATH)))
    return os.path.dirname(script_dir)


def parse_args(argv):
    """对应 bash 的参数解析; 返回 None 表示正常继续, 返回整数表示退出码。"""
    global JSON_MODE, ROOT, TARGET, STAGE_OVERRIDE
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == '--json':
            JSON_MODE = True
        elif arg == '--root':
            index += 1
            if index >= len(argv):
                _err_out('%s: --root 需要参数\n' % SCRIPT_PATH)
                return 2
            ROOT = argv[index]
        elif arg.startswith('--root='):
            ROOT = arg[len('--root='):]
        elif arg == '--stage':
            index += 1
            if index >= len(argv):
                _err_out('%s: --stage 需要参数\n' % SCRIPT_PATH)
                return 2
            STAGE_OVERRIDE = lower_ascii(argv[index])
        elif arg.startswith('--stage='):
            STAGE_OVERRIDE = lower_ascii(arg[len('--stage='):])
        elif arg in ('--help', '-h'):
            _out(USAGE)
            return 0
        elif arg == '--':
            break
        elif arg.startswith('-'):
            _err_out('%s: 未知参数: %s\n' % (SCRIPT_PATH, arg))
            _err_out(USAGE)
            return 2
        else:
            if TARGET:
                _err_out('%s: 只接受一个 TARGET\n' % SCRIPT_PATH)
                return 2
            TARGET = arg
        index += 1
    return None


def main(argv):
    global ROOT, TARGET, ROOT_DISPLAY

    parsed = parse_args(argv)
    if parsed is not None:
        return parsed

    if STAGE_OVERRIDE:
        if STAGE_OVERRIDE not in ('draft', 'deprecated', 'ready', 'implemented'):
            _err_out('%s: --stage 取值非法: %s (可用: draft|ready|implemented|deprecated)\n'
                     % (SCRIPT_PATH, STAGE_OVERRIDE))
            return 2

    if not ROOT:
        ROOT = default_root()
    if not os.path.isdir(ROOT):
        _err_out('%s: 根目录不存在: %s\n' % (SCRIPT_PATH, ROOT))
        return 2
    ROOT = to_slash(os.path.realpath(ROOT))
    ROOT_DISPLAY = display_path(ROOT)

    if TARGET:
        target_arg = TARGET
        if not TARGET.startswith('/'):
            TARGET = ROOT + '/' + TARGET
        if not os.path.exists(TARGET):
            shown = target_arg if target_arg.startswith('/') else ROOT_DISPLAY + '/' + target_arg
            _err_out('%s: TARGET 不存在: %s\n' % (SCRIPT_PATH, shown))
            return 2

    global C_OK, C_ERR, C_WARN, C_DIM, C_RESET
    if os.environ.get('NO_COLOR') or not sys.stdout.isatty():
        C_OK = C_ERR = C_WARN = C_DIM = C_RESET = ''
    else:
        C_OK = '\033[32m'
        C_ERR = '\033[31m'
        C_WARN = '\033[33m'
        C_DIM = '\033[2m'
        C_RESET = '\033[0m'

    if TARGET:
        code = run_single_target(TARGET)
        if code != 0:
            return code
    else:
        run_whole_repo()
        if CHECKED == 0:
            err('本仓没有任何规格产物,门禁无从校验')

    if not ERRORS:
        ok('字段校验通过 (检查 %d 个制品)' % CHECKED)

    status = 'pass'
    code = 0
    if ERRORS:
        status = 'violation'
        code = 1

    if JSON_MODE:
        _out('{"script":"check-md-schema.py","root":"%s","status":"%s","exit_code":%d,'
             '"error_count":%d,"warning_count":%d,"checked":%d,"stage_override":"%s",'
             '"errors":%s,"warnings":%s,"notes":%s}\n'
             % (json_escape(ROOT_DISPLAY), status, code, len(ERRORS), len(WARNINGS), CHECKED,
                STAGE_OVERRIDE, json_str_array(ERRORS), json_str_array(WARNINGS),
                json_str_array(NOTES)))

    return code


if __name__ == '__main__':
    try:
        _exit_code = main(sys.argv[1:])
    finally:
        sys.stdout.buffer.flush()
        sys.stderr.buffer.flush()
    sys.exit(_exit_code)
