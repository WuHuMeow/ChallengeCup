"""TraCI 断线韧性测试（IB W3）：FatalTraCIError 优雅退出与自动重连。"""
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import ControlAction, Scene, SceneMeta
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner
from engine.safety_executor import SafetyExecutor


_VALID_NET = Path(__file__).resolve().parents[1] / "data" / "intersection_data" / "1" / "sumo工程" / "demo_1.net.xml"
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
    events = []
    bridge = TraCIBridge(
        sumo_cfg=Path("demo_1.sumocfg"),
        max_restarts=1,
        event_callback=lambda event_type, detail: events.append(
            (event_type, detail)
        ),
    )
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
        assert [event_type for event_type, _ in events] == [
            "reconnect_started",
            "reconnect_succeeded",
        ]
        assert mock_start.call_count == 1  # 触发了一次重连


def test_start_clears_discovery_state_before_repopulating(tmp_path):
    bridge = _bridge()
    bridge.sumo_cfg = tmp_path / "demo_1.sumocfg"
    bridge.sumo_cfg.touch()
    bridge.tls_id = "stale_tls"
    bridge._controlled_lanes = ["stale_lane"]
    bridge._inbound_lanes = ["stale_inbound"]

    def load_mapping(current_bridge):
        assert current_bridge.tls_id == "new_tls"
        assert current_bridge._controlled_lanes == ["new_lane"]
        assert current_bridge._inbound_lanes is None
        current_bridge._inbound_lanes = ["new_inbound"]

    program = SimpleNamespace(
        programID="0",
        phases=(SimpleNamespace(state="G", duration=30.0),),
    )

    with (
        patch.object(traci, "start"),
        patch.object(
            traci.trafficlight, "getIDList", return_value=["new_tls"]
        ),
        patch.object(
            traci.trafficlight, "getControlledLanes", return_value=["new_lane"]
        ),
        patch.object(
            traci.trafficlight,
            "getControlledLinks",
            return_value=((('new_lane', 'out_lane', ':via'),),),
        ),
        patch.object(
            traci.trafficlight, "getAllProgramLogics", return_value=[program]
        ),
        patch.object(traci.trafficlight, "getProgram", return_value="0"),
        patch.object(
            TraCIBridge,
            "_load_edge_mapping",
            autospec=True,
            side_effect=load_mapping,
        ),
    ):
        bridge.start()

    assert bridge.tls_id == "new_tls"
    assert bridge._controlled_lanes == ["new_lane"]
    assert bridge._inbound_lanes == ["new_inbound"]


def test_start_defers_variant_signal_program_to_the_safety_boundary(tmp_path):
    config = tmp_path / "demo_1.sumocfg"
    config.touch()
    signal = tmp_path / "signal_program.add.xml"
    signal.write_text(
        "<additional><tlLogic id='new_tls' programID='variant_x1.1' "
        "type='static' offset='0'><phase duration='10' state='G'/></tlLogic>"
        "</additional>",
        encoding="utf-8",
    )
    bridge = TraCIBridge(config, additional_files=[signal])
    program = SimpleNamespace(
        programID="variant_x1.1",
        phases=(SimpleNamespace(state="G", duration=10.0),),
    )

    with (
        patch.object(traci, "start"),
        patch.object(traci.trafficlight, "getIDList", return_value=["new_tls"]),
        patch.object(
            traci.trafficlight, "getControlledLanes", return_value=["new_lane"]
        ),
        patch.object(
            traci.trafficlight,
            "getControlledLinks",
            return_value=((('new_lane', 'out_lane', ':via'),),),
        ),
        patch.object(
            traci.trafficlight, "getAllProgramLogics", return_value=[program]
        ),
        patch.object(
            traci.trafficlight, "getProgram", return_value="variant_x1.1"
        ),
        patch.object(traci.trafficlight, "setProgram") as set_program,
        patch.object(TraCIBridge, "_load_edge_mapping"),
    ):
        bridge.start()

    set_program.assert_not_called()
    actions = bridge.take_startup_actions()
    assert len(actions) == 1
    assert actions[0].tls_id == "new_tls"
    assert actions[0].action_type == "set_program"
    assert actions[0].value == {
        "program_id": "variant_x1.1",
        "phases": [{"duration": "10", "state": "G"}],
    }
    assert actions[0].reason == "install validated variant signal program"
    assert bridge.take_startup_actions() == ()


