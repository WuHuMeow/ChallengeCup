import json
import subprocess
import threading
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from algorithms.fixed_time import FixedTimeAlgorithm
from core.run_models import RunRequest, RunResult, RunStatus
from core.timebase import SimulationWindow
from engine.artifacts import RunArtifacts
from engine.mock_bridge import MockBridge
from engine.run_service import RunService
from engine.run_state import RunStateMachine
from engine.runner import SimulationRunner
from engine.traci_bridge import TraCIBridge, traci
from scenes.registry import SceneRegistry


def _result(tmp_path, status=RunStatus.QUEUED):
    return RunResult("run-1", status, "", tmp_path / "run-1", algorithm="fixed_time")


def test_state_machine_enforces_order_and_preserves_terminal_result(tmp_path):
    machine = RunStateMachine()
    queued = _result(tmp_path)
    machine.register(queued)

    assert machine.transition("run-1", RunStatus.STARTING, "").status is RunStatus.STARTING
    assert machine.transition("run-1", RunStatus.RUNNING, "").status is RunStatus.RUNNING
    assert machine.transition("run-1", RunStatus.STOPPING, "stop requested").status is RunStatus.STOPPING
    terminal = machine.transition("run-1", RunStatus.INTERRUPTED, "stop requested")

    with pytest.raises(ValueError, match="terminal"):
        machine.transition("run-1", RunStatus.FAILED, "late cleanup error")
    assert machine.get("run-1") is terminal


def test_state_machine_rejects_skipped_and_unknown_transitions(tmp_path):
    machine = RunStateMachine()
    machine.register(_result(tmp_path))

    with pytest.raises(ValueError, match="queued.*running"):
        machine.transition("run-1", RunStatus.RUNNING, "")
    with pytest.raises(KeyError, match="missing"):
        machine.transition("missing", RunStatus.STARTING, "")


class _LifecycleRunner:
    started = threading.Event()
    calls = []

    def __init__(self, **kwargs):
        self.artifacts = kwargs["artifacts"]
        type(self).calls.append(self)

    def run(self, window, stop_event=None, frame_sink=None):
        assert isinstance(window, SimulationWindow)
        type(self).started.set()
        assert stop_event is not None
        stop_event.wait(timeout=5)
        status = RunStatus.INTERRUPTED if stop_event.is_set() else RunStatus.COMPLETED
        now = datetime.now(timezone.utc).isoformat()
        self.artifacts.write_metadata(
            status.value,
            "stop requested" if status is RunStatus.INTERRUPTED else "",
            [],
            started_at=now,
            ended_at=now,
            sumo_version="test",
        )
        return RunResult(
            self.artifacts.run_id,
            status,
            "stop requested" if status is RunStatus.INTERRUPTED else "",
            self.artifacts.run_dir,
            algorithm=self.artifacts.algorithm,
        )


def _wait_for_status(service, run_id, expected, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = service.get(run_id)
        if result is not None and result.status is expected:
            return result
        time.sleep(0.001)
    raise AssertionError(f"run {run_id} did not reach {expected.value}")


class _ReleaseAfterStopRunner(_LifecycleRunner):
    stop_observed = threading.Event()
    release = threading.Event()

    def run(self, window, stop_event=None, frame_sink=None):
        assert isinstance(window, SimulationWindow)
        type(self).started.set()
        assert stop_event is not None
        assert stop_event.wait(timeout=5)
        type(self).stop_observed.set()
        assert type(self).release.wait(timeout=5)
        return super().run(window, stop_event=stop_event, frame_sink=frame_sink)


class _CompletedRunner(_LifecycleRunner):
    published = threading.Event()
    release = threading.Event()

    def run(self, window, stop_event=None, frame_sink=None):
        now = datetime.now(timezone.utc).isoformat()
        self.artifacts.write_metadata(
            RunStatus.COMPLETED.value,
            "",
            [],
            started_at=now,
            ended_at=now,
            sumo_version="test",
        )
        type(self).published.set()
        return RunResult(
            self.artifacts.run_id,
            RunStatus.COMPLETED,
            "",
            self.artifacts.run_dir,
            algorithm=self.artifacts.algorithm,
        )


class _ArtifactTerminalRunner(_LifecycleRunner):
    published = threading.Event()
    release = threading.Event()

    def run(self, window, stop_event=None, frame_sink=None):
        now = datetime.now(timezone.utc).isoformat()
        self.artifacts.write_metadata(
            RunStatus.COMPLETED.value,
            "",
            [],
            started_at=now,
            ended_at=now,
            sumo_version="test",
        )
        type(self).published.set()
        assert type(self).release.wait(timeout=5)
        return RunResult(
            self.artifacts.run_id,
            RunStatus.COMPLETED,
            "",
            self.artifacts.run_dir,
            algorithm=self.artifacts.algorithm,
        )


def test_stop_waits_for_owned_future_and_is_idempotent(tmp_path):
    _LifecycleRunner.started.clear()
    _LifecycleRunner.calls.clear()
    service = RunService(output_root=tmp_path, runner_factory=_LifecycleRunner)
    queued = service.submit(RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0))
    assert _LifecycleRunner.started.wait(timeout=2)

    assert service.stop(queued.run_id) is True
    terminal = service.get(queued.run_id)

    assert terminal.status is RunStatus.INTERRUPTED
    assert service.stop(queued.run_id) is False
    assert json.loads((terminal.run_dir / "status.json").read_text())["status"] == "interrupted"
    service.shutdown()


