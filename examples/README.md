# Examples

## 模块职责

`examples/` 提供可直接运行的最小入口，用于验证配置、场景、引擎、算法和输出链路。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `run_demo.py` | 默认使用 `MockBridge` 运行 10 步完整调用链；`--sumo` 切换真实仿真 |
| `run_fixed_time.py` | 使用 SUMO 运行单路口固定配时基线 |
| `run_ca_max_pressure.py` | 使用 SUMO 运行单路口 CA-MP 控制器 |

## 命令接口

```powershell
python examples/run_demo.py 1 ca_maxpressure
python examples/run_demo.py 1 fixed_time --sumo
python examples/run_fixed_time.py 1
python examples/run_ca_max_pressure.py 1 3600
```

`run_demo.py` 的算法参数可选 `fixed_time`、`actuated`、`ca_maxpressure`。真实仿真示例的路口 ID 为 `1` 至 `20`；`run_ca_max_pressure.py` 的第二个位置参数是仿真步数。

## 输入与输出

- 输入：`config/default.yaml`、`data/intersection_data/` 中的路口工程，以及命令行路口/算法/步数参数。
- `run_demo.py`、`run_fixed_time.py` 和 `run_ca_max_pressure.py` 直接创建
  `output/csv/{路口}_{算法}.csv`；这是运行时生成的文件，当前不随仓库保留。
- SUMO 模式优先使用 `engine/configs/demo_N.sumocfg`。如需可追踪的 `metrics.csv`、事件日志、
  SUMO XML 和摘要，应使用 `experiments.runner` 的 `--output-dir`；直接示例不创建该运行作用域。

## 依赖

- `run_demo.py` 的默认模式只需要项目 Python 依赖和路口数据。
- 带 `--sumo` 的模式、`run_fixed_time.py` 和 `run_ca_max_pressure.py` 需要 SUMO/TraCI。
- 所有脚本依赖 `core`、`scenes`、`engine` 和 `algorithms` 模块。

## 已知限制

- `run_demo.py --sumo` 和 `run_fixed_time.py` 固定运行 36000 步；当前没有独立步数参数。
- CA-MP 示例使用 `CAMaxPressureAlgorithm`；可调参数和完整矩阵入口见 `algorithms/` 与 `scripts/run_pdf_matrix.py`。
- 示例不负责批量矩阵、断点续跑或统计汇总；这些入口在 `experiments/runner.py`。
