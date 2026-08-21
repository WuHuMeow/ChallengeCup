"""Run-scoped output paths and metadata for simulation artifacts."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from collections.abc import Mapping
from uuid import uuid4


RAW_SUMO_OUTPUT_NAMES = (
    "tripinfo.xml",
    "stats.xml",
    "traj.xml",
    "collisions.xml",
)
STABLE_OUTPUT_NAMES = (
    "metrics.csv",
    "simulation_log.csv",
    "events.csv",
    *RAW_SUMO_OUTPUT_NAMES,
    "summary.json",
)

_TERMINAL_STATUS_VALUES = frozenset({
    "completed",
    "stopped",
    "ended_early",
    "disconnected",
    "interrupted",
    "failed",
})
_STATUS_TRANSITIONS = {
    "queued": frozenset({"starting", "stopping", "failed"}),
    "starting": frozenset({"running", "stopping", "failed"}),
    "running": frozenset({
        "stopping",
        "completed",
        "ended_early",
        "disconnected",
        "interrupted",
        "failed",
    }),
    "stopping": _TERMINAL_STATUS_VALUES - {"stopped"},
}
_ARTIFACT_LOCK = threading.RLock()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class RunArtifacts:
    """Stable paths for one isolated intersection/algorithm run."""

    run_dir: Path
    intersection_id: str
    algorithm: str
    flow_multiplier: float
    seed: int
    run_id: str

    @staticmethod
    def required_output_names() -> tuple[str, ...]:
        """Return the canonical non-empty files for a completed run."""
        return STABLE_OUTPUT_NAMES

    @staticmethod
    def raw_sumo_output_names() -> tuple[str, ...]:
        """Return raw SUMO XML retained as stable provenance inputs."""
        return RAW_SUMO_OUTPUT_NAMES

    @classmethod
    def create(
        cls,
        root: Path,
        intersection_id: str,
        algorithm: str,
        flow_multiplier: float,
        seed: int,
        run_id: str | None = None,
    ) -> "RunArtifacts":
        root = Path(root)
        for _ in range(5):
            resolved_run_id = run_id or uuid4().hex[:12]
            run_dir = (
                root
                / f"i{intersection_id}"
                / algorithm
                / f"x{flow_multiplier:g}"
                / f"s{seed}"
                / resolved_run_id
            )
            try:
                run_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                if run_id is not None:
                    raise
                continue
            return cls(
                run_dir,
                intersection_id,
                algorithm,
                flow_multiplier,
                seed,
                resolved_run_id,
            )
        raise FileExistsError("could not allocate a collision-free run directory")

    @property
    def metrics(self) -> Path:
        return self.run_dir / "metrics.csv"

    @property
    def step_log(self) -> Path:
        return self.run_dir / "simulation_log.csv"

    @property
    def events(self) -> Path:
        return self.run_dir / "events.csv"

    @property
    def tripinfo(self) -> Path:
        return self.run_dir / "tripinfo.xml"

    @property
    def stats(self) -> Path:
        return self.run_dir / "stats.xml"

    @property
    def trajectory(self) -> Path:
        return self.run_dir / "traj.xml"

    @property
    def collisions(self) -> Path:
        return self.run_dir / "collisions.xml"

    @property
    def queues(self) -> Path:
        return self.run_dir / "queues.xml"

    @property
    def metadata(self) -> Path:
        return self.run_dir / "run_metadata.json"

    @property
    def manifest(self) -> Path:
        return self.run_dir / "manifest.json"

    @property
    def status(self) -> Path:
        return self.run_dir / "status.json"

    @property
    def summary(self) -> Path:
        return self.run_dir / "summary.json"

    @property
    def figures(self) -> Path:
        return self.run_dir / "figures"

    def write_manifest(self, payload: Mapping[str, object]) -> None:
        """Atomically merge immutable run identity with resolved runtime facts."""
        with _ARTIFACT_LOCK:
            existing: dict[str, object] = {}
            if self.manifest.exists():
                existing = json.loads(self.manifest.read_text(encoding="utf-8"))
            merged = {
                **existing,
                **dict(payload),
                "run_id": self.run_id,
                "intersection_id": self.intersection_id,
                "algorithm": self.algorithm,
                "flow_multiplier": self.flow_multiplier,
                "seed": self.seed,
            }
            _atomic_json(self.manifest, merged)

    def write_status(
        self,
        status: str,
        reason: str,
        *,
        started_at: str | None = None,
        ended_at: str | None = None,
    ) -> None:
        """Atomically advance status while refusing terminal overwrites."""
        now = datetime.now(timezone.utc).isoformat()
        with _ARTIFACT_LOCK:
            existing: dict[str, object] = {}
            if self.status.exists():
                existing = json.loads(self.status.read_text(encoding="utf-8"))
                current = str(existing.get("status", ""))
                if current in _TERMINAL_STATUS_VALUES:
                    if current == status:
                        return
                    raise ValueError(
                        f"run {self.run_id} status is terminal ({current}); "
                        f"cannot write {status}"
                    )
                if current and status != current and status not in _STATUS_TRANSITIONS.get(
                    current, frozenset()
                ):
                    raise ValueError(f"invalid artifact status transition {current} -> {status}")
            payload = {
                "run_id": self.run_id,
                "status": status,
                "reason": reason,
                "updated_at": now,
                "started_at": started_at or existing.get("started_at"),
                "ended_at": ended_at or existing.get("ended_at"),
            }
            if status == "running" and payload["started_at"] is None:
                payload["started_at"] = now
            if status in _TERMINAL_STATUS_VALUES:
                payload["ended_at"] = now
            _atomic_json(self.status, payload)

    def write_metadata(
        self,
        status: str,
        reason: str,
        generated_files: list[Path],
        *,
        started_at: str,
        ended_at: str,
        sumo_version: str,
        requested_steps: int | None = None,
        final_simulation_time: float | None = None,
        step_length: float | None = None,
        configured_end_time: float | None = None,
        movement_capacity_inputs: dict[str, float] | None = None,
        algorithm_manifest: dict[str, object] | None = None,
        requested_seconds: float | None = None,
        warmup_seconds: float | None = None,
        sumo_pid: int | None = None,
    ) -> None:
        """Atomically replace run metadata with the current terminal state."""
        payload = {
            "run_id": self.run_id,
            "intersection_id": self.intersection_id,
            "algorithm": self.algorithm,
            "flow_multiplier": self.flow_multiplier,
            "seed": self.seed,
            "status": status,
            "reason": reason,
            "started_at": started_at,
            "ended_at": ended_at,
            "sumo_version": sumo_version,
            "requested_steps": requested_steps,
            "requested_seconds": requested_seconds,
            "warmup_seconds": warmup_seconds,
            "final_simulation_time": final_simulation_time,
            "step_length": step_length,
            "configured_end_time": configured_end_time,
            "movement_capacity_inputs": movement_capacity_inputs,
            "algorithm_manifest": algorithm_manifest,
            "sumo_pid": sumo_pid,
            "generated_files": [
                Path(path).name for path in generated_files if Path(path).exists()
            ],
        }
        with _ARTIFACT_LOCK:
            if self.status.exists():
                status_payload = json.loads(self.status.read_text(encoding="utf-8"))
                current_status = str(status_payload.get("status", ""))
                if current_status in _TERMINAL_STATUS_VALUES and current_status != status:
                    raise ValueError(
                        f"run {self.run_id} status is terminal ({current_status}); "
                        f"cannot write metadata status {status}"
                    )
            if self.metadata.exists():
                existing = json.loads(self.metadata.read_text(encoding="utf-8"))
                current = str(existing.get("status", ""))
                if current in _TERMINAL_STATUS_VALUES and current != status:
                    raise ValueError(
                        f"run {self.run_id} metadata is terminal ({current}); "
                        f"cannot write {status}"
                    )
            _atomic_json(self.metadata, payload)
        self.write_status(
            status,
            reason,
            started_at=started_at,
            ended_at=ended_at,
        )
