import copy
import dataclasses

from algorithms.classic_max_pressure import ClassicMaxPressureAlgorithm
from algorithms.registry import get_algorithm_registry
from core.movements import MovementKey, MovementState, PhaseMovementState
from core.types import JointState


def _movement(queue: float, downstream: float, service_rate: float) -> MovementState:
    return MovementState(
        key=MovementKey("in", "out"),
        queue_vehicles=queue,
        downstream_queue_vehicles=downstream,
        incoming_capacity=20,
        downstream_capacity=20,
        downstream_occupancy=0.0,
        saturation_rate=service_rate,
        turn_ratio=1.0,
    )


def _state() -> JointState:
    return JointState(
        step=1,
        timestamp=1.0,
        tls_id="tls0",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=10.0,
        phase_movements=(
            PhaseMovementState(0, "Gr", (_movement(8, 2, 1),), 30),
            PhaseMovementState(1, "rG", (_movement(6, 1, 2),), 30),
            PhaseMovementState(2, "rr", (_movement(100, 0, 10),), 3),
        ),
    )


def test_classic_pressure_uses_downstream_queue_and_service_rate():
    actions = ClassicMaxPressureAlgorithm().step(_state())

    assert actions[0].action_type == "set_phase"
    assert actions[0].value == 1


def test_classic_pressure_breaks_equal_scores_by_current_phase_then_index():
    state = _state()
    equal = dataclasses.replace(
        state.phase_movements[1], movements=(_movement(5, 0, 1),)
    )
    state.phase_movements = (state.phase_movements[0], equal)

    assert ClassicMaxPressureAlgorithm().step(state)[0].value == 0


def test_classic_pressure_does_not_use_capacity_prediction_or_spillback():
    baseline = ClassicMaxPressureAlgorithm().step(_state())
    changed = copy.deepcopy(_state())
    changed.phase_movements = tuple(
        dataclasses.replace(
            phase,
            movements=tuple(
                dataclasses.replace(
                    movement,
                    downstream_occupancy=1.0,
                    incoming_capacity=1,
                    downstream_capacity=1,
                )
                for movement in phase.movements
            ),
        )
        for phase in changed.phase_movements
    )

    assert ClassicMaxPressureAlgorithm().step(changed) == baseline


def test_classic_maxpressure_is_available_from_its_own_factory():
    spec = get_algorithm_registry().get("classic_maxpressure")

    assert spec.available is True
    assert isinstance(spec.factory(), ClassicMaxPressureAlgorithm)


def test_classic_manifest_has_no_capacity_aware_enhancement_flags():
    assert ClassicMaxPressureAlgorithm().manifest == {"name": "classic_maxpressure"}
