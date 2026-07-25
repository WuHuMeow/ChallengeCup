# Algorithms

## 模块职责

`algorithms/` 定义统一交通控制器契约，并实现固定配时、规则感应控制和 CA-MP 三种策略，供 `SimulationRunner` 与实验框架统一调度。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `base.py` | `BaseControlAlgorithm` 抽象接口 |
| `fixed_time.py` | SUMO 默认配时或可选 Excel 配时写入 |
| `rule_adaptive.py` | 基于排队阈值和绿灯时长的规则控制 |
| `ca_max_pressure.py` | 调用云端预测并输出 CA-MP MVI 控制动作 |

## 对外接口

所有控制器实现 `init(scene)`、`step(state)`、`reset()` 和 `name`：

```python
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm

algorithm = CAMaxPressureAlgorithm()
algorithm.init(scene)
actions = algorithm.step(state)  # list[ControlAction]
```

## 输入与输出

- 输入：`core.types.Scene` 和每步 `core.types.JointState`。
- 输出：`list[ControlAction]`；空列表表示本步不修改 SUMO 信号程序。
- 配置：感应控制和 CA-MP 参数来自 `config/default.yaml` 的 `algorithms.*`。

## 依赖

- 依赖 `core.types` 和 `core.config`。
- `FixedTimeAlgorithm(use_excel_timing=True)` 依赖 pandas、Excel 配时文件和已启动的 TraCI 连接。
- `CAMaxPressureAlgorithm` 依赖 `cloud.CloudPolicy`。

## 已知限制

- CA-MP 当前按最长队列选择相位；容量归一化压力、溢出门控和预测值融合尚未进入控制决策。
- 规则感应控制用队列数量近似相位数量，未读取真实相位拓扑。
- Excel 配时写入假设 SUMO 原程序按绿/黄交替排列，未写入 Excel 的全红时长。
- `reset()` 当前不会清理额外算法状态；重复实验由调用方重新创建实例更稳妥。
