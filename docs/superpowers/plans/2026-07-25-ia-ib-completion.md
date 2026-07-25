# IA/IB Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every PDF-relevant IA/IB infrastructure responsibility with reproducible SUMO runs, isolated artifacts, automated tests, truthful verification evidence, and cleanup of unused temporary files.

**Architecture:** Repair enhanced SUMO configurations first, then introduce a small `RunArtifacts` boundary shared by TraCI and `SimulationRunner`. Route real SUMO XML, metrics, step logs, events, and metadata into one run directory; integrate the optional EdgeChannel without changing default behavior; finish with IA validation scripts and a role-scoped verification report.

**Tech Stack:** Python 3.10+, pytest, SUMO/TraCI 1.27.1, dataclasses, pathlib, defusedxml, YAML, Dockerfile/Compose static validation.

## Global Constraints

- Treat `data/intersection_data/` as read-only.
- Use SUMO 1.27.1 for live acceptance; retain and report non-fatal signal warnings.
- Do not implement or claim CA-MP algorithm correctness, trained ML, formal 360-run results, report/PPT/video, `v1.0-final`, or submission acceptance.
- Docker build/run is conditional on Docker availability; static consistency is mandatory.
- Write generated validation artifacts under `output/verification/<run-id>/` and delete unreferenced artifacts before completion.
- Never delete pre-existing user files, historical outputs, or files whose provenance is uncertain.
- Every behavior change follows red-green-refactor and receives a focused commit.

---

## File Map

**Create:**

- `requirements-dev.txt`: reproducible test and quality dependencies.
- `engine/artifacts.py`: run-directory paths and metadata lifecycle.
- `scripts/validation_common.py`: shared SUMO execution and result records.
- `scripts/verify_ia_ib.py`: role-scoped acceptance orchestrator and report writer.
- `tests/test_generate_configs.py`: enhanced configuration generation contract.
- `tests/test_artifacts.py`: artifact layout and metadata tests.
- `tests/test_runner_channel.py`: EdgeChannel integration and waiting behavior.
- `tests/test_validation_scripts.py`: IA validation helpers and CLI behavior.
- `tests/test_docker_static.py`: Docker/Compose/current-layout consistency.
- `docs/reports/ia-ib-final-verification.md`: generated final evidence report.

**Modify:**

- `scripts/generate_configs.py`: derive correct relative input paths.
- `engine/configs/demo_1.sumocfg` through `demo_20.sumocfg`: regenerate mechanically.
- `engine/traci_bridge.py`: output overrides, validation, rejected-action details, reconnect state.
- `engine/mock_bridge.py`: maintain the bridge protocol used by runner tests.
- `engine/runner.py`: RunArtifacts, metadata, EdgeChannel, structured terminal states.
- `experiments/runner.py`: deterministic per-run layout and CLI wiring.
- `scripts/validate_all.py`: configurable output root and shared result handling.
- `scripts/batch_validate.py`: configurable steps/output/report and shared result handling.
- `scripts/check_outputs.py`: recursive run-directory contract.
- `scripts/check_seed_repro.py`: isolated run directories and cleanup-friendly output.
- `scripts/stress_memory.py`: selectable supported algorithm and complete resource result.
- `docker/Dockerfile`, `docker-compose.yml`, `.dockerignore`: current-layout consistency.
- `docs/deployment.md`, `docs/interface.md`, `scripts/README.md`, `tests/README.md`, `README.md`, `docs/reports/w6-review-issues.md`: verified current behavior and boundaries.

---

### Task 1: Reproducible Developer Test Environment

**Files:**
- Create: `requirements-dev.txt`
- Modify: `pyproject.toml`
- Test: `tests/test_flat_layout.py`

**Interfaces:**
- Consumes: runtime dependencies from `requirements.txt`.
- Produces: `.venv` commands that expose `pytest` and `flake8` without changing global Python.

- [ ] **Step 1: Add a failing development-metadata test**

```python
from pathlib import Path


def test_development_requirements_pin_test_tools():
    text = Path("requirements-dev.txt").read_text(encoding="utf-8")
    assert "-r requirements.txt" in text
    assert "pytest>=8.0,<9" in text
    assert "flake8>=7.0,<8" in text
```

- [ ] **Step 2: Run the focused test and confirm the missing-file failure**

Run: `python -m pytest tests/test_flat_layout.py::test_development_requirements_pin_test_tools -q`

Expected: FAIL with `FileNotFoundError: requirements-dev.txt`.

- [ ] **Step 3: Add the exact development dependencies**

```text
-r requirements.txt
pytest>=8.0,<9
flake8>=7.0,<8
```

Add this optional dependency block to `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.0,<9",
  "flake8>=7.0,<8",
]
```

- [ ] **Step 4: Create the local environment and install dependencies**

Run:

```powershell
& 'C:\Users\peng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest --version
```

Expected: pytest 8.x is reported. If package download is blocked, request network approval and rerun the same pip command.

