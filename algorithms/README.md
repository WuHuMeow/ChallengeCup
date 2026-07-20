# algorithms/

## 模块职责

算法库，定义标准算法接口（ABC），并实现三种递进式交通管控策略：固定配时基线、规则自适应、ML 增强。

## 当前完成情况

- [x] `base.py`：`BaseControlAlgorithm` 抽象基类，统一 `init(scene)` / `step(state)` / `reset()` / `name` 接口。
- [x] `fixed_time.py`：`FixedTimeAlgorithm` 可运行，默认使用 SUMO 默认程序；支持通过配置启用 Excel 配时写入。
- [x] `rule_adaptive.py`：`RuleAdaptiveAlgorithm` 基础实现，基于排队长度延长/切换绿灯。
- [ ] `ml_enhanced.py`：`MLEnhancedAlgorithm` 仅为骨架，未实现预测与排队的融合决策。

## 待完成情况

- [ ] `ml_enhanced.py`：实现云端预测 + 本地排队融合决策，输出真实 `ControlAction`。
- [ ] `fixed_time.py`：完善全红相位插入，精确还原 Excel 配时方案。
- [ ] `rule_adaptive.py`：根据实验结果调优阈值和相位切换策略。
- [ ] 补充 `docs/algorithm-design.md` 算法设计文档（配合成员6）。

## 需求分析

| 需求 | 说明 |
|------|------|
| 标准接口 | 三种算法必须实现统一 ABC，供 runner 统一调度 |
| 固定配时基线 | 读取 Excel 配时或 SUMO 默认程序，作为对照组 |
| 规则自适应 | 根据实时排队长度动态调整绿灯时长 |
| ML 增强 | 云端 XGBoost 预测未来流量，边缘规则融合决策 |
| 可解释性 | ML 增强不是端到端黑盒，需保留规则融合逻辑 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `base.py` | 标准算法接口 |
| `fixed_time.py` | 固定配时基线 |
| `rule_adaptive.py` | 规则自适应 |
| `ml_enhanced.py` | ML 增强（待完善） |

## 对外接口

```python
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from algorithms.ml_enhanced import MLEnhancedAlgorithm

algo = FixedTimeAlgorithm(use_excel_timing=True)
actions = algo.step(state)  # List[ControlAction]
```

## 负责人

- 成员3（算法负责人）主责；成员4（ML 模型工程师）提供 `CloudPolicy` 与 `model.pkl`。
