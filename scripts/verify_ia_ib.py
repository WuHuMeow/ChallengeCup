"""PDF-aligned IA/IB acceptance checks with pass/fail/not_run truthfulness."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field as dataclass_field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "docs" / "ia-ib-final-verification.md"
sys.path.insert(0, str(ROOT))

from core.run_models import RunRequest, RunStatus  # noqa: E402
from engine.run_service import RunService  # noqa: E402
from scripts.run_pdf_matrix import (  # noqa: E402
    build_pdf_matrix,
    is_complete,
    request_key,
    run_pdf_matrix,
)
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
    exit_code: int | None = None
    mode: str = "in_process"
    evidence_paths: list[str] = dataclass_field(default_factory=list)


def _result(
    name: str,
    started: float,
    command: str,
    warnings: list[str],
    errors: list[str],
    *,
    status: str | None = None,
    exit_code: int | None = None,
    mode: str = "in_process",
    evidence_paths: list[str] | None = None,
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
        exit_code,
        mode,
        list(evidence_paths or []),
    )


def _not_run(name: str, detail: str) -> CheckResult:
    return CheckResult(
        name,
        "not_run",
        0.0,
        "not run",
        [detail],
        [],
        exit_code=None,
        mode="not_run",
    )


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
    exit_codes: list[int] = []
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
        exit_codes.append(result.returncode)
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
    return _result(
        name,
        started,
        command,
        warnings,
        errors,
        exit_code=next((code for code in exit_codes if code), 0),
        mode="executed",
        evidence_paths=[str(output_root / name)],
    )


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
        if completed.stdout.strip():
            errors.append(completed.stdout.strip())
        if completed.stderr.strip():
            errors.append(completed.stderr.strip())
        if not errors:
            errors.append(f"process exited {completed.returncode} without output")
    return _result(
        name,
        started,
        " ".join(str(part) for part in command),
        [],
        errors,
        exit_code=completed.returncode,
        mode="executed",
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


def _matrix_request_identity(request: RunRequest) -> tuple[str, str, float, int, int]:
    return (
        str(request.intersection_id),
        str(request.algorithm),
        float(request.flow_multiplier),
        int(request.seed),
        int(request.steps),
    )


def _matrix_row_identity(row: dict[str, str]) -> tuple[str, str, float, int, int]:
    return (
        str(row["intersection_id"]),
        str(row["algorithm"]),
        float(row["flow_multiplier"]),
        int(row["seed"]),
        int(row["steps"]),
    )


def audit_matrix_csv(
    matrix_csv: Path,
    expected: int = 360,
    expected_requests: list[RunRequest] | None = None,
) -> CheckResult:
    """Audit an existing combined matrix without launching new SUMO runs."""
    started = time.perf_counter()
    errors = []
    try:
        rows = list(csv.DictReader(Path(matrix_csv).open(encoding="utf-8")))
    except OSError as exc:
        rows = []
        errors.append(str(exc))
    keys = set()
    for row in rows:
        try:
            keys.add(_matrix_row_identity(row))
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"invalid matrix identity: {exc}")
    if len(rows) != expected or len(keys) != expected:
        errors.append(
            f"matrix rows={len(rows)} unique={len(keys)} expected={expected}"
        )
    if expected_requests is not None:
        expected_keys = {
            _matrix_request_identity(request) for request in expected_requests
        }
        if keys != expected_keys:
            errors.append(
                "request set mismatch: "
                f"missing={len(expected_keys - keys)} "
                f"unexpected={len(keys - expected_keys)}"
            )
    for row in rows:
        run_id = row.get("run_id", "unknown")
        if row.get("status") != RunStatus.COMPLETED.value:
            errors.append(
                f"{run_id}: status={row.get('status')} reason={row.get('reason', '')}"
            )
            continue
        try:
            request = RunRequest(
                intersection_id=row["intersection_id"],
                algorithm=row["algorithm"],
                steps=int(row["steps"]),
                flow_multiplier=float(row["flow_multiplier"]),
                seed=int(row["seed"]),
            )
            run_dir = Path(row["run_dir"])
            if not run_dir.is_absolute():
                run_dir = ROOT / run_dir
            if not is_complete(run_dir, request):
                errors.append(f"{run_id}: incomplete or below requested horizon")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{run_id}: invalid matrix row: {exc}")
    return _result(
        "matrix",
        started,
        f"in-process audit of {matrix_csv}",
        [],
        errors,
        exit_code=None,
        mode="audited",
        evidence_paths=[str(matrix_csv)],
    )


def verify_matrix(
    verification_root: Path,
    quick: bool = False,
    matrix_csv: Path | None = None,
) -> CheckResult:
    started = time.perf_counter()
    intersections = ("1", "11", "16") if quick else None
    steps = 100 if quick else 36000
    expected = 54 if quick else 360
    matrix_root = verification_root / "matrix"
    requests = build_pdf_matrix(
        matrix_root,
        steps=steps,
        intersections=intersections,
    )
    if matrix_csv is not None:
        return audit_matrix_csv(
            matrix_csv,
            expected=expected,
            expected_requests=requests,
        )
    state_path = matrix_root / "matrix_state.json"
    state = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    reusable = 0
    for request in requests:
        run_id = state.get(request_key(request))
        if run_id is None:
            continue
        run_dir = (
            Path(request.output_root)
            / f"i{request.intersection_id}"
            / request.algorithm
            / f"x{request.flow_multiplier:g}"
            / f"s{request.seed}"
            / run_id
        )
        if is_complete(run_dir, request):
            reusable += 1
    results = run_pdf_matrix(
        matrix_root,
        steps=steps,
        resume=True,
        intersections=intersections,
    )
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
    for request, result in zip(requests, results):
        if (
            result.status is RunStatus.COMPLETED
            and not is_complete(result.run_dir, request)
        ):
            errors.append(
                f"{result.run_id}: incomplete or below requested horizon"
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
        mode="audited" if reusable == expected else "executed",
        evidence_paths=[
            str(matrix_root / "matrix.csv"),
            str(matrix_root / "matrix_state.json"),
        ],
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


def verify_automated_regression(verification_root: Path) -> CheckResult:
    """Run the repository-wide automated acceptance commands."""
    started = time.perf_counter()
    commands = [
        [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "algorithms",
            "api",
            "cloud",
            "core",
            "engine",
            "experiments",
            "ml",
            "scenes",
            "scripts",
            "visualization",
        ],
        [
            sys.executable,
            "-c",
            (
                "import algorithms, api, cloud, core, engine, experiments, "
                "ml, scenes, scripts, visualization"
            ),
        ],
        [
            sys.executable,
            "-m",
            "flake8",
            "algorithms",
            "api",
            "cloud",
            "core",
            "engine",
            "experiments",
            "scenes",
            "scripts",
            "visualization",
            "--max-line-length=100",
        ],
        ["git", "diff", "--check"],
    ]
    errors = []
    details = []
    exit_codes = []
    pycache = verification_root / "pycache"
    pycache.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["PYTHONPYCACHEPREFIX"] = str(pycache.resolve())
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        exit_codes.append(completed.returncode)
        command_text = " ".join(str(part) for part in command)
        details.append(f"{command_text} [exit={completed.returncode}]")
        if completed.returncode:
            output = "\n".join(
                value.strip()
                for value in (completed.stdout, completed.stderr)
                if value.strip()
            )
            errors.append(
                f"{command_text} exited {completed.returncode}"
                + (f":\n{output}" if output else "")
            )
    return _result(
        "automated_regression",
        started,
        "; ".join(details),
        [],
        errors,
        exit_code=next((code for code in exit_codes if code), 0),
        mode="executed",
        evidence_paths=[str(pycache)],
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
            exit_code=static.exit_code,
            mode="executed",
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
            exit_code=None,
            mode="not_run",
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
    exit_codes = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        exit_codes.append(completed.returncode)
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
        exit_code=next((code for code in exit_codes if code), 0),
        mode="executed",
        evidence_paths=[str(image_tar)] if image_tar.exists() else [],
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
    ("automated_regression", verify_automated_regression),
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


def repository_provenance() -> dict[str, object]:
    """Identify the checked source state without generated report churn."""
    excluded = (
        ":(exclude)docs/ia-ib-final-verification.md",
        ":(exclude)docs/reports/ia-ib-final-verification.md",
    )

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    commit_result = git("rev-parse", "HEAD")
    status_result = git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        ".",
        *excluded,
    )
    diff_result = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--", ".", *excluded],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    diff_bytes = diff_result.stdout or b""
    return {
        "commit": commit_result.stdout.strip() or "unknown",
        "dirty": bool(status_result.stdout.strip()),
        "diff_sha256": hashlib.sha256(diff_bytes).hexdigest(),
    }


def _result_status(results: list[CheckResult], name: str) -> str:
    item = next((candidate for candidate in results if candidate.name == name), None)
    return item.status if item is not None else "not_run"


def _local_sumo_status(results: list[CheckResult]) -> str:
    names = {
        "original_100",
        "enhanced_100",
        "enhanced_3600",
        "ca_mp_smoke",
        "exact_metrics",
        "figure_contracts",
        "matrix",
        "stress_runs",
    }
    selected = [item for item in results if item.name in names]
    if any(item.status == "fail" for item in selected):
        return "fail"
    if selected and all(item.status == "pass" for item in selected):
        return "pass"
    return "not_run"


def render_markdown(
    results: list[CheckResult],
    docker_status: str,
    *,
    provenance: dict[str, object] | None = None,
    second_machine_status: str = "not_run",
) -> str:
    provenance = provenance or repository_provenance()
    automated_status = _result_status(results, "automated_regression")
    repository_status = "pass" if automated_status == "pass" else automated_status
    docker_axis = _result_status(results, "docker")
    lines = [
        "# IA/IB Final Verification",
        "",
        "| Check | Status | Exit Code | Seconds |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {item.name} | {item.status} | "
        f"{item.exit_code if item.exit_code is not None else 'N/A'} | "
        f"{item.duration_seconds:.2f} |"
        for item in results
    )
    lines.extend(["", "## Docker", "", f"live validation: {docker_status}"])
    lines.extend([
        "",
        "## Repository provenance",
        "",
        f"- commit: `{provenance['commit']}`",
        f"- dirty: `{str(bool(provenance['dirty'])).lower()}`",
        f"- diff SHA-256: `{provenance['diff_sha256']}`",
        "",
        "## Evidence axes",
        "",
        f"- repository implementation: {repository_status}",
        f"- automated verification: {automated_status}",
        f"- local SUMO verification: {_local_sumo_status(results)}",
        f"- Docker live verification: {docker_axis}",
        f"- second-machine reproduction: {second_machine_status}",
    ])
    for item in results:
        exit_code = item.exit_code if item.exit_code is not None else "N/A"
        lines.extend([
            "",
            f"## {item.name}",
            "",
            f"Command: `{item.command}`",
            f"Exit code: `{exit_code}`",
            f"Mode: `{item.mode}`",
        ])
        lines.extend(f"- evidence: `{value}`" for value in item.evidence_paths)
        lines.extend(f"- warning: {value}" for value in item.warnings)
        lines.extend(f"- error: {value}" for value in item.errors)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IA/IB acceptance verification")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument(
        "--matrix-csv",
        type=Path,
        help="audit this existing matrix CSV instead of launching matrix runs",
    )
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
        verify_matrix(
            args.output_root,
            quick=args.quick,
            matrix_csv=args.matrix_csv,
        ),
        verify_stress_runs(args.output_root, quick=args.quick),
        verify_automated_regression(args.output_root),
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
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        render_markdown(
            results,
            docker_live_status(results),
            provenance=repository_provenance(),
        ),
        encoding="utf-8",
    )
    return 1 if any(item.status == "fail" for item in results) else 0


if __name__ == "__main__":
    sys.exit(main())
