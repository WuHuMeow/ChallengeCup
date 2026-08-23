from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.realtime import RealtimeHub
from api.server import create_app
from core.run_models import RunRequest, RunResult, RunStatus
from scenes.registry import SceneRegistry
from test_api import _strict_completed_result
from visualization.frame_publisher import FramePublisher


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
