"""Run-scoped output paths and metadata for simulation artifacts."""

from dataclasses import dataclass
import json
from pathlib import Path
from uuid import uuid4


class CorruptStatusArtifactError(RuntimeError):
    """Raised when a run's status artifact exists but cannot be trusted."""


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
        """Return the canonical files required for a completed run.
        NOTE: tripinfo.xml/stats.xml/traj.xml are removed — they are used
        only to compute summary.json and can be 10+ MB each on 0.1s-step
        intersections, rapidly filling the disk during batch runs.
        """
        return (
            "metrics.csv",
            "simulation_log.csv",
            "events.csv",
            "tripinfo.xml",
            "stats.xml",
            "traj.xml",
            "collisions.xml",
            "summary.json",
        )

    @classmethod
    def evidence_required_output_names(cls) -> tuple[str, ...]:
        """Files that must exist (and hash) for strict evidence validation."""
        return (
            "manifest.json",
            "provenance.json",
            "status.json",
            "run_metadata.json",
            *cls.required_output_names(),
            "hashes.json",
        )

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
        resolved_run_id = run_id or uuid4().hex[:12]
        run_dir = (
            Path(root)
            / f"i{intersection_id}"
            / algorithm
            / f"x{flow_multiplier:g}"
            / f"s{seed}"
            / resolved_run_id
        )
        run_dir.mkdir(parents=True, exist_ok=False)
        return cls(
            run_dir,
            intersection_id,
            algorithm,
            flow_multiplier,
            seed,
            resolved_run_id,
        )

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
    def queues(self) -> Path:
        return self.run_dir / "queues.xml"

    @property
    def collisions(self) -> Path:
        return self.run_dir / "collisions.xml"

    @property
    def provenance(self) -> Path:
        return self.run_dir / "provenance.json"

    @property
    def hashes(self) -> Path:
        return self.run_dir / "hashes.json"

    @property
    def metadata(self) -> Path:
        return self.run_dir / "run_metadata.json"

    @property
    def status(self) -> Path:
        return self.run_dir / "status.json"

    @property
    def manifest(self) -> Path:
        return self.run_dir / "run_manifest.json"

    def write_manifest(self, payload: dict[str, object]) -> None:
        """Atomically write the run manifest with the derived timing record."""
        temporary = self.manifest.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.manifest)

    def read_status(self) -> dict[str, object]:
        """Load the persisted status payload, failing closed when corrupt."""
        try:
            payload = json.loads(self.status.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CorruptStatusArtifactError(
                f"status artifact is corrupt: {self.status}: {exc}"
            ) from exc
        if not isinstance(payload, dict) or "status" not in payload:
            raise CorruptStatusArtifactError(
                f"status artifact is missing required fields: {self.status}"
            )
        return payload

    def write_status(
        self,
        status: str,
        reason: str = "",
        **extra: object,
    ) -> None:
        """Atomically record the current lifecycle state for observers."""
        payload = {
            "run_id": self.run_id,
            "intersection_id": self.intersection_id,
            "algorithm": self.algorithm,
            "status": status,
            "reason": reason,
        }
        payload.update(extra)
        temporary = self.status.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.status)

    @property
    def summary(self) -> Path:
        return self.run_dir / "summary.json"

    @property
    def figures(self) -> Path:
        return self.run_dir / "figures"

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
        requested_seconds: float | None = None,
        warmup_seconds: float | None = None,
        derived_steps: int | None = None,
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
            "final_simulation_time": final_simulation_time,
            "step_length": step_length,
            "configured_end_time": configured_end_time,
            "requested_seconds": requested_seconds,
            "warmup_seconds": warmup_seconds,
            "derived_steps": derived_steps,
            "generated_files": [
                Path(path).name for path in generated_files if Path(path).exists()
            ],
        }
        temporary = self.metadata.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.metadata)
