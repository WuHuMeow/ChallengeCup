# experiments/

## 模块职责

实验分析框架，负责多场景多算法交叉跑批、指标采集、结果汇总与统计检验。

## 当前完成情况

- [x] `runner.py`：`run_batch` 骨架，支持 20 路口 × 3 流量 × 3 算法批量实验配置。
- [x] `metrics.py`：基于 `JointState` 的单步指标计算（排队、延误、吞吐量近似）。
- [ ] `analyzer.py`：尚未实现。

## 待完成情况

- [ ] `runner.py`：支持替换流量变体、断点续跑、异常处理、结果汇总 CSV。
- [ ] `metrics.py`：接入精确的行程时间、燃油消耗（需 `tripinfo` 输出或 TraCI 精确读取）。
- [ ] `analyzer.py`：实现配对 t 检验、效应量、汇总表生成。
- [ ] 实现 27 次预跑批与 180 次全量跑批脚本。

## 需求分析

| 需求 | 说明 |
|------|------|
| 跑批规模 | 60 场景 × 3 算法 = 180 次仿真 |
| 指标覆盖 | 排队长度、延误、行程时间、通行量、停车次数、燃油消耗 |
| 统计检验 | 配对 t 检验，量化 ML 增强相对固定配时的改进 |
| 断点续跑 | 支持分批完成 180 次仿真 |
| 结果汇总 | 生成 `output/full_comparison.csv` 供可视化使用 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `runner.py` | 批量跑批框架 |
| `metrics.py` | 指标计算 |
| `analyzer.py` | 统计检验（待实现） |

## 对外接口

```python
from experiments.runner import run_batch

results = run_batch(
    intersection_ids=["1", "2", "3"],
    algorithms=["fixed_time", "rule_adaptive", "ml_enhanced"],
    steps=3600,
)
```

## 负责人

- 成员5（实验跑批工程师）主责，成员8（工程化）配合统计分析，成员1/成员2 配合异常场景处理。
