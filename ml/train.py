"""ML 流量预测模型训练、持久化与推理。

真实训练路径：train_flow_model() 用 scikit-learn GradientBoostingRegressor
在方向级流量样本上拟合"下一采样步流量"，经 joblib 持久化后由
cloud.cloud_policy.CloudPolicy 在线加载推理，EWMA 作为回退。

保留旧接口 train()/predict() 的签名兼容（返回 dict 含 "alpha"）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional, Sequence

import joblib
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.exceptions import NotFittedError

logger = logging.getLogger(__name__)

MODEL_TYPE = "gradient_boosting_flow_forecast"


def _matrix_from_rows(rows: Sequence[dict], feature_names: Sequence[str]) -> list[list[float]]:
    return [
        [float(row["features"][name]) for name in feature_names]
        for row in rows
    ]


def train_flow_model(
    rows: Sequence[dict],
    feature_names: Sequence[str],
    *,
    random_state: int = 42,
) -> dict:
    """在方向级样本上训练下一采样步流量预测模型。

    Args:
        rows: 数据集行，每行含 "features"（dict）与 "target"（float）。
        feature_names: 特征顺序，来自 ml.features.FEATURE_NAMES。
        random_state: 复现种子。

    Returns:
        模型 payload（dict），可经 save_flow_model 持久化。

    Raises:
        ValueError: 样本不足或特征缺失。
    """
    if len(rows) < 2:
        raise ValueError(f"need at least 2 samples to train, got {len(rows)}")
    missing = {
        name
        for row in rows
        for name in feature_names
        if name not in row["features"]
    }
    if missing:
        raise ValueError(f"rows missing feature columns: {sorted(missing)}")

    matrix = _matrix_from_rows(rows, feature_names)
    targets = [float(row["target"]) for row in rows]
    estimator = GradientBoostingRegressor(random_state=random_state)
    estimator.fit(matrix, targets)
    payload = {
        "model_type": MODEL_TYPE,
        "trained": True,
        "estimator": estimator,
        "feature_names": list(feature_names),
        "n_samples": len(rows),
    }
    logger.info(
        "train_flow_model: %d samples, %d features",
        len(rows), len(feature_names),
    )
    return payload


def save_flow_model(payload: dict, path: Path) -> Path:
    """持久化模型 payload（父目录不存在时自动创建）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, path)
    logger.info("save_flow_model: %s", path)
    return path


def load_flow_model(path: Path) -> Optional[dict]:
    """加载模型 payload；文件缺失返回 None。"""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        payload = joblib.load(path)
    except Exception as exc:  # noqa: BLE001 - 模型损坏时回退 EWMA
        logger.warning("load_flow_model failed: %s (%s)", path, exc)
        return None
    if not isinstance(payload, dict) or "estimator" not in payload:
        logger.warning("load_flow_model: unexpected payload in %s", path)
        return None
    return payload


def predict_flow(payload: dict, features: Dict[str, float]) -> float:
    """对单个方向级特征行预测下一采样步流量。

    Raises:
        ValueError: payload 未训练。
    """
    if not payload.get("trained") or "estimator" not in payload:
        raise ValueError("flow model payload is not trained")
    feature_names = payload["feature_names"]
    missing = [name for name in feature_names if name not in features]
    if missing:
        raise ValueError(f"features missing columns: {missing}")
    matrix = [[float(features[name]) for name in feature_names]]
    try:
        prediction = payload["estimator"].predict(matrix)
    except NotFittedError as exc:
        raise ValueError("flow model estimator is not fitted") from exc
    return float(prediction[0])


def train(
    features: Dict[str, list],
    labels: Dict[str, float],
    alpha: float = 0.3,
) -> Dict[str, float]:
    """旧接口：在 flows -> target 上训练小型 GBR，保持返回 dict 含 "alpha"。

    Args:
        features: 特征字典（使用 "flows" 列表作为单样本特征）。
        labels: 标签字典（"target"）。
        alpha: EWMA 平滑系数（回退预测使用）。

    Returns:
        模型参数字典。
    """
    flows = [float(value) for value in features.get("flows", [])]
    target = float(labels.get("target", 0.0))
    payload: Dict[str, object] = {"alpha": alpha}
    if len(flows) >= 1:
        estimator = GradientBoostingRegressor(random_state=42)
        try:
            estimator.fit([flows], [target])
            payload.update({
                "trained": True,
                "estimator": estimator,
                "feature_names": [f"flow_{i}" for i in range(len(flows))],
                "n_samples": 1,
            })
        except ValueError as exc:
            logger.warning("legacy train() fit failed: %s", exc)
            payload["trained"] = False
    else:
        payload["trained"] = False
    return payload


def predict(model: Dict[str, float], features: Dict[str, list]) -> float:
    """旧接口：有可用估计器时用模型预测，否则回退为流量均值。

    Args:
        model: train() 返回的模型字典。
        features: 特征字典（"flows"）。

    Returns:
        预测值。
    """
    flows = [float(value) for value in features.get("flows", [])]
    estimator = model.get("estimator")
    if (
        model.get("trained")
        and estimator is not None
        and flows
        and getattr(estimator, "n_features_in_", None) == len(flows)
    ):
        try:
            return float(estimator.predict([flows])[0])
        except (ValueError, NotFittedError):
            pass
    return float(sum(flows) / len(flows)) if flows else 0.0
