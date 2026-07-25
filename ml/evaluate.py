"""ML 模型评估。

计算 MAE、RMSE 指标。
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
