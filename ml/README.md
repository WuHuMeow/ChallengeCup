# ML

## 模块职责

`ml/` 定义从 `JointState` 提取特征、生成轻量模型参数、执行预测和计算预测误差的最小接口。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `features.py` | 提取队列、流量、等待时间和当前相位特征 |
| `train.py` | 返回模型参数字典并基于流量均值预测 |
| `evaluate.py` | 计算 MAE 和 RMSE |

## 对外接口

```python
from ml.evaluate import evaluate
from ml.features import extract_features
from ml.train import predict, train

features = extract_features(state, window=5)
model = train(features, labels, alpha=0.3)
value = predict(model, features)
metrics = evaluate([value], actuals)
```

## 输入与输出

- `extract_features()` 输入 `JointState`，输出列表型特征字典。
- `train()` 输入特征、标签和 alpha，输出模型参数字典。
- `predict()` 输出单个浮点预测值。
- `evaluate()` 输出 `{"mae": ..., "rmse": ...}`。

## 依赖

- 仅依赖 Python 标准库和 `core.types.JointState`。
- `CloudPolicy` 有独立 EWMA 实现，当前不调用本目录的训练/预测函数。

## 已知限制

- `window` 参数当前未使用，特征不包含历史窗口。
- `train()` 不执行拟合并返回 `trained=False`。
- `predict()` 忽略模型参数，返回当前流量特征的均值。
- 空预测或真实值列表会返回零误差，调用方需自行区分“无样本”和“完美预测”。
