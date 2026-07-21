# ml/

## 模块职责

机器学习模块，负责 EWMA（指数加权移动平均）轻量流量预测，为 CA-MP 算法提供短期流量趋势，修正压力值计算。

## 当前完成情况

- [x] `features.py`：特征工程 MVI，提供 `extract_features(state, window=5) -> dict` 接口。
- [x] `train.py`：训练与预测 MVI，提供 `train(features, labels, alpha) -> dict` 和 `predict(model, features) -> float`。
- [x] `evaluate.py`：模型评估，提供 `evaluate(predictions, actuals) -> dict`（MAE、RMSE）。

## 待完成情况

- [ ] `features.py`：实现 EWMA 滑动窗口特征（历史流量、排队趋势），利用 `window` 参数。
- [ ] `train.py`：实现 EWMA 参数校准（α 值选择），替换当前 MVI 默认返回。
- [ ] `train.py`：`predict()` 接入真实模型推理，替换当前流量均值返回。
- [ ] 产出 EWMA 模型参数供 CloudCoordinator 使用。

## 接口签名

```python
# features.py
def extract_features(state: JointState, window: int = 5) -> Dict[str, list]: ...

# train.py
def train(features: Dict[str, list], labels: Dict[str, float], alpha: float = 0.3) -> Dict[str, float]: ...
def predict(model: Dict[str, float], features: Dict[str, list]) -> float: ...

# evaluate.py
def evaluate(predictions: List[float], actuals: List[float]) -> Dict[str, float]: ...  # {"mae": ..., "rmse": ...}
```

## 需求分析

| 需求 | 说明 |
|------|------|
| 预测目标 | 根据历史流量 EWMA 预测未来短期流量趋势 |
| 轻量级 | EWMA 不需要 GPU，计算开销极小 |
| 修正压力 | 预测结果用于修正 CA-MP 的 pressure 计算 |
| 评估指标 | MAE、RMSE |

## 关键文件

| 文件 | 说明 |
|------|------|
| `features.py` | EWMA 特征工程 |
| `train.py` | EWMA 参数校准 + 预测 |
| `evaluate.py` | 预测精度评估 |

## 负责人

- AB（算法 B）：EWMA 预测实现与 CA-MP 集成
