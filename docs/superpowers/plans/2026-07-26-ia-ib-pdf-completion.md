# IA/IB PDF Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete every repository-owned IA/IB responsibility and the direct CA-MP, metrics, visualization, API, and deployment blockers required by the approved PDF-aligned design.

**Architecture:** Keep one end-to-end execution path: `RunRequest -> RunService -> Scene/Variant -> SimulationRunner -> TraCI/EdgeChannel/Algorithm -> RunArtifacts -> exact summary -> figures`. API and batch entry points call the same serialized RunService so concurrent submissions receive isolated run IDs without sharing the process-global TraCI connection.

**Tech Stack:** Python 3.12, pytest 8, SUMO/TraCI 1.27.x, FastAPI/Pydantic, dataclasses, defusedxml, pandas, Matplotlib, Docker/Compose.

## Global Constraints

- Treat `data/intersection_data/` as read-only.
- Use `ca_maxpressure` as the canonical algorithm identifier.
- Use `1.0` and `1.5` as the formal traffic multipliers and seeds `42`, `123`, `456`.
- Cover 3600 simulated seconds; at the configured 0.1-second step this is 36000 control ticks.
- Use a single RunService worker because the current TraCI client is process-global.
- A successful run must have non-empty metadata, metrics, events, step log, tripinfo, stats, and trajectory files.
- Missing exact metric data is `null`/`missing`, never a fabricated `0.0`.
- Docker and second-machine checks that were not executed are `not_run`, never `pass`.
- Follow red-green-refactor for every behavior change and commit each independently reviewable task.
- Use `.\.venv\Scripts\python.exe` after creating the local environment.

## Current Baseline

Run before Task 1:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected: `114 passed` before new tests are added. If dependency installation is unavailable, the existing `.worktrees/ia-ib-completion/.venv/Scripts/python.exe` may be used temporarily, but final verification must use the repository-local `.venv`.

---

### Task 1: Collision-Safe Run Models and Artifacts

**Files:**
- Create: `core/run_models.py`
- Modify: `engine/artifacts.py`
- Modify: `tests/test_artifacts.py`
- Create: `tests/test_run_models.py`

**Interfaces:**
- Produces: `RunStatus`, `VariantSpec`, `RunRequest`, `RunResult`.
- Produces: `RunArtifacts.create(..., run_id: str | None = None) -> RunArtifacts`.
- Produces: `RunArtifacts.summary` and `RunArtifacts.figures`.
- Consumed by: RunService, API, batch experiments, summary generation.

- [ ] **Step 1: Write failing run-model and collision tests**

```python
from core.run_models import RunRequest, RunStatus, VariantSpec
from engine.artifacts import RunArtifacts


def test_run_request_has_pdf_defaults():
    request = RunRequest(intersection_id="1", algorithm="fixed_time")
    assert request.steps == 36000
    assert request.flow_multiplier == 1.0
    assert request.seed == 42
    assert request.variant == VariantSpec()


def test_artifacts_add_unique_run_id(tmp_path):
    first = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    second = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    assert first.run_id != second.run_id
    assert first.run_dir.parent == second.run_dir.parent
    assert first.run_dir.name == first.run_id
    assert first.summary.name == "summary.json"
    assert first.figures.name == "figures"


def test_run_status_values_are_stable():
    assert [item.value for item in RunStatus] == [
        "queued", "running", "completed", "stopped",
        "ended_early", "disconnected", "interrupted", "failed",
    ]
```

- [ ] **Step 2: Run the focused tests and verify import/signature failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py tests/test_artifacts.py -q
```

Expected: FAIL because `core.run_models` and `RunArtifacts.run_id` do not exist.

- [ ] **Step 3: Add the exact shared models**

```python
# core/run_models.py
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ENDED_EARLY = "ended_early"
    DISCONNECTED = "disconnected"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


@dataclass(frozen=True)
class VariantSpec:
    vehicle_type_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    signal_duration_scale: float = 1.0
    closed_lanes: tuple[str, ...] = ()
    closure_begin: float = 0.0
    closure_end: float = 3600.0


@dataclass(frozen=True)
class RunRequest:
    intersection_id: str
    algorithm: str
    steps: int = 36000
    flow_multiplier: float = 1.0
    seed: int = 42
    output_root: Path | None = None
    edge_delay_steps: int = 0
    edge_directions: tuple[str, ...] = ()
    variant: VariantSpec = field(default_factory=VariantSpec)


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: RunStatus
    reason: str
    run_dir: Path
    summary: dict[str, Any] | None = None
```

- [ ] **Step 4: Add a run ID leaf to RunArtifacts**

```python
from uuid import uuid4

@classmethod
def create(cls, root, intersection_id, algorithm, flow_multiplier, seed, run_id=None):
    resolved_run_id = run_id or uuid4().hex[:12]
    run_dir = (
        Path(root) / f"i{intersection_id}" / algorithm
        / f"x{flow_multiplier:g}" / f"s{seed}" / resolved_run_id
    )
    run_dir.mkdir(parents=True, exist_ok=False)
    return cls(
        run_dir, intersection_id, algorithm, flow_multiplier, seed,
        resolved_run_id,
    )

@property
def summary(self) -> Path:
    return self.run_dir / "summary.json"

@property
def figures(self) -> Path:
    return self.run_dir / "figures"
```

Add `run_id` to metadata and create the `figures/` directory on demand rather than at artifact construction.

- [ ] **Step 5: Run focused and existing artifact tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py tests/test_artifacts.py tests/test_experiments.py -q
```

Expected: PASS after updating old deterministic-path assertions to include a run ID leaf.

- [ ] **Step 6: Commit**

