# EX（实验组） W6 任务书

> 周期：8/24（周日）- 8/31（周六） | 核心目标：数据最终确认、答辩准备、协助提交

## 每日任务

### Day 1（8/24 周日）

- [ ] 参加全员 review 会议
- [ ] 记录与实验数据相关的修改意见
- [ ] 整理需要修订的数据表格清单
- [ ] 评估修改意见对 360 组数据的影响范围

```bash
# 会前准备：列出当前所有交付数据文件
ls experiments/results/*.csv
```

**验证：** 会议记录文档中包含实验数据相关修改意见条目（≥ 1 条或明确"无修改意见"）

### Day 2（8/25 周一）

- [ ] 最终数据核对：确认报告中所有数字与 `all_metrics_v2.csv` 一致
- [ ] 确认改进百分比计算无误
- [ ] 确认 t 检验 p 值正确
- [ ] 修复任何数据不一致

```python
# 报告数字 vs CSV 一致性核对
import pandas as pd
df = pd.read_csv("experiments/results/all_metrics_v2.csv")
sig = pd.read_csv("experiments/results/significance_tests.csv")
imp = pd.read_csv("experiments/results/improvement_table.csv")

print("显著性结果:\n", sig[["flow_level", "metric", "p_value", "significant"]])
print("平均改进%:\n", imp.groupby("flow_level")["improvement"].mean())
# 与报告第四章逐一比对
```

**验证：** 报告第四章中每个数字都能在 `all_metrics_v2.csv` / `significance_tests.csv` / `improvement_table.csv` 中找到对应来源

### Day 3（8/26 周二）

- [ ] 确认实验结果文件完整：final_summary.csv / improvement_table.csv / significance_tests.csv / all_metrics_v2.csv
- [ ] 确认这 4 个文件在仓库中正确提交
- [ ] 检查文件内容非空、格式正确
- [ ] 确认 CSV 编码与列名规范

```bash
git status experiments/results/
for f in final_summary improvement_table significance_tests all_metrics_v2; do
    echo "$f: $(wc -l < experiments/results/$f.csv) lines"
done
```

**验证：** `ls experiments/results/{final_summary,improvement_table,significance_tests,all_metrics_v2}.csv` → 4 个文件均存在且 `git status` 显示已纳入版本控制

### Day 4（8/27 周三）

- [ ] 协助 TL 做最终验证：抽查 2 组实验重新运行，确认结果一致
- [ ] 确认 `experiments/README.md` 可复现说明准确
- [ ] 确认随机种子控制有效
- [ ] 记录抽查结果

```bash
# 抽查重跑 2 组
python experiments/runner.py --intersection 16 --algo ca_maxpressure --flow high --seed 123
python experiments/runner.py --intersection 1 --algo fixed_time --flow original --seed 456
# 采集后与 all_metrics_v2.csv 对应行比对
```

**验证：** 2 组重跑采集的 6 项指标与 `all_metrics_v2.csv` 对应行一致（误差 < 1%）

### Day 5（8/28 周四）

- [ ] 准备答辩 Q&A："实验设计为什么这样安排？"（20 路口覆盖不同拓扑，2 流量水平验证鲁棒性）
- [ ] 准备答辩 Q&A："3 次重复够吗？"（SUMO 随机性有限，3 次已足够显示趋势）
- [ ] 准备答辩 Q&A："统计方法为什么用 t 检验？"（样本小、正态假设合理）
- [ ] 准备答辩 Q&A："1.5 倍流量依据是什么？"（模拟高峰时段，参考雄安规划流量增长）
- [ ] 与 DA 对齐报告中的数据引用

```markdown
# 答辩 Q&A 要点（写入 docs/qa_experiment.md）
- 实验设计：20 路口覆盖不同拓扑（含 5 进口道路口 16），2 流量水平（normal/high=1.5x）验证鲁棒性
- 3 次重复：seeds=[42,123,456]，SUMO 随机性有限，3 次足以显示趋势且控制机器时间
- t 检验：配对 t 检验（同路口同种子配对），样本小、正态假设合理，p<0.05 显著
- 1.5 倍流量：模拟高峰时段，参考雄安规划流量增长
```

**验证：** `test -f docs/qa_experiment.md && grep -c "t 检验" docs/qa_experiment.md` → 输出 ≥ 1

### Day 6（8/29 周五）

- [ ] 参加模拟答辩
- [ ] 记录回答不好的问题
- [ ] 补充实验数据相关的应答依据
- [ ] 与 DA/DB 确认报告图表数据最终版

```bash
# 模拟答辩前确认所有数据文件可访问
ls experiments/results/*.csv docs/qa_experiment.md
```

**验证：** 模拟答辩记录中包含 ≥ 1 条待改进问题及补充答案

### Day 7（8/30-8/31）

- [ ] 协助最终提交
- [ ] Buffer：处理遗留问题
- [ ] 确认 experiments/ 目录最终状态干净
- [ ] 待命支持答辩

```bash
git status
ls experiments/results/
```

**验证：** `git status` 显示 experiments/ 下无未提交的脏文件，4 个核心 CSV 均已入库

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 数据最终核对 | 8/25 | 报告数字与 CSV 一致 |
| 2 | 结果文件完整 | 8/26 | 4 个 CSV 在仓库中正确提交 |
| 3 | 抽查验证 | 8/27 | 2 组重跑结果一致 |
| 4 | 答辩 Q&A | 8/28 | 4 个问题有答案（docs/qa_experiment.md） |

## 协作对接

- 与 **DA** 对接：报告数据引用对齐、图表数字最终确认
- 与 **TL** 对接：抽查 2 组实验重跑验证、最终提交
- 与 **DB** 对接：确认报告图表数据为最终版
