# 如何生成可视化图表

## 目的

使用 `visualization` 模块从运行目录或矩阵汇总生成可追溯图表。

## 前置条件

- 已安装项目依赖：`pip install -r requirements.txt`
- 已有包含 `summary.json`、`run_metadata.json` 和指标文件的运行目录

## 操作步骤

```python
from pathlib import Path
from visualization.plots import plot_algorithm_comparison

# 对比多算法的排队长度时序
plot_algorithm_comparison(
    csv_files=[
        Path("output/runs/.../fixed_time/<run_id>/metrics.csv"),
        Path("output/runs/.../ca_maxpressure/<run_id>/metrics.csv"),
    ],
    labels=["fixed_time", "ca_maxpressure"],
    output_file=Path("output/runs/comparison/queue.png"),
    metric="avg_queue_length",
)
```

### 可用图表函数

矩阵报告的推荐入口：

```bash
python -m visualization.report \
  --input output/runs/matrix-full \
  --output output/runs/matrix-full/figures
```

该命令生成算法柱状图、路口 x 算法热力图、代表性时序/轨迹（输入存在时）、
`summaries.csv` 和记录来源的 `manifest.json`。

## 示例

`plot_heatmap(results_csv, output_file, metric=...)` 可直接读取包含
`intersection_id`、`algorithm` 和目标指标的汇总 CSV。缺列或没有数值时会抛出
`ValueError`，不会生成占位图片。

## 常见问题

**Q: 中文显示为方块？**
A: matplotlib 默认不支持中文。在脚本开头加：
```python
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False
```

**Q: 图片保存在哪？**
A: 保存到命令指定的运行时目录；这些图表默认不进 Git。只有经复核的具体交付文件才能
按 `output/deliverables/README.md` 的规则单独纳入版本控制。
