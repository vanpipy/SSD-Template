"""SSD-Template 仓内机器能力库(ssdctl 的实现层)。

模块划分(每个模块只拥有一种行为):

- `paths`    : 仓库根 / 判据文件路径解析
- `artifacts`: 制品发现 + 状态块(§3.1)+ 复审块(§3.2)+ 稳定 ID(§3.3)
- `criteria` : 判据加载 + §4.1 的 12 种 kind 引擎
- `dispatch` : 调度谓词(§7):上游解析 + 5 合取
- `commands` : 6 个子命令的实现(§5.1)
- `util`     : 无状态小工具(时间戳 / 哈希 / external: 提取)

F9:仓内**不再有控制平面**(`control/` 已整体删除)—— 状态与评审的唯一权威
载体 = 制品本身,所以这里没有 `control` 模块。

契约来源:`docs/contracts/agent-first-implementation.md`。
"""

__all__ = ["artifacts", "commands", "criteria", "dispatch", "paths", "util"]
