# 交付 B（DB） W4 任务书

> 周期：8/10（周日）- 8/16（周六） | 核心目标：生成 1.5 倍压力图表、参数敏感性曲线、PyQt 看板（可选）、录制高压力视频素材

## 每日任务

### Day 1（8/10 周日）— 1.5 倍压力图表模板准备

- [ ] 设计原始流量 vs 1.5 倍流量对比柱状图模板（分组柱状图，两组并列）
- [ ] 设计高压力下 CA-MP 改进百分比热力图模板
- [ ] 等待 EX 数据，确认数据列名和格式

```python
# 1.5 倍压力对比柱状图模板
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from visualization.plots import ALGO_COLORS, ALGO_LABELS

def plot_pressure_comparison(df_normal, df_high, metric, title, ylabel, save_path):
    """原始流量 vs 1.5 倍流量分组对比"""
    fig, ax = plt.subplots(figsize=(12, 6))
    algos = df_normal['algorithm'].unique()
    x = np.arange(len(algos))
    width = 0.35
    normal_vals = [df_normal[df_normal['algorithm'] == a][metric].mean() for a in algos]
    high_vals = [df_high[df_high['algorithm'] == a][metric].mean() for a in algos]
    ax.bar(x - width/2, normal_vals, width, label='原始流量', color='#3498DB')
    ax.bar(x + width/2, high_vals, width, label='1.5× 流量', color='#E74C3C')
    ax.set_xticks(x)
    ax.set_xticklabels([ALGO_LABELS[a] for a in algos])
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(save_path, dpi=300)
    plt.close(fig)
```

**验证：**
```bash
python -c "import ast; ast.parse(open('visualization/plots.py').read()); print('syntax OK')"
# 预期输出：syntax OK
```

### Day 2（8/11 周一）— PyQt 实时看板实现（可选）

- [ ] 基于 W1 可行性测试结果，实现 PyQt 看板最小功能：当前相位 + 各进口道排队柱状图 + 压力折线
- [ ] 数据来源：读取 `simulation_log.csv` 实时刷新（或接入 runner.py 回调）
- [ ] 如果 PyQt 实现困难，果断放弃（不影响核心交付）

```python
# scripts/dashboard.py
import sys
import pandas as pd
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from visualization.plots import ALGO_COLORS

class Dashboard(QMainWindow):
    def __init__(self, csv_path='output/csv/simulation_log.csv'):
        super().__init__()
        self.setWindowTitle("CA-MP 实时监控看板")
        self.df = pd.read_csv(csv_path)
        self.idx = 0
        self.figure = Figure(figsize=(12, 8))
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.timer = QTimer()
        self.timer.timeout.connect(self._update)
        self.timer.start(100)  # 100ms 刷新

    def _update(self):
        self.figure.clear()
        row = self.df.iloc[self.idx % len(self.df)]
        # 子图1：各进口道排队柱状图
        ax1 = self.figure.add_subplot(2, 1, 1)
        ax1.bar(['N', 'S', 'E', 'W'], [row.get(f'queue_{d}', 0) for d in 'NSEW'],
                color=ALGO_COLORS['ca_max_pressure'])
        ax1.set_title(f"排队长度 (step={int(row['step'])})")
        # 子图2：压力折线
        ax2 = self.figure.add_subplot(2, 1, 2)
        ax2.plot(self.df['step'][:self.idx+1], self.df['pressure'][:self.idx+1],
                color='#3498DB')
        ax2.set_title('压力值变化')
        self.figure.tight_layout()
        self.canvas.draw()
        self.idx += 1

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dash = Dashboard()
    dash.show()
    sys.exit(app.exec_())
```

**验证：**
```bash
python scripts/dashboard.py
# 预期：弹出窗口 "CA-MP 实时监控看板"，柱状图和折线图每 100ms 刷新
# 如果 PyQt5 不可用则跳过此项
```

### Day 3（8/12 周二）— 1.5 倍压力数据图表

- [ ] 收到 1.5 倍压力数据后，生成 20 路口 × 2 流量水平 × 3 算法行程时间对比
- [ ] 生成高压力 vs 原始流量下 CA-MP 改进幅度对比图
- [ ] 输出到 `demo/assets/charts/`（PNG 300dpi + SVG）

```python
import pandas as pd
from visualization.plots import plot_improvement_heatmap

df_normal = pd.read_csv('output/csv/all_results_normal.csv')
df_high = pd.read_csv('output/csv/all_results_1.5x.csv')

plot_pressure_comparison(df_normal, df_high, 'avg_delay',
                        '1.5× 流量下行程时间对比', '行程时间 (s)',
                        'demo/assets/charts/pressure_comparison_delay.png')
plot_improvement_heatmap(df_high, 'demo/assets/charts/improvement_heatmap_high.png')
```

**验证：**
```bash
python -c "import os; assert os.path.exists('demo/assets/charts/pressure_comparison_delay.png'); assert os.path.exists('demo/assets/charts/improvement_heatmap_high.png'); print('OK')"
# 预期输出：OK
```

### Day 4（8/13 周三）— 参数敏感性曲线

