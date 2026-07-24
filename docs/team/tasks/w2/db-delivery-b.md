# 交付 B（DB） W2 任务书

> 周期：7/27（周日）- 8/2（周六） | 核心目标：用真实数据生成第一批图表、测试视频录制流程

## 每日任务

### Day 1（7/27 周日）— 时空轨迹图正式生成

- [ ] 调用 `visualization/plots.py` 中的 `plot_trajectory()` 生成路口 1 时空轨迹图
- [ ] 输出到 `demo/assets/charts/trajectory_intersection1.png`（300dpi）
- [ ] 检查中文标签、颜色映射（红=慢/堵，绿=快/畅）、坐标轴是否正确
- [ ] 如果 traj.xml 格式与预期不同，调整解析逻辑

```python
# 调用示例
from visualization.plots import plot_trajectory
plot_trajectory(
    fcd_path='data/intersection_data/1/sumo工程/traj.xml',
    save_path='demo/assets/charts/trajectory_intersection1.png'
)
```

**验证：**
```bash
python -c "from visualization.plots import plot_trajectory; plot_trajectory('data/intersection_data/1/sumo工程/traj.xml', 'demo/assets/charts/trajectory_intersection1.png'); print('OK')"
# 预期输出：OK，文件存在且 >= 100KB（300dpi PNG）
dir demo\assets\charts\trajectory_intersection1.png
```

### Day 2（7/28 周一）— 对比柱状图生成

- [ ] 用 TL 发来的路口 1 对比数据（`output/csv/`）生成柱状图：三算法平均行程时间对比
- [ ] 生成柱状图：三算法平均排队长度对比
- [ ] 输出到 `demo/assets/charts/`（PNG 300dpi + SVG）
- [ ] 将图表插入 DA 的 PPT 模板，调整配色、字号、图例位置确保投影清晰

```python
import pandas as pd
from visualization.plots import plot_bar_comparison

df = pd.read_csv('output/csv/intersection_1_results.csv')
plot_bar_comparison(df, metric='avg_delay', title='路口 1 平均行程时间对比',
                    ylabel='行程时间 (s)', save_path='demo/assets/charts/bar_delay_i1.png')
plot_bar_comparison(df, metric='avg_queue_length', title='路口 1 平均排队长度对比',
                    ylabel='排队长度 (veh)', save_path='demo/assets/charts/bar_queue_i1.png')
```

**验证：**
```bash
python -c "import os; assert os.path.exists('demo/assets/charts/bar_delay_i1.png'); assert os.path.exists('demo/assets/charts/bar_queue_i1.png'); print('OK')"
# 预期输出：OK
```

### Day 3（7/29 周二）— 录制第一段测试视频

- [ ] 用 SUMO-GUI 打开口 1，运行固定配时 3600 步，OBS 录制全过程（delay=0 加速）
- [ ] 运行 CA-MP 版本并录制：`python experiments/runner.py --intersection 1 --algo ca_maxpressure --gui --steps 3600`
- [ ] 输出 `demo/assets/recordings/test_fixed_time_i1.mp4` 和 `test_ca_mp_i1.mp4`
- [ ] 检查两段视频：画面流畅、信号灯切换可见、无卡顿

**验证：**
```bash
ffprobe -v quiet -show_entries format=duration -show_entries stream=width,height demo/assets/recordings/test_fixed_time_i1.mp4
# 预期：duration > 30s, width=1920, height=1080
ffprobe -v quiet -show_entries format=duration demo/assets/recordings/test_ca_mp_i1.mp4
# 预期：duration > 30s
```

### Day 4（7/30 周三）— 视频剪辑流程测试

- [ ] 用剪映/Premiere 将两段视频左右拼接（同屏对比）
- [ ] 添加简单字幕："左：固定配时 / 右：CA-MP"
- [ ] 输出 30 秒测试片段到 `demo/assets/recordings/test_split_screen.mp4`
- [ ] 确认剪辑工具能处理 OBS 输出格式；如拼接困难，备选：分别录制 + 画中画

**验证：**
```bash
ffprobe -v quiet -show_entries format=duration demo/assets/recordings/test_split_screen.mp4
# 预期：duration ≈ 30s，画面为左右分屏
```

### Day 5（7/31 周四）— 动态曲线图测试

- [ ] 用 IB 的 `simulation_log.csv` 生成"排队长度随时间变化"折线图
- [ ] 生成"压力值随时间变化"折线图，输出静态图到 `demo/assets/charts/`
- [ ] 测试 Matplotlib 动画（FuncAnimation）：将排队曲线做成 10 秒动画 GIF
- [ ] 评估动画 GIF 是否可用于视频素材

