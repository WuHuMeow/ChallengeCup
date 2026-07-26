from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from core.run_models import RunResult, RunStatus
from scenes.registry import SceneRegistry


class FakeRunService:
    def __init__(self, root: Path):
        self.root = root
        self.registry = SceneRegistry()
        self.records: dict[str, RunResult] = {}
        self.requests = []

    def submit(self, request):
        self.requests.append(request)
        result = RunResult(
            run_id="run-1",
            status=RunStatus.QUEUED,
            reason="",
            run_dir=self.root / "run-1",
        )
        self.records[result.run_id] = result
        return result

    def get(self, run_id):
        return self.records.get(run_id)

    def stop(self, run_id):
        if run_id not in self.records:
            return False
        current = self.records[run_id]
        self.records[run_id] = RunResult(
            current.run_id,
            RunStatus.STOPPED,
            "stop requested",
            current.run_dir,
        )
        return True


@pytest.fixture
def service(tmp_path):
    return FakeRunService(tmp_path)


@pytest.fixture
def client(service):
    return TestClient(create_app(service))


def test_health_reports_serialized_run_service(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "run_workers": 1}


def test_scenes_are_real_registry_rows(client):
    response = client.get("/api/scenes")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 20
    assert rows[0]["intersection_id"]
    assert rows[0]["name"]


def test_submit_read_and_stop_run(client, service):
    response = client.post("/api/runs", json={
        "intersection_id": "1",
        "algorithm": "fixed_time",
        "steps": 100,
        "flow_multiplier": 1.0,
        "seed": 42,
    })

    assert response.status_code == 202
    assert response.json()["run_id"] == "run-1"
    assert service.requests[0].intersection_id == "1"
    assert client.get("/api/runs/run-1").json()["status"] == "queued"
    assert client.post("/api/runs/run-1/stop").json()["status"] == "stopped"


def test_unknown_run_returns_404(client):
    assert client.get("/api/runs/missing").status_code == 404
    assert client.post("/api/runs/missing/stop").status_code == 404


def test_metrics_endpoint_returns_real_summary(client, service):
    run_dir = service.root / "run-1"
    service.records["run-1"] = RunResult(
        "run-1",
        RunStatus.COMPLETED,
        "",
        run_dir,
        {"metrics": {"avg_travel_time": 12.5}},
    )

    response = client.get("/api/runs/run-1/metrics")

    assert response.status_code == 200
    assert response.json()["avg_travel_time"] == 12.5


def _state_payload():
    return {
        "step": 10,
        "timestamp": 1.0,
        "tls_id": "tls_0",
        "current_phase": 0,
        "current_phase_name": "phase_0",
        "elapsed_phase_time": 12.0,
        "queues": [{
            "direction": "north",
            "queue_length": 5.0,
            "waiting_time": 10.0,
            "vehicle_count": 6,
            "capacity": 20.0,
        }],
        "flows": {"north": 300.0},
    }


def test_cloud_and_edge_endpoints_use_shared_state_contract(client):
    prediction = client.post("/api/cloud/predict", json={"state": _state_payload()})
    actions = client.post("/api/edge/control", json={"state": _state_payload()})

    assert prediction.status_code == 200
    assert "predicted_flows" in prediction.json()
    assert actions.status_code == 200
    assert isinstance(actions.json()["actions"], list)


def test_legacy_health_and_scenes_are_deprecated_wrappers(client):
    assert client.get("/health").json()["status"] == "ok"
    assert len(client.get("/scenes").json()) == 20
