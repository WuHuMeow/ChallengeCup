# Judge API Task 16 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing FastAPI application with judge-facing run controls, validated evidence/results, latest SUMO frame access, realtime WebSocket events, static frontend serving, and a checked-in OpenAPI contract.

**Architecture:** Keep `RunService`, `RealtimeHub`, `FramePublisher`, and `EvidenceReader` as the owners of lifecycle, event, frame, and evidence state. Add thin API adapters for validation and transport: result endpoints never accept filesystem paths, frame/static routes enforce containment, and WebSocket code only adapts the async subscription stream. FastAPI lifespan owns service shutdown exactly once.

**Tech Stack:** Python 3.12+, FastAPI, Starlette `TestClient`/WebSocket test client, Pydantic v2, existing `EvidenceReader`, `RunService`, `RealtimeHub`, and `FramePublisher`.

**Spec:** `docs/superpowers/plans/2026-08-18-judge-facing-final-release.md` Task 16.

## Global Constraints

- Do not modify, move, delete, repackage, or stage `赛题资料.7z` or `data/intersection_data`.
- Preserve all existing canonical and deprecated API routes and their response models.
- Results are returned only after `EvidenceReader.validate(run_dir) == []` and a sealed summary is loaded from disk.
- Frame and result paths must remain below the configured service output root; no caller-supplied absolute path is accepted.
- WebSocket subscriptions use the bounded `RealtimeHub`; no blocking filesystem, TraCI, or SUMO operation may run on the event loop.
- Native GUI is optional: unsupported environments return HTTP 409 with a stable reason.

### Task 1: Public result and evidence adapters

**Files:**
- Modify: `api/models.py`
- Modify: `api/server.py`
- Create: `tests/test_judge_api.py`

**Interfaces:**
- `GET /api/results` returns `{ "items": [...], "count": int }` for completed, validated runs known to the service.
- `GET /api/results/{run_id}` returns one validated `RunResultModel` with a disk-loaded `summary`.
- `GET /api/runs/{run_id}/safety` returns the validated safety section or 404 when no sealed safety data exists.
- New models remain Pydantic v2 models and reuse `RunResultModel` fields rather than exposing `Path` objects.
- The new test module copies the existing `_strict_completed_result` fixture shape from `tests/test_api.py` and adds a local `_strict_completed_result` helper; no production fixture is introduced.

- [ ] **Step 1: Write the failing tests**

```python
def test_results_endpoint_excludes_unsealed_and_unknown_runs(client, service):
    service.records["unsealed"] = RunResult(
        "unsealed", RunStatus.COMPLETED, "", service.root / "unsealed",
        {"metrics": {"throughput": 999}}, "fixed_time",
    )
    response = client.get("/api/results")
    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0}
    assert client.get("/api/results/missing").status_code == 404


def test_result_endpoint_reads_summary_from_sealed_disk(client, service):
    canonical = _strict_completed_result(service.root)
    service.records["run-1"] = replace(canonical, summary={"metrics": {"throughput": 999}})
    response = client.get("/api/results/run-1")
    assert response.status_code == 200
    assert response.json()["summary"]["throughput"] == 1


def test_safety_endpoint_is_run_scoped_and_fail_closed(client, service):
    service.records["run-1"] = make_sealed_result(service.root, "run-1")
    response = client.get("/api/runs/run-1/safety")
    assert response.status_code in {200, 404}
    assert client.get("/api/runs/../results").status_code != 200
```

- [ ] **Step 2: Run the new tests to verify RED**

Run: `.venv\Scripts\python.exe -m pytest --basetemp .task16-red-results-20260823 tests/test_judge_api.py -q`

Expected: collection fails because `tests/test_judge_api.py` and the result routes/models do not yet exist.

- [ ] **Step 3: Implement the minimum result/evidence contract**

