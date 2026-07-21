# EX（实验组） W1 任务书

> 周期：7/20（周日）- 7/26（周六） | 核心目标：设计实验矩阵、定义指标采集方案、搭好批量实验框架（W3 一到就能直接跑）

## 本周背景

你负责整个实验验证体系的设计与执行。W1 不需要跑实验（算法还没联调完），但必须把实验框架搭好——配置、脚本、输出格式全部定义清楚。

PDF 评分标准中"实验验证与性能评估"占 20 分：实验设计科学性（5 分）、对比数据与可视化（10 分）、分析结论（5 分）。

实验骨架基于仓库已有模块：
- `experiments/runner.py::run_batch()`：20 路口 × 3 算法 × 2 流量等级 × 3 种子 = **360 次仿真**
- `experiments/metrics.py::compute_metrics(step, state) -> SimulationMetrics`：单步指标
- `engine/collector.py::MetricsCollector`：按 `metrics.snapshot_interval=60` 写 CSV
- `config/default.yaml`：`seeds=[42,123,456]`、`scene.default_traffic_levels={normal:1.0, high:1.5}`

## 每日任务

### Day 1（7/20 周日）

- [ ] 创建 `experiments/config.yaml`，定义实验矩阵（20 路口、3 算法、2 流量等级、3 种子）
- [ ] 列出 6 项核心指标及数据来源（avg_travel_time / avg_queue_length / throughput / fuel_consumption / avg_delay / avg_stops）
- [ ] 计算总实验量：20 × 3 × 2 × 3 = 360 次仿真
- [ ] 估算机器时间：每次 5-10 分钟 → 总计 30-60 小时，写入 README 草稿

```yaml
# experiments/config.yaml
experiment:
  name: "CA-MP vs Baselines - 20 Intersections"
  version: "1.0"

intersections: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

algorithms:
  - {name: fixed_time,      module: algorithms.fixed_time.FixedTimeAlgorithm}
  - {name: actuated,        module: algorithms.rule_adaptive.RuleAdaptiveAlgorithm}
  - {name: ca_maxpressure,  module: algorithms.ca_max_pressure.CAMaxPressureAlgorithm}

flow_levels:
  - {name: normal, multiplier: 1.0}
  - {name: high,   multiplier: 1.5}

seeds: [42, 123, 456]   # 与 config/default.yaml 保持一致

simulation:
  steps: 3600
  warmup_steps: 300     # 预热步数（不计入统计）

metrics:
  - {name: avg_travel_time,  source: "tripinfo.xml - duration"}
  - {name: avg_queue_length, source: "SimulationMetrics.avg_queue_length"}
  - {name: throughput,       source: "SimulationMetrics.total_throughput"}
  - {name: fuel_consumption, source: "SimulationMetrics.fuel_consumption"}
  - {name: avg_delay,        source: "SimulationMetrics.avg_delay"}
  - {name: avg_stops,        source: "SimulationMetrics.total_stops"}
```

**验证：** `python -c "import yaml; c=yaml.safe_load(open('experiments/config.yaml',encoding='utf-8')); print(len(c['intersections'])*len(c['algorithms'])*len(c['flow_levels'])*len(c['seeds']))"` → 输出 `360`

### Day 2（7/21 周一）

- [ ] 阅读现有 `experiments/runner.py::run_batch()`，确认其参数（intersection_ids / algorithms / levels / seeds / steps / output_root）
- [ ] 在 `experiments/runner.py` 中补充 `generate_experiment_list(config)` 辅助函数，从 yaml 生成 360 组实验列表
- [ ] 在 `experiments/runner.py` 中补充 `run_all(config_path, output_dir)` 入口，循环调用 `run_batch` 并打印进度
- [ ] 记录 `run_single`/`runner` 当前缺失的能力（`--seed`、`--flow-multiplier`、`--output-dir`），W2 与 IB 协调补齐

```python
# experiments/runner.py（在已有 run_batch 基础上扩展）
from itertools import product

def generate_experiment_list(config: dict) -> list[dict]:
    """从 yaml 配置生成全部实验组合（360 组）。"""
    return [
        {
            "intersection": i,
            "algorithm": a["name"],
            "flow_level": f["name"],
            "flow_multiplier": f["multiplier"],
            "seed": s,
            "steps": config["simulation"]["steps"],
        }
        for i, a, f, s in product(
            config["intersections"],
            config["algorithms"],
            config["flow_levels"],
            config["seeds"],
        )
    ]

def run_all(config_path="experiments/config.yaml", output_dir="experiments/results"):
    config = load_config(config_path)
    experiments = generate_experiment_list(config)
    print(f"Total experiments: {len(experiments)}")
    # W2 起接入 run_batch / 断点续跑
```

