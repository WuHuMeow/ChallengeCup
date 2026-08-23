from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.realtime import RealtimeHub
from api.server import create_app
from api.websocket import stream_run_events
from core.run_models import RunRequest, RunResult, RunStatus
from core.types import MetricSummary
from engine.artifacts import RunArtifacts
from engine.events import EVENT_FIELDS
from experiments.evidence import (
    EvidenceWriter,
    RunManifest,
    canonical_mapping_sha256,
)
from scenes.registry import SceneRegistry
from visualization.frame_publisher import FramePublisher, FrameRecord


def _strict_completed_result(root: Path) -> RunResult:
    artifacts = RunArtifacts.create(
        root,
        "1",
        "fixed_time",
        1.0,
        42,
        run_id="run-1",
    )
    source_hashes = {"net": "b" * 64, "sumocfg": "c" * 64}
    writer = EvidenceWriter(artifacts.run_dir)
    writer.begin(
        RunManifest(
            run_id=artifacts.run_id,
            code_commit="a" * 40,
            scene_manifest_sha256=canonical_mapping_sha256(source_hashes),
            algorithm="fixed_time",
            parameters={},
            flow_multiplier=1.0,
            seed=42,
            duration_seconds=1.0,
            warmup_seconds=0.0,
            derived_steps=1,
            sumo_version="1.27.1",
            python_version="3.12.13",
            prediction_enabled=False,
            scene_id="1",
            scene_source_sha256=source_hashes,
            step_length=1.0,
            requested_seconds=1.0,
        )
    )
    artifacts.metrics.write_text(
        "step,timestamp,avg_queue_length,max_queue_length\n0,0,1,2\n",
        encoding="utf-8",
    )
    artifacts.step_log.write_text(
        "step,timestamp,current_phase\n0,0,0\n",
        encoding="utf-8",
    )
    with artifacts.events.open("w", newline="", encoding="utf-8") as output:
        csv.DictWriter(output, fieldnames=list(EVENT_FIELDS)).writeheader()
    artifacts.tripinfo.write_text(
        '<tripinfos><tripinfo id="v0" depart="0" arrival="1" duration="1" '
        'timeLoss="0" waitingCount="0"><emissions fuel_abs="1" '
        'CO2_abs="1000"/></tripinfo></tripinfos>',
        encoding="utf-8",
    )
    artifacts.stats.write_text(
        '<summary><step time="1"/></summary>',
        encoding="utf-8",
    )
    artifacts.trajectory.write_text("<fcd-export/>", encoding="utf-8")
    artifacts.collisions.write_text("<collisions/>", encoding="utf-8")
    summary = MetricSummary.from_raw_outputs(
        artifacts.run_dir,
        warmup_seconds=0.0,
    )
    writer.finalize(RunStatus.COMPLETED, summary)
    artifacts.write_status("queued", "")
    artifacts.write_status("starting", "")
    artifacts.write_status("running", "")
    artifacts.write_metadata(
        "completed",
        "",
        list(artifacts.run_dir.iterdir()),
        started_at="2026-08-22T00:00:00+00:00",
        ended_at="2026-08-22T00:00:01+00:00",
        sumo_version="1.27.1",
        requested_steps=1,
        requested_seconds=1.0,
        warmup_seconds=0.0,
        final_simulation_time=1.0,
        step_length=1.0,
    )
    writer.seal()
    return RunResult(
        "run-1",
        RunStatus.COMPLETED,
        "",
        artifacts.run_dir,
        json.loads(artifacts.summary.read_text(encoding="utf-8")),
    )


class FakeJudgeService:
    def __init__(self, root: Path):
        self.root = root
        self.output_root = root
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
    return FakeJudgeService(tmp_path / "runs")


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


def test_results_reject_valid_sealed_evidence_outside_service_output_root(
    client, service
):
    external = _strict_completed_result(service.root.parent / "external")
    service.records["run-1"] = external

    assert client.get("/api/results").json() == {"items": [], "count": 0}
    assert client.get("/api/results/run-1").status_code == 404