- [ ] 生成 overflow_threshold 敏感性曲线：X 轴 0.8-0.95，Y 轴平均行程时间，两条线（路口 1、路口 16）
- [ ] 生成 EWMA alpha 敏感性曲线（同样格式）
- [ ] 输出 PNG + SVG

```python
import pandas as pd
import matplotlib.pyplot as plt

df_sens = pd.read_csv('output/csv/sensitivity_results.csv')

# overflow_threshold 敏感性
fig, ax = plt.subplots(figsize=(10, 6))
for i_id in [1, 16]:
    sub = df_sens[df_sens['intersection_id'] == i_id]
    ax.plot(sub['overflow_threshold'], sub['avg_delay'],
            marker='o', label=f'路口 {i_id}')
ax.set_xlabel('overflow_threshold')
ax.set_ylabel('平均行程时间 (s)')
ax.set_title('参数敏感性：overflow_threshold')
ax.legend()
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig('demo/assets/charts/sensitivity_threshold.png', dpi=300)
fig.savefig('demo/assets/charts/sensitivity_threshold.svg')
plt.close(fig)

# EWMA alpha 敏感性
fig, ax = plt.subplots(figsize=(10, 6))
for i_id in [1, 16]:
    sub = df_sens[df_sens['intersection_id'] == i_id]
    ax.plot(sub['ewma_alpha'], sub['avg_delay'],
            marker='s', label=f'路口 {i_id}')
ax.set_xlabel('EWMA alpha')
ax.set_ylabel('平均行程时间 (s)')
ax.set_title('参数敏感性：EWMA alpha')
ax.legend()
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig('demo/assets/charts/sensitivity_alpha.png', dpi=300)
fig.savefig('demo/assets/charts/sensitivity_alpha.svg')
plt.close(fig)
print('OK')
```

**验证：**
```bash
python -c "import os; assert os.path.exists('demo/assets/charts/sensitivity_threshold.png'); assert os.path.exists('demo/assets/charts/sensitivity_alpha.png'); print('OK')"
# 预期输出：OK，两张图各含两条曲线（路口 1、路口 16）
```

### Day 5（8/14 周四）— 录制 1.5 倍流量视频素材

- [ ] 路口 16，1.5 倍流量，FixedTime 录屏（OBS，1080p）
- [ ] 路口 16，1.5 倍流量，CA-MP 录屏
- [ ] 确认高压力下对比效果明显（排队更长、CA-MP 优势更大）
- [ ] 这些是视频"效果对比"段落的核心素材

```bash
# 1.5 倍流量 FixedTime
sumo-gui -c data/intersection_data/16/sumo工程/demo_16_1.5x.sumocfg --start
# 1.5 倍流量 CA-MP
python experiments/runner.py --intersection 16 --algo ca_maxpressure --gui --steps 3600 --flow-scale 1.5
```

**验证：**
```bash
ffprobe -v quiet -show_entries stream=width,height -show_entries format=duration demo/assets/recordings/fixed_time_i16_1.5x.mp4
# 预期：width=1920, height=1080, duration > 60s
ffprobe -v quiet -show_entries format=duration demo/assets/recordings/ca_mp_i16_1.5x.mp4
# 预期：duration > 60s
```

### Day 6（8/15 周五）— 图表最终整理

- [ ] 更新所有图表为最终版（含 1.5 倍数据）
- [ ] 整理 `demo/assets/charts/` 按用途分子目录：`report/`、`ppt/`、`video/`
- [ ] 与 DA 确认报告/PPT 还需要哪些图

```bash
mkdir demo\assets\charts\report demo\assets\charts\ppt demo\assets\charts\video
```

**验证：**
```bash
dir demo\assets\charts\report\ | find /c ".png"
# 预期：>= 10（报告用图表）
dir demo\assets\charts\ppt\ | find /c ".png"
# 预期：>= 5（PPT 用图表）
```

### Day 7（8/16 周六）— Buffer / PyQt 看板录制

- [ ] 修复本周图表问题
- [ ] 如果 PyQt 看板完成，录制看板演示片段（用于视频"系统演示"段落）
- [ ] 提交所有素材给 TL

**验证：**
```bash
dir demo\assets\recordings\dashboard_demo.mp4 2>nul && echo EXISTS || echo SKIP
# 预期：EXISTS（如果 PyQt 看板完成）或 SKIP（如果放弃）
```

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 1.5 倍压力对比图表 | 8/12 | 分组柱状图 + 热力图，PNG+SVG |
| 参数敏感性曲线 | 8/13 | threshold + alpha 两张，各含路口 1/16 两条线 |
| 1.5 倍流量录屏 × 2 | 8/14 | 路口 16 高压力对比，1080p 30fps |
| 最终版图表整理 | 8/15 | 按 report/ppt/video 分类 |
| PyQt 看板（可选） | 8/11 | 如果能做就做，不影响核心交付 |

## 协作对接

- 与 EX 对接获取 1.5 倍压力数据和参数敏感性实验数据（Day 1、Day 3）
- 与 DA 确认报告/PPT 图表最终需求（Day 6）
- PyQt 看板如需接入 runner.py 回调，与 IB 对接接口格式
