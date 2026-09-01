# Judge Native Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a judge-facing native one-click launcher that starts the existing FastAPI/Web/SUMO system from the repository interpreter, records truthful diagnostics, opens the browser only after health passes, focuses only the owned SUMO-GUI process, and shuts every owned process down cleanly.

**Architecture:** One Python entrypoint performs project-interpreter bootstrap, preflight, bounded port selection, diagnostics, RunService composition, Uvicorn lifecycle, readiness polling, browser opening, and PID-scoped Windows GUI focus. Thin PowerShell and batch wrappers provide the double-click/native entry. The existing FastAPI lifespan remains the sole cleanup authority for RunService and its SUMO children.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, TraCI/SUMO 1.27.1, Python standard library (`argparse`, `ctypes`, `json`, `socket`, `threading`, `urllib`, `webbrowser`), PowerShell, Windows batch, pytest.

**Spec:** `.superpowers/sdd/2026-08-18-judge-facing-final-release/task-18-brief.md`

**Parent plan task:** Global Task 18, “Implement native one-click startup and diagnostics”. Tasks 18.1 through 18.6 below are implementation subtasks inside Global Task 18, not Global Tasks 18-23.

## Global Constraints

- Use the existing `api.server.create_app(run_service=..., web_dist=...)`; do not add a second application or duplicate API routes.
- Use one `RunService(max_workers=1)` and the existing FastAPI lifespan `shutdown(wait=True)` cleanup path.
- The native wrapper must select a repository interpreter and must never assume that a global `python` command is usable.
- A repository `.venv` takes precedence; the future Task 19 container may run with its current interpreter when no repository virtual environment exists and all preflight checks pass.
- Scan at most ten consecutive ports starting at the requested port, never wrap past port 65535, and record every conflict.
- Open a browser only after `/api/health` returns JSON with `status == "ok"`.
- On Windows, `auto` prefers `sumo-gui`; `native` requires Windows plus `sumo-gui`; `headless` requires `sumo`. On non-Windows systems, `auto` selects headless SUMO.
- Focus a native GUI only by the exact `TraCIBridge.process_id` owned by the requested run; never search by window title or process name.
- Write diagnostics atomically to `output/evidence/judge-launch/launcher.json` using schema `judge-launcher.v1` and `pass`/`fail`/`not_run` check vocabulary.
- Store repository-relative executable identities in diagnostics; do not persist user-profile or machine-specific absolute paths.
- Do not modify, overwrite, delete, move, or repack `赛题资料.7z` or any path under `data/intersection_data`.
- Do not clean, stage, or rewrite historical scratch directories, test output directories, `node_modules`, or unrelated user files.

## File responsibility map

- `scripts/run_judge.py`: all launcher behavior and testable pure adapters; no shell-specific policy.
- `scripts/start_judge.ps1`: repository-root discovery, local interpreter selection, argument forwarding, working-directory restoration, and exit-code propagation.
- `scripts/start_judge.bat`: PowerShell delegation and exit-code propagation only.
- `tests/test_judge_launcher.py`: unit, integration, wrapper-contract, and process-lifecycle tests for Task 18.
- `docs/deployment.md`: authoritative one-click command, options, diagnostics path, failure guidance, and manual fallback.
- `README.md`: minimal judge-facing quick-start pointer; broad release-document rewriting remains Global Task 20.
- `.superpowers/sdd/2026-08-18-judge-facing-final-release/progress.md`: exact Task 18 evidence, rulings, reviews, commits, and protection gates after verification.

---

### Task 18.1: Define launcher contracts, interpreter bootstrap, port selection, and diagnostics

**Files:**
- Create: `tests/test_judge_launcher.py`
- Create: `scripts/run_judge.py`

**Interfaces:**
- Produces `repo_root_from_script(script_path: Path) -> Path`.
- Produces `project_interpreter(repo_root: Path, platform_name: str | None = None) -> Path | None`.
- Produces `ensure_project_interpreter(repo_root: Path, argv: Sequence[str], *, executable: Path | None = None, execv: Callable[..., object] = os.execv) -> str`, returning `project_venv` or `current_runtime` when no re-exec is needed.
- Produces immutable `PortSelection(requested: int, selected: int, conflicts: tuple[int, ...])`.
- Produces `select_port(host: str, requested: int, attempts: int = 10, *, socket_factory: Callable[..., socket.socket] = socket.socket) -> PortSelection`.
- Produces `DiagnosticsWriter(path: Path, initial: Mapping[str, object])` with thread-safe `update(**changes) -> dict[str, object]` and `snapshot() -> dict[str, object]`.
- Produces `parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace` with the exact command contract in the Task 18 brief.

Define the socket test double in `tests/test_judge_launcher.py` before the tests that use it:

