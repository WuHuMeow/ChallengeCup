# EX（实验组） W5 任务书

> 周期：8/17（周日）- 8/23（周六） | 核心目标：最终数据整理、协助报告数据章节、确保实验可复现

## 每日任务

### Day 1（8/17 周日）

- [ ] 确认 `all_metrics_v2.csv` 包含全部 360 组实验
- [ ] 确认无缺失值（所有指标非空）
- [ ] 生成最终版汇总统计表
- [ ] 将最终数据发给 DA（报告定稿用）

```python
import pandas as pd
df = pd.read_csv("experiments/results/all_metrics_v2.csv")
assert df.shape[0] == 360, f"expected 360 rows, got {df.shape[0]}"
assert df.isnull().sum().sum() == 0, "found missing values"
print("360 组完整，无缺失值")
print(df.groupby(["flow_level", "algorithm"]).size())
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('experiments/results/all_metrics_v2.csv'); print(df.shape[0], df.isnull().sum().sum())"` → 输出 `360 0`

### Day 2（8/18 周一）

- [ ] 协助 DA 完善报告第四章：核对所有数据表格的准确性
- [ ] 确认改进百分比计算正确：(baseline - ca_mp) / baseline × 100%
- [ ] 确认 t 检验结果准确（配对 t 检验，p 值正确）
- [ ] 补充 DA 可能遗漏的统计细节（标准差、显著性标记）

```python
# 核对改进百分比计算
import pandas as pd
df = pd.read_csv("experiments/results/all_metrics_v2.csv")
pivot = df.pivot_table(index=["intersection", "flow_level"], columns="algorithm",
                       values="avg_travel_time", aggfunc="mean")
pivot["improvement"] = (pivot["fixed_time"] - pivot["ca_maxpressure"]) / pivot["fixed_time"] * 100
print(pivot["improvement"].describe())  # 与报告第四章数字比对
```

**验证：** 将 `pivot["improvement"].mean()` 与报告第四章中的"平均改进 XX%"比对 → 数字一致

### Day 3（8/19 周二）

- [ ] 生成 `experiments/results/final_summary.csv`：20 路口 × 3 算法 × 2 流量 × 6 指标（均值±std）
- [ ] 生成 `experiments/results/improvement_table.csv`：CA-MP 改进百分比
- [ ] 生成 `experiments/results/significance_tests.csv`：t 检验结果
- [ ] 确认这 3 个文件随代码仓库一起提交

```python
# 生成 3 个最终结果文件
from experiments.analysis import aggregate_results, significance_test
import pandas as pd

df = pd.read_csv("experiments/results/all_metrics_v2.csv")

aggregate_results(df).to_csv("experiments/results/final_summary.csv", index=False)

# improvement_table.csv 与 significance_tests.csv
records = []
for level in ["normal", "high"]:
    sub = df[df["flow_level"] == level]
    for metric in ["avg_travel_time", "avg_queue_length", "throughput",
                   "fuel_consumption", "avg_delay", "avg_stops"]:
        r = significance_test(sub, metric)
        records.append({"flow_level": level, "metric": metric, **r})
pd.DataFrame(records).to_csv("experiments/results/significance_tests.csv", index=False)
```

**验证：** `ls experiments/results/final_summary.csv experiments/results/improvement_table.csv experiments/results/significance_tests.csv` → 3 个文件均存在

### Day 4（8/20 周三）

- [ ] 完善 `experiments/README.md` 可复现说明：如何从零复现全部 360 组实验
- [ ] 写明预计运行时间（30-60 小时）与硬件要求
- [ ] 写明随机种子说明（seeds=[42,123,456]）
- [ ] 确认任何人按说明能复现结果

```markdown
# experiments/README.md（可复现说明章节）
## 从零复现
1. 安装依赖：pip install -r requirements.txt
2. 批量运行：python -m experiments.runner   # 360 组，约 30-60 小时
3. 采集指标：python experiments/collector.py --results-dir experiments/results
4. 生成分析：python experiments/analysis.py --input experiments/results/all_metrics_v2.csv
## 随机种子
- seeds = [42, 123, 456]，固定种子保证可复现
## 硬件要求
- 内存 ≥ 8GB，单核 SUMO；后台跑批不占用 GUI
```

**验证：** `grep -c "360" experiments/README.md && grep -c "42, 123, 456" experiments/README.md` → 两条均输出 ≥ 1

### Day 5（8/21 周四）

- [ ] 协助 TL 做数据最终验证：抽查 5 组实验重新运行，确认结果一致
- [ ] 确认随机种子控制有效（同种子重跑结果一致）
- [ ] 准备答辩问题："为什么选 3 次重复？"
- [ ] 准备答辩问题："1.5 倍流量怎么确定的？""统计方法为什么用 t 检验？"

```bash
# 抽查重跑：固定种子结果应一致
python experiments/runner.py --intersection 1 --algo ca_maxpressure --flow original --seed 42
python -c "from experiments.collector import collect_single_experiment; print(collect_single_experiment('experiments/results/i1_ca_maxpressure_original_s42'))"
# 与 all_metrics_v2.csv 中对应行比对
```

**验证：** 重跑后采集的 6 项指标与 `all_metrics_v2.csv` 中 `i1/ca_maxpressure/original/42` 行一致（误差 < 1%）

### Day 6（8/22 周五）

- [ ] Buffer：处理遗留问题
- [ ] 整理 `experiments/` 目录最终状态
- [ ] 确认所有交付 CSV 在仓库中正确提交
- [ ] 清理临时验证脚本

```bash
git status experiments/
ls experiments/results/*.csv
```

**验证：** `ls experiments/results/ | grep -E "final_summary|improvement_table|significance_tests|all_metrics_v2"` → 列出 4 个核心 CSV

### Day 7（8/23 周六）

- [ ] Buffer
- [ ] 最终自查：360 组数据、3 个结果 CSV、可复现说明齐全
- [ ] 待命协助 TL/DA 收尾

**验证：** `python -c "import pandas as pd; print(pd.read_csv('experiments/results/all_metrics_v2.csv').shape)"` → 输出 `(360, ...)`

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 最终数据整理 | 8/17 | 360 组无缺失 |
| 2 | 报告数据核对 | 8/18 | 所有表格准确，改进% / p 值一致 |
| 3 | 最终结果文件 | 8/19 | final_summary / improvement_table / significance_tests 3 个 CSV 完整 |
| 4 | 可复现说明 | 8/20 | 外人能按 README 复现 360 组 |
| 5 | 抽查验证通过 | 8/21 | 5 组重跑结果一致 |

## 协作对接

- 与 **DA** 对接：报告第四章数据核对、改进百分比与 t 检验数字一致
- 与 **TL** 对接：抽查 5 组实验重跑验证、随机种子有效性确认
- 答辩问题准备：3 次重复 / 1.5 倍流量 / t 检验方法的依据
