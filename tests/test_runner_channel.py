import csv
import json
import threading

import pytest
from unittest.mock import patch

from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import ControlAction, Scene, SceneMeta
from engine.artifacts import RunArtifacts
from engine.edge_channel import EdgeChannel
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner


class CountingAlgorithm(FixedTimeAlgorithm):
    def __init__(self):
        self.steps: list[int] = []

    def step(self, state):
        self.steps.append(state.step)
        return []

    def init(self, scene):
        self.scene = scene


class InvalidActionAlgorithm(FixedTimeAlgorithm):
    def step(self, state):
        return [ControlAction(state.tls_id, "set_phase", "north", "bad phase")]


def make_scene() -> Scene:
    return Scene(SceneMeta(
        intersection_id="1", name="test",
        sumo_net="x.net.xml", sumo_rou="x.rou.xml", sumo_flow="x.flow.xml",
        sumo_turn="x.turn.xml", sumo_cfg="x.sumocfg", timing_xlsx="x.xlsx",
    ))


def test_delayed_channel_waits_without_stopping_simulation(tmp_path):
    algorithm = CountingAlgorithm()
    artifacts = RunArtifacts.create(tmp_path, "1", algorithm.name, 1.0, 42)
    runner = SimulationRunner(
        make_scene(), algorithm, bridge=MockBridge(), artifacts=artifacts,
        state_channel=EdgeChannel(delay_steps=2),
    )
    runner.run(5)
    assert algorithm.steps == [0, 1, 2]
    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    assert [row["type"] for row in events].count("channel_wait") == 2


def test_successful_run_writes_completed_metadata(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    SimulationRunner(
        make_scene(), FixedTimeAlgorithm(), bridge=MockBridge(), artifacts=artifacts,
    ).run(3)
    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert "events.csv" in payload["generated_files"]
    assert payload["started_at"].endswith("+00:00")
    assert payload["ended_at"].endswith("+00:00")
    assert payload["sumo_version"]


def test_invalid_action_is_logged_and_does_not_stop_run(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "invalid", 1.0, 42)
    SimulationRunner(
        make_scene(), InvalidActionAlgorithm(), bridge=MockBridge(), artifacts=artifacts,
    ).run(2)
    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    assert [row["type"] for row in events].count("action_rejected") == 2
    assert not any(row["type"] == "action_applied" for row in events)
    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"


def test_stop_event_writes_stopped_terminal_state(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    stop_event = threading.Event()
    stop_event.set()

    SimulationRunner(
        make_scene(),
        FixedTimeAlgorithm(),
        bridge=MockBridge(),
        artifacts=artifacts,
    ).run(10, stop_event=stop_event)

    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    assert payload["status"] == "stopped"
    assert [row["detail"] for row in events if row["type"] == "terminal"] == [
        "stopped"
    ]


class _EarlyEndBridge(MockBridge):
    def is_exhausted(self):
        return self._current_step >= 1


class _ConfiguredEndBridge(_EarlyEndBridge):
    configured_end_time = 0.1


class _ExhaustedBeforeConfiguredEndBridge(_EarlyEndBridge):
    configured_end_time = 0.3


def test_reaching_configured_sumo_end_is_completed(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)

    SimulationRunner(
        make_scene(),
        FixedTimeAlgorithm(),
        bridge=_ConfiguredEndBridge(),
        artifacts=artifacts,
    ).run(10)

    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["reason"] == ""


def test_exhausted_simulation_with_configured_end_advances_to_horizon(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    bridge = _ExhaustedBeforeConfiguredEndBridge()

    SimulationRunner(
        make_scene(),
        FixedTimeAlgorithm(),
        bridge=bridge,
        artifacts=artifacts,
    ).run(10)

    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert bridge._current_step == 3


def test_ordinary_early_end_is_distinct_from_disconnect(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)

    SimulationRunner(
        make_scene(),
        FixedTimeAlgorithm(),
        bridge=_EarlyEndBridge(),
        artifacts=artifacts,
    ).run(10)

    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "ended_early"
    assert "exhausted" in payload["reason"]


class _ReconnectBridge(MockBridge):
    def __init__(self):
        super().__init__()
        self.event_callback = lambda event_type, detail: None
        self._emitted = False

    def step(self):
        if not self._emitted:
            self.event_callback("reconnect_started", "attempt=1/1")
            self.event_callback("reconnect_succeeded", "attempt=1")
            self._emitted = True
        return super().step()


def test_reconnect_events_are_written_to_events_csv(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)

    SimulationRunner(
        make_scene(),
        FixedTimeAlgorithm(),
        bridge=_ReconnectBridge(),
        artifacts=artifacts,
    ).run(2)

    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    event_types = [row["type"] for row in events]
    assert event_types.count("reconnect_started") == 1
    assert event_types.count("reconnect_succeeded") == 1


class _CloseFailBridge(MockBridge):
    def close(self):
        raise RuntimeError("close failed")


class _OutputBridge(MockBridge):
    def __init__(self, artifacts):
        super().__init__()
        self.artifacts = artifacts

    def close(self):
        self.artifacts.tripinfo.write_text(
            '<tripinfos><tripinfo id="v0" duration="10" timeLoss="2" '
            'waitingCount="1"><emissions fuel_abs="0.5"/></tripinfo>'
            "</tripinfos>",
            encoding="utf-8",
        )
        self.artifacts.stats.write_text("<summary/>", encoding="utf-8")
        self.artifacts.trajectory.write_text("<fcd-export/>", encoding="utf-8")
        self.artifacts.collisions.write_text("<collisions/>", encoding="utf-8")
        super().close()


def test_completed_run_writes_exact_summary_after_bridge_close(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    runner = SimulationRunner(
        make_scene(),
        FixedTimeAlgorithm(),
        bridge=_OutputBridge(artifacts),
        artifacts=artifacts,
    )

    runner.run(1)

    payload = json.loads(artifacts.summary.read_text(encoding="utf-8"))
    assert payload["metrics"]["avg_travel_time"] == 10
    metadata = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert "summary.json" in metadata["generated_files"]


def test_close_failure_marks_metadata_failed(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    runner = SimulationRunner(
        make_scene(), FixedTimeAlgorithm(), bridge=_CloseFailBridge(), artifacts=artifacts
    )

    with pytest.raises(RuntimeError, match="close failed"):
        runner.run(1)

    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["reason"] == "close failed"


def test_cleanup_failure_still_closes_bridge_and_writes_metadata(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    bridge = MockBridge()
    runner = SimulationRunner(
        make_scene(), FixedTimeAlgorithm(), bridge=bridge, artifacts=artifacts
    )
    with patch("engine.runner.MetricsCollector.save", side_effect=RuntimeError("save failed")):
        with pytest.raises(RuntimeError, match="save failed"):
            runner.run(1)

    assert bridge._started is False
    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["reason"] == "save failed"


def test_metadata_uses_traci_server_version(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    with patch(
        "engine.runner.traci.getVersion", return_value=("SUMO 1.27.1", 27)
    ) as get_version:
        SimulationRunner(
            make_scene(), FixedTimeAlgorithm(), bridge=MockBridge(), artifacts=artifacts
        ).run(1)

    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["sumo_version"] == "1.27.1"
    get_version.assert_called_once()
