"""一键训练 ML 流量预测模型并生成评估证据。

用法（仓库根目录）：
    python scripts/train_ml.py
    python scripts/train_ml.py --run-root output/runs/formal/runs \
        --matrix-csv output/runs/formal/matrix.csv \
        --model-path ml/model.pkl \
        --evidence-dir output/evidence/ml

流程：扫描 formal 矩阵的 metrics.csv 遥测 -> 构建方向级样本（seed 42 训练 /
43、44 留出）-> 训练 GradientBoostingRegressor -> 与 EWMA(α=0.3) 基线在同
一留出集对比 MAE/RMSE -> 保存模型并写 evaluation.json（含 SHA-256 溯源）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.dataset import build_dataset, split_by_seed  # noqa: E402
from ml.evaluate import compare_with_ewma  # noqa: E402
from ml.features import FEATURE_NAMES  # noqa: E402
from ml.train import predict_flow, save_flow_model, train_flow_model  # noqa: E402

DEFAULT_RUN_ROOT = Path("output/runs/formal/runs")
DEFAULT_MATRIX_CSV = Path("output/runs/formal/matrix.csv")
DEFAULT_MODEL_PATH = Path("ml/model.pkl")
DEFAULT_EVIDENCE_DIR = Path("output/evidence/ml")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def train_from_telemetry(
    run_root: Path,
    matrix_csv: Path,
    model_path: Path,
    evidence_dir: Path,
) -> dict:
    """训练、评估、持久化并写证据；返回证据 payload。"""
    dataset = build_dataset(run_root, matrix_csv=matrix_csv)
    rows = dataset["rows"]
    if not rows:
        raise SystemExit(
            f"no training samples built from {run_root} "
            f"(matrix_csv={matrix_csv}); check telemetry availability"
        )
    train_rows, test_rows = split_by_seed(dataset)
    if not train_rows or not test_rows:
        raise SystemExit(
            f"empty split: train={len(train_rows)} test={len(test_rows)}; "
            "expected calibration seed 42 and holdout seeds in telemetry"
        )

    started = time.monotonic()
    payload = train_flow_model(train_rows, list(FEATURE_NAMES))
    train_seconds = time.monotonic() - started

    # 留出集逐点评估：模型预测 vs EWMA(α=0.3) 递归预测，标签口径一致。
    ordered = sorted(test_rows, key=lambda row: (row["scene_id"], row["direction"], row["step"]))
    actuals = [float(row["target"]) for row in ordered]
    model_predictions = [predict_flow(payload, row["features"]) for row in ordered]

    # EWMA 需要按 (scene, direction) 时间顺序的观测序列做递归预测。
    ewma_predictions: list[float] = []
    from ml.evaluate import ewma_forecast

    series_groups: dict[tuple[str, str], list[dict]] = {}
    for row in ordered:
        series_groups.setdefault((row["scene_id"], row["direction"]), []).append(row)
    for key in sorted(series_groups):
        group = series_groups[key]
        observations = [float(row["features"]["flow_t"]) for row in group]
        ewma_predictions.extend(ewma_forecast(observations))

    report = compare_with_ewma(actuals, model_predictions)
    report["ewma"] = {
        "mae": _mae(ewma_predictions, actuals),
        "rmse": _rmse(ewma_predictions, actuals),
    }

    save_flow_model(payload, model_path)

    evidence = {
        "schema": "challenge-cup-ml-flow-forecast",
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_root": str(run_root),
        "matrix_csv": str(matrix_csv),
        "matrix_kind_filter": "normal",
        "feature_names": list(FEATURE_NAMES),
        "label": "next_sample_flow (veh/h, 600s ahead)",
        "split": {
            "calibration_seeds": [42],
            "holdout_seeds": sorted({int(row["seed"]) for row in test_rows}),
            "train_samples": len(train_rows),
            "holdout_samples": len(test_rows),
        },
        "model": {
            "type": payload["model_type"],
            "estimator": type(payload["estimator"]).__name__,
            "n_samples": payload["n_samples"],
            "train_seconds": round(train_seconds, 3),
            "path": str(model_path),
            "sha256": _sha256(model_path),
        },
        "evaluation": report,
    }
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / "evaluation.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"model saved to {model_path}")
    print(f"evidence written to {evidence_path}")
    print(
        f"holdout n={report['n']}: model MAE={report['model']['mae']:.2f} "
        f"vs EWMA MAE={report['ewma']['mae']:.2f}"
    )
    return evidence


def _mae(predictions: list[float], actuals: list[float]) -> float:
    if not predictions or not actuals:
        return 0.0
    n = min(len(predictions), len(actuals))
    return sum(abs(predictions[i] - actuals[i]) for i in range(n)) / n


def _rmse(predictions: list[float], actuals: list[float]) -> float:
    if not predictions or not actuals:
        return 0.0
    n = min(len(predictions), len(actuals))
    return (
        sum((predictions[i] - actuals[i]) ** 2 for i in range(n)) / n
    ) ** 0.5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--matrix-csv", type=Path, default=DEFAULT_MATRIX_CSV)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    if not args.matrix_csv.is_file():
        raise SystemExit(f"matrix.csv not found: {args.matrix_csv}")
    if not args.run_root.is_dir():
        raise SystemExit(f"run root not found: {args.run_root}")

    train_from_telemetry(
        args.run_root, args.matrix_csv, args.model_path, args.evidence_dir
    )


if __name__ == "__main__":
    main()
