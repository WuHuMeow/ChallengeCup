"""XGBoost 训练脚本。

从 CSV 数据集训练未来流量预测模型，输出 `ml/model.pkl`。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)


def load_dataset(csv_files: List[Path]) -> pd.DataFrame:
    """加载一个或多个 CSV 文件为训练数据。"""
    frames = [pd.read_csv(f) for f in csv_files]
    return pd.concat(frames, ignore_index=True)


def train(csv_files: List[Path], output_model: Path) -> None:
    """训练并保存模型。"""
    # TODO: 成员4 在此完善特征工程、模型选择、调参与评估。
    df = load_dataset(csv_files)
    logger.info("加载训练样本: %d 条, 特征数: %d", len(df), len(df.columns))

    # 占位：直接保存一个空模型文件，避免 CloudPolicy 加载失败。
    output_model.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(None, output_model)
    logger.info("模型已保存至: %s", output_model)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 3:
        print("Usage: python ml/train.py <csv1> <csv2> ... <output_model.pkl>")
        sys.exit(1)

    *csv_paths, model_path = sys.argv[1:]
    train([Path(p) for p in csv_paths], Path(model_path))