- [ ] **Step 5: Run the focused test**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_flat_layout.py::test_development_requirements_pin_test_tools -q`

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```powershell
git add requirements-dev.txt pyproject.toml tests/test_flat_layout.py
git commit -m "build: add reproducible test environment"
```

---

### Task 2: Correct and Reproducible Enhanced SUMO Configurations

**Files:**
- Create: `tests/test_generate_configs.py`
- Modify: `scripts/generate_configs.py`
- Modify: `engine/configs/demo_1.sumocfg` through `engine/configs/demo_20.sumocfg`

**Interfaces:**
- Consumes: `scripts.generate_configs.DATA` and `OUT_DIR`.
- Produces: `relative_input_path(source: Path, output_dir: Path) -> str` and `generate_configs() -> list[Path]`.

- [ ] **Step 1: Write failing path and generation tests**

```python
from pathlib import Path
from scripts.generate_configs import generate_configs, relative_input_path


def test_relative_input_path_uses_config_directory(tmp_path):
    out = tmp_path / "engine" / "configs"
    source = tmp_path / "data" / "intersection_data" / "1" / "sumo工程" / "demo_1.net.xml"
    assert relative_input_path(source, out) == "../../data/intersection_data/1/sumo工程/demo_1.net.xml"


def test_generate_configs_writes_twenty_resolvable_configs(tmp_path):
    data = Path("data/intersection_data").resolve()
    out = tmp_path / "engine" / "configs"
    written = generate_configs(data_root=data, output_dir=out)
    assert len(written) == 20
    text = written[0].read_text(encoding="utf-8")
    assert "../../../data" not in text
    assert "demo_1.net.xml" in text


def test_generate_configs_preserves_original_step_length(tmp_path):
    written = generate_configs(
        data_root=Path("data/intersection_data").resolve(),
        output_dir=tmp_path / "configs",
    )
    route_1 = written[0].read_text(encoding="utf-8")
    route_11 = written[10].read_text(encoding="utf-8")
    assert "<step-length" not in route_1
    assert '<step-length value="0.1"/>' in route_11
```

- [ ] **Step 2: Verify tests fail on missing functions**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_generate_configs.py -q`

Expected: collection FAIL because `generate_configs` and `relative_input_path` are not exported.

- [ ] **Step 3: Implement path derivation and a callable generator**

```python
import os


def relative_input_path(source: Path, output_dir: Path) -> str:
    return Path(os.path.relpath(source, output_dir)).as_posix()


def generate_configs(data_root: Path = DATA, output_dir: Path = OUT_DIR) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for n in range(1, 21):
        src_dir = data_root / str(n) / "sumo工程"
        original = (src_dir / f"demo_{n}.sumocfg").read_text(encoding="utf-8")
        step_match = re.search(r'<step-length\s+value="([^"]+)"', original)
        step_length = (
            f'        <step-length value="{step_match.group(1)}"/>\n'
            if step_match else ""
        )
        config = TEMPLATE.format(
            net=relative_input_path(src_dir / f"demo_{n}.net.xml", output_dir),
            rou=relative_input_path(src_dir / f"demo_{n}.rou.xml", output_dir),
            step_length=step_length,
            ignore_route_errors=(
                "    <processing>\n"
                '        <ignore-route-errors value="true"/>\n'
                "    </processing>\n"
                if "ignore-route-errors" in original else ""
            ),
            queue_output=(
                '        <queue-output value="queues.xml"/>\n'
                if "queue-output" in original else ""
            ),
        )
        target = output_dir / f"demo_{n}.sumocfg"
        target.write_text(config, encoding="utf-8")
        written.append(target)
    return written
```

Make `main()` call `generate_configs()` and print the returned count.

- [ ] **Step 4: Run tests and regenerate tracked configurations**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_generate_configs.py -q
.\.venv\Scripts\python.exe scripts/generate_configs.py
rg -n "\.\./\.\./\.\./data" engine/configs
```

Expected: tests pass, 20 configurations are generated, and `rg` returns no matches.

- [ ] **Step 5: Smoke-test representative enhanced configurations**

Run:

```powershell
$ids = 1, 11, 16
foreach ($id in $ids) {
  $dir = "output/verification/config-smoke/$id"
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  sumo -c "engine/configs/demo_$id.sumocfg" --no-step-log true -e 100 `
    --tripinfo-output "$dir/tripinfo.xml" --summary-output "$dir/stats.xml" `
    --fcd-output "$dir/traj.xml"
  if ($LASTEXITCODE -ne 0) { throw "enhanced config failed: $id" }
}
```

Expected: routes 1, 11, and 16 exit with code 0. Task 3 performs the full 20-route smoke after the shared validation CLI exists.

- [ ] **Step 6: Commit**

```powershell
git add scripts/generate_configs.py engine/configs tests/test_generate_configs.py
git commit -m "fix: regenerate valid SUMO configurations"
```

---

### Task 3: Shared IA Validation Primitives

**Files:**
- Create: `scripts/validation_common.py`
- Create: `tests/test_validation_scripts.py`
- Modify: `scripts/validate_all.py`
- Modify: `scripts/batch_validate.py`

**Interfaces:**
- Consumes: a SUMO configuration path, end time, and output directory.
- Produces: `ValidationResult` and `run_sumo_validation(config, end, output_dir) -> ValidationResult`.

- [ ] **Step 1: Write failing unit tests for result classification**

```python
from pathlib import Path
from unittest.mock import patch
from scripts.validation_common import run_sumo_validation


