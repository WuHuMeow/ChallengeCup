"""Thread-safe, monotonic lifecycle state for simulation runs."""

from __future__ import annotations

import threading

from core.run_models import RunResult, RunStatus
from engine.artifacts import RunArtifacts


TERMINAL_STATUSES = frozenset({
    RunStatus.COMPLETED,
    RunStatus.STOPPED,
    RunStatus.ENDED_EARLY,
    RunStatus.DISCONNECTED,
    RunStatus.INTERRUPTED,
    RunStatus.FAILED,
})

_ALLOWED_TRANSITIONS = {
    RunStatus.QUEUED: frozenset({
        RunStatus.STARTING,
        RunStatus.STOPPING,
        RunStatus.FAILED,
    }),
    RunStatus.STARTING: frozenset({
        RunStatus.RUNNING,
        RunStatus.STOPPING,
        RunStatus.FAILED,
    }),
    RunStatus.RUNNING: frozenset({
        RunStatus.STOPPING,
        RunStatus.COMPLETED,
        RunStatus.ENDED_EARLY,
        RunStatus.DISCONNECTED,
        RunStatus.INTERRUPTED,
        RunStatus.FAILED,
    }),
    RunStatus.STOPPING: frozenset({
        RunStatus.COMPLETED,
        RunStatus.ENDED_EARLY,
        RunStatus.DISCONNECTED,
        RunStatus.INTERRUPTED,
        RunStatus.FAILED,
    }),
}


class RunStateMachine:
    """Own run results and reject backward or terminal-overwriting updates."""

    def __init__(self) -> None:
        self._records: dict[str, RunResult] = {}
        self._artifacts: dict[str, RunArtifacts] = {}
        self._lock = threading.RLock()

    def register(
        self,
        result: RunResult,
        artifacts: RunArtifacts | None = None,
    ) -> RunResult:
        if result.status is not RunStatus.QUEUED:
            raise ValueError("new runs must be registered as queued")
        with self._lock:
            if result.run_id in self._records:
                raise ValueError(f"run already registered: {result.run_id}")
            self._records[result.run_id] = result
            if artifacts is not None:
                self._artifacts[result.run_id] = artifacts
                artifacts.write_status(result.status.value, result.reason)
            return result

    def get(self, run_id: str) -> RunResult | None:
        with self._lock:
            return self._records.get(run_id)

    def list(self) -> tuple[RunResult, ...]:
        """Return a stable snapshot of all known run states."""
        with self._lock:
            return tuple(self._records.values())

    def transition(
        self,
        run_id: str,
        new_status: RunStatus,
        reason: str,
        *,
        summary: dict[str, object] | None = None,
        persist_artifact: bool = True,
    ) -> RunResult:
        with self._lock:
            current = self._records.get(run_id)
            if current is None:
                raise KeyError(run_id)
            if current.status in TERMINAL_STATUSES:
                raise ValueError(
                    f"run {run_id} is terminal ({current.status.value}); "
                    f"cannot transition to {new_status.value}"
                )
            allowed = _ALLOWED_TRANSITIONS.get(current.status, frozenset())
            if new_status not in allowed:
                raise ValueError(
                    f"invalid run transition {current.status.value} -> {new_status.value}"
                )
            result = RunResult(
                run_id=current.run_id,
                status=new_status,
                reason=reason,
                run_dir=current.run_dir,
                summary=summary if summary is not None else current.summary,
                algorithm=current.algorithm,
            )
            artifacts = self._artifacts.get(run_id)
            if artifacts is not None and persist_artifact:
                artifacts.write_status(new_status.value, reason)
            self._records[run_id] = result
            return result
