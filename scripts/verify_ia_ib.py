"""PDF-aligned IA/IB acceptance checks with pass/fail/not_run truthfulness."""

from __future__ import annotations

import argparse
import csv
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

from core.run_models import RunRequest, RunStatus  # noqa: E402
from engine.run_service import RunService  # noqa: E402
from scripts.run_pdf_matrix import run_pdf_matrix  # noqa: E402
from scripts.stress_memory import parse_stress_args, run_stress  # noqa: E402
from scripts.validation_common import run_sumo_validation  # noqa: E402
from visualization.report import generate_matrix_figures  # noqa: E402


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
    *,
    status: str | None = None,
) -> CheckResult:
    resolved = status or ("pass" if not errors else "fail")
    if resolved not in {"pass", "fail", "not_run"}:
        raise ValueError(f"unknown check status: {resolved}")
    return CheckResult(
        name,
        resolved,
        time.perf_counter() - started,
        command,
        warnings,
        errors,
    )


def _not_run(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "not_run", 0.0, "not run", [detail], [])


def verify_data_integrity(_: Path) -> CheckResult:
    started = time.perf_counter()
    errors: list[str] = []
    data_root = ROOT / "data" / "intersection_data"
    for intersection in range(1, 21):
        root = data_root / str(intersection)
        files = list(root.rglob("*")) if root.exists() else []
        expected = [
            f"demo_{intersection}.net.xml",
            f"demo_{intersection}.rou.xml",
            f"demo_{intersection}.flow.xml",
            f"demo_{intersection}.sumocfg",
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


def _verify_configs(
    name: str,
    config_root: Path,
    end: int,
    output_root: Path,
) -> CheckResult:
    started = time.perf_counter()
    warnings: list[str] = []
    errors: list[str] = []
    for intersection in range(1, 21):
        config = config_root / f"demo_{intersection}.sumocfg"
        if config_root.name == "intersection_data":
            config = (
                config_root
                / str(intersection)
                / "sumo工程"
                / f"demo_{intersection}.sumocfg"
            )
        if not config.exists():
            errors.append(f"missing config: {config}")
            continue
        result = run_sumo_validation(
            config,
            end=end,
            output_dir=output_root / name / str(intersection),
        )
        warnings.extend(
            f"intersection {intersection}: {item}" for item in result.warnings
        )
        errors.extend(
            f"intersection {intersection}: {item}" for item in result.errors
        )
        if not result.ok and not result.errors:
            errors.append(f"intersection {intersection}: SUMO exit {result.returncode}")
    command = (
        f"sumo -c <{config_root}/demo_N.sumocfg> --no-step-log true -e {end} "
        f"--tripinfo-output <{output_root}/{name}/N/tripinfo.xml> "
        f"--summary-output <{output_root}/{name}/N/stats.xml> "
        f"--fcd-output <{output_root}/{name}/N/traj.xml>"
    )
    return _result(name, started, command, warnings, errors)


def verify_original_configs(
    verification_root: Path,
    output_root: Path | None = None,
) -> CheckResult:
    return _verify_configs(
        "original_100",
        ROOT / "data" / "intersection_data",
        100,
        output_root or verification_root,
    )


def verify_enhanced_configs(
    verification_root: Path,
    output_root: Path | None = None,
) -> CheckResult:
    return _verify_configs(
        "enhanced_100",
        ROOT / "engine" / "configs",
        100,
        output_root or verification_root,
    )


def verify_enhanced_full(
    verification_root: Path,
    output_root: Path | None = None,
) -> CheckResult:
    return _verify_configs(
        "enhanced_3600",
        ROOT / "engine" / "configs",
        3600,
        output_root or verification_root,
    )


def _pytest_check(name: str, files: list[str]) -> CheckResult:
    started = time.perf_counter()
    command = [
        sys.executable,
        "-m",
        "pytest",
        *files,
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    errors = []
    if completed.returncode:
        errors.append(completed.stdout.strip())
        if completed.stderr.strip():
            errors.append(completed.stderr.strip())
    return _result(
        name,
        started,
        " ".join(str(part) for part in command),
        [],
        errors,
    )


def verify_variant_contracts(_: Path) -> CheckResult:
    return _pytest_check(
        "variant_contracts",
        ["tests/test_variants.py", "tests/test_scenes.py"],
    )


def verify_runtime_contracts(_: Path) -> CheckResult:
    return _pytest_check(
        "runtime_contracts",
        [
            "tests/test_run_service.py",
            "tests/test_events.py",
            "tests/test_resilience.py",
            "tests/test_runner_channel.py",
        ],
    )


def verify_api_contracts(_: Path) -> CheckResult:
    return _pytest_check(
        "api_contracts",
        ["tests/test_api.py", "tests/test_api_contract.py"],
    )


def verify_ca_mp_smoke(verification_root: Path) -> CheckResult:
    started = time.perf_counter()
    errors = []
    service = RunService(output_root=verification_root / "ca_mp_smoke")
    try:
        result = service.run_sync(
            RunRequest(
                "1",
                "ca_maxpressure",
                steps=100,
                flow_multiplier=1.5,
                seed=42,
            )
        )
    finally:
        service.shutdown()
    if result.status is not RunStatus.COMPLETED:
        errors.append(f"{result.status.value}: {result.reason}")
    if not (result.run_dir / "summary.json").exists():
        errors.append("summary.json missing")
    if (result.run_dir / "events.csv").exists():
        with (result.run_dir / "events.csv").open(
            newline="",
            encoding="utf-8",
        ) as source:
            rejected = [
                row for row in csv.DictReader(source)
                if row["type"] == "action_rejected"
            ]
        if rejected:
            errors.append(f"{len(rejected)} rejected control actions")
    return _result(
        "ca_mp_smoke",
        started,
        "RunService(RunRequest('1','ca_maxpressure',steps=100,flow=1.5))",
        [],
        errors,
    )


def verify_exact_metrics(verification_root: Path) -> CheckResult:
    started = time.perf_counter()
    errors = []
    service = RunService(output_root=verification_root / "exact_metrics")
    try:
        result = service.run_sync(
            RunRequest("1", "fixed_time", steps=100, seed=42)
        )
    finally:
        service.shutdown()
    metrics = (result.summary or {}).get("metrics", {})
    for field in (
        "avg_travel_time",
        "avg_delay",
        "throughput",
        "total_stops",
        "fuel_consumption",
    ):
        if metrics.get(field) is None:
            errors.append(f"exact metric missing: {field}")
    return _result(
        "exact_metrics",
        started,
        "fixed_time 100-step run; parse tripinfo.xml -> summary.json",
        [],
        errors,
    )


def verify_figure_contracts(verification_root: Path) -> CheckResult:
    started = time.perf_counter()
    contract = _pytest_check(
        "figure_contracts",
        ["tests/test_visualization.py"],
    )
    if contract.status == "fail":
        return contract
    errors = []
    output = verification_root / "figures"
    try:
        figures = generate_matrix_figures(verification_root, output)
        if not figures or any(path.stat().st_size <= 1000 for path in figures):
            errors.append("figure output is empty or too small")
        manifest = json.loads(
            (output / "manifest.json").read_text(encoding="utf-8")
        )
        for item in manifest["figures"]:
            for source in item["sources"]:
                if not Path(source).exists():
                    errors.append(f"missing figure source: {source}")
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    return _result(
        "figure_contracts",
        started,
        "pytest tests/test_visualization.py; python -m visualization.report",
        [],
        errors,
    )


def verify_matrix(verification_root: Path, quick: bool = False) -> CheckResult:
    started = time.perf_counter()
    intersections = ("1", "11", "16") if quick else None
    steps = 100 if quick else 36000
    results = run_pdf_matrix(
        verification_root / "matrix",
        steps=steps,
        resume=True,
        intersections=intersections,
    )
    expected = 54 if quick else 360
    errors = []
    if len(results) != expected:
        errors.append(f"expected {expected} rows, got {len(results)}")
    failed = [
        result
        for result in results
        if result.status is not RunStatus.COMPLETED
    ]
    if failed:
        errors.extend(
            f"{result.run_id}: {result.status.value}: {result.reason}"
            for result in failed
        )
    return _result(
        "matrix",
        started,
        (
            "python scripts/run_pdf_matrix.py "
            f"{'--quick ' if quick else ''}--output-root "
            f"{verification_root / 'matrix'}"
        ),
        [],
        errors,
    )


def verify_stress_runs(
    verification_root: Path,
    quick: bool = False,
) -> CheckResult:
    started = time.perf_counter()
    steps = 100 if quick else 3600
    args = parse_stress_args([
        "--algorithm",
        "actuated",
        "--intersections",
        "1",
        "11",
        "16",
        "--steps",
        str(steps),
        "--flow-multiplier",
        "1.5",
        "--output-root",
        str(verification_root / "stress"),
        "--max-python-mib",
        "1024",
    ])
    records = run_stress(args)
    errors = [
        f"intersection {item['intersection']}: {item['error']}"
        for item in records
        if item["exit_status"]
    ]
    return _result(
        "stress_runs",
        started,
        "python scripts/stress_memory.py --intersections 1 11 16",
        [],
        errors,
    )


def verify_baseline_runs(
    verification_root: Path,
    steps: int = 3600,
) -> CheckResult:
    """Deprecated compatibility wrapper; runtime checks supersede it."""
    return verify_stress_runs(verification_root, quick=steps <= 100)


def verify_docker_static(_: Path) -> CheckResult:
    return _pytest_check("docker_static", ["tests/test_docker_static.py"])


def verify_docker(verification_root: Path) -> CheckResult:
    started = time.perf_counter()
    static = verify_docker_static(verification_root)
    if static.status == "fail":
        return _result(
            "docker",
            started,
            static.command,
            static.warnings,
            static.errors,
        )
    docker = shutil.which("docker")
    if docker is None:
        return _result(
            "docker",
            started,
            static.command,
            ["Docker unavailable; live build/run/save/load not run"],
            [],
            status="not_run",
        )
    verification_root.mkdir(parents=True, exist_ok=True)
    image_tar = verification_root / "ca-mp-ia-ib.tar"
    volume = f"{(ROOT / 'output').resolve()}:/app/output"
    commands = [
        [docker, "build", "-t", "ca-mp:ia-ib", "-f", "docker/Dockerfile", "."],
        [docker, "run", "--rm", "-v", volume, "ca-mp:ia-ib"],
        [docker, "save", "ca-mp:ia-ib", "-o", str(image_tar)],
        [docker, "load", "-i", str(image_tar)],
        [docker, "run", "--rm", "ca-mp:ia-ib"],
    ]
    errors = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            errors.append(
                completed.stderr.strip()
                or f"command failed ({completed.returncode}): {command}"
            )
            break
    return _result(
        "docker",
        started,
        "; ".join(" ".join(command) for command in commands),
        [],
        errors,
    )


checks: list[tuple[str, Callable[..., CheckResult]]] = [
    ("data_integrity", verify_data_integrity),
    ("original_100", verify_original_configs),
    ("enhanced_100", verify_enhanced_configs),
    ("enhanced_3600", verify_enhanced_full),
    ("variant_contracts", verify_variant_contracts),
    ("runtime_contracts", verify_runtime_contracts),
    ("api_contracts", verify_api_contracts),
    ("ca_mp_smoke", verify_ca_mp_smoke),
    ("exact_metrics", verify_exact_metrics),
    ("figure_contracts", verify_figure_contracts),
    ("matrix", verify_matrix),
    ("stress_runs", verify_stress_runs),
    ("docker", verify_docker),
]


def docker_live_status(results: list[CheckResult]) -> str:
    docker = next(
        (item for item in results if item.name in {"docker", "docker_static"}),
        None,
    )
    if docker is None:
        return "not run: Docker check missing"
    if docker.status == "not_run" or any(
        "Docker unavailable" in value for value in docker.warnings
    ):
        return "not run: Docker unavailable"
    return "fail" if docker.status == "fail" else "pass"


def render_markdown(
    results: list[CheckResult],
    docker_status: str,
) -> str:
    lines = [
        "# IA/IB Final Verification",
        "",
        "| Check | Status | Seconds |",
        "|---|---:|---:|",
    ]
    lines.extend(
        f"| {item.name} | {item.status} | {item.duration_seconds:.2f} |"
        for item in results
    )
    lines.extend(["", "## Docker", "", f"live validation: {docker_status}"])
    for item in results:
        lines.extend(["", f"## {item.name}", "", f"Command: `{item.command}`"])
        lines.extend(f"- warning: {value}" for value in item.warnings)
        lines.extend(f"- error: {value}" for value in item.errors)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IA/IB acceptance verification")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "output" / "verification",
    )
    args = parser.parse_args(argv)
    args.output_root.mkdir(parents=True, exist_ok=True)

    results = [
        verify_data_integrity(args.output_root),
        verify_original_configs(args.output_root, args.output_root),
        verify_enhanced_configs(args.output_root, args.output_root),
        (
            _not_run("enhanced_3600", "quick mode")
            if args.quick
            else verify_enhanced_full(args.output_root, args.output_root)
        ),
        verify_variant_contracts(args.output_root),
        verify_runtime_contracts(args.output_root),
        verify_api_contracts(args.output_root),
        verify_ca_mp_smoke(args.output_root),
        verify_exact_metrics(args.output_root),
        verify_figure_contracts(args.output_root),
        verify_matrix(args.output_root, quick=args.quick),
        verify_stress_runs(args.output_root, quick=args.quick),
        verify_docker(args.output_root),
    ]
    (args.output_root / "verification.json").write_text(
        json.dumps(
            [asdict(item) for item in results],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report = ROOT / "docs" / "reports" / "ia-ib-final-verification.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        render_markdown(results, docker_live_status(results)),
        encoding="utf-8",
    )
    return 1 if any(item.status == "fail" for item in results) else 0


if __name__ == "__main__":
    sys.exit(main())
