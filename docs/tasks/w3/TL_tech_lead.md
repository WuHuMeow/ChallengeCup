# Tech Lead W3 任务书

> 周期：8/3–8/9 | 核心目标：全量实验顺利运行，180 组原始流量实验完成，数据质量确认

## 每日任务

### Day 1（8/3）

- [ ] 确认 W2 预跑结果（路口 1-10 原始流量）无异常数据
- [ ] 启动路口 11-20 × 3 算法 × 原始流量 × 3 种子 = 90 组实验
- [ ] 监控运行状态，处理失败实验（记录失败路口和原因）
- [ ] 确认输出 CSV 目录结构正确

启动批量实验：

```python
from experiments.runner import run_batch
from core.types import TrafficLevel

# 原始流量全量跑批（20 路口 × 3 算法 × 3 种子 = 180 组）
results = run_batch(
    levels=[TrafficLevel.NORMAL],
    steps=3600,
)
# 输出路径格式：output/csv/{路口}_{level}_{算法}_s{seed}.csv
# 例如：output/csv/16_normal_ca_maxpressure_s42.csv
```

**验证：** `ls output/csv/ | wc -l` → 文件数持续增长（目标 180 个）

### Day 2（8/4）

- [ ] 检查实验进度：目标完成 180/360 组（原始流量部分）
- [ ] Review DB 产出的图表质量：配色是否统一、坐标轴标注是否清晰、分辨率 ≥ 300dpi
- [ ] Review DA 的报告初稿（第一/二/三章），提出修改意见
- [ ] 将修改意见整理为清单发给 DA 和 DB

检查进度：

```python
import os
csv_dir = "output/csv"
normal_files = [f for f in os.listdir(csv_dir) if "normal" in f]
print(f"原始流量已完成: {len(normal_files)}/180")
```

**验证：** `ls output/csv/ | grep "normal" | wc -l` → ≥ 90（原始流量已完成过半）

### Day 3（8/5）

- [ ] 继续监控实验运行，处理失败实验
- [ ] 抽查 3-5 个路口的实验结果：CA-MP 的 avg_queue_length 是否低于 FixedTime
- [ ] 如某路口 CA-MP 效果不佳，与 AB 分析原因
- [ ] 记录异常路口编号和初步原因

抽查对比：

```python
import pandas as pd

for iid in ["5", "10", "16"]:
    ft = pd.read_csv(f"output/csv/{iid}_normal_fixed_time_s42.csv")
    ca = pd.read_csv(f"output/csv/{iid}_normal_ca_maxpressure_s42.csv")
    diff = ft["avg_queue_length"].mean() - ca["avg_queue_length"].mean()
    status = "✓ CA-MP 更优" if diff > 0 else "✗ CA-MP 更差"
    print(f"路口 {iid}: FixedTime={ft['avg_queue_length'].mean():.2f}, "
          f"CA-MP={ca['avg_queue_length'].mean():.2f} → {status}")
```

**验证：** 随机抽取一个 CSV，`python -c "import pandas as pd; df = pd.read_csv('output/csv/5_normal_ca_maxpressure_s42.csv'); print(df['avg_queue_length'].mean())"` → 输出合理数值（非 NaN、非 0）

### Day 4（8/6）

- [ ] 确认原始流量 180 组实验全部完成
- [ ] 用 `experiments/metrics.py` 汇总全部结果
- [ ] 生成汇总对比表：20 路口 × 6 指标 × 3 算法
- [ ] 将完整数据发给 DA（报告）和 DB（图表）

生成汇总表：

```python
import pandas as pd, os

rows = []
for f in os.listdir("output/csv"):
    if "normal" not in f or not f.endswith(".csv"):
        continue
    df = pd.read_csv(f"output/csv/{f}")
    parts = f.replace(".csv", "").split("_")
    rows.append({
        "intersection": parts[0],
        "algorithm": "_".join(parts[2:-1]),  # 处理 ca_maxpressure 含下划线
        "seed": parts[-1].replace("s", ""),
        "avg_queue": df["avg_queue_length"].mean(),
        "avg_delay": df["avg_delay"].mean(),
        "throughput": df["total_throughput"].sum(),
        "fuel": df["fuel_consumption"].sum(),
    })
summary = pd.DataFrame(rows)
summary.to_csv("output/summary_normal.csv", index=False)
print(f"汇总表: {len(summary)} 行")
```

