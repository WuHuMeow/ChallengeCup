# W1 任务书：实验组（EX）

> 周期：7/20（周日）- 7/26（周六）
> 核心目标：设计实验矩阵、定义指标采集方案、编写采集脚本框架

---

## 背景

你负责整个实验验证体系的设计与执行。W1 不需要跑实验（算法还没联调完），但必须把实验框架搭好——配置、脚本、输出格式全部定义清楚，W3 一到就能直接批量跑。

PDF 评分标准中"实验验证与性能评估"占 20 分：
- 实验设计科学性（5 分）
- 对比数据与可视化（10 分）
- 分析结论（5 分）

---

## 每日任务

### Day 1（7/20 周日）

**设计实验矩阵**
1. 创建 `experiments/config.yaml`：

```yaml
# 实验矩阵配置
experiment:
  name: "CA-MP vs Baselines - 20 Intersections"
  version: "1.0"

intersections: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

algorithms:
  - name: fixed_time
    module: src.algorithm.fixed_time.FixedTimeController
  - name: actuated
    module: src.algorithm.actuated.ActuatedController
  - name: ca_maxpressure
    module: src.algorithm.ca_max_pressure.CAMaxPressureController

flow_levels:
  - name: original
    multiplier: 1.0
  - name: high_pressure
    multiplier: 1.5

repetitions: 3  # 每组重复次数（不同随机种子）
seeds: [42, 123, 456]

simulation:
  steps: 3600  # 每组仿真步数
  warmup_steps: 300  # 预热步数（不计入统计）

metrics:
  - name: avg_travel_time
    description: "平均行程时间（秒）"
    source: "tripinfo.xml - duration"
  - name: avg_queue_length
    description: "平均排队长度（辆）"
    source: "stats.xml - haltingNumber"
  - name: throughput
    description: "吞吐量（辆/小时）"
    source: "tripinfo.xml - 完成车辆数 / 时间"
  - name: fuel_consumption
    description: "总油耗（ml）"
    source: "tripinfo.xml - fuel"
  - name: avg_delay
    description: "平均延误（秒）"
    source: "tripinfo.xml - timeLoss"
  - name: avg_stops
    description: "平均停车次数"
    source: "tripinfo.xml - stops"
```

2. 计算总实验量：20 路口 × 3 算法 × 2 流量 × 3 重复 = **360 次仿真**
3. 估算机器时间：每次 5-10 分钟 → 总计 30-60 小时

### Day 2（7/21 周一）

**编写批量运行脚本框架**
1. 创建 `experiments/runner.py`：

```python
"""批量实验运行器"""
import yaml
import subprocess
import os
import time
from pathlib import Path
from itertools import product


def load_config(config_path: str = "experiments/config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_experiment_list(config: dict) -> list[dict]:
    """生成所有实验组合"""
    experiments = []
    for intersection, algo, flow, seed in product(
        config["intersections"],
        config["algorithms"],
        config["flow_levels"],
        config["seeds"]
    ):
        experiments.append({
            "intersection": intersection,
            "algorithm": algo["name"],
            "flow_level": flow["name"],
            "flow_multiplier": flow["multiplier"],
            "seed": seed,
            "steps": config["simulation"]["steps"],
        })
    return experiments


def run_single_experiment(exp: dict, output_dir: str) -> dict:
    """运行单次实验，返回结果文件路径"""
    exp_name = f"i{exp['intersection']}_{exp['algorithm']}_{exp['flow_level']}_s{exp['seed']}"
    exp_output = os.path.join(output_dir, exp_name)
    os.makedirs(exp_output, exist_ok=True)

    cmd = [
        "python", "src/platform/main.py",
        "--intersection", str(exp["intersection"]),
        "--algo", exp["algorithm"],
        "--steps", str(exp["steps"]),
        "--seed", str(exp["seed"]),
        "--flow-multiplier", str(exp["flow_multiplier"]),
        "--output-dir", exp_output,
    ]

    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start_time

    return {
        "experiment": exp_name,
        "success": result.returncode == 0,
        "elapsed_seconds": elapsed,
        "output_dir": exp_output,
        "error": result.stderr if result.returncode != 0 else None,
    }


def run_all(config_path: str = "experiments/config.yaml",
            output_dir: str = "experiments/results"):
    """批量运行所有实验"""
    config = load_config(config_path)
    experiments = generate_experiment_list(config)
    print(f"Total experiments: {len(experiments)}")

    results = []
    for i, exp in enumerate(experiments):
        print(f"[{i+1}/{len(experiments)}] Running: {exp['intersection']}_{exp['algorithm']}_{exp['flow_level']}_s{exp['seed']}")
        result = run_single_experiment(exp, output_dir)
        results.append(result)
        if not result["success"]:
            print(f"  FAILED: {result['error']}")

    # 保存运行日志
    ...


if __name__ == "__main__":
    run_all()
```

