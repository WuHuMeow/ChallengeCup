"""TraCI 断线韧性测试（IB W3）：FatalTraCIError 优雅退出与自动重连。"""
import logging
from pathlib import Path
from unittest.mock import patch

from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import Scene, SceneMeta
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner
from engine.traci_bridge import TraCIBridge, traci


def _bridge(max_restarts: int = 0) -> TraCIBridge:
    return TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"), max_restarts=max_restarts)


def test_step_returns_none_on_fatal_error(caplog):
    bridge = _bridge()
    with patch.object(traci, "simulationStep",
                      side_effect=traci.exceptions.FatalTraCIError("connection closed")), \
         patch.object(traci, "isLoaded", return_value=False):
        import logging
        with caplog.at_level(logging.ERROR):
            assert bridge.step() is None
    assert any("closing gracefully" in r.message for r in caplog.records)


def test_step_restarts_when_allowed():
    bridge = _bridge(max_restarts=1)
    calls = {"n": 0}

    def flaky_step():
        calls["n"] += 1
        if calls["n"] == 1:
            raise traci.exceptions.FatalTraCIError("boom")

    with patch.object(traci, "simulationStep", side_effect=flaky_step), \
         patch.object(traci, "isLoaded", return_value=False), \
         patch.object(TraCIBridge, "start", autospec=True) as mock_start, \
         patch.object(traci.simulation, "getTime", return_value=0.0):
        assert bridge.step() == 0.0
        assert mock_start.call_count == 1  # 触发了一次重连


def test_close_idempotent():
    bridge = _bridge()
    with patch.object(traci, "isLoaded", side_effect=[True, False]), \
         patch.object(traci, "close") as mock_close:
        bridge.close()
        bridge.close()  # 第二次应为 no-op
        assert mock_close.call_count == 1


class _FatalStateBridge(MockBridge):
    """get_state 抛 FatalTraCIError 的桥（模拟 SUMO 进程被杀）。"""

    def get_state(self):
        raise traci.exceptions.FatalTraCIError("connection closed")


def _scene() -> Scene:
    meta = SceneMeta(
        intersection_id="1", name="t",
        sumo_net="x.net.xml", sumo_rou="x.rou.xml", sumo_flow="x.flow.xml",
        sumo_turn="x.turn.xml", sumo_cfg="x.sumocfg", timing_xlsx="x.xlsx",
    )
    return Scene(meta=meta)


def test_runner_exits_cleanly_on_fatal_error(tmp_path, caplog):
    """get_state 抛 FatalTraCIError 时 runner 不抛异常、正常收尾。"""
    runner = SimulationRunner(
        _scene(), FixedTimeAlgorithm(),
        output_csv=tmp_path / "snap.csv",
        bridge=_FatalStateBridge(),
    )
    with caplog.at_level(logging.ERROR):
        history = runner.run(10)  # 不应抛出未捕获异常
    assert history == []  # 第一步即断开，无快照
    assert any("closing gracefully" in r.message for r in caplog.records)
