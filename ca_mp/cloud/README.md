# Cloud

## 模块职责

`cloud/` 在单机进程内模拟云端策略服务：维护每个方向的 EWMA 流量预测，并按全局平均压力周期性下发绿灯参数。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `cloud_policy.py` | `CloudPolicy` 预测、压力分档、参数缓存和重置 |

## 对外接口

```python
from cloud.cloud_policy import CloudPolicy

policy = CloudPolicy()
prediction = policy.predict(state)
params = policy.dispatch_params(state)
base_green = policy.dispatch_base_green(state)
policy.reset()
```

## 输入与输出

- 输入：包含 `flows`、`queues`、`step` 的 `JointState`。
- `predict()` 输出 `PredictionResult`，其中包含预测时域和各方向预测流量。
- `dispatch_params()` 输出 `min_green`、`max_green`、`base_green` 字典，并在配置的更新间隔内复用缓存。

## 依赖

- 参数来自 `config/default.yaml` 的 `algorithms.ca_maxpressure`。
- 数据契约来自 `core.types`。
- 若 `paths.model_path` 指向有效文件，会尝试通过 joblib 加载模型。

## 已知限制

- 已加载的模型当前不参与 `predict()`；在线预测始终使用进程内 EWMA 状态。
- 压力分档阈值和下发参数硬编码在 `PRESSURE_TIERS`，不从配置读取。
- `horizon_seconds` 直接等于步数，假设仿真步长为 1 秒。
- 云端边界仅是 Python 模块调用，没有网络传输、鉴权或多路口全局聚合服务。