def test_validation_distinguishes_warning_from_error(tmp_path):
    completed = type("Result", (), {
        "returncode": 0,
        "stdout": "",
        "stderr": "Warning: signal phase\n",
    })()
    with patch("scripts.validation_common.subprocess.run", return_value=completed):
        result = run_sumo_validation(Path("demo.sumocfg"), 100, tmp_path)
    assert result.ok is True
    assert result.warnings == ["Warning: signal phase"]
    assert result.errors == []


def test_validation_rejects_error_text_even_with_zero_exit(tmp_path):
    completed = type("Result", (), {
        "returncode": 0,
        "stdout": "",
        "stderr": "Error: inaccessible network\n",
    })()
    with patch("scripts.validation_common.subprocess.run", return_value=completed):
        result = run_sumo_validation(Path("demo.sumocfg"), 100, tmp_path)
    assert result.ok is False
    assert result.errors == ["Error: inaccessible network"]
```

- [ ] **Step 2: Run tests and verify import failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_validation_scripts.py -q`

Expected: collection FAIL because `scripts.validation_common` does not exist.

- [ ] **Step 3: Implement the shared immutable result and runner**

```python
from dataclasses import dataclass
from pathlib import Path
import subprocess
import time


@dataclass(frozen=True)
class ValidationResult:
    config: Path
    ok: bool
    returncode: int
    elapsed_seconds: float
    warnings: list[str]
    errors: list[str]
    output_dir: Path


def run_sumo_validation(config: Path, end: int, output_dir: Path) -> ValidationResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    command = [
        "sumo", "-c", str(config), "--no-step-log", "true", "-e", str(end),
        "--tripinfo-output", (output_dir / "tripinfo.xml").resolve().as_posix(),
        "--summary-output", (output_dir / "stats.xml").resolve().as_posix(),
        "--fcd-output", (output_dir / "traj.xml").resolve().as_posix(),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    lines = completed.stderr.splitlines()
    warnings = [line for line in lines if line.startswith("Warning:")]
    errors = [line for line in lines if line.startswith("Error:")]
    return ValidationResult(
        config=config,
        ok=completed.returncode == 0 and not errors,
        returncode=completed.returncode,
        elapsed_seconds=time.perf_counter() - started,
        warnings=warnings,
        errors=errors,
        output_dir=output_dir,
    )
```

- [ ] **Step 4: Give both validation CLIs explicit output and report options**

`validate_all.py` must accept `--steps`, `--output-root`, and route remaining positional values as intersection IDs. `batch_validate.py` must accept `--steps`, `--output-root`, `--report`, and `--no-report`; report writing occurs only when `--report` is supplied or the default report is explicitly enabled.

Use this parsing shape in both scripts:

```python
parser.add_argument("ids", nargs="*", type=int)
parser.add_argument("--steps", type=int, default=100)
parser.add_argument("--output-root", type=Path, required=True)
```

- [ ] **Step 5: Run unit and live smoke checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_validation_scripts.py tests/test_script_paths.py -q
.\.venv\Scripts\python.exe scripts/validate_all.py --steps 100 --output-root output/verification/original-smoke
.\.venv\Scripts\python.exe scripts/batch_validate.py --steps 100 --output-root output/verification/enhanced-smoke --no-report
```

Expected: unit tests pass and both live commands report `20/20 PASS`.

- [ ] **Step 6: Commit**

```powershell
git add scripts/validation_common.py scripts/validate_all.py scripts/batch_validate.py tests/test_validation_scripts.py
git commit -m "feat: unify SUMO validation commands"
```

---

### Task 4: Isolated Run Artifact Contract

**Files:**
- Create: `engine/artifacts.py`
- Create: `tests/test_artifacts.py`

**Interfaces:**
- Consumes: `root`, `intersection_id`, `algorithm`, `flow_multiplier`, `seed`.
- Produces: `RunArtifacts.create(...) -> RunArtifacts`, path properties, `write_metadata(status, reason, generated_files)`.

- [ ] **Step 1: Write failing artifact-layout tests**

```python
import json
from engine.artifacts import RunArtifacts


def test_run_artifacts_create_stable_layout(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "16", "actuated", 1.5, 42)
    assert artifacts.run_dir == tmp_path / "i16" / "actuated" / "x1.5" / "s42"
    assert artifacts.metrics.name == "metrics.csv"
    assert artifacts.events.name == "events.csv"
    assert artifacts.tripinfo.name == "tripinfo.xml"


