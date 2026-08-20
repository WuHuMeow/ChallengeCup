"""simulation_log.csv 每步日志测试（IB W2 Day 5）。"""
import csv
from pathlib import Path

from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import Scene, SceneMeta
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


def test_step_log_written_every_step(tmp_path):
    log = tmp_path / "simulation_log.csv"
    runner = SimulationRunner(
        _scene(), FixedTimeAlgorithm(),
        output_csv=tmp_path / "snap.csv",
        bridge=MockBridge(),
        step_log_csv=log,
    )
    runner.run(10)
    rows = list(csv.DictReader(open(log, encoding="utf-8")))
    assert len(rows) == 10  # 每步一行
    assert "queue_north" in rows[0] and "pressure_north" in rows[0]
    assert float(rows[0]["pressure_north"]) >= 0.0
