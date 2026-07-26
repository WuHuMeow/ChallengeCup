from pathlib import Path
from unittest.mock import patch

from core.types import ControlAction
from engine.artifacts import RunArtifacts
from engine.mock_bridge import MockBridge
from engine.traci_bridge import TraCIBridge, traci


def test_build_cmd_redirects_all_sumo_outputs(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    bridge = TraCIBridge(Path("demo_1.sumocfg"), artifacts=artifacts, seed=42)
    cmd = bridge._build_cmd()
    assert cmd[cmd.index("--tripinfo-output") + 1] == (
        artifacts.tripinfo.resolve().as_posix()
    )
    assert cmd[cmd.index("--summary-output") + 1] == (
        artifacts.stats.resolve().as_posix()
    )
    assert cmd[cmd.index("--fcd-output") + 1] == (
        artifacts.trajectory.resolve().as_posix()
    )


def test_build_cmd_redirects_configured_queue_output(tmp_path):
    config = tmp_path / "demo_11.sumocfg"
    config.write_text(
        '<configuration><output><queue-output value="queues.xml"/>'
        "</output></configuration>",
        encoding="utf-8",
    )
    artifacts = RunArtifacts.create(tmp_path, "11", "actuated", 1.5, 42)

    cmd = TraCIBridge(config, artifacts=artifacts)._build_cmd()

    assert cmd[cmd.index("--queue-output") + 1] == (
        artifacts.queues.resolve().as_posix()
    )


def test_invalid_phase_returns_rejection_without_calling_traci():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    with patch.object(traci.trafficlight, "setPhase") as set_phase:
        results = bridge.apply_actions([
            ControlAction("tls", "set_phase", "north", "invalid phase")
        ])
    assert [result.accepted for result in results] == [False]
    assert [result.detail for result in results] == [
        "set_phase value must be an integer: 'north'"
    ]
    set_phase.assert_not_called()


def test_invalid_actions_return_explicit_rejections_without_side_effects():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    actions = [
        ControlAction("other", "set_phase", 1),
        ControlAction("tls", "set_phase_duration", "bad"),
        ControlAction("tls", "set_phase_duration", 0),
        ControlAction("tls", "set_program", "  "),
        ControlAction("tls", "unknown", 1),
    ]
    with (
        patch.object(traci.trafficlight, "setPhase") as set_phase,
        patch.object(traci.trafficlight, "setPhaseDuration") as set_duration,
        patch.object(traci.trafficlight, "setProgram") as set_program,
    ):
        results = bridge.apply_actions(actions)
    assert [result.accepted for result in results] == [False] * 5
    assert [result.detail for result in results] == [
        "unknown tls_id: 'other'",
        "set_phase_duration value must be numeric: 'bad'",
        "set_phase_duration value must be positive: 0.0",
        "set_program value must be non-empty",
        "unknown action_type: 'unknown'",
    ]
    set_phase.assert_not_called()
    set_duration.assert_not_called()
    set_program.assert_not_called()


def test_valid_actions_are_applied_and_not_rejected():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    actions = [
        ControlAction("tls", "set_phase", 2),
        ControlAction("tls", "set_phase_duration", "3.5"),
        ControlAction("tls", "set_program", "program_1"),
    ]
    with (
        patch.object(traci.trafficlight, "setPhase") as set_phase,
        patch.object(traci.trafficlight, "setPhaseDuration") as set_duration,
        patch.object(traci.trafficlight, "setProgram") as set_program,
    ):
        results = bridge.apply_actions(actions)
    assert [result.accepted for result in results] == [True, True, True]
    assert [result.action for result in results] == actions
    set_phase.assert_called_once_with("tls", 2)
    set_duration.assert_called_once_with("tls", 3.5)
    set_program.assert_called_once_with("tls", "program_1")


def test_mock_bridge_uses_the_same_action_rejection_contract():
    bridge = MockBridge(tls_id="tls")
    actions = [
        ControlAction("other", "set_phase", 1),
        ControlAction("tls", "set_phase", "north"),
        ControlAction("tls", "set_phase_duration", 0),
        ControlAction("tls", "set_program", "  "),
        ControlAction("tls", "unknown", 1),
        ControlAction("tls", "set_phase", 3),
    ]
    results = bridge.apply_actions(actions)
    assert [result.accepted for result in results] == [
        False, False, False, False, False, True
    ]
    assert [result.detail for result in results if not result.accepted] == [
        "unknown tls_id: 'other'",
        "set_phase value must be an integer: 'north'",
        "set_phase_duration value must be positive: 0.0",
        "set_program value must be non-empty",
        "unknown action_type: 'unknown'",
    ]
    assert [action.value for action in bridge._applied_actions] == [3]