2. 此时 main.py 还不支持 `--seed`、`--flow-multiplier`、`--output-dir` 参数——记录下来，W2 与 IB 协调添加

### Day 3（7/22 周二）

**编写指标采集脚本**
1. 创建 `experiments/collector.py`：

```python
"""指标采集：从 SUMO 输出文件中提取实验指标"""
import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path


def collect_tripinfo(tripinfo_path: str) -> dict:
    """从 tripinfo.xml 采集行程级指标"""
    tree = ET.parse(tripinfo_path)
    root = tree.getroot()

    durations = []
    time_losses = []
    fuels = []
    stops = []

    for trip in root.findall("tripinfo"):
        durations.append(float(trip.get("duration", 0)))
        time_losses.append(float(trip.get("timeLoss", 0)))
        fuels.append(float(trip.get("fuel", 0)))
        stops.append(int(trip.get("stops", 0)))

    n = len(durations)
    if n == 0:
        return {"avg_travel_time": 0, "avg_delay": 0, "fuel_consumption": 0,
                "avg_stops": 0, "throughput": 0, "num_vehicles": 0}

    return {
        "avg_travel_time": sum(durations) / n,
        "avg_delay": sum(time_losses) / n,
        "fuel_consumption": sum(fuels),
        "avg_stops": sum(stops) / n,
        "throughput": n,  # 完成行程的车辆数
        "num_vehicles": n,
    }


def collect_summary(summary_path: str) -> dict:
    """从 stats.xml (summary output) 采集排队指标"""
    tree = ET.parse(summary_path)
    root = tree.getroot()

    halting_numbers = []
    for step in root.findall("step"):
        halting = int(step.get("halting", 0))
        halting_numbers.append(halting)

    avg_queue = sum(halting_numbers) / max(len(halting_numbers), 1)
    max_queue = max(halting_numbers) if halting_numbers else 0

    return {
        "avg_queue_length": avg_queue,
        "max_queue_length": max_queue,
    }


def collect_single_experiment(output_dir: str) -> dict:
    """采集单次实验的所有指标"""
    tripinfo = Path(output_dir) / "tripinfo.xml"
    summary = Path(output_dir) / "stats.xml"

    metrics = {}
    if tripinfo.exists():
        metrics.update(collect_tripinfo(str(tripinfo)))
    if summary.exists():
        metrics.update(collect_summary(str(summary)))
    return metrics


def collect_all(results_dir: str = "experiments/results") -> pd.DataFrame:
    """批量采集所有实验结果，输出 DataFrame"""
    records = []
    for exp_dir in Path(results_dir).iterdir():
        if not exp_dir.is_dir():
            continue
        # 解析实验名：i1_fixed_time_original_s42
        parts = exp_dir.name.split("_")
        metrics = collect_single_experiment(str(exp_dir))
        metrics["experiment"] = exp_dir.name
        metrics["intersection"] = int(parts[0][1:])
        metrics["algorithm"] = parts[1] + "_" + parts[2] if len(parts) > 4 else parts[1]
        metrics["flow_level"] = parts[-2]
        metrics["seed"] = int(parts[-1][1:])
        records.append(metrics)

    return pd.DataFrame(records)
```

### Day 4（7/23 周三）

**定义输出格式与统计方案**
1. 创建 `experiments/analysis.py`（框架）：

