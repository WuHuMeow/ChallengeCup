from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

import pytest

from core.movements import MovementKey, MovementState, PhaseMovementState
from core.types import CollisionRecord, ControlAction, SafetyVehicleState
from engine.action_validation import validate_control_action
from engine.artifacts import RunArtifacts
from engine.mock_bridge import MockBridge
from engine.safety import ConflictDefinition
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

    assert valid_duration == (3.5, None, None)
    assert valid_program == ("program_1", None, None)
    assert invalid == (
        None,
        "invalid_phase_type",
        "set_phase value must be an integer: 'north'",
    )


@pytest.mark.parametrize("value", [True, -1, 4])
def test_control_action_validation_rejects_invalid_phase_domain(value):
    _, _, error = validate_control_action(
        ControlAction("tls", "set_phase", value),
        "tls",
        phase_count=4,
    )

    assert error is not None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_control_action_validation_rejects_non_finite_duration(value):
    _, _, error = validate_control_action(
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

    assert result == (None, "unknown_program", "unknown signal program: 'missing'")


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
    assert cmd[cmd.index("--collision-output") + 1] == (
        artifacts.collisions.resolve().as_posix()
    )
    assert cmd[cmd.index("--tripinfo-output.write-unfinished") + 1] == "true"
    assert cmd[cmd.index("--device.emissions.probability") + 1] == "1"
    assert cmd[cmd.index("--emissions.volumetric-fuel") + 1] == "true"


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


def test_get_state_publishes_precise_movement_and_safety_observations():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    bridge.step_length = 0.1
    movement = MovementState(MovementKey("in_0", "out_0"), 2, 1, 10, 10, 0.2, 0.5, 1)
    phase_movement = PhaseMovementState(0, "G", (movement,), 30.0)
    bridge._movement_state_builder = SimpleNamespace(
        snapshot=lambda: (phase_movement,),
        movement_keys=(MovementKey("in_0", "out_0"),),
        capacity_inputs={
            "vehicle_length_m": 5.0,
            "minimum_gap_m": 2.5,
            "capacity_spacing_m": 7.5,
        },
    )
    program = SimpleNamespace(
        programID="program_0",
        phases=[SimpleNamespace(state="G", duration=30.0, name="green")],
    )
    with (
        patch.object(traci.simulation, "getTime", return_value=1.2),
        patch.object(
            traci.simulation,
            "getCollisions",
            return_value=(
                SimpleNamespace(
                    collider="collider",
                    victim="victim",
                    colliderType="car",
                    victimType="bus",
                    colliderSpeed=8.0,
                    victimSpeed=2.0,
                    collisionType="junction",
                    lane=":tls_0",
                    pos=4.5,
                ),
            ),
        ),
        patch.object(traci.simulation, "getStartingTeleportIDList", return_value=("start",)),
        patch.object(traci.simulation, "getEndingTeleportIDList", return_value=("end",)),
        patch.object(traci.trafficlight, "getPhase", return_value=0),
        patch.object(traci.trafficlight, "getAllProgramLogics", return_value=[program]),
        patch.object(traci.trafficlight, "getProgram", return_value="program_0"),
        patch.object(traci.trafficlight, "getSpentDuration", return_value=1.2),
        patch.object(traci.trafficlight, "getControlledLinks", return_value=[]),
        patch.object(traci.vehicle, "getIDList", return_value=["veh-1"]),
        patch.object(traci.vehicle, "getLaneID", return_value="in_0"),
        patch.object(traci.vehicle, "getSpeed", return_value=5.0),
        patch.object(traci.vehicle, "getPosition", return_value=(1.0, 2.0)),
        patch.object(traci.vehicle, "getNextTLS", return_value=(("tls", 3, 12.0, "r"),)),
    ):
        state = bridge.get_state()

    assert state.step == 12
    assert state.timestamp == 1.2
    assert state.phase_movements == (phase_movement,)
    assert state.collisions == (
        CollisionRecord(
            collider_id="collider",
            victim_id="victim",
            collider_type="car",
            victim_type="bus",
            collider_speed_mps=8.0,
            victim_speed_mps=2.0,
            collision_type="junction",
            lane_id=":tls_0",
            position_m=4.5,
        ),
    )
    assert state.collision_vehicle_ids == ("collider", "victim")
    assert state.starting_teleport_vehicle_ids == ("start",)
    assert state.ending_teleport_vehicle_ids == ("end",)
    assert state.teleport_vehicle_ids == ("end", "start")
    assert state.safety_vehicles[0].position_xy == (1.0, 2.0)
    assert state.safety_vehicles[0].distance_to_tls_m == 12.0
    assert bridge.movement_capacity_inputs["capacity_spacing_m"] == 7.5


def test_turn_ratios_are_read_from_the_scene_turn_file(tmp_path):
    config = tmp_path / "demo_1.sumocfg"
    config.write_text("<configuration/>", encoding="utf-8")
    (tmp_path / "demo_1.turn.xml").write_text(
        '<edgeRelations><interval begin="0" end="10">'
        '<edgeRelation from="-E1" to="E3" probability="0.4"/>'
        "</interval></edgeRelations>",
        encoding="utf-8",
    )
    bridge = TraCIBridge(config)

    bridge._load_turn_ratios()

    assert bridge.get_turn_ratio("-E1_0", "E3_1") == 0.4
    assert bridge.get_turn_ratio("-E1_0", "E2_0") is None


def test_observed_vehicle_turns_fill_missing_turn_relations():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge._movement_state_builder = SimpleNamespace(
        movement_keys=(
            MovementKey("in_0", "out_a_0"),
            MovementKey("in_0", "out_b_0"),
        )
    )
    bridge._record_turn_observations(
        (
            SafetyVehicleState("a", "in_0", 5.0, (0.0, 0.0)),
            SafetyVehicleState("b", "in_0", 5.0, (0.0, 0.0)),
        )
    )
    bridge._record_turn_observations(
        (
            SafetyVehicleState("a", ":internal_0", 5.0, (0.0, 0.0)),
            SafetyVehicleState("b", ":internal_1", 5.0, (0.0, 0.0)),
        )
    )
    bridge._record_turn_observations(
        (
            SafetyVehicleState("a", "out_a_0", 5.0, (0.0, 0.0)),
            SafetyVehicleState("b", "out_b_0", 5.0, (0.0, 0.0)),
        )
    )

    assert bridge.get_turn_ratio("in_0", "out_a_0") == 0.5
    assert bridge.get_turn_ratio("in_0", "out_b_0") == 0.5


def test_network_request_foes_build_conflict_point_distances(tmp_path):
    config = tmp_path / "demo_1.sumocfg"
    config.write_text(
        '<configuration><input><net-file value="network.net.xml"/>'
        "</input></configuration>",
        encoding="utf-8",
    )
    (tmp_path / "network.net.xml").write_text(
        "<net>"
        '<edge id=":tls_0" function="internal">'
        '<lane id=":tls_0_0" index="0" speed="10" length="20" '
        'shape="0,0 10,10"/></edge>'
        '<edge id=":tls_1" function="internal">'
        '<lane id=":tls_1_0" index="0" speed="10" length="20" '
        'shape="0,10 10,0"/></edge>'
        '<junction id="tls" type="traffic_light">'
        '<request index="0" response="00" foes="10" cont="0"/>'
        '<request index="1" response="00" foes="01" cont="0"/>'
        "</junction>"
        '<connection from="a" to="b" fromLane="0" toLane="0" '
        'via=":tls_0_0" tl="tls" linkIndex="0"/>'
        '<connection from="c" to="d" fromLane="0" toLane="0" '
        'via=":tls_1_0" tl="tls" linkIndex="1"/>'
        "</net>",
        encoding="utf-8",
    )
    bridge = TraCIBridge(config)
    bridge.tls_id = "tls"

    bridge._load_conflict_definitions()

    assert len(bridge.conflict_definitions) == 1
    definition = bridge.conflict_definitions[0]
    assert (definition.first_link_index, definition.second_link_index) == (0, 1)
    assert definition.first_distance_after_stopline_m == pytest.approx(5 * 2**0.5)
    assert definition.second_distance_after_stopline_m == pytest.approx(5 * 2**0.5)


def test_network_foes_map_junction_internal_lanes_to_controlled_link_indices(tmp_path):
    config = tmp_path / "demo_chain.sumocfg"
    config.write_text(
        '<configuration><input><net-file value="network.net.xml"/>'
        "</input></configuration>",
        encoding="utf-8",
    )
    (tmp_path / "network.net.xml").write_text(
        "<net>"
        '<edge id=":tls_0" function="internal"><lane id=":tls_0_0" '
        'index="0" shape="0,0 3,3"/></edge>'
        '<edge id=":tls_1" function="internal"><lane id=":tls_1_0" '
        'index="0" shape="3,3 10,10"/></edge>'
        '<edge id=":tls_2" function="internal"><lane id=":tls_2_0" '
        'index="0" shape="0,10 3,7"/></edge>'
        '<edge id=":tls_3" function="internal"><lane id=":tls_3_0" '
        'index="0" shape="3,7 10,0"/></edge>'
        '<junction id="tls" type="traffic_light" '
        'intLanes=":tls_1_0 :tls_3_0">'
        '<request index="0" response="00" foes="10" cont="0"/>'
        '<request index="1" response="00" foes="01" cont="0"/>'
        "</junction>"
        '<connection from="a" to="b" fromLane="0" toLane="0" '
        'via=":tls_0_0" tl="tls" linkIndex="7"/>'
        '<connection from="c" to="d" fromLane="0" toLane="0" '
        'via=":tls_2_0" tl="tls" linkIndex="9"/>'
        '<connection from=":tls_0" to=":tls_1" fromLane="0" toLane="0" '
        'via=":tls_1_0"/>'
        '<connection from=":tls_2" to=":tls_3" fromLane="0" toLane="0" '
        'via=":tls_3_0"/>'
        "</net>",
        encoding="utf-8",
    )
    bridge = TraCIBridge(config)
    bridge.tls_id = "tls"

    bridge._load_conflict_definitions()

    assert [
        (definition.first_link_index, definition.second_link_index)
        for definition in bridge.conflict_definitions
    ] == [(7, 9)]


def test_network_foes_use_lane_endpoints_when_internal_links_are_absent(tmp_path):
    config = tmp_path / "demo_11.sumocfg"
    config.write_text(
        '<configuration><input><net-file value="network.net.xml"/>'
        "</input></configuration>",
        encoding="utf-8",
    )
    (tmp_path / "network.net.xml").write_text(
        "<net>"
        '<edge id="west_in"><lane id="west_in_0" index="0" '
        'shape="-10,0 -2,0"/></edge>'
        '<edge id="east_out"><lane id="east_out_0" index="0" '
        'shape="2,0 10,0"/></edge>'
        '<edge id="south_in"><lane id="south_in_0" index="0" '
        'shape="0,-10 0,-2"/></edge>'
        '<edge id="north_out"><lane id="north_out_0" index="0" '
        'shape="0,2 0,10"/></edge>'
        '<junction id="tls" type="traffic_light">'
        '<request index="0" response="00" foes="10" cont="0"/>'
        '<request index="1" response="00" foes="01" cont="0"/>'
        "</junction>"
        '<connection from="west_in" to="east_out" fromLane="0" '
        'toLane="0" tl="tls" linkIndex="0"/>'
        '<connection from="south_in" to="north_out" fromLane="0" '
        'toLane="0" tl="tls" linkIndex="1"/>'
        "</net>",
        encoding="utf-8",
    )
    bridge = TraCIBridge(config)
    bridge.tls_id = "tls"

    bridge._load_conflict_definitions()

    assert bridge.conflict_definitions == (
        ConflictDefinition(0, 1, 2.0, 2.0),
    )


def test_network_foes_keep_closest_approach_when_paths_do_not_cross(tmp_path):
    config = tmp_path / "demo_parallel.sumocfg"
    config.write_text(
        '<configuration><input><net-file value="network.net.xml"/>'
        "</input></configuration>",
        encoding="utf-8",
    )
    (tmp_path / "network.net.xml").write_text(
        "<net>"
        '<edge id=":tls_0" function="internal"><lane id=":tls_0_0" '
        'index="0" shape="0,0 10,0"/></edge>'
        '<edge id=":tls_1" function="internal"><lane id=":tls_1_0" '
        'index="0" shape="0,2 10,2"/></edge>'
        '<junction id="tls" type="traffic_light">'
        '<request index="0" response="00" foes="10" cont="0"/>'
        '<request index="1" response="00" foes="01" cont="0"/>'
        "</junction>"
        '<connection from="a" to="b" fromLane="0" toLane="0" '
        'via=":tls_0_0" tl="tls" linkIndex="0"/>'
        '<connection from="c" to="d" fromLane="0" toLane="0" '
        'via=":tls_1_0" tl="tls" linkIndex="1"/>'
        "</net>",
        encoding="utf-8",
    )
    bridge = TraCIBridge(config)
    bridge.tls_id = "tls"

    bridge._load_conflict_definitions()

    assert len(bridge.conflict_definitions) == 1


def test_traci_lane_occupancy_converts_percent_to_fraction():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))

    with patch.object(traci.lane, "getLastStepOccupancy", return_value=1.0):
        occupancy = bridge.get_lane_occupancy("out_0")

    assert occupancy == 0.01