Add a private helper in `api/server.py` that obtains only `run_service.get(run_id)` records, rejects unknown/non-terminal/unsealed runs, calls `EvidenceReader.validate`, then returns `EvidenceReader.load_summary`. Add `ResultListModel` and `SafetyModel` in `api/models.py`; do not serialize `run_dir` in list items. Return 404 for invalid or absent sealed evidence and 422 for invalid request bodies.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest --basetemp .task16-green-results-20260823 tests/test_judge_api.py -q`

Expected: all result/evidence tests pass and no existing API test regresses.

- [ ] **Step 5: Commit the result adapter**

```powershell
git add api/models.py api/server.py tests/test_judge_api.py
git commit -m "feat: expose validated judge result endpoints"
```

### Task 2: Frame endpoint and static resource serving

**Files:**
- Create: `api/static.py`
- Modify: `api/server.py`
- Modify: `api/models.py`
- Modify: `tests/test_judge_api.py`

**Interfaces:**
- `GET /api/runs/{run_id}/frame?sequence=N` returns `image/png` and headers `X-Run-Id`, `X-Frame-Sequence`, `X-Simulation-Time`; it returns 404 for unknown/missing frames and does not return an older sequence.
- `GET /` and static asset paths serve `web/dist/index.html` and files only when they resolve below `web/dist`; absent builds return a structured 404.
- FastAPI lifespan calls `RunService.shutdown(wait=True)` exactly once on application shutdown.

- [ ] **Step 1: Write the failing frame/static/lifespan tests**

```python
def test_frame_endpoint_returns_latest_png_and_metadata(client, service):
    service.frame_publisher.publish(FrameRecord("run-1", 2, 12.5, b"png", 3.0))
    response = client.get("/api/runs/run-1/frame")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-run-id"] == "run-1"
    assert response.headers["x-frame-sequence"] == "2"
    assert response.headers["x-simulation-time"] == "12.5"


def test_frame_endpoint_rejects_unknown_and_older_sequence(client, service):
    service.frame_publisher.publish(FrameRecord("run-1", 2, 12.5, b"png", 3.0))
    assert client.get("/api/runs/missing/frame").status_code == 404
    assert client.get("/api/runs/run-1/frame?sequence=3").status_code == 404


def test_static_serving_never_escapes_dist(tmp_path, monkeypatch):
    app = create_app(FakeRunService(tmp_path))
    assert TestClient(app).get("/../pyproject.toml").status_code != 200
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `.venv\Scripts\python.exe -m pytest --basetemp .task16-red-frame-20260823 tests/test_judge_api.py -q`

Expected: frame/static tests fail because the routes and static adapter are absent.

- [ ] **Step 3: Implement containment-safe adapters**

Implement `latest_frame_response(service, run_id, sequence)` using `FramePublisher.latest`, compare `sequence` numerically, and return a `StreamingResponse`/`Response` with the four stable headers. Implement `api/static.py::install_static_routes(application, dist_root)` with `Path.resolve()` containment checks and a fallback 404 response. Add an application lifespan context that shuts down the service and closes its realtime/frame owners once.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest --basetemp .task16-green-frame-20260823 tests/test_judge_api.py tests/test_api.py -q`

Expected: frame/static/lifespan and legacy API tests pass.

- [ ] **Step 5: Commit the frame/static adapter**

```powershell
git add api/static.py api/server.py api/models.py tests/test_judge_api.py
git commit -m "feat: serve run-scoped frames and static assets"
```

### Task 3: Realtime WebSocket and native GUI endpoint

**Files:**
- Create: `api/websocket.py`
- Modify: `api/server.py`
- Modify: `tests/test_judge_api.py`

**Interfaces:**
- `WS /api/runs/{run_id}/events` sends the latest replay followed by bounded live messages from `RealtimeHub`; unknown run IDs close with code 4404.
- `POST /api/runs/{run_id}/native-gui` returns `{ "status": "shown" }` when the injected launcher succeeds, otherwise HTTP 409 with `{ "detail": "native SUMO-GUI is unavailable: ..." }`.
- WebSocket adapters never call `time.sleep`, read result files, or invoke TraCI.

- [ ] **Step 1: Write the failing WebSocket/native GUI tests**

```python
def test_events_websocket_replays_latest_and_receives_live_message(client, service):
    service.realtime_hub.publish("run-1", {"type": "status", "status": "queued"})
    with client.websocket_connect("/api/runs/run-1/events") as socket:
        assert socket.receive_json()["status"] == "queued"
        service.realtime_hub.publish("run-1", {"type": "metrics", "simulation_time": 1.0})
        assert socket.receive_json()["type"] == "metrics"


