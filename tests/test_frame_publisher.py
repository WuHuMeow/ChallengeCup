import asyncio
from pathlib import Path
import threading

from api.realtime import RealtimeHub
from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import Scene, SceneMeta
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner
from visualization.frame_publisher import FramePublisher, FrameRecord


_VALID_NET = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "intersection_data"
    / "1"
    / "sumo工程"
    / "demo_1.net.xml"
)


def _scene() -> Scene:
    return Scene(SceneMeta(
        intersection_id="1",
        name="test",
        sumo_net=_VALID_NET,
        sumo_rou="x.rou.xml",
        sumo_flow="x.flow.xml",
        sumo_turn="x.turn.xml",
        sumo_cfg="x.sumocfg",
        timing_xlsx="x.xlsx",
    ))


class _FrameBridge(MockBridge):
    def __init__(self):
        super().__init__()
        self.capture_threads: list[int] = []
        self.capture_calls = 0

    def capture_gui_frame(self, view_id="View #0"):
        self.capture_calls += 1
        self.capture_threads.append(threading.get_ident())
        return FrameRecord(
            "runner",
            self.capture_calls,
            float(self._current_step) * self.step_length,
            f"frame-{self.capture_calls}".encode(),
            float(self.capture_calls),
        )


def test_frame_publisher_keeps_one_newest_frame_per_run():
    publisher = FramePublisher()
    publisher.publish(FrameRecord("run-1", 1, 1.0, b"old", 1.0))
    publisher.publish(FrameRecord("run-1", 2, 2.0, b"new", 2.0))
    publisher.publish(FrameRecord("run-1", 1, 1.0, b"stale", 3.0))

    latest = publisher.latest("run-1")

    assert latest is not None
    assert latest.sequence == 2
    assert latest.png == b"new"
    assert publisher.size("run-1") == 1


def test_frame_publisher_clear_removes_run_frame():
    publisher = FramePublisher()
    publisher.publish(FrameRecord("run-1", 1, 1.0, b"frame", 1.0))

    publisher.clear("run-1")

    assert publisher.latest("run-1") is None
    assert publisher.size("run-1") == 0


def test_realtime_hub_replays_latest_and_delivers_new_messages():
    hub = RealtimeHub()
    hub.publish("run-1", {"type": "status", "status": "running"})

    async def consume() -> list[dict[str, object]]:
        subscription = hub.subscribe("run-1")
        first = await subscription.__anext__()
        task = asyncio.create_task(subscription.__anext__())
        await asyncio.sleep(0)
        hub.publish("run-1", {"type": "metrics", "simulation_time": 1.0})
        second = await asyncio.wait_for(task, timeout=1.0)
        await subscription.aclose()
        return [first, second]

    messages = asyncio.run(consume())

    assert messages == [
        {"run_id": "run-1", "type": "status", "status": "running"},
        {"run_id": "run-1", "type": "metrics", "simulation_time": 1.0},
    ]


def test_realtime_hub_publishes_status_from_atomic_latest_snapshot():
    hub = RealtimeHub()
    hub.publish("run-1", {"type": "terminal", "simulation_time": 5.0})

    hub.publish_status("run-1", "completed", "")

    latest = hub.latest("run-1")
    assert latest is not None
    assert latest["type"] == "status"
    assert latest["status"] == "completed"
    assert latest["simulation_time"] == 5.0


def test_realtime_hub_serializes_cross_thread_publication_order():
    hub = RealtimeHub()
    first_scheduled = threading.Event()
    release_first = threading.Event()
    scheduled: list[str] = []

    class ControlledLoop:
        def call_soon_threadsafe(self, _callback, _queue, payload):
            if payload["status"] == "stopping":
                first_scheduled.set()
                release_first.wait(timeout=1.0)
            scheduled.append(payload["status"])

    loop = ControlledLoop()
    queue = object()
    with hub._lock:
        hub._subscribers["run-1"] = {(loop, queue)}

    first = threading.Thread(
        target=hub.publish,
        args=("run-1", {"type": "status", "status": "stopping"}),
    )
    second = threading.Thread(
        target=hub.publish,
        args=("run-1", {"type": "status", "status": "terminal"}),
    )
    first.start()
    assert first_scheduled.wait(timeout=1.0)
    second.start()
    second.join(timeout=0.1)
    release_first.set()
    first.join(timeout=1.0)
    second.join(timeout=1.0)

    assert scheduled == ["stopping", "terminal"]


def test_runner_captures_frames_on_owner_thread_and_ignores_sink_failure():
    bridge = _FrameBridge()
    frames = []

    def failing_sink(frame):
        frames.append(frame)
        raise RuntimeError("disconnected stream")

    runner = SimulationRunner(
        _scene(),
        FixedTimeAlgorithm(),
        bridge=bridge,
        frame_interval_seconds=0.0,
    )

    runner.run(3, frame_sink=failing_sink)

    assert bridge.capture_calls == 3
    assert [frame.sequence for frame in frames] == [1, 2, 3]
    assert len(set(bridge.capture_threads)) == 1


def test_runner_skips_capture_when_the_frame_slot_is_unread():
    bridge = _FrameBridge()
    publisher = FramePublisher()
    runner = SimulationRunner(
        _scene(),
        FixedTimeAlgorithm(),
        bridge=bridge,
        frame_interval_seconds=0.0,
    )

    runner.run(
        3,
        frame_sink=publisher.publish,
        frame_ready=lambda: publisher.can_capture("runner"),
    )

    assert bridge.capture_calls == 1
    assert publisher.latest("runner").sequence == 1


def test_runner_suppresses_frame_event_when_frame_sink_rejects_record():
    bridge = _FrameBridge()
    events = []
    runner = SimulationRunner(
        _scene(),
        FixedTimeAlgorithm(),
        bridge=bridge,
        event_sink=events.append,
        frame_interval_seconds=0.0,
    )

    runner.run(1, frame_sink=lambda _record: False)

    assert not any(event["type"] == "frame" for event in events)


def test_runner_publishes_status_metrics_and_terminal_events():
    events = []
    runner = SimulationRunner(
        _scene(),
        FixedTimeAlgorithm(),
        bridge=MockBridge(),
        event_sink=events.append,
    )

    runner.run(2)

    assert {event["type"] for event in events} >= {
        "status",
        "metrics",
        "terminal",
    }
    assert all(event["run_id"] for event in events)
