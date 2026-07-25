# 如何生成可视化图表

## 目的

使用 `visualization` 模块从仿真结果 CSV 生成对比图表。

## 前置条件

- 已安装项目依赖：`pip install -e .`（含 matplotlib、seaborn）
- 已有仿真结果 CSV（参见指南 03/04/07）

## 操作步骤

```python
from visualization.plots import plot_comparison

# 对比多算法的排队长度时序
plot_comparison(
    csv_paths=[
        "output/csv/16_fixed_time.csv",
        "output/csv/16_ca_maxpressure.csv",
    ],
    metric="avg_queue_length",
    title="路口 16 排队长度对比",
    output_path="output/figures/queue_comparison.png",
)
```

### 可用图表函数

查看 `visualization/plots.py` 中的公开函数。典型用法：

```python
import matplotlib.pyplot as plt
from visualization import plots

# 具体函数签名见模块 README：visualization/README.md
```

## 示例

生成完整对比图后保存：
```bash
python -c "
from visualization.plots import plot_comparison
plot_comparison(
    csv_paths=['output/csv/16_fixed_time.csv', 'output/csv/16_ca_maxpressure.csv'],
    metric='avg_delay',
    output_path='output/figures/delay_16.png'
)
"
```

## 常见问题

**Q: 中文显示为方块？**
A: matplotlib 默认不支持中文。在脚本开头加：
```python
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False
```

**Q: 图片保存在哪？**
A: 建议保存到 `output/figures/`（已被 .gitignore 覆盖）。交付用图手动复制到 `output/deliverables/`。
