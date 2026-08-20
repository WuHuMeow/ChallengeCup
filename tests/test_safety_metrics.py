"""Safety event and completed-vehicle metric contract tests."""

from core.movements import MovementKey, MovementState, PhaseMovementState
from core.types import (
    ActionResult,
    CollisionRecord,
    ControlAction,
    JointState,
    MetricSummary,
    SafetyVehicleState,
)
from engine.safety import ConflictDefinition, SafetyObservationCollector


def _movement(incoming: str, outgoing: str) -> MovementState:
    return MovementState(MovementKey(incoming, outgoing), 1, 0, 10, 10, 0, 0.5, 1)


def _state(
    timestamp: float,
    *,
    step: int | None = None,
    current_phase: int = 0,
    signal_states: tuple[str, ...] = ("Gr", "rG"),
    legal_phase_transitions: tuple[tuple[int, int], ...] | None = None,
    vehicles: tuple[SafetyVehicleState, ...] = (),
    collisions: tuple[str, ...] = (),
    collision_records: tuple[CollisionRecord, ...] = (),
    starting_teleports: tuple[str, ...] = (),
    ending_teleports: tuple[str, ...] = (),
) -> JointState:
    return JointState(
        step=int(timestamp) if step is None else step,
        timestamp=timestamp,
        tls_id="tls0",
        current_phase=current_phase,
        current_phase_name=f"phase_{current_phase}",
        elapsed_phase_time=timestamp,
        phase_movements=tuple(
            PhaseMovementState(
                index,
                signal_state,
                (
                    _movement(
                        "north_in" if index % 2 == 0 else "east_in",
                        "north_out" if index % 2 == 0 else "east_out",
                    ),
                ),
                30,
            )
            for index, signal_state in enumerate(signal_states)
        ),
        legal_phase_transitions=(
            legal_phase_transitions
            if legal_phase_transitions is not None
            else tuple(
                (index, (index + 1) % len(signal_states))
                for index in range(len(signal_states))
            )
        ),
        safety_vehicles=vehicles,
        collisions=collision_records,
        collision_vehicle_ids=collisions,
        starting_teleport_vehicle_ids=starting_teleports,
        ending_teleport_vehicle_ids=ending_teleports,
        teleport_vehicle_ids=tuple(sorted(set(starting_teleports + ending_teleports))),
    )


def _vehicle(
    vehicle_id: str,
    lane_id: str,
    speed_mps: float,
    *,
    position_xy: tuple[float, float] = (0.0, 0.0),
    distance_to_tls_m: float | None = None,
    next_tls_link_index: int | None = None,
    next_tls_state: str | None = None,
) -> SafetyVehicleState:
    return SafetyVehicleState(
        vehicle_id=vehicle_id,
        lane_id=lane_id,
        speed_mps=speed_mps,
        position_xy=position_xy,
        next_tls_id="tls0" if distance_to_tls_m is not None else None,
        distance_to_tls_m=distance_to_tls_m,
        next_tls_link_index=next_tls_link_index,
        next_tls_state=next_tls_state,
    )


def test_collision_report_emits_run_scoped_event():
    events = SafetyObservationCollector("run-1").observe(
        None,
        _state(12.5, collisions=("veh-b", "veh-a", "veh-a")),
        (),
    )

    assert len(events) == 1
    assert events[0].event_type == "collision"
    assert events[0].run_id == "run-1"
    assert events[0].simulation_seconds == 12.5
    assert events[0].entity_ids == ("veh-a", "veh-b")
    assert events[0].source == "sumo_collision"
    assert events[0].confidence == 1.0


def test_collision_records_preserve_each_collider_victim_pair():
    events = SafetyObservationCollector("run-1").observe(
        None,
        _state(
            1.2,
            step=12,
            collision_records=(
                CollisionRecord("collider-a", "victim-a"),
                CollisionRecord("collider-b", "victim-b"),
            ),
        ),
        (),
    )

    assert [event.entity_ids for event in events] == [
        ("collider-a", "victim-a"),
        ("collider-b", "victim-b"),
    ]
    assert {event.step for event in events} == {12}
    assert "collider=collider-a victim=victim-a" in events[0].detail


def test_teleport_report_emits_observation_event():
    collector = SafetyObservationCollector("run-1")
    first = collector.observe(
        None,
        _state(4.0, starting_teleports=("veh-a",)),
        (),
    )
    repeated = collector.observe(
        _state(4.0, starting_teleports=("veh-a",)),
        _state(5.0, starting_teleports=("veh-a",)),
        (),
    )
    ending = collector.observe(
        _state(5.0, starting_teleports=("veh-a",)),
        _state(6.0, ending_teleports=("veh-a",)),
        (),
    )

    assert [event.event_type for event in first] == ["teleport"]
    assert first[0].detail == "phase=starting"
    assert repeated == ()
    assert ending == ()


