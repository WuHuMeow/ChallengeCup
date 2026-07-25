"""events.csv 事件日志测试（IB W3 Day 2）。"""
import csv

from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import ControlAction, Scene, SceneMeta
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner


def _scene() -> Scene:
    meta = SceneMeta(
        intersection_id="1", name="t",
        sumo_net="x.net.xml", sumo_rou="x.rou.xml", sumo_flow="x.flow.xml",
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
    assert types[0] == "run_start" and types[-1] == "run_end"
    assert "set_phase" in types
    detail = next(r["detail"] for r in rows if r["type"] == "set_phase")
    assert "测试动作" in detail