```python
"""实验结果统计分析"""
import pandas as pd
import numpy as np
from scipy import stats


def aggregate_results(df: pd.DataFrame) -> pd.DataFrame:
    """按 (intersection, algorithm, flow_level) 聚合，计算均值和标准差"""
    group_cols = ["intersection", "algorithm", "flow_level"]
    metric_cols = ["avg_travel_time", "avg_queue_length", "throughput",
                   "fuel_consumption", "avg_delay", "avg_stops"]

    agg = df.groupby(group_cols)[metric_cols].agg(["mean", "std"]).reset_index()
    return agg


def compare_algorithms(df: pd.DataFrame) -> pd.DataFrame:
    """生成算法对比表：CA-MP vs FixedTime vs Actuated"""
    pivot = df.pivot_table(
        index=["intersection", "flow_level"],
        columns="algorithm",
        values="avg_travel_time",
        aggfunc="mean"
    )
    # 计算改进百分比
    if "fixed_time" in pivot.columns and "ca_maxpressure" in pivot.columns:
        pivot["improvement_vs_fixed"] = (
            (pivot["fixed_time"] - pivot["ca_maxpressure"]) / pivot["fixed_time"] * 100
        )
    return pivot


def significance_test(df: pd.DataFrame, metric: str = "avg_travel_time"):
    """对 CA-MP vs FixedTime 做 t 检验"""
    ca_mp = df[df["algorithm"] == "ca_maxpressure"][metric]
    fixed = df[df["algorithm"] == "fixed_time"][metric]
    t_stat, p_value = stats.ttest_ind(ca_mp, fixed)
    return {"t_statistic": t_stat, "p_value": p_value, "significant": p_value < 0.05}
```

2. 确定统计方法：
   - 每组 3 次重复 → 报告均值 ± 标准差
   - CA-MP vs FixedTime 做配对 t 检验（p < 0.05 为显著）
   - 改进百分比 = (baseline - ca_mp) / baseline × 100%

### Day 5（7/24 周四）

**流量放大方案**
1. 1.5 倍压力测试需要修改 flow.xml 中的流量
2. 设计方案：
   - 不修改原始 flow.xml（只读）
   - 在 runner.py 中，运行前生成临时 flow.xml（将 vehsPerHour × multiplier）
   - 或者：在 main.py 中通过 TraCI 动态调整流量
3. 与 IB 确认：main.py 是否支持 `--flow-multiplier` 参数
4. 写一个 `scripts/scale_flow.py`：读取原始 flow.xml → 乘以倍率 → 输出临时文件

### Day 6（7/25 周五）

**验证采集脚本**
1. 用路口 1 的已有输出（`intersection_data/1/sumo工程/stats.xml` 和 `traj.xml`）测试 collector.py
2. 确认能正确解析 stats.xml 格式
3. 确认 tripinfo.xml 的字段名（需要在 sumocfg 中添加 tripinfo-output）
4. 记录：哪些路口的 sumocfg 缺少 tripinfo-output 配置（需要 IB 补充）

### Day 7（7/26 周六）

**Buffer / 文档**
1. 编写 `experiments/README.md`：说明实验设计、运行方法、输出格式
2. 整理 W1 产出，提交给 TL
3. 如果时间充裕，预研 Matplotlib 图表样式（为 W3 出图做准备）

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `experiments/config.yaml` | 7/20 | 实验矩阵完整定义 |
| 2 | `experiments/runner.py` | 7/21 | 批量运行脚本框架（可生成 360 组实验列表） |
| 3 | `experiments/collector.py` | 7/22 | 能从 tripinfo.xml/stats.xml 提取 6 项指标 |
| 4 | `experiments/analysis.py` | 7/23 | 聚合、对比、t 检验框架 |
| 5 | `scripts/scale_flow.py` | 7/24 | 流量放大脚本 |
| 6 | `experiments/README.md` | 7/26 | 实验设计文档 |

---

## 注意事项

- W1 你不需要跑实验——算法还没联调完
- 你的核心产出是"框架"——W3 一到就能直接 `python experiments/runner.py` 批量跑
- 指标采集脚本必须 robust——处理文件不存在、字段缺失等异常
- 与 IB 确认 main.py 需要新增的参数：`--seed`、`--flow-multiplier`、`--output-dir`
- 统计方法用 scipy.stats.ttest_ind，不需要复杂统计
- 360 次实验的机器时间要提前规划——W2 结束就开始排队跑
