"""Cloud-edge message envelope with simulation-time delay and rejection events."""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Deque, Iterable

from core.types import JointState


@dataclass(frozen=True)
class EdgeMessage:
    run_id: str
    simulation_time: float
    sent_at: float
    expires_at: float
    payload_version: str
    payload: JointState


@dataclass(frozen=True)
class EdgeChannelEvent:
    event_type: str
    detail: str
    simulation_time: float


class EdgeChannel:
    """Move only versioned, non-expired, direction-authorized edge messages."""

    def __init__(
        self,
        delay_seconds: float = 1.0,
        allowed_directions: Iterable[str] | None = None,
        *,
        delay_steps: int | None = None,
    ) -> None:
        self.delay_seconds = max(0.0, float(
            delay_seconds if delay_steps is None else delay_steps
        ))
        self.allowed_directions = (
            None if allowed_directions is None else frozenset(allowed_directions)
        )
        self._buffer: Deque[EdgeMessage] = deque()
        self.events: list[EdgeChannelEvent] = []

    def send(self, message: EdgeMessage) -> None:
        if not isinstance(message, EdgeMessage):
            raise TypeError("EdgeChannel.send requires an EdgeMessage")
        if self.allowed_directions is not None:
            directions = {
                queue.direction for queue in message.payload.queues
            } | set(message.payload.flows)
            forbidden = sorted(directions - self.allowed_directions)
            if forbidden:
                self.events.append(EdgeChannelEvent(
                    "message_rejected",
                    f"disallowed_direction={forbidden[0]}",
                    message.simulation_time,
                ))
                return
        self._buffer.append(message)

    def receive(self, now: float) -> EdgeMessage | None:
        while self._buffer:
            message = self._buffer[0]
            if now < message.simulation_time + self.delay_seconds:
                return None
            self._buffer.popleft()
            if now >= message.expires_at:
                self.events.append(EdgeChannelEvent(
                    "message_expired", "expired", now
                ))
                continue
            return message
        return None
