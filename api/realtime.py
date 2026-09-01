"""Thread-safe, non-blocking runtime event fan-out."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
import threading
from typing import Any


class RealtimeHub:
    """Publish run-scoped messages without owning a simulation resource."""

    def __init__(self, queue_size: int = 128) -> None:
        if isinstance(queue_size, bool) or queue_size <= 0:
            raise ValueError("queue_size must be an integer > 0")
        self._queue_size = int(queue_size)
        self._latest: dict[str, dict[str, Any]] = {}
        self._subscribers: dict[
            str, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]]
        ] = {}
        self._lock = threading.RLock()

    def publish(self, run_id: str, message: Mapping[str, object]) -> None:
        """Store and schedule one message for each current subscriber."""
        self._validate_run_id(run_id)
        with self._lock:
            stale = self._publish_locked(run_id, message)
        for loop, queue in stale:
            self._remove_subscriber(run_id, loop, queue)

    def publish_status(
        self,
        run_id: str,
        status: object,
        reason: str = "",
        simulation_time: float | None = None,
    ) -> None:
        """Publish a lifecycle status with an atomic latest-time snapshot."""
        self._validate_run_id(run_id)
        with self._lock:
            if simulation_time is None:
                latest = self._latest.get(run_id) or {}
                try:
                    simulation_time = float(latest.get("simulation_time", 0.0))
                except (TypeError, ValueError):
                    simulation_time = 0.0
            status_value = getattr(status, "value", status)
            stale = self._publish_locked(
                run_id,
                {
                    "type": "status",
                    "status": status_value,
                    "reason": reason,
                    "simulation_time": float(simulation_time),
                },
            )
        for loop, queue in stale:
            self._remove_subscriber(run_id, loop, queue)

    def latest(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            message = self._latest.get(run_id)
            return dict(message) if message is not None else None

    async def subscribe(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield the latest message first, then live messages until closed."""
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_id must be a non-empty string")
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self._queue_size
        )
        subscription = (loop, queue)
        with self._lock:
            self._subscribers.setdefault(run_id, set()).add(subscription)
            latest = self._latest.get(run_id)
        if latest is not None:
            queue.put_nowait(dict(latest))
        try:
            while True:
                yield await queue.get()
        finally:
            self._remove_subscriber(run_id, loop, queue)

    def close(self) -> None:
        with self._lock:
            self._subscribers.clear()
            self._latest.clear()

    def _offer(
        self,
        queue: asyncio.Queue[dict[str, Any]],
        payload: dict[str, Any],
    ) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(dict(payload))
        except asyncio.QueueFull:
            pass

    @staticmethod
    def _validate_run_id(run_id: str) -> None:
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_id must be a non-empty string")

    def _publish_locked(
        self,
        run_id: str,
        message: Mapping[str, object],
    ) -> list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]]:
        """Publish while the caller owns the hub lock."""
        payload = {"run_id": run_id, **dict(message)}
        payload["run_id"] = run_id
        self._latest[run_id] = payload
        stale: list[
            tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]
        ] = []
        subscribers = tuple(self._subscribers.get(run_id, ()))
        for loop, queue in subscribers:
            try:
                # Keep callback scheduling in the same critical section as
                # latest-state publication to preserve cross-thread order.
                loop.call_soon_threadsafe(self._offer, queue, payload)
            except RuntimeError:
                stale.append((loop, queue))
        return stale

    def _remove_subscriber(
        self,
        run_id: str,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> None:
        with self._lock:
            subscribers = self._subscribers.get(run_id)
            if subscribers is None:
                return
            subscribers.discard((loop, queue))
            if not subscribers:
                self._subscribers.pop(run_id, None)
