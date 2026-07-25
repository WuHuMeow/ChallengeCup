"""Acceptance checks for IA/IB data, SUMO configurations, and pressure runs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.runner import parse_args, run_single  # noqa: E402
from scripts.stress_memory import parse_stress_args, run_stress  # noqa: E402
from scripts.validation_common import run_sumo_validation  # noqa: E402


@dataclass
class CheckResult:
    name: str
    status: str
    duration_seconds: float
    command: str
    warnings: list[str]
    errors: list[str]


def _result(
    name: str,
    started: float,
    command: str,
    warnings: list[str],
    errors: list[str],
) -> CheckResult:
    return CheckResult(
        name,
        "pass" if not errors else "fail",
        time.perf_counter() - started,
        command,
        warnings,
        errors,
    )


def verify_data_integrity(_: Path) -> CheckResult:
    started = time.perf_counter()
    errors: list[str] = []
    data_root = ROOT / "data" / "intersection_data"
    for intersection in range(1, 21):
        root = data_root / str(intersection)
        files = list(root.rglob("*")) if root.exists() else []
        expected = [
            f"demo_{intersection}.net.xml", f"demo_{intersection}.rou.xml",
            f"demo_{intersection}.flow.xml", f"demo_{intersection}.sumocfg",
            f"demo_{intersection}.turn.xml",
        ]
        present = {path.name for path in files if path.is_file()}
        errors.extend(
            f"intersection {intersection} missing {name}"
            for name in expected
            if name not in present
        )
        if not any(path.suffix.lower() == ".xlsx" for path in files):
            errors.append(f"intersection {intersection} missing timing workbook")
    return _result("data_integrity", started, "static data inventory", [], errors)


def _verify_configs(name: str, config_root: Path, end: int, output_root: Path) -> CheckResult:
    started = time.perf_counter()
    warnings: list[str] = []
    errors: list[str] = []
    for intersection in range(1, 21):
        config = config_root / f"demo_{intersection}.sumocfg"
        if config_root.name == "intersection_data":
            config = config_root / str(intersection) / "sumo工程" / f"demo_{intersection}.sumocfg"
        if not config.exists():
            errors.append(f"missing config: {config}")
            continue
        result = run_sumo_validation(
            config,
            end=end,
            output_dir=output_root / name / str(intersection),
        )
        warnings.extend(f"intersection {intersection}: {item}" for item in result.warnings)
        errors.extend(f"intersection {intersection}: {item}" for item in result.errors)
        if not result.ok and not result.errors:
            errors.append(f"intersection {intersection}: SUMO exit {result.returncode}")
    command = (
        f"sumo -c <{config_root}/demo_N.sumocfg> --no-step-log true -e {end} "
        f"--tripinfo-output <{output_root}/{name}/N/tripinfo.xml> "
        f"--summary-output <{output_root}/{name}/N/stats.xml> "
        f"--fcd-output <{output_root}/{name}/N/traj.xml>"
    )
    return _result(
        name,
        started,
        command,
        warnings,
        errors,
    )


def verify_original_configs(
    verification_root: Path, output_root: Path | None = None
) -> CheckResult:
    out = output_root or verification_root
    return _verify_configs("original_100", ROOT / "data" / "intersection_data", 100, out)


def verify_enhanced_configs(
    verification_root: Path, output_root: Path | None = None
) -> CheckResult:
    out = output_root or verification_root
    return _verify_configs("enhanced_100", ROOT / "engine" / "configs", 100, out)


def verify_enhanced_full(verification_root: Path, output_root: Path | None = None) -> CheckResult:
    out = output_root or verification_root
    return _verify_configs("enhanced_3600", ROOT / "engine" / "configs", 3600, out)


def _run_experiment_set(name: str, verification_root: Path, steps: int) -> CheckResult:
    started = time.perf_counter()
    errors: list[str] = []
    out = verification_root / name
    for intersection in ("1", "11", "16"):
        try:
            args = parse_args([
                "--intersection", intersection, "--steps", str(steps),
                "--algorithm", "actuated", "--flow-multiplier", "1.0",
                "--output-dir", str(out), "--seed", "42",
            ])
            run_single(args)
        except Exception as exc:
            errors.append(f"intersection {intersection}: {type(exc).__name__}: {exc}")
    command = (
        "python -m experiments.runner --intersection <1|11|16> "
        f"--algorithm actuated --steps {steps} --flow-multiplier 1.0 "
        f"--seed 42 --output-dir {out}"
    )
    return _result(
        name,
        started,
        command,
        [],
        errors,
    )


def verify_baseline_runs(verification_root: Path, steps: int = 3600) -> CheckResult:
    return _run_experiment_set("baseline_runs", verification_root, steps)


def verify_stress_runs(verification_root: Path, quick: bool = False) -> CheckResult:
    started = time.perf_counter()
    steps = 100 if quick else 3600
    args = parse_stress_args([
        "--algorithm", "actuated", "--intersections", "1", "11", "16",
        "--steps", str(steps), "--flow-multiplier", "1.5",
        "--output-root", str(verification_root / "stress"), "--max-python-mib", "1024",
    ])
    records = run_stress(args)
    errors = [
        f"intersection {item['intersection']}: {item['error']}"
        for item in records
        if item["exit_status"]
    ]
    command = (
        "python scripts/stress_memory.py --algorithm actuated "
        f"--intersections 1 11 16 --steps {steps} --flow-multiplier 1.5 "
        f"--output-root {verification_root / 'stress'} --max-python-mib 1024"
    )
    return _result("stress_runs", started, command, [], errors)


def verify_docker_static(verification_root: Path) -> CheckResult:
    started = time.perf_counter()
    errors: list[str] = []
    warnings: list[str] = []
    dockerfile = ROOT / "docker" / "Dockerfile"
    compose = ROOT / "docker-compose.yml"
    if not dockerfile.exists():
        errors.append(f"missing {dockerfile}")
    elif "sumo" not in dockerfile.read_text(encoding="utf-8", errors="ignore").lower():
        errors.append("Dockerfile does not reference SUMO")
    if not compose.exists():
        errors.append(f"missing {compose}")
    test_file = ROOT / "tests" / "test_docker_static.py"
    if not test_file.exists():
        test_file = ROOT / "tests" / "test_docker.py"
    if not test_file.exists():
        errors.append(f"missing Docker contract test: {test_file}")
    else:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-q"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            errors.append(completed.stderr.strip() or "Task 9 Docker tests failed")
    if shutil.which("docker") is None:
        warnings.append("live validation: Docker unavailable; not run")
    else:
        completed = subprocess.run(
            [
                "docker",
                "build",
                "-t",
                "ca-mp:ia-ib",
                "-f",
                "docker/Dockerfile",
                ".",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            errors.append(completed.stderr.strip() or "Docker build failed")
        else:
            run_result = subprocess.run(
                ["docker", "run", "--rm", "ca-mp:ia-ib", "1"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if run_result.returncode:
                errors.append(run_result.stderr.strip() or "Docker run failed")
            else:
                warnings.append("live validation: Docker build/run completed")
    return _result(
        "docker_static",
        started,
        "python -m pytest tests/test_docker_static.py -q; "
        "docker build -t ca-mp:ia-ib -f docker/Dockerfile .; "
        "docker run --rm ca-mp:ia-ib 1 (live commands conditional)",
        warnings,
        errors,
    )


# Public registry used by reports and downstream acceptance tooling.
checks: list[tuple[str, Callable[..., CheckResult]]] = [
    ("data_integrity", verify_data_integrity),
    ("original_100", verify_original_configs),
    ("enhanced_100", verify_enhanced_configs),
    ("enhanced_3600", verify_enhanced_full),
    ("baseline_runs", verify_baseline_runs),
    ("stress_runs", verify_stress_runs),
    ("docker_static", verify_docker_static),
]


def docker_live_status(results: list[CheckResult]) -> str:
    docker = next((item for item in results if item.name == "docker_static"), None)
    if docker is None:
        return "not run: Docker check missing"
    if any("Docker unavailable" in value for value in docker.warnings):
        return "not run: Docker unavailable"
    if docker.status == "fail":
        return "fail"
    return "pass"


def render_markdown(
    results: list[CheckResult], docker_status: str, ab_blockers: list[str]
) -> str:
    lines = ["# IA/IB Final Verification", "", "| Check | Status | Seconds |", "|---|---:|---:|"]
    lines.extend(
        f"| {item.name} | {item.status} | {item.duration_seconds:.2f} |"
        for item in results
    )
    lines.extend(["", "## Docker", "", f"live validation: {docker_status}"])
    lines.extend(
        ["", "## Cross-role blockers", ""]
        + [f"- AB blocker: {item}" for item in ab_blockers]
    )
    for item in results:
        lines.extend(["", f"## {item.name}", "", f"Command: `{item.command}`"])
        lines.extend(f"- warning: {value}" for value in item.warnings)
        lines.extend(f"- error: {value}" for value in item.errors)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IA/IB acceptance verification")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="skip enhanced 3600-step check and shorten runs",
    )
    parser.add_argument("--output-root", type=Path, default=ROOT / "output" / "verification")
    args = parser.parse_args(argv)
    args.output_root.mkdir(parents=True, exist_ok=True)
    results: list[CheckResult] = [verify_data_integrity(args.output_root)]
    results.append(verify_original_configs(args.output_root, args.output_root))
    results.append(verify_enhanced_configs(args.output_root, args.output_root))
    if not args.quick:
        results.append(verify_enhanced_full(args.output_root, args.output_root))
    results.append(verify_baseline_runs(args.output_root, 100 if args.quick else 3600))
    results.append(verify_stress_runs(args.output_root, args.quick))
    results.append(verify_docker_static(args.output_root))
    (args.output_root / "verification.json").write_text(
        json.dumps([asdict(item) for item in results], indent=2), encoding="utf-8"
    )
    report = ROOT / "docs" / "reports" / "ia-ib-final-verification.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        render_markdown(
            results,
            docker_live_status(results),
            ["CA-MP remains an AB blocker; no correctness claim made."],
        ),
        encoding="utf-8",
    )
    return 1 if any(item.status == "fail" for item in results) else 0


if __name__ == "__main__":
    sys.exit(main())