def test_invalid_phase_returns_rejection_without_calling_traci():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    with patch.object(traci.trafficlight, "setPhase") as set_phase:
        results = bridge._apply_actions([
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
        patch("engine.traci_bridge.MovementStateBuilder", return_value=object()),
    ):
        results = bridge._apply_actions(actions)
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
        patch.object(traci.trafficlight, "getPhase", return_value=0),
        patch.object(traci.trafficlight, "setPhase") as set_phase,
        patch.object(traci.trafficlight, "setProgram") as set_program,
    ):
        results = bridge._apply_actions(actions)

    assert [result.accepted for result in results] == [False, False]
    assert [result.reason_code for result in results] == [
        "phase_out_of_range",
        "unknown_program",
    ]
    set_phase.assert_not_called()
    set_program.assert_not_called()


def test_traci_rejects_non_sequential_green_to_green_phase_jump():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    programs = [
        SimpleNamespace(
            programID="program_0",
            phases=[
                SimpleNamespace(state="Gr"),
                SimpleNamespace(state="yr"),
                SimpleNamespace(state="rG"),
            ],
        )
    ]
    with (
        patch.object(traci.trafficlight, "getAllProgramLogics", return_value=programs),
        patch.object(traci.trafficlight, "getProgram", return_value="program_0"),
        patch.object(traci.trafficlight, "getPhase", return_value=0),
        patch.object(traci.trafficlight, "setPhase") as set_phase,
    ):
        result = bridge._apply_actions(
            [ControlAction("tls", "set_phase", 2, "unsafe direct jump")]
        )[0]

    assert result.accepted is False
    assert result.reason_code == "illegal_phase_transition"
    set_phase.assert_not_called()


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
        results = bridge._apply_actions(actions)

    assert [result.accepted for result in results] == [False, True, False]
    assert get_programs.call_count == 2
    set_phase.assert_not_called()
    set_duration.assert_called_once_with("tls", 3.0)
    set_program.assert_not_called()


