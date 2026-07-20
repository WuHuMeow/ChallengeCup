# ml/

## 模块职责

机器学习模块，负责特征工程、XGBoost 模型训练、模型评估，并产出 `ml/model.pkl` 供云端预测服务使用。

## 当前完成情况

- [x] `features.py`：特征工程骨架，提供 `extract_features(state, history)` 接口。
- [x] `train.py`：训练脚本骨架，支持命令行调用。
- [x] `evaluate.py`：模型评估骨架，提供 RMSE/MAE/R² 占位。
- [ ] 尚未产出真实 `model.pkl`。

## 待完成情况

- [ ] `features.py`：根据 CSV 数据实现滑动窗口、时段 one-hot、方向级特征等。
- [ ] `train.py`：实现完整 XGBoost 训练流水线，输出 `model.pkl`。
- [ ] `evaluate.py`：实现真实评估指标计算与预测-真实散点图绘制。
- [ ] 准备随机森林 / LightGBM 备选模型兜底方案。
- [ ] 按路口划分训练/验证/测试集，防止数据泄漏。

## 需求分析

| 需求 | 说明 |
|------|------|
| 预测目标 | 根据过去 5 分钟状态，预测未来 5 分钟各方向流量 |
| 特征工程 | 历史流量窗口、排队趋势、当前相位、时段编码 |
| 模型选择 | 主模型 XGBoost，备选随机森林/LightGBM |
| 评估指标 | RMSE、MAE、R²、特征重要性 |
| 数据泄漏防护 | 按路口分层划分训练/测试集 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `features.py` | 特征工程 |
| `train.py` | XGBoost 训练脚本 |
| `evaluate.py` | 模型评估 |
| `model.pkl` | 训练产出（待生成） |

## 对外接口

```bash
python ml/train.py data/output/*.csv ml/model.pkl
python ml/evaluate.py data/output/test.csv ml/model.pkl output/
```

## 负责人

- 成员4（ML 模型工程师）主责，成员1（仿真引擎工程师）提供训练 CSV。