```python
class _FakeSocket:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def setsockopt(self, level, option, value):
        self.owner.options.append((level, option, value))

    def bind(self, address):
        self.owner.binds.append(address)
        if address[1] in self.owner.conflicted_ports:
            raise OSError("address in use")


class FakeSocketSequence:
    def __init__(self, conflicted_ports):
        self.conflicted_ports = set(conflicted_ports)
        self.binds = []
        self.options = []

    def __call__(self, *_args, **_kwargs):
        return _FakeSocket(self)
```

- [ ] **Step 1: Write RED tests for interpreter and port contracts**

Add tests equivalent to:

```python
def test_project_interpreter_prefers_repository_venv(tmp_path):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")

    assert project_interpreter(tmp_path, "win32") == python


def test_ensure_project_interpreter_reexecutes_exact_repository_python(tmp_path):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")
    calls = []

    ensure_project_interpreter(
        tmp_path,
        ["--port", "8765"],
        executable=tmp_path / "global-python.exe",
        execv=lambda executable, command: calls.append((executable, command)),
    )

    assert calls[0][0] == str(python)
    assert calls[0][1][-2:] == ["--port", "8765"]


def test_select_port_skips_conflicts_within_bounded_window():
    sockets = FakeSocketSequence(conflicted_ports={8000, 8001})
    selection = select_port("127.0.0.1", 8000, attempts=10, socket_factory=sockets)

    assert selection.selected == 8002
    assert selection.conflicts == (8000, 8001)


def test_select_port_fails_after_ten_conflicts():
    sockets = FakeSocketSequence(conflicted_ports=set(range(8000, 8010)))

    with pytest.raises(LauncherError, match="no free port in 8000..8009"):
        select_port("127.0.0.1", 8000, attempts=10, socket_factory=sockets)
```

The fake socket must record `SO_REUSEADDR` use and every `(host, port)` bind attempt so the
test proves that the scan is consecutive and bounded rather than selecting an arbitrary port.

- [ ] **Step 2: Run the focused RED tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .task18-red-contracts-20260823 `
  tests/test_judge_launcher.py -k "interpreter or port or diagnostics" -q
```

Expected: collection fails because `scripts.run_judge` and its public contracts do not exist.

- [ ] **Step 3: Implement argument validation and interpreter bootstrap**

Use this command shape:

```python
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=bounded_port, default=8000)
    parser.add_argument("--port-attempts", type=bounded_attempts, default=10)
    parser.add_argument(
        "--open-browser",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--gui-mode",
        choices=("auto", "native", "headless"),
        default="auto",
    )
    parser.add_argument("--health-timeout", type=positive_finite, default=30.0)
    parser.add_argument(
        "--diagnostics",
        type=Path,
        default=Path("output/evidence/judge-launch/launcher.json"),
    )
    return parser.parse_args(argv)
```

Resolve `.venv/Scripts/python.exe` on Windows and `.venv/bin/python` elsewhere. Compare
resolved, case-normalized interpreter paths before re-executing. If no project interpreter
exists, return `current_runtime`; dependency preflight in Task 18.2 decides whether that
runtime is usable. This preserves the future container entrypoint without weakening the
native PowerShell wrapper.

- [ ] **Step 4: Implement bounded port selection**

Validate `requested in range(1, 65536)`, `attempts in range(1, 11)`, and stop at port 65535.
For each candidate, open an IPv4 TCP socket, set `SO_REUSEADDR`, bind, and close immediately.
Treat only `OSError` from bind as a conflict. Raise `LauncherError` containing the exact
scanned interval when no candidate is free.

- [ ] **Step 5: Write RED tests for atomic diagnostics**

```python
def test_diagnostics_writer_replaces_complete_json_atomically(tmp_path):
    path = tmp_path / "launcher.json"
    writer = DiagnosticsWriter(path, {"schema": "judge-launcher.v1", "status": "starting"})
    writer.update(status="ready", network={"selected_port": 8001})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert payload["network"]["selected_port"] == 8001
    assert not list(tmp_path.glob(".launcher.json.*.tmp"))


def test_diagnostics_writer_preserves_previous_document_when_replace_fails(
    monkeypatch, tmp_path
):
    path = tmp_path / "launcher.json"
    writer = DiagnosticsWriter(path, {"schema": "judge-launcher.v1", "status": "starting"})
    before = path.read_bytes()
    monkeypatch.setattr(os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("busy")))

    with pytest.raises(OSError, match="busy"):
        writer.update(status="ready")

    assert path.read_bytes() == before
```

- [ ] **Step 6: Implement thread-safe atomic diagnostics**

Copy the initial mapping, create the parent directory, serialize with UTF-8,
`ensure_ascii=False`, `sort_keys=True`, `allow_nan=False`, and a trailing newline. Write a
unique sibling temporary file and call `os.replace`. Remove only that writer-owned temporary
file in `finally`. Hold one `threading.RLock` across snapshot mutation and replacement so the
readiness worker and Uvicorn main thread cannot publish torn state.