def test_traci_rejects_phase_action_when_current_phase_is_unavailable():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    programs = [SimpleNamespace(programID="program_0", phases=[object()] * 2)]
    with (
        patch.object(traci.trafficlight, "getAllProgramLogics", return_value=programs),
        patch.object(traci.trafficlight, "getProgram", return_value="program_0"),
        patch.object(
            traci.trafficlight,
            "getPhase",
            side_effect=traci.exceptions.FatalTraCIError("not connected"),
        ),
        patch.object(traci.trafficlight, "setPhase") as set_phase,
    ):
        result = bridge._apply_actions(
            [ControlAction("tls", "set_phase", 1)]
        )[0]

    assert result.accepted is False
    assert result.reason_code == "control_domain_unavailable"
    set_phase.assert_not_called()


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
        patch.object(traci.trafficlight, "getPhase", return_value=1),
        patch.object(traci.trafficlight, "setPhase") as set_phase,
        patch.object(traci.trafficlight, "setPhaseDuration") as set_duration,
        patch.object(traci.trafficlight, "setProgram") as set_program,
        patch("engine.traci_bridge.MovementStateBuilder", return_value=object()),
    ):
        results = bridge._apply_actions(actions)
    assert [result.accepted for result in results] == [True, True, True]
    assert [result.action for result in results] == actions
    set_phase.assert_called_once_with("tls", 2)
    set_duration.assert_called_once_with("tls", 3.5)
    set_program.assert_called_once_with("tls", "program_1")


