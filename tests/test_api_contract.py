import json
import subprocess
import sys
from pathlib import Path

from api.server import create_app
from core.run_models import RunStatus
from scripts.export_api_contract import export_contracts


def test_openapi_contains_canonical_pdf_endpoints():
    paths = create_app().openapi()["paths"]

    for path in [
        "/api/health",
        "/api/scenes",
        "/api/runs",
        "/api/runs/{run_id}",
        "/api/runs/{run_id}/metrics",
        "/api/runs/{run_id}/stop",
        "/api/cloud/predict",
        "/api/edge/control",
    ]:
        assert path in paths


def test_runtime_run_status_matches_checked_in_openapi_contract():
    runtime = create_app().openapi()["components"]["schemas"]["RunStatus"]["enum"]
    checked_in = json.loads(
        (Path(__file__).resolve().parents[1] / "docs" / "api" / "openapi.json").read_text(
            encoding="utf-8"
        )
    )["components"]["schemas"]["RunStatus"]["enum"]

    assert runtime == checked_in
    assert runtime == [item.value for item in RunStatus]
    assert "interrupted" in runtime
    assert "stopped" in runtime


def test_exported_openapi_and_postman_are_parseable(tmp_path):
    openapi_path, postman_path = export_contracts(tmp_path)

    openapi = json.loads(openapi_path.read_text(encoding="utf-8"))
    postman = json.loads(postman_path.read_text(encoding="utf-8"))
    assert openapi["info"]["version"] == "1.0.0"
    assert postman["info"]["schema"].endswith(
        "collection.json"
    )
    names = {item["name"] for item in postman["item"]}
    assert {"Health", "Scenes", "Submit Run", "Run Status", "Run Metrics"} <= names


def test_export_script_runs_directly_from_repository_root(tmp_path):
    root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/export_api_contract.py",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "openapi.json").is_file()
    assert (tmp_path / "postman_collection.json").is_file()
