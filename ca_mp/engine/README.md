# Engine

## 模块职责

`engine/` 封装 SUMO/TraCI 生命周期、离线 Mock 状态、每步控制循环、指标采集、详细日志、事件日志和可选 V2X 延迟通道。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `runner.py` | `SimulationRunner` 运行循环和输出协调 |
| `traci_bridge.py` | SUMO 启停、状态读取、车辆采样和动作写入 |
| `mock_bridge.py` | 与运行器兼容的确定性离线桥接 |
| `collector.py` | 指标快照 CSV 和逐步日志 CSV |
| `events.py` | 运行生命周期与控制动作事件 CSV |
| `edge_channel.py` | 方向过滤和固定步数延迟的内存消息通道 |
| `configs/` | 由 `scripts/simulation/generate_configs.py` 生成的 20 个增强 SUMO 配置 |

## 对外接口

```python
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner

bridge = MockBridge(tls_id="tls_0", directions=["E0", "E1", "E2", "E3"])
runner = SimulationRunner(scene, algorithm, bridge=bridge)
history = runner.run(steps=10)
```

未传入 `bridge` 时，`SimulationRunner` 创建 `TraCIBridge`，优先使用 `engine/configs/demo_N.sumocfg`。

## 输入与输出

- 输入：`Scene`、实现 `BaseControlAlgorithm` 的控制器、步数、随机种子和可选附加 flow 文件。
- 状态：桥接层生成 `JointState`，算法返回 `ControlAction`。
- 输出：指标 CSV、可选逐步日志 CSV、可选事件 CSV，以及内存中的指标快照列表。

## 依赖

- 真实桥接依赖 SUMO/TraCI、路口工程和边映射元数据。
- 运行器依赖 `algorithms`、`core` 和 `experiments.metrics`。
- Mock 模式不启动 SUMO，但仍需要有效 `Scene` 元数据。

## 已知限制

- `SimulationRunner` 能在 FatalTraCIError 后关闭并保存已有输出，但不支持断点恢复。
- `MockBridge` 只验证接口与确定性行为，不模拟真实交通动力学。
- 车辆快照最多保留 500 辆并可采样；`arrival_history` 只记录 departed 数，不区分方向。
- 行程时间和燃油指标仍需通过 SUMO `tripinfo` 二次校准。
- `engine/configs/` 是生成文件，修改应回到生成脚本后重新生成。
