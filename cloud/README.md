# cloud/

## 模块职责

云端策略层（CloudCoordinator），负责全局参数下发与 EWMA 流量预测。在赛道 B 单机实现中，以模块边界模拟"云端"，周期性向边缘节点下发 `min_green`/`max_green`/`base_green` 等参数，并根据全局压力动态调整。

## 当前完成情况

- [x] `cloud_policy.py`：`CloudPolicy` 类，EWMA 流量预测已实现（`predict()`），`dispatch_base_green()` MVI 已添加。

## 待完成情况

- [ ] `dispatch_base_green()`：根据全局压力评估动态调整 base_green（当前返回配置固定值）。
- [ ] 接入 ML 模型（XGBoost）作为 EWMA 的增强预测。
- [ ] 实现周期性参数下发调度逻辑。

## 需求分析

| 需求 | 说明 |
|------|------|
| 参数下发 | 周期性向边缘下发 min_green/max_green/base_green |
| EWMA 预测 | 轻量流量预测修正压力值 |
| 兜底机制 | 预测未就绪时使用默认参数，避免阻塞仿真 |
| 云-边接口 | 清晰定义 PredictionResult 输入输出 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `cloud_policy.py` | CloudCoordinator 全局参数下发（待重构） |

## 对外接口

```python
from cloud.cloud_policy import CloudPolicy
from core.types import JointState

policy = CloudPolicy()
pred = policy.predict(state)          # -> PredictionResult
base_green = policy.dispatch_base_green(state)  # -> float
```

## 负责人

- AB（算法 B）：CAMaxPressureController + EWMA 预测
- IB（仿真基础设施 B）：云-边-端消息流贯通
