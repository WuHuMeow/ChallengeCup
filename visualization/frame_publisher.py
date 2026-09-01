"""Bounded publication of the latest SUMO GUI frame per run."""

from __future__ import annotations

from dataclasses import dataclass
import threading


@dataclass(frozen=True)
class FrameRecord:
    run_id: str
    sequence: int
    simulation_time: float
    png: bytes
    captured_at: float


class FramePublisher:
    """Keep one immutable, newest frame for each active run."""

    def __init__(self) -> None:
        self._frames: dict[str, FrameRecord] = {}
        self._lock = threading.RLock()

    def publish(self, record: FrameRecord) -> bool:
        with self._lock:
            previous = self._frames.get(record.run_id)
            if previous is not None and record.sequence <= previous.sequence:
                return False
            self._frames[record.run_id] = record
            return True

    def latest(self, run_id: str) -> FrameRecord | None:
        with self._lock:
            return self._frames.get(run_id)

    def can_capture(self, run_id: str) -> bool:
        """Return whether the current frame has been consumed or is absent."""
        with self._lock:
            return run_id not in self._frames

    def consume(
        self,
        run_id: str,
        after_sequence: int | None = None,
    ) -> FrameRecord | None:
        """Release the capture slot and return only a client-newer frame."""
        with self._lock:
            record = self._frames.pop(run_id, None)
            if record is None:
                return None
            if after_sequence is not None and record.sequence <= after_sequence:
                return None
            return record

    def size(self, run_id: str) -> int:
        with self._lock:
            return int(run_id in self._frames)

    def clear(self, run_id: str) -> None:
        with self._lock:
            self._frames.pop(run_id, None)

    def clear_all(self) -> None:
        with self._lock:
            self._frames.clear()