```powershell
git add core/run_models.py engine/artifacts.py tests/test_run_models.py tests/test_artifacts.py tests/test_experiments.py
git commit -m "feat: add collision-safe run models"
```

---

### Task 2: Auditable Actions, Reconnects, Stops, and Terminal States

**Files:**
- Modify: `core/types.py`
- Modify: `engine/traci_bridge.py`
- Modify: `engine/mock_bridge.py`
- Modify: `engine/runner.py`
- Modify: `tests/test_events.py`
- Modify: `tests/test_resilience.py`
- Modify: `tests/test_runner_channel.py`
- Modify: `tests/test_mock_bridge.py`

**Interfaces:**
- Produces: `ActionResult(action, accepted, detail)`.
- Produces: `TraCIBridge(event_callback=...)`.
- Produces: `SimulationRunner.run(..., stop_event: threading.Event | None = None)`.
- Persists exactly one `terminal` event and one final RunStatus.

- [ ] **Step 1: Write failing action and terminal-state tests**

```python
def test_rejected_action_is_not_logged_as_applied(tmp_path):
    runner, artifacts = make_runner_with_rejected_action(tmp_path)
    runner.run(2)
    events = read_events(artifacts.events)
    assert [row["type"] for row in events].count("action_rejected") == 2
    assert not any(row["type"] == "action_applied" for row in events)


def test_stop_event_writes_stopped_terminal_state(tmp_path):
    stop = threading.Event()
    stop.set()
    runner, artifacts = make_runner(tmp_path)
    runner.run(steps=10, stop_event=stop)
    assert read_metadata(artifacts.metadata)["status"] == "stopped"
    assert terminal_events(artifacts.events) == ["stopped"]


def test_reconnect_events_are_persisted(tmp_path):
    runner, artifacts = make_runner_with_one_reconnect(tmp_path)
    runner.run(2)
    event_types = [row["type"] for row in read_events(artifacts.events)]
    assert event_types.count("reconnect_started") == 1
    assert event_types.count("reconnect_succeeded") == 1


def test_ordinary_early_end_is_not_disconnected(tmp_path):
    runner, artifacts = make_runner_with_early_end(tmp_path)
    runner.run(10)
    assert read_metadata(artifacts.metadata)["status"] == "ended_early"
```

- [ ] **Step 2: Run focused tests and verify failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_events.py tests/test_resilience.py tests/test_runner_channel.py -q
```

Expected: FAIL because rejected actions are also logged normally, reconnects are not events, and stop/early-end statuses do not exist.

- [ ] **Step 3: Return one result for every attempted action**

```python
# core/types.py
@dataclass(frozen=True)
class ActionResult:
    action: ControlAction
    accepted: bool
    detail: str
```

Change `TraCIBridge.apply_actions()` and `MockBridge.apply_actions()` to return `list[ActionResult]`. For each action:

```python
if action.tls_id != self.tls_id:
    results.append(ActionResult(action, False, f"unknown tls_id: {action.tls_id!r}"))
    continue
# validate the exact action value
# call TraCI only after validation
results.append(ActionResult(action, True, "applied"))
```

- [ ] **Step 4: Add bridge lifecycle callbacks**

```python
def __init__(..., event_callback=None):
    self.event_callback = event_callback or (lambda event_type, detail: None)

def _emit(self, event_type: str, detail: str) -> None:
    self.event_callback(event_type, detail)

# inside step()
self._emit("reconnect_started", f"attempt={self._restarts + 1}/{self.max_restarts}")
...
self._emit("reconnect_succeeded", f"attempt={self._restarts}")
...
self._emit("reconnect_failed", str(exc))
```

Expose `is_exhausted()` as:

```python
def is_exhausted(self) -> bool:
    return traci.simulation.getMinExpectedNumber() <= 0
```

- [ ] **Step 5: Make Runner assign truthful terminal states**

Use `RunStatus` values and this loop:

```python
status = RunStatus.RUNNING
for step in range(steps):
    if stop_event is not None and stop_event.is_set():
        status, reason = RunStatus.STOPPED, "stop requested"
        break
    tick = self._tick(step)
    if tick == "disconnected":
        status, reason = RunStatus.DISCONNECTED, self._terminal_reason
        break
    if tick == "ended_early":
        status, reason = RunStatus.ENDED_EARLY, "SUMO exhausted before target"
        break
else:
    status = RunStatus.COMPLETED
```

Runner must create the EventLogger before the bridge or assign the callback immediately after bridge construction:

```python
event_callback=lambda kind, detail: self.event_logger.log(
    len(self.metrics_history), kind, detail
) if self.event_logger else None
```

Log accepted and rejected action results separately. Save collectors and close the bridge first, update the final status for any cleanup or summary failure, then append and save exactly one terminal event before writing metadata:

```python
self.event_logger.log(last_step, "terminal", status.value)
```

- [ ] **Step 6: Run all runtime resilience tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_events.py tests/test_resilience.py tests/test_runner_channel.py tests/test_mock_bridge.py tests/test_traci_outputs.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add core/types.py engine/traci_bridge.py engine/mock_bridge.py engine/runner.py tests/test_events.py tests/test_resilience.py tests/test_runner_channel.py tests/test_mock_bridge.py
git commit -m "feat: make runtime events and terminal states auditable"
```

---

### Task 3: Serialized RunService and Unified Batch Execution

**Files:**
- Create: `engine/run_service.py`
- Modify: `experiments/runner.py`
- Create: `tests/test_run_service.py`
- Modify: `tests/test_experiments.py`

**Interfaces:**
- Produces: `RunService.submit(request) -> RunResult`.
- Produces: `RunService.run_sync(request) -> RunResult`.
- Produces: `RunService.get(run_id) -> RunResult`.
- Produces: `RunService.stop(run_id) -> bool`.
- `run_batch()` returns `list[RunResult]` and never constructs SimulationRunner directly.

