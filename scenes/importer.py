"""Copy validated SUMO inputs into a standalone destination package."""

from __future__ import annotations

import shutil
import json
from pathlib import Path

from scenes.models import SceneManifest
from scenes.validator import SceneValidationError, SceneValidator


class SceneImporter:
    """Import only scenes whose structural preflight has passed."""

    def __init__(self, repository_root: Path | str | None = None) -> None:
        self.validator = SceneValidator(repository_root=repository_root)

    def import_scene(self, source_root: Path, destination_root: Path) -> SceneManifest:
        manifest = self.validator.validate(source_root)
        if manifest.validation_status != "pass":
            detail = "; ".join(manifest.warnings) or "scene validation failed"
            raise SceneValidationError(detail)

        source = Path(source_root).resolve()
        destination = Path(destination_root).resolve() / manifest.scene_id
        if source == destination or source in destination.parents:
            raise SceneValidationError("destination must not be inside source_root")
        if destination.exists():
            raise FileExistsError(f"scene package already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(source, destination)
            (destination / "manifest.json").write_text(
                json.dumps(
                    {
                        "scene_id": manifest.scene_id,
                        "source_files": dict(manifest.source_files),
                        "sha256": dict(manifest.sha256),
                        "step_length": manifest.step_length,
                        "tls_ids": list(manifest.tls_ids),
                        "lane_ids": list(manifest.lane_ids),
                        "movement_count": manifest.movement_count,
                        "validation_status": manifest.validation_status,
                        "warnings": list(manifest.warnings),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            if destination.exists():
                shutil.rmtree(destination)
            raise
        return manifest
