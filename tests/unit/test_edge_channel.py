"""EdgeChannel V2X 消息过滤与延迟测试（IB W2，PDF 加分项）。"""
from core.types import JointState, QueueState
from engine.edge_channel import EdgeChannel


def _state(step: int, directions=("north", "south")) -> JointState:
    return JointState(
        step=step, timestamp=float(step), tls_id="tls_0",
        current_phase=0, current_phase_name="p0", elapsed_phase_time=0.0,
        queues=[QueueState(direction=d, queue_length=1.0, waiting_time=0.0,
                           vehicle_count=1) for d in directions],
        flows={d: 100.0 for d in directions},
    )


def test_one_step_delay():
    ch = EdgeChannel(delay_steps=1)
    ch.send(_state(0))
    assert ch.receive() is None  # 延迟未满
    ch.send(_state(1))
    got = ch.receive()
    assert got is not None and got.step == 0  # 收到 1 步前的消息


def test_zero_delay_passthrough():
    ch = EdgeChannel(delay_steps=0)
    ch.send(_state(5))
    assert ch.receive().step == 5


def test_direction_filter():
    ch = EdgeChannel(delay_steps=0, allowed_directions=["north"])
    ch.send(_state(0, directions=("north", "south")))
    got = ch.receive()
    assert [q.direction for q in got.queues] == ["north"]
    assert list(got.flows.keys()) == ["north"]


def test_no_filter_keeps_all():
    ch = EdgeChannel(delay_steps=0)
    ch.send(_state(0))
    assert len(ch.receive().queues) == 2
