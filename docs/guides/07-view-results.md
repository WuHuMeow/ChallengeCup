# 如何查看/导出结果

## 目的

找到仿真输出文件，理解 CSV 字段含义，提取关键指标用于报告。

## 前置条件

- 已运行过至少一次仿真（参见指南 03 或 04）

## 操作步骤

### 输出目录结构

```
output/
└── runs/
    └── i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/
        ├── metrics.csv
        ├── simulation_log.csv
        ├── events.csv
        ├── tripinfo.xml / stats.xml / traj.xml
        ├── summary.json / run_metadata.json
        └── variants/
```

这些目录由命令运行时创建，当前仓库没有保留已删除的完整矩阵产物。

### 指标快照 CSV 字段

文件：运行目录内的 `metrics.csv`。`avg_travel_time`、`throughput`、停车和油耗等精确
运行级指标以同目录 `summary.json` 为准；缺失值为 JSON `null`，不能按 0 解释。

| 列名 | 含义 | 单位 |
|------|------|------|
| step | 采集步编号 | 步 |
| timestamp | 仿真时间 | 秒 |
| avg_queue_length | 平均排队长度 | 米 |
| max_queue_length | 最大排队长度 | 米 |
| avg_delay | 平均延误 | 秒/辆 |
| total_throughput | 累计通过车辆数 | 辆 |
| avg_travel_time | 平均行程时间 | 秒 |
| total_stops | 累计停车次数 | 次 |
| fuel_consumption | 累计油耗 | mL |
| queue_{方向} | 各进口道排队 | 米 |
| flow_{方向} | 各进口道流量 | 辆/小时 |

### 用 pandas 快速分析

```python
import pandas as pd

df = pd.read_csv("output/runs/i16/ca_maxpressure/x1.0/s42/<run_id>/metrics.csv")
print(df[["avg_queue_length", "avg_delay", "total_throughput"]].describe())
```

## 常见问题

**Q: CSV 文件被 .gitignore 忽略了？**
A: 是的，`*.csv` 在 `.gitignore` 中。结果文件不提交到仓库，需要时重新运行生成。

**Q: 如何汇总矩阵结果？**
A: 运行 `python -m visualization.report --input output/runs/matrix-full --output output/runs/matrix-full/figures`，
它会生成 `summaries.csv`、图表和来源 `manifest.json`。

**Q: 快照间隔太大/太小？**
A: 修改 `config/default.yaml` 中 `metrics.snapshot_interval`（默认 600 步 = 60 秒一行）。
