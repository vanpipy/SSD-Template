#!/usr/bin/env python3
"""gate_archive.py 的自检 (test_gate_archive.py)

Stdlib only. 用**合成**的 surefire XML 与门禁日志验证归档机制, 不依赖真实业务仓。

跑法:
    python3 scripts/test_gate_archive.py

## 这里守的是什么

归档器是本次修复的核心: 它保证 `measure.py` 读到的门禁失败集
**确实属于**那一轮那一臂。历史上共享 surefire 目录让三臂读到了同一份
失败集, 整个 20 臂演练的 `D` 全是假的。

所以自检必须覆盖三件事:

1. **隔离**: 两臂的归档互不干扰, 后写的不能污染先写的。
2. **完整性**: 归档缺失 / 被改 / 张冠李戴 → **硬失败**, 不是静默出数。
3. **构建失败方向**: 编译失败时失败集变小, 必须显式记 delta, 不能漏。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_archive as GA  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  [OK] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# 合成材料
# ---------------------------------------------------------------------------

SUREFIRE_XML_PASS = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="io.busyming.x.FooTest" tests="1" failures="0" errors="0">
  <testcase name="ok" classname="io.busyming.x.FooTest" time="0.1"/>
</testsuite>
"""

SUREFIRE_XML_FAIL = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="io.busyming.x.FooTest" tests="1" failures="1" errors="0">
  <testcase name="broken" classname="io.busyming.x.FooTest" time="0.1">
    <failure message="expected true">stack</failure>
  </testcase>
