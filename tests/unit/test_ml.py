"""ML 模块接口契约测试。"""
from core.types import JointState, QueueState
from ml.features import extract_features
from ml.train import train, predict
from ml.evaluate import evaluate


def _make_state() -> JointState:
    return JointState(
        step=10, timestamp=10.0, tls_id="tls_0",
        current_phase=0, current_phase_name="p0",
        elapsed_phase_time=5.0,
        queues=[
            QueueState(direction="E0", queue_length=5.0, waiting_time=8.0, vehicle_count=6),
            QueueState(direction="E1", queue_length=3.0, waiting_time=4.0, vehicle_count=4),
        ],
        flows={"E0": 300.0, "E1": 200.0},
    )


def test_extract_features_returns_dict():
    features = extract_features(_make_state())
    assert isinstance(features, dict)
    assert "queue_lengths" in features
    assert "flows" in features


def test_extract_features_with_window():
    features = extract_features(_make_state(), window=10)
    assert isinstance(features, dict)


def test_train_returns_model_dict():
    features = {"queue_lengths": [5.0, 3.0], "flows": [300.0, 200.0]}
    labels = {"target": 350.0}
    model = train(features, labels)
    assert isinstance(model, dict)
    assert "alpha" in model


def test_predict_returns_float():
    model = {"alpha": 0.3}
    features = {"queue_lengths": [5.0], "flows": [300.0]}
    result = predict(model, features)
    assert isinstance(result, float)


def test_evaluate_returns_metrics():
    predictions = [100.0, 200.0, 300.0]
    actuals = [110.0, 190.0, 310.0]
    metrics = evaluate(predictions, actuals)
    assert isinstance(metrics, dict)
    assert "mae" in metrics
    assert "rmse" in metrics
    assert metrics["mae"] > 0
