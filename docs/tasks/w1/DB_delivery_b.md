# W1 任务书：交付 B（DB）

> 周期：7/20（周日）- 7/26（周六）
> 核心目标：确定录屏方案、测试可视化工具链、准备视频制作流程

---

## 背景

你负责所有视觉交付物：Matplotlib 实验图表、PyQt 实时看板（可选加分项）、5-8 分钟演示视频的录制与剪辑。W1 的任务是"磨刀"——把工具链跑通，W3 实验数据一出就能立刻出图，W5 直接录视频。

PDF 评分标准中"团队展示与综合表现"占 15 分，视频是核心得分项。

---

## 每日任务

### Day 1（7/20 周日）

**SUMO-GUI 录屏方案验证**
1. 安装 OBS Studio（免费录屏软件）：https://obsproject.com/
2. 用 SUMO-GUI 打开口 1：
   ```bash
   sumo-gui -c intersection_data/1/sumo工程/demo_1.sumocfg --start
   ```
3. 测试 OBS 录制 SUMO-GUI 窗口：
   - 录制 30 秒仿真运行
   - 检查：帧率是否流畅（≥30fps）、窗口是否完整、有无卡顿
4. 测试 SUMO 自带截图功能：
   - SUMO-GUI 菜单 → Edit → Screenshot → 保存当前帧
   - 或用命令行：`sumo-gui --save-screen`（如果版本支持）
5. 确定录屏方案：
   - **方案 A（推荐）**：OBS 录制 SUMO-GUI 窗口，输出 1080p MP4
   - **方案 B**：SUMO 逐帧截图 + ffmpeg 合成视频
   - 记录选择结果，告知 TL

### Day 2（7/21 周一）

**Matplotlib 图表样式设计**
1. 创建 `src/visualization/plots.py`，定义统一图表样式：

```python
"""实验结果图表生成（Matplotlib）"""
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd

# 全局样式设置
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']  # 中文显示
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.dpi'] = 150
matplotlib.rcParams['savefig.dpi'] = 300
matplotlib.rcParams['figure.figsize'] = (10, 6)

# 算法配色方案
ALGO_COLORS = {
    'fixed_time': '#E74C3C',      # 红色
    'actuated': '#F39C12',        # 橙色
    'ca_maxpressure': '#2ECC71',  # 绿色
}

ALGO_LABELS = {
    'fixed_time': '固定配时',
    'actuated': '感应控制',
    'ca_maxpressure': 'CA-MP（本文）',
}


def plot_bar_comparison(df: pd.DataFrame, metric: str, title: str,
                        ylabel: str, save_path: str) -> None:
    """柱状图：各算法在某指标上的对比"""
    ...


def plot_line_over_time(data: dict, xlabel: str, ylabel: str,
                        title: str, save_path: str) -> None:
    """折线图：指标随时间变化"""
    ...


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

2. 用假数据测试每种图表类型能否正常渲染（中文显示、配色、保存）
3. 确认图表保存为 PNG（300dpi）和 SVG（矢量，PPT 用）

### Day 3（7/22 周二）

**时空轨迹图方案**
1. 理解 SUMO fcd-output 格式（`traj.xml`）：
   ```xml
   <timestep time="1.00">
     <vehicle id="EW_car.0" x="123.45" y="678.90" angle="90.00" speed="13.89" .../>
     <vehicle id="SN_car.0" x="234.56" y="789.01" angle="180.00" speed="10.50" .../>
   </timestep>
   ```
2. 设计时空轨迹图：
   - X 轴：时间（秒）
   - Y 轴：车辆位置（沿行驶方向的距离）
   - 每条线 = 一辆车的轨迹
   - 颜色 = 速度（红=慢/堵，绿=快/畅）
3. 写一个测试脚本，用路口 1 已有的 `traj.xml` 生成一张轨迹图
4. 这张图是 PDF 明确要求的"时空轨迹图"——必须做好

### Day 4（7/23 周三）

**PyQt 看板可行性测试**
1. 测试 PyQt5 + Matplotlib 嵌入：
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
           # 子图1：各进口道压力实时曲线
           # 子图2：当前相位 + 绿灯倒计时
           # 子图3：排队长度柱状图
           ...

       def update(self, status):
           """每仿真步调用，刷新图表"""
           ...

   app = QApplication(sys.argv)
   dash = Dashboard()
   dash.show()
   sys.exit(app.exec_())
   ```
2. 确认：
   - PyQt5 是否已安装（`pip install PyQt5`）
   - Matplotlib 嵌入是否正常显示
   - 中文是否正常
