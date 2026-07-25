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
