import csv
import json

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
    assert any(row["type"] == "invalid_action" for row in events)
    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"


class _CloseFailBridge(MockBridge):
    def close(self):
        raise RuntimeError("close failed")


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
