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
        expected_run_id: str | None = None,
        accepted_payload_versions: Iterable[str] | None = None,
    ) -> None:
        self.delay_seconds = max(0.0, float(
            delay_seconds if delay_steps is None else delay_steps
        ))
        self.allowed_directions = (
            None if allowed_directions is None else frozenset(allowed_directions)
        )
        self._buffer: Deque[EdgeMessage] = deque()
        self.events: list[EdgeChannelEvent] = []
        self.expected_run_id = expected_run_id
        self.accepted_payload_versions = (
            None
            if accepted_payload_versions is None
            else frozenset(accepted_payload_versions)
        )

    def bind_contract(
        self, expected_run_id: str, accepted_payload_versions: Iterable[str]
    ) -> None:
        """Bind this channel to the active Runner and supported schema versions."""
        versions = frozenset(accepted_payload_versions)
        if self.expected_run_id not in (None, expected_run_id):
            raise ValueError("EdgeChannel already bound to a different run")
        if self.accepted_payload_versions not in (None, versions):
            raise ValueError("EdgeChannel already bound to different payload versions")
        self.expected_run_id = expected_run_id
        self.accepted_payload_versions = versions

    def send(self, message: EdgeMessage) -> None:
        if not isinstance(message, EdgeMessage):
            raise TypeError("EdgeChannel.send requires an EdgeMessage")
        if message.simulation_time != message.payload.timestamp:
            self.events.append(EdgeChannelEvent(
                "message_rejected",
                "payload_timestamp_mismatch",
                message.simulation_time,
            ))
            return
        if message.sent_at > message.simulation_time:
            self.events.append(EdgeChannelEvent(
                "message_rejected",
                "sent_at_after_simulation_time",
                message.simulation_time,
            ))
            return
        if message.expires_at <= message.sent_at:
            self.events.append(EdgeChannelEvent(
                "message_rejected",
                "expires_at_not_after_sent_at",
                message.simulation_time,
            ))
            return
        if message.expires_at <= message.simulation_time:
            self.events.append(EdgeChannelEvent(
                "message_rejected",
                "expires_at_not_after_simulation_time",
                message.simulation_time,
            ))
            return
        if self.expected_run_id is not None and message.run_id != self.expected_run_id:
            self.events.append(EdgeChannelEvent(
                "message_rejected",
                f"stale_run_id={message.run_id}",
                message.simulation_time,
            ))
            return
        if (
            self.accepted_payload_versions is not None
            and message.payload_version not in self.accepted_payload_versions
        ):
            self.events.append(EdgeChannelEvent(
                "message_rejected",
                f"incompatible_payload_version={message.payload_version}",
                message.simulation_time,
            ))
            return
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
