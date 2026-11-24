"""SSD-Template 仓内机器能力库(ssdctl 的实现层)。

模块划分(每个模块只拥有一种行为):

- `paths`    : 仓库根 / 判据文件 / 控制平面路径解析
- `artifacts`: 制品发现 + 状态块(§3.1)+ 复审块(§3.2)+ 稳定 ID(§3.3)
- `criteria` : 判据加载 + §4.1 的 12 种 kind 引擎
- `control`  : 控制平面(§6):决定文件 / 证据链 / 派生 state.json
- `dispatch` : 调度谓词(§7):上游解析 + 5 合取
- `commands` : 8 个子命令的实现(§5.1)

契约来源:`docs/contracts/agent-first-implementation.md`。
"""

__all__ = ["artifacts", "commands", "control", "criteria", "dispatch", "paths"]