def test_rejected_phase_action_emits_illegal_transition():
    action = ControlAction("tls0", "set_phase", 99, "candidate")
    events = SafetyObservationCollector("run-1").observe(
        None,
        _state(3.0),
        (
            ActionResult(
                action,
                False,
                "phase transition rejected",
                reason_code="illegal_phase_transition",
            ),
        ),
    )

    assert [event.event_type for event in events] == ["illegal_transition"]
    assert events[0].source == "action_validation"


def test_rejected_phase_parameter_error_is_not_an_illegal_transition():
    action = ControlAction("other", "set_phase", 99, "candidate")

    events = SafetyObservationCollector("run-1").observe(
        None,
        _state(3.0),
        (
            ActionResult(
                action,
                False,
                "unknown tls_id: 'other'",
                reason_code="unknown_tls",
            ),
        ),
    )

    assert events == ()


def test_observed_green_to_green_jump_emits_illegal_transition():
    events = SafetyObservationCollector("run-1").observe(
        _state(1.0, current_phase=0, signal_states=("Gr", "yr", "rG")),
        _state(2.0, current_phase=2, signal_states=("Gr", "yr", "rG")),
        (),
    )

    assert [event.event_type for event in events] == ["illegal_transition"]
    assert events[0].source == "derived_signal_transition"


def test_observed_sequential_phase_change_is_not_an_illegal_transition():
    events = SafetyObservationCollector("run-1").observe(
        _state(1.0, current_phase=0),
        _state(2.0, current_phase=1),
        (),
    )

    assert "illegal_transition" not in {event.event_type for event in events}


def test_successful_program_switch_suppresses_one_topology_transition_check():
    collector = SafetyObservationCollector("run-1")
    before_switch = _state(1.0, current_phase=0)
    switch_snapshot = _state(2.0, current_phase=0)
    program_action = ControlAction("tls0", "set_program", "program_1")
    collector.observe(
        before_switch,
        switch_snapshot,
        (ActionResult(program_action, True, "applied"),),
    )

    events = collector.observe(
        switch_snapshot,
        _state(
            3.0,
            current_phase=2,
            signal_states=("Gr", "yr", "rG"),
        ),
        (),
    )

    assert "illegal_transition" not in {event.event_type for event in events}


def test_speed_delta_emits_harsh_braking_event():
    previous = _state(1.0, vehicles=(_vehicle("veh-a", "north_in", 15.0),))
    current = _state(2.0, vehicles=(_vehicle("veh-a", "north_in", 8.0),))

    events = SafetyObservationCollector("run-1").observe(previous, current, ())

    assert [event.event_type for event in events] == ["harsh_braking"]
    assert events[0].entity_ids == ("veh-a",)


def test_lane_transition_against_red_phase_emits_red_light_event():
    previous = _state(
        1.0,
        vehicles=(
            _vehicle(
                "veh-a",
                "east_in",
                8.0,
                distance_to_tls_m=4.0,
                next_tls_link_index=1,
                next_tls_state="r",
            ),
        ),
    )
    current = _state(2.0, vehicles=(_vehicle("veh-a", "east_out", 8.0),))

    events = SafetyObservationCollector("run-1").observe(previous, current, ())

    assert [event.event_type for event in events] == ["red_light"]
    assert events[0].source == "derived_lane_transition"


def test_lane_transition_after_phase_turns_green_is_not_a_red_light_event():
    previous = _state(
        1.0,
        current_phase=0,
        vehicles=(_vehicle("veh-a", "east_in", 8.0),),
    )
    current = _state(
        2.0,
        current_phase=1,
        vehicles=(_vehicle("veh-a", "east_out", 8.0),),
    )

    events = SafetyObservationCollector("run-1").observe(previous, current, ())

    assert "red_light" not in {event.event_type for event in events}


def test_yellow_signal_crossing_is_not_reported_as_red_light():
    previous = _state(
        1.0,
        signal_states=("Gy", "rG"),
        vehicles=(
            _vehicle(
                "veh-a",
                "east_in",
                8.0,
                distance_to_tls_m=4.0,
                next_tls_link_index=1,
                next_tls_state="y",
            ),
        ),
    )
    current = _state(
        2.0,
        signal_states=("Gy", "rG"),
        vehicles=(_vehicle("veh-a", ":tls0_1_0", 8.0),),
    )

    events = SafetyObservationCollector("run-1").observe(previous, current, ())

    assert "red_light" not in {event.event_type for event in events}


def test_one_second_crossing_window_scales_with_vehicle_speed():
    previous = _state(
        1.0,
        vehicles=(
            _vehicle(
                "veh-a",
                "east_in",
                15.0,
                distance_to_tls_m=12.0,
                next_tls_link_index=1,
                next_tls_state="r",
            ),
        ),
    )
    current = _state(
        2.0,
        vehicles=(_vehicle("veh-a", ":tls0_1_0", 15.0),),
    )

    events = SafetyObservationCollector("run-1").observe(previous, current, ())

    assert [event.event_type for event in events] == ["red_light"]


