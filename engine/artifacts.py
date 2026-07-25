"""Run-scoped output paths and metadata for simulation artifacts."""

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class RunArtifacts:
    """Stable paths for one isolated intersection/algorithm run."""

    run_dir: Path
    intersection_id: str
    algorithm: str
    flow_multiplier: float
    seed: int

    @classmethod
    def create(
        cls,
        root: Path,
        intersection_id: str,
        algorithm: str,
        flow_multiplier: float,
        seed: int,
    ) -> "RunArtifacts":
        run_dir = (
            Path(root)
            / f"i{intersection_id}"
            / algorithm
            / f"x{flow_multiplier:g}"
            / f"s{seed}"
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        return cls(run_dir, intersection_id, algorithm, flow_multiplier, seed)

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
    def metadata(self) -> Path:
        return self.run_dir / "run_metadata.json"

    def write_metadata(
        self,
        status: str,
        reason: str,
        generated_files: list[Path],
        *,
        started_at: str,
        ended_at: str,
        sumo_version: str,
    ) -> None:
        """Atomically replace run metadata with the current terminal state."""
        payload = {
            "intersection_id": self.intersection_id,
            "algorithm": self.algorithm,
            "flow_multiplier": self.flow_multiplier,
            "seed": self.seed,
            "status": status,
            "reason": reason,
            "started_at": started_at,
            "ended_at": ended_at,
            "sumo_version": sumo_version,
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
