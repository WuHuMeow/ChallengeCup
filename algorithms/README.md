# algorithms/

## 模块职责

算法库，定义标准算法接口（ABC），并实现三种交通管控策略：固定配时基线、感应控制（Actuated）、CA-MP（容量感知最大压力）。

## 当前完成情况

- [x] `base.py`：`BaseControlAlgorithm` 抽象基类，统一 `init(scene)` / `step(state)` / `reset()` / `name` 接口。
- [x] `fixed_time.py`：`FixedTimeAlgorithm` 可运行，默认使用 SUMO 默认程序；支持通过配置启用 Excel 配时写入。
- [x] `rule_adaptive.py`：`RuleAdaptiveAlgorithm` 基础实现（感应控制基线），基于排队长度延长/切换绿灯。
- [ ] `ca_max_pressure.py`：CA-MP 骨架，待实现容量归一化压力 + 溢出门控 + 云端动态绿灯。

## 待完成情况

- [ ] `ca_max_pressure.py`：实现 CA-MP 核心逻辑（pressure = queue/capacity、occupancy > 90% 强制放行、动态绿灯时长）。
- [ ] `ca_max_pressure.py`：接入 EWMA 流量预测修正压力值。
- [ ] `fixed_time.py`：完善全红相位插入，精确还原 Excel 配时方案。
- [ ] `rule_adaptive.py`：根据实验结果调优阈值和相位切换策略。

## 需求分析

| 需求 | 说明 |
|------|------|
| 标准接口 | 三种算法必须实现统一 ABC，供 runner 统一调度 |
| 固定配时基线 | 读取 Excel 配时或 SUMO 默认程序，作为对照组 |
| 感应控制 | 根据实时排队长度动态调整绿灯时长（Actuated） |
| CA-MP | 容量归一化压力 + 溢出门控 + 云端参数自适应 |
| 可解释性 | CA-MP 基于经典 MaxPressure 理论，规则清晰可解释 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `base.py` | 标准算法接口 |
| `fixed_time.py` | 固定配时基线 |
| `rule_adaptive.py` | 感应控制（Actuated） |
| `ca_max_pressure.py` | CA-MP（核心创新，待完善） |

## 对外接口

```python
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm

algo = FixedTimeAlgorithm(use_excel_timing=True)
actions = algo.step(state)  # List[ControlAction]
```

## 负责人

- AA（算法 A）：FixedTimeController + ActuatedController（基线）
- AB（算法 B）：CAMaxPressureController（核心创新）+ EWMA 预测