3. 如果 PyQt5 安装有问题，备选方案：用 Matplotlib 的 `animation.FuncAnimation` 做动态图
4. 记录可行性结论，W4 正式实现

### Day 5（7/24 周四）

**视频脚本初稿**
1. 创建 `demo/视频脚本.md`：

```markdown
# 演示视频脚本（7 分钟）

## 0:00-0:45 | 问题引入
- 画面：雄安新区路网规划图 + 窄路实景
- 旁白："雄安新区采用'窄路密网'规划理念，路口间距短、车道容量低..."
- 字幕：关键数据（24m 短边、4 辆车排满）

## 0:45-1:30 | 方案概述
- 画面：云-边-端架构图动画（PPT 导出）
- 旁白："我们提出 CA-MP 算法，通过容量归一化、溢出门控、云端协调..."
- 字幕：三个创新点关键词

## 1:30-3:30 | 系统演示
- 画面：SUMO-GUI 录屏，左右分屏对比
  - 左：固定配时（车辆排队、堵死）
  - 右：CA-MP（车辆顺畅通过）
- 旁白："左侧为传统固定配时，右侧为 CA-MP..."
- 字幕：实时指标（排队长度、通过车辆数）

## 3:30-5:00 | 数据说话
- 画面：指标对比图表动画（柱状图、折线图依次出现）
- 旁白："在 20 个路口上，CA-MP 平均行程时间降低 XX%..."
- 字幕：关键数字

## 5:00-6:00 | 云-边-端协同
- 画面：消息流可视化（V2X → Edge → Cloud 动画）
- 旁白："车辆通过 V2X 上报状态，边缘节点实时决策，云端周期调参..."

## 6:00-7:00 | 总结
- 画面：创新点总结 + 团队成员
- 旁白："总结三个创新点...未来工作..."
```

2. 与 DA 确认脚本内容与 PPT 结构一致
3. 确定旁白方式：真人录音 / AI 配音 / 纯字幕

### Day 6（7/25 周五）

**ffmpeg 视频处理测试**
1. 安装 ffmpeg：https://ffmpeg.org/download.html
2. 测试基本操作：
   - 视频裁剪：`ffmpeg -i input.mp4 -ss 00:01:30 -to 00:03:30 -c copy output.mp4`
   - 视频拼接：`ffmpeg -f concat -i filelist.txt -c copy output.mp4`
   - 添加字幕：`ffmpeg -i input.mp4 -vf subtitles=sub.srt output.mp4`
   - 调整分辨率：`ffmpeg -i input.mp4 -vf scale=1920:1080 output.mp4`
3. 确认 OBS 输出格式与 ffmpeg 兼容
4. 如果不用 ffmpeg，确认剪映/Premiere 是否可用

### Day 7（7/26 周六）

**Buffer / 素材整理**
1. 整理 `demo/assets/` 目录结构：
   ```
   demo/
   ├── assets/
   │   ├── background/     # 雄安背景图
   │   ├── screenshots/    # SUMO-GUI 截图
   │   ├── charts/         # Matplotlib 图表（W3 产出）
   │   └── recordings/     # 录屏原始文件（W5 产出）
   ├── 视频脚本.md
   ├── 演示方案.md
   └── output/             # 最终视频输出
   ```
2. 提交 W1 产出给 TL

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 录屏方案确认 | 7/20 | OBS/ffmpeg 可用，录 30 秒测试视频 |
| 2 | `src/visualization/plots.py` | 7/21 | 5 种图表函数定义 + 假数据测试通过 |
| 3 | 时空轨迹图测试 | 7/22 | 用路口 1 的 traj.xml 生成一张轨迹图 |
| 4 | PyQt 可行性结论 | 7/23 | 确认能做/不能做，备选方案明确 |
| 5 | `demo/视频脚本.md` | 7/24 | 7 分钟脚本完整 |
| 6 | ffmpeg 测试通过 | 7/25 | 裁剪/拼接/字幕操作可用 |

---

## 注意事项

- W1 是"磨刀"阶段——不产出最终内容，只确保工具链可用
- Matplotlib 中文显示是常见坑——Day 2 必须验证 SimHei/Microsoft YaHei 可用
- 时空轨迹图是 PDF 明确要求的，优先级最高
- PyQt 看板是加分项，如果 W4 时间不够可以砍掉
- 视频最终用剪映/Premiere 剪辑（你会），ffmpeg 只做预处理
- 录屏时 SUMO-GUI 窗口大小固定为 1920×1080，避免后期缩放模糊
