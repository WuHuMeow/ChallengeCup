"""Shared SUMO validation result and execution primitives."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from defusedxml import ElementTree as ET


@dataclass(frozen=True)
class ValidationResult:
    config: Path
    ok: bool
    returncode: int
    elapsed_seconds: float
    warnings: list[str]
    errors: list[str]
    output_dir: Path


def _has_queue_output(config: Path) -> bool:
    try:
        root = ET.parse(config).getroot()
    except (OSError, ET.ParseError):
        return False
    return any(node.tag == "queue-output" for node in root.iter())


def run_sumo_validation(
    config: Path, end: int, output_dir: Path
) -> ValidationResult:
    """Run one SUMO configuration and classify diagnostic lines."""
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    command = [
        "sumo",
        "-c",
        str(config),
        "--no-step-log",
        "true",
        "-e",
        str(end),
        "--tripinfo-output",
        (output_dir / "tripinfo.xml").resolve().as_posix(),
        "--summary-output",
        (output_dir / "stats.xml").resolve().as_posix(),
        "--fcd-output",
        (output_dir / "traj.xml").resolve().as_posix(),
    ]
    if _has_queue_output(config):
        command.extend(
            ["--queue-output", (output_dir / "queues.xml").resolve().as_posix()]
        )
    completed = subprocess.run(command, capture_output=True, text=True)
    lines = completed.stderr.splitlines()
    warnings = [line for line in lines if line.startswith("Warning:")]
    errors = [line for line in lines if line.startswith("Error:")]
    return ValidationResult(
        config=config,
        ok=completed.returncode == 0 and not errors,
        returncode=completed.returncode,
        elapsed_seconds=time.perf_counter() - started,
        warnings=warnings,
        errors=errors,
        output_dir=output_dir,
    )