- [ ] **Step 1: Write failing queue and batch-boundary tests**

```python
def test_concurrent_submissions_get_unique_queued_runs(tmp_path):
    service = RunService(output_root=tmp_path, runner_factory=BlockingRunner)
    first = service.submit(RunRequest("1", "fixed_time"))
    second = service.submit(RunRequest("1", "fixed_time"))
    assert first.status is RunStatus.QUEUED
    assert second.status is RunStatus.QUEUED
    assert first.run_id != second.run_id
    assert first.run_dir != second.run_dir
    assert service.max_workers == 1


def test_run_batch_delegates_every_case_to_run_service(fake_service):
    results = run_batch(
        intersection_ids=["1"], algorithms=["fixed_time", "ca_maxpressure"],
        levels=[TrafficLevel.NORMAL], seeds=[42], steps=10,
        run_service=fake_service,
    )
    assert len(fake_service.requests) == 2
    assert results == fake_service.results
```

- [ ] **Step 2: Run focused tests and verify missing RunService**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_experiments.py -q
```

Expected: FAIL because `engine.run_service` does not exist and `run_batch()` builds runners directly.

- [ ] **Step 3: Implement the single-worker service**

```python
class RunService:
    def __init__(self, output_root=Path("output/runs"), runner_factory=SimulationRunner):
        self.output_root = Path(output_root)
        self.runner_factory = runner_factory
        self.max_workers = 1
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._records: dict[str, RunResult] = {}
        self._stops: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def submit(self, request: RunRequest) -> RunResult:
        artifacts = RunArtifacts.create(
            request.output_root or self.output_root,
            request.intersection_id, request.algorithm,
            request.flow_multiplier, request.seed,
        )
        queued = RunResult(
            artifacts.run_id, RunStatus.QUEUED, "", artifacts.run_dir
        )
        with self._lock:
            self._records[artifacts.run_id] = queued
            self._stops[artifacts.run_id] = threading.Event()
        self._executor.submit(self._execute, request, artifacts)
        return queued
```

`_execute()` validates the request, creates the Scene, VariantBundle, EdgeChannel, algorithm and runner, writes `running`, executes, then reloads metadata into `RunResult`. `run_sync()` uses the same `_execute()` path without the executor. `stop()` only sets the matching event.

- [ ] **Step 4: Route single and batch entry points through RunService**

```python
def run_single(args, run_service=None) -> RunResult:
    service = run_service or RunService(output_root=resolve_output_root(args))
    return service.run_sync(request_from_args(args))

def run_batch(..., run_service=None) -> list[RunResult]:
    service = run_service or RunService(output_root=output_root)
    return [
        service.run_sync(build_request(intersection_id, algorithm, level, seed, steps))
        for intersection_id, algorithm, level, seed in itertools.product(...)
    ]
```

Remove the legacy `output_root/csv/...` path and every direct `SimulationRunner(...)` construction from `run_batch()`.

- [ ] **Step 5: Run service, experiment, artifact, and seed tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_experiments.py tests/test_artifacts.py tests/test_seed.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add engine/run_service.py experiments/runner.py tests/test_run_service.py tests/test_experiments.py tests/test_artifacts.py tests/test_seed.py
git commit -m "feat: unify runs behind serialized service"
```

---

### Task 4: Real REST API, OpenAPI, and Postman/Apifox Contracts

**Files:**
- Create: `api/models.py`
- Modify: `api/server.py`
- Create: `scripts/export_api_contract.py`
- Create: `docs/api/openapi.json`
- Create: `docs/api/postman_collection.json`
- Modify: `tests/test_api.py`
- Create: `tests/test_api_contract.py`

**Interfaces:**
- Produces: `create_app(run_service: RunService | None = None) -> FastAPI`.
- Canonical endpoints are all below `/api`.
- Compatibility endpoints forward to the same service and are deprecated.

- [ ] **Step 1: Replace placeholder endpoint tests with real contracts**

```python
def test_submit_and_read_run(client, fake_service):
    response = client.post("/api/runs", json={
        "intersection_id": "1", "algorithm": "fixed_time",
        "steps": 100, "flow_multiplier": 1.0, "seed": 42,
    })
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    assert client.get(f"/api/runs/{run_id}").status_code == 200


def test_scenes_are_real_registry_rows(client):
    rows = client.get("/api/scenes").json()
    assert len(rows) == 20
    assert rows[0]["intersection_id"]


def test_cloud_and_edge_endpoints_return_shared_contracts(client):
    state = make_state_payload()
    prediction = client.post("/api/cloud/predict", json={"state": state})
    actions = client.post("/api/edge/control", json={"state": state})
    assert prediction.status_code == 200
    assert "predicted_flows" in prediction.json()
    assert actions.status_code == 200
    assert isinstance(actions.json()["actions"], list)
```

- [ ] **Step 2: Run API tests and verify placeholder failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_api_contract.py -q
```

Expected: FAIL because the current endpoints return empty lists, zero metrics, and an in-memory MVI state.

- [ ] **Step 3: Add Pydantic request/response adapters**

Define in `api/models.py`:

```python
class VariantSpecModel(BaseModel):
    vehicle_type_overrides: dict[str, dict[str, str]] = Field(default_factory=dict)
    signal_duration_scale: float = 1.0
    closed_lanes: list[str] = Field(default_factory=list)
    closure_begin: float = 0.0
    closure_end: float = 3600.0

class RunRequestModel(BaseModel):
    intersection_id: str
    algorithm: Literal["fixed_time", "actuated", "ca_maxpressure"]
    steps: int = Field(default=36000, gt=0)
    flow_multiplier: float = Field(default=1.0, gt=0)
    seed: int = Field(default=42, ge=0)
    edge_delay_steps: int = Field(default=0, ge=0)
    variant: VariantSpecModel = Field(default_factory=VariantSpecModel)
