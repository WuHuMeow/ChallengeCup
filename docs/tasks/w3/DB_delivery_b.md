# 交付 B（DB） W3 任务书

> 周期：8/3（周日）- 8/9（周六） | 核心目标：批量生成实验图表、录制重点路口视频素材

## 每日任务

### Day 1（8/3 周日）— 完善批量生成函数

- [ ] 完善 `visualization/plots.py` 中的 `generate_all_charts()` 函数，覆盖 6 类图表
- [ ] 用 W2 的预跑数据测试批量生成，确认无报错
- [ ] 确认输出目录 `demo/assets/charts/` 中文件命名规范

```python
def generate_all_charts(metrics_csv: str, output_dir: str):
    """一键生成所有报告/PPT 用图表"""
    df = pd.read_csv(metrics_csv)
    # 1. 20 路口 × 3 算法 行程时间柱状图
    # 2. 20 路口 × 3 算法 排队长度柱状图
    # 3. 改进百分比热力图
    # 4. 路口 16 专项对比图
    # 5. 时空轨迹图（路口 16）
    # 6. 指标随时间变化曲线（路口 16）
    for i in range(1, 21):
        sub = df[df['intersection_id'] == i]
        plot_bar_comparison(sub, 'avg_delay', f'路口 {i} 行程时间对比',
                           '行程时间 (s)', f'{output_dir}/bar_delay_i{i}.png')
        plot_bar_comparison(sub, 'avg_queue_length', f'路口 {i} 排队长度对比',
                           '排队长度 (veh)', f'{output_dir}/bar_queue_i{i}.png')
    plot_improvement_heatmap(df, f'{output_dir}/improvement_heatmap.png')
    print(f'Generated charts for 20 intersections -> {output_dir}')
```

**验证：**
```bash
python scripts/batch_charts.py
# 预期输出：Generated charts for 20 intersections -> demo/assets/charts/
dir demo\assets\charts\bar_delay_i*.png | find /c ".png"
# 预期：20
```

### Day 2（8/4 周一）— 第一批正式图表

- [ ] 收到 EX 的初步聚合数据后，生成 20 路口行程时间对比柱状图
- [ ] 生成 20 路口排队长度对比柱状图
- [ ] 生成 CA-MP 改进百分比热力图
- [ ] 输出到 `demo/assets/charts/`（PNG 300dpi + SVG），发给 DA 插入报告

```python
import pandas as pd
from visualization.plots import plot_bar_comparison, plot_improvement_heatmap

df = pd.read_csv('output/csv/all_results.csv')

# 热力图：20 路口 × 各指标改进百分比
plot_improvement_heatmap(df, 'demo/assets/charts/improvement_heatmap.png')
plot_improvement_heatmap(df, 'demo/assets/charts/improvement_heatmap.svg')
```

**验证：**
```bash
python -c "import os; files = [f for f in os.listdir('demo/assets/charts') if f.startswith('bar_')]; print(f'{len(files)} bar charts'); assert len(files) >= 40"
# 预期：>= 40 bar charts（20 路口 × 2 指标）
```

### Day 3（8/5 周二）— 路口 16 专项图表

- [ ] 生成路口 16 时空轨迹图（从 `traj.xml`）
- [ ] 生成路口 16 排队长度随时间变化曲线（从 `simulation_log.csv`）
- [ ] 在曲线图中标注溢出门控触发时刻（垂直虚线）
- [ ] 生成路口 16 三算法行程时间对比柱状图

```python
import pandas as pd
import matplotlib.pyplot as plt
from visualization.plots import plot_trajectory, ALGO_COLORS, ALGO_LABELS

# 时空轨迹图
plot_trajectory('data/intersection_data/16/sumo工程/traj.xml',
                'demo/assets/charts/trajectory_intersection16.png')

# 排队长度曲线 + 溢出门控标注
df = pd.read_csv('output/csv/simulation_log_i16.csv')
fig, ax = plt.subplots(figsize=(12, 5))
for algo in df['algorithm'].unique():
    sub = df[df['algorithm'] == algo]
    ax.plot(sub['step'], sub['avg_queue_length'],
            label=ALGO_LABELS[algo], color=ALGO_COLORS[algo])
# 标注溢出门控触发
overflow_steps = df[(df['algorithm'] == 'ca_max_pressure') & (df['overflow_gate'] == 1)]['step']
for s in overflow_steps:
    ax.axvline(x=s, color='gray', linestyle='--', alpha=0.5)
ax.set_xlabel('仿真步 (step)')
ax.set_ylabel('平均排队长度 (veh)')
ax.set_title('路口 16 排队长度随时间变化')
ax.legend()
fig.savefig('demo/assets/charts/queue_time_i16.png', dpi=300)
plt.close(fig)
print('OK')
```

**验证：**
```bash
python -c "import os; assert os.path.exists('demo/assets/charts/trajectory_intersection16.png'); assert os.path.exists('demo/assets/charts/queue_time_i16.png'); print('OK')"
# 预期输出：OK
```

### Day 4（8/6 周三）— 全量数据更新图表

