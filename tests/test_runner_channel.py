import csv
import json
from pathlib import Path
import threading

import pytest
from unittest.mock import patch

from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from algorithms.capacity_aware_max_pressure import (
    CapacityAwareConfig,
    CapacityAwareMaxPressureAlgorithm,
)
from core.movements import MovementKey, MovementState, PhaseMovementState
from core.types import ControlAction, JointState, Scene, SceneMeta
from engine.artifacts import RunArtifacts
from engine.edge_channel import EdgeChannel, EdgeMessage
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner


_VALID_NET = Path(__file__).resolve().parents[1] / "data" / "intersection_data" / "1" / "sumo工程" / "demo_1.net.xml"


class CountingAlgorithm(FixedTimeAlgorithm):
    def __init__(self):
        self.steps: list[int] = []
        self.resolved_timing_plan = None

    def step(self, state):
        self.steps.append(state.step)
        return []

    def init(self, scene):
        self.scene = scene


class InvalidActionAlgorithm(FixedTimeAlgorithm):
    def step(self, state):
        return [ControlAction(state.tls_id, "set_phase", "north", "bad phase")]


class StaleActionAlgorithm(CountingAlgorithm):
    def step(self, state):
        return [
            ControlAction(
                state.tls_id,
                "set_phase_duration",
                5.0,
                "stale delayed decision",
                issued_at=0.0,
                expires_at=0.0,
            )
        ]


class RejectedCapacityActionBridge(MockBridge):
    """Use the existing action validator to reject a legal algorithm target."""

    def get_state(self):
        return JointState(
            step=self._current_step,
            timestamp=float(self._current_step) * self.step_length,
            tls_id=self.tls_id,
            current_phase=0,
            current_phase_name="p0",
            elapsed_phase_time=30.0,
            phase_movements=(
                PhaseMovementState(
                    0,
                    "G",
                    (MovementState(
                        MovementKey("in_current", "out_current"),
                        1.0, 0.0, 10.0, 10.0, 0.0, 1.0, 1.0,
                    ),),
                    30.0,
                ),
                PhaseMovementState(
                    2,
                    "G",
                    (MovementState(
                        MovementKey("in_target", "out_target"),
                        5.0, 0.0, 10.0, 10.0, 0.0, 1.0, 1.0,
                    ),),
                    30.0,
                ),
            ),
            legal_phase_transitions=((0, 2),),
        )


class ClearanceCapacityActionBridge(MockBridge):
    def __init__(self):
        super().__init__(tls_id="tls_clearance", phase_count=4)
        self._phases = (
            PhaseMovementState(
                0,
                "Grr",
                (MovementState(
                    MovementKey("in_current", "out_current"),
                    1.0, 0.0, 10.0, 10.0, 0.0, 1.0, 1.0,
                ),),
                30.0,
            ),
            PhaseMovementState(1, "yrr", (), 3.0),
            PhaseMovementState(2, "rrr", (), 1.0),
            PhaseMovementState(
                3,
                "rGG",
                (MovementState(
                    MovementKey("in_target", "out_target"),
                    9.0, 0.0, 10.0, 10.0, 0.0, 1.0, 1.0,
                ),),
                30.0,
            ),
        )

    def get_state(self):
        current_phase = (0, 1, 2, 3)[self._current_step]
        elapsed = (10.0, 3.0, 1.0, 0.0)[self._current_step]
        return JointState(
            step=self._current_step,
            timestamp=(0.0, 3.0, 4.0, 5.0)[self._current_step],
            tls_id=self.tls_id,
            current_phase=current_phase,
            current_phase_name=f"p{current_phase}",
            elapsed_phase_time=elapsed,
            phase_movements=self._phases,
            legal_phase_transitions=((0, 1), (1, 2), (2, 3)),
        )

    def step(self):
        self._current_step += 1
        return (0.0, 3.0, 4.0, 5.0)[self._current_step]


class _SafetyExecutorSpy:
    def __init__(self):
        self.calls = []

    def apply(self, actions, state, bridge):
        self.calls.append((tuple(actions), state, bridge))
        return ()


