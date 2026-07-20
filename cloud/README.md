# cloud/

## 模块职责

云端策略层，封装离线训练好的 ML 模型，对外提供未来流量预测服务。在赛道 B 单机实现中，以模块边界模拟"云端"，供边缘 ML 增强算法调用。

## 当前完成情况

- [x] `cloud_policy.py`：`CloudPolicy` 类，负责加载 `ml/model.pkl`，提供 `predict(JointState) -> PredictionResult` 接口。
- [ ] 当前为兜底实现：若模型不存在，返回当前流量作为预测值，确保下游可运行。

## 待完成情况

- [ ] 接入真实的 `ml/model.pkl` 推理逻辑。
- [ ] 完善特征工程调用（`ml/features.py`），确保训练/推理特征维度一致。
- [ ] 可选：将 `CloudPolicy` 包装为独立服务进程，体现"云-边"分离。

## 需求分析

| 需求 | 说明 |
|------|------|
| 模型加载 | 离线训练产出 `ml/model.pkl`，运行时加载 |
| 预测服务 | 输入 `JointState`，输出未来各方向流量预测 |
| 兜底机制 | 模型未就绪时返回当前流量，避免阻塞仿真 |
| 云-边接口 | 清晰定义 `CloudPolicy.predict()` 输入输出 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `cloud_policy.py` | 云端流量预测服务封装 |

## 对外接口

```python
from cloud.cloud_policy import CloudPolicy
from core.types import JointState

policy = CloudPolicy()
pred = policy.predict(state)
```

## 负责人

- 成员4（ML 模型工程师）主责，成员3（算法负责人）消费预测结果。