- [ ] **Step 7: Run Task 18.1 GREEN and static checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .task18-green-contracts-20260823 `
  tests/test_judge_launcher.py -k "interpreter or port or diagnostics or parse_args" -q
.\.venv\Scripts\python.exe -m compileall -q scripts/run_judge.py tests/test_judge_launcher.py
git diff --check -- scripts/run_judge.py tests/test_judge_launcher.py
```

Expected: focused tests pass, compileall exits 0, and the diff check is clean.

- [ ] **Step 8: Commit the launcher foundation**

```bash
git add scripts/run_judge.py tests/test_judge_launcher.py
git commit -m "feat: add judge launcher preflight foundation"
```

---

### Task 18.2: Implement runtime preflight, Uvicorn ownership, health readiness, and browser ordering

**Files:**
- Modify: `scripts/run_judge.py`
- Modify: `tests/test_judge_launcher.py`

**Interfaces:**
- Consumes `PortSelection`, `DiagnosticsWriter`, and parsed launcher arguments from Task 18.1.
- Produces immutable `ExecutableRecord(name: str, path: Path | None, version: str | None, status: str, detail: str)`.
- Produces immutable `RuntimeSelection(mode: str, sumo_binary: Path, native_gui: bool)`.
- Produces `resolve_sumo_executable(name: str, *, environ: Mapping[str, str] = os.environ, which: Callable[[str], str | None] = shutil.which) -> Path | None`.
- Produces `select_runtime(gui_mode: str, *, platform_name: str = sys.platform, sumo: Path | None, sumo_gui: Path | None) -> RuntimeSelection`.
- Produces `collect_preflight(repo_root: Path, args: argparse.Namespace, interpreter_source: str) -> tuple[dict[str, object], RuntimeSelection, PortSelection]`.
- Produces `build_application(repo_root: Path, runtime: RuntimeSelection, runner_registry: RunnerRegistry | None = None) -> tuple[FastAPI, RunService, RunnerRegistry]`.
- Produces immutable `HealthResult(status: str, attempts: int, detail: str)`.
- Produces `wait_for_health(url: str, timeout: float, *, opener: Callable[..., object] = urllib.request.urlopen, monotonic: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> HealthResult`.
- Produces `perform_readiness(server: object, writer: DiagnosticsWriter, url: str, browser_url: str, *, timeout: float, open_browser: bool, wait_for_health_fn: Callable[..., HealthResult] = wait_for_health, browser_open: Callable[..., bool] = webbrowser.open) -> HealthResult`.
- Produces `run_server(args: argparse.Namespace, *, server_factory: Callable[[uvicorn.Config], object] = uvicorn.Server, browser_open: Callable[..., bool] = webbrowser.open, health_opener: Callable[..., object] = urllib.request.urlopen) -> int`.

Define these shared Task 18.2 test helpers explicitly:

```python
class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class SequencedOpener:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)

    def __call__(self, *_args, **_kwargs):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def launcher_args(tmp_path, **overrides):
    values = {
        "host": "127.0.0.1",
        "port": 8000,
        "port_attempts": 10,
        "open_browser": False,
        "gui_mode": "headless",
        "health_timeout": 5.0,
        "diagnostics": tmp_path / "launcher.json",
    }
    values.update(overrides)
    return SimpleNamespace(**values)
```

- [ ] **Step 1: Write RED tests for runtime selection and preflight failures**

```python
@pytest.mark.parametrize(
    ("platform_name", "mode", "has_gui", "expected_name", "native_gui"),
    [
        ("win32", "auto", True, "sumo-gui.exe", True),
        ("win32", "auto", False, "sumo.exe", False),
        ("linux", "auto", True, "sumo", False),
        ("win32", "headless", True, "sumo.exe", False),
        ("win32", "native", True, "sumo-gui.exe", True),
    ],
)
def test_select_runtime_uses_explicit_gui_policy(
    tmp_path, platform_name, mode, has_gui, expected_name, native_gui
):
    sumo = tmp_path / "sumo.exe"
    gui = tmp_path / "sumo-gui.exe" if has_gui else None
    selection = select_runtime(
        mode, platform_name=platform_name, sumo=sumo, sumo_gui=gui
    )

    assert selection.sumo_binary.name == expected_name
    assert selection.native_gui is native_gui


def test_native_mode_fails_outside_windows(tmp_path):
    with pytest.raises(LauncherError, match="native GUI requires Windows"):
        select_runtime(
            "native",
            platform_name="linux",
            sumo=tmp_path / "sumo",
            sumo_gui=tmp_path / "sumo-gui",
        )


def test_preflight_fails_when_production_assets_are_missing(tmp_path):
    (tmp_path / "api" / "static" / "dist").mkdir(parents=True)
    (tmp_path / "output").mkdir()

    with pytest.raises(PreflightError, match="web build unavailable"):
        collect_preflight(tmp_path, launcher_args(tmp_path), "project_venv")
```

The repository fixture must supply only test-owned fake executables, a fake static
`index.html`, and writable output paths. It must not read or mutate the real protected data.

- [ ] **Step 2: Implement executable discovery and version probes**

