# Visualization

## 模块职责

`visualization/` 将运行 CSV 和运行摘要转换为带来源清单的静态 Matplotlib 图片，供报告、答辩和结果检查使用。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `plots.py` | 时序算法对比曲线和路口-算法指标热力图 |
| `report.py` | 从运行产物汇总、生成单次/矩阵图表并写入 `manifest.json` |

## 对外接口

```python
from visualization.plots import plot_algorithm_comparison, plot_heatmap

plot_algorithm_comparison(
    csv_files,
    labels,
    output_file,
    metric="avg_queue_length",
)
plot_heatmap(results_csv, output_file)
```

```powershell
python -m visualization.report --input output/runs/example --output output/runs/example/figures
```

## 输入与输出

- `plot_algorithm_comparison()` 输入带 `step` 和目标指标列的多个 CSV，输出折线图文件。
- `plot_heatmap()` 输入包含 `intersection_id`、`algorithm` 和目标指标列的 CSV，输出实际透视后的热力图。
- `generate_run_figures()` 读取一个运行目录的 `summary.json`、`metrics.csv` 和可选 `traj.xml`；
  `generate_matrix_figures()` 递归读取带 `run_metadata.json` 的 `summary.json`，输出图表、`summaries.csv` 和 `manifest.json`。
- 所有输出目录由函数或 CLI 在运行时创建；上例的 `output/runs/example/` 不是当前仓库中的保留结果。

## 依赖

- 依赖 pandas 和 Matplotlib。
- 输入列名需与 `MetricsCollector` 或实验汇总格式一致。

## 已知限制

- 只有包含必需列和数值指标的输入才能绘制；缺列、无数值或没有可收集的 `summary.json` 时函数会抛出 `ValueError`。
- 当前没有箱线图或交互式看板；矩阵报告提供算法柱状图、热力图和代表性时序/轨迹图。
- 图表未统一中文字体、颜色和高分辨率导出策略。
- `zip(csv_files, labels)` 会静默忽略长度不一致的多余项。
