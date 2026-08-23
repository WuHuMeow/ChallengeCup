from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.realtime import RealtimeHub
from api.server import create_app
from core.run_models import RunRequest, RunResult, RunStatus
from scenes.registry import SceneRegistry
from test_api import _strict_completed_result
from visualization.frame_publisher import FramePublisher, FrameRecord


class FakeJudgeService:
    def __init__(self, root: Path):
        self.root = root
        self.registry = SceneRegistry()
        self.records: dict[str, RunResult] = {}
        self.frame_publisher = FramePublisher()
        self.realtime_hub = RealtimeHub()
        self.max_workers = 1
        self.native_gui = None
        self.shutdown_calls = 0

    def submit(self, request: RunRequest) -> RunResult:
        result = RunResult(
            "run-1",
            RunStatus.QUEUED,
            "",
            self.root / "run-1",
            algorithm=request.algorithm,
        )
        self.records[result.run_id] = result
        return result

    def get(self, run_id: str) -> RunResult | None:
        return self.records.get(run_id)

    def list_results(self) -> tuple[RunResult, ...]:
        return tuple(self.records.values())

    def stop(self, run_id: str) -> bool:
        result = self.records.get(run_id)
        if result is None:
            return False
        self.records[run_id] = replace(result, status=RunStatus.INTERRUPTED)
        return True

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_calls += 1
        self.realtime_hub.close()
        self.frame_publisher.clear_all()


@pytest.fixture
def service(tmp_path):
    return FakeJudgeService(tmp_path)


@pytest.fixture
def client(service):
    return TestClient(create_app(service))


def test_results_endpoint_excludes_unsealed_and_unknown_runs(client, service):
    canonical = _strict_completed_result(service.root)
    service.records["run-1"] = canonical
    service.records["unsealed"] = RunResult(
        "unsealed",
        RunStatus.COMPLETED,
        "",
        service.root / "unsealed",
        {"metrics": {"throughput": 999}},
        "fixed_time",
    )

    response = client.get("/api/results")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert [item["run_id"] for item in payload["items"]] == ["run-1"]
    assert "run_dir" not in payload["items"][0]
    assert client.get("/api/results/missing").status_code == 404


def test_result_endpoint_reads_summary_from_sealed_disk(client, service):
    canonical = _strict_completed_result(service.root)
    service.records["run-1"] = replace(
        canonical,
        summary={"metrics": {"throughput": 999999}},
    )

    response = client.get("/api/results/run-1")

    assert response.status_code == 200
    assert response.json()["summary"]["metrics"]["throughput"] == 1


def test_frame_endpoint_returns_latest_png_and_metadata(client, service):
    service.records["run-1"] = RunResult(
        "run-1", RunStatus.RUNNING, "", service.root / "run-1", algorithm="fixed_time"
    )
    service.frame_publisher.publish(
        FrameRecord("run-1", 2, 12.5, b"png", 3.0)
    )

    response = client.get("/api/runs/run-1/frame")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-run-id"] == "run-1"
    assert response.headers["x-frame-sequence"] == "2"
    assert response.headers["x-simulation-time"] == "12.5"
    assert response.content == b"png"


def test_frame_endpoint_rejects_unknown_and_unavailable_sequence(client, service):
    service.records["run-1"] = RunResult(
        "run-1", RunStatus.RUNNING, "", service.root / "run-1", algorithm="fixed_time"
    )
    service.frame_publisher.publish(
        FrameRecord("run-1", 2, 12.5, b"png", 3.0)
    )

    assert client.get("/api/runs/missing/frame").status_code == 404
    assert client.get("/api/runs/run-1/frame?sequence=3").status_code == 404
    assert client.get("/api/runs/run-1/frame?sequence=1").status_code == 200


def test_static_serving_is_contained_and_lifespan_shuts_down_service(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("judge", encoding="utf-8")
    service = FakeJudgeService(tmp_path / "runs")

    with TestClient(create_app(service, web_dist=dist)) as isolated_client:
        assert isolated_client.get("/").text == "judge"
        assert isolated_client.get("/../pyproject.toml").status_code != 200

    assert service.shutdown_calls == 1


def test_events_websocket_replays_latest_and_receives_live_message(client, service):
    service.records["run-1"] = RunResult(
        "run-1", RunStatus.RUNNING, "", service.root / "run-1", algorithm="fixed_time"
    )
    service.realtime_hub.publish(
        "run-1", {"type": "status", "status": "queued"}
    )

    with client.websocket_connect("/api/runs/run-1/events") as socket:
        assert socket.receive_json()["status"] == "queued"
        service.realtime_hub.publish(
            "run-1", {"type": "metrics", "simulation_time": 1.0}
        )
        assert socket.receive_json()["type"] == "metrics"


def test_events_websocket_rejects_unknown_run(client):
    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect("/api/runs/missing/events"):
            pass
    assert caught.value.code == 4404


def test_native_gui_returns_409_when_launcher_unavailable(client, service):
    service.records["run-1"] = RunResult(
        "run-1", RunStatus.RUNNING, "", service.root / "run-1", algorithm="fixed_time"
    )
    service.native_gui = lambda _run_id: (False, "display unavailable")

    response = client.post("/api/runs/run-1/native-gui")

    assert response.status_code == 409
    assert "display unavailable" in response.json()["detail"]
