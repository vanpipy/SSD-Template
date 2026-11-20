#!/usr/bin/env python3
"""门禁产物的**每轮每臂归档** (gate_archive.py)

Stdlib only. 供 scripts/run-round.sh 与 scripts/measure.py 共用。

## 它守的是什么

`measure.py` 过去在**测量时刻**去读业务仓工作区里的
`<module>/target/surefire-reports/*.xml`。那个目录是**四个仓共享**的,
而且**跨轮次、跨臂**共享:

    12:23  B-01/ssd      门禁跑完  -> 留下 XML (全过)
    12:31  F-03/ssd      门禁跑完  -> 覆盖 XML (全过)
    12:45  F-06/control  门禁跑完  -> 留下 XML (含 1 个失败)
    12:49  全部 20 次 measure 开始 -> 读到的全是 F-06 的 XML

于是 B-01 / F-03 / F-04 三臂的 `D_gate_new` 都记成了 1,
而它们自己的门禁日志里明明是**通过**的。这不是理论风险,
它已经污染过一次 20 臂的完整演练。

根因有两条, 缺一不可:

1. **读取时刻晚于写入时刻**。门禁跑完到测量开始之间隔了十几分钟,
   期间其它臂的门禁又跑了, 把 XML 覆盖了。
2. **没有归属记录**。磁盘上的 XML 不知道自己属于哪一轮、哪一臂,
   所以无法自证, 只能相信「谁最后跑的就是谁的」。

## 修法

门禁**跑完立刻**把产物复制到**每轮每臂专属**的目录:

    docs/efficacy/gates/archives/<round>/<arm>/
        manifest.json            归属元数据 + 每个文件的 sha256
        surefire/<module>/TEST-*.xml    后端 surefire XML 副本
        vitest/<repo>/...                前端 vitest 产物副本 (若有)

`measure.py` 只从归档目录读, **不再**读业务仓工作区。
归档目录是**只读的证据**, 一次写成, 之后只被读。

## manifest schema

```json
{
  "version": "v1",
  "round_id": "F-06",
  "arm": "ssd",
  "captured_at": "2026-11-19T12:48:03+08:00",
  "gate_log": "docs/efficacy/gates/F-06-ssd.txt",
  "gate_log_sha256": "<64 hex>",
  "repos": [
    {
      "alias": "B",
      "command": "mvn -o -fae -Dmaven.test.failure.ignore=true test -pl X -am",
      "exit_code": 0,
      "build_status": "SUCCESS",
      "scope": "busyming-merchandising-service",
      "files": [
        {"path": "surefire/busyming-merchandising-service/TEST-io.busyming.FooTest.xml",
         "sha256": "<64 hex>", "bytes": 12345}
      ],
      "file_count": 1,
      "failure_count": 3
    }
  ]
}
```

`build_status` 取值:

| 值 | 含义 |
|---|---|
| `SUCCESS` | 构建成功 |
| `TEST_FAILURE` | 构建成功但有测试失败 (正常现象, 计入 `D`) |
| `BUILD_FAILURE` | **构建/编译失败**。测试可能根本没跑, 失败集会**假性缩小** |
| `UNKNOWN` | 日志里没有 BUILD 标记 |

`BUILD_FAILURE` 必须显式存在: 编译失败时 surefire **不产出** XML,
于是失败集变小, `D` 反而变小 —— 方向完全相反。
`measure.py` 靠这个字段把「构建失败」显式记成 delta。

## 为什么归档不进冻结集

归档是**实验进行中**产生的观测记录, 与 `rounds/` 同性质:
每轮每臂一份, 内容取决于那一臂跑了什么, 冻结时**还不存在**。
它进 `.gitignore`, 不进冻结提交。

但**归档器本身** (`scripts/gate_archive.py`) 进冻结集:
它是「怎么归档」的约定, 属于尺子的一部分。
"""
import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# manifest 版本。改动 schema 时必须递增, 并同步 FORMULA.md。
MANIFEST_VERSION = "v1"

# manifest 文件名
MANIFEST_NAME = "manifest.json"

# 归档根目录相对路径 (相对规格仓根)
ARCHIVE_SUBDIR = os.path.join("docs", "efficacy", "gates", "archives")

