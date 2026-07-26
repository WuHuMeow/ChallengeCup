"""Export deterministic OpenAPI and Postman contracts for review and import."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.server import create_app  # noqa: E402


BASE_URL = "{{baseUrl}}"


def _request(
    name: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "method": method,
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "url": {
            "raw": f"{BASE_URL}{path}",
            "host": [BASE_URL],
            "path": [part for part in path.split("/") if part],
        },
    }
    if body is not None:
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, ensure_ascii=False, indent=2),
            "options": {"raw": {"language": "json"}},
        }
    return {
        "name": name,
        "request": request,
        "event": [{
            "listen": "test",
            "script": {
                "type": "text/javascript",
                "exec": [
                    "pm.test('successful response', function () {",
                    "  pm.expect(pm.response.code).to.be.within(200, 299);",
                    "});",
                ],
            },
        }],
    }


def _state_body() -> dict[str, Any]:
    return {
        "state": {
            "step": 10,
            "timestamp": 1.0,
            "tls_id": "tls_0",
            "current_phase": 0,
            "current_phase_name": "phase_0",
            "elapsed_phase_time": 12.0,
            "queues": [],
            "flows": {},
        }
    }


def _postman_collection() -> dict[str, Any]:
    run_body = {
        "intersection_id": "1",
        "algorithm": "fixed_time",
        "steps": 100,
        "flow_multiplier": 1.0,
        "seed": 42,
    }
    return {
        "info": {
            "name": "雄安车路云协同管控平台 API",
            "schema": (
                "https://schema.getpostman.com/json/collection/"
                "v2.1.0/collection.json"
            ),
        },
        "variable": [{"key": "baseUrl", "value": "http://localhost:8000"}],
        "item": [
            _request("Health", "GET", "/api/health"),
            _request("Scenes", "GET", "/api/scenes"),
            _request("Submit Run", "POST", "/api/runs", run_body),
            _request("Run Status", "GET", "/api/runs/{{runId}}"),
            _request("Run Metrics", "GET", "/api/runs/{{runId}}/metrics"),
            _request("Stop Run", "POST", "/api/runs/{{runId}}/stop"),
            _request("Cloud Predict", "POST", "/api/cloud/predict", _state_body()),
            _request("Edge Control", "POST", "/api/edge/control", _state_body()),
        ],
    }


def export_contracts(output_dir: Path = Path("docs/api")) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    openapi_path = output_dir / "openapi.json"
    postman_path = output_dir / "postman_collection.json"
    openapi_path.write_text(
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    postman_path.write_text(
        json.dumps(_postman_collection(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return openapi_path, postman_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/api"),
        help="directory for openapi.json and postman_collection.json",
    )
    args = parser.parse_args()
    paths = export_contracts(args.output_dir)
    for path in paths:
        print(path)