Search in this order: explicit `%SUMO_HOME%/bin`, `shutil.which`, then the Windows project
default `C:/Program Files (x86)/Eclipse/Sumo/bin` when running on Windows. Probe each resolved
binary with `[path, "--version"]`, capture UTF-8 with replacement, and record only the file
name plus version in diagnostics. Probe package versions through `importlib.metadata.version`
for FastAPI, Uvicorn, TraCI, and sumolib. A missing required dependency is `fail`, not
`not_run`.

- [ ] **Step 3: Implement preflight aggregation**

Preflight must verify:

```text
Python >= 3.10
FastAPI import/version available
Uvicorn import/version available
TraCI import/version available
sumolib import/version available
selected SUMO executable available and version exactly 1.27.1
api/static/dist/index.html is a regular file
output/runs is writable
diagnostics parent is writable
requested port has a free candidate in the bounded scan
```

Write a `starting` diagnostics document before probes that may fail, update it with every
check, then change top-level status to `failed` with an actionable reason before returning
exit code 2. Do not start Uvicorn after any required `fail` result.

- [ ] **Step 4: Write RED tests for health semantics and browser ordering**

```python
def test_wait_for_health_accepts_only_exact_ok_json():
    fake_clock = FakeClock()
    opener = SequencedOpener([
        ConnectionRefusedError(),
        FakeResponse(200, {"status": "starting"}),
        FakeResponse(200, {"status": "ok", "run_workers": 1}),
    ])

    result = wait_for_health(
        "http://127.0.0.1:8000/api/health",
        5.0,
        opener=opener,
        monotonic=fake_clock.monotonic,
        sleep=fake_clock.sleep,
    )

    assert result.status == "pass"
    assert result.attempts == 3


def test_perform_readiness_opens_browser_only_after_health(tmp_path):
    events = []
    server = SimpleNamespace(should_exit=False)
    writer = DiagnosticsWriter(
        tmp_path / "launcher.json",
        {"schema": "judge-launcher.v1", "status": "starting"},
    )

    result = perform_readiness(
        server,
        writer,
        "http://127.0.0.1:8000/api/health",
        "http://127.0.0.1:8000/",
        timeout=5.0,
        open_browser=True,
        wait_for_health_fn=lambda *_args, **_kwargs: (
            events.append("health") or HealthResult("pass", 1, "status ok")
        ),
        browser_open=lambda *_args, **_kwargs: events.append("browser") or True,
    )

    assert result.status == "pass"
    assert events == ["health", "browser"]
    assert writer.snapshot()["status"] == "ready"
```

Add a composition test asserting `application.state.run_service is service`, then enter and
leave `TestClient(application)` while wrapping `service.shutdown` with a counter. Require
exactly one `shutdown(wait=True)` call. This extends the existing FastAPI lifespan regression
without inventing a fake Uvicorn lifecycle.

- [ ] **Step 5: Implement the application composition boundary**

Construct exactly one service and application:

```python
registry = runner_registry or RunnerRegistry(runtime)
service = RunService(
    output_root=repo_root / "output" / "runs",
    runner_factory=registry.create_runner,
)
service.native_gui = registry.show_native_gui
application = create_app(
    run_service=service,
    web_dist=repo_root / "api" / "static" / "dist",
)
```

Do not call `service.shutdown()` from `run_server`; `create_app` lifespan already owns that
operation. If Uvicorn construction fails before lifespan starts, call `service.shutdown`
once in that exceptional pre-start path and record the failure.

- [ ] **Step 6: Implement readiness worker and main-thread Uvicorn**

Create `uvicorn.Config(application, host=args.host, port=selection.selected,
log_level="info", access_log=True)`, instantiate the server, start one daemon readiness
thread, and call `server.run()` on the main thread. The worker:

1. polls the exact health URL at a bounded interval;
2. records attempt count and detail;
3. on success, sets `ready_at`, top-level `ready`, and browser status;
4. invokes `webbrowser.open(url, new=2)` only when `args.open_browser` is true;
5. on timeout, records top-level `failed` and sets `server.should_exit = True`.

After `server.run()` returns, join the worker with a bounded timeout. Preserve `failed` if it
already failed; otherwise set top-level `stopped`, record `stopped_at`, and return 0. Keyboard
interrupt and ordinary signal-driven stop are normal `stopped` outcomes after readiness.

- [ ] **Step 7: Run Task 18.2 GREEN and API lifecycle regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .task18-green-server-20260823 `
  tests/test_judge_launcher.py tests/test_judge_api.py::test_static_serving_is_contained_and_lifespan_shuts_down_service -q
.\.venv\Scripts\python.exe -m compileall -q scripts/run_judge.py
git diff --check -- scripts/run_judge.py tests/test_judge_launcher.py
```

Expected: launcher and existing lifespan tests pass; the launcher does not add a second
shutdown call.

- [ ] **Step 8: Commit server orchestration**

```bash
git add scripts/run_judge.py tests/test_judge_launcher.py
git commit -m "feat: launch healthy judge service with diagnostics"
```

