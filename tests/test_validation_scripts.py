import json
from pathlib import Path
from unittest.mock import patch

from scripts.validation_common import ValidationResult, run_sumo_validation


def test_validation_distinguishes_warning_from_error(tmp_path):
    completed = type(
        "Result",
        (),
        {
            "returncode": 0,
            "stdout": "",
            "stderr": "Warning: signal phase\n",
        },
    )()
    with patch(
        "scripts.validation_common.subprocess.run", return_value=completed
    ):
        result = run_sumo_validation(Path("demo.sumocfg"), 100, tmp_path)

    assert result.ok is True
    assert result.warnings == ["Warning: signal phase"]
    assert result.errors == []


def test_validation_rejects_error_text_even_with_zero_exit(tmp_path):
    completed = type(
        "Result",
        (),
        {
            "returncode": 0,
            "stdout": "",
            "stderr": "Error: inaccessible network\n",
        },
    )()
    with patch(
        "scripts.validation_common.subprocess.run", return_value=completed
    ):
        result = run_sumo_validation(Path("demo.sumocfg"), 100, tmp_path)

    assert result.ok is False
    assert result.errors == ["Error: inaccessible network"]


def test_validation_redirects_queue_output_into_run_directory(tmp_path):
    completed = type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    config = tmp_path / "demo_11.sumocfg"
    config.write_text(
        "<configuration><output><queue-output value=\"queues.xml\"/>"
        "</output></configuration>",
        encoding="utf-8",
    )
    with patch(
        "scripts.validation_common.subprocess.run", return_value=completed
    ) as run:
        run_sumo_validation(config, 100, tmp_path)

    command = run.call_args.args[0]
    for option, filename in (
        ("--tripinfo-output", "tripinfo.xml"),
        ("--summary-output", "stats.xml"),
        ("--fcd-output", "traj.xml"),
    ):
        index = command.index(option)
        assert command[index + 1] == (tmp_path / filename).resolve().as_posix()
    queue_index = command.index("--queue-output")
    assert command[queue_index + 1] == (tmp_path / "queues.xml").resolve().as_posix()


def test_validate_all_parses_ids_steps_and_output_root():
    from scripts import validate_all

    args = validate_all.build_parser().parse_args(
        ["1", "11", "--steps", "250", "--output-root", "validation-output"]
    )

    assert args.ids == [1, 11]
    assert args.steps == 250
    assert args.output_root == Path("validation-output")


def test_batch_validate_report_options_are_explicit():
    from scripts import batch_validate

    parser = batch_validate.build_parser()
    default_report = parser.parse_args(
        ["--output-root", "validation-output", "--report"]
    )
    no_report = parser.parse_args(
        ["--output-root", "validation-output", "--no-report"]
    )

    assert default_report.report == batch_validate.REPORT
    assert default_report.no_report is False
    assert no_report.report is None
    assert no_report.no_report is True


def test_validate_all_prints_warning_lines_without_failing(tmp_path, capsys):
    from scripts import validate_all

    result = ValidationResult(
        config=Path("demo_1.sumocfg"),
        ok=True,
        returncode=0,
        elapsed_seconds=0.1,
        warnings=["Warning: signal phase"],
        errors=[],
        output_dir=tmp_path / "1",
    )
    with patch(
        "scripts.validate_all.run_sumo_validation", return_value=result
    ):
        returncode = validate_all.main(
            ["1", "--steps", "100", "--output-root", str(tmp_path)]
        )

    output = capsys.readouterr().out
    assert returncode == 0
    assert "Warning: signal phase" in output.splitlines()
    assert "1/1 PASS warnings=1 errors=0" in output


