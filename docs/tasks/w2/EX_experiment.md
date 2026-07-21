# EX（实验组） W2 任务书

> 周期：7/27（周日）- 8/2（周六） | 核心目标：完成 runner.py 联调、验证采集脚本、开始预跑实验（路口 1-10 原始流量）

## 每日任务

### Day 1（7/27 周日）

- [ ] 与 IB 联调 `experiments/runner.py`：确认支持 `--seed`、`--flow-multiplier`、`--output-dir`
- [ ] 用路口 1 跑一次完整实验（ca_maxpressure / original / seed=42）
- [ ] 验证输出目录下有：tripinfo.xml、stats.xml、traj.xml、simulation_log.csv（或 MetricsCollector CSV）
- [ ] 修复联调中发现的问题，记录到 README 常见问题

```bash
# 单路口联调命令
python experiments/runner.py --intersection 1 --algo ca_maxpressure --flow original --seed 42

# 期望输出目录结构
ls experiments/results/i1_ca_maxpressure_original_s42/
# tripinfo.xml  stats.xml  traj.xml  simulation_log.csv
```

**验证：** `python experiments/runner.py --intersection 1 --algo ca_maxpressure --flow original --seed 42 && ls experiments/results/i1_ca_maxpressure_original_s42/` → 列出 tripinfo.xml / stats.xml / traj.xml / simulation_log.csv

### Day 2（7/28 周一）

- [ ] 用 Day 1 输出文件验证 `collector.py` 能采集全部 6 项指标
- [ ] 确认 6 项指标都有非零值：avg_travel_time / avg_queue_length / throughput / fuel_consumption / avg_delay / avg_stops
- [ ] 用假数据（3 次重复）测试 `analysis.aggregate_results()`，确认输出均值±std
- [ ] 修复采集脚本的 bug（字段名、空值、类型）

```python
# 验证脚本（临时）：scripts/verify_collect.py
from experiments.collector import collect_single_experiment
from experiments.analysis import aggregate_results
import pandas as pd

m = collect_single_experiment("experiments/results/i1_ca_maxpressure_original_s42")
expected = {"avg_travel_time", "avg_queue_length", "throughput",
            "fuel_consumption", "avg_delay", "avg_stops"}
assert expected.issubset(m.keys()), f"missing: {expected - set(m)}"
print({k: round(v, 2) for k, v in m.items() if k in expected})
```

**验证：** `python scripts/verify_collect.py` → 打印 6 项指标且全部非零，无 AssertionError

### Day 3（7/29 周二）

- [ ] 在 `experiments/runner.py` 中添加断点续跑（已完成的实验跳过）
- [ ] 添加进度显示：`[42/360] Running: i5_ca_maxpressure_high_s123`
- [ ] 添加失败重试（最多 2 次）
- [ ] 每跑完一组追加结果到 `experiments/results/summary.csv`
- [ ] 跑 5 组实验测试断点续跑：中断后重启，确认从上次位置继续

```python
# experiments/runner.py（断点续跑核心逻辑）
def run_all(config_path="experiments/config.yaml", output_dir="experiments/results"):
    config = load_config(config_path)
    experiments = generate_experiment_list(config)
    done = load_summary(output_dir)  # 已完成的实验名集合

    for i, exp in enumerate(experiments):
        name = exp_name(exp)
        if name in done:
            continue  # 断点续跑：跳过已完成
        print(f"[{i+1}/{len(experiments)}] Running: {name}")
        for attempt in range(3):  # 最多重试 2 次
            result = run_single_experiment(exp, output_dir)
            if result["success"]:
                append_summary(output_dir, result)
                break
```

**验证：** 跑 5 组后 Ctrl+C 中断，再次执行 `python -m experiments.runner` → 日志显示跳过已完成实验，从第 6 组继续

### Day 4（7/30 周三）

- [ ] 用 `--flow-multiplier 1.5` 跑路口 1，验证流量放大功能
- [ ] 对比原始 vs 1.5 倍流量输出：车辆数应增加约 50%
- [ ] 确认 `scripts/scale_flow.py` 正确工作（vehsPerHour × 1.5）
- [ ] 如流量放大有问题，与 IB 协调修复

