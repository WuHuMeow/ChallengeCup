"""ML 流量预测训练闭环测试：dataset -> train -> evaluate -> CloudPolicy 接线。"""

import csv
import math
from pathlib import Path

import pytest

from core.types import JointState, QueueState
from ml.dataset import build_dataset, split_by_seed
from ml.evaluate import compare_with_ewma, ewma_forecast
from ml.features import FEATURE_NAMES, build_flow_feature_row
from ml.train import load_flow_model, predict_flow, save_flow_model, train_flow_model


def _write_metrics_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _metrics_row(
    step: int,
    phase: int,
    avg_queue: float,
    flows: dict[str, float],
    queues: dict[str, float],
) -> dict:
    row = {
        "step": step,
        "timestamp": float(step),
        "tls_id": "J1",
        "current_phase": phase,
        "avg_queue_length": avg_queue,
        "max_queue_length": avg_queue,
        "avg_delay": 0.0,
        "total_throughput": 0,
        "avg_travel_time": "",
        "total_stops": 0,
        "fuel_consumption": "",
    }
    for index, direction in enumerate(sorted(set(flows) | set(queues))):
        row[f"flow_{direction}_0"] = flows.get(direction, 0.0)
        row[f"queue_{direction}_0"] = queues.get(direction, 0.0)
    return row


def _write_run(
    root: Path,
    *,
    scene: str,
    algorithm: str,
    flow: str,
    seed: int,
    run_id: str,
    rows: list[dict],
) -> Path:
    run_dir = root / f"i{scene}" / algorithm / f"x{flow}" / f"s{seed}" / run_id
    _write_metrics_csv(run_dir / "metrics.csv", rows)
    return run_dir


@pytest.fixture()
def synthetic_runs(tmp_path: Path) -> Path:
    """两个 normal run（seed 42/43）+ 一个 disturbance run，每个 4 个时间步、单方向。"""
    root = tmp_path / "runs"
    _write_run(
        root,
        scene="1",
        algorithm="capacity_aware_maxpressure",
        flow="1.0",
        seed=42,
        run_id="run_a",
        rows=[
            _metrics_row(0, 0, 0.0, {"E0": 100.0}, {"E0": 0.0}),
            _metrics_row(600, 1, 1.0, {"E0": 200.0}, {"E0": 2.0}),
            _metrics_row(1200, 2, 2.0, {"E0": 300.0}, {"E0": 4.0}),
            _metrics_row(1800, 2, 3.0, {"E0": 400.0}, {"E0": 6.0}),
        ],
    )
    _write_run(
        root,
        scene="2",
        algorithm="fixed_time",
        flow="1.0",
        seed=43,
        run_id="run_b",
        rows=[
            _metrics_row(0, 0, 0.0, {"E0": 500.0}, {"E0": 0.0}),
            _metrics_row(600, 1, 1.0, {"E0": 600.0}, {"E0": 1.0}),
            _metrics_row(1200, 2, 2.0, {"E0": 700.0}, {"E0": 2.0}),
            _metrics_row(1800, 3, 3.0, {"E0": 800.0}, {"E0": 3.0}),
        ],
    )
    _write_run(
        root,
        scene="1",
        algorithm="capacity_aware_maxpressure",
        flow="1.0",
        seed=42,
        run_id="run_disturb",
        rows=[
            _metrics_row(0, 0, 0.0, {"E0": 10.0}, {"E0": 0.0}),
            _metrics_row(600, 1, 1.0, {"E0": 20.0}, {"E0": 1.0}),
            _metrics_row(1200, 2, 2.0, {"E0": 30.0}, {"E0": 2.0}),
        ],
    )
    matrix_rows = [
        {
            "run_dir": str(root / "i1" / "capacity_aware_maxpressure" / "x1.0" / "s42" / "run_a"),
            "matrix_kind": "normal",
        },
        {
            "run_dir": str(root / "i2" / "fixed_time" / "x1.0" / "s43" / "run_b"),
            "matrix_kind": "normal",
        },
        {
            "run_dir": str(root / "i1" / "capacity_aware_maxpressure" / "x1.0" / "s42" / "run_disturb"),
            "matrix_kind": "disturbance",
        },
    ]
    _write_metrics_csv(tmp_path / "matrix.csv", matrix_rows)
    return tmp_path