**验证：** `python -c "from experiments.runner import generate_experiment_list, load_config; print(len(generate_experiment_list(load_config())))"` → 输出 `360`

### Day 3（7/22 周二）

- [ ] 创建 `experiments/collector.py`，实现 `collect_from_csv(output_csv)` 从 MetricsCollector CSV 提取 6 项指标
- [ ] 实现 `collect_tripinfo(tripinfo_path)` 作为备用（解析 tripinfo.xml 的 duration/timeLoss/fuel/stops）
- [ ] 实现 `collect_single_experiment(output_dir)`：优先 CSV，缺失则回退 tripinfo
- [ ] 处理空文件 / 字段缺失等异常，返回带默认值的 dict

```python
# experiments/collector.py
import pandas as pd
from pathlib import Path

METRIC_COLS = ["avg_queue_length", "max_queue_length", "avg_delay",
               "total_throughput", "avg_travel_time", "total_stops",
               "fuel_consumption"]

def collect_from_csv(output_csv: str) -> dict:
    """从 MetricsCollector 输出 CSV 聚合 6 项指标。"""
    df = pd.read_csv(output_csv)
    if df.empty:
        return {m: 0 for m in METRIC_COLS} | {"num_steps": 0}
    return {
        "avg_travel_time":  df["avg_travel_time"].mean(),
        "avg_delay":        df["avg_delay"].mean(),
        "fuel_consumption": df["fuel_consumption"].sum(),
        "avg_stops":        df["total_stops"].mean(),
        "throughput":       df["total_throughput"].max(),
        "avg_queue_length": df["avg_queue_length"].mean(),
        "max_queue_length": df["max_queue_length"].max(),
        "num_steps":        len(df),
    }
```

**验证：** `python -c "from experiments.collector import collect_from_csv; print(sorted(collect_from_csv.__doc__ and {} or {}))"` 不报错；用任意已有 CSV 调用 `collect_from_csv(path)` 返回的 dict 含 6 项指标键

### Day 4（7/23 周三）

- [ ] 创建 `experiments/analysis.py`，实现 `aggregate_results(df)` 按 (intersection, algorithm, flow_level) 聚合均值±std
- [ ] 实现 `compare_algorithms(df)` 生成 CA-MP vs FixedTime 改进百分比表
- [ ] 实现 `significance_test(df, metric)` 做配对 t 检验（p < 0.05 显著）
- [ ] 在 README 草稿中明确统计方案：3 次重复 → 均值±std；改进% = (baseline - ca_mp) / baseline × 100%

```python
# experiments/analysis.py
import pandas as pd
from scipy import stats

GROUP_COLS = ["intersection", "algorithm", "flow_level"]
METRIC_COLS = ["avg_travel_time", "avg_queue_length", "throughput",
               "fuel_consumption", "avg_delay", "avg_stops"]

def aggregate_results(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(GROUP_COLS)[METRIC_COLS].agg(["mean", "std"]).reset_index()

def significance_test(df: pd.DataFrame, metric: str = "avg_travel_time"):
    """CA-MP vs FixedTime 配对 t 检验（同路口同种子配对）。"""
    pivot = df.pivot_table(index=["intersection", "seed"], columns="algorithm", values=metric)
    t_stat, p_value = stats.ttest_rel(pivot["ca_maxpressure"], pivot["fixed_time"])
    return {"t_statistic": t_stat, "p_value": p_value, "significant": p_value < 0.05}
```

**验证：** `python -c "from experiments.analysis import aggregate_results, significance_test; print('ok')"` → 输出 `ok`

### Day 5（7/24 周四）

- [ ] 设计 1.5 倍流量方案：不修改原始 flow.xml（只读），运行前生成临时 flow 文件（vehsPerHour × multiplier）
- [ ] 创建 `scripts/scale_flow.py`：读取原始 flow.xml → 乘以倍率 → 输出到 `output/variants/`
- [ ] 与 IB 确认：`SimulationRunner` / `VariantGenerator` 是否已支持流量倍率（参考 `scenes/variant.py`）
- [ ] 在脚本中保留原始 flow.xml 不被覆盖

