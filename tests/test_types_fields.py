"""core/types.py 新增字段契约测试（IB W1/W4）。"""
import pytest

from core.movements import PhaseMovementState
from core.types import JointState, QueueState, VehicleState


def test_queue_state_capacity_defaults_zero():
    q = QueueState(direction="north", queue_length=3.0, waiting_time=5.0, vehicle_count=4)
    assert q.capacity == 0.0


def test_vehicle_state_fields():
    v = VehicleState(vehicle_id="veh_1", lane_id="-E2_0", speed=8.5)
    assert v.vehicle_id == "veh_1"
    assert v.lane_id == "-E2_0"
    assert v.speed == 8.5


def test_joint_state_new_fields_default_empty():
    state = JointState(
        step=0, timestamp=0.0, tls_id="tls_0",
        current_phase=0, current_phase_name="p0", elapsed_phase_time=0.0,
        queues=[], flows={},
    )
    assert state.vehicles == []
    assert state.arrival_history == []
    assert state.detector_values == {}
    assert state.phase_movements == ()


def test_joint_state_normalizes_phase_movements_to_tuple():
    phase = PhaseMovementState(0, "Gr", (), 30.0)
    source = [phase]
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls_0",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=0.0,
        phase_movements=source,
    )
    source.clear()

    assert state.phase_movements == (phase,)


def test_joint_state_rejects_non_phase_movement_items():
    with pytest.raises(ValueError, match="phase_movements"):
        JointState(
            step=0,
            timestamp=0.0,
            tls_id="tls_0",
            current_phase=0,
            current_phase_name="p0",
            elapsed_phase_time=0.0,
            phase_movements=[object()],
        )


def test_joint_state_preserves_movement_phase_state_tuple():
    phase = PhaseMovementState(phase_index=0, signal_state="Gr", movements=(), nominal_duration=30.0)
    state = JointState(
        step=0, timestamp=0.0, tls_id="tls_0",
        current_phase=0, current_phase_name="p0", elapsed_phase_time=0.0,
        queues=[], flows={}, phase_movements=(phase,),
    )

    assert state.phase_movements == (phase,)
