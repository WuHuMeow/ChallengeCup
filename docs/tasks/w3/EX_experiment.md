# EX（实验组） W3 任务书

> 周期：8/3（周日）- 8/9（周六） | 核心目标：完成原始流量全量实验（180 组）、采集全部指标、生成对比分析与统计报告

## 每日任务

### Day 1（8/3 周日）

- [ ] 启动剩余实验：路口 11-20 × 3 算法 × 原始流量 × 3 种子 = 90 组（后台运行）
- [ ] 监控运行进度，处理失败实验（重试）
- [ ] 确认 W2 预跑的路口 1-10 共 90 组结果完整
- [ ] 记录失败原因，加入补跑队列

```bash
nohup python experiments/runner.py --intersections 11-20 --flow original \
    > experiments/results/pretrain_11_20.log 2>&1 &

tail -f experiments/results/pretrain_11_20.log
```

**验证：** `tail -n 3 experiments/results/pretrain_11_20.log` → 显示 `[N/90] Running: ...` 进度行

### Day 2（8/4 周一）

- [ ] 检查进度：目标完成原始流量全部 180 组
- [ ] 对已完成实验做初步采集，确认输出 DataFrame 格式正确
- [ ] 标记失败实验，安排补跑
- [ ] 核对 DataFrame 列：intersection / algorithm / flow_level / seed + 6 指标

```bash
python experiments/collector.py --results-dir experiments/results \
    --output experiments/results/metrics_partial.csv
```

```python
# 检查 DataFrame 格式
import pandas as pd
df = pd.read_csv("experiments/results/metrics_partial.csv")
print(df.shape)
print(df.columns.tolist())
# 期望列含: intersection, algorithm, flow_level, seed,
#          avg_travel_time, avg_queue_length, throughput,
#          fuel_consumption, avg_delay, avg_stops
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('experiments/results/metrics_partial.csv'); print(df.shape[0])"` → 输出已完成实验数（接近 180）

### Day 3（8/5 周二）

- [ ] 补跑失败实验，确保 180 组逐步补齐
- [ ] 按 (intersection, algorithm, flow_level) 聚合，计算均值±std
- [ ] 将聚合数据发给 DB（用于生成图表）
- [ ] 确认每个 (路口, 算法) 组合都有 3 个种子的数据

```python
# experiments/analysis.py 聚合
from experiments.analysis import aggregate_results
import pandas as pd

df = pd.read_csv("experiments/results/metrics_partial.csv")
agg = aggregate_results(df)  # groupby(intersection, algorithm, flow_level).agg(mean, std)
agg.to_csv("experiments/results/agg_partial.csv", index=False)
print(agg.head())
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('experiments/results/metrics_partial.csv'); print(df.groupby(['intersection','algorithm']).size().min())"` → 输出 `3`（每组至少 3 种子）

### Day 4（8/6 周三）

- [ ] 确认原始流量 180 组实验全部完成
- [ ] 运行完整采集，输出 `all_metrics.csv`（180 行 × 6 指标）
- [ ] 运行分析：生成 20 路口 × 3 算法 × 6 指标汇总表
- [ ] 输出 CA-MP vs FixedTime 改进百分比表 + t 检验 p 值

```bash
python experiments/collector.py --results-dir experiments/results \
    --output experiments/results/all_metrics.csv
python experiments/analysis.py --input experiments/results/all_metrics.csv
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('experiments/results/all_metrics.csv'); print(df.shape)"` → 输出 `(180, ...)`

### Day 5（8/7 周四）

- [ ] 数据质量检查：是否有缺失值（某路口某指标为空）
- [ ] 检查异常值：行程时间为 0 或极大、排队长度异常
- [ ] 检查 3 次重复的标准差是否合理（不应太大）
- [ ] 标记问题数据，与 IA/IB 排查；生成最终版 `all_metrics.csv`

```python
# 数据质量检查
import pandas as pd
df = pd.read_csv("experiments/results/all_metrics.csv")

print("缺失值:\n", df.isnull().sum())
print("异常行程时间:", df[df["avg_travel_time"] <= 0].shape[0])
# 重复标准差：每组 3 种子的 std 不应过大
std_check = df.groupby(["intersection", "algorithm"])["avg_travel_time"].std()
print("std 过大的组:\n", std_check[std_check > std_check.mean() * 2])
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('experiments/results/all_metrics.csv'); print(df.isnull().sum().sum())"` → 输出 `0`（无缺失值）

### Day 6（8/8 周五）

- [ ] 生成统计报告：CA-MP 平均改进 XX%（行程时间 / 排队 / 油耗）
- [ ] 分路口统计：改进最大 / 最小的路口
- [ ] 显著性统计：t 检验 p < 0.05 的路口比例
- [ ] 将统计报告发给 DA（填入报告第四章），原始数据发给 DB（生成最终图表）

```python
# 生成统计报告核心数字
from experiments.analysis import aggregate_results, significance_test
import pandas as pd

df = pd.read_csv("experiments/results/all_metrics.csv")
for metric in ["avg_travel_time", "avg_queue_length", "fuel_consumption"]:
    result = significance_test(df, metric)
    print(f"{metric}: p={result['p_value']:.4f}, significant={result['significant']}")
```

**验证：** `python experiments/analysis.py --input experiments/results/all_metrics.csv` → 输出包含每个指标的 p 值与显著性标记

### Day 7（8/9 周六）

- [ ] Buffer：补跑 / 修复遗留失败实验
- [ ] 整理 `experiments/results/` 目录结构（按流量等级 / 路口分类）
- [ ] 提交代码和数据给 TL
- [ ] 确认 180 组实验全部入库，无遗漏

```bash
# 整理后的目录结构
ls experiments/results/
# all_metrics.csv  agg_*.csv  csv/  variants/  summary.csv
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('experiments/results/all_metrics.csv'); print(df.shape[0], df['algorithm'].nunique())"` → 输出 `180 3`

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 原始流量 180 组实验完成 | 8/6 | 全部成功，无遗漏 |
| 2 | `all_metrics.csv` | 8/6 | 180 行 × 6 指标，无缺失值 |
| 3 | 聚合对比表 | 8/6 | 20 路口 × 3 算法 × 均值±std |
| 4 | 改进百分比表 | 8/8 | CA-MP vs FixedTime |
| 5 | t 检验结果 | 8/8 | 6 指标 p 值齐全 |
| 6 | 统计报告 | 8/8 | 发给 DA，含总体改进% / 分路口 / 显著性比例 |

## 协作对接

- 与 **IA/IB** 协调：排查异常数据（缺失值、行程时间为 0、SUMO 崩溃）
- 与 **DA** 对接：统计报告填入报告第四章；与 **DB** 对接：原始数据 + 聚合数据用于出图
- 数据质量优先——补跑全部失败实验，确保 180 组完整入库后再做分析
