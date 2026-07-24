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
- Mock 输出：默认写入 `output/csv/{路口}_{算法}.csv`。
- SUMO 输出：指标 CSV 写入 `output/csv/`；增强配置还会产生 SUMO XML 输出。

## 依赖

- `run_demo.py` 的默认模式只需要项目 Python 依赖和路口数据。
- 带 `--sumo` 的模式、`run_fixed_time.py` 和 `run_ca_max_pressure.py` 需要 SUMO/TraCI。
- 所有脚本依赖 `core`、`scenes`、`engine` 和 `algorithms` 模块。

## 已知限制

- `run_demo.py --sumo` 固定运行 3600 步；当前没有独立步数参数。
- `run_fixed_time.py` 固定运行 3600 步。
- CA-MP 示例调用的是当前 MVI 控制器，尚未实现完整容量感知压力与溢出门控。
- 示例不负责批量矩阵、断点续跑或统计汇总；这些入口在 `experiments/runner.py`。