```python
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

df = pd.read_csv('output/csv/simulation_log.csv')

# 静态折线图
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(df['step'], df['avg_queue_length'], color='#2ECC71', label='CA-MP')
ax.set_xlabel('仿真步 (step)')
ax.set_ylabel('平均排队长度 (veh)')
ax.set_title('排队长度随时间变化')
ax.legend()
fig.savefig('demo/assets/charts/queue_over_time_i1.png', dpi=300)

# 动画 GIF
fig2, ax2 = plt.subplots()
line, = ax2.plot([], [], color='#2ECC71')
ax2.set_xlim(0, len(df))
ax2.set_ylim(0, df['avg_queue_length'].max() * 1.1)

def update(frame):
    line.set_data(df['step'][:frame], df['avg_queue_length'][:frame])
    return line,

ani = FuncAnimation(fig2, update, frames=range(0, len(df), 10), interval=50)
ani.save('demo/assets/charts/queue_animation.gif', writer='pillow', fps=20)
print('OK')
```

**验证：**
```bash
python -c "import os; assert os.path.exists('demo/assets/charts/queue_over_time_i1.png'); assert os.path.exists('demo/assets/charts/queue_animation.gif'); print('OK')"
# 预期输出：OK
```

### Day 6（8/1 周五）— 素材整理与对接

- [ ] 整理 `demo/assets/` 目录：charts/ 放图表，recordings/ 放录屏
- [ ] 统一命名规范：`{类型}_{路口}_{算法}_{日期}.png/mp4`
- [ ] 与 DA 确认哪些图表需要放入报告/PPT
- [ ] 提交本周产出给 TL

**验证：**
```bash
dir demo\assets\charts\
# 预期：包含 trajectory_intersection1.png, bar_delay_i1.png, bar_queue_i1.png, queue_over_time_i1.png 等
dir demo\assets\recordings\
# 预期：包含 test_fixed_time_i1.mp4, test_ca_mp_i1.mp4, test_split_screen.mp4
```

### Day 7（8/2 周六）— Buffer / 批量生成脚本准备

- [ ] 修复本周图表/视频中发现的问题
- [ ] 设计视频转场动画方案（PPT 导出为视频片段？）
- [ ] 编写 W3 图表批量生成脚本骨架：输入 results DataFrame → 输出 20 路口 × 4 指标对比图表

```python
# scripts/batch_charts.py（骨架）
import pandas as pd
from visualization.plots import (plot_bar_comparison, plot_improvement_heatmap,
                                  plot_line_over_time, plot_trajectory)

def generate_all_charts(metrics_csv: str, output_dir: str):
    """一键生成所有报告/PPT 用图表"""
    df = pd.read_csv(metrics_csv)
    for i in range(1, 21):
        sub = df[df['intersection_id'] == i]
        plot_bar_comparison(sub, 'avg_delay', f'路口 {i} 行程时间对比',
                           '行程时间 (s)', f'{output_dir}/bar_delay_i{i}.png')
        plot_bar_comparison(sub, 'avg_queue_length', f'路口 {i} 排队长度对比',
                           '排队长度 (veh)', f'{output_dir}/bar_queue_i{i}.png')
    plot_improvement_heatmap(df, f'{output_dir}/improvement_heatmap.png')
    print(f'All charts saved to {output_dir}')

if __name__ == '__main__':
    generate_all_charts('output/csv/all_results.csv', 'demo/assets/charts/')
```

**验证：**
```bash
python scripts/batch_charts.py
# 预期输出：All charts saved to demo/assets/charts/（W3 有真实数据后验证）
# 本周仅确认脚本无语法错误：
python -c "import ast; ast.parse(open('scripts/batch_charts.py').read()); print('syntax OK')"
```

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 时空轨迹图（路口 1） | 7/27 | 中文正常、颜色映射正确、300dpi PNG |
| 对比柱状图（路口 1） | 7/28 | 三算法对比清晰，PNG + SVG 双格式 |
| 测试录屏 × 2 | 7/29 | 固定配时 + CA-MP 各一段，1080p 流畅 |
| 同屏对比测试片段 | 7/30 | 30 秒左右拼接视频，含字幕 |
| 动态曲线图测试 | 7/31 | 排队/压力折线图 + 动画 GIF |
| 图表批量生成脚本 | 8/2 | 语法正确，一键生成 20 路口图表逻辑完整 |

## 协作对接

- 与 TL 对接获取路口 1 对比数据（Day 2 前）
- 与 IB 确认 `simulation_log.csv` 的列名和格式（Day 5）
- 与 DA 确认报告/PPT 需要哪些图表（Day 6）
