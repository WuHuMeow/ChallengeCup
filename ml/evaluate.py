"""ML 模型评估。

计算 RMSE、MAE、R²，并生成预测值 vs 真实值可视化。
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = logging.getLogger(__name__)


def evaluate(csv_file: Path, model_path: Path, output_dir: Path) -> dict:
    """评估模型在测试集上的表现。"""
    # TODO: 成员4 在此完善真实评估流程。
    df = pd.read_csv(csv_file)
    model = joblib.load(model_path)

    # 占位指标
    metrics = {
        "rmse": 0.0,
        "mae": 0.0,
        "r2": 0.0,
        "samples": len(df),
    }

    logger.info("评估结果: %s", metrics)
    return metrics


def plot_predictions(y_true, y_pred, output_dir: Path) -> None:
    """绘制预测值与真实值对比图。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 6))
    plt.scatter(y_true, y_pred, alpha=0.5)
    plt.xlabel("真实值")
    plt.ylabel("预测值")
    plt.title("流量预测：预测值 vs 真实值")
    plt.savefig(output_dir / "prediction_scatter.png")
    plt.close()