def test_stop_waits_after_terminal_state_publication_until_cleanup(
    monkeypatch, tmp_path
):
    _CompletedRunner.published.clear()
    _CompletedRunner.release.clear()
    service = RunService(output_root=tmp_path, runner_factory=_CompletedRunner)
    terminal_published = threading.Event()
    wait_entered = threading.Event()
    wait_returned = threading.Event()
    original_transition = service._states.transition
    original_wait_until_done = service._wait_until_done

    def transition_with_terminal_pause(run_id, new_status, reason, **kwargs):
        result = original_transition(run_id, new_status, reason, **kwargs)
        if new_status is RunStatus.COMPLETED:
            terminal_published.set()
        if new_status is RunStatus.COMPLETED:
            assert _CompletedRunner.published.is_set()
            assert _CompletedRunner.release.wait(timeout=5)
        return result

    def observed_wait_until_done(run_id):
        wait_entered.set()
        try:
            return original_wait_until_done(run_id)
        finally:
            wait_returned.set()

    monkeypatch.setattr(service._states, "transition", transition_with_terminal_pause)
    monkeypatch.setattr(service, "_wait_until_done", observed_wait_until_done)
    queued = service.submit(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )
    assert terminal_published.wait(timeout=2)

    stop_results = []
    stop_errors = []
    stopper = threading.Thread(
        target=lambda: _capture_stop(service, queued.run_id, stop_results, stop_errors),
        name="terminal-stopper",
    )
    stopper.start()
    try:
        assert wait_entered.wait(timeout=2)
        assert not wait_returned.is_set()
        assert stop_results == []
        assert stop_errors == []
    finally:
        _CompletedRunner.release.set()
        try:
            assert wait_returned.wait(timeout=5)
        finally:
            stopper.join(timeout=5)
            service.shutdown()

    assert not stopper.is_alive()
    assert stop_results == [False]
    assert service.get(queued.run_id).status is RunStatus.COMPLETED
    assert json.loads((queued.run_dir / "status.json").read_text())["status"] == "completed"


def test_stop_handles_terminal_artifact_before_state_publication(
    monkeypatch, tmp_path
):
    _ArtifactTerminalRunner.published.clear()
    _ArtifactTerminalRunner.release.clear()
    service = RunService(output_root=tmp_path, runner_factory=_ArtifactTerminalRunner)
    wait_entered = threading.Event()
    wait_returned = threading.Event()
    original_wait_until_done = service._wait_until_done

    def observed_wait_until_done(run_id):
        wait_entered.set()
        try:
            return original_wait_until_done(run_id)
        finally:
            wait_returned.set()

    monkeypatch.setattr(service, "_wait_until_done", observed_wait_until_done)
    queued = service.submit(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )
    assert _ArtifactTerminalRunner.published.wait(timeout=2)

    stop_results = []
    stop_errors = []
    stopper = threading.Thread(
        target=lambda: _capture_stop(service, queued.run_id, stop_results, stop_errors),
        name="artifact-terminal-stopper",
    )
    stopper.start()
    try:
        assert wait_entered.wait(timeout=2)
        assert not wait_returned.is_set()
        assert stop_results == []
        assert stop_errors == []
    finally:
        _ArtifactTerminalRunner.release.set()
        try:
            assert wait_returned.wait(timeout=5)
        finally:
            stopper.join(timeout=5)
            service.shutdown()

    assert not stopper.is_alive()
    assert stop_results == [False]
    assert stop_errors == []
    assert service.get(queued.run_id).status is RunStatus.COMPLETED
    assert json.loads((queued.run_dir / "status.json").read_text())["status"] == "completed"


