# EX（实验组） W4 任务书

> 周期：8/10（周日）- 8/16（周六） | 核心目标：完成 1.5 倍压力测试（180 组）、参数敏感性实验（54 组）、最终数据分析

## 本周背景

本周引入两类新实验：
- **1.5 倍压力测试**：`config/default.yaml` 中 `scene.default_traffic_levels.high: 1.5`，对应 `TrafficLevel.HIGH`，由 `VariantGenerator` 生成放大流量文件
- **参数敏感性实验**：针对 CA-MP 的两个关键参数（`overflow_occupancy_threshold`、`ewma_alpha`，见 `config/default.yaml::algorithms.ca_maxpressure`）做扫描，确定最优组合

## 每日任务

### Day 1（8/10 周日）

- [ ] 启动 1.5 倍压力测试：20 路口 × 3 算法 × 1.5 倍 × 3 种子 = 180 组（后台运行）
- [ ] 监控进度，处理失败实验
- [ ] 确认 `VariantGenerator` 生成的 high 流量文件正确（vehsPerHour × 1.5）
- [ ] 记录失败原因，加入补跑队列

```bash
nohup python experiments/runner.py --flow high \
    > experiments/results/high_pressure.log 2>&1 &

tail -f experiments/results/high_pressure.log
```

**验证：** `tail -n 3 experiments/results/high_pressure.log` → 显示 `[N/180] Running: ...` 进度行

### Day 2（8/11 周一）

- [ ] 监控 1.5 倍测试进度
- [ ] 与 AB 协调，设计参数敏感性实验矩阵
- [ ] overflow_threshold: [0.8, 0.85, 0.9, 0.95] × 路口 1/16 × 3 种子 = 24 组
- [ ] EWMA alpha: [0.2, 0.3, 0.4, 0.5, 0.6] × 路口 1/16 × 3 种子 = 30 组
- [ ] 准备参数敏感性实验配置文件

```yaml
# experiments/sensitivity.yaml
sensitivity:
  overflow_threshold:
    values: [0.8, 0.85, 0.9, 0.95]
    intersections: [1, 16]
    seeds: [42, 123, 456]   # 4 × 2 × 3 = 24 组
  ewma_alpha:
    values: [0.2, 0.3, 0.4, 0.5, 0.6]
    intersections: [1, 16]
    seeds: [42, 123, 456]   # 5 × 2 × 3 = 30 组
# 合计 54 组
```

**验证：** `python -c "print(4*2*3 + 5*2*3)"` → 输出 `54`

### Day 3（8/12 周二）

- [ ] 确认 1.5 倍测试接近完成
- [ ] 启动参数敏感性实验（54 组，规模小，很快跑完）
- [ ] 采集 1.5 倍测试的已完成部分
- [ ] 监控敏感性实验运行状态

```bash
# 启动参数敏感性实验
nohup python experiments/run_sensitivity.py --config experiments/sensitivity.yaml \
    > experiments/results/sensitivity.log 2>&1 &

# 采集 1.5 倍已完成部分
python experiments/collector.py --results-dir experiments/results \
    --flow high --output experiments/results/metrics_high_partial.csv
```

**验证：** `tail -n 3 experiments/results/sensitivity.log` → 显示敏感性实验进度（共 54 组）

### Day 4（8/13 周三）

- [ ] 确认全部 1.5 倍测试完成（180 组）
- [ ] 采集全部结果，输出 `all_metrics_v2.csv`（360 行）
- [ ] 生成 1.5 倍压力对比表：原始 vs 1.5 倍流量下各算法表现
- [ ] 计算 CA-MP 在高压力下的改进百分比

```bash
python experiments/collector.py --results-dir experiments/results \
    --output experiments/results/all_metrics_v2.csv
```