def test_safety_endpoint_returns_validated_canonical_counters(client, service):
    service.records["run-1"] = _strict_completed_result(service.root)

    response = client.get("/api/runs/run-1/safety")

    assert response.status_code == 200
    assert response.json() == {
        "collision": 0,
        "red_light": 0,
        "illegal_transition": 0,
        "harsh_braking": 0,
        "teleport": 0,
        "potential_conflict": 0,
    }


def test_scenes_include_validated_manifest_provenance(client):
    response = client.get("/api/scenes")

    assert response.status_code == 200
    row = response.json()[0]
    assert row["scene_id"] == row["intersection_id"]
    assert row["validation_status"] == "pass"
    assert isinstance(row["warnings"], list)
    assert row["step_length"] > 0
    assert row["sha256"]


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
    assert service.frame_publisher.latest("run-1") is None


def test_frame_endpoint_rejects_unknown_and_unavailable_sequence(client, service):
    service.records["run-1"] = RunResult(
        "run-1", RunStatus.RUNNING, "", service.root / "run-1", algorithm="fixed_time"
    )
    service.frame_publisher.publish(
        FrameRecord("run-1", 2, 12.5, b"png", 3.0)
    )

    assert client.get("/api/runs/missing/frame").status_code == 404
    assert client.get("/api/runs/run-1/frame?sequence=3").status_code == 404
    assert service.frame_publisher.can_capture("run-1") is True
    assert service.frame_publisher.publish(
        FrameRecord("run-1", 4, 14.0, b"new-png", 4.0)
    ) is True
    assert client.get("/api/runs/run-1/frame?sequence=3").status_code == 200


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


def test_events_websocket_releases_idle_subscription_on_disconnect(service):
    service.records["run-1"] = RunResult(
        "run-1", RunStatus.RUNNING, "", service.root / "run-1", algorithm="fixed_time"
    )

    async def exercise_disconnect():
        accepted = asyncio.Event()
        disconnected = asyncio.Event()

        class IdleDisconnectWebSocket:
            async def accept(self):
                accepted.set()

            async def receive(self):
                await disconnected.wait()
                return {"type": "websocket.disconnect", "code": 1000}

            async def send_json(self, _message):
                return None

        task = asyncio.create_task(
            stream_run_events(IdleDisconnectWebSocket(), service, "run-1")
        )
        await asyncio.wait_for(accepted.wait(), timeout=1)
        for _ in range(100):
            with service.realtime_hub._lock:
                subscriber_count = len(
                    service.realtime_hub._subscribers.get("run-1", ())
                )
            if subscriber_count == 1:
                break
            await asyncio.sleep(0)
        assert subscriber_count == 1

        disconnected.set()
        await asyncio.wait_for(task, timeout=1)
        with service.realtime_hub._lock:
            assert service.realtime_hub._subscribers.get("run-1", set()) == set()

    asyncio.run(exercise_disconnect())


def test_native_gui_returns_409_when_launcher_unavailable(client, service):
    service.records["run-1"] = RunResult(
        "run-1", RunStatus.RUNNING, "", service.root / "run-1", algorithm="fixed_time"
    )
    service.native_gui = lambda _run_id: (False, "display unavailable")

    response = client.post("/api/runs/run-1/native-gui")

    assert response.status_code == 409
    assert "display unavailable" in response.json()["detail"]


def test_native_gui_success_returns_only_shown_status(client, service):
    service.records["run-1"] = RunResult(
        "run-1", RunStatus.RUNNING, "", service.root / "run-1", algorithm="fixed_time"
    )
    service.native_gui = lambda _run_id: (True, "")

    response = client.post("/api/runs/run-1/native-gui")

    assert response.status_code == 200
    assert response.json() == {"status": "shown"}
