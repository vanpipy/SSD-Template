#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check-traceability.py — 跨文件引用追溯校验(单进程 Python 端口)

与 `check-traceability.sh`(bash 原件)行为等价:
  - 同一套 CLI(--json / --root DIR / TARGET / --help;--stage 一律拒绝)
  - 同一套退出码(0=通过 1=违规 2=调用错误/环境错误)
  - 逐字节相同的 stdout(含 ANSI 颜色、JSON 单行、错误文案与顺序)

移植说明(语义对照、awk↔re 差异、路径呈现)见
`scripts/tests/fixtures/traceability-corpus.json` 的 rules 字段。

与原件的差别仅限实现方式:
  - 原件用 `$(...)` 命令替换 + 每行 grep/awk 子进程;本实现全程零 fork
  - 原件的路径是 Git Bash 的 MSYS 形式(`/c/...`、`/tmp/...`);本实现复刻该呈现
    (见 to_display/to_native),使 `--json` 的 root 字段与原件逐字节一致
"""

import os
import re
import sys

# 原件用 bash printf 输出 UTF-8 字节;本实现必须同样按 UTF-8 + LF 输出,
# 否则 Windows 默认的 GBK 控制台编码会让 '✗'/'⚠' 抛 UnicodeEncodeError,
# 且文本模式会把 \n 翻译成 \r\n(字节不等价)。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace', newline='\n')
    except (AttributeError, ValueError):  # pragma: no cover - 极老解释器
        pass

# --- 脚本自身路径(与原件 `SCRIPT_PATH=$0` 同义) ---
SCRIPT_PATH = sys.argv[0]
SCRIPT_DIR = os.path.dirname(os.path.realpath(SCRIPT_PATH))
DEFAULT_ROOT = os.path.dirname(SCRIPT_DIR)

# --- 端口自指口径 ---
# 端口一律用新身份自称: JSON 的 "script" 字段、--help 用法行、
# --stage 拒绝前缀都用 .py 口径, 不再指向集成阶段会被删除的 .sh。
# 差分器对两侧同时归一化 basename(见本仓差分口径的 IDENT),
# 因此身份切换不影响「归一化后逐字节相同」的判定。


# --- 路径呈现(Git Bash 语义) ---
# Git Bash 的 `pwd -P`:
#   - %TEMP% 下的路径呈现为 /tmp/...   (fstab: `none /tmp usertemp`)
#   - 其余盘符路径呈现为 /<盘符小写>/...  (fstab: `none / cygdrive`)
def _native_temp_dir():
    temp = os.environ.get('TEMP') or os.environ.get('TMP') or ''
    if re.match(r'^[A-Za-z]:[\\/]', temp):
        return os.path.normpath(temp)
    local = os.environ.get('LOCALAPPDATA') or ''
    if local and re.match(r'^[A-Za-z]:[\\/]', local):
        return os.path.normpath(os.path.join(local, 'Temp'))
    return None


def _display_prefixes():
    pairs = []
    t = _native_temp_dir()
    if t:
        pairs.append((os.path.realpath(t).replace('\\', '/').rstrip('/'), '/tmp'))
    return pairs


def to_display(native_path):
    """原生路径 → Git Bash 呈现形式。"""
    p = str(native_path).replace('\\', '/')
    for nat, disp in _display_prefixes():
        if p == nat:
            return disp
        if p.startswith(nat + '/'):
            return disp + p[len(nat):]
    m = re.match(r'^([A-Za-z]):(?:/(.*))?$', p)
    if m:
        return '/' + m.group(1).lower() + '/' + (m.group(2) or '')
    return p


def to_native(disp_path):
    """Git Bash 呈现形式 → 原生路径(仅用于文件 I/O)。"""
    p = str(disp_path)
    if os.name != 'nt':
        return p
    m = re.match(r'^/([A-Za-z])(?:/(.*))?$', p)
    if m:
        return m.group(1).upper() + ':\\' + (m.group(2) or '').replace('/', '\\')
    t = _native_temp_dir()
    if t and (p == '/tmp' or p.startswith('/tmp/')):
        rest = p[len('/tmp'):].lstrip('/')
        return os.path.join(t, *rest.split('/')) if rest else t
    return p


def gnu_basename(path, suffix=None):
    """GNU basename 语义(去掉结尾斜杠;可选去后缀)。"""
    p = str(path).rstrip('/')
    b = p.rsplit('/', 1)[-1] if '/' in p else p
    if suffix and b.endswith(suffix) and len(b) > len(suffix):
        b = b[:-len(suffix)]
    return b


def gnu_dirname(path):
    """GNU dirname 语义。"""
    p = str(path).rstrip('/')
    d = p.rsplit('/', 1)[0] if '/' in p else ''
    return d if d else '.'


# --- CLI ---
JSON = 0
ROOT_ARG = ""
TARGET = ""

args = sys.argv[1:]
i = 0
while i < len(args):
    a = args[i]
    if a == '--json':
        JSON = 1
    elif a == '--root':
        if len(args) - i < 2:
            sys.stderr.write('✗ --root 需要目录参数\n')
            sys.exit(2)
        ROOT_ARG = args[i + 1]
        i += 1
    elif a.startswith('--root='):
        ROOT_ARG = a[len('--root='):]
    elif a == '--stage' or a.startswith('--stage='):
        sys.stderr.write('%s: 本门禁与阶段无关;--stage 只对 scripts/check-md-schema.py 有效\n'
                         % SCRIPT_PATH)
        sys.exit(2)
    elif a == '--help' or a == '-h':
        sys.stdout.write('用法: %s [--json] [--root DIR] [TARGET]\n' % SCRIPT_PATH)
        sys.exit(0)
    elif a.startswith('-'):
        sys.stderr.write('✗ 未知参数: %s\n' % a)
        sys.exit(2)
    else:
        if TARGET == '':
            TARGET = a
        else:
            sys.stderr.write('✗ 只能指定一个 TARGET\n')
            sys.exit(2)
    i += 1

if not ROOT_ARG:
    ROOT_ARG = DEFAULT_ROOT
if not os.path.isdir(to_native(ROOT_ARG)):
    sys.stderr.write('✗ --root 目录不存在: %s\n' % ROOT_ARG)
    sys.exit(2)
ROOT = to_display(os.path.realpath(to_native(ROOT_ARG)))

# 相对 TARGET 一律按 ROOT 解析(与其余门禁脚本的 CLI 语义一致)
if TARGET:
    if not TARGET.startswith('/'):
        TARGET = ROOT + '/' + TARGET

NO_COLOR = os.environ.get('NO_COLOR', '0')
if NO_COLOR == '1':
    C_ERR = C_WARN = C_OK = C_DIM = C_RESET = ''
else:
    C_ERR = '\033[0;31m'
    C_WARN = '\033[0;33m'
    C_OK = '\033[0;32m'
    C_DIM = '\033[0;36m'
    C_RESET = '\033[0m'

ERRORS = []
WARNINGS = []
NOTES = []


def err(msg):
    ERRORS.append(msg)
    if not JSON:
        sys.stdout.write('%s✗%s %s\n' % (C_ERR, C_RESET, msg))


def warn(msg):
    WARNINGS.append(msg)
    if not JSON:
        sys.stdout.write('%s⚠%s %s\n' % (C_WARN, C_RESET, msg))


def note(msg):
    NOTES.append(msg)
    if not JSON:
        sys.stdout.write('%s·%s %s\n' % (C_DIM, C_RESET, msg))


def ok(msg):
    if not JSON:
        sys.stdout.write('%s✓%s %s\n' % (C_OK, C_RESET, msg))


def json_escape(s):
    """与原件 awk 版 json_escape 同序:反斜杠 → 引号 → 制表 → 回车 → 换行。"""
    out = s.replace('\\', '\\\\')
    out = out.replace('"', '\\"')
    out = out.replace('\t', '\\t')
    out = out.replace('\r', '\\r')
    out = out.replace('\n', '\\n')
    return out


def json_str_array(items):
    return '[' + ','.join('"%s"' % json_escape(it) for it in items) + ']'


# --- 常量(与原件逐字相同) ---
TOPIC_RE = r'^[a-z0-9]+(-[a-z0-9]+)*$'
DATE_RE = r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
DATETOPIC_RE = r'^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$'
LEDGER_ID_RE = r'^(PRD|TECH|TEST|PLAN)-[0-9]{8}-[0-9]{2}$'
REL_TYPE_RE = r'^(supersede|inherit|depend|shared|conflict|relate|split-from|merge-into)$'
NODE_PATH_RE = r'^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$'

# POSIX [[:space:]] 在 C locale 下 = 空格 \t \n \v \f \r
_WS = '[ \t\r\n\v\f]'


def _read_lines(path):
    """读文件为行列表(去掉末尾换行产生的空行,与 awk 的记录切分一致)。"""
    try:
        with open(to_native(path), 'r', encoding='utf-8', errors='replace', newline='') as f:
            data = f.read()
    except OSError:
        return []
    lines = data.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return lines


def _isfile(path):
    return os.path.isfile(to_native(path))


def _isdir(path):
    return os.path.isdir(to_native(path))


def _exists(path):
    return os.path.exists(to_native(path))


def _listdir_names(path):
    """目录条目名(不含隐藏项),按 C 序排序;目录不存在返回 None。"""
    nat = to_native(path)
    if not os.path.isdir(nat):
        return None
    names = []
    try:
        for entry in os.scandir(nat):
            if entry.name.startswith('.'):
                continue
            names.append(entry.name)
    except OSError:
        return []
    names.sort()
    return names


# --- 辅助(与原件同名函数语义一致) ---
def abs_norm(p):
    """路径规整(不依赖 GNU realpath --relative-to)。"""
    d = gnu_dirname(p)
    b = gnu_basename(p)
    nat = to_native(d)
    if os.path.isdir(nat):
        phys = to_display(os.path.realpath(nat))
        return phys + '/' + b
    return p


def rel_of(p):
    """仓内相对路径(相对 ROOT)。"""
    root = ROOT.rstrip('/') + '/'
    if p.startswith(root):
        return p[len(root):]
    return p


def extract_ids(prefix, path):
    """抽取标识:标识前不得紧邻字母数字(避免 PV-001 之类子串误匹配)。"""
    pat = re.compile(re.escape(prefix) + r'[0-9]+')
    found = set()
    for line in _read_lines(path):
        pos = 0
        while True:
            m = pat.search(line, pos)
            if not m:
                break
            pre = line[:m.start()]
            if pre == '' or re.search(r'[A-Za-z0-9]', pre) is None:
                found.add(m.group(0))
            pos = m.end()
    return sorted(found)


def state_of(path):
    """读取 `> **状态**: X`(容忍 `**状态**: X`)。"""
    for line in _read_lines(path):
        if re.match(r'^' + _WS + r'*>?' + _WS + r'*\*\*状态\*\*' + _WS + r'*[:：]?', line):
            val = line
            val = re.sub(r'^[^:：]*[:：]' + _WS + '*', '', val, count=1)
            val = re.sub(r'^' + _WS + r'*[|*`]+' + _WS + r'*', '', val)
            val = re.sub(r'' + _WS + r'*[|*`]+$', '', val)
            m = re.search(r'(Draft|Ready|Implemented|Deprecated)', val)
            if m:
                return m.group(0)
    return ''


def section_body(path, h):
    """`## <前缀>` 段内容。"""
    out = []
    insec = False
    seclevel = 2
    for line in _read_lines(path):
        if re.match(r'^#+' + _WS, line):
            lvl = len(re.match(r'^(#+)', line).group(1))
            if insec:
                if lvl <= seclevel:
                    break
                continue
            text = re.sub(r'^#+' + _WS + '+', '', line, count=1)
            if lvl == 2 and text.startswith(h):
                insec = True
                seclevel = 2
            continue
        if insec:
            out.append(line)
    return out


def _section_after_heading(lines, heading_re):
    """原件的两处 awk 段提取:标题行本身不计入,遇到同级标题即结束。"""
    out = []
    f = False
    for line in lines:
        if line.startswith('```'):
            f = not f
            continue
        if (not f) and re.match(heading_re, line):
            f = True
            continue
        if (not f) and f and re.match(r'^#{1,6}' + _WS, line):
            break
        if f:
            out.append(line)
    return out


# --- 制品发现(全深度扫描 + 形状判定) ---
PRD_ARTIFACTS = []
TD_DIRS = []
PLAN_FILES = []
TC_FILES = []
HAS_PRD_LAYER = 0
HAS_TD_LAYER = 0
HAS_PLAN_LAYER = 0
HAS_TC_LAYER = 0


def discover():
    global PRD_ARTIFACTS, TD_DIRS, PLAN_FILES, TC_FILES
    global HAS_PRD_LAYER, HAS_TD_LAYER, HAS_PLAN_LAYER, HAS_TC_LAYER

    names = _listdir_names(ROOT + '/prd')
    if names is not None:
        for dn in names:
            if not re.match(DATE_RE, dn):
                continue
            sub = _listdir_names(ROOT + '/prd/' + dn)
            if sub is None:
                continue
            for bn in sub:
                if not bn.endswith('.md'):
                    continue
                topic = gnu_basename(bn, '.md')
                if not re.match(TOPIC_RE, topic):
                    continue
                PRD_ARTIFACTS.append(ROOT + '/prd/' + dn + '/' + bn)
                HAS_PRD_LAYER = 1

    names = _listdir_names(ROOT + '/tech_design')
    if names is not None:
        for dn in names:
            if not re.match(DATETOPIC_RE, dn):
                continue
            if not _isdir(ROOT + '/tech_design/' + dn):
                continue
            TD_DIRS.append(ROOT + '/tech_design/' + dn + '/')
            HAS_TD_LAYER = 1

    names = _listdir_names(ROOT + '/plan')
    if names is not None:
        for dn in names:
            if not re.match(DATETOPIC_RE, dn):
                continue
            d = ROOT + '/plan/' + dn
            if not _isdir(d):
                continue
            sub = _listdir_names(d)
            if sub is None:
                continue
            for bn in sub:
                if not bn.endswith('.md'):
                    continue
                topic = gnu_basename(bn, '.md')
                if not re.match(TOPIC_RE, topic):
                    continue
                PLAN_FILES.append(d + '/' + bn)
                HAS_PLAN_LAYER = 1

    names = _listdir_names(ROOT + '/test_cases')
    if names is not None:
        for dn in names:
            if not re.match(DATE_RE, dn):
                continue
            sub = _listdir_names(ROOT + '/test_cases/' + dn)
            if sub is None:
                continue
            for bn in sub:
                if not bn.endswith('.md'):
                    continue
                topic = gnu_basename(bn, '.md')
                if topic.endswith('-key-points'):
                    continue
                TC_FILES.append(ROOT + '/test_cases/' + dn + '/' + bn)
                HAS_TC_LAYER = 1


discover()

# --- 层容错(M11) ---
if HAS_PLAN_LAYER == 1 and HAS_TD_LAYER == 0:
    err('存在 Plan 制品但 tech_design 层没有任何 Tech Design — 下游层存在而上游层缺失(契约 M11)')
if HAS_TD_LAYER == 1 and HAS_PRD_LAYER == 0:
    warn('存在 Tech Design 但 prd 层没有 PRD — 按契约 M11 跳过 PRD↔Tech Design 闭环')
if HAS_TC_LAYER == 1 and HAS_TD_LAYER == 0 and HAS_PLAN_LAYER == 0:
    warn('存在 Test Cases 但没有上游 Tech Design/Plan — 按契约 M11 跳过上游闭环')

CHECKED = 0
LEDGER_STATES = ""     # "ID=STATE" 列表
DEPRECATED_NODES = ""   # 已 Deprecated 的节点标识(台账 ID 或仓内路径)
EDGE_A = ""
EDGE_REL = ""
EDGE_B = ""


def _fields(row):
    """awk -F'|' 的字段切分。"""
    return row.split('|')


def _trim(s):
    """gsub(/^[ \\t]+|[ \\t]+$/, \"\", s) 的等价。"""
    return re.sub(r'^[ \t]+|[ \t]+$', '', s)


def _ledger_states_lookup(node):
    """`grep \"^${node}=\"` 的等价(node 当正则;非法正则按未命中处理)。"""
    pat = node + '='
    try:
        rx = re.compile('^' + pat)
    except re.error:
        return None
    for token in LEDGER_STATES.split(' '):
        if not token:
            continue
        if rx.match(token):
            return token[len(node) + 1:]
    return None


def process_ledger(lf):
    """T6 台账 ID 格式与唯一性。"""
    global CHECKED, LEDGER_STATES, DEPRECATED_NODES
    body = _section_after_heading(_read_lines(lf), r'^##' + _WS + r'+PRD台账' + _WS + r'*$')
    if not body:
        return
    if not any(line.startswith('|') for line in body):
        return
    rows = [line for line in body if line.startswith('|')]

    id_col = 0
    st_col = 0
    for row in rows:
        fs = _fields(row)
        nf = len(fs)
        rid = 0
        rst = 0
        for idx in range(2, nf):
            c = _trim(fs[idx - 1])
            if c == 'ID':
                rid = idx
            elif c == '状态':
                rst = idx
        if rid:
            id_col = rid
            st_col = rst if rst else 7
            break
    if not id_col:
        warn('%s — 台账表未找到 `ID` 列, 跳过 ID 校验' % rel_of(lf))
        return

    CHECKED += 1
    seen = " "
    for row in rows:
        fs = _fields(row)
        lid = _trim(fs[id_col - 1]) if id_col - 1 < len(fs) else ''
        if lid == '' or lid == 'ID':
            continue
        if '[' in lid or ']' in lid:
            continue
        if re.match(r'^[?:+-]+$', lid):
            continue
        if not re.match(LEDGER_ID_RE, lid):
            err("%s — 台账 ID 格式非法: '%s' (期望 {PRD|TECH|TEST|PLAN}-{YYYYMMDD}-{NN})"
                % (rel_of(lf), lid))
            continue
        if ' ' + lid + ' ' in seen:
            err('%s — 台账 ID 重复: %s' % (rel_of(lf), lid))
            continue
        seen = seen + lid + ' '
        lst = _trim(fs[st_col - 1]) if st_col - 1 < len(fs) else ''
        LEDGER_STATES = LEDGER_STATES + ' ' + lid + '=' + lst
        if lst == 'Deprecated':
            DEPRECATED_NODES = DEPRECATED_NODES + ' ' + lid


def node_state(node):
    """节点状态解析:台账 ID 优先,其次仓内路径。"""
    s = _ledger_states_lookup(node)
    if s:
        return s
    if node.endswith('.md') and _isfile(ROOT + '/' + node):
        return state_of(ROOT + '/' + node)
    return None


def process_matrix(readme):
    """T7 关系边表 / T8 supersede 双向一致性。"""
    global CHECKED, EDGE_A, EDGE_REL, EDGE_B
    edges = _section_after_heading(_read_lines(readme), r'^###' + _WS + r'+关系边表' + _WS + r'*$')
    if not edges:
        return
    CHECKED += 1
    for row in [ln for ln in edges if ln.startswith('|')]:
        if not re.match(r'^\|' + _WS + r'*[0-9]+' + _WS + r'*\|', row):
            continue
        fs = _fields(row)
        a = _trim(fs[2]) if 2 < len(fs) else ''
        rel_type = _trim(fs[3]) if 3 < len(fs) else ''
        b = _trim(fs[4]) if 4 < len(fs) else ''
        EDGE_A = EDGE_A + ' ' + a
        EDGE_REL = EDGE_REL + ' ' + rel_type
        EDGE_B = EDGE_B + ' ' + b
        if not re.match(REL_TYPE_RE, rel_type):
            err("%s — 关系边类型非法: '%s' (应为 supersede/inherit/depend/shared/conflict/relate/split-from/merge-into)"
                % (rel_of(readme), rel_type))
        for node in (a, b):
            if node == '':
                continue
            if node.endswith('.md'):
                if re.match(NODE_PATH_RE, node) and not _exists(ROOT + '/' + node):
                    err('%s — 关系边节点路径不存在: %s' % (rel_of(readme), node))
            else:
                if _ledger_states_lookup(node) is None:
                    warn('%s — 关系边节点标识未在台账登记且不是仓内路径, 无法核对: %s'
                         % (rel_of(readme), node))
        if rel_type == 'supersede':
            st = node_state(b)
            if st:
                if st != 'Deprecated':
                    err('%s — supersede 边的被替代节点状态不是 Deprecated: %s (当前: %s)'
                        % (rel_of(readme), b, st))
            else:
                warn('%s — 无法解析被替代节点状态, 跳过 supersede 一致性核对: %s'
                     % (rel_of(readme), b))

    # T8 反向:已 Deprecated 的 PRD 必须有 supersede 边指向它
    for pf in PRD_ARTIFACTS:
        st = state_of(pf)
        if st != 'Deprecated':
            continue
        node = rel_of(pf)
        if node not in EDGE_B.split(' '):
            err('%s — 状态为 Deprecated, 但 README 关系边表中没有 supersede 边指向它' % rel_of(pf))


def process_test_registry(readme):
    """T10 README 用例登记表。"""
    seen = " "
    for row in [ln for ln in _read_lines(readme) if ln.startswith('|')]:
        m = re.search(r'TEST-[0-9]{8}-[0-9]{2}', row)
        if not m:
            continue
        tid = m.group(0)
        m2 = re.search(r'`[^`]+\.md`', row)
        if not m2:
            continue
        path = m2.group(0).replace('`', '')
        if ' ' + tid + ' ' in seen:
            err('%s — 用例登记 ID 重复: %s' % (rel_of(readme), tid))
        else:
            seen = seen + tid + ' '
        if not _exists(ROOT + '/' + path):
            err('%s — 用例登记路径不存在: %s' % (rel_of(readme), path))


def _changes_without_v(lines):
    """T4 正向:变更索引里没有 V 引用�� Change 标题行(逐行复刻原件 awk)。"""
    out = []
    in_chg = False
    prev = ''
    found = False
    for line in lines:
        if line.startswith('### Change #') or line.startswith('#### Change #'):
            if in_chg and not found:
                out.append(prev)
            in_chg = True
            prev = line
            found = False
            continue
        if line.startswith('##'):
            if in_chg and not found:
                out.append(prev)
            in_chg = False
        if in_chg and re.search(r'(^|[^A-Za-z])V-[0-9]+', line):
            found = True
    if in_chg and not found:
        out.append(prev)
    return out


def _v_section_has_change(lines, v):
    """T4 反向:V 段内是否出现 `Change #N`。"""
    h = '### ' + v + ':'
    p = False
    for line in lines:
        if line.startswith(h):
            p = True
            continue
        if p and line.startswith('### '):
            p = False
        if p and re.search(r'Change #[0-9]+', line):
            return True
    return False


def process_plan(pf):
    """T3 KD 闭环 / T2 V 闭环 / T4 Change↔V / T11 参考 Test Cases。"""
    global CHECKED
    rel = rel_of(pf)
    dir_ = gnu_dirname(pf)
    CHECKED += 1
    lines = _read_lines(pf)

    td_ref = ''
    m = re.search(r'\.\./\.\.?/tech_design/[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9_-]+',
                  '\n'.join(lines))
    if m:
        td_ref = m.group(0)
    td_rel = ''
    if td_ref:
        td_abs = abs_norm(dir_ + '/' + td_ref)
        td_rel = rel_of(td_abs)
        if not _isdir(ROOT + '/' + td_rel):
            td_rel = ''
    if not td_rel:
        if HAS_TD_LAYER == 1:
            err('%s — 未引用可解析的 Tech Design(`../../tech_design/{date}-{topic}/`); 上游层存在但引用缺失'
                % rel)
    else:
        kd_src = ''
        if _isfile(ROOT + '/' + td_rel + '/ards.md'):
            kd_src = ROOT + '/' + td_rel + '/ards.md'
        if not kd_src and _isfile(ROOT + '/' + td_rel + '/decisions.md'):
            kd_src = ROOT + '/' + td_rel + '/decisions.md'
        if kd_src:
            for kd in extract_ids('KD-', pf):
                if not re.search(r'^##' + _WS + '+' + re.escape(kd) + ':',
                                 '\n'.join(_read_lines(kd_src)), re.M):
                    err('%s — 引用 %s 但 %s 中没有 `## %s:` 定义' % (rel, kd, rel_of(kd_src), kd))
        else:
            warn('%s — Tech Design %s 既无 ards.md 也无 decisions.md, 跳过 KD 闭环' % (rel, td_rel))

    for v in extract_ids('V-', pf):
        if not re.search(r'^###' + _WS + '+' + re.escape(v) + ':', '\n'.join(lines), re.M):
            err('%s — 引用 %s 但同文件没有 `### %s:` 定义' % (rel, v, v))

    if re.search(r'^##' + _WS + r'+变更索引', '\n'.join(lines), re.M):
        for chg in _changes_without_v(lines):
            for word in chg.split():
                if word == '':
                    continue
                err('%s — %s 未引用任何 V-{n}(Change 段应有 `**验证**: V-{n}`)' % (rel, word))

        defined = set()
        for line in lines:
            mm = re.match(r'^###' + _WS + r'+V-[0-9]+:', line)
            if mm:
                vv = re.search(r'V-[0-9]+', mm.group(0))
                if vv:
                    defined.add(vv.group(0))
        for v in sorted(defined):
            if not _v_section_has_change(lines, v):
                err('%s — %s 已定义但无 Change 关联(Change 段 / 变更索引 / 对账行 / V 段自引均未覆盖)'
                    % (rel, v))

    refs = []
    for line in lines:
        if re.match(r'^' + _WS + r'*>?' + _WS + r'\*\*参考 Test Cases\*\*', line):
            refs.extend(mm.group(0).replace('`', '')
                        for mm in re.finditer(r'`[^`]+`', line))
    for r in ' '.join(refs).split():
        if r.startswith('test_cases/'):
            if HAS_TC_LAYER == 1 and not _exists(ROOT + '/' + r):
                err('%s — 参考 Test Cases 引用不存在: %s' % (rel, r))


def process_td(tdd):
    """T1 PRD 场景 → TD 场景映射覆盖。"""
    global CHECKED
    rel = rel_of(tdd)
    readme = tdd + '/README.md'
    if not _isfile(readme):
        return
    CHECKED += 1
    lines = _read_lines(readme)

    prd_ref = ''
    m = re.search(r'\.\./\.\./prd/[A-Za-z0-9._/-]+\.md', '\n'.join(lines))
    if m:
        prd_ref = m.group(0)
    if not prd_ref:
        if HAS_PRD_LAYER == 1:
            warn('%s/README.md — 未引用上游 PRD(`../../prd/{date}/{topic}.md`), 跳过 PRD↔Tech Design 闭环'
                 % rel)
        return
    prd_abs = abs_norm(tdd + '/' + prd_ref)
    prd_rel = rel_of(prd_abs)
    if not _isfile(ROOT + '/' + prd_rel):
        if HAS_PRD_LAYER == 1:
            err('%s/README.md — 引用的上游 PRD 不存在: %s' % (rel, prd_rel))
        return

    mapping_src = ''
    if _isfile(tdd + '/scenario-mapping.md'):
        mapping_src = tdd + '/scenario-mapping.md'
    if not mapping_src and _isfile(tdd + '/ards.md'):
        mapping_src = readme
    if not mapping_src:
        return
    row_re = r'^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|$'
    if mapping_src == readme:
        body = section_body(mapping_src, '场景映射')
        mapping_rows = sum(1 for ln in body if re.search(row_re, ln))
    else:
        mapping_rows = sum(1 for ln in _read_lines(mapping_src) if re.search(row_re, ln))
    prd_lines = _read_lines(ROOT + '/' + prd_rel)
    prd_count = sum(1 for ln in prd_lines
                    if re.search(r'^###' + _WS + r'*场景[:：]', ln))
    if mapping_rows < prd_count:
        err('%s — 场景映射表格行数 (%d) 少于 PRD 场景数 (%d)'
            % (rel_of(mapping_src), mapping_rows, prd_count))


def process_cascade_plan(pf):
    """T12 父 PRD / 父 TD Deprecated → Plan 应同步降级。"""
    rel = rel_of(pf)
    self_state = state_of(pf)
    lines = _read_lines(pf)
    text = '\n'.join(lines)
    m = re.search(r'\.\./\.\./prd/[A-Za-z0-9._/-]+\.md', text)
    if m:
        prd_abs = abs_norm(gnu_dirname(pf) + '/' + m.group(0))
        prd_rel = rel_of(prd_abs)
        if _isfile(ROOT + '/' + prd_rel):
            parent_state = state_of(ROOT + '/' + prd_rel)
            if parent_state == 'Deprecated' and self_state != 'Deprecated':
                err('%s — 父 PRD 已 Deprecated (%s), Plan 未同步降级 (当前: %s)'
                    % (rel, prd_rel, self_state if self_state else '未声明'))
    m = re.search(r'\.\./\.\.?/tech_design/[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9_-]+', text)
    if m:
        td_rel = 'tech_design/' + gnu_basename(m.group(0))
        if _isfile(ROOT + '/' + td_rel + '/README.md'):
            parent_state = state_of(ROOT + '/' + td_rel + '/README.md')
            if parent_state == 'Deprecated' and self_state != 'Deprecated':
                err('%s — 父 Tech Design 已 Deprecated (%s), Plan 未同步降级 (当前: %s)'
                    % (rel, td_rel, self_state if self_state else '未声明'))


def process_cascade_td(tdd):
    """T12 父 PRD Deprecated → Tech Design 应同步降级。"""
    rel = rel_of(tdd)
    readme = tdd + '/README.md'
    if not _isfile(readme):
        return
    self_state = state_of(readme)
    m = re.search(r'\.\./\.\./prd/[A-Za-z0-9._/-]+\.md', '\n'.join(_read_lines(readme)))
    if not m:
        return
    prd_abs = abs_norm(tdd + '/' + m.group(0))
    prd_rel = rel_of(prd_abs)
    if not _isfile(ROOT + '/' + prd_rel):
        return
    parent_state = state_of(ROOT + '/' + prd_rel)
    if parent_state == 'Deprecated' and self_state != 'Deprecated':
        err('%s/README.md — 父 PRD 已 Deprecated (%s), Tech Design 未同步降级 (当前: %s)'
            % (rel, prd_rel, self_state if self_state else '未声明'))


def process_testcase(tf):
    """T9 test_cases 元信息上游引用存在性。"""
    global CHECKED
    rel = rel_of(tf)
    CHECKED += 1
    refs = []
    for line in _read_lines(tf):
        if not line.startswith('|'):
            continue
        fs = _fields(line)
        key = _trim(fs[1]) if 1 < len(fs) else ''
        key = key.replace('*', '')
        if key in ('来源', '来源 Tech Design', '来源 Plan', 'Tech Design', 'Plan'):
            third = fs[2] if 2 < len(fs) else ''
            refs.extend(mm.group(0).replace('`', '')
                        for mm in re.finditer(r'`[^`]+`', third))
    for r in ' '.join(refs).split():
        if (r.startswith('prd/') or r.startswith('material/')
                or r.startswith('tech_design/') or r.startswith('plan/')):
            if not _exists(ROOT + '/' + r):
                err('%s — 元信息上游引用不存在: %s' % (rel, r))


def run_all():
    """全仓模式。"""
    # M6: 全仓没有任何规格产物 → 门禁无从校验, 退出码 1
    if (HAS_PRD_LAYER == 0 and HAS_TD_LAYER == 0
            and HAS_PLAN_LAYER == 0 and HAS_TC_LAYER == 0):
        err('本仓没有任何规格产物,门禁无从校验')
    ledger_files = []
    names = _listdir_names(ROOT + '/material')
    if names is not None:
        for dn in names:
            sub = _listdir_names(ROOT + '/material/' + dn)
            if sub is None:
                continue
            for bn in sub:
                if bn.endswith('.md'):
                    ledger_files.append(ROOT + '/material/' + dn + '/' + bn)
    names = _listdir_names(ROOT + '/prd')
    if names is not None:
        for dn in names:
            sub = _listdir_names(ROOT + '/prd/' + dn)
            if sub is None:
                continue
            for bn in sub:
                if bn.endswith('.md'):
                    ledger_files.append(ROOT + '/prd/' + dn + '/' + bn)
    if _isfile(ROOT + '/PRDS.md'):
        ledger_files.append(ROOT + '/PRDS.md')
    for lf in ledger_files:
        process_ledger(lf)
    for pf in PLAN_FILES:
        process_plan(pf)
    for tdd in TD_DIRS:
        process_td(tdd)
    for pf in PLAN_FILES:
        process_cascade_plan(pf)
    for tdd in TD_DIRS:
        process_cascade_td(tdd)
    for tf in TC_FILES:
        process_testcase(tf)
    if _isfile(ROOT + '/README.md'):
        process_matrix(ROOT + '/README.md')
        process_test_registry(ROOT + '/README.md')


if TARGET:
    if not _exists(TARGET):
        sys.stderr.write('✗ TARGET 不存在: %s\n' % TARGET)
        sys.exit(2)
    t_abs = abs_norm(TARGET)
    t_rel = rel_of(t_abs)
    if t_rel.startswith('prd/'):
        for tdd in TD_DIRS:
            m = re.search(r'\.\./\.\./prd/[A-Za-z0-9._/-]+\.md',
                          '\n'.join(_read_lines(tdd + '/README.md')))
            if not m:
                continue
            prd_abs = abs_norm(tdd + '/' + m.group(0))
            if rel_of(prd_abs) != t_rel:
                continue
            process_td(tdd)
            process_cascade_td(tdd)
    elif t_rel.startswith('tech_design/'):
        tdd_dir = gnu_dirname(t_abs)
        process_td(tdd_dir)
        process_cascade_td(tdd_dir)
    elif t_rel.startswith('plan/'):
        for pf in PLAN_FILES:
            if rel_of(pf) != t_rel:
                continue
            process_plan(pf)
            process_cascade_plan(pf)
    elif t_rel.startswith('test_cases/'):
        for tf in TC_FILES:
            if rel_of(tf) != t_rel:
                continue
            process_testcase(tf)
    else:
        sys.stderr.write('✗ TARGET 不在任何规格层内: %s\n' % t_rel)
        sys.exit(2)
else:
    run_all()

# --- 汇总 ---
ERRC = len(ERRORS)
WARNC = len(WARNINGS)
if ERRC > 0:
    STATUS = 'violation'
    EXIT = 1
else:
    STATUS = 'pass'
    EXIT = 0

if JSON == 1:
    sys.stdout.write(
        '{"script":"check-traceability.py","root":"%s","status":"%s","exit_code":%d,'
        '"error_count":%d,"warning_count":%d,"checked":%d,"errors":%s,"warnings":%s,"notes":%s}\n'
        % (json_escape(ROOT), STATUS, EXIT, ERRC, WARNC, CHECKED,
           json_str_array(ERRORS), json_str_array(WARNINGS), json_str_array(NOTES)))
else:
    if ERRC > 0:
        sys.stdout.write('✗ 追溯校验: %d 项违规\n' % ERRC)
    else:
        ok('追溯校验通过 (检查 %d 个制品)' % CHECKED)
    if WARNC > 0:
        sys.stdout.write('· %d 项提示\n' % WARNC)

sys.exit(EXIT)