```python
# 1.5 倍压力对比
import pandas as pd
df = pd.read_csv("experiments/results/all_metrics_v2.csv")
print(df.shape)  # 期望 (360, ...)
high = df[df["flow_level"] == "high"]
pivot = high.pivot_table(index="intersection", columns="algorithm",
                         values="avg_travel_time", aggfunc="mean")
pivot["improvement_vs_fixed"] = (pivot["fixed_time"] - pivot["ca_maxpressure"]) / pivot["fixed_time"] * 100
print(pivot.head())
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('experiments/results/all_metrics_v2.csv'); print(df.shape[0])"` → 输出 `360`

### Day 5（8/14 周四）

- [ ] 参数敏感性分析：生成 overflow_threshold 敏感性曲线数据
- [ ] 生成 EWMA alpha 敏感性曲线数据
- [ ] 确定最优参数组合（指标最优的 threshold + alpha）
- [ ] 将分析结果发给 DA（报告）和 DB（图表）

```python
# 敏感性曲线数据
import pandas as pd
df = pd.read_csv("experiments/results/sensitivity_results.csv")

# overflow_threshold 敏感性
thresh = df.groupby("overflow_threshold")["avg_travel_time"].mean()
thresh.to_csv("experiments/results/sensitivity_threshold.csv")

# EWMA alpha 敏感性
alpha = df.groupby("ewma_alpha")["avg_travel_time"].mean()
alpha.to_csv("experiments/results/sensitivity_alpha.csv")

print("最优 threshold:", thresh.idxmin(), "最优 alpha:", alpha.idxmin())
```

**验证：** `test -f experiments/results/sensitivity_threshold.csv && test -f experiments/results/sensitivity_alpha.csv && echo ok` → 输出 `ok`

### Day 6（8/15 周五）

- [ ] 生成最终版实验数据汇总：`all_metrics_v2.csv`（180 原始 + 180 高压力 = 360 组）
- [ ] 最终对比表（含两种流量水平）
- [ ] 最终 t 检验（原始 + 1.5 倍分别做）
- [ ] 整理参数敏感性结论，发给 DA 和 DB

```python
# 分流量等级做 t 检验
from experiments.analysis import significance_test
import pandas as pd

df = pd.read_csv("experiments/results/all_metrics_v2.csv")
for level in ["normal", "high"]:
    sub = df[df["flow_level"] == level]
    result = significance_test(sub, "avg_travel_time")
    print(f"{level}: p={result['p_value']:.4f}, significant={result['significant']}")
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('experiments/results/all_metrics_v2.csv'); print(df['flow_level'].value_counts().to_dict())"` → 输出 `{'normal': 180, 'high': 180}`

### Day 7（8/16 周六）

- [ ] Buffer：补跑 / 修复
- [ ] 整理最终实验数据目录
- [ ] 编写实验可复现说明（放入 `experiments/README.md`）
- [ ] 确认 360 组 + 54 组敏感性实验全部入库

```bash
ls experiments/results/
# all_metrics_v2.csv  sensitivity_threshold.csv  sensitivity_alpha.csv
# final_summary.csv（W5 生成）...
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('experiments/results/all_metrics_v2.csv'); print(df.shape[0], df['flow_level'].nunique())"` → 输出 `360 2`

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 1.5 倍压力测试 180 组完成 | 8/13 | 全部成功 |
| 2 | 参数敏感性实验 54 组 | 8/13 | 全部成功 |
| 3 | `all_metrics_v2.csv` | 8/14 | 360 行完整数据 |
| 4 | 1.5 倍压力对比表 | 8/14 | 含改进百分比 |
| 5 | 参数敏感性曲线数据 | 8/14 | threshold + alpha 两条曲线数据 |
| 6 | 最终统计报告 | 8/15 | 发给 DA，含双流量等级 t 检验 |

## 协作对接

- 与 **AB** 协调：参数敏感性实验矩阵设计（threshold / alpha 取值范围）、最优参数确认
- 与 **DA/DB** 对接：1.5 倍压力对比表、敏感性曲线数据用于报告与图表
- 敏感性实验规模小（54 组）优先跑完，1.5 倍测试（180 组）后台并行
