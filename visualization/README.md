# visualization/

## 模块职责

可视化层，基于 Matplotlib/Seaborn 将实验数据转换为图表，支撑答辩 PPT、Demo 视频与实验报告。

## 当前完成情况

- [x] `plots.py`：图表函数骨架，包含算法对比、热力图占位。
- [ ] `report.py`：尚未实现。

## 待完成情况

- [ ] `plots.py`：实现真实数据驱动的对比柱状图、时序图、热力图。
- [ ] `report.py`：实现报告自动生成（可选）。
- [ ] 确定统一配色与图表风格（红=固定配时，橙=感应控制，绿=CA-MP）。
- [ ] 输出高分辨率图表供 PPT 与报告使用。

## 需求分析

| 需求 | 说明 |
|------|------|
| 算法对比 | 同一场景下三种算法核心指标并排对比 |
| 时序分析 | 单路口排队长度随时间变化曲线 |
| 多场景热力图 | 20 路口 × 3 算法 × 指标 的热力图 |
| 中文字体 | Windows 下需配置 SimHei/Microsoft YaHei |

## 关键文件

| 文件 | 说明 |
|------|------|
| `plots.py` | 图表生成 |
| `report.py` | 报告生成（待实现） |

## 对外接口

```python
from visualization.plots import plot_algorithm_comparison

plot_algorithm_comparison(csv_files, labels, output_path, metric="avg_queue_length")
```

## 负责人

- DB（交付 B）：可视化（Matplotlib 图表 + PyQt 看板）、视频录制剪辑