def make_scene() -> Scene:
    return Scene(SceneMeta(
        intersection_id="1", name="test",
        sumo_net=_VALID_NET, sumo_rou="x.rou.xml", sumo_flow="x.flow.xml",
        sumo_turn="x.turn.xml", sumo_cfg="x.sumocfg", timing_xlsx="x.xlsx",
    ))


def test_delayed_channel_waits_without_stopping_simulation(tmp_path):
    algorithm = CountingAlgorithm()
    artifacts = RunArtifacts.create(tmp_path, "1", algorithm.name, 1.0, 42)
    runner = SimulationRunner(
        make_scene(), algorithm, bridge=MockBridge(), artifacts=artifacts,
        state_channel=EdgeChannel(delay_seconds=0.2),
    )
    runner.run(5)
    assert algorithm.steps == [0, 1, 2]
    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    assert [row["type"] for row in events].count("channel_wait") == 2


def test_runner_consumes_an_edge_message_before_calling_the_algorithm(tmp_path):
    """Removing the envelope adapter would make EdgeChannel reject the bare JointState."""
    algorithm = CountingAlgorithm()
    artifacts = RunArtifacts.create(tmp_path, "1", algorithm.name, 1.0, 42)
    runner = SimulationRunner(
        make_scene(),
        algorithm,
        bridge=MockBridge(),
        artifacts=artifacts,
        state_channel=EdgeChannel(delay_seconds=0.0),
    )

    runner.run(2)

    assert algorithm.steps == [0, 1]


def test_runner_binding_rejects_prebuffered_message_from_another_run(tmp_path):
    """A stale pre-bound envelope must not reach the algorithm after Runner binding."""
    algorithm = CountingAlgorithm()
    artifacts = RunArtifacts.create(tmp_path, "1", algorithm.name, 1.0, 42)
    channel = EdgeChannel(delay_seconds=0.0)
    stale_state = MockBridge().get_state()
    stale_state.step = 99
    channel.send(EdgeMessage(
        run_id="stale-run",
        simulation_time=0.0,
        sent_at=0.0,
        expires_at=60.0,
        payload_version="joint-state.v1",
        payload=stale_state,
    ))
    runner = SimulationRunner(
        make_scene(),
        algorithm,
        bridge=MockBridge(),
        artifacts=artifacts,
        state_channel=channel,
    )

    runner.run(1)

    assert algorithm.steps == [0]
    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    assert [(row["type"], row["detail"]) for row in events if row["type"] == "message_rejected"] == [
        ("message_rejected", "stale_run_id=stale-run"),
    ]


def test_runner_routes_every_action_batch_through_the_safety_executor(tmp_path):
    algorithm = CountingAlgorithm()
    bridge = MockBridge()
    runner = SimulationRunner(
        make_scene(),
        algorithm,
        bridge=bridge,
        output_csv=tmp_path / "metrics.csv",
    )
    safety_executor = _SafetyExecutorSpy()
    runner.safety_executor = safety_executor

    runner.run(1)

    assert len(safety_executor.calls) == 1
    actions, state, called_bridge = safety_executor.calls[0]
    assert actions == ()
    assert state.timestamp == 0.0
    assert called_bridge is bridge


def test_runner_records_rejected_channel_event_at_message_simulation_time(tmp_path):
    """Channel rejection evidence must retain envelope time rather than runner step."""
    bridge = MockBridge(step_length=12.5)
    bridge._current_step = 1
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    runner = SimulationRunner(
        make_scene(),
        FixedTimeAlgorithm(),
        bridge=bridge,
        artifacts=artifacts,
        state_channel=EdgeChannel(delay_seconds=0.0, allowed_directions=["north"]),
    )

    runner.run(1)

    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    rejected = next(row for row in events if row["type"] == "message_rejected")
    assert rejected["detail"] == "disallowed_direction=east"
    assert rejected["simulation_seconds"] == "12.5"


def test_runner_records_stale_action_rejection_and_safe_fallback(tmp_path):
    bridge = MockBridge()
    bridge._current_step = 1
    artifacts = RunArtifacts.create(tmp_path, "1", "stale", 1.0, 42)

    SimulationRunner(
        make_scene(),
        StaleActionAlgorithm(),
        bridge=bridge,
        artifacts=artifacts,
    ).run(1)

    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    rejected = next(row for row in events if row["type"] == "action_rejected")
    assert rejected["reason"] == "stale_action"
    assert "fallback=fixed_timing_unchanged" in rejected["detail"]
    assert bridge._applied_actions == []