CSV 文件的列结构（由 `engine/collector.py` 生成）：

```
step, timestamp, tls_id, current_phase,
avg_queue_length, max_queue_length, avg_delay,
total_throughput, avg_travel_time, total_stops, fuel_consumption,
queue_north, queue_south, queue_east, queue_west,
flow_north, flow_south, flow_east, flow_west
```

**验证：** `ls output/csv/ | grep "normal" | wc -l` → 输出 `180`

### Day 5（8/7）

- [ ] Review 全部实验数据：CA-MP 优于 FixedTime 的路口比例（目标 > 80%）
- [ ] 标记异常路口（CA-MP 反而更差的），与 AB 讨论原因
- [ ] 确认数据质量：无缺失文件、无全零 CSV、无异常值
- [ ] 将异常分析结论记录到文档

数据质量检查：

```python
import os, pandas as pd

csv_dir = "output/csv"
normal_files = [f for f in os.listdir(csv_dir) if "normal" in f]

# 检查缺失
assert len(normal_files) == 180, f"缺失文件: {180 - len(normal_files)} 个"

# 检查全零或异常
bad = []
for f in normal_files:
    df = pd.read_csv(f"{csv_dir}/{f}")
    if df["avg_queue_length"].mean() == 0 or df["avg_queue_length"].isna().any():
        bad.append(f)
print(f"异常文件: {len(bad)} 个" + (f" → {bad}" if bad else ""))

# CA-MP 胜率
wins = 0
for iid in [str(i) for i in range(1, 21)]:
    ft = pd.read_csv(f"{csv_dir}/{iid}_normal_fixed_time_s42.csv")
    ca = pd.read_csv(f"{csv_dir}/{iid}_normal_ca_maxpressure_s42.csv")
    if ca["avg_queue_length"].mean() < ft["avg_queue_length"].mean():
        wins += 1
print(f"CA-MP 胜率: {wins}/20 = {wins/20*100:.0f}%")
```

**验证：** `python -c "import os; files = [f for f in os.listdir('output/csv') if 'normal' in f]; empty = [f for f in files if os.path.getsize(f'output/csv/{f}') < 100]; print(len(empty), '个异常文件')"` → 输出 `0 个异常文件`

### Day 6（8/8）

- [ ] 打 tag：`git tag v0.3-w3-complete`
- [ ] 编写 W3 周报
- [ ] 确认 W4 计划：1.5 倍压力测试 + EWMA 接入验证 + Docker 打包
- [ ] 与 IA 协调 Docker 环境准备

**验证：** `git tag -l "v0.3*"` → 输出 `v0.3-w3-complete`

### Day 7（8/9）

- [ ] 处理遗留问题（失败实验重跑、数据修补）
- [ ] 准备 W4 的 Docker 环境（确认 IA 已安装 Docker、基础镜像可用）
- [ ] 确认 DA/DB 已收到全部数据并开始制作

**验证：** `docker --version` → 输出版本号（确认环境就绪）

## 交付物

| 文件 | 截止 | 验收标准 |
|------|------|----------|
| 原始流量 180 组 CSV | Day 4 | `output/csv/` 下 180 个文件，每个 > 100 字节 |
| 汇总对比表 | Day 4 | `output/summary_normal.csv`，20 路口 × 6 指标 × 3 算法，无空值 |
| 数据质量确认 | Day 5 | 无缺失、无全零、异常路口已标记、CA-MP 胜率 > 80% |
| git tag v0.3 | Day 6 | `git tag -l "v0.3*"` 有输出 |

## 协作对接

- Day 4 将完整实验数据发给 DA 和 DB
- Day 5 将异常路口分析发给 AB
- Day 6 与 IA 确认 Docker 环境就绪