def test_feature_row_uses_documented_order():
    row = build_flow_feature_row(
        flow_t=300.0,
        flow_lag1=200.0,
        queue_t=4.0,
        queue_lag1=2.0,
        avg_queue_t=2.0,
        phase=2,
    )
    assert list(row) == list(FEATURE_NAMES)
    assert row["flow_t"] == 300.0
    assert row["queue_lag1"] == 2.0


def test_build_dataset_produces_lagged_direction_samples(synthetic_runs: Path):
    dataset = build_dataset(
        synthetic_runs / "runs", matrix_csv=synthetic_runs / "matrix.csv"
    )
    # 每个 normal run 有 4 个时间步：去掉首行（无滞后）与末行（无目标）→ 每方向 2 个样本。
    assert dataset["feature_names"] == list(FEATURE_NAMES)
    rows = dataset["rows"]
    assert len(rows) == 4  # 2 个 run x 1 个方向 x 2 个样本
    sample = next(
        row
        for row in rows
        if row["scene_id"] == "1" and row["step"] == 1200
    )
    assert sample["direction"] == "E0"
    assert sample["features"]["flow_t"] == 300.0
    assert sample["features"]["flow_lag1"] == 200.0
    assert sample["features"]["queue_t"] == 4.0
    assert sample["features"]["queue_lag1"] == 2.0
    assert sample["features"]["avg_queue_t"] == 2.0
    assert sample["features"]["phase"] == 2
    assert sample["target"] == 400.0  # 下一采样步 flow


def test_build_dataset_excludes_disturbance_runs(synthetic_runs: Path):
    dataset = build_dataset(
        synthetic_runs / "runs", matrix_csv=synthetic_runs / "matrix.csv"
    )
    assert all(row["matrix_kind"] == "normal" for row in dataset["rows"])
    assert not any(row["seed"] == 42 and row["scene_id"] == "1"
                   and row["step"] == 1200 and row["target"] == 40.0
                   for row in dataset["rows"])


def test_split_by_seed_has_no_leakage(synthetic_runs: Path):
    dataset = build_dataset(
        synthetic_runs / "runs", matrix_csv=synthetic_runs / "matrix.csv"
    )
    train_rows, test_rows = split_by_seed(dataset)
    assert {row["seed"] for row in train_rows} == {42}
    assert {row["seed"] for row in test_rows} == {43}
    assert train_rows and test_rows


def test_train_flow_model_fits_saves_and_loads():
    rows = [
        {
            "features": {"flow_t": float(flow), "flow_lag1": float(flow) - 10.0,
                         "queue_t": 1.0, "queue_lag1": 1.0,
                         "avg_queue_t": 1.0, "phase": 0},
            "target": 2.0 * float(flow),
            "seed": 42,
        }
        for flow in range(100, 200)
    ]
    payload = train_flow_model(rows, list(FEATURE_NAMES))
    assert payload["trained"] is True
    assert payload["feature_names"] == list(FEATURE_NAMES)
    assert payload["n_samples"] == len(rows)

    probe = build_flow_feature_row(150.0, 140.0, 1.0, 1.0, 1.0, 0)
    predicted = predict_flow(payload, probe)
    assert math.isclose(predicted, 300.0, rel_tol=0.1)

    with pytest.raises(ValueError):
        predict_flow({"trained": False, "feature_names": list(FEATURE_NAMES)}, probe)


def test_save_and_load_roundtrip(tmp_path: Path):
    rows = [
        {
            "features": {"flow_t": float(flow), "flow_lag1": float(flow),
                         "queue_t": 0.0, "queue_lag1": 0.0,
                         "avg_queue_t": 0.0, "phase": 0},
            "target": float(flow) + 1.0,
            "seed": 42,
        }
        for flow in range(50, 150)
    ]
    payload = train_flow_model(rows, list(FEATURE_NAMES))
    model_path = tmp_path / "model.pkl"
    save_flow_model(payload, model_path)
    loaded = load_flow_model(model_path)
    assert loaded is not None
    probe = build_flow_feature_row(120.0, 120.0, 0.0, 0.0, 0.0, 0)
    assert math.isclose(
        predict_flow(loaded, probe), predict_flow(payload, probe), rel_tol=1e-9
    )
    assert load_flow_model(tmp_path / "missing.pkl") is None


def test_legacy_train_and_predict_contract_still_holds():
    from ml.train import predict as legacy_predict
    from ml.train import train as legacy_train

    model = legacy_train({"flows": [300.0]}, {"target": 310.0})
    assert isinstance(model, dict)
    assert "alpha" in model
    result = legacy_predict({"alpha": 0.3}, {"flows": [300.0, 200.0]})
    assert isinstance(result, float)