def test_half_second_channel_releases_after_exactly_two_ticks(tmp_path):
    """A two-step delay is one simulation second, and delivers states 0, 1, 2."""
    algorithm = CountingAlgorithm()
    artifacts = RunArtifacts.create(tmp_path, "1", algorithm.name, 1.0, 42)
    runner = SimulationRunner(
        make_scene(),
        algorithm,
        bridge=MockBridge(step_length=0.5),
        artifacts=artifacts,
        state_channel=EdgeChannel(delay_seconds=1.0),
    )

    runner.run(5)

    assert algorithm.steps == [0, 1, 2]


def test_delayed_valid_control_action_is_applied_before_message_expiry(tmp_path):
    bridge = MockBridge(step_length=0.1)
    artifacts = RunArtifacts.create(tmp_path, "1", "actuated", 1.0, 42)

    SimulationRunner(
        make_scene(),
        RuleAdaptiveAlgorithm(
            min_green=0.1,
            max_green=60.0,
            queue_threshold=0.0,
        ),
        bridge=bridge,
        artifacts=artifacts,
        state_channel=EdgeChannel(delay_seconds=0.2),
    ).run(5)

    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    assert not any(row["reason"] == "stale_action" for row in events)
    assert any(row["type"] == "action_applied" for row in events)
    assert bridge._applied_actions[0].issued_at == 0.1
    assert bridge._applied_actions[0].expires_at == 60.1


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


def test_capacity_aware_run_metadata_records_the_frozen_prediction_manifest(tmp_path):
    """Dropping algorithm provenance would leave prediction units unauditable in a real run."""
    artifacts = RunArtifacts.create(tmp_path, "1", "capacity_aware_maxpressure", 1.0, 42)
    SimulationRunner(
        make_scene(),
        CapacityAwareMaxPressureAlgorithm(),
        bridge=MockBridge(),
        artifacts=artifacts,
    ).run(1)

    manifest = json.loads(artifacts.metadata.read_text(encoding="utf-8"))["algorithm_manifest"]
    assert manifest["prediction_enabled"] is False
    assert manifest["horizon_seconds"] == 300.0
    assert manifest["prediction_weight"] == 0.15
    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    audit = next(json.loads(row["detail"]) for row in events if row["type"] == "algorithm_audit")
    assert audit["layer"] == "M3"
    assert audit["safety_boundary"] == "safety_executor"
    assert audit["final_decision"]["action"] == "no_action"


def test_runner_audit_correlates_shared_rejected_action_result(tmp_path):
    """The persisted decision must include the validator result from apply_actions()."""
    artifacts = RunArtifacts.create(tmp_path, "1", "capacity_aware_maxpressure", 1.0, 42)
    SimulationRunner(
        make_scene(),
        CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m4()),
        bridge=RejectedCapacityActionBridge(),
        artifacts=artifacts,
    ).run(1)

    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    audit = next(json.loads(row["detail"]) for row in events if row["type"] == "algorithm_audit")
    rejected = next(row for row in events if row["type"] == "action_rejected")
    outcome = audit["final_decision"]["action_results"][0]
    assert rejected["detail"].startswith("type=set_phase value=2")
    assert outcome["action_type"] == "set_phase"
    assert outcome["value"] == 2
    assert outcome["accepted"] is False
    assert outcome["reason_code"] == "clearance_path_unavailable"