def test_write_metadata_is_atomic_and_structured(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    artifacts.metrics.write_text("step\n0\n", encoding="utf-8")
    artifacts.write_metadata(
        "completed", "", [artifacts.metrics],
        started_at="2026-07-25T10:00:00+08:00",
        ended_at="2026-07-25T10:01:00+08:00",
        sumo_version="1.27.1",
    )
    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["intersection_id"] == "1"
    assert payload["generated_files"] == ["metrics.csv"]
    assert payload["sumo_version"] == "1.27.1"
    assert payload["started_at"] < payload["ended_at"]
```

- [ ] **Step 2: Run tests and confirm missing-module failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_artifacts.py -q`

Expected: collection FAIL because `engine.artifacts` does not exist.

- [ ] **Step 3: Implement the dataclass and atomic metadata write**

```python
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class RunArtifacts:
    run_dir: Path
    intersection_id: str
    algorithm: str
    flow_multiplier: float
    seed: int

    @classmethod
    def create(cls, root: Path, intersection_id: str, algorithm: str,
               flow_multiplier: float, seed: int) -> "RunArtifacts":
        run_dir = Path(root) / f"i{intersection_id}" / algorithm / f"x{flow_multiplier:g}" / f"s{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return cls(run_dir, intersection_id, algorithm, flow_multiplier, seed)

    metrics = property(lambda self: self.run_dir / "metrics.csv")
    step_log = property(lambda self: self.run_dir / "simulation_log.csv")
    events = property(lambda self: self.run_dir / "events.csv")
    tripinfo = property(lambda self: self.run_dir / "tripinfo.xml")
    stats = property(lambda self: self.run_dir / "stats.xml")
    trajectory = property(lambda self: self.run_dir / "traj.xml")
    queues = property(lambda self: self.run_dir / "queues.xml")
    metadata = property(lambda self: self.run_dir / "run_metadata.json")

    def write_metadata(self, status: str, reason: str, generated_files: list[Path],
                       started_at: str, ended_at: str, sumo_version: str) -> None:
        payload = {
            "intersection_id": self.intersection_id,
            "algorithm": self.algorithm,
            "flow_multiplier": self.flow_multiplier,
            "seed": self.seed,
            "status": status,
            "reason": reason,
            "started_at": started_at,
            "ended_at": ended_at,
            "sumo_version": sumo_version,
            "generated_files": [path.name for path in generated_files if path.exists()],
        }
        temporary = self.metadata.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.metadata)
```

- [ ] **Step 4: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_artifacts.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add engine/artifacts.py tests/test_artifacts.py
git commit -m "feat: define isolated run artifacts"
```

---

### Task 5: TraCI Output Redirection and Action Validation

**Files:**
- Modify: `engine/traci_bridge.py`
- Modify: `engine/mock_bridge.py`
- Modify: `tests/test_seed.py`
- Modify: `tests/test_resilience.py`
- Create: `tests/test_traci_outputs.py`

**Interfaces:**
- Consumes: optional `artifacts: RunArtifacts`.
- Produces: `_build_cmd()` with absolute output overrides and `apply_actions(actions) -> list[str]` rejection details.

- [ ] **Step 1: Write failing output and invalid-action tests**

```python
from pathlib import Path
from engine.artifacts import RunArtifacts
from engine.traci_bridge import TraCIBridge
from core.types import ControlAction


def test_build_cmd_redirects_all_sumo_outputs(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    bridge = TraCIBridge(Path("demo_1.sumocfg"), artifacts=artifacts, seed=42)
    cmd = bridge._build_cmd()
    assert cmd[cmd.index("--tripinfo-output") + 1] == artifacts.tripinfo.resolve().as_posix()
    assert cmd[cmd.index("--summary-output") + 1] == artifacts.stats.resolve().as_posix()
    assert cmd[cmd.index("--fcd-output") + 1] == artifacts.trajectory.resolve().as_posix()


def test_invalid_phase_returns_rejection_without_calling_traci():
    bridge = TraCIBridge(Path("demo_1.sumocfg"))
    bridge.tls_id = "tls"
    rejected = bridge.apply_actions([
        ControlAction("tls", "set_phase", "north", "invalid phase")
    ])
    assert rejected == ["set_phase value must be an integer: 'north'"]
```

- [ ] **Step 2: Run focused tests and verify signature failures**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_traci_outputs.py -q`

Expected: FAIL because `artifacts` is not accepted and `apply_actions` returns `None`.

- [ ] **Step 3: Add output flags and explicit rejections**

Add `artifacts: RunArtifacts | None = None` to `TraCIBridge.__init__`. Append these command arguments when artifacts are present:

```python
cmd.extend([
    "--tripinfo-output", self.artifacts.tripinfo.resolve().as_posix(),
    "--summary-output", self.artifacts.stats.resolve().as_posix(),
    "--fcd-output", self.artifacts.trajectory.resolve().as_posix(),
])
```

Implement `apply_actions` with this return contract:

```python
def apply_actions(self, actions: List[ControlAction]) -> list[str]:
    rejected: list[str] = []
    for action in actions:
        if action.tls_id != self.tls_id:
            rejected.append(f"unknown tls_id: {action.tls_id!r}")
            continue
        if action.action_type == "set_phase":
            if not isinstance(action.value, int):
                rejected.append(f"set_phase value must be an integer: {action.value!r}")
                continue
            traci.trafficlight.setPhase(action.tls_id, action.value)
        elif action.action_type == "set_phase_duration":
            try:
                duration = float(action.value)
            except (TypeError, ValueError):
                rejected.append(f"set_phase_duration value must be numeric: {action.value!r}")
                continue
            if duration <= 0:
                rejected.append(f"set_phase_duration value must be positive: {duration!r}")
                continue
            traci.trafficlight.setPhaseDuration(action.tls_id, duration)
        elif action.action_type == "set_program":
            program = str(action.value).strip()
            if not program:
                rejected.append("set_program value must be non-empty")
                continue
            traci.trafficlight.setProgram(action.tls_id, program)
        else:
            rejected.append(f"unknown action_type: {action.action_type!r}")
    return rejected
```

Make `MockBridge.apply_actions()` apply the same TLS/type/value checks, return identical rejection strings, and collect only valid actions. This keeps the bridge protocol meaningful in runner tests without requiring SUMO.

- [ ] **Step 4: Strengthen restart state tests**

Add assertions that restart clears `tls_id`, `_controlled_lanes`, and `_inbound_lanes` before `start()` repopulates them. Preserve the existing retry limit and idempotent close behavior.

- [ ] **Step 5: Run bridge tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_traci_outputs.py tests/test_seed.py tests/test_resilience.py tests/test_mock_bridge.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add engine/traci_bridge.py engine/mock_bridge.py tests/test_traci_outputs.py tests/test_seed.py tests/test_resilience.py
git commit -m "feat: isolate TraCI outputs and validate actions"
```

---

### Task 6: Runner Metadata and EdgeChannel Integration

**Files:**
- Modify: `engine/runner.py`
- Modify: `engine/events.py`
- Create: `tests/test_runner_channel.py`
- Modify: `tests/test_events.py`
- Modify: `tests/test_step_log.py`

**Interfaces:**
- Consumes: `artifacts: RunArtifacts | None`, `state_channel: EdgeChannel | None`.
- Produces: `run()` terminal metadata states `completed`, `disconnected`, `interrupted`, or `failed`.

- [ ] **Step 1: Write failing delayed-channel and metadata tests**

```python
import csv
import json
from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import Scene, SceneMeta
from engine.artifacts import RunArtifacts
from engine.edge_channel import EdgeChannel
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner


class CountingAlgorithm(FixedTimeAlgorithm):
    def __init__(self):
        self.steps: list[int] = []

    def step(self, state):
        self.steps.append(state.step)
        return []


class InvalidActionAlgorithm(FixedTimeAlgorithm):
    def step(self, state):
        from core.types import ControlAction
        return [ControlAction(state.tls_id, "set_phase", "north", "bad phase")]


def make_scene() -> Scene:
    return Scene(SceneMeta(
        intersection_id="1", name="test",
        sumo_net="x.net.xml", sumo_rou="x.rou.xml", sumo_flow="x.flow.xml",
        sumo_turn="x.turn.xml", sumo_cfg="x.sumocfg", timing_xlsx="x.xlsx",
    ))


def test_delayed_channel_waits_without_stopping_simulation(tmp_path):
    algorithm = CountingAlgorithm()
    artifacts = RunArtifacts.create(tmp_path, "1", algorithm.name, 1.0, 42)
    runner = SimulationRunner(
        make_scene(), algorithm, bridge=MockBridge(), artifacts=artifacts,
        state_channel=EdgeChannel(delay_steps=2),
    )
    runner.run(5)
    assert algorithm.steps == [0, 1, 2]
    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    assert [row["type"] for row in events].count("channel_wait") == 2


def test_successful_run_writes_completed_metadata(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    SimulationRunner(
        make_scene(), FixedTimeAlgorithm(), bridge=MockBridge(), artifacts=artifacts,
    ).run(3)
    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert "events.csv" in payload["generated_files"]


def test_invalid_action_is_logged_and_does_not_stop_run(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "invalid", 1.0, 42)
    SimulationRunner(
        make_scene(), InvalidActionAlgorithm(), bridge=MockBridge(), artifacts=artifacts,
    ).run(2)
    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    assert any(row["type"] == "invalid_action" for row in events)
    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
```

- [ ] **Step 2: Run tests and verify constructor failures**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_runner_channel.py -q`

Expected: FAIL because `artifacts` and `state_channel` are not accepted.

- [ ] **Step 3: Wire artifact defaults and channel flow**

When `artifacts` is present, set collector/log paths from it and pass it into a newly created TraCIBridge. Split `_tick` into raw simulation state and control state:

```python
raw_state = self.bridge.get_state()
control_state = raw_state
if self.state_channel is not None:
    self.state_channel.send(raw_state)
    control_state = self.state_channel.receive()
if control_state is None:
    actions = []
    self.event_logger.log(step, "channel_wait", "delayed state unavailable")
else:
    actions = self.algorithm.step(control_state)
for detail in self.bridge.apply_actions(actions):
    self.event_logger.log(step, "invalid_action", detail)
```

Metrics and step logs must use `raw_state`; algorithm actions use `control_state`.

- [ ] **Step 4: Implement truthful terminal metadata**

Track UTC-aware ISO `started_at`/`ended_at`, `sumo_version`, `status`, and `reason` around the run loop. Add `self._terminal_reason = ""`; `_tick()` sets it to `"fatal TraCI error"` or `"bridge returned no simulation time"` before returning `False`. On a `False` tick use `disconnected`; on success use `completed`; KeyboardInterrupt uses `interrupted` and is re-raised after cleanup; all other exceptions use `failed` and are re-raised. In `finally`, save collectors/events, close the bridge, then call `artifacts.write_metadata(...)` with every required field.

- [ ] **Step 5: Run runner and logging tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_runner_channel.py tests/test_events.py tests/test_step_log.py tests/test_resilience.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add engine/runner.py engine/events.py tests/test_runner_channel.py tests/test_events.py tests/test_step_log.py
git commit -m "feat: integrate edge channel and run metadata"
```

---

### Task 7: Deterministic Experiment CLI and Output Checks

**Files:**
- Modify: `experiments/runner.py`
- Modify: `scripts/check_outputs.py`
- Modify: `scripts/check_seed_repro.py`
- Modify: `tests/test_experiments.py`
- Modify: `tests/test_seed.py`

**Interfaces:**
- Consumes: CLI `--intersection`, `--algorithm`, `--flow-multiplier`, `--seed`, `--steps`, `--output-dir`.
- Produces: `build_artifacts(args) -> RunArtifacts`, a run path containing all mandatory files, and nonzero exit on incomplete output.

- [ ] **Step 1: Write failing deterministic-layout tests**

```python
from pathlib import Path
from experiments.runner import build_artifacts, parse_args


def test_build_artifacts_encodes_all_run_dimensions(tmp_path):
    args = parse_args([
        "--intersection", "16", "--algorithm", "actuated",
        "--flow-multiplier", "1.5", "--seed", "123",
        "--output-dir", str(tmp_path),
    ])
    artifacts = build_artifacts(args)
    assert artifacts.run_dir == tmp_path / "i16" / "actuated" / "x1.5" / "s123"
```

- [ ] **Step 2: Run tests and verify missing-function failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_experiments.py::test_build_artifacts_encodes_all_run_dimensions -q`

Expected: collection FAIL because `build_artifacts` does not exist.

- [ ] **Step 3: Implement CLI validation and artifact wiring**

```python
def build_artifacts(args: argparse.Namespace) -> RunArtifacts:
    root = Path(args.output_dir) if args.output_dir else get_config().path("paths.output_root") / "runs"
    return RunArtifacts.create(
        root, args.intersection, args.algorithm, args.flow_multiplier, args.seed,
    )
```

Reject intersection IDs outside `1..20`, `steps <= 0`, `seed < 0`, and `flow_multiplier <= 0` through `parser.error(...)`. `run_single()` must pass the same RunArtifacts to `SimulationRunner` and TraCIBridge.

- [ ] **Step 4: Make output checking recursive and contract-based**

Replace the fixed three-level glob with recursive metadata discovery:

```python
for metadata in root.rglob("run_metadata.json"):
    run_dir = metadata.parent
    required = ["metrics.csv", "simulation_log.csv", "events.csv", "tripinfo.xml", "stats.xml", "traj.xml"]
    for name in required:
        path = run_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(path)
```

Return nonzero when no run directories are found or any mandatory file is absent.

- [ ] **Step 5: Update seed reproduction script**

Use three separate RunArtifacts directories below the supplied `--output-root`; compare `metrics.csv` rows after excluding metadata timestamps. Add `--steps` and `--output-root` arguments so acceptance can isolate and clean the generated evidence.

- [ ] **Step 6: Run CLI and MockBridge tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_experiments.py tests/test_seed.py tests/test_artifacts.py -q`

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add experiments/runner.py scripts/check_outputs.py scripts/check_seed_repro.py tests/test_experiments.py tests/test_seed.py
git commit -m "feat: standardize experiment run outputs"
```

---

### Task 8: IA/IB Pressure and Resource Verification

**Files:**
- Modify: `scripts/stress_memory.py`
- Modify: `tests/test_experiments.py`
- Create: `scripts/verify_ia_ib.py`

**Interfaces:**
- Consumes: a verification root, supported baseline algorithm, intersections, steps, and optional full mode.
- Produces: machine-readable `verification.json` and Markdown `docs/reports/ia-ib-final-verification.md`.

- [ ] **Step 1: Write failing stress argument tests**

```python
from scripts.stress_memory import parse_stress_args


def test_stress_defaults_to_supported_baseline():
    args = parse_stress_args([])
    assert args.algorithm == "actuated"
    assert args.flow_multiplier == 1.5
    assert args.intersections == ["1", "11", "16"]
```

- [ ] **Step 2: Run focused test and verify missing parser**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_experiments.py::test_stress_defaults_to_supported_baseline -q`

Expected: FAIL because `parse_stress_args` does not exist.

- [ ] **Step 3: Refactor stress script around explicit baselines**

Add `--algorithm {fixed_time,actuated}`, `--intersections`, `--steps`, `--output-root`, and `--max-python-mib` arguments. Default to Actuated, intersections 1/11/16, 3600 control steps, and 1024 MiB. Record control steps, simulated time, wall duration, Python peak, output sizes, and exit status per run; return nonzero on any failed threshold.

- [ ] **Step 4: Implement the acceptance orchestrator**

`scripts/verify_ia_ib.py` must:

```python
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import time


@dataclass
class CheckResult:
    name: str
    status: str
    duration_seconds: float
    command: str
    warnings: list[str]
    errors: list[str]


checks = [
    ("data_integrity", verify_data_integrity),
    ("original_100", verify_original_configs),
    ("enhanced_100", verify_enhanced_configs),
    ("enhanced_3600", verify_enhanced_full),
    ("baseline_runs", verify_baseline_runs),
    ("stress_runs", verify_stress_runs),
    ("docker_static", verify_docker_static),
]


def verify_data_integrity(_: Path) -> CheckResult:
    started = time.perf_counter()
    errors: list[str] = []
    for intersection in range(1, 21):
        root = Path("data/intersection_data") / str(intersection)
        files = list(root.rglob("*"))
        expected = [
            f"demo_{intersection}.net.xml", f"demo_{intersection}.rou.xml",
            f"demo_{intersection}.flow.xml", f"demo_{intersection}.sumocfg",
            f"demo_{intersection}.turn.xml",
        ]
        present = {path.name for path in files if path.is_file()}
        errors.extend(f"intersection {intersection} missing {name}" for name in expected if name not in present)
        if not any(path.suffix == ".xlsx" for path in files):
            errors.append(f"intersection {intersection} missing timing workbook")
    return CheckResult(
        "data_integrity", "pass" if not errors else "fail",
        time.perf_counter() - started, "static data inventory", [], errors,
    )


def render_markdown(results: list[CheckResult], docker_available: bool,
                    ab_blockers: list[str]) -> str:
    lines = ["# IA/IB Final Verification", "", "| Check | Status | Seconds |", "|---|---:|---:|"]
    lines.extend(f"| {item.name} | {item.status} | {item.duration_seconds:.2f} |" for item in results)
    lines.extend(["", "## Docker", "", "live validation: " + ("run" if docker_available else "not run: Docker unavailable")])
    lines.extend(["", "## Cross-role blockers", ""] + [f"- AB blocker: {item}" for item in ab_blockers])
    for item in results:
        lines.extend(["", f"## {item.name}", "", f"Command: `{item.command}`"])
        lines.extend([f"- warning: {value}" for value in item.warnings])
        lines.extend([f"- error: {value}" for value in item.errors])
    return "\n".join(lines) + "\n"
```

The original/enhanced functions call `run_sumo_validation()` for the required 20 configurations and fold all warnings/errors into one CheckResult. Baseline and stress functions invoke the exact Task 7/8 CLI functions for intersections 1/11/16. `verify_docker_static` runs the Task 9 pytest file and checks `shutil.which("docker")` before any live command.

Support `--quick` to omit `enhanced_3600` and long stress runs, and `--output-root` for all generated files. Serialize `[asdict(result) for result in results]` to `<output-root>/verification.json` first, then write `render_markdown(...)` to `docs/reports/ia-ib-final-verification.md`. Return exit code 1 when any status is `fail`; `not run` is permitted only for Docker live validation.

- [ ] **Step 5: Run quick acceptance**

Run: `.\.venv\Scripts\python.exe scripts/verify_ia_ib.py --quick --output-root output/verification/quick`

Expected: all IA/IB quick checks pass; Docker is `not run` when unavailable; CA-MP is listed as an AB blocker rather than an IA/IB failure.

- [ ] **Step 6: Commit**

```powershell
git add scripts/stress_memory.py scripts/verify_ia_ib.py tests/test_experiments.py
git commit -m "feat: automate IA and IB acceptance checks"
```

---

### Task 9: Docker and Compose Static Consistency

**Files:**
- Create: `tests/test_docker_static.py`
- Modify: `docker/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `.dockerignore`

**Interfaces:**
- Consumes: current flat repository paths and runtime entrypoint.
- Produces: a statically valid image context and a conditional live Docker check.

- [ ] **Step 1: Write failing static consistency tests**

```python
from pathlib import Path


def test_dockerfile_copies_every_runtime_package():
    text = Path("docker/Dockerfile").read_text(encoding="utf-8")
    for package in ["algorithms", "cloud", "core", "engine", "experiments", "scenes"]:
        assert f"COPY {package}/ ./{package}/" in text
    assert "ENTRYPOINT [\"python3\", \"examples/run_fixed_time.py\"]" in text
    assert "RUN python3 -m compileall -q" in text


def test_compose_mounts_output_and_uses_current_dockerfile():
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "dockerfile: docker/Dockerfile" in text
    assert "./output:/app/output" in text
    assert "init: true" in text


def test_dockerignore_keeps_required_source():
    text = Path(".dockerignore").read_text(encoding="utf-8")
    assert "data/intersection_data" not in text
    assert "engine/configs" not in text
```

- [ ] **Step 2: Run tests and inspect any current mismatch**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_docker_static.py -q`

Expected: FAIL because the current Dockerfile has no build-time compile check and Compose does not enable init-based signal forwarding.

- [ ] **Step 3: Make Docker files match the verified local entrypoint**

Keep Ubuntu 22.04 plus `ppa:sumo/stable`, install `requirements.txt`, copy only required runtime directories, set `SUMO_HOME=/usr/share/sumo`, and mount `/app/output`. Add a build-time `python3 -m compileall -q` check after source copies and set `init: true` on the Compose service for clean signal forwarding.

- [ ] **Step 4: Run static and conditional live checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_docker_static.py -q
docker --version
```

Expected: static tests pass. If Docker exists, additionally run `docker build -t ca-mp:ia-ib -f docker/Dockerfile .` and `docker run --rm ca-mp:ia-ib 1`; otherwise record `not run: Docker unavailable`.

- [ ] **Step 5: Commit**

```powershell
git add docker/Dockerfile docker-compose.yml .dockerignore tests/test_docker_static.py
git commit -m "test: validate container deployment contract"
```

---

### Task 10: Documentation and Role-Scoped Evidence

**Files:**
- Modify: `docs/deployment.md`
- Modify: `docs/interface.md`
- Modify: `scripts/README.md`
- Modify: `tests/README.md`
- Modify: `README.md`
- Modify: `docs/reports/w6-review-issues.md`
- Create/Modify: `docs/reports/ia-ib-final-verification.md`

**Interfaces:**
- Consumes: verified CLI names, run layout, test counts, live results, Docker state, AB blockers.
- Produces: one current source of truth for IA/IB setup, interfaces, commands, and acceptance evidence.

- [ ] **Step 1: Add a failing documentation contract test**

Add to `tests/test_script_paths.py`:

```python
def test_active_docs_reference_current_verification_commands():
    deployment = (REPOSITORY_ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
    scripts = (REPOSITORY_ROOT / "scripts" / "README.md").read_text(encoding="utf-8")
    assert "scripts/verify_ia_ib.py" in deployment
    assert "output/verification" in deployment
    assert "scripts/verify_ia_ib.py" in scripts
```

- [ ] **Step 2: Run the documentation test and verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_script_paths.py::test_active_docs_reference_current_verification_commands -q`

Expected: FAIL because the new command is not yet documented.

- [ ] **Step 3: Update documentation with exact verified commands**

Document local `.venv` setup, quick/full verification, per-run output layout, EdgeChannel data flow, terminal metadata statuses, Docker conditional validation, and cleanup policy. Update README IA/IB statuses only from fresh results. Keep AB/EX/DA/DB limitations explicit.

Mark only IA/IB-owned entries closed in `w6-review-issues.md`; retain CA-MP and exact-metric issues under their owners.

- [ ] **Step 4: Generate and inspect the final report**

Run: `.\.venv\Scripts\python.exe scripts/verify_ia_ib.py --output-root output/verification/final`

Expected: `docs/reports/ia-ib-final-verification.md` contains every required check, real commands, durations, warnings, Docker status, and AB blockers.

- [ ] **Step 5: Run documentation and link checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_script_paths.py -q
rg -n "ca_mp/|tests/unit|tests/integration|scripts/simulation" README.md docs scripts/README.md tests/README.md
```

Expected: tests pass; `rg` returns only explicitly labelled historical migration references.

- [ ] **Step 6: Commit**

```powershell
git add docs/deployment.md docs/interface.md docs/reports/ia-ib-final-verification.md docs/reports/w6-review-issues.md scripts/README.md tests/README.md README.md tests/test_script_paths.py
git commit -m "docs: record IA and IB acceptance evidence"
```

---

### Task 11: Full Regression, Live Acceptance, and Temporary-File Cleanup

**Files:**
- Modify only if a verification defect is found; otherwise no source edits.

**Interfaces:**
- Consumes: all prior tasks and `output/verification/final`.
- Produces: clean worktree, retained Markdown evidence, and no unreferenced generated artifacts.

- [ ] **Step 1: Run the complete automated suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization
.\.venv\Scripts\python.exe -m flake8 engine cloud experiments scripts --max-line-length=100
git diff --check
```

Expected: all tests pass, compileall is silent with exit code 0, flake8 has no errors, and diff check is clean.

- [ ] **Step 2: Run full IA/IB live acceptance**

Run: `.\.venv\Scripts\python.exe scripts/verify_ia_ib.py --output-root output/verification/final`

Expected: original 20x100, enhanced 20x100, enhanced 20x3600 seconds, baseline runner, seed, stress, and static Docker checks pass. Docker live result is pass or explicitly `not run`; CA-MP remains an AB-owned blocker if still invalid.

- [ ] **Step 3: Inventory generated files before cleanup**

Run:

```powershell
git status --short --ignored
Get-ChildItem -Recurse -File engine,config,data | Where-Object { $_.Name -match '^(tripinfo|stats|traj|queues)\.xml$' }
Get-ChildItem -Recurse -File | Where-Object { $_.Name -match '^(page_.*\.png|temp_.*\.pdf|.*\.tmp)$' }
```

Expected: no run products exist under source/config/data; all verification products are under `output/verification/final`.

- [ ] **Step 4: Delete only this run's unreferenced temporary artifacts**

Resolve every deletion target to an absolute path and confirm it is inside `output/verification/final` or a cache directory created during this implementation. Remove intermediate smoke/quick directories and unreferenced XML/CSV/log files; retain the Markdown report and any compact JSON summary it references. Do not delete any pre-existing or uncertain file.

- [ ] **Step 5: Re-run evidence and cleanliness checks**

Run:

```powershell
git status --short
git diff --check
Select-String -Path docs/reports/ia-ib-final-verification.md -Pattern "PASS|not run|AB blocker"
```

Expected: only intentional source/document changes are present before the final commit; no unexplained untracked files remain; the report contains truthful outcomes.

- [ ] **Step 6: Commit any final report refresh**

```powershell
git add docs/reports/ia-ib-final-verification.md
git commit -m "test: finalize IA and IB verification"
```

- [ ] **Step 7: Record remaining non-IA/IB blockers**

Final handoff must explicitly list Docker live validation if unavailable, AB CA-MP correctness, EX formal experiments, DA/DB deliverables, TL final review/tag, and submission receipt. Do not describe IA/IB completion as whole-project completion.
