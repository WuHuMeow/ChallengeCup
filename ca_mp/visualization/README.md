# Visualization

## 模块职责

`visualization/` 将实验 CSV 转换为静态 Matplotlib 图片，供报告、答辩和结果检查使用。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `plots.py` | 时序算法对比曲线和热力图占位输出 |

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

## 输入与输出

- `plot_algorithm_comparison()` 输入带 `step` 和目标指标列的多个 CSV，输出折线图文件。
- `plot_heatmap()` 输入结果 CSV 和输出路径，当前只生成带标题的占位图片。
- 两个函数都会自动创建输出文件的父目录。

## 依赖

- 依赖 pandas 和 Matplotlib。
- 输入列名需与 `MetricsCollector` 或实验汇总格式一致。

## 已知限制

- `plot_heatmap()` 尚未读取或透视输入数据，只输出占位画布。
- 当前没有箱线图、柱状汇总图、报告生成器或交互式看板实现。
- 图表未统一中文字体、颜色和高分辨率导出策略。
- `zip(csv_files, labels)` 会静默忽略长度不一致的多余项。
