"""ML 模型评估。

计算 MAE、RMSE 指标，并提供与 EWMA 基线的同集对比。
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List

logger = logging.getLogger(__name__)


def evaluate(predictions: List[float], actuals: List[float]) -> Dict[str, float]:
    """评估预测结果。

    Args:
        predictions: 预测值列表。
        actuals: 真实值列表。

    Returns:
        指标字典 {"mae": ..., "rmse": ...}。
    """
    if not predictions or not actuals:
        return {"mae": 0.0, "rmse": 0.0}

    n = min(len(predictions), len(actuals))
    errors = [abs(predictions[i] - actuals[i]) for i in range(n)]
    mae = sum(errors) / n
    rmse = math.sqrt(sum(e ** 2 for e in errors) / n)

    logger.info("评估结果: MAE=%.4f, RMSE=%.4f (n=%d)", mae, rmse, n)
    return {"mae": mae, "rmse": rmse}


def ewma_forecast(observations: List[float], alpha: float = 0.3) -> List[float]:
    """递归 EWMA 一步预测：pred[0]=obs[0]；pred[i]=alpha*obs[i-1]+(1-alpha)*pred[i-1]。"""
    if not observations:
        return []
    predictions = [float(observations[0])]
    for index in range(1, len(observations)):
        predictions.append(
            alpha * observations[index - 1] + (1.0 - alpha) * predictions[index - 1]
        )
    return predictions


def compare_with_ewma(
    actuals: List[float],
    model_predictions: List[float],
    alpha: float = 0.3,
) -> Dict[str, object]:
    """在同一测试集上对比 ML 模型与 EWMA 基线。

    EWMA 的输入取 actuals 的观测序列（递归一步预测），
    与 ML 模型共享同一评估口径（样本逐点对齐）。

    Returns:
        {"n": int, "model": {"mae","rmse"}, "ewma": {"mae","rmse"}}
    """
    ewma_predictions = ewma_forecast(actuals, alpha=alpha)
    report = {
        "n": min(len(actuals), len(model_predictions)),
        "model": evaluate(model_predictions, actuals),
        "ewma": evaluate(ewma_predictions, actuals),
    }
    logger.info(
        "对比结果: model MAE=%.4f vs EWMA MAE=%.4f (n=%d)",
        report["model"]["mae"], report["ewma"]["mae"], report["n"],
    )
    return report