```

Add explicit queue/state/action models and conversion methods to the dataclasses in `core.types` and `core.run_models`.

- [ ] **Step 4: Build the app around RunService**

```python
def create_app(run_service=None) -> FastAPI:
    app = FastAPI(title="雄安车路云协同管控平台", version="1.0.0")
    app.state.run_service = run_service or RunService()

    @app.post("/api/runs", status_code=202)
    def submit_run(payload: RunRequestModel):
        return serialize_result(app.state.run_service.submit(payload.to_domain()))

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        result = app.state.run_service.get(run_id)
        if result is None:
            raise HTTPException(404, "unknown run_id")
        return serialize_result(result)
```

Implement all canonical endpoints, then implement `/health`, `/scenes`, `/run`, `/status`, and old `/api/simulation/*` only as deprecated wrappers.

- [ ] **Step 5: Export machine-readable API evidence**

`scripts/export_api_contract.py` imports `app.openapi()`, writes deterministic UTF-8 JSON to `docs/api/openapi.json`, then creates a Postman v2.1 collection containing health, scenes, submit, status, metrics, stop, cloud and edge requests with status-code and response-field tests.

Run:

```powershell
.\.venv\Scripts\python.exe scripts/export_api_contract.py
.\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_api_contract.py -q
```

Expected: both JSON files parse, contain no placeholder endpoints, and tests pass.

- [ ] **Step 6: Commit**

```powershell
git add api/models.py api/server.py scripts/export_api_contract.py docs/api/openapi.json docs/api/postman_collection.json tests/test_api.py tests/test_api_contract.py
git commit -m "feat: expose real run and control APIs"
```

---

### Task 5: Parameterized Scene and Disturbance Bundles

**Files:**
- Modify: `scenes/variant.py`
- Modify: `core/run_models.py`
- Modify: `engine/run_service.py`
- Modify: `tests/test_scenes.py`
- Create: `tests/test_variants.py`

**Interfaces:**
- Produces: `VariantBundle(additional_files, manifest)`.
- Produces: `VariantGenerator.generate_bundle(scene_meta, flow_multiplier, spec, output_dir)`.

- [ ] **Step 1: Write failing bundle tests**

```python
def test_bundle_scales_flow_vehicle_and_signal_without_touching_source(tmp_path):
    meta = SceneRegistry().get_scene("1").meta
    original = meta.sumo_flow.read_bytes()
    bundle = VariantGenerator().generate_bundle(
        meta, 1.5,
        VariantSpec(
            vehicle_type_overrides={"car": {"sigma": "0.2"}},
            signal_duration_scale=1.1,
        ),
        tmp_path,
    )
    assert len(bundle.additional_files) == 2
    assert bundle.manifest["flow_multiplier"] == 1.5
    assert meta.sumo_flow.read_bytes() == original


def test_lane_closure_additional_is_bounded_and_reproducible(tmp_path):
    spec = VariantSpec(
        closed_lanes=("edge_0_0",), closure_begin=600, closure_end=1200
    )
    first = generate_bundle(spec, tmp_path / "a")
    second = generate_bundle(spec, tmp_path / "b")
    assert normalized_xml(first.additional_files[-1]) == normalized_xml(
        second.additional_files[-1]
    )
```

- [ ] **Step 2: Run tests and verify missing bundle interface**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_scenes.py tests/test_variants.py -q
```

Expected: FAIL because only flow scaling exists.

- [ ] **Step 3: Add bundle and manifest types**

```python
@dataclass(frozen=True)
class VariantBundle:
    additional_files: tuple[Path, ...]
    manifest: dict[str, object]
```

`generate_bundle()` must:

1. clone the source flow XML;
2. apply flow scaling to `number`, `probability`, and `vehsPerHour`;
3. apply declared vType attribute overrides;
4. write a `tlLogic` additional file with every green duration multiplied by `signal_duration_scale` and yellow/all-red durations unchanged;
5. write a rerouter additional file for explicit `closed_lanes`;
6. write `variant_manifest.json` with source hashes and parameters.

Use this closure XML:

```xml
<additional>
  <rerouter id="incident_rerouter" edges="EDGE_ID">
    <interval begin="600" end="1200">
      <closingLaneReroute id="edge_0_0" allow="authority"/>
    </interval>
  </rerouter>
</additional>
```

- [ ] **Step 4: Wire the bundle into RunService**

```python
bundle = VariantGenerator().generate_bundle(
    scene.meta, request.flow_multiplier, request.variant,
    artifacts.run_dir / "variants",
)
runner = self.runner_factory(
    scene=scene, algorithm=algorithm,
    additional_files=list(bundle.additional_files),
    artifacts=artifacts, seed=request.seed,
    state_channel=build_edge_channel(request),
)
```

- [ ] **Step 5: Run variant and service tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_scenes.py tests/test_variants.py tests/test_run_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add scenes/variant.py core/run_models.py engine/run_service.py tests/test_scenes.py tests/test_variants.py tests/test_run_service.py
git commit -m "feat: generate parameterized SUMO scenario bundles"
```

---

### Task 6: Phase-Aware Capacity-Normalized CA-MP

**Files:**
- Modify: `core/types.py`
- Modify: `engine/traci_bridge.py`
- Modify: `algorithms/ca_max_pressure.py`
- Modify: `config/default.yaml`
- Modify: `tests/test_algorithms.py`
- Modify: `tests/test_edge_mapping.py`

**Interfaces:**
- Produces: `PhaseTrafficState`.
- `JointState.phase_states` describes legal signal phases and downstream saturation.
- CA-MP returns only integer `set_phase` and numeric `set_phase_duration` actions.

- [ ] **Step 1: Replace MVI tests with exact pressure and safety tests**

```python
def test_ca_mp_uses_capacity_normalized_pressure():
    state = make_phase_state(
        current=0,
        phases=[
            phase(0, incoming_queue=8, incoming_capacity=10, outgoing_queue=1,
                  outgoing_capacity=10, outgoing_occupancy=0.1),
            phase(2, incoming_queue=12, incoming_capacity=30, outgoing_queue=0,
                  outgoing_capacity=30, outgoing_occupancy=0.1),
        ],
    )
    actions = CAMaxPressureAlgorithm().step(state)
    assert actions[0].value == 0


def test_ca_mp_blocks_saturated_downstream():
    state = make_phase_state(
        current=0,
        phases=[
            phase(0, 8, 10, 0, 10, 0.95),
            phase(2, 4, 10, 0, 10, 0.20),
        ],
    )
    assert selected_green(CAMaxPressureAlgorithm(), state) == 2


def test_ca_mp_switches_through_yellow_before_target():
    algo = CAMaxPressureAlgorithm()
    algo.init(scene_with_phases(greens=(0, 2), transitions={0: 1}))
    first = algo.step(high_pressure_on_phase_2(current=0, elapsed=20))
    assert first[0].value == 1
    second = algo.step(high_pressure_on_phase_2(current=1, elapsed=3))
    assert second[0].value == 2
```

- [ ] **Step 2: Run algorithm tests and verify MVI failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_algorithms.py tests/test_edge_mapping.py -q
```

Expected: FAIL because CA-MP returns direction strings and JointState has no phase traffic data.

- [ ] **Step 3: Add phase traffic data**

```python
@dataclass(frozen=True)
class PhaseTrafficState:
    phase_index: int
    signal_state: str
    nominal_duration: float
    incoming_lanes: tuple[str, ...]
    outgoing_lanes: tuple[str, ...]
    incoming_queue: float
    incoming_capacity: float
    outgoing_queue: float
    outgoing_capacity: float
    outgoing_occupancy: float
```

Add `phase_states: List[PhaseTrafficState] = field(default_factory=list)` to `JointState`.

TraCIBridge derives phase states from `getControlledLinks()`, program phase strings, incoming lane halting counts/capacities, outgoing lane halting counts/capacities, and `getLastStepOccupancy()`.

- [ ] **Step 4: Implement the exact CA-MP score**

```python
def phase_pressure(
    self, phase: PhaseTrafficState, predicted_arrivals: float
) -> float:
    incoming = phase.incoming_queue / max(phase.incoming_capacity, 1.0)
    outgoing = phase.outgoing_queue / max(phase.outgoing_capacity, 1.0)
    prediction = self.prediction_weight * (
        predicted_arrivals / max(phase.incoming_capacity, 1.0)
    )
    if phase.outgoing_occupancy >= self.overflow_threshold:
        return float("-inf")
    return incoming - outgoing + prediction
```

For each phase, sum `PredictionResult.predicted_flows` over `incoming_lanes` and pass that value to `phase_pressure()`. Implement min/max green, cloud-dispatched parameters, dynamic duration clamping, pending target phase, and yellow/all-red transition handling. `reset()` clears pending state and resets CloudPolicy.

Add `prediction_weight: 0.15` and explicit transition settings to `config/default.yaml`.

- [ ] **Step 5: Run algorithm, cloud, bridge, and 100-step live checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_algorithms.py tests/test_cloud.py tests/test_edge_mapping.py tests/test_traci_outputs.py -q
.\.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm ca_maxpressure --steps 100 --output-dir output/verification/ca-mp-smoke
```

Expected: all tests pass; the smoke run exits 0; `events.csv` has no `action_rejected`.

- [ ] **Step 6: Commit**

```powershell
git add core/types.py engine/traci_bridge.py algorithms/ca_max_pressure.py config/default.yaml tests/test_algorithms.py tests/test_edge_mapping.py
git commit -m "feat: implement phase-aware capacity max pressure"
```

---

### Task 7: Exact SUMO Metrics and Run Summaries

**Files:**
- Modify: `core/types.py`
- Modify: `engine/artifacts.py`
- Modify: `engine/traci_bridge.py`
- Modify: `engine/runner.py`
- Modify: `experiments/metrics.py`
- Create: `experiments/summary.py`
- Create: `tests/test_metrics.py`
- Modify: `tests/test_traci_outputs.py`

**Interfaces:**
- Produces: `parse_tripinfo(path) -> ExactMetrics`.
- Produces: `write_run_summary(artifacts) -> dict`.
- Successful Runner calls summary generation after SUMO output is closed.

- [ ] **Step 1: Write failing exact-metric fixture tests**

```python
def test_tripinfo_summary_uses_real_duration_delay_stops_and_fuel(tmp_path):
    path = write_tripinfo(tmp_path, [
        {"duration": 100, "timeLoss": 20, "waitingCount": 2, "fuel_abs": 5},
        {"duration": 140, "timeLoss": 40, "waitingCount": 4, "fuel_abs": 7},
    ])
    exact = parse_tripinfo(path)
    assert exact.avg_travel_time == 120
    assert exact.avg_delay == 30
    assert exact.total_stops == 6
    assert exact.fuel_consumption == 12
    assert exact.throughput == 2


def test_missing_exact_fields_are_null_not_zero(tmp_path):
    exact = parse_tripinfo(write_empty_tripinfo(tmp_path))
    assert exact.avg_travel_time is None
    assert exact.fuel_consumption is None
```

- [ ] **Step 2: Run focused tests and verify missing parser**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_metrics.py tests/test_traci_outputs.py -q
```

Expected: FAIL because `experiments.summary` does not exist and live metrics contain fixed placeholders.

- [ ] **Step 3: Enable exact SUMO outputs**

Extend the TraCI command with:

```python
"--tripinfo-output.write-unfinished", "true",
"--device.emissions.probability", "1",
```

Keep tripinfo, summary and FCD output isolated under RunArtifacts. Parse nested `<emissions fuel_abs="...">` when present.

- [ ] **Step 4: Implement exact parsing and summary writing**

```python
@dataclass(frozen=True)
class ExactMetrics:
    avg_travel_time: float | None
    avg_delay: float | None
    avg_queue_length: float | None
    max_queue_length: float | None
    throughput: int
    total_stops: int | None
    fuel_consumption: float | None


def write_run_summary(artifacts: RunArtifacts) -> dict:
    exact = parse_tripinfo(artifacts.tripinfo)
    queue = parse_queue_metrics(artifacts.metrics)
    payload = {
        "run_id": artifacts.run_id,
        "metrics": {**asdict(exact), **queue},
        "sources": {
            "travel": artifacts.tripinfo.name,
            "queue": artifacts.metrics.name,
        },
    }
    artifacts.summary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
```

Change instantaneous `SimulationMetrics.avg_travel_time`, `total_stops`, and `fuel_consumption` to optional values and write empty CSV fields rather than zero when unavailable.

- [ ] **Step 5: Generate summary after bridge close**

Runner closes TraCI before parsing XML, then calls `write_run_summary()` only for `completed` and `ended_early` runs whose core XML exists. Summary failure changes the run to `failed` and is recorded in metadata.

- [ ] **Step 6: Run metrics, runner, and live artifact tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_metrics.py tests/test_traci_outputs.py tests/test_runner_channel.py tests/test_artifacts.py -q
.\.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm fixed_time --steps 100 --output-dir output/verification/metrics-smoke
```

Expected: summary JSON contains non-placeholder values or explicit `null`; no exact field is fabricated.

- [ ] **Step 7: Commit**

```powershell
git add core/types.py engine/artifacts.py engine/traci_bridge.py engine/runner.py experiments/metrics.py experiments/summary.py tests/test_metrics.py tests/test_traci_outputs.py tests/test_runner_channel.py
git commit -m "feat: derive exact metrics from SUMO outputs"
```

---

### Task 8: Standard Comparison Figures and Heatmaps

**Files:**
- Modify: `visualization/plots.py`
- Create: `visualization/report.py`
- Create: `tests/test_visualization.py`

**Interfaces:**
- Produces: `collect_summaries(root) -> pandas.DataFrame`.
- Produces: `generate_run_figures(run_dir) -> list[Path]`.
- Produces: `generate_matrix_figures(root, output_dir) -> list[Path]`.

- [ ] **Step 1: Write failing heatmap and provenance tests**

```python
def test_heatmap_pivots_intersection_by_algorithm(tmp_path):
    csv_path = write_summary_csv(tmp_path)
    output = tmp_path / "heatmap.png"
    plot_heatmap(csv_path, output, metric="avg_travel_time")
    assert output.exists() and output.stat().st_size > 1000


def test_every_figure_has_provenance_manifest(tmp_path):
    generated = generate_matrix_figures(sample_matrix(tmp_path), tmp_path / "figures")
    manifest = json.loads((tmp_path / "figures/manifest.json").read_text())
    assert {Path(item).name for item in generated} == {
        item["file"] for item in manifest["figures"]
    }
    assert all(item["sources"] for item in manifest["figures"])
```

- [ ] **Step 2: Run visualization tests and verify placeholder failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_visualization.py -q
```

Expected: FAIL because the current heatmap draws only a title.

- [ ] **Step 3: Implement the real heatmap and aggregate plots**

```python
def plot_heatmap(results_csv, output_file, metric="avg_travel_time"):
    frame = pd.read_csv(results_csv)
    pivot = frame.pivot_table(
        index="intersection_id", columns="algorithm",
        values=metric, aggfunc="mean",
    )
    figure, axis = plt.subplots(figsize=(10, 8))
    image = axis.imshow(pivot.to_numpy(), aspect="auto", cmap="viridis")
    axis.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=30)
    axis.set_yticks(range(len(pivot.index)), pivot.index)
    figure.colorbar(image, ax=axis, label=metric)
    figure.tight_layout()
    figure.savefig(output_file, dpi=160)
    plt.close(figure)
```

`visualization/report.py` generates algorithm bars, time-series curves, intersection heatmaps, and a representative FCD time-space plot. It writes `manifest.json` with source files, metric, parameters and command.

- [ ] **Step 4: Run tests and generate smoke figures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_visualization.py -q
.\.venv\Scripts\python.exe -m visualization.report --input output/verification/metrics-smoke --output output/verification/figures-smoke
```

Expected: every PNG is non-empty and manifest sources exist.

- [ ] **Step 5: Commit**

```powershell
git add visualization/plots.py visualization/report.py tests/test_visualization.py
git commit -m "feat: generate evidence-grade comparison figures"
```

---

### Task 9: CA-MP Calibration and Resumable 360-Run Matrix

**Files:**
- Create: `experiments/tuning.py`
- Modify: `experiments/runner.py`
- Create: `scripts/run_pdf_matrix.py`
- Create: `tests/test_tuning.py`
- Modify: `tests/test_experiments.py`

**Interfaces:**
- Produces: `tune_ca_mp(output_root) -> dict`.
- Produces: `run_pdf_matrix(output_root, steps, resume=True) -> list[RunResult]`.
- Produces: `selected_params.json`, `matrix.csv`, and `holdout_summary.json`.

- [ ] **Step 1: Write failing matrix and no-leakage tests**

```python
def test_pdf_matrix_has_exact_360_requests():
    requests = build_pdf_matrix(Path("out"), steps=36000)
    assert len(requests) == 360
    assert {r.intersection_id for r in requests} == {str(i) for i in range(1, 21)}
    assert {r.algorithm for r in requests} == {
        "fixed_time", "actuated", "ca_maxpressure"
    }
    assert {r.flow_multiplier for r in requests} == {1.0, 1.5}
    assert {r.seed for r in requests} == {42, 123, 456}


def test_tuning_uses_seed_42_only_and_holdout_uses_123_456():
    assert calibration_seeds() == (42,)
    assert holdout_seeds() == (123, 456)
```

- [ ] **Step 2: Run tests and verify missing modules**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tuning.py tests/test_experiments.py -q
```

Expected: FAIL because tuning and matrix builders do not exist.

- [ ] **Step 3: Implement the bounded calibration grid**

Use exactly:

```python
PARAMETER_GRID = {
    "overflow_occupancy_threshold": (0.85, 0.90, 0.95),
    "prediction_weight": (0.0, 0.15),
    "base_green": (25.0, 35.0, 45.0),
}
CALIBRATION_INTERSECTIONS = ("1", "11", "16")
CALIBRATION_SEEDS = (42,)
HOLDOUT_SEEDS = (123, 456)
```

Rank parameter sets with a documented relative composite:

```text
0.35 * travel_time_ratio
+ 0.30 * queue_ratio
+ 0.15 * fuel_ratio
- 0.20 * throughput_ratio
```

Lower is better. Failed or missing runs receive infinite score. Write every candidate and source run ID to `tuning_results.csv`; freeze the winner in `selected_params.json`.

- [ ] **Step 4: Implement resumable matrix execution**

```python
def is_complete(result_dir: Path) -> bool:
    metadata = read_json(result_dir / "run_metadata.json")
    required = ("metrics.csv", "events.csv", "simulation_log.csv",
                "tripinfo.xml", "stats.xml", "traj.xml", "summary.json")
    return (
        metadata.get("status") == "completed"
        and all((result_dir / name).stat().st_size > 0 for name in required)
    )
```

`run_pdf_matrix()` submits the exact 360 requests through RunService, writes a `matrix_state.json` mapping the stable request key `(intersection, algorithm, flow, seed, steps)` to `run_id` after every run, and uses that file to locate prior run directories. It skips only valid completed runs when `resume=True`, retains failures, and builds `matrix.csv`.

- [ ] **Step 5: Add quick and full CLI modes**

```powershell
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py --quick --output-root output/verification/matrix-quick
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py --steps 36000 --output-root output/verification/matrix-final
```

Quick mode uses intersections 1, 11, 16 and 100 steps but retains all algorithms, flows and seeds. Full mode is exactly 360 runs.

- [ ] **Step 6: Run tests and quick matrix**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tuning.py tests/test_experiments.py tests/test_run_service.py -q
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py --quick --output-root output/verification/matrix-quick
```

Expected: tests pass; quick matrix contains 54 successful or explicitly failed rows and no silently omitted cases.

- [ ] **Step 7: Commit**

```powershell
git add experiments/tuning.py experiments/runner.py scripts/run_pdf_matrix.py tests/test_tuning.py tests/test_experiments.py
git commit -m "feat: add calibrated resumable PDF experiment matrix"
```

---

### Task 10: Docker, Offline Packaging, and Acceptance Orchestration

**Files:**
- Modify: `docker/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `docker/README.md`
- Modify: `scripts/verify_ia_ib.py`
- Create: `scripts/package_offline.py`
- Modify: `tests/test_docker_static.py`
- Modify: `tests/test_validation_scripts.py`

**Interfaces:**
- Container entry point is `python3 -m experiments.runner`.
- Produces: offline manifest and conditional Docker build/run/save/load evidence.
- Acceptance includes runtime, API, variants, metrics, figures and matrix checks.

- [ ] **Step 1: Write failing container and acceptance tests**

```python
def test_container_uses_unified_experiment_entrypoint():
    text = Path("docker/Dockerfile").read_text()
    assert 'ENTRYPOINT ["python3", "-m", "experiments.runner"]' in text


def test_verifier_has_pdf_aligned_checks():
    names = [name for name, _ in checks]
    assert names == [
        "data_integrity", "original_100", "enhanced_100", "enhanced_3600",
        "variant_contracts", "runtime_contracts", "api_contracts",
        "ca_mp_smoke", "exact_metrics", "figure_contracts",
        "matrix", "stress_runs", "docker",
    ]


def test_docker_unavailable_is_not_run_not_pass():
    result = verify_docker(...)
    assert result.status == "not_run"
```

- [ ] **Step 2: Run focused tests and verify failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_docker_static.py tests/test_validation_scripts.py -q
```

Expected: FAIL because the image uses the fixed-time example and the verifier still reports CA-MP as a blocker.

- [ ] **Step 3: Use the unified container entrypoint**

Docker defaults:

```dockerfile
ENTRYPOINT ["python3", "-m", "experiments.runner"]
CMD ["--intersection", "1", "--algorithm", "fixed_time",
     "--steps", "100", "--output-dir", "/app/output/runs"]
```

Compose passes the same arguments and mounts `/app/output`. Keep the build-time compile check and current source copies.

- [ ] **Step 4: Add offline packaging**

`package_offline.py` writes:

- source archive excluding `.git`, `.venv`, caches and generated output;
- `requirements.txt`;
- Docker image digest and `docker save` command/result when Docker exists;
- SHA-256 manifest;
- exact `docker load` and run commands;
- `not_run` for image export when Docker is unavailable.

It must not claim second-machine verification; that requires a separately supplied evidence JSON with machine, timestamp, commands and exit codes.

- [ ] **Step 5: Expand verify_ia_ib**

Each check returns `pass`, `fail`, or `not_run`. Remove the hard-coded AB blocker. Quick mode runs contract tests and the 54-case quick matrix; full mode runs 20 original/enhanced checks, 3600-second enhanced validation, the full 360 matrix, stress runs and Docker when available.

Docker live flow when available:

```powershell
docker build -t ca-mp:ia-ib -f docker/Dockerfile .
docker run --rm -v ${PWD}/output:/app/output ca-mp:ia-ib
docker save ca-mp:ia-ib -o output/verification/ca-mp-ia-ib.tar
docker load -i output/verification/ca-mp-ia-ib.tar
docker run --rm ca-mp:ia-ib
```

- [ ] **Step 6: Run static and quick acceptance**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_docker_static.py tests/test_validation_scripts.py -q
.\.venv\Scripts\python.exe scripts/verify_ia_ib.py --quick --output-root output/verification/quick
```

Expected: all repository-owned checks pass; Docker is `pass` or `not_run`; no CA-MP blocker remains.

- [ ] **Step 7: Commit**

```powershell
git add docker/Dockerfile docker-compose.yml docker/README.md scripts/verify_ia_ib.py scripts/package_offline.py tests/test_docker_static.py tests/test_validation_scripts.py
git commit -m "feat: finalize offline deployment and acceptance gates"
```

---

### Task 11: Documentation, Full Verification, and Truthful Completion Report

**Files:**
- Modify: `README.md`
- Modify: `docs/interface.md`
- Modify: `docs/architecture/interface.md`
- Modify: `docs/deployment.md`
- Modify: `docs/operations/deployment.md`
- Modify: `scripts/README.md`
- Modify: `tests/README.md`
- Modify: `algorithms/README.md`
- Modify: `docs/reports/ia-ib-final-verification.md`
- Modify: `docs/reports/batch-validation-report.md`
- Modify: `tests/test_script_paths.py`

**Interfaces:**
- Documentation commands match the new RunService/API/artifact paths.
- Final report separates repository, automated, local SUMO, Docker and second-machine completion.

- [ ] **Step 1: Add failing documentation contract tests**

```python
def test_active_docs_use_run_id_artifact_layout():
    text = active_docs_text()
    assert "s{seed}/{run_id}" in text
    assert "output_root/csv" not in text


def test_active_docs_have_pdf_api_and_matrix_commands():
    text = active_docs_text()
    assert "docs/api/postman_collection.json" in text
    assert "scripts/run_pdf_matrix.py" in text
    assert "--output-root" in text


def test_active_docs_do_not_call_ca_mp_mvi():
    assert "CA-MP MVI" not in active_docs_text()
```

- [ ] **Step 2: Run doc tests and verify stale-layout failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_script_paths.py -q
```

Expected: FAIL on legacy API, output layouts and CA-MP MVI language.

- [ ] **Step 3: Update all active documentation**

Document:

- environment creation;
- canonical API and Postman/Apifox import;
- `RunRequest`, RunService serialization and stop behavior;
- exact artifact tree with `run_id`;
- scene variation and disturbance syntax;
- CA-MP pressure, overflow, dynamic green and calibration split;
- exact metric sources and `null` semantics;
- quick/full matrix commands;
- Docker build/run/save/load and offline package;
- truthful five-axis completion statuses.

Keep historical migration documents unchanged unless an active link points to stale instructions.

- [ ] **Step 4: Run full automated regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization
.\.venv\Scripts\python.exe -m flake8 algorithms api cloud core engine experiments scenes scripts visualization --max-line-length=100
git diff --check
```

Expected: all pass with no unexplained warnings.

- [ ] **Step 5: Run full SUMO and PDF acceptance**

Run:

```powershell
.\.venv\Scripts\python.exe scripts/verify_ia_ib.py --output-root output/verification/final
```

Expected:

- original 20/20 pass;
- enhanced 20/20 pass through 3600 simulated seconds;
- runtime/API/variant/metrics/figure contracts pass;
- full matrix contains 360 rows;
- stress runs pass;
- Docker is `pass` or `not_run`;
- second-machine status is `pass` only with external evidence, otherwise `not_run`.

- [ ] **Step 6: Inspect outputs and clean only task-generated temporary files**

Run:

```powershell
git status --short --ignored
Get-ChildItem -Recurse -File engine,config,data |
  Where-Object { $_.Name -match '^(tripinfo|stats|traj|queues)\\.xml$' }
Get-ChildItem output/verification -Recurse -File |
  Measure-Object -Property Length -Sum
```

Keep final reports, summaries, manifests and figures referenced by documentation. Remove only smoke/quick directories generated by this implementation and not cited by the report. Do not remove historical outputs or files of uncertain origin.

- [ ] **Step 7: Regenerate and inspect final reports**

Verify the report includes:

```text
repository implementation
automated verification
local SUMO verification
Docker live verification
second-machine reproduction
```

No axis may say `100% verified` when a required external check is `not_run`.

- [ ] **Step 8: Commit documentation and evidence**

```powershell
git add README.md docs/interface.md docs/architecture/interface.md docs/deployment.md docs/operations/deployment.md scripts/README.md tests/README.md algorithms/README.md docs/reports/ia-ib-final-verification.md docs/reports/batch-validation-report.md tests/test_script_paths.py
git commit -m "docs: publish IA and IB PDF-aligned completion evidence"
```

- [ ] **Step 9: Final cleanliness verification**

Run:

```powershell
git status --short
git log --oneline -12
```

Expected: clean worktree and one focused commit per task.