def test_events_websocket_rejects_unknown_run(client):
    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect("/api/runs/missing/events"):
            pass
    assert caught.value.code == 4404


def test_native_gui_returns_409_when_launcher_unavailable(client, service):
    service.native_gui = lambda _run_id: (False, "display unavailable")
    response = client.post("/api/runs/run-1/native-gui")
    assert response.status_code == 409
    assert "display unavailable" in response.json()["detail"]
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `.venv\Scripts\python.exe -m pytest --basetemp .task16-red-events-20260823 tests/test_judge_api.py -q`

Expected: WebSocket and native GUI tests fail because their adapters/routes are absent.

- [ ] **Step 3: Implement the async adapter and launcher seam**

Implement `api/websocket.py::stream_run_events(websocket, hub, run_id)` that checks `service.get(run_id)`, accepts the socket, iterates `hub.subscribe(run_id)`, sends JSON, and closes on disconnect. Add a small injected `native_gui` callable on the service/application state; default it to a function returning `(False, "native launcher unavailable")`. Never shell out from the request handler.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest --basetemp .task16-green-events-20260823 tests/test_judge_api.py tests/test_api.py -q`

Expected: WebSocket replay/backpressure and native GUI 409 tests pass.

- [ ] **Step 5: Commit realtime adapters**

```powershell
git add api/websocket.py api/server.py tests/test_judge_api.py
git commit -m "feat: expose realtime judge events and native gui status"
```

### Task 4: OpenAPI, contract gates, and Task 16 verification

**Files:**
- Modify: `docs/api/openapi.json`
- Modify: `tests/test_api_contract.py`
- Modify: `tests/test_judge_api.py`

**Interfaces:**
- Checked-in OpenAPI is generated from `create_app().openapi()` and includes every canonical Task 16 route, response schema, WebSocket documentation note, and 404/409 response.
- Existing aliases remain present and point to canonical route behavior.

- [ ] **Step 1: Add failing contract assertions**

```python
def test_openapi_contains_judge_workflow_routes():
    paths = create_app().openapi()["paths"]
    assert "/api/results" in paths
    assert "/api/runs/{run_id}/frame" in paths
    assert "/api/runs/{run_id}/safety" in paths
    assert "/api/runs/{run_id}/native-gui" in paths
```

- [ ] **Step 2: Run the contract tests to verify RED**

Run: `.venv\Scripts\python.exe -m pytest --basetemp .task16-red-contract-20260823 tests/test_api_contract.py tests/test_judge_api.py -q`

Expected: the new route assertions fail until all routes and schemas are installed.

- [ ] **Step 3: Export and validate OpenAPI**

Run `scripts/export_api_contract.py --output-dir .task16-contract-export-20260823`, compare the generated OpenAPI JSON to `docs/api/openapi.json`, and add explicit schema checks for `ResultListModel`, frame response headers, and 404/409 responses. Keep the checked-in contract deterministic.

- [ ] **Step 4: Run the Task 16 verification gates**

```powershell
.venv\Scripts\python.exe -m pytest --basetemp .task16-focused-20260823 tests/test_judge_api.py tests/test_api.py tests/test_api_contract.py -q
.venv\Scripts\python.exe -m flake8 api tests/test_judge_api.py tests/test_api.py tests/test_api_contract.py --ignore=E501,W503
.venv\Scripts\python.exe -m compileall -q api engine tests visualization
git diff --check
```

Expected: all focused tests pass, static checks exit 0, and no protected path appears in the diff.

- [ ] **Step 5: Commit the contract**

```powershell
git add docs/api/openapi.json tests/test_api_contract.py tests/test_judge_api.py
git commit -m "feat: publish judge workflow API contract"
```