```python
# scripts/scale_flow.py
import xml.etree.ElementTree as ET
from pathlib import Path

def scale_flow(src: str, dst: str, multiplier: float) -> None:
    """将 flow.xml 中所有 vehsPerHour 乘以 multiplier，输出到 dst。"""
    tree = ET.parse(src)
    for flow in tree.getroot().iter("flow"):
        vph = float(flow.get("vehsPerHour", 0))
        flow.set("vehsPerHour", str(vph * multiplier))
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    import sys
    scale_flow(sys.argv[1], sys.argv[2], float(sys.argv[3]))
```

**验证：** `python scripts/scale_flow.py <某路口 flow.xml> /tmp/flow_x1.5.xml 1.5 && python -c "import xml.etree.ElementTree as ET; print([f.get('vehsPerHour') for f in ET.parse('/tmp/flow_x1.5.xml').getroot().iter('flow')][:3])"` → 输出的 vehsPerHour 为原值 × 1.5

### Day 6（7/25 周五）

- [ ] 用路口 1 的已有 CSV 输出测试 `collector.py`，确认能正确解析 MetricsCollector 字段
- [ ] 确认 CSV 列名与 `engine/collector.py::MetricsCollector.record` 一致（step / timestamp / tls_id / current_phase / 6 指标 / queue_{dir} / flow_{dir}）
- [ ] 确认 tripinfo.xml 字段名（duration / timeLoss / fuel / stops），如 sumocfg 缺少 tripinfo-output 则记录
- [ ] 列出哪些路口的 sumocfg 缺少 tripinfo-output 配置，整理清单交给 IB 补充

```python
# 验证脚本（临时）：scripts/check_outputs.py
from pathlib import Path
from experiments.collector import collect_from_csv

for csv_path in Path("output/csv").glob("*.csv"):
    metrics = collect_from_csv(str(csv_path))
    missing = [k for k, v in metrics.items() if v in (0, None)]
    print(csv_path.name, "->", metrics["num_steps"], "steps;",
          "missing:", missing or "none")
```

**验证：** `python scripts/check_outputs.py` → 每个 CSV 输出 `N steps; missing: none`（或明确列出缺失字段，便于交给 IB）

### Day 7（7/26 周六）

- [ ] 编写 `experiments/README.md`：实验设计、运行方法、输出格式、统计方案
- [ ] 整理 W1 全部产出（config.yaml / runner.py / collector.py / analysis.py / scale_flow.py）提交给 TL
- [ ] 如时间充裕，预研 Matplotlib 图表样式（为 W3 出图做准备）
- [ ] 在 README 中明确 360 次实验的机器时间预算与排队计划

```markdown
# experiments/README.md（结构草稿）
## 实验设计
- 矩阵：20 路口 × 3 算法 × 2 流量等级 × 3 种子 = 360 次
- 指标：avg_travel_time / avg_queue_length / throughput / fuel / avg_delay / stops
## 运行方法
- 批量：python -m experiments.runner
- 采集：python experiments/collector.py --results-dir experiments/results
## 统计方案
- 均值±std；CA-MP vs FixedTime 配对 t 检验（p<0.05）
```

**验证：** `test -f experiments/README.md && grep -c "360" experiments/README.md` → 输出 ≥ 1（README 存在且包含实验规模说明）

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `experiments/config.yaml` | 7/20 | 实验矩阵完整定义，加载后组合数 = 360 |
| 2 | `experiments/runner.py` | 7/21 | 批量运行框架，`generate_experiment_list` 返回 360 组 |
| 3 | `experiments/collector.py` | 7/22 | 能从 CSV / tripinfo.xml 提取 6 项指标，空文件不崩溃 |
| 4 | `experiments/analysis.py` | 7/23 | 聚合、对比、配对 t 检验框架可调用 |
| 5 | `scripts/scale_flow.py` | 7/24 | 流量放大脚本，输出 vehsPerHour = 原值 × 倍率 |
| 6 | `experiments/README.md` | 7/26 | 实验设计 / 运行方法 / 统计方案完整 |

## 协作对接

- 与 **IB** 协调：`SimulationRunner` 需新增 `--seed`、`--flow-multiplier`、`--output-dir` 参数；补充缺失的 tripinfo-output 配置
- 与 **TL** 同步：W1 框架产出 review，确认 360 组实验的机器时间排期
- W1 不跑实验——核心产出是"框架"，W3 一到就能 `python -m experiments.runner` 直接批量跑