def test_start_defers_variant_program_for_every_discovered_tls(tmp_path):
    config = tmp_path / "demo_1.sumocfg"
    config.touch()
    signal = tmp_path / "signal_program.add.xml"
    signal.write_text(
        "<additional>"
        "<tlLogic id='tls_main' programID='variant_main' type='static' offset='0'>"
        "<phase duration='10' state='G'/></tlLogic>"
        "<tlLogic id='tls_side' programID='variant_side' type='static' offset='0'>"
        "<phase duration='10' state='G'/></tlLogic>"
        "<tlLogic id='missing_tls' programID='variant_missing' type='static' offset='0'>"
        "<phase duration='10' state='G'/></tlLogic>"
        "</additional>",
        encoding="utf-8",
    )
    bridge = TraCIBridge(config, additional_files=[signal])
    program = SimpleNamespace(
        programID="0",
        phases=(SimpleNamespace(state="G", duration=10.0),),
    )

    with (
        patch.object(traci, "start"),
        patch.object(
            traci.trafficlight,
            "getIDList",
            return_value=["tls_main", "tls_side"],
        ),
        patch.object(
            traci.trafficlight,
            "getControlledLanes",
            return_value=["main_lane"],
        ),
        patch.object(
            traci.trafficlight,
            "getControlledLinks",
            return_value=((('main_lane', 'out_lane', ':via'),),),
        ),
        patch.object(
            traci.trafficlight,
            "getAllProgramLogics",
            return_value=[program],
        ),
        patch.object(traci.trafficlight, "getProgram", return_value="0"),
        patch.object(traci.trafficlight, "setProgram") as set_program,
        patch.object(TraCIBridge, "_load_edge_mapping"),
    ):
        bridge.start()
        first_actions = bridge.take_startup_actions()
        bridge.start()
        reconnect_actions = bridge.take_startup_actions()

    expected = [
        ("tls_main", "variant_main"),
        ("tls_side", "variant_side"),
    ]
    for actions in (first_actions, reconnect_actions):
        assert [
            (action.tls_id, action.value["program_id"])
            for action in actions
        ] == expected
    set_program.assert_not_called()


def test_secondary_variant_program_uses_its_startup_state_through_safety():
    bridge = _bridge()
    bridge.tls_id = "tls_main"
    bridge._tls_ids = ("tls_main", "tls_side")
    primary_builder = object()
    bridge._movement_state_builder = primary_builder
    old_program = SimpleNamespace(
        programID="0",
        phases=(SimpleNamespace(state="rr", duration=1.0),),
    )
    programs = {
        "tls_main": [old_program],
        "tls_side": [old_program],
    }
    active_programs = {"tls_main": "0", "tls_side": "0"}

    def install_logic(tls_id, logic):
        programs[tls_id] = [logic]

    def activate_program(tls_id, program_id):
        active_programs[tls_id] = program_id

    action = ControlAction.for_simulation_time(
        "tls_side",
        "set_program",
        {
            "program_id": "variant_side",
            "phases": [
                {"duration": 30.0, "state": "Gr"},
                {"duration": 3.0, "state": "yr"},
                {"duration": 1.0, "state": "rr"},
                {"duration": 30.0, "state": "rG"},
                {"duration": 3.0, "state": "ry"},
                {"duration": 1.0, "state": "rr"},
            ],
        },
        "install validated variant signal program",
        0.0,
    )

    with (
        patch.object(traci.simulation, "getTime", return_value=0.0),
        patch.object(traci.trafficlight, "getPhase", return_value=0),
        patch.object(traci.trafficlight, "getSpentDuration", return_value=0.0),
        patch.object(
            traci.trafficlight,
            "getAllProgramLogics",
            side_effect=lambda tls_id: programs[tls_id],
        ),
        patch.object(
            traci.trafficlight,
            "getProgram",
            side_effect=lambda tls_id: active_programs[tls_id],
        ),
        patch.object(
            traci.trafficlight,
            "getControlledLinks",
            return_value=(
                (("in_0", "out_0", ":via_0"),),
                (("in_1", "out_1", ":via_1"),),
            ),
        ),
        patch.object(
            traci.trafficlight,
            "setProgramLogic",
            side_effect=install_logic,
        ),
        patch.object(
            traci.trafficlight,
            "setProgram",
            side_effect=activate_program,
        ) as set_program,
    ):
        state = bridge.get_startup_state("tls_side")
        result = SafetyExecutor().apply([action], state, bridge)[0]

    assert state.tls_id == "tls_side"
    assert result.accepted is True
    set_program.assert_called_once_with("tls_side", "variant_side")
    assert bridge.tls_id == "tls_main"
    assert bridge._movement_state_builder is primary_builder


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
        sumo_net=_VALID_NET, sumo_rou="x.rou.xml", sumo_flow="x.flow.xml",
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
