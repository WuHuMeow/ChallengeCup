# 交付 B（DB） W1 任务书

> 周期：7/20（周日）- 7/26（周六） | 核心目标：确定录屏方案、测试可视化工具链、准备视频制作流程

## 本周背景

你负责所有视觉交付物：Matplotlib 实验图表、PyQt 实时看板（可选加分项）、5-8 分钟演示视频的录制与剪辑。W1 的任务是"磨刀"——把工具链跑通，W3 实验数据一出就能立刻出图，W5 直接录视频。PDF 评分标准中"团队展示与综合表现"占 15 分，视频是核心得分项。

## 每日任务

### Day 1（7/20 周日）— SUMO-GUI 录屏方案验证

- [ ] 安装 OBS Studio（https://obsproject.com/），配置输出为 1920×1080 MP4
- [ ] 用 SUMO-GUI 打开口 1 并录制 30 秒仿真运行，检查帧率 ≥30fps、窗口完整无卡顿
- [ ] 测试 SUMO 自带截图功能（Edit → Screenshot）作为备选
- [ ] 确定录屏方案（A: OBS 录窗口 / B: 逐帧截图 + ffmpeg 合成），记录结论告知 TL

**验证：**
```bash
sumo-gui -c data/intersection_data/1/sumo工程/demo_1.sumocfg --start
# OBS 录制 30 秒后检查输出文件
ffprobe -v quiet -show_entries stream=width,height,r_frame_rate demo/assets/recordings/test_30s.mp4
# 预期输出包含：width=1920, height=1080, r_frame_rate=30/1
```

### Day 2（7/21 周一）— Matplotlib 图表样式设计

- [ ] 创建 `visualization/plots.py`，定义全局样式（中文字体、DPI、配色方案）
- [ ] 实现 5 种图表函数骨架：柱状图、折线图、时空轨迹图、热力图、箱线图
- [ ] 用假数据测试每种图表类型能否正常渲染（中文显示、配色、保存）
- [ ] 确认图表保存为 PNG（300dpi）和 SVG（矢量，PPT 用）

```python
"""visualization/plots.py — 实验结果图表生成"""
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd

# 全局样式设置
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.dpi'] = 150
matplotlib.rcParams['savefig.dpi'] = 300
matplotlib.rcParams['figure.figsize'] = (10, 6)

ALGO_COLORS = {
    'fixed_time': '#E74C3C',
    'rule_adaptive': '#F39C12',
    'ca_max_pressure': '#2ECC71',
}
ALGO_LABELS = {
    'fixed_time': '固定配时',
    'rule_adaptive': '感应控制',
    'ca_max_pressure': 'CA-MP（本文）',
}

def plot_bar_comparison(df: pd.DataFrame, metric: str, title: str,
                        ylabel: str, save_path: str) -> None:
    """柱状图：各算法在某指标上的对比"""
    fig, ax = plt.subplots()
    algos = df['algorithm'].unique()
    values = [df[df['algorithm'] == a][metric].mean() for a in algos]
    colors = [ALGO_COLORS[a] for a in algos]
    ax.bar([ALGO_LABELS[a] for a in algos], values, color=colors)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)

def plot_line_over_time(data: dict, xlabel: str, ylabel: str,
                        title: str, save_path: str) -> None:
    """折线图：指标随时间变化"""
    fig, ax = plt.subplots()
    for algo, series in data.items():
        ax.plot(series['step'], series['value'], label=ALGO_LABELS[algo],
                color=ALGO_COLORS[algo])
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)

def plot_trajectory(fcd_path: str, save_path: str) -> None:
    """时空轨迹图：从 traj.xml (fcd-output) 绘制车辆轨迹"""
    ...

def plot_improvement_heatmap(df: pd.DataFrame, save_path: str) -> None:
    """热力图：20 路口 × 各指标的改进百分比"""
    ...

def plot_queue_distribution(df: pd.DataFrame, save_path: str) -> None:
    """箱线图：各算法排队长度分布"""
    ...
```

**验证：**
```bash
python -c "from visualization.plots import *; import pandas as pd; import numpy as np; df = pd.DataFrame({'algorithm': ['fixed_time','rule_adaptive','ca_max_pressure']*10, 'avg_delay': np.random.rand(30)*100}); plot_bar_comparison(df, 'avg_delay', '测试', '延迟(s)', 'demo/assets/charts/test_bar.png'); print('OK')"
# 预期输出：OK，且 demo/assets/charts/test_bar.png 存在、中文正常显示
```

### Day 3（7/22 周二）— 时空轨迹图方案

- [ ] 理解 SUMO fcd-output 格式（`traj.xml`），确认字段：time, vehicle id, x, y, speed
- [ ] 设计时空轨迹图：X 轴=时间(s)，Y 轴=沿行驶方向距离，颜色=速度（红慢绿快）
- [ ] 用路口 1 已有的 `traj.xml` 生成一张轨迹图，验证渲染效果
- [ ] 此图为 PDF 明确要求的"时空轨迹图"，优先级最高

