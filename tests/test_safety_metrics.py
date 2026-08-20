"""Safety event and completed-vehicle metric contract tests."""

from core.movements import MovementKey, MovementState, PhaseMovementState
from core.types import (
    ActionResult,
    ControlAction,
    JointState,
    MetricSummary,
    SafetyVehicleState,
)
from engine.safety import SafetyObservationCollector


def _movement(incoming: str, outgoing: str) -> MovementState:
    return MovementState(MovementKey(incoming, outgoing), 1, 0, 10, 10, 0, 0.5, 1)


def _state(
    timestamp: float,
    *,
    current_phase: int = 0,
    vehicles: tuple[SafetyVehicleState, ...] = (),
    collisions: tuple[str, ...] = (),
    teleports: tuple[str, ...] = (),
) -> JointState:
    return JointState(
        step=int(timestamp),
        timestamp=timestamp,
        tls_id="tls0",
        current_phase=current_phase,
        current_phase_name=f"phase_{current_phase}",
        elapsed_phase_time=timestamp,
        phase_movements=(
            PhaseMovementState(0, "Gr", (_movement("north_in", "north_out"),), 30),
            PhaseMovementState(1, "rG", (_movement("east_in", "east_out"),), 30),
        ),
        safety_vehicles=vehicles,
        collision_vehicle_ids=collisions,
        teleport_vehicle_ids=teleports,
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


def test_teleport_report_emits_observation_event():
    events = SafetyObservationCollector("run-1").observe(
        None,
        _state(4.0, teleports=("veh-a",)),
        (),
    )

    assert [event.event_type for event in events] == ["teleport"]


def test_rejected_phase_action_emits_illegal_transition():
    action = ControlAction("tls0", "set_phase", 99, "candidate")
    events = SafetyObservationCollector("run-1").observe(
        None,
        _state(3.0),
        (ActionResult(action, False, "phase transition rejected"),),
    )

    assert [event.event_type for event in events] == ["illegal_transition"]
    assert events[0].source == "action_validation"


def test_speed_delta_emits_harsh_braking_event():
    previous = _state(1.0, vehicles=(_vehicle("veh-a", "north_in", 15.0),))
    current = _state(2.0, vehicles=(_vehicle("veh-a", "north_in", 8.0),))

    events = SafetyObservationCollector("run-1").observe(previous, current, ())

    assert [event.event_type for event in events] == ["harsh_braking"]
    assert events[0].entity_ids == ("veh-a",)


def test_lane_transition_against_red_phase_emits_red_light_event():
    previous = _state(1.0, vehicles=(_vehicle("veh-a", "east_in", 8.0),))
    current = _state(2.0, vehicles=(_vehicle("veh-a", "east_out", 8.0),))

    events = SafetyObservationCollector("run-1").observe(previous, current, ())

    assert [event.event_type for event in events] == ["red_light"]
    assert events[0].source == "derived_lane_transition"


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


def test_spatial_and_time_proximity_emits_potential_conflict():
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

    events = SafetyObservationCollector("run-1").observe(None, _state(5.0, vehicles=vehicles), ())

    assert [event.event_type for event in events] == ["potential_conflict"]
    assert events[0].entity_ids == ("veh-a", "veh-b")
    assert events[0].source == "derived_spatial_time_proximity"


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