def test_ewma_forecast_matches_recursive_formula():
    observations = [100.0, 200.0, 300.0, 400.0]
    predictions = ewma_forecast(observations, alpha=0.3)
    # pred[0]=obs[0]；pred[i]=alpha*obs[i-1]+(1-alpha)*pred[i-1]
    expected = [observations[0]]
    for observation, previous_prediction in zip(observations[:-1], expected):
        expected.append(0.3 * observation + 0.7 * previous_prediction)
    assert predictions == pytest.approx(expected)
    assert len(predictions) == len(observations)


def test_compare_with_ewma_reports_both_models():
    actuals = [100.0, 200.0, 300.0, 400.0]
    model_predictions = [110.0, 210.0, 310.0, 410.0]
    report = compare_with_ewma(actuals, model_predictions, alpha=0.3)
    assert report["n"] == 4
    assert report["model"]["mae"] == pytest.approx(10.0)
    assert report["ewma"]["mae"] >= 0.0
    assert set(report["model"]) == {"mae", "rmse"}


def _make_state(flows: dict[str, float], queues: dict[str, float], step: int) -> JointState:
    return JointState(
        step=step,
        timestamp=float(step),
        tls_id="tls_0",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=10.0,
        queues=[
            QueueState(direction=direction, queue_length=queue, waiting_time=0.0,
                       vehicle_count=queue, capacity=100.0)
            for direction, queue in queues.items()
        ],
        flows=flows,
    )


def test_cloud_policy_uses_saved_model_after_history_builds(tmp_path: Path):
    from cloud.cloud_policy import CloudPolicy

    rows = [
        {
            "features": {"flow_t": float(flow), "flow_lag1": float(flow),
                         "queue_t": 0.0, "queue_lag1": 0.0,
                         "avg_queue_t": 0.0, "phase": 0},
            "target": 2.0 * float(flow),
            "seed": 42,
        }
        for flow in range(100, 300)
    ]
    payload = train_flow_model(rows, list(FEATURE_NAMES))
    model_path = tmp_path / "model.pkl"
    save_flow_model(payload, model_path)

    policy = CloudPolicy(model_path=model_path)
    assert policy.model_source == "ewma"

    first = policy.predict(_make_state({"E0": 200.0}, {"E0": 5.0}, step=600))
    assert policy.model_source == "ewma"  # 首步无滞后特征，回退 EWMA
    assert first.predicted_flows["E0"] == pytest.approx(200.0 / 12.0)

    second = policy.predict(_make_state({"E0": 250.0}, {"E0": 5.0}, step=1200))
    assert policy.model_source == "model"
    # 模型学到 target = 2 * flow_t，EWMA 只会给出接近 250 的值
    assert second.predicted_flows["E0"] == pytest.approx(500.0 / 12.0, rel=0.15)


def test_cloud_policy_falls_back_to_ewma_without_model(tmp_path: Path):
    from cloud.cloud_policy import CloudPolicy

    policy = CloudPolicy(model_path=tmp_path / "missing.pkl")
    state_a = _make_state({"E0": 300.0}, {"E0": 1.0}, step=0)
    state_b = _make_state({"E0": 100.0}, {"E0": 1.0}, step=600)
    policy.predict(state_a)
    result = policy.predict(state_b)
    expected = (0.3 * 100.0 + 0.7 * 300.0) / 12.0
    assert result.predicted_flows["E0"] == pytest.approx(expected)
    assert policy.model_source == "ewma"


def test_cloud_policy_reset_clears_model_history(tmp_path: Path):
    from cloud.cloud_policy import CloudPolicy

    rows = [
        {
            "features": {"flow_t": float(flow), "flow_lag1": float(flow),
                         "queue_t": 0.0, "queue_lag1": 0.0,
                         "avg_queue_t": 0.0, "phase": 0},
            "target": 2.0 * float(flow),
            "seed": 42,
        }
        for flow in range(100, 300)
    ]
    payload = train_flow_model(rows, list(FEATURE_NAMES))
    model_path = tmp_path / "model.pkl"
    save_flow_model(payload, model_path)
    policy = CloudPolicy(model_path=model_path)
    policy.predict(_make_state({"E0": 200.0}, {"E0": 5.0}, step=600))
    policy.predict(_make_state({"E0": 250.0}, {"E0": 5.0}, step=1200))
    assert policy.model_source == "model"

    policy.reset()
    assert policy._flow_history == {}
    assert policy.model_source == "ewma"