```python
# 测试脚本：scripts/test_trajectory.py
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np

tree = ET.parse('data/intersection_data/1/sumo工程/traj.xml')
root = tree.getroot()

traces = {}  # vehicle_id -> [(time, position, speed), ...]
for ts in root.findall('timestep'):
    t = float(ts.get('time'))
    for veh in ts.findall('vehicle'):
        vid = veh.get('id')
        x, y, speed = float(veh.get('x')), float(veh.get('y')), float(veh.get('speed'))
        traces.setdefault(vid, []).append((t, np.hypot(x, y), speed))

fig, ax = plt.subplots(figsize=(12, 6))
norm = plt.Normalize(0, 14)
for vid, pts in list(traces.items())[:20]:  # 取前 20 辆车
    times = [p[0] for p in pts]
    pos = [p[1] for p in pts]
    speeds = [p[2] for p in pts]
    ax.scatter(times, pos, c=speeds, cmap='RdYlGn', norm=norm, s=2)
ax.set_xlabel('时间 (s)')
ax.set_ylabel('位置 (m)')
ax.set_title('时空轨迹图 — 路口 1')
fig.savefig('demo/assets/charts/trajectory_intersection1.png', dpi=300)
print('OK')
```

**验证：**
```bash
python scripts/test_trajectory.py
# 预期输出：OK，demo/assets/charts/trajectory_intersection1.png 生成且颜色映射正确
```

### Day 4（7/23 周三）— PyQt 看板可行性测试

- [ ] 安装 PyQt5（`pip install PyQt5`），确认 Matplotlib 嵌入正常显示
- [ ] 运行测试脚本，验证中文渲染和窗口显示
- [ ] 如果 PyQt5 安装有问题，记录备选方案（Matplotlib `animation.FuncAnimation`）
- [ ] 记录可行性结论，W4 正式实现

```python
# scripts/test_dashboard.py
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np

class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CA-MP 实时监控")
        self.figure = Figure(figsize=(12, 8))
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self._init_plots()

    def _init_plots(self):
        ax1 = self.figure.add_subplot(2, 1, 1)
        ax1.set_title('各进口道压力实时曲线')
        ax2 = self.figure.add_subplot(2, 1, 2)
        ax2.set_title('排队长度')
        self.figure.tight_layout()
        self.canvas.draw()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dash = Dashboard()
    dash.show()
    sys.exit(app.exec_())
```

**验证：**
```bash
python scripts/test_dashboard.py
# 预期：弹出窗口标题 "CA-MP 实时监控"，两个子图正常显示中文标题，无报错
# 如果 PyQt5 不可用：pip install PyQt5 后重试；仍失败则记录备选方案
```

### Day 5（7/24 周四）— 视频脚本初稿

- [ ] 创建 `demo/视频脚本.md`，按 6 段结构编写 7 分钟脚本（问题引入→方案概述→系统演示→数据说话→云端协同→总结）
- [ ] 与 DA 确认脚本内容与 PPT 结构一致
- [ ] 确定旁白方式：真人录音 / AI 配音 / 纯字幕

**验证：**
```bash
# 确认文件存在且包含 6 个时间段标记
grep -c "##" demo/视频脚本.md
# 预期输出：>= 6（6 个段落标题）
```

### Day 6（7/25 周五）— ffmpeg 视频处理测试

- [ ] 安装 ffmpeg（https://ffmpeg.org/download.html），确认命令行可用
- [ ] 测试视频裁剪、拼接、添加字幕、调整分辨率四项操作
- [ ] 确认 OBS 输出格式与 ffmpeg 兼容
- [ ] 如不用 ffmpeg，确认剪映/Premiere 可用

```bash
# 裁剪
ffmpeg -i input.mp4 -ss 00:01:30 -to 00:03:30 -c copy output_clip.mp4
# 拼接
ffmpeg -f concat -safe 0 -i filelist.txt -c copy output_merged.mp4
# 添加字幕
ffmpeg -i input.mp4 -vf subtitles=sub.srt output_sub.mp4
# 调整分辨率
ffmpeg -i input.mp4 -vf scale=1920:1080 output_1080p.mp4
```

**验证：**
```bash
ffmpeg -version
# 预期输出：ffmpeg version x.x.x ...
ffmpeg -i demo/assets/recordings/test_30s.mp4 -ss 00:00:05 -to 00:00:15 -c copy demo/assets/recordings/test_clip.mp4
ffprobe -v quiet -show_entries format=duration demo/assets/recordings/test_clip.mp4
# 预期：duration≈10.0
```

### Day 7（7/26 周六）— Buffer / 素材整理

- [ ] 整理 `demo/assets/` 目录结构（background/、screenshots/、charts/、recordings/）
- [ ] 检查本周所有产出文件完整性
- [ ] 提交 W1 产出给 TL

**验证：**
```bash
ls demo/assets/
# 预期输出包含：background  charts  recordings  screenshots
ls demo/视频脚本.md
# 预期：文件存在
```

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 录屏方案确认 | 7/20 | OBS/ffmpeg 可用，录 30 秒测试视频（1080p, 30fps） |
| `visualization/plots.py` | 7/21 | 5 种图表函数定义 + 假数据测试通过，中文正常 |
| 时空轨迹图测试 | 7/22 | 用路口 1 的 traj.xml 生成一张轨迹图，颜色映射正确 |
| PyQt 可行性结论 | 7/23 | 确认能做/不能做，备选方案明确 |
| `demo/视频脚本.md` | 7/24 | 7 分钟脚本完整，6 段结构 |
| ffmpeg 测试通过 | 7/25 | 裁剪/拼接/字幕/缩放操作可用 |

## 协作对接

- 与 TL 确认录屏方案选择（Day 1 结束时汇报）
- 与 DA 对齐视频脚本与 PPT 结构（Day 5）
- 录屏时 SUMO-GUI 窗口大小固定为 1920×1080，避免后期缩放模糊
