# experiments/

## 模块职责

实验分析框架，负责多场景多算法交叉跑批、指标采集、结果汇总与统计检验。

## 当前完成情况

- [x] `runner.py`：`run_batch` 支持 20 路口 × 2 流量 × 3 算法 × 3 种子 = 360 次批量实验。
- [x] `metrics.py`：基于 `JointState` 的单步指标计算（排队、延误、吞吐量近似）。

## 待完成情况

- [ ] `runner.py`：支持断点续跑、异常处理、结果汇总 CSV。
- [ ] `metrics.py`：接入精确的行程时间、燃油消耗（需 `tripinfo` 输出或 TraCI 精确读取）。
- [ ] 实现配对 t 检验、效应量、汇总表生成（统计检验模块）。

## 需求分析

| 需求 | 说明 |
|------|------|
| 跑批规模 | 20 路口 × 3 算法 × 2 流量 × 3 种子 = 360 次仿真 |
| 指标覆盖 | 平均行程时间、排队长度、吞吐量、油耗、延误、停车次数 |
| 统计检验 | 配对 t 检验，量化 CA-MP 相对固定配时的改进 |
| 断点续跑 | 支持分批完成 360 次仿真 |
| 结果汇总 | 生成 `output/full_comparison.csv` 供可视化使用 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `runner.py` | 批量跑批框架（360 次） |
| `metrics.py` | 指标计算 |

## 对外接口

```python
from experiments.runner import run_batch

results = run_batch(
    intersection_ids=["1", "2", "3"],
    algorithms=["fixed_time", "actuated", "ca_maxpressure"],
    seeds=[42, 123, 456],
    steps=3600,
)
```

## 负责人

- EX（实验组）：实验矩阵设计、批量运行、指标采集、统计分析
