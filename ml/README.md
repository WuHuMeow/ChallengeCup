# ML

## 模块职责

`ml/` 实现流量预测的真实训练闭环：从 formal 矩阵遥测构建方向级数据集、训练
GradientBoosting 流量预测模型、与 EWMA 基线对比评估、持久化模型供
`cloud.cloud_policy.CloudPolicy` 在线推理（模型优先、EWMA 回退）。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `features.py` | 特征契约：`FEATURE_NAMES` + `build_flow_feature_row()`（训练/推理共用顺序）+ JointState 特征提取 |
| `dataset.py` | 扫描 formal runs 的 `metrics.csv`，构建方向级滞后特征样本；按种子校准/留出分割 |
| `train.py` | `train_flow_model()` 真实训练（sklearn GradientBoostingRegressor）、`save/load_flow_model()`、`predict_flow()`；保留 `train()/predict()` 旧签名兼容 |
| `evaluate.py` | MAE/RMSE、`ewma_forecast()` 递归 EWMA、`compare_with_ewma()` 同集对比 |
| `model.pkl` | 训练产物（joblib），由 `scripts/train_ml.py` 生成，CloudPolicy 启动时加载 |

## 训练与复现

```bash
python scripts/train_ml.py
# 依赖 output/runs/formal/runs/ 与 output/runs/formal/matrix.csv（formal 矩阵遥测）
# 产物：ml/model.pkl + output/evidence/ml/evaluation.json（含 SHA-256 溯源）
```

- 样本：每个 (run, 方向) 展开为 `[flow_t, flow_lag1, queue_t, queue_lag1, avg_queue_t, phase]`
  → 下一采样步 flow（600s，与云端参数下发周期同尺度）。
- 分割：seed 42 训练 / seed 43、44 留出（与 `experiments/tuning.py` 的校准/留出口径一致）。
- 只使用 `matrix_kind == "normal"` 的 run，扰动 run 不进训练。

## 当前正式证据（2026-08-31，`output/evidence/ml/evaluation.json`）

| 指标（留出集 n=25,584） | GBR 模型 | EWMA(α=0.3) 基线 |
| --- | --- | --- |
| MAE (veh/h) | **3,810.2** | 4,885.2 |
| RMSE (veh/h) | **5,634.7** | 7,653.9 |

模型相对 EWMA 基线 MAE 改善约 **22%**。训练 12,792 样本耗时 < 1 秒。

## 对外接口

```python
from ml.dataset import build_dataset, split_by_seed
from ml.features import FEATURE_NAMES, build_flow_feature_row, extract_features
from ml.train import train_flow_model, save_flow_model, load_flow_model, predict_flow
from ml.evaluate import evaluate, ewma_forecast, compare_with_ewma

dataset = build_dataset(Path("output/runs/formal/runs"), matrix_csv=Path("output/runs/formal/matrix.csv"))
train_rows, test_rows = split_by_seed(dataset)
payload = train_flow_model(train_rows, list(FEATURE_NAMES))
value = predict_flow(payload, row["features"])
```

`CloudPolicy.predict()` 在 `ml/model.pkl` 存在且各方向已有滞后观测时使用模型，
否则回退 EWMA；`policy.model_source` 记录最近一次预测来源（`"model"` / `"ewma"`）。

## 已知限制

- 旧接口 `train()/predict()` 保持签名兼容：`train()` 在样本充足时真实拟合，
  `predict()` 无估计器时回退流量均值。
- `extract_features(window=...)` 的历史窗口参数仍未启用（方向级滞后在
  `dataset.py`/`CloudPolicy` 内部实现）。
- 空预测或真实值列表会返回零误差，调用方需自行区分"无样本"和"完美预测"。