def test_runner_audit_keeps_green_request_while_bridge_executes_clearance(tmp_path):
    artifacts = RunArtifacts.create(
        tmp_path, "1", "capacity_aware_maxpressure", 1.0, 42
    )
    bridge = ClearanceCapacityActionBridge()

    SimulationRunner(
        make_scene(),
        CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m3()),
        bridge=bridge,
        artifacts=artifacts,
    ).run(3)

    assert [
        (action.action_type, action.value) for action in bridge._applied_actions
    ] == [
        ("set_phase", 1),
        ("set_phase_duration", 3.0),
        ("set_phase", 2),
        ("set_phase_duration", 1.0),
        ("set_phase", 3),
        ("set_phase_duration", 30.0),
    ]
    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    audits = [
        json.loads(row["detail"])
        for row in events
        if row["type"] == "algorithm_audit"
    ]
    assert [audit["selected_phase"] for audit in audits] == [3, 3, 3]
    assert [
        [
            (result["action_type"], result["value"], result["accepted"])
            for result in audit["final_decision"]["action_results"]
        ]
        for audit in audits
    ] == [
        [("set_phase", 3, True), ("set_phase_duration", 30.0, True)],
        [("set_phase", 3, True), ("set_phase_duration", 30.0, True)],
        [("set_phase", 3, True), ("set_phase_duration", 30.0, True)],
    ]


def test_runner_uses_capacity_algorithm_non_default_minimum_green(tmp_path):
    artifacts = RunArtifacts.create(
        tmp_path,
        "1",
        "capacity_aware_maxpressure",
        1.0,
        42,
    )
    bridge = ClearanceCapacityActionBridge()
    config = CapacityAwareConfig(True, True, False, 12.0, 30.0, 0.9)

    SimulationRunner(
        make_scene(),
        CapacityAwareMaxPressureAlgorithm(config),
        bridge=bridge,
        artifacts=artifacts,
    ).run(1)

    assert bridge._applied_actions == []
    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    assert [
        row["reason"]
        for row in events
        if row["type"] == "action_rejected"
    ] == ["minimum_green_violation", "phase_change_rejected"]


class _StartRecordingBridge(MockBridge):
    def __init__(self):
        super().__init__()
        self.start_calls = 0

    def start(self):
        self.start_calls += 1
        super().start()


def test_invalid_fixed_plan_fails_before_starting_the_bridge(tmp_path):
    invalid_net = tmp_path / "invalid.net.xml"
    invalid_net.write_text("<net/>", encoding="utf-8")
    scene = Scene(
        SceneMeta(
            intersection_id="invalid",
            name="invalid",
            sumo_net=invalid_net,
            sumo_rou=tmp_path / "routes.rou.xml",
            sumo_flow=tmp_path / "flow.xml",
            sumo_turn=tmp_path / "turn.xml",
            sumo_cfg=tmp_path / "run.sumocfg",
            timing_xlsx=tmp_path / "timing.xlsx",
        )
    )
    bridge = _StartRecordingBridge()
    artifacts = RunArtifacts.create(tmp_path, "invalid", "fixed_time", 1.0, 42)

    with pytest.raises(ValueError, match="timing plan"):
        SimulationRunner(scene, FixedTimeAlgorithm(), bridge=bridge, artifacts=artifacts).run(1)

    assert bridge.start_calls == 0


def test_capacity_aware_invalid_lane_capacity_fails_before_starting_bridge(tmp_path):
    """Capacity-aware formal validation must name bad lanes before TraCI starts."""
    net = tmp_path / "invalid-capacity.net.xml"
    net.write_text(
        "<net><edge id='in'><lane id='in_0' length='0'/></edge>"
        "<edge id='out'><lane id='out_0' length='20'/></edge>"
        "<tlLogic id='tls' type='static' programID='0' offset='0'>"
        "<phase duration='30' state='G'/></tlLogic>"
        "<connection from='in' to='out' fromLane='0' toLane='0' tl='tls' linkIndex='0'/>"
        "</net>",
        encoding="utf-8",
    )
    scene = Scene(SceneMeta(
        intersection_id="invalid", name="invalid", sumo_net=net,
        sumo_rou=tmp_path / "routes.rou.xml", sumo_flow=tmp_path / "flow.xml",
        sumo_turn=tmp_path / "turn.xml", sumo_cfg=tmp_path / "run.sumocfg",
        timing_xlsx=tmp_path / "timing.xlsx",
    ))
    bridge = _StartRecordingBridge()
    artifacts = RunArtifacts.create(tmp_path, "invalid", "capacity_aware_maxpressure", 1.0, 42)

    with pytest.raises(ValueError, match="in_0"):
        SimulationRunner(
            scene, CapacityAwareMaxPressureAlgorithm(), bridge=bridge, artifacts=artifacts
        ).run(1)

    assert bridge.start_calls == 0


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