---

### Task 18.3: Implement exact-PID native SUMO-GUI focus

**Files:**
- Modify: `scripts/run_judge.py`
- Modify: `tests/test_judge_launcher.py`

**Interfaces:**
- Consumes `RuntimeSelection` from Task 18.2.
- Produces `RunnerRegistry(runtime: RuntimeSelection, *, runner_type: type[SimulationRunner] = SimulationRunner)`.
- `RunnerRegistry.create_runner(**kwargs) -> SimulationRunner` passes `sumo_binary=str(runtime.sumo_binary)`, records `artifacts.run_id -> runner`, and returns the runner.
- `RunnerRegistry.show_native_gui(run_id: str) -> tuple[bool, str]` returns a stable success/failure reason and never raises across the API boundary.
- Produces `focus_window_for_pid(pid: int, *, platform_name: str = sys.platform, user32: object | None = None) -> tuple[bool, str]`.

- [ ] **Step 1: Write RED tests for runner binding and exact PID focus**

```python
def test_runner_registry_injects_selected_binary_and_registers_run(tmp_path):
    created = []

    class FakeRunner:
        def __init__(self, **kwargs):
            created.append(kwargs)
            self.artifacts = kwargs["artifacts"]
            self.bridge = SimpleNamespace(process_id=41005)

    runtime = RuntimeSelection("native", tmp_path / "sumo-gui.exe", True)
    registry = RunnerRegistry(runtime, runner_type=FakeRunner)
    artifacts = SimpleNamespace(run_id="run-owned")

    runner = registry.create_runner(scene=object(), algorithm=object(), artifacts=artifacts)

    assert created[0]["sumo_binary"] == str(runtime.sumo_binary)
    assert registry.runner_for("run-owned") is runner


def test_show_native_gui_uses_only_requested_runs_owned_pid(monkeypatch, tmp_path):
    class FakeRunner:
        def __init__(self, artifacts, **_kwargs):
            pids = {"run-a": 41005, "run-b": 41006}
            self.artifacts = artifacts
            self.bridge = SimpleNamespace(process_id=pids[artifacts.run_id])

    native_registry = RunnerRegistry(
        RuntimeSelection("native", tmp_path / "sumo-gui.exe", True),
        runner_type=FakeRunner,
    )
    native_registry.create_runner(artifacts=SimpleNamespace(run_id="run-a"))
    native_registry.create_runner(artifacts=SimpleNamespace(run_id="run-b"))
    focused = []
    monkeypatch.setattr(
        run_judge,
        "focus_window_for_pid",
        lambda pid, **_kwargs: focused.append(pid) or (True, "focused"),
    )

    assert native_registry.show_native_gui("run-a") == (True, "focused")
    assert focused == [41005]


def test_focus_window_enumerates_exact_pid_and_restores_only_that_window():
    user32 = FakeUser32(
        windows={101: {"pid": 41005, "visible": True}, 202: {"pid": 99999, "visible": True}}
    )

    assert focus_window_for_pid(41005, platform_name="win32", user32=user32)[0] is True
    assert user32.restored == [101]
    assert user32.foreground == [101]
```

Define the ctypes-compatible window test double before the focus test:

```python
class FakeUser32:
    def __init__(self, windows):
        self.windows = windows
        self.restored = []
        self.foreground = []

    def EnumWindows(self, callback, lparam):
        for hwnd in self.windows:
            callback(hwnd, lparam)
        return True

    def GetWindowThreadProcessId(self, hwnd, pid_pointer):
        pid_pointer._obj.value = self.windows[hwnd]["pid"]
        return 1

    def IsWindowVisible(self, hwnd):
        return self.windows[hwnd]["visible"]

    def ShowWindow(self, hwnd, _command):
        self.restored.append(hwnd)
        return True

    def SetForegroundWindow(self, hwnd):
        self.foreground.append(hwnd)
        return True
```

Also cover unknown run ID, runner without a PID, headless mode, non-Windows mode, invisible
windows, and `SetForegroundWindow` failure. Every failure returns `(False, reason)`.

- [ ] **Step 2: Run the native focus RED tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .task18-red-native-gui-20260823 `
  tests/test_judge_launcher.py -k "runner_registry or native_gui or focus_window" -q
```

Expected: tests fail because `RunnerRegistry` and `focus_window_for_pid` are absent.

- [ ] **Step 3: Implement runner registration without RunService internals**

Use a `threading.RLock` and a private `dict[str, object]`. Read the run identity from
`kwargs["artifacts"].run_id`; reject a missing or empty ID with `LauncherError`. Override any
incoming `sumo_binary` with the preflight-selected binary. Do not read or mutate
`RunService._runners`, and do not change `engine/run_service.py`.

For `show_native_gui`, return `native GUI disabled by launcher mode` when the runtime is
headless, `unknown run_id` when unregistered, and `SUMO process is not ready` when
`runner.bridge.process_id` is absent. Pass only the resulting positive integer PID to the
focus adapter.