def test_plan_backed_program_is_defined_then_activated():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    programs = [SimpleNamespace(programID="program_0", phases=[object()])]
    action = ControlAction(
        "tls",
        "set_program",
        {
            "program_id": "frozen",
            "phases": [
                {"duration": 30.0, "state": "Gr"},
                {"duration": 3.0, "state": "yr"},
            ],
        },
    )
    with (
        patch.object(traci.trafficlight, "getAllProgramLogics", return_value=programs),
        patch.object(traci.trafficlight, "getProgram", return_value="program_0"),
        patch.object(traci.trafficlight, "getPhase", return_value=0),
        patch.object(traci.trafficlight, "Phase", side_effect=lambda duration, state: (duration, state)),
        patch.object(
            traci.trafficlight,
            "Logic",
            side_effect=lambda program_id, logic_type, phase_index, phases: SimpleNamespace(
                programID=program_id, phases=phases
            ),
        ),
        patch.object(traci.trafficlight, "setProgramLogic") as define,
        patch.object(traci.trafficlight, "setProgram") as set_program,
        patch("engine.traci_bridge.MovementStateBuilder", return_value=object()),
    ):
        result = bridge._apply_actions([action])[0]

    assert result.accepted is True
    assert define.call_args.args[0] == "tls"
    assert define.call_args.args[1].programID == "frozen"
    assert define.call_args.args[1].phases == [(30.0, "Gr"), (3.0, "yr")]
    set_program.assert_called_once_with("tls", "frozen")


