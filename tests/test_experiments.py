"""实验框架接口测试。"""
import inspect
import pytest
from algorithms.registry import get_algorithm_registry
from experiments.runner import run_batch
from scripts.split_jobs import ALGOS, JOBS


def test_formal_experiment_algorithms_come_from_registry():
    assert [
        item.key for item in get_algorithm_registry().list(formal_only=True)
    ] == [
        "fixed_time",
        "classic_maxpressure",
        "capacity_aware_maxpressure",
    ]


def test_split_jobs_uses_only_formal_registry_algorithms():
    assert ALGOS == [
        "fixed_time",
        "classic_maxpressure",
        "capacity_aware_maxpressure",
    ]
    assert {algorithm for _, algorithm, _, _ in JOBS} == set(ALGOS)


def test_demo_constructs_algorithms_through_the_registry():
    from examples.run_demo import create_algorithm

    algorithm = create_algorithm("capacity_aware_maxpressure")

    assert algorithm.name == "capacity_aware_maxpressure"


def test_run_batch_signature_accepts_seeds():
    """run_batch 应接受 seeds 参数。"""
    sig = inspect.signature(run_batch)
    assert "seeds" in sig.parameters


def test_parse_args_defaults():
    from experiments.runner import parse_args
    args = parse_args([])
    assert args.seed == 42
    assert args.flow_multiplier == 1.0
    assert args.output_dir is None
    assert args.intersection == "1"
    assert args.steps == 36000
    assert args.algorithm == "fixed_time"


def test_parse_args_custom():
    from experiments.runner import parse_args
    args = parse_args([
        "--seed", "7", "--flow-multiplier", "1.5",
        "--output-dir", "output/x", "--intersection", "16",
        "--steps", "100", "--algorithm", "capacity_aware_maxpressure",
    ])
    assert (args.seed, args.flow_multiplier, args.intersection) == (7, 1.5, "16")
    assert args.algorithm == "capacity_aware_maxpressure"


def test_build_artifacts_encodes_all_run_dimensions(tmp_path):
    from experiments.runner import build_artifacts, parse_args

    args = parse_args([
        "--intersection", "16", "--algorithm", "actuated",
        "--flow-multiplier", "1.5", "--seed", "123",
        "--output-dir", str(tmp_path),
    ])
    artifacts = build_artifacts(args)
    assert artifacts.run_dir.parent == (
        tmp_path / "i16" / "actuated" / "x1.5" / "s123"
    )
    assert artifacts.run_dir.name == artifacts.run_id


@pytest.mark.parametrize("option,value", [
    ("--intersection", "0"),
    ("--intersection", "21"),
    ("--steps", "0"),
    ("--seed", "-1"),
    ("--flow-multiplier", "0"),
])
def test_parse_args_rejects_invalid_dimensions(option, value):
    from experiments.runner import parse_args

    with pytest.raises(SystemExit):
        parse_args([option, value])


def test_run_single_delegates_to_run_service(tmp_path):
    from unittest.mock import Mock
    from experiments.runner import parse_args, run_single

    args = parse_args([
        "--intersection", "1", "--steps", "1",
        "--output-dir", str(tmp_path),
    ])
    expected = Mock()
    service = Mock()
    service.run_sync.return_value = expected

    result = run_single(args, run_service=service)

    request = service.run_sync.call_args.args[0]
    assert result is expected
    assert request.intersection_id == "1"
    assert request.algorithm == "fixed_time"
    assert request.output_root == tmp_path


def test_run_batch_delegates_every_case_to_run_service(tmp_path):
    from core.run_models import RunResult, RunStatus
    from core.types import TrafficLevel
    from experiments.runner import run_batch

    class FakeService:
        def __init__(self):
            self.requests = []

        def run_sync(self, request):
            self.requests.append(request)
            return RunResult(
                run_id=f"run-{len(self.requests)}",
                status=RunStatus.COMPLETED,
                reason="",
                run_dir=tmp_path / f"run-{len(self.requests)}",
            )

    service = FakeService()
    results = run_batch(
        intersection_ids=["1"],
        algorithms=["fixed_time", "capacity_aware_maxpressure"],
        levels=[TrafficLevel.NORMAL],
        seeds=[42],
        steps=10,
        output_root=tmp_path,
        run_service=service,
    )

    assert len(results) == 2
    assert [request.algorithm for request in service.requests] == [
        "fixed_time",
        "capacity_aware_maxpressure",
    ]
    assert all(request.output_root == tmp_path for request in service.requests)


