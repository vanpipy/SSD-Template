"""与载体无关的纯函数:时间戳、内容哈希、外部事实引用提取。

F9 起仓内**不再有控制平面**(决定文件 / 证据链 / 派生 `state.json`):
留痕 = 制品(状态块 + 复审块)+ git 历史(见 `WORKFLOW.md` §5)。
本模块只留下不依赖任何目录结构的小工具,便于单独测试。
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime

_EXTERNAL_REF_RE = re.compile(r"external:[^\s|,]+")


def sha256_text(text: str) -> str:
    """内容哈希(留痕用;旧证据链的 `sha256:...` 形态保留)。"""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    """带时区的 ISO-8601 时间戳(契约 §3.1 要求带时区)。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def external_refs(text: str) -> list[str]:
    """从文本里摘出全部 `external:<ref>` 依据(契约 §5.2 的 Implemented 前提)。

    去重且保持出现顺序;调用方取第一个作为权威依据。
    """
    refs: list[str] = []
    for found in _EXTERNAL_REF_RE.findall(text or ""):
        if found not in refs:
            refs.append(found)
    return refs