# 后端 surefire XML 的来源模式, 相对后端仓根
SUREFIRE_GLOB = os.path.join("busyming-merchandising-*",
                             "target", "surefire-reports", "TEST-*.xml")

# --- 门禁日志里的构建状态标记 ---------------------------------------------

RE_BUILD_SUCCESS = "BUILD SUCCESS"
RE_BUILD_FAILURE = "BUILD FAILURE"
RE_COMPILATION_ERROR = "COMPILATION ERROR"
RE_EXIT_CODE = "EXIT="

# 门禁日志里用于判定「有测试失败」的标记。
RE_FAILURE_MARKER = "<<< FAILURE!"
RE_ERROR_MARKER = "[ERROR]"


class LogSummary:
    """门禁日志的**流式摘要**。

    为什么需要它: 门禁日志可以到几十 MB (后端全量 `mvn test` 约 72 MB),
    逐行 `+=` 拼字符串是**平方级**的 —— 5 千行 0.2 秒, 8 万行 179 秒,
    50 万行要两小时。而 `write_archive` 真正需要的只有三样:
    构建状态标记、退出码、是否有测试失败。所以这里只保留**结论**,
    不保留正文。

    内存占用与日志长度**无关**, 这是它替代全文拼接的关键。
    """

    __slots__ = ("has_build_success", "has_build_failure",
                 "has_compilation_error", "has_failure_marker",
                 "has_error_marker", "exit_code")

    def __init__(self):
        self.has_build_success = False
        self.has_build_failure = False
        self.has_compilation_error = False
        self.has_failure_marker = False
        self.has_error_marker = False
        self.exit_code = None

    def feed_line(self, line):
        """吸收一行日志, 只更新结论标志。"""
        if RE_BUILD_SUCCESS in line:
            self.has_build_success = True
        if RE_BUILD_FAILURE in line:
            self.has_build_failure = True
        if RE_COMPILATION_ERROR in line:
            self.has_compilation_error = True
        if RE_FAILURE_MARKER in line:
            self.has_failure_marker = True
        if RE_ERROR_MARKER in line:
            self.has_error_marker = True
        # 退出码只在行首匹配 (避免正文里出现 "EXIT=" 误判),
        # 且**取最后一次** —— maven 的退出码写在日志尾部。
        s = line.strip()
        if s.startswith(RE_EXIT_CODE):
            try:
                self.exit_code = int(s[len(RE_EXIT_CODE):].strip())
            except ValueError:
                pass

    def build_status(self):
        """按 `classify_build_status` 的同一套判定给出结论。"""
        if self.has_build_failure or self.has_compilation_error:
            return "BUILD_FAILURE"
        if self.has_build_success:
            if self.has_error_marker and self.has_failure_marker:
                return "TEST_FAILURE"
            return "SUCCESS"
        if self.exit_code is not None and self.exit_code != 0:
            return "BUILD_FAILURE"
        return "UNKNOWN"

    @property
    def text(self):
        """兼容旧接口: 拼一个只含标记的最小文本。

        `classify_build_status` 只做子串判定, 所以用标记拼出来的
        最小文本能得出**完全相同**的结论, 但内存占用是常数级。
        """
        parts = []
        if self.has_build_success:
            parts.append(RE_BUILD_SUCCESS)
        if self.has_build_failure:
            parts.append(RE_BUILD_FAILURE)
        if self.has_compilation_error:
            parts.append(RE_COMPILATION_ERROR)
        if self.has_error_marker:
            parts.append(RE_ERROR_MARKER)
        if self.has_failure_marker:
            parts.append(RE_FAILURE_MARKER)
        return "\n".join(parts)