- [ ] **Step 4: Implement PID-scoped Windows focus with ctypes**

Use `ctypes.WINFUNCTYPE` and `user32.EnumWindows`. For each enumerated `HWND`, call
`GetWindowThreadProcessId` and keep only visible windows whose PID equals the requested PID.
For the first exact match, call `ShowWindow(hwnd, SW_RESTORE)` followed by
`SetForegroundWindow(hwnd)`. Do not inspect window title text. Return stable reasons:

```text
native GUI is supported only on Windows
invalid SUMO process id
no visible window for SUMO process <pid>
could not focus SUMO process <pid>
focused SUMO process <pid>
```

The optional `user32` argument supplies a test double; production lazily loads
`ctypes.windll.user32` only on Windows.

- [ ] **Step 5: Verify API integration and exact-PID behavior GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .task18-green-native-gui-20260823 `
  tests/test_judge_launcher.py `
  tests/test_judge_api.py -k "native_gui or launcher or focus" -q
.\.venv\Scripts\python.exe -m compileall -q scripts/run_judge.py
git diff --check -- scripts/run_judge.py tests/test_judge_launcher.py
```

Expected: exact-PID focus tests and existing 404/409/200 native-GUI API tests pass.

- [ ] **Step 6: Commit native GUI ownership**

```bash
git add scripts/run_judge.py tests/test_judge_launcher.py
git commit -m "feat: focus owned SUMO GUI by run pid"
```

---

### Task 18.4: Add PowerShell/batch one-click wrappers and minimal judge documentation

**Files:**
- Create: `scripts/start_judge.ps1`
- Create: `scripts/start_judge.bat`
- Modify: `tests/test_judge_launcher.py`
- Modify: `docs/deployment.md`
- Modify: `README.md`

**Interfaces:**
- `scripts/start_judge.ps1 [launcher arguments...]` runs the repository-local Python from the
  repository root and returns the Python process exit code.
- `scripts/start_judge.bat [launcher arguments...]` calls PowerShell with `-NoProfile` and
  `-ExecutionPolicy Bypass`, forwards `%*`, and returns `%ERRORLEVEL%`.
- Documentation exposes the default double-click/PowerShell path, headless fallback, explicit
  native mode, diagnostics path, and manual Uvicorn fallback.

- [ ] **Step 1: Write RED wrapper contract tests**

```python
def test_powershell_wrapper_prefers_project_venv_and_forwards_all_arguments():
    repo_root = Path(__file__).resolve().parents[1]
    text = (repo_root / "scripts" / "start_judge.ps1").read_text(encoding="utf-8")
    assert ".venv\\Scripts\\python.exe" in text
    assert "run_judge.py" in text
    assert "@args" in text
    assert "exit $exitCode" in text


def test_batch_wrapper_delegates_and_preserves_exit_code():
    repo_root = Path(__file__).resolve().parents[1]
    text = (repo_root / "scripts" / "start_judge.bat").read_text(encoding="utf-8")
    assert "-NoProfile" in text
    assert "-ExecutionPolicy Bypass" in text
    assert "%*" in text
    assert "exit /b %ERRORLEVEL%" in text
```

Add a Windows-only subprocess test that creates a temporary fake repository with a fake
`python.exe` command script, invokes the PowerShell wrapper with `--port 8765 --no-browser`,
and asserts the exact forwarded arguments and nonzero exit-code propagation. Skip this one
test with an explicit reason outside Windows.

- [ ] **Step 2: Run wrapper RED tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .task18-red-wrappers-20260823 `
  tests/test_judge_launcher.py -k "wrapper or powershell or batch" -q
```

Expected: tests fail because the two wrapper files do not exist.

- [ ] **Step 3: Implement the PowerShell wrapper**

Use this behavior, preserving the caller's current directory with `try/finally`:

```powershell
$repoRoot = Split-Path -Parent $PSScriptRoot
$candidates = @(
  (Join-Path $repoRoot ".venv\Scripts\python.exe"),
  (Join-Path $repoRoot ".venv-native\Scripts\python.exe")
)
$python = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
  Select-Object -First 1