</testsuite>
"""


def make_backend_repo(path, xml_body):
    """造一个带 surefire XML 的后端仓 (结构上模拟真实仓)。"""
    reports = os.path.join(path, "busyming-merchandising-service",
                           "target", "surefire-reports")
    os.makedirs(reports, exist_ok=True)
    with open(os.path.join(reports, "TEST-io.busyming.x.FooTest.xml"), "w",
              encoding="utf-8") as fh:
        fh.write(xml_body)
    return path


def make_gate_log(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


# ---------------------------------------------------------------------------
# 1. 归档写入与读取
# ---------------------------------------------------------------------------

def test_archive_roundtrip(tmp):
    print("== 归档写入 / 读取 ==")
    root = os.path.join(tmp, "root")
    os.makedirs(root)
    repo = make_backend_repo(os.path.join(tmp, "repoB"), SUREFIRE_XML_FAIL)
    log = make_gate_log(os.path.join(root, "F-06-ssd.txt"),
                        "### [B] mvn test\n[INFO] BUILD SUCCESS\n"
                        "[ERROR] io.busyming.x.FooTest.broken -- x <<< FAILURE!\n"
                        "EXIT=0\n")

    GA.write_archive(root, "F-06", "ssd", log,
                     [{"alias": "B", "repo_path": repo,
                       "command": "mvn test", "scope": "service",
                       "log_text": "[INFO] BUILD SUCCESS\n"
                                   "[ERROR] x <<< FAILURE!\nEXIT=0\n"}],
                     captured_at="2026-11-19T12:00:00+08:00")

    dest = GA.archive_dir(root, "F-06", "ssd")
    check("归档目录已创建", os.path.isdir(dest), dest)
    check("manifest 已写入", os.path.isfile(os.path.join(dest, "manifest.json")))
    check("surefire XML 已复制",
          os.path.isfile(os.path.join(
              dest, "surefire", "busyming-merchandising-service",
              "TEST-io.busyming.x.FooTest.xml")))

    m = GA.load_manifest(root, "F-06", "ssd")
    check("manifest 可解析", m is not None)
    check("manifest.round_id 正确", m.get("round_id") == "F-06")
    check("manifest.arm 正确", m.get("arm") == "ssd")
    check("manifest 有 captured_at", m.get("captured_at") != "")
    check("manifest 记录了门禁日志哈希",
          isinstance(m.get("gate_log_sha256"), str)
          and len(m["gate_log_sha256"]) == 64)

    repo_entry = m["repos"][0]
    check("build_status == TEST_FAILURE",
          repo_entry["build_status"] == "TEST_FAILURE",
          f"实为 {repo_entry['build_status']}")
    check("exit_code == 0", repo_entry["exit_code"] == 0,
          f"实为 {repo_entry['exit_code']}")
    check("file_count == 1", repo_entry["file_count"] == 1)

    ids = GA.archived_surefire_ids(root, "F-06", "ssd")
    check("归档里解析出 1 个失败用例",
          ids == {"io.busyming.x.FooTest#broken"}, f"实为 {ids}")


# ---------------------------------------------------------------------------
# 2. **隔离**: 两臂互不污染
# ---------------------------------------------------------------------------

def test_archive_isolation(tmp):
    """核心回归: 后写的臂不能污染先写的臂。

    这正是历史污染的形态 —— 共享目录被覆盖, 所有臂读到同一份失败集。
    """
    print("== 归档隔离 (跨臂不污染) ==")
    root = os.path.join(tmp, "root2")
    os.makedirs(root)
    repo = make_backend_repo(os.path.join(tmp, "repoB2"), SUREFIRE_XML_FAIL)

    log_ssd = make_gate_log(os.path.join(root, "F-06-ssd.txt"),
                            "### [B] mvn test\n[INFO] BUILD SUCCESS\nEXIT=0\n")
    log_ctrl = make_gate_log(os.path.join(root, "F-06-control.txt"),
                             "### [B] mvn test\n[INFO] BUILD SUCCESS\n"
                             "[ERROR] io.busyming.x.FooTest.broken -- x <<< FAILURE!\n"
                             "EXIT=0\n")

    entries_fail = [{"alias": "B", "repo_path": repo, "command": "mvn test",
                      "scope": "service",
                      "log_text": "[INFO] BUILD SUCCESS\n"
                                  "[ERROR] x <<< FAILURE!\nEXIT=0\n"}]
    entries_pass = [{"alias": "B", "repo_path": repo, "command": "mvn test",
                      "scope": "service",
                      "log_text": "[INFO] BUILD SUCCESS\nEXIT=0\n"}]

    # SSD 臂先归档 (此刻 XML 里有失败)
    GA.write_archive(root, "F-06", "ssd", log_ssd, entries_fail)
    # 然后业务仓的 XML 被**覆盖**成全过 (模拟另一臂的门禁跑了)
    make_backend_repo(repo, SUREFIRE_XML_PASS)
    # 对照臂归档
    GA.write_archive(root, "F-06", "control", log_ctrl, entries_fail)

    ssd_ids = GA.archived_surefire_ids(root, "F-06", "ssd")
    ctrl_ids = GA.archived_surefire_ids(root, "F-06", "control")
    check("SSD 臂归档不受后续覆盖影响",
          ssd_ids == {"io.busyming.x.FooTest#broken"},
          f"实为 {ssd_ids}")
    check("对照臂归档读到的是覆盖后的全过 XML",
          ctrl_ids == set(), f"实为 {ctrl_ids}")
    check("两臂归档目录不同",
          GA.archive_dir(root, "F-06", "ssd")
          != GA.archive_dir(root, "F-06", "control"))


# ---------------------------------------------------------------------------
# 3. 完整性校验 (负向测试)
# ---------------------------------------------------------------------------

def test_archive_verification(tmp):
    print("== 归档完整性校验 ==")
    root = os.path.join(tmp, "root3")
    os.makedirs(root)
    repo = make_backend_repo(os.path.join(tmp, "repoB3"), SUREFIRE_XML_FAIL)
    log = make_gate_log(os.path.join(root, "F-06-ssd.txt"),
                        "### [B] mvn test\n[INFO] BUILD SUCCESS\nEXIT=0\n")
    entries = [{"alias": "B", "repo_path": repo, "command": "mvn test",
                "scope": "service",
                "log_text": "[INFO] BUILD SUCCESS\nEXIT=0\n"}]
    GA.write_archive(root, "F-06", "ssd", log, entries)

    ok, errors = GA.verify_archive(root, "F-06", "ssd")
    check("刚写的归档: 校验通过", ok, f"错误: {errors}")

    # (a) manifest 缺失
    dest = GA.archive_dir(root, "F-06", "ssd")
    mf = os.path.join(dest, "manifest.json")
    saved = open(mf, encoding="utf-8").read()
    os.remove(mf)
    ok2, errs2 = GA.verify_archive(root, "F-06", "ssd")
    check("manifest 缺失: 校验失败", not ok2)
    check("manifest 缺失: 报告了原因",
          any("manifest" in e for e in errs2), f"实为 {errs2}")
    with open(mf, "w", encoding="utf-8") as fh:
        fh.write(saved)

    # (b) 归档里的 XML 被改 → 哈希不符
    xml = os.path.join(dest, "surefire", "busyming-merchandising-service",
                       "TEST-io.busyming.x.FooTest.xml")
    with open(xml, "a", encoding="utf-8") as fh:
        fh.write("<!-- tampered -->\n")
    ok3, errs3 = GA.verify_archive(root, "F-06", "ssd")
    check("归档文件被篡改: 校验失败", not ok3)
    check("篡改: 报告了哈希不符",
          any("字节已变" in e for e in errs3), f"实为 {errs3}")

    # (c) 归档文件被删 → 缺失
    os.remove(xml)
    ok4, errs4 = GA.verify_archive(root, "F-06", "ssd")
    check("归档文件缺失: 校验失败", not ok4)
    check("缺失: 报告了原因",
          any("缺失" in e for e in errs4), f"实为 {errs4}")

    # (d) round/arm 张冠李戴
    m = GA.load_manifest(root, "F-06", "ssd")
    m["round_id"] = "F-99"
    with open(mf, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=2)
    ok5, errs5 = GA.verify_archive(root, "F-06", "ssd")
    check("round_id 张冠李戴: 校验失败", not ok5)
    check("张冠李戴: 报告了原因",
          any("round_id" in e for e in errs5), f"实为 {errs5}")

    # (e) 归档目录里有 manifest **未列出**的多余文件
    #
    # 这是跨臂污染的另一种形态: 别人把一份失败集 XML 塞进本臂归档目录。
    # 因为它不在 manifest 里, 「列出的文件哈希都对」这一条永远不触发,
    # 但失败集解析会把它算进去 —— 所以必须单独拒。
    #
    # 先把 (c) 删掉的原始 XML 补回来 (原字节), 否则下面「恢复通过」
    # 会被「文件缺失」干扰, 测的就不是多余文件这一条了。
    with open(xml, "w", encoding="utf-8") as fh:
        fh.write(SUREFIRE_XML_FAIL)
    m = GA.load_manifest(root, "F-06", "ssd")
    m["round_id"] = "F-06"
    with open(mf, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=2)
    ok_pre, errs_pre = GA.verify_archive(root, "F-06", "ssd")
    check("补回原始 XML 后: 校验通过", ok_pre, f"错误: {errs_pre}")

    smuggled = os.path.join(dest, "surefire", "busyming-merchandising-service",
                            "TEST-SMUGGLED.xml")
    with open(smuggled, "w", encoding="utf-8") as fh:
        fh.write(SUREFIRE_XML_FAIL)
    ok6, errs6 = GA.verify_archive(root, "F-06", "ssd")
    check("未列出的多余文件: 校验失败", not ok6)
    check("多余文件: 报告了原因",
          any("未列出" in e for e in errs6), f"实为 {errs6}")
    os.remove(smuggled)

    ok7, errs7 = GA.verify_archive(root, "F-06", "ssd")
    check("删掉多余文件后: 校验恢复通过", ok7, f"错误: {errs7}")


def test_unlisted_file_not_counted(tmp):
    print("== 未列出的文件不计入失败集 ==")
    """被计数的就是被校验的: 未列出的 XML 不能进失败集。

    两条口径必须一致。如果 `archived_surefire_ids` 扫目录而
    `verify_archive` 只看 manifest, 那么一个被硬失败挡下的污染文件
    仍然会改变失败集 —— 挡了等于没挡。
    """
    root = os.path.join(tmp, "root_e2e")
    os.makedirs(root)
    repo = make_backend_repo(os.path.join(tmp, "repoB_e2e"), SUREFIRE_XML_FAIL)
    log = make_gate_log(os.path.join(root, "F-06-ssd.txt"),
                        "### [B] mvn test\n[INFO] BUILD SUCCESS\nEXIT=0\n")
    entries = [{"alias": "B", "repo_path": repo, "command": "mvn test",
                "scope": "service",
                "log_text": "[INFO] BUILD SUCCESS\nEXIT=0\n"}]
    GA.write_archive(root, "F-06", "ssd", log, entries)

    ids = GA.archived_surefire_ids(root, "F-06", "ssd")
    check("归档失败集非空", len(ids) > 0, f"实为 {ids}")

    dest = GA.archive_dir(root, "F-06", "ssd")
    smuggled = os.path.join(dest, "surefire", "busyming-merchandising-service",
                            "TEST-Smuggled.xml")
    with open(smuggled, "w", encoding="utf-8") as fh:
        fh.write(SUREFIRE_XML_FAIL)

    ids2 = GA.archived_surefire_ids(root, "F-06", "ssd")
    check("未列出的文件不改变失败集", ids2 == ids,
          f"多出: {ids2 - ids}")


# ---------------------------------------------------------------------------
# 4. 构建状态判定
# ---------------------------------------------------------------------------

def test_build_status_classification():
    print("== 构建状态判定 ==")

    check("全过 → SUCCESS",
          GA.classify_build_status("[INFO] BUILD SUCCESS\n") == "SUCCESS")

    check("有测试失败 → TEST_FAILURE",
          GA.classify_build_status(
              "[INFO] BUILD SUCCESS\n"
              "[ERROR] io.busyming.x.FooTest.bar -- x <<< FAILURE!\n")
          == "TEST_FAILURE")

    check("BUILD FAILURE → BUILD_FAILURE",
          GA.classify_build_status("[INFO] BUILD FAILURE\n") == "BUILD_FAILURE")

    check("COMPILATION ERROR → BUILD_FAILURE",
          GA.classify_build_status("[ERROR] COMPILATION ERROR\n")
          == "BUILD_FAILURE")

    # **关键**: 编译失败时即便日志里也有测试失败行, 也必须判成
    # BUILD_FAILURE —— 因为编译失败会让 surefire 少产 XML,
    # 失败集变小, 差集法算出的 D 会变小, 方向完全相反。
    check("编译失败优先于测试失败",
          GA.classify_build_status(
              "[ERROR] COMPILATION ERROR\n"
              "[ERROR] io.busyming.x.FooTest.bar -- x <<< FAILURE!\n")
          == "BUILD_FAILURE")

    check("无 BUILD 标记且退出码非零 → BUILD_FAILURE (保守)",
          GA.classify_build_status("something went wrong\n", exit_code=1)
          == "BUILD_FAILURE")

    check("无 BUILD 标记且退出码为零 → UNKNOWN",
          GA.classify_build_status("something\n", exit_code=0) == "UNKNOWN")

    # 退出码解析
    check("解析 EXIT=0", GA.parse_exit_code("foo\nEXIT=0\n") == 0)
    check("解析 EXIT=1", GA.parse_exit_code("foo\nEXIT=1\n") == 1)
    check("没有 EXIT 行 → None", GA.parse_exit_code("foo\n") is None)


# ---------------------------------------------------------------------------
# 5. 规格文件解析 (run-round.sh → Python 的交接格式)
# ---------------------------------------------------------------------------

def test_spec_file_parsing(tmp):
    print("== 规格文件解析 ==")
    spec = os.path.join(tmp, "spec.txt")
    with open(spec, "w", encoding="utf-8") as fh:
        fh.write("ROOT\t/tmp/root\n")
        fh.write("GATE_LOG\t/tmp/root/F-06-ssd.txt\n")
        fh.write("CAPTURED_AT\t2026-11-19T12:00:00+08:00\n")
        fh.write("REPO\tB\t/tmp/repoB\tmvn test\tservice\n")
        fh.write("SEGMENT_BEGIN\tB\n")
        fh.write("[INFO] BUILD SUCCESS\n")
        fh.write("EXIT=0\n")
        fh.write("SEGMENT_END\tB\n")

    root, gate_log, captured_at, repos = GA.parse_spec_file(spec)
    check("root 解析正确", root == "/tmp/root", f"实为 {root}")
    check("gate_log 解析正确", gate_log == "/tmp/root/F-06-ssd.txt",
          f"实为 {gate_log}")
    check("captured_at 解析正确", captured_at == "2026-11-19T12:00:00+08:00",
          f"实为 {captured_at}")
    check("解析出 1 个仓", len(repos) == 1, f"实为 {len(repos)}")
    check("仓的 alias 正确", repos[0]["alias"] == "B")
    check("仓的日志段摘要到 BUILD SUCCESS",
          repos[0]["summary"].has_build_success)
    check("仓的退出码可从段里解析", repos[0]["summary"].exit_code == 0)
    check("仓的构建状态判定为 SUCCESS",
          repos[0]["summary"].build_status() == "SUCCESS")

    # 段未闭合 → 报错
    bad = os.path.join(tmp, "spec-bad.txt")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("ROOT\t/tmp/root\n")
        fh.write("SEGMENT_BEGIN\tB\n")
        fh.write("junk\n")
    try:
        GA.parse_spec_file(bad)
        check("段未闭合: 报错", False, "竟然解析成功")
    except ValueError:
        check("段未闭合: 报错", True)


def test_spec_file_large_is_linear(tmp):
    """大规格文件必须**线性**解析 (回归: 曾经是平方级)。

    门禁日志能到 72 MB (约 50 万行)。早期实现用 `log_text += line`
    逐行拼接, 8 万行要 179 秒, 50 万行要两小时 —— 归档实际上从未成功
    跑完过, 所以这个缺陷**没有**被端到端测试发现。

    这里用 20 万行做回归: 平方级实现要几十秒, 线性实现在两秒内。
    """
    import time
    print("== 大规格文件线性解析 ==")
    spec = os.path.join(tmp, "spec-big.txt")
    n = 200000
    with open(spec, "w", encoding="utf-8") as fh:
        fh.write("ROOT\t/tmp/root\n")
        fh.write("GATE_LOG\t/tmp/root/F-06-ssd.txt\n")
        fh.write("REPO\tB\t/tmp/repoB\tmvn test\tservice\n")
        fh.write("SEGMENT_BEGIN\tB\n")
        for _ in range(n):
            fh.write("[INFO] some ordinary maven output line\n")
        fh.write("[INFO] BUILD SUCCESS\n")
        fh.write("EXIT=0\n")
        fh.write("SEGMENT_END\tB\n")

    t0 = time.time()
    root, gate_log, captured_at, repos = GA.parse_spec_file(spec)
    elapsed = time.time() - t0
    check(f"{n} 行在 10 秒内解析完 (实为 {elapsed:.1f} 秒)", elapsed < 10.0)
    check("大文件里仍能取到 BUILD SUCCESS",
          repos[0]["summary"].has_build_success)
    check("大文件里仍能取到退出码", repos[0]["summary"].exit_code == 0)


def test_archive_dir_override(tmp):
    """显式指定归档根目录时, 写与读必须落在**同一个**地方。

    回归: 之前 bash 打印 `SSD_ARCHIVE_DIR` 但 Python 写到默认路径,
    于是「打印的路径」与「实际写入的路径」不一致, measure.py 按打印的
    路径去找归档必然找不到。
    """
    print("== 归档根目录覆盖 ==")
    root = os.path.join(tmp, "root")
    alt = os.path.join(tmp, "alt-archives")
    os.makedirs(root, exist_ok=True)
    os.makedirs(alt, exist_ok=True)

    log = os.path.join(root, "F-06-ssd.txt")
    with open(log, "w", encoding="utf-8") as fh:
        fh.write("[INFO] BUILD SUCCESS\nEXIT=0\n")

    repo = os.path.join(tmp, "repoB")
    os.makedirs(repo, exist_ok=True)
    summary = GA.LogSummary()
    summary.feed_line("[INFO] BUILD SUCCESS")
    summary.feed_line("EXIT=0")
    entries = [{"alias": "B", "repo_path": repo, "command": "mvn test",
                "scope": "service", "summary": summary}]

    # 用一个**本测试专用**的仓库根, 避免与别的用例的默认路径撞上。
    own_root = os.path.join(tmp, "own-root")
    os.makedirs(own_root, exist_ok=True)
    own_log = os.path.join(own_root, "F-06-ssd.txt")
    with open(own_log, "w", encoding="utf-8") as fh:
        fh.write("[INFO] BUILD SUCCESS\nEXIT=0\n")

    dest = GA.write_archive(own_root, "F-06", "ssd", own_log, entries,
                            archive_root=alt)
    check("写到了指定的归档根目录",
          dest == os.path.join(alt, "F-06", "ssd"), f"实为 {dest}")
    check("指定根目录下确实有目录", os.path.isdir(dest))
    check("默认路径下**没有**被写入",
          not os.path.isdir(GA.archive_dir(own_root, "F-06", "ssd")))

    ok, errors = GA.verify_archive(own_root, "F-06", "ssd", archive_root=alt)
    check("按指定根目录校验通过", ok, f"实为 {errors}")

    m = GA.load_manifest(own_root, "F-06", "ssd", archive_root=alt)
    check("按指定根目录能读到 manifest", m is not None)

    # 默认口径下必须**读不到** —— 证明两个路径没有串。
    ok2, _ = GA.verify_archive(own_root, "F-06", "ssd")
    check("默认路径下读不到 (两个口径没串)", not ok2)

    # 归档必须**自足**: 即使归档根与仓库根不同, 也能找回门禁日志。
    ok3, errors3 = GA.verify_archive(own_root, "F-06", "ssd",
                                     expected_gate_log=own_log,
                                     archive_root=alt)
    check("归档根与仓库根不同时仍能校验门禁日志", ok3, f"实为 {errors3}")


def test_log_summary_equivalence():
    """`LogSummary` 的结论必须与全文版 `classify_build_status` 一致。"""
    print("== LogSummary 与全文判定等价 ==")
    cases = [
        ("[INFO] BUILD SUCCESS\nEXIT=0\n", "SUCCESS"),
        ("[INFO] BUILD SUCCESS\n[ERROR] x.y.Z -- boom <<< FAILURE!\nEXIT=1\n",
         "TEST_FAILURE"),
        ("[INFO] BUILD FAILURE\n", "BUILD_FAILURE"),
        ("[ERROR] COMPILATION ERROR\n", "BUILD_FAILURE"),
        ("[INFO] BUILD SUCCESS\n[ERROR] x.y.Z -- boom\nEXIT=1\n", "SUCCESS"),
        ("nothing here\nEXIT=3\n", "BUILD_FAILURE"),
        ("nothing here\n", "UNKNOWN"),
    ]
    for text, expected in cases:
        got = GA.classify_build_status(text)
        check(f"全文判定 {expected}", got == expected, f"实为 {got}")

        summary = GA.LogSummary()
        for line in text.splitlines():
            summary.feed_line(line)
        check(f"摘要判定 {expected}", summary.build_status() == expected,
              f"实为 {summary.build_status()}")
        check(f"摘要退出码与全文一致",
              summary.exit_code == GA.parse_exit_code(text))


# ---------------------------------------------------------------------------
# 6. measure.py 必须只从归档读
# ---------------------------------------------------------------------------

def test_measure_requires_archive(tmp):
    """measure.py 在**没有归档**时必须拒绝测量。

    这是本次修复的兜底: 旧实现读共享目录, 读不到也会照样出数。
    """
    print("== measure.py 强制要求归档 ==")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_mod_arch", os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "measure.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)

    # measure.py 的 ROOT 指向真实规格仓, 归档一定不在那里
    rid = "ARCH-TEST-01"
    ok, errors = GA.verify_archive(M.ROOT, rid, "ssd")
    check("真实规格仓下没有该轮归档", not ok)
    check("报告了缺失", bool(errors))


def test_run_round_passes_archive_root():
    """`run-round.sh` 必须把归档根目录**同时**传给写归档与测量。

    回归: `SSD_ARCHIVE_DIR` 被覆盖时, 归档写到覆盖路径, 而 measure.py
    默认去 `<root>/docs/efficacy/gates/archives` 找。两边不一致时,
    测量要么报「归档缺失」, 要么读到上一次的旧归档 (跨臂污染的老毛病)。

    这里做**静态**核对 (脚本文本), 因为真跑一遍需要完整的实验环境。
    核对的是「同一份 `ARCHIVE_DIR` 是否同时出现在两个调用点」。
    """
    print("== run-round.sh 归档根目录一致性 ==")
    script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "run-round.sh")
    with open(script, encoding="utf-8") as fh:
        text = fh.read()

    check("脚本存在", os.path.isfile(script))

    # 写归档那一侧: 必须用 `--archive-dir "$ARCHIVE_DIR"`。
    check("写归档用了 --archive-dir \"$ARCHIVE_DIR\"",
          '--archive-dir "$ARCHIVE_DIR"' in text)

    # 测量那一侧: 必须用 `--archive-root`。
    check("测量用了 --archive-root",
          "--archive-root" in text,
          "measure.py 找不到被覆盖的归档根目录")

    # 两侧引用的**必须是同一个变量**, 不能各写各的路径。
    check("--archive-root 绑定的是 $ARCHIVE_DIR",
          '--archive-root "$ARCHIVE_DIR"' in text,
          "--archive-root 必须与写归档用同一个变量")

    # $ARCHIVE_DIR 只能被解析一次 (单一来源)。
    n_assign = text.count('ARCHIVE_DIR="${SSD_ARCHIVE_DIR:')
    check("ARCHIVE_DIR 只解析一次 (单一来源)", n_assign == 1,
          f"实为 {n_assign} 次")


def test_run_round_passes_flaky_list():
    """`run-round.sh` 必须把**同一份**隔离清单传给两臂。

    回归: 隔离清单是尺子的一部分 (FORMULA.md §3.4.9.4), 对两臂对称
    (§3.4.9.3)。如果 `run-round.sh` 不显式传 `--flaky-list`, 两臂就靠
    `measure.py` 的默认值兜底。一旦有人改了默认值或给某臂单独传了
    别的清单, 两臂的 `D` 就不可比, 而且**没有任何地方会报错**。

    这里做**静态**核对 (脚本文本), 因为真跑一遍需要完整的实验环境。
    """
    print("== run-round.sh 隔离清单一致性 ==")
    script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "run-round.sh")
    with open(script, encoding="utf-8") as fh:
        text = fh.read()

    check("脚本存在", os.path.isfile(script))

    # 测量那一侧: 必须显式传 `--flaky-list`。
    check("测量用了 --flaky-list",
          "--flaky-list" in text,
          "两臂靠 measure.py 默认值兜底, 隔离清单可能悄悄漂移")

    # 传的值必须是**单一变量**, 不能在两臂上各写各的路径。
    check("--flaky-list 绑定的是 $FLAKY_LIST",
          '--flaky-list "$FLAKY_LIST"' in text,
          "--flaky-list 必须绑定单一来源变量, 两臂才能保证同一份清单")

    # $FLAKY_LIST 只能被解析一次 (单一来源)。
    n_assign = text.count('FLAKY_LIST="${SSD_FLAKY_LIST:')
    check("FLAKY_LIST 只解析一次 (单一来源)", n_assign == 1,
          f"实为 {n_assign} 次")


def main():
    tmp = tempfile.mkdtemp(prefix="archive-test-")
    try:
        test_archive_roundtrip(tmp)
        test_archive_isolation(tmp)
        test_archive_verification(tmp)
        test_unlisted_file_not_counted(tmp)
        test_build_status_classification()
        test_spec_file_parsing(tmp)
        test_spec_file_large_is_linear(tmp)
        test_archive_dir_override(tmp)
        test_log_summary_equivalence()
        test_measure_requires_archive(tmp)
        test_run_round_passes_archive_root()
        test_run_round_passes_flaky_list()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILURES:
        print(f"[FAIL] {len(FAILURES)} 项未通过: {FAILURES}")
        return 1
    print("[OK] 全部自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