- [ ] 全量数据到齐后，重新运行批量生成脚本更新所有图表为最终版
- [ ] 生成 PPT 用图表（更大字号 figsize=(12,7)、fontsize=14、简洁图例）
- [ ] 生成报告用图表（更详细、含误差棒 errorbar）

```python
# 报告用图表：含误差棒
def plot_bar_with_error(df, metric, title, ylabel, save_path):
    fig, ax = plt.subplots(figsize=(10, 6))
    algos = df['algorithm'].unique()
    means = [df[df['algorithm'] == a][metric].mean() for a in algos]
    stds = [df[df['algorithm'] == a][metric].std() for a in algos]
    colors = [ALGO_COLORS[a] for a in algos]
    ax.bar([ALGO_LABELS[a] for a in algos], means, yerr=stds,
           color=colors, capsize=5)
    ax.set_title(title, fontsize=14)
    ax.set_ylabel(ylabel, fontsize=12)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300)
    plt.close(fig)
```

**验证：**
```bash
python scripts/batch_charts.py
# 预期：所有图表更新为全量数据版本，无报错
```

### Day 5（8/7 周四）— 录制路口 16 视频素材

- [ ] SUMO-GUI 打开口 16，运行 FixedTime 3600 步，OBS 录屏
- [ ] SUMO-GUI 打开口 16，运行 CA-MP 3600 步，OBS 录屏
- [ ] 确保录屏中能看到：短边排队、溢出门控触发、信号切换
- [ ] 录制路口 1 的对比素材（备选）

```bash
# 固定配时
sumo-gui -c data/intersection_data/16/sumo工程/demo_16.sumocfg --start
# CA-MP
python experiments/runner.py --intersection 16 --algo ca_maxpressure --gui --steps 3600
```

**验证：**
```bash
ffprobe -v quiet -show_entries stream=width,height,r_frame_rate -show_entries format=duration demo/assets/recordings/fixed_time_i16.mp4
# 预期：width=1920, height=1080, r_frame_rate=30/1, duration > 60s
ffprobe -v quiet -show_entries format=duration demo/assets/recordings/ca_mp_i16.mp4
# 预期：duration > 60s
```

### Day 6（8/8 周五）— 动态可视化动画

- [ ] 用 `simulation_log.csv` 生成排队长度实时变化动画（MP4，10-15 秒）
- [ ] 生成压力值变化动画，用于视频"云-边-端协同"段落
- [ ] 整理所有素材到 `demo/assets/`

```python
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

df = pd.read_csv('output/csv/simulation_log_i16.csv')
ca = df[df['algorithm'] == 'ca_max_pressure']

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
line_q, = ax1.plot([], [], color='#2ECC71')
line_p, = ax2.plot([], [], color='#3498DB')
ax1.set_ylabel('排队长度 (veh)'); ax1.set_title('路口 16 排队长度变化')
ax2.set_ylabel('压力值'); ax2.set_title('路口 16 压力值变化')
ax1.set_xlim(0, len(ca)); ax2.set_xlim(0, len(ca))
ax1.set_ylim(0, ca['avg_queue_length'].max() * 1.1)
ax2.set_ylim(ca['pressure'].min(), ca['pressure'].max() * 1.1)

def update(frame):
    line_q.set_data(ca['step'][:frame], ca['avg_queue_length'][:frame])
    line_p.set_data(ca['step'][:frame], ca['pressure'][:frame])
    return line_q, line_p

ani = FuncAnimation(fig, update, frames=range(0, len(ca), 5), interval=30)
ani.save('demo/assets/charts/animation_i16.mp4', writer='ffmpeg', fps=30, dpi=150)
print('OK')
```

**验证：**
```bash
ffprobe -v quiet -show_entries format=duration demo/assets/charts/animation_i16.mp4
# 预期：duration 10-15s
```

### Day 7（8/9 周六）— Buffer / 素材确认

- [ ] 修复本周图表/视频中发现的问题
- [ ] 与 DA 确认：报告中需要哪些图、PPT 中需要哪些图
- [ ] 提交所有素材给 TL

**验证：**
```bash
dir demo\assets\charts\ | find /c ".png"
# 预期：>= 45 个 PNG 文件（20 路口 × 2 指标 + 热力图 + 路口 16 专项）
```

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 批量图表生成脚本 | 8/3 | 一键生成 20 路口所有图表，无报错 |
| 20 路口对比图表 | 8/4 | 柱状图 × 40 + 热力图，PNG+SVG |
| 路口 16 专项图表 | 8/5 | 轨迹图 + 排队曲线（含门控标注）+ 对比柱状图 |
| 最终版图表（全量数据） | 8/6 | 含误差棒（报告版）+ 大字号（PPT 版） |
| 路口 16 录屏 × 2 | 8/7 | FixedTime + CA-MP，1080p 30fps |
| 动态可视化动画 | 8/8 | 排队/压力变化 MP4 动画 |

## 协作对接

- 与 EX 对接获取初步聚合数据和全量数据（Day 2、Day 4）
- 与 DA 确认报告/PPT 图表需求清单（Day 7）
- 路口 16 录屏需确认 SUMO 工程文件可用（与 IB 确认）
