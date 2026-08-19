from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.types import ControlAction
from engine.action_validation import validate_control_action
from engine.artifacts import RunArtifacts
from engine.mock_bridge import MockBridge
from engine.traci_bridge import TraCIBridge, traci
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator


def test_control_action_validation_normalizes_values_and_rejections():
    valid_duration = validate_control_action(
        ControlAction("tls", "set_phase_duration", "3.5"), "tls"
    )
    valid_program = validate_control_action(
        ControlAction("tls", "set_program", " program_1 "), "tls"
    )
    invalid = validate_control_action(
        ControlAction("tls", "set_phase", "north"), "tls"
    )

    assert valid_duration == (3.5, None)
    assert valid_program == ("program_1", None)
    assert invalid == (None, "set_phase value must be an integer: 'north'")


@pytest.mark.parametrize("value", [True, -1, 4])
def test_control_action_validation_rejects_invalid_phase_domain(value):
    _, error = validate_control_action(
        ControlAction("tls", "set_phase", value),
        "tls",
        phase_count=4,
    )

    assert error is not None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_control_action_validation_rejects_non_finite_duration(value):
    _, error = validate_control_action(
        ControlAction("tls", "set_phase_duration", value),
        "tls",
    )

    assert error is not None
    assert "finite" in error


def test_control_action_validation_rejects_unknown_program():
    result = validate_control_action(
        ControlAction("tls", "set_program", "missing"),
        "tls",
        program_ids={"program_0", "program_1"},
    )

    assert result == (None, "unknown signal program: 'missing'")


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
    assert cmd[cmd.index("--tripinfo-output.write-unfinished") + 1] == "true"
    assert cmd[cmd.index("--device.emissions.probability") + 1] == "1"


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


def test_scene_11_variant_keeps_configured_queue_output_redirect(tmp_path):
    meta = SceneRegistry().get_scene("11").meta
    bundle = VariantGenerator().generate_bundle(
        meta,
        1.0,
        None,
        tmp_path / "variants",
    )
    artifacts = RunArtifacts.create(tmp_path, "11", "actuated", 1.0, 42)

    cmd = TraCIBridge(bundle.sumo_cfg, artifacts=artifacts)._build_cmd()

    assert cmd[cmd.index("--queue-output") + 1] == (
        artifacts.queues.resolve().as_posix()
    )


def test_get_state_uses_spent_duration_after_phase_duration_override():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    program = SimpleNamespace(
        programID="program_0",
        phases=[SimpleNamespace(state="G", duration=50.0, name="green")],
    )
    with (
        patch.object(traci.simulation, "getTime", return_value=14.0),
        patch.object(traci.trafficlight, "getPhase", return_value=0),
        patch.object(
            traci.trafficlight,
            "getAllProgramLogics",
            return_value=[program],
        ),
        patch.object(traci.trafficlight, "getProgram", return_value="program_0"),
        patch.object(
            traci.trafficlight,
            "getSpentDuration",
            return_value=4.0,
        ) as get_spent,
        patch.object(traci.trafficlight, "getPhaseDuration", return_value=50.0) as get_total,
        patch.object(traci.trafficlight, "getNextSwitch", return_value=98.0) as get_next,
        patch.object(traci.trafficlight, "getControlledLinks", return_value=[]),
        patch.object(traci.vehicle, "getIDList", return_value=[]),
    ):
        state = bridge.get_state()

    assert state.elapsed_phase_time == 4.0
    get_spent.assert_called_once_with("tls")
    get_total.assert_not_called()
    get_next.assert_not_called()


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


def test_traci_rejects_out_of_range_phase_and_unknown_program():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    programs = [
        SimpleNamespace(programID="program_0", phases=[object()] * 4),
        SimpleNamespace(programID="program_1", phases=[object()] * 2),
    ]
    actions = [
        ControlAction("tls", "set_phase", 4),
        ControlAction("tls", "set_program", "missing"),
    ]
    with (
        patch.object(traci.trafficlight, "getAllProgramLogics", return_value=programs),
        patch.object(traci.trafficlight, "getProgram", return_value="program_0"),
        patch.object(traci.trafficlight, "setPhase") as set_phase,
        patch.object(traci.trafficlight, "setProgram") as set_program,
    ):
        results = bridge.apply_actions(actions)

    assert [result.accepted for result in results] == [False, False]
    set_phase.assert_not_called()
    set_program.assert_not_called()


def test_traci_rejects_domain_actions_when_program_domain_is_unavailable():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    actions = [
        ControlAction("tls", "set_phase", 1),
        ControlAction("tls", "set_phase_duration", 3.0),
        ControlAction("tls", "set_program", "program_0"),
    ]
    with (
        patch.object(
            traci.trafficlight,
            "getAllProgramLogics",
            side_effect=traci.exceptions.FatalTraCIError("not connected"),
        ) as get_programs,
        patch.object(traci.trafficlight, "setPhase") as set_phase,
        patch.object(traci.trafficlight, "setPhaseDuration") as set_duration,
        patch.object(traci.trafficlight, "setProgram") as set_program,
    ):
        results = bridge.apply_actions(actions)

    assert [result.accepted for result in results] == [False, True, False]
    assert get_programs.call_count == 2
    set_phase.assert_not_called()
    set_duration.assert_called_once_with("tls", 3.0)
    set_program.assert_not_called()


def test_valid_actions_are_applied_and_not_rejected():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    programs = [
        SimpleNamespace(programID="program_0", phases=[object()] * 4),
        SimpleNamespace(programID="program_1", phases=[object()] * 3),
    ]
    actions = [
        ControlAction("tls", "set_phase", 2),
        ControlAction("tls", "set_phase_duration", "3.5"),
        ControlAction("tls", "set_program", "program_1"),
    ]
    with (
        patch.object(traci.trafficlight, "getAllProgramLogics", return_value=programs),
        patch.object(traci.trafficlight, "getProgram", return_value="program_0"),
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


def test_mock_bridge_rejects_the_same_domain_errors_as_traci():
    bridge = MockBridge(tls_id="tls")
    actions = [
        ControlAction("tls", "set_phase", True),
        ControlAction("tls", "set_phase", 4),
        ControlAction("tls", "set_phase_duration", float("nan")),
        ControlAction("tls", "set_program", "missing"),
    ]

    results = bridge.apply_actions(actions)

    assert [result.accepted for result in results] == [False] * 4
    assert bridge._applied_actions == []