def test_red_signal_crossing_into_internal_lane_emits_red_light_event():
    previous = _state(
        1.0,
        vehicles=(
            _vehicle(
                "veh-a",
                "east_in",
                8.0,
                distance_to_tls_m=1.0,
                next_tls_link_index=1,
                next_tls_state="r",
            ),
        ),
    )
    current = _state(
        2.0,
        vehicles=(_vehicle("veh-a", ":tls0_1_0", 8.0),),
    )

    events = SafetyObservationCollector("run-1").observe(previous, current, ())

    assert [event.event_type for event in events] == ["red_light"]
    assert events[0].source == "derived_red_signal_crossing"


def test_internal_lane_crossing_after_link_turns_green_is_not_red_light():
    previous = _state(
        1.0,
        current_phase=0,
        vehicles=(
            _vehicle(
                "veh-a",
                "east_in",
                8.0,
                distance_to_tls_m=1.0,
                next_tls_link_index=1,
                next_tls_state="r",
            ),
        ),
    )
    current = _state(
        2.0,
        current_phase=1,
        vehicles=(_vehicle("veh-a", ":tls0_1_0", 8.0),),
    )

    events = SafetyObservationCollector("run-1").observe(previous, current, ())

    assert "red_light" not in {event.event_type for event in events}


def test_missing_next_signal_state_does_not_fabricate_red_light_event():
    previous = _state(
        1.0,
        vehicles=(
            _vehicle(
                "veh-a",
                "east_in",
                8.0,
                distance_to_tls_m=1.0,
                next_tls_link_index=1,
            ),
        ),
    )
    current = _state(
        2.0,
        vehicles=(_vehicle("veh-a", ":tls0_1_0", 8.0),),
    )

    events = SafetyObservationCollector("run-1").observe(previous, current, ())

    assert events == ()


def test_network_foe_and_time_proximity_emit_one_conflict_episode():
    vehicles = (
        _vehicle(
            "veh-a",
            "north_in",
            10.0,
            position_xy=(0.0, 0.0),
            distance_to_tls_m=10.0,
            next_tls_link_index=0,
        ),
        _vehicle(
            "veh-b",
            "east_in",
            10.0,
            position_xy=(5.0, 0.0),
            distance_to_tls_m=12.0,
            next_tls_link_index=1,
        ),
    )

    collector = SafetyObservationCollector(
        "run-1",
        conflict_definitions=(ConflictDefinition(0, 1, 0.0, 0.0),),
    )
    events = collector.observe(None, _state(5.0, vehicles=vehicles), ())
    repeated = collector.observe(
        _state(5.0, vehicles=vehicles),
        _state(5.1, vehicles=vehicles),
        (),
    )

    assert [event.event_type for event in events] == ["potential_conflict"]
    assert events[0].entity_ids == ("veh-a", "veh-b")
    assert events[0].source == "derived_network_foe_ttc"
    assert repeated == ()


def test_non_foe_links_do_not_emit_potential_conflict():
    vehicles = (
        _vehicle(
            "veh-a",
            "north_in",
            10.0,
            position_xy=(0.0, 0.0),
            distance_to_tls_m=10.0,
            next_tls_link_index=0,
        ),
        _vehicle(
            "veh-b",
            "east_in",
            10.0,
            position_xy=(1.0, 0.0),
            distance_to_tls_m=10.0,
            next_tls_link_index=2,
        ),
    )
    collector = SafetyObservationCollector(
        "run-1",
        conflict_definitions=(ConflictDefinition(0, 1, 0.0, 0.0),),
    )

    events = collector.observe(None, _state(5.0, vehicles=vehicles), ())

    assert events == ()


def test_unfinished_vehicles_are_excluded_from_completed_metrics():
    summary = MetricSummary.from_tripinfo(
        completed=[
            {
                "id": "done",
                "duration": "20",
                "timeLoss": "4",
                "waitingCount": "2",
                "emissions": {"fuel_abs": "12.5", "CO2_abs": "2500"},
            }
        ],
        unfinished=[
            {
                "id": "active",
                "duration": "99",
                "timeLoss": "99",
                "waitingCount": "99",
                "emissions": {"fuel_abs": "999", "CO2_abs": "999000"},
            }
        ],
    )

    assert summary.completed_vehicle_count == 1
    assert summary.unfinished_vehicle_count == 1
    assert summary.throughput == 1
    assert summary.avg_travel_time_seconds == 20.0
    assert summary.avg_delay_seconds == 4.0
    assert summary.total_stops == 2
    assert summary.fuel_ml == 12.5
    assert summary.co2_g == 2.5
    assert summary.fuel_ml_per_completed == 12.5
    assert summary.co2_g_per_completed == 2.5
