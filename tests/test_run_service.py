import json
import threading
from datetime import datetime, timezone

from core.run_models import RunRequest, RunStatus
from engine.run_service import RunService


class RecordingRunner:
    calls = []

    def __init__(self, **kwargs):
        self.artifacts = kwargs["artifacts"]
        type(self).calls.append(kwargs)

    def run(self, steps, stop_event=None):
        status = "stopped" if stop_event and stop_event.is_set() else "completed"
        self.artifacts.metrics.write_text("step\n0\n", encoding="utf-8")
        now = datetime.now(timezone.utc).isoformat()
        self.artifacts.write_metadata(
            status,
            "stop requested" if status == "stopped" else "",
            [self.artifacts.metrics],
            started_at=now,
            ended_at=now,
            sumo_version="test",
        )
        return []


def test_run_sync_returns_completed_result_with_isolated_artifacts(tmp_path):
    RecordingRunner.calls = []
    service = RunService(output_root=tmp_path, runner_factory=RecordingRunner)

    result = service.run_sync(RunRequest("1", "fixed_time", steps=2))

    assert result.status is RunStatus.COMPLETED
    assert result.run_dir.name == result.run_id
    assert json.loads((result.run_dir / "run_metadata.json").read_text())[
        "status"
    ] == "completed"
    assert len(RecordingRunner.calls) == 1


class BlockingRunner(RecordingRunner):
    release = threading.Event()
    started = threading.Event()

    def run(self, steps, stop_event=None):
        type(self).started.set()
        type(self).release.wait(timeout=5)
        return super().run(steps, stop_event=stop_event)


def test_concurrent_submissions_are_queued_with_unique_run_ids(tmp_path):
    BlockingRunner.release.clear()
    BlockingRunner.started.clear()
    service = RunService(output_root=tmp_path, runner_factory=BlockingRunner)

    first = service.submit(RunRequest("1", "fixed_time", steps=1))
    second = service.submit(RunRequest("1", "fixed_time", steps=1))

    assert first.status is RunStatus.QUEUED
    assert second.status is RunStatus.QUEUED
    assert first.run_id != second.run_id
    assert first.run_dir != second.run_dir
    assert service.max_workers == 1

    BlockingRunner.release.set()
    service.shutdown(wait=True)


def test_stop_sets_the_matching_run_event(tmp_path):
    BlockingRunner.release.clear()
    BlockingRunner.started.clear()
    service = RunService(output_root=tmp_path, runner_factory=BlockingRunner)
    queued = service.submit(RunRequest("1", "fixed_time", steps=10))
    assert BlockingRunner.started.wait(timeout=2)

    assert service.stop(queued.run_id) is True
    BlockingRunner.release.set()
    service.shutdown(wait=True)

    assert service.get(queued.run_id).status is RunStatus.STOPPED
    assert service.stop("missing") is False