def test_stress_defaults_to_supported_baseline():
    from scripts.stress_memory import parse_stress_args

    args = parse_stress_args([])
    assert args.algorithm == "actuated"
    assert args.flow_multiplier == 1.5
    assert args.intersections == ["1", "11", "16"]
    assert args.steps == 3600
    assert args.max_python_mib == 1024


def test_stress_output_sizes_are_limited_to_one_run(tmp_path):
    from scripts.stress_memory import _output_sizes

    run_dir = tmp_path / "i1" / "actuated" / "x1.5" / "s42"
    run_dir.mkdir(parents=True)
    csv_path = run_dir / "metrics.csv"
    csv_path.write_text("metrics", encoding="utf-8")
    (tmp_path / "i11" / "other.csv").parent.mkdir(parents=True)
    (tmp_path / "i11" / "other.csv").write_text("other", encoding="utf-8")

    sizes = _output_sizes(run_dir, csv_path)

    assert str(csv_path) in sizes
    assert not any("other.csv" in path for path in sizes)


def test_stress_uses_configured_step_length():
    from scripts.stress_memory import _simulated_time_seconds

    assert _simulated_time_seconds("11", 100) == pytest.approx(10.0)


def test_stress_reports_actual_logged_simulation_time(tmp_path):
    from scripts.stress_memory import _actual_simulated_time_seconds

    run_dir = tmp_path / "i11" / "actuated" / "x1.5" / "s42"
    run_dir.mkdir(parents=True)
    metrics = run_dir / "metrics.csv"
    (run_dir / "simulation_log.csv").write_text(
        "step,timestamp\n0,0.0\n4,0.4\n", encoding="utf-8"
    )

    assert _actual_simulated_time_seconds(metrics, "11", 100) == pytest.approx(0.5)


def test_stress_accepts_run_result_from_unified_service(tmp_path, monkeypatch):
    from core.run_models import RunResult, RunStatus
    from scripts import stress_memory

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "metrics.csv").write_text("step\n0\n", encoding="utf-8")
    (run_dir / "simulation_log.csv").write_text(
        "step,timestamp\n0,0.0\n", encoding="utf-8"
    )
    result = RunResult(
        run_id="run",
        status=RunStatus.COMPLETED,
        reason="",
        run_dir=run_dir,
    )
    monkeypatch.setattr(stress_memory, "run_single", lambda args: result)
    args = stress_memory.parse_stress_args([
        "--intersections", "1",
        "--steps", "1",
        "--output-root", str(tmp_path),
    ])

    records = stress_memory.run_stress(args)

    assert records[0]["exit_status"] == 0
    assert str(run_dir / "metrics.csv") in records[0]["output_sizes"]


def test_verify_docker_static_runs_static_contract_test(tmp_path, monkeypatch):
    from scripts import verify_ia_ib

    (tmp_path / "docker").mkdir()
    (tmp_path / "docker" / "Dockerfile").write_text("FROM ubuntu sumo", encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
    test_file = tmp_path / "tests" / "test_docker_static.py"
    test_file.parent.mkdir()
    test_file.write_text("", encoding="utf-8")
    calls = []
    monkeypatch.setattr(verify_ia_ib, "ROOT", tmp_path)
    monkeypatch.setattr(verify_ia_ib.shutil, "which", lambda _: None)
    monkeypatch.setattr(
        verify_ia_ib.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command)
        or type("Result", (), {"returncode": 0, "stderr": ""})(),
    )

    result = verify_ia_ib.verify_docker_static(tmp_path / "verification")

    assert result.status == "pass"
    assert any("test_docker_static.py" in str(part) for part in calls[0])


def test_docker_live_status_distinguishes_not_run_fail_and_pass():
    from scripts.verify_ia_ib import CheckResult, docker_live_status

    unavailable = CheckResult(
        "docker_static", "pass", 0.1, "docker", ["Docker unavailable; not run"], []
    )
    failed = CheckResult("docker_static", "fail", 0.1, "docker", [], ["build failed"])
    passed = CheckResult("docker_static", "pass", 0.1, "docker", [], [])

    assert docker_live_status([unavailable]) == "not run: Docker unavailable"
    assert docker_live_status([failed]) == "fail"
    assert docker_live_status([passed]) == "pass"
