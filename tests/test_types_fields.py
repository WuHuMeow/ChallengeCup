"""core/types.py 新增字段契约测试（IB W1/W4）。"""
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
