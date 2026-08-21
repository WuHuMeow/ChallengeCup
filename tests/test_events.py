"""events.csv 事件日志测试（IB W3 Day 2）。"""
import csv

import pytest
from pathlib import Path

from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import (
    ControlAction,
    JointState,
    SafetyEvent,
    SafetyVehicleState,
    Scene,
    SceneMeta,
)
from engine.events import EventLogger
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner


_VALID_NET = Path(__file__).resolve().parents[1] / "data" / "intersection_data" / "1" / "sumo工程" / "demo_1.net.xml"


def _scene() -> Scene:
    meta = SceneMeta(
        intersection_id="1", name="t",
        sumo_net=_VALID_NET, sumo_rou="x.rou.xml", sumo_flow="x.flow.xml",
        sumo_turn="x.turn.xml", sumo_cfg="x.sumocfg", timing_xlsx="x.xlsx",
    )
    return Scene(meta=meta)


class _ActionAlgo(FixedTimeAlgorithm):
    @property
    def name(self) -> str:
        return "action_algo"

    def step(self, state):
        return [ControlAction(tls_id=state.tls_id, action_type="set_phase",
                              value=1, reason="测试动作")]


def test_events_csv_lifecycle_and_actions(tmp_path):
    events = tmp_path / "events.csv"
    runner = SimulationRunner(
        _scene(), _ActionAlgo(), output_csv=tmp_path / "snap.csv",
        bridge=MockBridge(), events_csv=events,
    )
    runner.run(5)
    rows = list(csv.DictReader(open(events, encoding="utf-8")))
    types = [r["type"] for r in rows]
    assert types[0] == "run_start" and types[-1] == "terminal"
    assert types.count("terminal") == 1
    assert "action_applied" in types
    applied = next(r for r in rows if r["type"] == "action_applied")
    detail = applied["detail"]
    assert rows[-1]["detail"] == "completed"
    assert "测试动作" in detail
    assert applied["simulation_seconds"] == "0.0"
    assert applied["accepted"] == "true"
    assert applied["action_type"] == "set_phase"
    assert applied["action_value"] == "1"


@pytest.mark.parametrize(
    ("internal_name", "contract_name"),
    [
        ("fixed_time", "fixed_time"),
        ("rule_adaptive", "actuated"),
        ("ca_maxpressure", "capacity_aware_maxpressure"),
        ("capacity_aware_maxpressure", "capacity_aware_maxpressure"),
    ],
)
def test_events_csv_algorithm_uses_external_contract_name(
    tmp_path, internal_name, contract_name
):
    events = tmp_path / f"{internal_name}.csv"
    logger = EventLogger(
        events,
        run_id="run-1",
        intersection_id="1",
        algorithm=internal_name,
    )
    logger.log(0, "run_start", "started", status="running")
    logger.save()

    rows = list(csv.DictReader(events.open(encoding="utf-8")))
    assert rows[0]["algorithm"] == contract_name


def test_simulation_runner_wires_canonical_algorithm_context(tmp_path):
    events = tmp_path / "events.csv"
    runner = SimulationRunner(
        _scene(),
        FixedTimeAlgorithm(),
        output_csv=tmp_path / "snap.csv",
        bridge=MockBridge(),
        events_csv=events,
    )

    runner.run(1)

    rows = list(csv.DictReader(events.open(encoding="utf-8")))
    assert {row["algorithm"] for row in rows} == {"fixed_time"}
    assert {row["intersection_id"] for row in rows} == {"1"}


def test_event_logger_writes_machine_readable_safety_fields(tmp_path):
    events = tmp_path / "events.csv"
    logger = EventLogger(events, run_id="run-1", intersection_id="1", algorithm="fixed_time")
    logger.log_safety(
        SafetyEvent(
            run_id="run-1",
            step=12,
            simulation_seconds=1.25,
            event_type="collision",
            entity_ids=("veh-a", "veh-b"),
            source="sumo_collision",
            confidence=1.0,
        )
    )
    logger.save()

    row = next(csv.DictReader(events.open(encoding="utf-8")))
    assert row["type"] == "collision"
    assert row["step"] == "12"
    assert row["simulation_seconds"] == "1.25"
    assert row["entity_ids"] == '["veh-a", "veh-b"]'
    assert row["source"] == "sumo_collision"
    assert row["confidence"] == "1.0"


def test_event_logger_rejects_safety_event_from_another_run(tmp_path):
    logger = EventLogger(tmp_path / "events.csv", run_id="run-1")
    event = SafetyEvent(
        run_id="run-2",
        step=10,
        simulation_seconds=1.0,
        event_type="teleport",
        entity_ids=("veh-a",),
        source="sumo_teleport",
        confidence=1.0,
    )

    with pytest.raises(ValueError, match="run_id"):
        logger.log_safety(event)


class _SafetyBridge(MockBridge):
    def get_state(self) -> JointState:
        speed = 15.0 if self._current_step == 0 else 8.0
        return JointState(
            step=self._current_step,
            timestamp=float(self._current_step),
            tls_id=self.tls_id,
            current_phase=0,
            current_phase_name="phase_0",
            elapsed_phase_time=float(self._current_step),
            safety_vehicles=(
                SafetyVehicleState("veh-a", "north", speed, (0.0, 0.0)),
            ),
            collision_vehicle_ids=("veh-a",) if self._current_step == 0 else (),
        )


class _FinalStepCollisionBridge(_SafetyBridge):
    def get_state(self) -> JointState:
        state = super().get_state()
        state.collision_vehicle_ids = (
            ("veh-final",) if self._current_step == 1 else ()
        )
        return state


def test_simulation_runner_records_safety_observations(tmp_path):
    events = tmp_path / "events.csv"
    runner = SimulationRunner(
        _scene(),
        FixedTimeAlgorithm(),
        output_csv=tmp_path / "metrics.csv",
        bridge=_SafetyBridge(),
        events_csv=events,
    )

    runner.run(2)

    rows = list(csv.DictReader(events.open(encoding="utf-8")))
    assert [row["type"] for row in rows].count("collision") == 1
    assert [row["type"] for row in rows].count("harsh_braking") == 1
    assert next(row for row in rows if row["type"] == "harsh_braking")["source"] == (
        "derived_speed_delta"
    )


def test_simulation_runner_flushes_safety_from_the_final_step(tmp_path):
    events = tmp_path / "events.csv"
    runner = SimulationRunner(
        _scene(),
        FixedTimeAlgorithm(),
        output_csv=tmp_path / "metrics.csv",
        bridge=_FinalStepCollisionBridge(),
        events_csv=events,
    )

    runner.run(1)

    rows = list(csv.DictReader(events.open(encoding="utf-8")))
    collision = next(row for row in rows if row["type"] == "collision")
    assert collision["simulation_seconds"] == "1.0"
    assert collision["entity_ids"] == '["veh-final"]'