def test_successful_program_switch_rebuilds_movement_topology():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    old_builder = object()
    new_builder = object()
    bridge._movement_state_builder = old_builder
    programs = [
        SimpleNamespace(programID="program_0", phases=[object()]),
        SimpleNamespace(programID="program_1", phases=[object(), object()]),
    ]

    with (
        patch.object(traci.trafficlight, "getAllProgramLogics", return_value=programs),
        patch.object(traci.trafficlight, "getProgram", return_value="program_0"),
        patch.object(traci.trafficlight, "getPhase", return_value=0),
        patch.object(traci.trafficlight, "setProgram") as set_program,
        patch("engine.traci_bridge.MovementStateBuilder", return_value=new_builder) as builder,
    ):
        result = bridge._apply_actions(
            [ControlAction("tls", "set_program", "program_1")]
        )[0]

    assert result.accepted is True
    set_program.assert_called_once_with("tls", "program_1")
    builder.assert_called_once_with(bridge, "tls")
    assert bridge._movement_state_builder is new_builder


def test_failed_program_topology_rebuild_restores_previous_program_and_builder():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    old_builder = object()
    bridge._movement_state_builder = old_builder
    programs = [
        SimpleNamespace(programID="program_0", phases=[object()]),
        SimpleNamespace(programID="program_1", phases=[object(), object()]),
    ]
    with (
        patch.object(traci.trafficlight, "getAllProgramLogics", return_value=programs),
        patch.object(traci.trafficlight, "getProgram", return_value="program_0"),
        patch.object(traci.trafficlight, "getPhase", return_value=0),
        patch.object(traci.trafficlight, "setProgram") as set_program,
        patch(
            "engine.traci_bridge.MovementStateBuilder",
            side_effect=RuntimeError("broken topology"),
        ),
    ):
        result = bridge._apply_actions(
            [ControlAction("tls", "set_program", "program_1")]
        )[0]

    assert result.accepted is False
    assert result.reason_code == "topology_rebuild_failed"
    assert set_program.call_args_list == [
        call("tls", "program_1"),
        call("tls", "program_0"),
    ]
    assert bridge._movement_state_builder is old_builder


def test_mock_bridge_uses_the_same_action_rejection_contract():
    bridge = MockBridge(tls_id="tls")
    actions = [
        ControlAction("other", "set_phase", 1),
        ControlAction("tls", "set_phase", "north"),
        ControlAction("tls", "set_phase_duration", 0),
        ControlAction("tls", "set_program", "  "),
        ControlAction("tls", "unknown", 1),
        ControlAction("tls", "set_phase", 1),
    ]
    results = bridge._apply_actions(actions)
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
    assert [action.value for action in bridge._applied_actions] == [1]


def test_mock_bridge_rejects_the_same_domain_errors_as_traci():
    bridge = MockBridge(tls_id="tls")
    actions = [
        ControlAction("tls", "set_phase", True),
        ControlAction("tls", "set_phase", 4),
        ControlAction("tls", "set_phase_duration", float("nan")),
        ControlAction("tls", "set_program", "missing"),
    ]

    results = bridge._apply_actions(actions)

    assert [result.accepted for result in results] == [False] * 4
    assert bridge._applied_actions == []