if (-not $python) {
  Write-Error "Project Python not found. Create .venv and install requirements-dev.txt."
  exit 2
}
$previous = Get-Location
try {
  Set-Location -LiteralPath $repoRoot
  & $python (Join-Path $PSScriptRoot "run_judge.py") @args
  $exitCode = $LASTEXITCODE
} finally {
  Set-Location -LiteralPath $previous
}
exit $exitCode
```

Do not use global `python`, activate a profile, install dependencies, or modify execution
policy persistently.

- [ ] **Step 4: Implement the batch wrapper**

```bat
@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_judge.ps1" %*
exit /b %ERRORLEVEL%
```

- [ ] **Step 5: Update only the Task 18 documentation surface**

At the start of `docs/deployment.md`, add “评委一键启动” with these exact commands:

```powershell
.\scripts\start_judge.ps1
.\scripts\start_judge.ps1 --gui-mode headless --no-browser
.\scripts\start_judge.ps1 --gui-mode native --port 8765
```

Explain that the launcher may select the next free port within ten candidates, prints the
selected URL, opens the browser only after health, and writes
`output/evidence/judge-launch/launcher.json`. Include troubleshooting for missing `.venv`,
missing SUMO 1.27.1, missing Web build, exhausted ports, and native GUI unavailable. Preserve
the existing manual API, matrix, validation, and Docker sections.

In `README.md` “快速开始”, add one compact judge-launch paragraph pointing to
`docs/deployment.md`; do not rewrite historical status, the formal experiment matrix, Docker
claims, or release packaging before Global Task 20.

- [ ] **Step 6: Run wrapper and documentation GREEN checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .task18-green-wrappers-20260823 `
  tests/test_judge_launcher.py -k "wrapper or powershell or batch" -q
rg -n "start_judge|launcher.json|gui-mode" README.md docs/deployment.md
git diff --check -- scripts/start_judge.ps1 scripts/start_judge.bat README.md docs/deployment.md tests/test_judge_launcher.py
```

Expected: wrapper tests pass, both docs expose the intended entry, and no unrelated section
was removed.

- [ ] **Step 7: Commit wrappers and minimal documentation**

```bash
git add scripts/start_judge.ps1 scripts/start_judge.bat tests/test_judge_launcher.py docs/deployment.md README.md
git commit -m "feat: add one-click judge startup wrappers"
```

---

### Task 18.5: Verify real native lifecycle, regression, browser acceptance, and protected invariants

**Files:**
- Test: `tests/test_judge_launcher.py`
- Test: `tests/test_judge_api.py`
- Test: `tests/test_run_lifecycle.py`
- Implementation: `engine/traci_bridge.py`
- Test: `tests/test_seed.py`
- Test: `web/tests/judge-flow.spec.ts`
- Generate runtime evidence only: `output/evidence/judge-launch/launcher.json`
- Generate runtime evidence only: `output/evidence/judge-launch/native-smoke.json`

**Interfaces:**
- Produces real evidence from the checked-in launcher; generated evidence is not staged unless
  the parent release policy explicitly requires it.
- Preserves the Task 17 Web console contract and all protected file invariants.

- [ ] **Step 1: Run the complete focused launcher and lifecycle suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .task18-final-focused-20260823 `
  tests/test_judge_launcher.py `
  tests/test_judge_api.py `
  tests/test_run_lifecycle.py -q
```

Expected: PASS with no hanging test process and no duplicate shutdown.

- [ ] **Step 2: Run a real headless one-click smoke**

Start the PowerShell wrapper in a hidden helper process with
`--host 127.0.0.1 --port 8765 --gui-mode headless --no-browser`. Wait for the diagnostics
document to report `ready`; read the selected port from that document rather than assuming
8765. Then:

1. request `/api/health` and require `status == "ok"`;
2. `POST /api/runs` for intersection 1, `fixed_time`, seed 42, and a short duration;
3. poll the returned run ID to a terminal state;
4. stop the launcher with a console interrupt or process signal;
5. require launcher diagnostics `stopped` and prove no launcher-owned SUMO child remains.

Write the observed request URL, run ID, terminal status, launcher exit code, timestamps, and
cleanup result atomically to `output/evidence/judge-launch/native-smoke.json`. Do not record
unrelated process lists or user absolute paths.

- [ ] **Step 3: Run the real Windows native-GUI smoke**

On this verified Windows environment, start the wrapper with
`--gui-mode native --no-browser`, submit the same short run, wait until the runner reports a
frame or running event, then call `POST /api/runs/{run_id}/native-gui`. Require HTTP 200 and
`{"status":"shown"}`. Stop the run and launcher, and verify cleanup. If `sumo-gui.exe` or an
interactive desktop is genuinely unavailable at execution time, record `not_run` with the
actual reason; do not replace the real check with a mock.

- [ ] **Step 4: Run frontend production and browser gates**

Run from `web/`:

```powershell
npm ci
npm run typecheck
npm run build
npm run test:e2e -- --project=chromium
```

Expected: TypeScript, Vite build, and all Task 17 Playwright tests pass. Then launch the Task
18 service in `auto` mode, open its selected URL in the Codex in-app browser only after
diagnostics says health `pass`, and verify Simulation, Comparison, History, and Scene remain
usable. Mark the verified tab as a deliverable.

- [ ] **Step 5: Run affected and full Python regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .task18-final-affected-20260823 `
  tests/test_judge_launcher.py tests/test_judge_api.py tests/test_api_contract.py `
  tests/test_run_service.py tests/test_run_lifecycle.py -q
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .task18-final-full-20260823 -q
.\.venv\Scripts\python.exe -m compileall -q `
  scripts api core engine algorithms scenes visualization