def _capture_stop(service, run_id, results, errors):
    try:
        results.append(service.stop(run_id))
    except Exception as exc:
        errors.append(exc)


def test_switch_scene_waits_for_old_run_then_queues_distinct_run(tmp_path):
    _LifecycleRunner.started.clear()
    _LifecycleRunner.calls.clear()
    service = RunService(output_root=tmp_path, runner_factory=_LifecycleRunner)
    active = service.submit(RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0))
    assert _LifecycleRunner.started.wait(timeout=2)

    old, new = service.switch_scene(
        active.run_id,
        RunRequest("2", "fixed_time", duration_seconds=1, warmup_seconds=0),
    )

    assert old.status is RunStatus.INTERRUPTED
    assert old.run_dir != new.run_dir
    assert new.status is RunStatus.QUEUED
    assert service.stop(new.run_id) is True
    service.shutdown()


def test_stopping_queued_run_never_signals_or_starts_active_run(tmp_path):
    _LifecycleRunner.started.clear()
    _LifecycleRunner.calls.clear()
    service = RunService(output_root=tmp_path, runner_factory=_LifecycleRunner)
    active = service.submit(RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0))
    assert _LifecycleRunner.started.wait(timeout=2)
    queued = service.submit(RunRequest("2", "fixed_time", duration_seconds=1, warmup_seconds=0))

    assert service.stop(queued.run_id) is True
    assert service.get(queued.run_id).status is RunStatus.INTERRUPTED
    assert service.get(active.run_id).status is RunStatus.RUNNING
    assert len(_LifecycleRunner.calls) == 1

    assert service.stop(active.run_id) is True
    service.shutdown()