def sha256_file(path):
    """文件的 sha256 (十六进制)。读不到返回 None。"""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def sha256_text(text):
    """字符串的 sha256 (按 UTF-8 字节)。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def classify_build_status(log_text, exit_code=None):
    """从门禁日志判定构建状态。

    返回 `SUCCESS` / `TEST_FAILURE` / `BUILD_FAILURE` / `UNKNOWN`。

    判定顺序有讲究:

    - 出现 `BUILD FAILURE` 或 `COMPILATION ERROR` → `BUILD_FAILURE`。
      **优先于**测试失败, 因为编译失败会让 surefire 少产出 XML,
      失败集**假性缩小**, 必须显式标出来。
    - 否则出现 `BUILD SUCCESS` → 有测试失败就是 `TEST_FAILURE`, 否则 `SUCCESS`。
    - 两者都没有 → `UNKNOWN` (日志被截断, 或门禁不是 maven)。
    """
    if RE_BUILD_FAILURE in log_text or RE_COMPILATION_ERROR in log_text:
        return "BUILD_FAILURE"
    if RE_BUILD_SUCCESS in log_text:
        # surefire 的失败行是 `[ERROR] <FQN>.<method> -- ... <<< FAILURE!`
        if RE_ERROR_MARKER in log_text and RE_FAILURE_MARKER in log_text:
            return "TEST_FAILURE"
        return "SUCCESS"
    if exit_code is None:
        # 没显式传退出码时, 自己从日志里解析 —— 否则同一份日志
        # 「带 exit_code 调用」与「不带调用」会得出**不同**结论。
        # 早期实现就有这个不一致, 流式摘要版是自洽的, 全文版要跟上。
        exit_code = parse_exit_code(log_text)
    if exit_code is not None and exit_code != 0:
        # 非零退出码但没有 BUILD 标记: 至少不是成功, 且不是已知形态。
        # 归入 BUILD_FAILURE 会让 measure 记 delta (保守, 方向安全);
        # 归入 UNKNOWN 则会被漏掉 (危险)。所以选保守的一侧。
        return "BUILD_FAILURE"
    return "UNKNOWN"


def parse_exit_code(log_text):
    """从门禁日志尾部解析 `EXIT=<code>` 行。找不到返回 None。"""
    for line in reversed(log_text.splitlines()):
        s = line.strip()
        if s.startswith(RE_EXIT_CODE):
            try:
                return int(s[len(RE_EXIT_CODE):].strip())
            except ValueError:
                return None
    return None


def archive_dir(root, round_id, arm, archive_root=None):
    """某轮某臂的归档目录绝对路径。

    `archive_root` 给了就用它 (归档根目录被显式指定时的情形),
    否则用 `root` + 固定子目录。两种口径必须**一致**, 否则
    「写归档」与「读归档」会落在不同地方 —— 那正是本次修复要根除的
    那类归属不明问题。
    """
    base = archive_root or root
    if archive_root:
        return os.path.join(base, round_id, arm)
    return os.path.join(base, ARCHIVE_SUBDIR, round_id, arm)


def _collect_surefire(repo_path):
    """收集后端仓的 surefire XML。

    返回 [(归档内相对路径, 源文件绝对路径), ...], 按路径排序 (稳定)。

    真实布局: `<repo>/<module>/target/surefire-reports/TEST-<FQN>.xml`,
    模块目录是仓库的**直接子目录** (busyming-merchandising-service 等)。
    归档内路径保留模块名, 不同模块的同名测试类不会互相覆盖。
    """
    import glob
    out = []
    pattern = os.path.join(repo_path, SUREFIRE_GLOB)
    for path in sorted(glob.glob(pattern)):
        base = os.path.basename(path)
        if not base.startswith("TEST-") or not base.endswith(".xml"):
            continue
        # 模块名 = 相对仓根的**第一段**。
        # 真实布局: <repo>/<module>/target/surefire-reports/TEST-<FQN>.xml
        # 从文件名往上数固定层数容易错 (target / surefire-reports / module),
        # 用相对路径的第一段则不会错。
        rel = os.path.relpath(path, repo_path)
        module = rel.split(os.sep)[0]
        rel_out = os.path.join("surefire", module, base)
        out.append((rel_out, path))
    return out


def _collect_vitest(repo_path):
    """收集前端仓的 vitest 产物。

    vitest 默认不产 XML, 只有配置了 `--reporter=junit` 之类才有。
    所以这里只收集**确实存在**的 junit XML, 没有就返回空列表 ——
    前端门的失败标识走**日志解析**, 不依赖 XML。
    """
    import glob
    out = []
    for pattern in (
        os.path.join(repo_path, "**", "junit*.xml"),
        os.path.join(repo_path, "**", "test-results*.xml"),
    ):
        for path in sorted(glob.glob(pattern, recursive=True)):
            if "node_modules" in path:
                continue
            rel = os.path.join("vitest", os.path.basename(repo_path),
                               os.path.relpath(path, repo_path))
            out.append((rel, path))
    return out


def write_archive(root, round_id, arm, gate_log_path, repo_entries,
                  overwrite=True, captured_at="", archive_root=None):
    """把一轮一臂的门禁产物归档。

    `repo_entries` 形如:

        [{"alias": "B", "repo_path": "/abs/path/to/backend",
          "command": "mvn ...", "scope": "busyming-merchandising-service",
          "summary": LogSummary()}]

    日志正文用 `LogSummary` (流式摘要) 代替: `write_archive` 只需要
    构建状态与退出码, 不需要正文。旧接口 `log_text` 仍然接受 (给测试用),
    但走全文字符串路径。

    `archive_root` 显式指定归档根目录 (默认 `root` + 固定子目录)。

    返回归档目录路径。已存在且 `overwrite=False` 时直接复用。
    """
    dest = archive_dir(root, round_id, arm, archive_root)
    if os.path.isdir(dest) and not overwrite:
        return dest

    # 先清空, 避免上一轮残留的文件混进本次归档。
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)

    repos = []
    for entry in repo_entries:
        alias = entry["alias"]
        repo_path = entry["repo_path"]
        summary = entry.get("summary")
        log_text = entry.get("log_text", "")
        if summary is None:
            # 兼容旧调用方: 传的是全文字符串。
            summary = LogSummary()
            for line in log_text.splitlines():
                summary.feed_line(line)
        exit_code = entry.get("exit_code")
        if exit_code is None:
            exit_code = summary.exit_code

        files = []
        if alias == "B":
            files = _collect_surefire(repo_path)
        else:
            files = _collect_vitest(repo_path)

        file_records = []
        for rel, src in files:
            dst = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                shutil.copy2(src, dst)
            except OSError:
                continue
            digest = sha256_file(dst)
            size = os.path.getsize(dst) if os.path.isfile(dst) else 0
            if digest is None:
                continue
            file_records.append({"path": rel.replace(os.sep, "/"),
                                 "sha256": digest, "bytes": size})

        repos.append({
            "alias": alias,
            "command": entry.get("command", ""),
            "scope": entry.get("scope", ""),
            "exit_code": exit_code,
            "build_status": summary.build_status(),
            "file_count": len(file_records),
            "failure_count": entry.get("failure_count", 0),
            "files": file_records,
        })

    manifest = {
        "version": MANIFEST_VERSION,
        "round_id": round_id,
        "arm": arm,
        "captured_at": captured_at,
        # 门禁日志路径。存**两个**:
        #   - `gate_log`: 相对仓库根, 便于阅读与搬迁;
        #   - `gate_log_abs`: 绝对路径, 让归档**自足** ——
        #     归档根目录与仓库根不同时 (演练、临时目录), 只靠相对路径
        #     还原不出日志在哪, 校验会误报「日志不存在」。
        "gate_log": os.path.relpath(gate_log_path, root).replace(os.sep, "/"),
        "gate_log_abs": os.path.abspath(gate_log_path),
        "gate_log_sha256": sha256_file(gate_log_path),
        "repos": repos,
    }
    with open(os.path.join(dest, MANIFEST_NAME), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return dest


def load_manifest(root, round_id, arm, archive_root=None):
    """读取某轮某臂的 manifest。缺失返回 None。"""
    path = os.path.join(archive_dir(root, round_id, arm, archive_root),
                        MANIFEST_NAME)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def verify_archive(root, round_id, arm, expected_gate_log=None,
                   archive_root=None):
    """校验归档的**完整性**。

    返回 (是否通过, 错误列表)。校验内容:

    1. manifest 存在且可解析;
    2. manifest 的 `round_id` / `arm` 与目录一致 (防止张冠李戴);
    3. manifest 记录的门禁日志存在, 且字节哈希与记录一致;
    4. manifest 列出的每个文件都存在, 且字节哈希与记录一致;
    5. 归档目录里**没有** manifest 未列出的多余文件 (防止事后塞文件)。

    任何一条不满足 → **硬失败**。

    为什么哈希必须对: 归档目录是可写的, 归档完之后如果有人改了
    里面的 XML (或者磁盘损坏), 差集法就会用一份**与记录不符**的失败集,
    而 `D` 照常出数。哈希是「归档之后没人动过它」的唯一机器证据。

    为什么还要拒多列 (第 5 条): 只查「列出的文件都对」是不够的。
    如果有人把别的臂的 XML 拷进来, 或者把某个失败测试的 XML 删掉再
    塞一个同名的新文件, 哈希那一条会抓到字节变化 —— 但如果塞进来的是
    一个 manifest 里根本**没有**的文件 (比如从另一轮归档拷的失败集),
    第 4 条永远不触发, 而第 5 条会触发。所以两条必须同时在。
    """
    errors = []
    dest = archive_dir(root, round_id, arm, archive_root)
    manifest = load_manifest(root, round_id, arm, archive_root)
    if manifest is None:
        return False, [f"归档 manifest 缺失或不可解析: {dest}/{MANIFEST_NAME}"]

    if manifest.get("round_id") != round_id:
        errors.append(f"manifest.round_id = {manifest.get('round_id')!r}, "
                      f"期望 {round_id!r}")
    if manifest.get("arm") != arm:
        errors.append(f"manifest.arm = {manifest.get('arm')!r}, "
                      f"期望 {arm!r}")

    gate_log_rel = manifest.get("gate_log")
    gate_log_abs = manifest.get("gate_log_abs")
    if not gate_log_abs:
        # 旧归档 (无 `gate_log_abs`) → 回落到相对仓库根解析。
        gate_log_abs = os.path.join(root, gate_log_rel) if gate_log_rel else ""
    if gate_log_abs:
        if not os.path.isfile(gate_log_abs):
            errors.append(f"归档指向的门禁日志不存在: {gate_log_rel or gate_log_abs}")
        else:
            actual = sha256_file(gate_log_abs)
            recorded = manifest.get("gate_log_sha256")
            if recorded and actual != recorded:
                errors.append(
                    f"门禁日志字节已变: {gate_log_rel or gate_log_abs} "
                    f"(记录 {recorded[:12]}, 实际 {str(actual)[:12]})")
    if expected_gate_log:
        expected_abs = os.path.abspath(expected_gate_log)
        if gate_log_abs and os.path.abspath(gate_log_abs) != expected_abs:
            errors.append(f"归档指向的门禁日志 {gate_log_rel or gate_log_abs} "
                          f"与本次测量用的 {expected_gate_log} 不是同一份")

    # 第 4 条: manifest 列出的文件必须都在, 且字节一致。
    listed = set()
    for repo in manifest.get("repos", []):
        alias = repo.get("alias", "?")
        for f in repo.get("files", []):
            rel = f.get("path", "")
            listed.add(rel)
            path = os.path.join(dest, rel.replace("/", os.sep))
            if not os.path.isfile(path):
                errors.append(f"[{alias}] 归档文件缺失: {rel}")
                continue
            actual = sha256_file(path)
            if actual != f.get("sha256"):
                errors.append(
                    f"[{alias}] 归档文件字节已变: {rel} "
                    f"(记录 {str(f.get('sha256'))[:12]}, 实际 {str(actual)[:12]})")

    # 第 5 条: 归档目录里不能有 manifest 未列出的多余文件。
    #
    # 只允许 manifest.json 本身 + 列出的那些。多一个文件就说明有人在
    # 归档之后动过目录, 而失败集正是从这些 XML 算出来的, 必须硬失败。
    errors.extend(_find_unlisted_files(dest, listed))

    return (not errors), errors


def _find_unlisted_files(dest, listed):
    """找出归档目录里 manifest 未列出的多余文件。

    返回错误列表。允许存在的只有 `manifest.json` 本身 (它不是被
    校验的数据文件, 而是被校验的清单)。

    目录本身不存在时返回空列表 —— 「目录缺失」由第 1/4 条负责报。
    """
    errors = []
    if not os.path.isdir(dest):
        return errors
    for dirpath, _dirnames, filenames in os.walk(dest):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, dest).replace(os.sep, "/")
            if rel == MANIFEST_NAME:
                continue
            if rel not in listed:
                errors.append(f"归档里有 manifest 未列出的多余文件: {rel}")
    return errors


def archived_surefire_ids(root, round_id, arm, archive_root=None):
    """从归档里解析后端 surefire 失败标识集合。

    返回 `pkg.Class#method` 集合。与 `gate_ids.parse_surefire_xml_ids`
    **同口径** (用 XML 文件名反推 FQN, 不用 `classname` 显示名),
    且直接复用 `gate_ids.parse_surefire_xml_files` 这段解析逻辑,
    保证与基线快照的标识口径**逐字一致**。

    只解析 **manifest 列出的** XML, 不扫目录。理由: 目录扫描会把
    manifest 之外的文件也算进去, 而那些文件按第 5 条校验就该被拒。
    两个口径必须一致: 「被计数的」就是「被校验的」。
    """
    import gate_ids as G

    manifest = load_manifest(root, round_id, arm, archive_root)
    if manifest is None:
        return set()
    dest = archive_dir(root, round_id, arm, archive_root)
    paths = []
    for repo in manifest.get("repos", []):
        for f in repo.get("files", []):
            rel = f.get("path", "")
            if not rel.startswith("surefire/") or not rel.endswith(".xml"):
                continue
            paths.append(os.path.join(dest, rel.replace("/", os.sep)))
    return G.parse_surefire_xml_files(sorted(paths))


def parse_spec_file(spec_path):
    """解析 run-round.sh 生成的归档规格文件。

    格式 (制表符分隔):

        ROOT\t<路径>
        GATE_LOG\t<路径>
        CAPTURED_AT\t<ISO8601>
        REPO\t<alias>\t<repo_path>\t<command>\t<scope>
        SEGMENT_BEGIN\t<alias>
        <该仓的日志正文, 可多行>
        SEGMENT_END\t<alias>

    返回 (root, gate_log, captured_at, repo_entries)。格式不对 → 抛 ValueError。

    **流式**: 逐行读, 不把日志正文留在内存里。每个仓只保留一个
    `LogSummary` (常数级), 所以规格文件有 50 万行也能在**秒级**解析完。
    早期实现用 `log_text += line` 逐行拼接, 那是平方级的 —— 8 万行就要
    179 秒, 50 万行要两小时, 门禁归档实际上**从未成功跑完过**。
    """
    root = gate_log = captured_at = ""
    repos = []
    by_alias = {}
    current = None
    with open(spec_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.startswith("SEGMENT_BEGIN\t"):
                alias = line.split("\t", 1)[1].strip()
                # REPO 行已经建好了条目, 这里只把日志摘要**挂**到它身上。
                # 不新建条目: 否则同一个仓会被数成两个。
                current = by_alias.get(alias)
                if current is None:
                    current = {"alias": alias, "repo_path": "", "command": "",
                               "scope": "", "summary": LogSummary()}
                    by_alias[alias] = current
                    repos.append(current)
                continue
            if line.startswith("SEGMENT_END\t"):
                if current is None:
                    raise ValueError("SEGMENT_END 没有对应的 SEGMENT_BEGIN")
                current = None
                continue
            if current is not None:
                current["summary"].feed_line(line)
                continue
            if not line.strip():
                continue
            parts = line.split("\t")
            key = parts[0]
            if key == "ROOT":
                root = parts[1].strip() if len(parts) > 1 else ""
            elif key == "GATE_LOG":
                gate_log = parts[1].strip() if len(parts) > 1 else ""
            elif key == "CAPTURED_AT":
                captured_at = parts[1].strip() if len(parts) > 1 else ""
            elif key == "REPO":
                if len(parts) < 5:
                    raise ValueError(f"REPO 行字段不足: {line}")
                alias = parts[1].strip()
                entry = {"alias": alias,
                         "repo_path": parts[2].strip(),
                         "command": parts[3].strip(),
                         "scope": parts[4].strip(),
                         "summary": LogSummary()}
                if alias in by_alias:
                    # 同一仓出现两次: 保留已有的, 只补空缺字段。
                    existing = by_alias[alias]
                    for k, v in entry.items():
                        if k == "summary":
                            continue
                        if not existing.get(k) and v:
                            existing[k] = v
                else:
                    by_alias[alias] = entry
                    repos.append(entry)
    if current is not None:
        raise ValueError("SEGMENT_BEGIN 没有对应的 SEGMENT_END")
    if not root or not gate_log:
        raise ValueError("规格文件缺少 ROOT 或 GATE_LOG")
    return root, gate_log, captured_at, repos


def main():
    """命令行入口。

    子命令:
      archive            按规格文件归档 (run-round.sh 走这条)
      verify             校验某轮某臂的归档完整性
      show               打印归档 manifest
      --print-archive-dir  打印归档根目录 (bash 侧用来对齐路径)
    """
    import argparse
    ap = argparse.ArgumentParser(description="门禁产物归档")
    sub = ap.add_subparsers(dest="cmd")

    ap_archive = sub.add_parser("archive", help="归档一轮一臂的门禁产物")
    ap_archive.add_argument("--root", default="")
    ap_archive.add_argument("--round-id", required=True)
    ap_archive.add_argument("--arm", required=True, choices=["ssd", "control"])
    ap_archive.add_argument("--gate-log", default="")
    ap_archive.add_argument("--spec", default="",
                             help="run-round.sh 生成的规格文件")
    ap_archive.add_argument("--repo", action="append", default=[],
                             help="仓标识与路径, 形如 B=/abs/path (可重复)")
    ap_archive.add_argument("--archive-dir", default="",
                             help="归档根目录 (默认 <root>/%s)" % ARCHIVE_SUBDIR)

    ap_verify = sub.add_parser("verify", help="校验归档完整性")
    ap_verify.add_argument("--root", required=True)
    ap_verify.add_argument("--round-id", required=True)
    ap_verify.add_argument("--arm", required=True)
    ap_verify.add_argument("--archive-dir", default="",
                            help="归档根目录 (默认 <root>/%s)" % ARCHIVE_SUBDIR)

    ap_show = sub.add_parser("show", help="打印归档 manifest")
    ap_show.add_argument("--root", required=True)
    ap_show.add_argument("--round-id", required=True)
    ap_show.add_argument("--arm", required=True)
    ap_show.add_argument("--archive-dir", default="",
                          help="归档根目录 (默认 <root>/%s)" % ARCHIVE_SUBDIR)

    # 顶层标志 (不带子命令时)
    ap.add_argument("--print-archive-dir", action="store_true")

    args = ap.parse_args()

    if args.print_archive_dir:
        print(os.path.abspath(os.path.join(
            os.getcwd(), ARCHIVE_SUBDIR)))
        return 0

    if args.cmd == "archive":
        root = args.root
        gate_log = args.gate_log
        captured_at = ""
        entries = []
        archive_root = args.archive_dir or None
        if args.spec:
            try:
                sroot, sgate, sat, entries = parse_spec_file(args.spec)
            except (OSError, ValueError) as exc:
                print(f"[FAIL] 规格文件解析失败: {exc}", file=sys.stderr)
                return 1
            root = root or sroot
            gate_log = gate_log or sgate
            captured_at = sat
        if not root or not gate_log:
            print("[FAIL] 需要 --root 与 --gate-log (或 --spec)", file=sys.stderr)
            return 1
        for spec in args.repo:
            if "=" not in spec:
                continue
            alias, path = spec.split("=", 1)
            entries.append({"alias": alias.strip(), "repo_path": path.strip()})

        dest = write_archive(root, args.round_id, args.arm, gate_log, entries,
                             captured_at=captured_at, archive_root=archive_root)
        print(f"[archive] {args.round_id}/{args.arm} -> {dest}")
        ok, errors = verify_archive(root, args.round_id, args.arm,
                                    archive_root=archive_root)
        if not ok:
            for e in errors:
                print(f"[FAIL] {e}", file=sys.stderr)
            return 1
        print("[archive] 完整性校验通过")
        return 0

    if args.cmd == "verify":
        ok, errors = verify_archive(args.root, args.round_id, args.arm,
                                    archive_root=args.archive_dir or None)
        if ok:
            print("[OK] 归档完整性校验通过")
            return 0
        for e in errors:
            print(f"[FAIL] {e}", file=sys.stderr)
        return 1

    if args.cmd == "show":
        m = load_manifest(args.root, args.round_id, args.arm,
                          archive_root=args.archive_dir or None)
        if m is None:
            print(f"[FAIL] manifest 缺失: {args.round_id}/{args.arm}",
                  file=sys.stderr)
            return 1
        print(json.dumps(m, ensure_ascii=False, indent=2))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