```bash
python experiments/runner.py --intersection 1 --algo ca_maxpressure --flow high --seed 42

# 对比车辆数（tripinfo 行数 ≈ 完成行程数）
wc -l experiments/results/i1_ca_maxpressure_original_s42/tripinfo.xml
wc -l experiments/results/i1_ca_maxpressure_high_s42/tripinfo.xml
```

**验证：** 对比两个 tripinfo.xml 的 `<tripinfo>` 数量，high 版本应约为 original 的 1.5 倍（误差 ±10%）

### Day 5（7/31 周四）

- [ ] 启动预跑：路口 1-5 × 3 算法 × 原始流量 × 3 种子 = 45 组（后台运行）
- [ ] 监控运行状态，记录失败实验及原因（超时 / 内存 / SUMO 崩溃）
- [ ] 不阻塞其他工作：后台跑实验时不占用机器做重计算
- [ ] 失败的实验加入重跑队列

```bash
# 后台预跑路口 1-5 原始流量
nohup python experiments/runner.py --intersections 1-5 --flow original \
    > experiments/results/pretrain_1_5.log 2>&1 &

# 监控进度
tail -f experiments/results/pretrain_1_5.log
```

**验证：** `tail -n 5 experiments/results/pretrain_1_5.log` → 显示 `[N/45] Running: ...` 进度行

### Day 6（8/1 周五）

- [ ] 检查预跑结果：45 组实验是否全部成功
- [ ] 用 `collector.py` 采集指标，用 `analysis.py` 生成初步对比表
- [ ] 将初步结果发给 TL 和 DA："路口 1-5 的 CA-MP vs FixedTime 对比数据已出"
- [ ] 如有异常结果（如 CA-MP 反而更差），立即报告 AB

```bash
python experiments/collector.py --results-dir experiments/results \
    --output experiments/results/metrics_1_5.csv
python experiments/analysis.py --input experiments/results/metrics_1_5.csv
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('experiments/results/metrics_1_5.csv'); print(df.shape, df['algorithm'].unique())"` → 输出 `(45, ...)` 且包含 3 种算法

### Day 7（8/2 周六）

- [ ] 继续预跑：路口 6-10 × 3 算法 × 原始流量 × 3 种子 = 45 组
- [ ] 完善 `experiments/README.md`：如何运行 / 如何采集 / 如何生成对比表 / 常见问题
- [ ] 提交代码给 TL
- [ ] 整理失败实验记录，安排 W3 补跑

```bash
nohup python experiments/runner.py --intersections 6-10 --flow original \
    > experiments/results/pretrain_6_10.log 2>&1 &
```

**验证：** `wc -l experiments/results/summary.csv` → 行数 ≥ 90（含表头，路口 1-10 共 90 组）

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `experiments/runner.py` 联调通过 | 7/27 | 单次实验输出 tripinfo/stats/traj/csv 完整 |
| 2 | `collector.py` 验证通过 | 7/28 | 6 项指标正确采集且非零 |
| 3 | `experiments/runner.py` 断点续跑 | 7/29 | 中断后能跳过已完成实验继续 |
| 4 | 流量放大验证 | 7/30 | 1.5 倍流量车辆数增加 ~50% |
| 5 | 路口 1-5 预跑完成 | 8/1 | 45 组实验成功 |
| 6 | 路口 6-10 预跑完成 | 8/2 | 45 组实验成功 |
| 7 | `experiments/README.md` | 8/2 | 使用说明完整（运行 / 采集 / 对比表 / FAQ） |

## 协作对接

- 与 **IB** 协调：runner 参数联调、流量放大异常修复
- 与 **TL/DA** 同步：路口 1-5 初步对比数据；异常结果（CA-MP 更差）立即报告 **AB**
- 预跑只为 W3 减负——只跑"原始流量"，1.5 倍压力测试留到 W4；机器时间不够时优先路口 1、11、16