git diff --check
```

Expected: affected and full suites match or improve the current green baseline; compileall
and diff check exit 0.

- [ ] **Step 6: Verify protected invariants and scoped staging**

Record and compare:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath .\赛题资料.7z
git ls-files -- data/intersection_data | Measure-Object
Get-ChildItem -Recurse -File -LiteralPath data/intersection_data | Measure-Object
git diff --name-only -- 赛题资料.7z data/intersection_data
git diff --cached --name-only -- 赛题资料.7z data/intersection_data
git status --short
```

Expected: archive SHA-256 remains
`12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`, official scene
counts remain 163 tracked and 232 on disk, protected diffs are empty, and only the exact Task
18 source/docs/plan paths are candidates for staging. Do not remove unrelated untracked
scratch or `web/node_modules`.

---

### Task 18.6: Complete Terra/Sol review, ledger, final verification, and commits

**Files:**
- Modify: `.superpowers/sdd/2026-08-18-judge-facing-final-release/progress.md`
- Create: `.superpowers/sdd/2026-08-18-judge-facing-final-release/task-18-report.md`
- Review: exact Global Task 18 diff only

**Interfaces:**
- Produces one standards review from the existing Terra reviewer and one specification review
  from the existing Sol reviewer.
- Produces a Task 18 report that records exact commands, exit codes, counts, real-smoke facts,
  browser acceptance, limitations, protection hashes/counts, review findings, and commit IDs.
- Marks only Global Task 18 complete; Global Tasks 19-24 remain not started.

- [ ] **Step 1: Prepare the exact scoped review diff**

Review only these tracked Task 18 paths:

```text
.superpowers/sdd/2026-08-18-judge-facing-final-release/task-18-brief.md
docs/superpowers/plans/2026-08-23-judge-native-launcher-task18.md
scripts/run_judge.py
scripts/start_judge.ps1
scripts/start_judge.bat
engine/traci_bridge.py
tests/test_judge_launcher.py
tests/test_run_lifecycle.py
tests/test_seed.py
docs/deployment.md
README.md
```

Do not include historical scratch, generated Web assets unchanged from Task 17, protected
data, or unrelated untracked files in the review diff.

- [ ] **Step 2: Ask existing Terra and Sol reviewers for independent review**

Use only the already-running Terra and Sol subagents, in parallel if both slots are available:

- Terra standards review: code quality, process ownership, Windows/PowerShell correctness,
  atomic diagnostics, security/path hygiene, test quality, and maintainability.
- Sol specification review: exact Task 18 brief, parent plan/PDF alignment, health-before-
  browser, bounded port selection, interpreter rules, PID ownership, real evidence honesty,
  protected invariants, and Global Task numbering.

Each reviewer reports Critical, Important, and Minor findings with exact file/line evidence, or
`CLEAN`. Do not create any additional subagent.

- [ ] **Step 3: Resolve review findings test-first**

For every valid finding, add or tighten a failing test, run it RED, implement the smallest
fix, rerun the focused test GREEN, and rerun the affected Task 18 gate. Send the exact fix diff
back to the original reviewer for re-review. Continue until both Terra and Sol report no open
Critical or Important finding.

- [ ] **Step 4: Write the Task 18 report and progress ledger**

The report must distinguish:

```text
Global Task 18 status
Task 18 implementation subtasks 18.1-18.6
unit/integration results
real headless smoke
real native-GUI smoke or truthful unavailable status
Codex in-app browser acceptance
affected/full baselines
protected archive/data invariants
Terra standards verdict
Sol specification verdict
known limitations deferred to Global Tasks 19-24
```

Update the progress ledger from “Task 18 not started” to a dated closeout. Do not mark Docker,
release docs, packaging, formal matrix, or final materials complete; those belong to Global
Tasks 19-24.

- [ ] **Step 5: Stage by exact allowlist and commit closeout**

```bash
git add \
  .superpowers/sdd/2026-08-18-judge-facing-final-release/task-18-brief.md \
  .superpowers/sdd/2026-08-18-judge-facing-final-release/task-18-report.md \
  .superpowers/sdd/2026-08-18-judge-facing-final-release/progress.md \
  docs/superpowers/plans/2026-08-23-judge-native-launcher-task18.md \
  scripts/run_judge.py scripts/start_judge.ps1 scripts/start_judge.bat \
  engine/traci_bridge.py tests/test_judge_launcher.py tests/test_run_lifecycle.py \
  tests/test_seed.py docs/deployment.md README.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: close task 18 native judge launcher"
```

If implementation commits from Tasks 18.1-18.4 already contain the source files, the final
commit contains only the brief/plan/report/progress closeout changes. Never restage unrelated
paths merely to match this illustrative full allowlist.

- [ ] **Step 6: Verify the exact final HEAD**

After the final commit, rerun the focused launcher suite, one launcher health smoke, frontend
build, `git diff --check HEAD^..HEAD`, scoped protected-path diffs, and tracked worktree/index
checks. Record the exact final HEAD in `task-18-report.md`. Global Task 18 is complete only
after the exact final HEAD evidence and both review verdicts are consistent.