def test_batch_report_keeps_warning_and_error_on_separate_lines(tmp_path):
    from scripts import batch_validate

    report = tmp_path / "batch-report.md"
    result = ValidationResult(
        config=Path("demo_1.sumocfg"),
        ok=False,
        returncode=0,
        elapsed_seconds=0.1,
        warnings=["Warning: signal phase"],
        errors=["Error: inaccessible network"],
        output_dir=tmp_path / "1",
    )
    with patch(
        "scripts.batch_validate.run_sumo_validation", return_value=result
    ):
        returncode = batch_validate.main(
            [
                "1",
                "--steps",
                "100",
                "--output-root",
                str(tmp_path),
                "--report",
                str(report),
            ]
        )

    lines = report.read_text(encoding="utf-8").splitlines()
    assert returncode == 1
    assert "Warning: signal phase" in lines
    assert "Error: inaccessible network" in lines
    assert lines.index("Warning: signal phase") != lines.index(
        "Error: inaccessible network"
    )


def test_verifier_has_pdf_aligned_checks():
    from scripts.verify_ia_ib import checks

    assert [name for name, _ in checks] == [
        "data_integrity",
        "original_100",
        "enhanced_100",
        "enhanced_3600",
        "variant_contracts",
        "runtime_contracts",
        "api_contracts",
        "ca_mp_smoke",
        "exact_metrics",
        "figure_contracts",
        "matrix",
        "stress_runs",
        "automated_regression",
        "docker",
    ]


def test_automated_regression_records_commands_and_exit_codes(monkeypatch):
    from scripts import verify_ia_ib

    calls = []

    def completed(command, **kwargs):
        calls.append(command)
        return type(
            "Result",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )()

    monkeypatch.setattr(verify_ia_ib.subprocess, "run", completed)

    result = verify_ia_ib.verify_automated_regression(Path("unused"))

    assert result.status == "pass"
    assert result.exit_code == 0
    assert len(calls) == 5
    assert any(command[1:3] == ["-m", "pytest"] for command in calls)
    assert any(command[1:3] == ["-m", "compileall"] for command in calls)
    assert any(command[1] == "-c" and "import algorithms" in command[2] for command in calls)
    assert any(command[1:3] == ["-m", "flake8"] for command in calls)
    assert ["git", "diff", "--check"] in calls
    assert result.command.count("exit=0") == 5


def test_docker_unavailable_is_not_run_not_pass(tmp_path, monkeypatch):
    from scripts import verify_ia_ib

    monkeypatch.setattr(
        verify_ia_ib,
        "verify_docker_static",
        lambda _: verify_ia_ib.CheckResult(
            "docker_static", "pass", 0.1, "static", [], []
        ),
    )
    monkeypatch.setattr(verify_ia_ib.shutil, "which", lambda _: None)

    result = verify_ia_ib.verify_docker(tmp_path)

    assert result.status == "not_run"
    assert any("Docker unavailable" in warning for warning in result.warnings)


def test_final_report_has_no_hard_coded_ab_blocker():
    from scripts.verify_ia_ib import CheckResult, render_markdown

    report = render_markdown(
        [CheckResult("ca_mp_smoke", "pass", 0.1, "run", [], [], exit_code=0)],
        "not run: Docker unavailable",
    )

    assert "CA-MP remains an AB blocker" not in report
    assert "AB blocker:" not in report
    assert "| Check | Status | Exit Code | Seconds |" in report
    assert "| ca_mp_smoke | pass | 0 |" in report
    assert "Exit code: `0`" in report


def test_final_report_uses_flat_document_path():
    from scripts.verify_ia_ib import REPORT_PATH, ROOT

    assert REPORT_PATH == ROOT / "docs" / "ia-ib-final-verification.md"


def test_offline_package_marks_second_machine_not_run(tmp_path, monkeypatch):
    from scripts import package_offline

    root = tmp_path / "repo"
    root.mkdir()
    (root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (root / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "output").mkdir()
    (root / "output" / "generated.txt").write_text("skip", encoding="utf-8")
    monkeypatch.setattr(package_offline.shutil, "which", lambda _: None)

    manifest_path = package_offline.package_offline(
        root,
        tmp_path / "package",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["docker"]["status"] == "not_run"
    assert manifest["second_machine"]["status"] == "not_run"
    assert manifest["files"]["source_archive"]["sha256"]
    assert "docker load" in manifest["commands"]["load"]