@pytest.mark.parametrize("secondary", ["finalize", "metadata", "seal"])
def test_cancelled_queued_run_never_sticks_stopping_on_evidence_failure(
    tmp_path,
    secondary,
):
    _LifecycleRunner.started.clear()
    _LifecycleRunner.calls.clear()
    service = RunService(output_root=tmp_path, runner_factory=_LifecycleRunner)
    active = service.submit(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )
    assert _LifecycleRunner.started.wait(timeout=2)
    queued = service.submit(
        RunRequest("2", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )
    target = {
        "finalize": "engine.run_service.EvidenceWriter.finalize",
        "metadata": "engine.run_service.RunService._write_terminal_metadata",
        "seal": "engine.run_service.EvidenceWriter.seal",
    }[secondary]

    try:
        with patch(target, side_effect=OSError(f"{secondary} unavailable")):
            assert service.stop(queued.run_id) is True

        assert service.get(queued.run_id).status is RunStatus.INTERRUPTED
        assert service._done[queued.run_id].is_set()
        assert service.stop(queued.run_id) is False
    finally:
        service.stop(active.run_id)
        service.shutdown()


def test_cancelled_queued_run_terminalizes_in_memory_when_status_storage_fails(
    tmp_path,
):
    _LifecycleRunner.started.clear()
    service = RunService(output_root=tmp_path, runner_factory=_LifecycleRunner)
    active = service.submit(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )
    assert _LifecycleRunner.started.wait(timeout=2)
    queued = service.submit(
        RunRequest("2", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )
    original_write_status = RunArtifacts.write_status

    def fail_terminal_status(artifacts, status, reason, **kwargs):
        if status in {"interrupted", "failed"}:
            raise OSError("status storage unavailable")
        return original_write_status(artifacts, status, reason, **kwargs)

    try:
        with patch.object(RunArtifacts, "write_status", new=fail_terminal_status):
            assert service.stop(queued.run_id) is True
        assert service.get(queued.run_id).status is RunStatus.INTERRUPTED
        assert service._done[queued.run_id].is_set()
    finally:
        service.stop(active.run_id)
        service.shutdown()


def test_stop_between_queued_observation_and_start_preserves_interrupted(
    monkeypatch, tmp_path
):
    service = RunService(output_root=tmp_path, runner_factory=_LifecycleRunner)
    execute_observed_queued = threading.Event()
    release_execute = threading.Event()
    original_transition = service._states.transition

    def transition_with_queued_race(run_id, new_status, reason, **kwargs):
        if (
            new_status is RunStatus.STARTING
            and threading.current_thread().name.startswith("ThreadPoolExecutor")
        ):
            execute_observed_queued.set()
            assert release_execute.wait(timeout=5)
        return original_transition(run_id, new_status, reason, **kwargs)

    monkeypatch.setattr(
        service._states,
        "transition",
        transition_with_queued_race,
    )
    queued = service.submit(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )
    assert execute_observed_queued.wait(timeout=2)
    stop_results = []
    stop_errors = []

    def request_stop():
        try:
            stop_results.append(service.stop(queued.run_id))
        except Exception as exc:  # captured to assert public stop behavior
            stop_errors.append(exc)

    stopper = threading.Thread(target=request_stop, name="queued-stopper")
    stopper.start()
    try:
        _wait_for_status(service, queued.run_id, RunStatus.STOPPING)
    finally:
        release_execute.set()
        stopper.join(timeout=5)
        service.shutdown()

    assert not stopper.is_alive()
    assert stop_errors == []
    assert stop_results == [True]
    assert service.get(queued.run_id).status is RunStatus.INTERRUPTED


def test_concurrent_stop_callers_are_serialized_and_idempotent(monkeypatch, tmp_path):
    _ReleaseAfterStopRunner.started.clear()
    _ReleaseAfterStopRunner.stop_observed.clear()
    _ReleaseAfterStopRunner.release.clear()
    service = RunService(output_root=tmp_path, runner_factory=_ReleaseAfterStopRunner)
    queued = service.submit(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )
    assert _ReleaseAfterStopRunner.started.wait(timeout=2)

    original_transition = service._states.transition
    both_attempted_stopping = threading.Barrier(2)

    def transition_with_concurrent_stop_race(run_id, new_status, reason, **kwargs):
        if (
            new_status is RunStatus.STOPPING
            and threading.current_thread().name.startswith("concurrent-stopper-")
        ):
            try:
                both_attempted_stopping.wait(timeout=0.2)
            except threading.BrokenBarrierError:
                pass
        return original_transition(run_id, new_status, reason, **kwargs)

    monkeypatch.setattr(
        service._states,
        "transition",
        transition_with_concurrent_stop_race,
    )
    stop_results = []
    stop_errors = []

    def request_stop():
        try:
            stop_results.append(service.stop(queued.run_id))
        except Exception as exc:  # captured to assert public stop behavior
            stop_errors.append(exc)

    stoppers = [
        threading.Thread(target=request_stop, name=f"concurrent-stopper-{index}")
        for index in range(2)
    ]
    for stopper in stoppers:
        stopper.start()
    try:
        _wait_for_status(service, queued.run_id, RunStatus.STOPPING)
        assert _ReleaseAfterStopRunner.stop_observed.wait(timeout=2)
        assert stop_results == []
        assert stop_errors == []
    finally:
        _ReleaseAfterStopRunner.release.set()
        for stopper in stoppers:
            stopper.join(timeout=5)
        service.shutdown()

    assert all(not stopper.is_alive() for stopper in stoppers)
    assert stop_errors == []
    assert sorted(stop_results) == [False, True]
    assert service.get(queued.run_id).status is RunStatus.INTERRUPTED


def test_switch_scene_waits_when_another_caller_is_already_stopping(
    monkeypatch, tmp_path
):
    _ReleaseAfterStopRunner.started.clear()
    _ReleaseAfterStopRunner.stop_observed.clear()
    _ReleaseAfterStopRunner.release.clear()
    service = RunService(output_root=tmp_path, runner_factory=_ReleaseAfterStopRunner)
    active = service.submit(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )
    assert _ReleaseAfterStopRunner.started.wait(timeout=2)

    stop_results = []
    stopper = threading.Thread(
        target=lambda: stop_results.append(service.stop(active.run_id)),
        name="first-stopper",
    )
    stopper.start()
    assert _ReleaseAfterStopRunner.stop_observed.wait(timeout=2)
    _wait_for_status(service, active.run_id, RunStatus.STOPPING)

    original_stop = service.stop
    original_submit = service.submit
    switch_reached_stop = threading.Event()
    replacement_submitted = threading.Event()

    def observed_stop(run_id):
        if threading.current_thread().name == "scene-switcher":
            switch_reached_stop.set()
        return original_stop(run_id)

    def observed_submit(request):
        if threading.current_thread().name == "scene-switcher":
            replacement_submitted.set()
        return original_submit(request)

    monkeypatch.setattr(service, "stop", observed_stop)
    monkeypatch.setattr(service, "submit", observed_submit)
    switched = []
    switcher = threading.Thread(
        target=lambda: switched.append(
            service.switch_scene(
                active.run_id,
                RunRequest("2", "fixed_time", duration_seconds=1, warmup_seconds=0),
            )
        ),
        name="scene-switcher",
    )
    switcher.start()
    assert switch_reached_stop.wait(timeout=2)
    submitted_before_old_finished = replacement_submitted.wait(timeout=0.2)
    try:
        assert service.get(active.run_id).status is RunStatus.STOPPING
    finally:
        _ReleaseAfterStopRunner.release.set()
        stopper.join(timeout=5)
        switcher.join(timeout=5)
        if switched:
            service.stop(switched[0][1].run_id)
        service.shutdown()

    assert submitted_before_old_finished is False
    assert not stopper.is_alive()
    assert not switcher.is_alive()
    assert stop_results == [True]
    assert switched[0][0].status is RunStatus.INTERRUPTED


class _TimedBridge(MockBridge):
    def __init__(self, step_length=0.4):
        super().__init__(step_length=step_length)


def test_runner_uses_simulation_seconds_and_records_derived_steps(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    bridge = _TimedBridge(step_length=0.4)

    result = SimulationRunner(
        SceneRegistry().get_scene("1"),
        FixedTimeAlgorithm(),
        bridge=bridge,
        artifacts=artifacts,
    ).run(SimulationWindow(1.0, 0.2), threading.Event())

    manifest = json.loads(artifacts.manifest.read_text())
    status = json.loads(artifacts.status.read_text())
    assert result.status is RunStatus.COMPLETED
    assert bridge._current_step == 3
    assert manifest["requested_seconds"] == 1.0
    assert manifest["warmup_seconds"] == 0.2
    assert manifest["derived_steps"] == 3
    assert manifest["step_length"] == 0.4
    assert status["status"] == "completed"


@pytest.mark.parametrize("invocation", ["positional", "keyword"])
def test_integer_runner_calls_return_legacy_list_with_artifacts(tmp_path, invocation):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    runner = SimulationRunner(
        SceneRegistry().get_scene("1"),
        FixedTimeAlgorithm(),
        bridge=MockBridge(),
        artifacts=artifacts,
    )

    result = runner.run(2) if invocation == "positional" else runner.run(steps=2)

    assert isinstance(result, list)
    assert result


def test_formal_simulation_window_returns_run_result_with_artifacts(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    result = SimulationRunner(
        SceneRegistry().get_scene("1"),
        FixedTimeAlgorithm(),
        bridge=MockBridge(),
        artifacts=artifacts,
    ).run(SimulationWindow(2.0, 0.0))

    assert isinstance(result, RunResult)
    assert result.status is RunStatus.COMPLETED


class _DisconnectedBridge(_TimedBridge):
    def step(self):
        return None


class _EarlyBridge(_TimedBridge):
    def is_exhausted(self):
        return self._current_step >= 1


class _FailingBridge(_TimedBridge):
    def get_state(self):
        raise RuntimeError("state failed")


@pytest.mark.parametrize(
    ("bridge", "stop", "expected"),
    [
        (_TimedBridge(), True, RunStatus.INTERRUPTED),
        (_DisconnectedBridge(), False, RunStatus.DISCONNECTED),
        (_EarlyBridge(), False, RunStatus.ENDED_EARLY),
        (_FailingBridge(), False, RunStatus.FAILED),
    ],
)
def test_runner_writes_each_non_completed_terminal_outcome(
    tmp_path, bridge, stop, expected
):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    stop_event = threading.Event()
    if stop:
        stop_event.set()
    runner = SimulationRunner(
        SceneRegistry().get_scene("1"),
        FixedTimeAlgorithm(),
        bridge=bridge,
        artifacts=artifacts,
    )

    if expected is RunStatus.FAILED:
        with pytest.raises(RuntimeError, match="state failed"):
            runner.run(SimulationWindow(1.0, 0.2), stop_event)
    else:
        result = runner.run(SimulationWindow(1.0, 0.2), stop_event)
        assert result.status is expected

    assert json.loads(artifacts.status.read_text(encoding="utf-8"))["status"] == expected.value
    assert json.loads(artifacts.metadata.read_text(encoding="utf-8"))["status"] == expected.value


class _OwnedProcess:
    def __init__(self, pid):
        self.pid = pid
        self.terminated = False
        self.killed = False
        self.waits = 0

    def poll(self):
        return None

    def wait(self, timeout=None):
        self.waits += 1
        if self.waits == 1:
            raise subprocess.TimeoutExpired("sumo", timeout)
        return 0

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class _ConnectionHandle:
    def __init__(self):
        self.close_calls = []

    def close(self, wait=True):
        self.close_calls.append(wait)


def test_bridge_cleanup_targets_only_its_recorded_process(monkeypatch, tmp_path):
    bridge = TraCIBridge(tmp_path / "unused.sumocfg")
    owned = _OwnedProcess(41001)
    unrelated = _OwnedProcess(41002)
    bridge._owned_process = owned
    monkeypatch.setattr(traci, "isLoaded", lambda: False)

    bridge.close()

    assert bridge.process_id == 41001
    assert owned.terminated is True
    assert owned.killed is False
    assert unrelated.terminated is False
    assert unrelated.killed is False


def test_bridge_close_reaps_child_when_connection_close_is_interrupted(tmp_path):
    bridge = TraCIBridge(tmp_path / "unused.sumocfg")
    owned = _OwnedProcess(41009)

    class InterruptingConnection:
        def close(self, wait=True):
            raise KeyboardInterrupt()

    bridge._owned_process = owned
    bridge._connection = InterruptingConnection()
    bridge._connection_label = "owned-label"

    with pytest.raises(KeyboardInterrupt):
        bridge.close()

    assert owned.terminated is True
    assert owned.killed is False
    assert bridge._owned_process is None
    assert bridge._connection is None
    assert bridge._connection_label is None


def test_bridge_start_failure_reaps_process_created_during_connection_setup(
    monkeypatch, tmp_path
):
    bridge_process = _OwnedProcess(41003)
    unrelated = _OwnedProcess(41004)
    config = tmp_path / "unused.sumocfg"
    config.write_text("<configuration />", encoding="utf-8")
    bridge = TraCIBridge(
        config,
        process_factory=lambda *args, **kwargs: bridge_process,
    )
    connection = _ConnectionHandle()
    connections = {}
    labels = []
    global_close_calls = []

    def fail_after_partial_connection(*args, label="default", **kwargs):
        labels.append(label)
        connections[label] = connection
        raise RuntimeError("connect failed")

    def get_connection(label):
        return connections[label]

    monkeypatch.setattr(traci, "getFreeSocketPort", lambda: 41005)
    monkeypatch.setattr(traci, "init", fail_after_partial_connection)
    monkeypatch.setattr(traci, "getConnection", get_connection)
    monkeypatch.setattr(traci, "isLoaded", lambda: False)
    monkeypatch.setattr(
        traci, "close", lambda wait=False: global_close_calls.append(wait)
    )

    with pytest.raises(RuntimeError, match="connect failed"):
        bridge.start()

    assert bridge.process_id == 41003
    assert bridge_process.terminated is True
    assert bridge_process.killed is False
    assert unrelated.terminated is False
    assert unrelated.killed is False
    assert labels[0] != "default"
    assert connection.close_calls == [False]
    assert global_close_calls == []


def test_bridge_start_interrupt_reaps_recorded_process(monkeypatch, tmp_path):
    bridge_process = _OwnedProcess(41005)
    config = tmp_path / "unused.sumocfg"
    config.write_text("<configuration />", encoding="utf-8")
    bridge = TraCIBridge(
        config,
        process_factory=lambda *args, **kwargs: bridge_process,
    )
    connection = _ConnectionHandle()
    connections = {}
    global_close_calls = []

    def interrupt_after_partial_connection(*args, label="default", **kwargs):
        connections[label] = connection
        raise KeyboardInterrupt()

    monkeypatch.setattr(traci, "getFreeSocketPort", lambda: 41006)
    monkeypatch.setattr(traci, "init", interrupt_after_partial_connection)
    monkeypatch.setattr(traci, "getConnection", lambda label: connections[label])
    monkeypatch.setattr(traci, "isLoaded", lambda: False)
    monkeypatch.setattr(
        traci, "close", lambda wait=False: global_close_calls.append(wait)
    )

    with pytest.raises(KeyboardInterrupt):
        bridge.start()

    assert bridge.process_id == 41005
    assert bridge_process.terminated is True
    assert bridge_process.killed is False
    assert connection.close_calls == [False]
    assert global_close_calls == []


def test_bridge_init_race_does_not_close_another_owners_connection(
    monkeypatch, tmp_path
):
    bridge_process = _OwnedProcess(41007)
    other_connection = _ConnectionHandle()
    global_close_calls = []
    labels = []
    connection_loaded = False
    config = tmp_path / "unused.sumocfg"
    config.write_text("<configuration />", encoding="utf-8")
    bridge = TraCIBridge(
        config,
        process_factory=lambda *args, **kwargs: bridge_process,
    )

    def is_loaded():
        return connection_loaded

    def collide_during_init(*args, label="default", **kwargs):
        nonlocal connection_loaded
        labels.append(label)
        connection_loaded = True
        raise RuntimeError("another owner connected")

    def close_global(wait=False):
        global_close_calls.append(wait)
        other_connection.close(wait=wait)

    def no_owned_connection(label):
        raise KeyError(label)

    monkeypatch.setattr(traci, "getFreeSocketPort", lambda: 41008)
    monkeypatch.setattr(traci, "isLoaded", is_loaded)
    monkeypatch.setattr(traci, "init", collide_during_init)
    monkeypatch.setattr(traci, "getConnection", no_owned_connection)
    monkeypatch.setattr(traci, "close", close_global)

    with pytest.raises(RuntimeError, match="another owner connected"):
        bridge.start()

    assert labels[0] != "default"
    assert other_connection.close_calls == []
    assert global_close_calls == []
    assert bridge.process_id == 41007
    assert bridge_process.terminated is True
    assert bridge_process.killed is False


def test_bridge_start_rejects_existing_connection_before_launch(monkeypatch, tmp_path):
    config = tmp_path / "unused.sumocfg"
    config.write_text("<configuration />", encoding="utf-8")
    launches = []
    close_calls = []

    def process_factory(*args, **kwargs):
        launches.append((args, kwargs))
        return _OwnedProcess(41007)

    bridge = TraCIBridge(config, process_factory=process_factory)
    monkeypatch.setattr(traci, "isLoaded", lambda: True)
    monkeypatch.setattr(traci, "close", lambda wait=False: close_calls.append(wait))
    monkeypatch.setattr(
        traci,
        "init",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("connection setup")),
    )

    runner = SimulationRunner(
        SceneRegistry().get_scene("1"),
        FixedTimeAlgorithm(),
        bridge=bridge,
        output_csv=tmp_path / "metrics.csv",
    )

    with pytest.raises(RuntimeError, match="TraCI connection already active"):
        runner.run(1)

    assert launches == []
    assert close_calls == []
