from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import threading
from types import SimpleNamespace

import pytest

from scripts import run_judge


class _FakeSocket:
    def __init__(self, owner: "FakeSocketSequence") -> None:
        self.owner = owner

    def __enter__(self) -> "_FakeSocket":
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def setsockopt(self, level: int, option: int, value: int) -> None:
        self.owner.options.append((level, option, value))

    def bind(self, address: tuple[str, int]) -> None:
        self.owner.binds.append(address)
        if address[1] in self.owner.conflicted_ports:
            raise OSError("address in use")


class FakeSocketSequence:
    def __init__(self, conflicted_ports: set[int]) -> None:
        self.conflicted_ports = set(conflicted_ports)
        self.binds: list[tuple[str, int]] = []
        self.options: list[tuple[int, int, int]] = []

    def __call__(self, *_args, **_kwargs) -> _FakeSocket:
        return _FakeSocket(self)


def test_repo_root_is_parent_of_scripts_directory(tmp_path: Path) -> None:
    script = tmp_path / "repo" / "scripts" / "run_judge.py"

    assert run_judge.repo_root_from_script(script) == tmp_path / "repo"


def test_parse_args_accepts_no_browser_and_validates_port() -> None:
    args = run_judge.parse_args(
        ["--port", "8765", "--no-browser", "--gui-mode", "headless"]
    )

    assert args.port == 8765
    assert args.open_browser is False
    assert args.gui_mode == "headless"

    with pytest.raises(SystemExit):
        run_judge.parse_args(["--port", "0"])


def test_project_interpreter_prefers_repository_venv_on_windows(tmp_path: Path) -> None:
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")

    assert run_judge.project_interpreter(tmp_path, "win32") == python


def test_project_interpreter_uses_posix_venv_layout(tmp_path: Path) -> None:
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")

    assert run_judge.project_interpreter(tmp_path, "linux") == python


def test_ensure_project_interpreter_reexecutes_exact_repository_python(
    tmp_path: Path,
) -> None:
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")
    calls: list[tuple[str, list[str]]] = []

    run_judge.ensure_project_interpreter(
        tmp_path,
        ["--port", "8765"],
        executable=tmp_path / "global-python.exe",
        platform_name="win32",
        script_path=tmp_path / "scripts" / "run_judge.py",
        execv=lambda executable, command: calls.append((executable, command)),
    )

    assert calls == [
        (
            str(python.resolve()),
            [
                str(python.resolve()),
                str((tmp_path / "scripts" / "run_judge.py").resolve()),
                "--port",
                "8765",
            ],
        )
    ]


def test_ensure_project_interpreter_allows_current_runtime_without_venv(
    tmp_path: Path,
) -> None:
    assert (
        run_judge.ensure_project_interpreter(
            tmp_path,
            [],
            executable=tmp_path / "container-python",
            platform_name="linux",
            script_path=tmp_path / "scripts" / "run_judge.py",
            execv=lambda *_args: pytest.fail("must not re-exec without a project venv"),
        )
        == "current_runtime"
    )


def test_select_port_skips_conflicts_within_bounded_window() -> None:
    sockets = FakeSocketSequence(conflicted_ports={8000, 8001})

    selection = run_judge.select_port(
        "127.0.0.1", 8000, attempts=10, socket_factory=sockets
    )

    assert selection.requested == 8000
    assert selection.selected == 8002
    assert selection.conflicts == (8000, 8001)
    assert sockets.binds == [
        ("127.0.0.1", 8000),
        ("127.0.0.1", 8001),
        ("127.0.0.1", 8002),
    ]
    assert sockets.options == [
        (socket.SOL_SOCKET, socket.SO_REUSEADDR, 1),
        (socket.SOL_SOCKET, socket.SO_REUSEADDR, 1),
        (socket.SOL_SOCKET, socket.SO_REUSEADDR, 1),
    ]


def test_select_port_fails_after_ten_conflicts() -> None:
    sockets = FakeSocketSequence(conflicted_ports=set(range(8000, 8010)))

    with pytest.raises(run_judge.LauncherError, match="no free port in 8000..8009"):
        run_judge.select_port(
            "127.0.0.1", 8000, attempts=10, socket_factory=sockets
        )

    assert sockets.binds == [("127.0.0.1", port) for port in range(8000, 8010)]


def test_select_port_never_wraps_past_65535() -> None:
    sockets = FakeSocketSequence(conflicted_ports={65535})

    with pytest.raises(run_judge.LauncherError, match="no free port in 65535..65535"):
        run_judge.select_port(
            "127.0.0.1", 65535, attempts=10, socket_factory=sockets
        )

    assert sockets.binds == [("127.0.0.1", 65535)]


def test_diagnostics_writer_replaces_complete_json_atomically(tmp_path: Path) -> None:
    path = tmp_path / "launcher.json"
    writer = run_judge.DiagnosticsWriter(
        path,
        {"schema": "judge-launcher.v1", "status": "starting"},
    )

    writer.update(status="ready", network={"selected_port": 8001})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "judge-launcher.v1"
    assert payload["status"] == "ready"
    assert payload["network"]["selected_port"] == 8001
    assert not list(tmp_path.glob(".launcher.json.*.tmp"))


def test_diagnostics_writer_preserves_previous_document_when_replace_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "launcher.json"
    writer = run_judge.DiagnosticsWriter(
        path,
        {"schema": "judge-launcher.v1", "status": "starting"},
    )
    before = path.read_bytes()

    def fail_replace(*_args) -> None:
        raise OSError("busy")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="busy"):
        writer.update(status="ready")

    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".launcher.json.*.tmp"))


@pytest.mark.parametrize("target_kind", ["archive", "official", "traversal"])
def test_run_server_rejects_protected_diagnostics_targets_before_writing(
    target_kind: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    archive = tmp_path / "赛题资料.7z"
    archive.write_bytes(b"protected archive bytes")
    official = tmp_path / "data" / "intersection_data" / "official.net.xml"
    official.parent.mkdir(parents=True)
    official.write_bytes(b"protected official data")
    targets = {
        "archive": archive,
        "official": official,
        "traversal": Path("output") / ".." / "data" / "intersection_data" / official.name,
    }
    before_archive = archive.read_bytes()
    before_data = {
        path.relative_to(official.parent): path.read_bytes()
        for path in official.parent.rglob("*")
        if path.is_file()
    }

    args = run_judge.parse_args(
        ["--no-browser", "--diagnostics", str(targets[target_kind])]
    )
    code = run_judge.run_server(args, repo_root=tmp_path)

    after_data = {
        path.relative_to(official.parent): path.read_bytes()
        for path in official.parent.rglob("*")
        if path.is_file()
    }
    assert code != 0
    assert "protected" in capsys.readouterr().err.lower()
    assert archive.read_bytes() == before_archive
    assert after_data == before_data


def test_run_server_rejects_diagnostics_reparse_into_official_data(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    official_data = tmp_path / "data" / "intersection_data"
    official_data.mkdir(parents=True)
    official = official_data / "official.net.xml"
    official.write_bytes(b"protected official data")
    linked_data = tmp_path / "linked-data"
    if os.name == "nt":
        linked = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(linked_data), str(official_data)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if linked.returncode != 0:
            pytest.skip(f"directory junction unavailable: {linked.stderr.strip()}")
    else:
        linked_data.symlink_to(official_data, target_is_directory=True)
    before = {
        path.relative_to(official_data): path.read_bytes()
        for path in official_data.rglob("*")
        if path.is_file()
    }

    args = run_judge.parse_args(
        ["--no-browser", "--diagnostics", str(linked_data / "launcher.json")]
    )
    code = run_judge.run_server(args, repo_root=tmp_path)

    after = {
        path.relative_to(official_data): path.read_bytes()
        for path in official_data.rglob("*")
        if path.is_file()
    }
    assert code != 0
    assert "protected" in capsys.readouterr().err.lower()
    assert after == before


@pytest.mark.parametrize("absolute", [False, True])
def test_legal_diagnostics_targets_remain_writable(
    absolute: bool,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    requested = (
        tmp_path / "external-diagnostics" / "launcher.json"
        if absolute
        else Path("output") / "evidence" / "launcher.json"
    )

    target = run_judge.resolve_diagnostics_path(repo_root, requested)
    run_judge.DiagnosticsWriter(
        target,
        {"schema": "judge-launcher.v1", "status": "starting"},
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload == {"schema": "judge-launcher.v1", "status": "starting"}


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
    tmp_path: Path,
    platform_name: str,
    mode: str,
    has_gui: bool,
    expected_name: str,
    native_gui: bool,
) -> None:
    sumo = tmp_path / ("sumo.exe" if platform_name == "win32" else "sumo")
    gui = tmp_path / "sumo-gui.exe" if has_gui else None

    selection = run_judge.select_runtime(
        mode,
        platform_name=platform_name,
        sumo=sumo,
        sumo_gui=gui,
    )

    assert selection.sumo_binary.name == expected_name
    assert selection.native_gui is native_gui


def test_native_mode_fails_outside_windows(tmp_path: Path) -> None:
    with pytest.raises(run_judge.LauncherError, match="native GUI requires Windows"):
        run_judge.select_runtime(
            "native",
            platform_name="linux",
            sumo=tmp_path / "sumo",
            sumo_gui=tmp_path / "sumo-gui",
        )


def test_parse_args_accepts_container_gui() -> None:
    args = run_judge.parse_args(["--gui-mode", "container-gui", "--no-browser"])

    assert args.gui_mode == "container-gui"


def test_container_gui_selects_sumo_gui_without_native_focus(tmp_path: Path) -> None:
    selection = run_judge.select_runtime(
        "container-gui",
        platform_name="linux",
        environ={"DISPLAY": ":99"},
        sumo=None,
        sumo_gui=tmp_path / "sumo-gui",
    )

    assert selection == run_judge.RuntimeSelection(
        "container-gui", tmp_path / "sumo-gui", False
    )


@pytest.mark.parametrize(
    ("platform_name", "environ", "sumo_gui", "message"),
    [
        ("win32", {"DISPLAY": ":99"}, Path("sumo-gui"), "non-Windows"),
        ("linux", {}, Path("sumo-gui"), "DISPLAY"),
        ("linux", {"DISPLAY": " \t"}, Path("sumo-gui"), "DISPLAY"),
        ("linux", {"DISPLAY": ":99"}, None, "sumo-gui"),
    ],
)
def test_container_gui_rejects_invalid_runtime(
    platform_name: str,
    environ: dict[str, str],
    sumo_gui: Path | None,
    message: str,
) -> None:
    with pytest.raises(run_judge.LauncherError, match=message):
        run_judge.select_runtime(
            "container-gui",
            platform_name=platform_name,
            environ=environ,
            sumo=None,
            sumo_gui=sumo_gui,
        )


def test_container_gui_runtime_diagnostics_and_native_focus_are_disabled(
    tmp_path: Path,
) -> None:
    runtime = run_judge.select_runtime(
        "container-gui",
        platform_name="linux",
        environ={"DISPLAY": ":99"},
        sumo=None,
        sumo_gui=tmp_path / "sumo-gui",
    )
    registry = run_judge.RunnerRegistry(runtime, runner_type=object)

    assert runtime.mode == "container-gui"
    assert runtime.native_gui is False
    assert registry.show_native_gui("missing-run") == (
        False,
        "native GUI disabled by launcher mode",
    )


def test_collect_preflight_windows_headless_keeps_gui_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "api" / "static" / "dist").mkdir(parents=True)
    (tmp_path / "api" / "static" / "dist" / "index.html").write_text(
        "<html></html>", encoding="utf-8"
    )
    (tmp_path / "output").mkdir()
    args = SimpleNamespace(
        host="127.0.0.1",
        port=8000,
        port_attempts=1,
        diagnostics=tmp_path / "launcher.json",
        gui_mode="headless",
    )
    resolved: list[str] = []
    sumo = tmp_path / "sumo.exe"
    sumo_gui = tmp_path / "sumo-gui.exe"

    def resolve(name: str) -> Path:
        resolved.append(name)
        return {"sumo.exe": sumo, "sumo-gui.exe": sumo_gui}[name]

    monkeypatch.setattr(run_judge.sys, "platform", "win32")
    monkeypatch.setattr(run_judge, "resolve_sumo_executable", resolve)
    monkeypatch.setattr(run_judge, "_executable_version", lambda _path: "1.27.1")
    monkeypatch.setattr(run_judge, "_package_version", lambda _package: "1.0")
    monkeypatch.setattr(run_judge, "_package_import_error", lambda _module: None)

    checks, runtime, _selection = run_judge.collect_preflight(
        tmp_path, args, "project_venv"
    )

    assert resolved == ["sumo.exe", "sumo-gui.exe"]
    assert runtime == run_judge.RuntimeSelection("headless", sumo, False)
    assert checks["sumo"]["mode"] == "headless"
    assert checks["sumo"]["gui"] == {"status": "pass", "version": "1.27.1"}


def test_collect_preflight_linux_container_gui_resolves_gui_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "api" / "static" / "dist").mkdir(parents=True)
    (tmp_path / "api" / "static" / "dist" / "index.html").write_text(
        "<html></html>", encoding="utf-8"
    )
    (tmp_path / "output").mkdir()
    args = SimpleNamespace(
        host="127.0.0.1",
        port=8000,
        port_attempts=1,
        diagnostics=tmp_path / "launcher.json",
        gui_mode="container-gui",
    )
    resolved: list[str] = []
    sumo = tmp_path / "sumo"
    sumo_gui = tmp_path / "sumo-gui"

    def resolve(name: str) -> Path:
        resolved.append(name)
        return {"sumo": sumo, "sumo-gui": sumo_gui}[name]

    monkeypatch.setattr(run_judge.sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":99")
    monkeypatch.setattr(run_judge, "resolve_sumo_executable", resolve)
    monkeypatch.setattr(run_judge, "_executable_version", lambda _path: "1.27.1")
    monkeypatch.setattr(run_judge, "_package_version", lambda _package: "1.0")
    monkeypatch.setattr(run_judge, "_package_import_error", lambda _module: None)

    checks, runtime, _selection = run_judge.collect_preflight(
        tmp_path, args, "project_venv"
    )

    assert resolved == ["sumo", "sumo-gui"]
    assert runtime == run_judge.RuntimeSelection("container-gui", sumo_gui, False)
    assert checks["sumo"]["mode"] == "container-gui"
    assert checks["sumo"]["native_gui"] is False
    assert checks["sumo"]["gui"] == {"status": "pass", "version": "1.27.1"}


def test_preflight_fails_when_production_assets_are_missing(tmp_path: Path) -> None:
    (tmp_path / "api" / "static" / "dist").mkdir(parents=True)
    (tmp_path / "output").mkdir()
    args = SimpleNamespace(
        host="127.0.0.1",
        port=8000,
        port_attempts=10,
        diagnostics=tmp_path / "launcher.json",
        gui_mode="headless",
    )

    with pytest.raises(run_judge.PreflightError, match="web build unavailable"):
        run_judge.collect_preflight(tmp_path, args, "project_venv")


class _FakeResponse:
    def __init__(self, status: int, payload: dict[str, object]) -> None:
        self.status = status
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class _SequencedOpener:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)

    def __call__(self, *_args, **_kwargs) -> _FakeResponse:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_wait_for_health_accepts_only_exact_ok_json() -> None:
    clock = _FakeClock()
    opener = _SequencedOpener(
        [
            ConnectionRefusedError(),
            _FakeResponse(200, {"status": "starting"}),
            _FakeResponse(200, {"status": "ok", "run_workers": 1}),
        ]
    )

    result = run_judge.wait_for_health(
        "http://127.0.0.1:8000/api/health",
        5.0,
        opener=opener,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    assert result.status == "pass"
    assert result.attempts == 3


def test_wait_for_health_stops_when_launcher_shutdown_is_requested() -> None:
    stop_event = __import__("threading").Event()
    stop_event.set()

    result = run_judge.wait_for_health(
        "http://127.0.0.1:8000/api/health",
        5.0,
        opener=lambda *_args, **_kwargs: pytest.fail("health must not be queried after cancellation"),
        stop_event=stop_event,
    )

    assert result == run_judge.HealthResult("fail", 0, "health wait cancelled")


def test_perform_readiness_opens_browser_only_after_health(tmp_path: Path) -> None:
    events: list[str] = []
    server = SimpleNamespace(should_exit=False)
    writer = run_judge.DiagnosticsWriter(
        tmp_path / "launcher.json",
        {"schema": "judge-launcher.v1", "status": "starting"},
    )

    result = run_judge.perform_readiness(
        server,
        writer,
        "http://127.0.0.1:8000/api/health",
        "http://127.0.0.1:8000/",
        timeout=5.0,
        open_browser=True,
        wait_for_health_fn=lambda *_args, **_kwargs: (
            events.append("health")
            or run_judge.HealthResult("pass", 1, "status ok")
        ),
        browser_open=lambda *_args, **_kwargs: events.append("browser") or True,
    )

    assert result.status == "pass"
    assert events == ["health", "browser"]
    assert writer.snapshot()["status"] == "ready"
    assert writer.snapshot()["ready_at"].endswith("Z")
    assert server.should_exit is False


def test_build_application_shuts_down_created_service_when_create_app_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from api import server as api_server
    from engine import run_service as run_service_module

    created: list[object] = []

    class _CreatedService:
        def __init__(self, **_kwargs) -> None:
            self.shutdown_waits: list[bool] = []
            created.append(self)

        def shutdown(self, wait: bool = True) -> None:
            self.shutdown_waits.append(wait)

    monkeypatch.setattr(run_service_module, "RunService", _CreatedService)
    monkeypatch.setattr(
        api_server,
        "create_app",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("create_app failed")),
    )
    registry = SimpleNamespace(
        create_runner=lambda **_kwargs: object(),
        show_native_gui=lambda _run_id: (False, "not started"),
    )

    with pytest.raises(RuntimeError, match="create_app failed"):
        run_judge.build_application(
            tmp_path,
            run_judge.RuntimeSelection("headless", tmp_path / "sumo", False),
            runner_registry=registry,
        )

    assert len(created) == 1
    assert created[0].shutdown_waits == [True]


def test_run_server_opens_browser_after_health_and_records_stop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []
    browser_seen = __import__("threading").Event()

    runtime = run_judge.RuntimeSelection("headless", tmp_path / "sumo", False)
    selection = run_judge.PortSelection(8000, 8000, ())

    class _FakeService:
        def __init__(self) -> None:
            self.shutdown_calls = 0

        def shutdown(self, wait: bool = True) -> None:
            self.shutdown_calls += 1

    service = _FakeService()
    monkeypatch.setattr(
        run_judge,
        "collect_preflight",
        lambda *_args: ({"status": "pass"}, runtime, selection),
    )
    monkeypatch.setattr(
        run_judge,
        "build_application",
        lambda *_args, **_kwargs: (SimpleNamespace(), service, SimpleNamespace()),
    )

    class _FakeServer:
        def __init__(self) -> None:
            self.should_exit = False
            self.run_calls = 0

        def run(self) -> None:
            self.run_calls += 1
            assert browser_seen.wait(timeout=2.0)
            events.append("server-return")

    fake_server = _FakeServer()

    def health_opener(*_args, **_kwargs):
        events.append("health")
        return _FakeResponse(200, {"status": "ok", "run_workers": 1})

    def browser_open(*_args, **_kwargs):
        events.append("browser")
        browser_seen.set()
        return True

    code = run_judge.run_server(
        SimpleNamespace(
            host="127.0.0.1",
            port=8000,
            port_attempts=10,
            open_browser=True,
            gui_mode="headless",
            health_timeout=5.0,
            diagnostics=tmp_path / "launcher.json",
        ),
        repo_root=tmp_path,
        server_factory=lambda _config: fake_server,
        browser_open=browser_open,
        health_opener=health_opener,
    )

    assert code == 0
    assert fake_server.run_calls == 1
    assert events == ["health", "browser", "server-return"]
    payload = json.loads((tmp_path / "launcher.json").read_text(encoding="utf-8"))
    assert payload["status"] == "stopped"
    assert payload["browser"]["requested"] is True
    assert service.shutdown_calls == 1


def test_run_server_marks_early_server_exit_before_health_as_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = run_judge.RuntimeSelection("headless", tmp_path / "sumo", False)
    selection = run_judge.PortSelection(8000, 8000, ())

    class _FakeService:
        def __init__(self) -> None:
            self.shutdown_waits: list[bool] = []

        def shutdown(self, wait: bool = True) -> None:
            self.shutdown_waits.append(wait)

    service = _FakeService()

    monkeypatch.setattr(
        run_judge,
        "collect_preflight",
        lambda *_args: ({"status": "pass"}, runtime, selection),
    )
    monkeypatch.setattr(
        run_judge,
        "build_application",
        lambda *_args, **_kwargs: (SimpleNamespace(), service, SimpleNamespace()),
    )

    class _EarlyExitServer:
        should_exit = False

        def run(self) -> None:
            return None

    code = run_judge.run_server(
        SimpleNamespace(
            host="127.0.0.1",
            port=8000,
            port_attempts=10,
            open_browser=False,
            gui_mode="headless",
            health_timeout=5.0,
            diagnostics=tmp_path / "launcher.json",
        ),
        repo_root=tmp_path,
        server_factory=lambda _config: _EarlyExitServer(),
        health_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionRefusedError()),
    )

    payload = json.loads((tmp_path / "launcher.json").read_text(encoding="utf-8"))
    assert code == 2
    assert payload["status"] == "failed"
    assert payload["health"]["status"] == "fail"
    assert payload["stopped_at"]
    assert service.shutdown_waits == [True]


def test_run_server_records_normal_stop_when_interrupt_follows_health(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = run_judge.RuntimeSelection("headless", tmp_path / "sumo", False)
    selection = run_judge.PortSelection(8000, 8000, ())

    class _FakeService:
        def __init__(self) -> None:
            self.shutdown_waits: list[bool] = []

        def shutdown(self, wait: bool = True) -> None:
            self.shutdown_waits.append(wait)

    service = _FakeService()

    monkeypatch.setattr(
        run_judge,
        "collect_preflight",
        lambda *_args: ({"status": "pass"}, runtime, selection),
    )
    monkeypatch.setattr(
        run_judge,
        "build_application",
        lambda *_args, **_kwargs: (SimpleNamespace(), service, SimpleNamespace()),
    )
    readiness_seen = threading.Event()

    class _InterruptServer:
        should_exit = False

        def run(self) -> None:
            assert readiness_seen.wait(timeout=2.0)
            raise KeyboardInterrupt()

    def health_opener(*_args, **_kwargs):
        return _FakeResponse(200, {"status": "ok"})

    def browser_open(*_args, **_kwargs):
        readiness_seen.set()
        return True

    code = run_judge.run_server(
        SimpleNamespace(
            host="127.0.0.1",
            port=8000,
            port_attempts=10,
            open_browser=True,
            gui_mode="headless",
            health_timeout=5.0,
            diagnostics=tmp_path / "launcher.json",
        ),
        repo_root=tmp_path,
        server_factory=lambda _config: _InterruptServer(),
        browser_open=browser_open,
        health_opener=health_opener,
    )

    payload = json.loads((tmp_path / "launcher.json").read_text(encoding="utf-8"))
    assert code == 0
    assert payload["status"] == "stopped"
    assert service.shutdown_waits == [True]
    assert not any(
        thread.name == "judge-health" and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_run_server_shuts_down_service_when_server_run_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = run_judge.RuntimeSelection("headless", tmp_path / "sumo", False)
    selection = run_judge.PortSelection(8000, 8000, ())

    class _FakeService:
        def __init__(self) -> None:
            self.shutdown_waits: list[bool] = []

        def shutdown(self, wait: bool = True) -> None:
            self.shutdown_waits.append(wait)

    service = _FakeService()
    monkeypatch.setattr(
        run_judge,
        "collect_preflight",
        lambda *_args: ({"status": "pass"}, runtime, selection),
    )
    monkeypatch.setattr(
        run_judge,
        "build_application",
        lambda *_args, **_kwargs: (SimpleNamespace(), service, SimpleNamespace()),
    )

    class _FailingServer:
        should_exit = False

        def run(self) -> None:
            raise RuntimeError("server run failed")

    code = run_judge.run_server(
        SimpleNamespace(
            host="127.0.0.1",
            port=8000,
            port_attempts=10,
            open_browser=False,
            gui_mode="headless",
            health_timeout=5.0,
            diagnostics=tmp_path / "launcher.json",
        ),
        repo_root=tmp_path,
        server_factory=lambda _config: _FailingServer(),
        health_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ConnectionRefusedError()
        ),
    )

    payload = json.loads((tmp_path / "launcher.json").read_text(encoding="utf-8"))
    assert code == 2
    assert service.shutdown_waits == [True]
    assert payload["status"] == "failed"
    assert payload["stopped_at"]
    assert "RuntimeError: server run failed" in payload["reason"]
    assert not any(
        thread.name == "judge-health" and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_run_server_cleans_up_and_preserves_system_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = run_judge.RuntimeSelection("headless", tmp_path / "sumo", False)
    selection = run_judge.PortSelection(8000, 8000, ())

    class _FakeService:
        def __init__(self) -> None:
            self.shutdown_waits: list[bool] = []

        def shutdown(self, wait: bool = True) -> None:
            self.shutdown_waits.append(wait)

    service = _FakeService()
    monkeypatch.setattr(
        run_judge,
        "collect_preflight",
        lambda *_args: ({"status": "pass"}, runtime, selection),
    )
    monkeypatch.setattr(
        run_judge,
        "build_application",
        lambda *_args, **_kwargs: (SimpleNamespace(), service, SimpleNamespace()),
    )

    class _ExitingServer:
        should_exit = False

        def run(self) -> None:
            raise SystemExit(7)

    with pytest.raises(SystemExit) as caught:
        run_judge.run_server(
            SimpleNamespace(
                host="127.0.0.1",
                port=8000,
                port_attempts=10,
                open_browser=False,
                gui_mode="headless",
                health_timeout=5.0,
                diagnostics=tmp_path / "launcher.json",
            ),
            repo_root=tmp_path,
            server_factory=lambda _config: _ExitingServer(),
            health_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                ConnectionRefusedError()
            ),
        )

    payload = json.loads((tmp_path / "launcher.json").read_text(encoding="utf-8"))
    assert caught.value.code == 7
    assert service.shutdown_waits == [True]
    assert payload["status"] == "failed"
    assert payload["stopped_at"]
    assert "SystemExit: 7" in payload["reason"]
    assert not any(
        thread.name == "judge-health" and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_run_server_cleans_service_when_uvicorn_construction_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = run_judge.RuntimeSelection("headless", tmp_path / "sumo", False)
    selection = run_judge.PortSelection(8000, 8000, ())
    service = SimpleNamespace(shutdown_calls=0)

    def shutdown(*, wait: bool = True) -> None:
        assert wait is True
        service.shutdown_calls += 1

    service.shutdown = shutdown
    monkeypatch.setattr(
        run_judge,
        "collect_preflight",
        lambda *_args: ({"status": "pass"}, runtime, selection),
    )
    monkeypatch.setattr(
        run_judge,
        "build_application",
        lambda *_args, **_kwargs: (SimpleNamespace(), service, SimpleNamespace()),
    )

    def fail_server_factory(_config):
        raise RuntimeError("uvicorn construction failed")

    code = run_judge.run_server(
        SimpleNamespace(
            host="127.0.0.1",
            port=8000,
            port_attempts=10,
            open_browser=False,
            gui_mode="headless",
            health_timeout=5.0,
            diagnostics=tmp_path / "launcher.json",
        ),
        repo_root=tmp_path,
        server_factory=fail_server_factory,
    )

    payload = json.loads((tmp_path / "launcher.json").read_text(encoding="utf-8"))
    assert code == 2
    assert service.shutdown_calls == 1
    assert payload["status"] == "failed"
    assert "uvicorn construction failed" in payload["reason"]


@pytest.mark.parametrize(
    "raised",
    [SystemExit(9), KeyboardInterrupt("uvicorn construction interrupted")],
    ids=["system-exit", "keyboard-interrupt"],
)
def test_run_server_cleans_service_and_preserves_baseexception_from_server_factory(
    raised: BaseException,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = run_judge.RuntimeSelection("headless", tmp_path / "sumo", False)
    selection = run_judge.PortSelection(8000, 8000, ())

    class _FakeService:
        def __init__(self) -> None:
            self.shutdown_waits: list[bool] = []

        def shutdown(self, wait: bool = True) -> None:
            self.shutdown_waits.append(wait)

    service = _FakeService()
    monkeypatch.setattr(
        run_judge,
        "collect_preflight",
        lambda *_args: ({"status": "pass"}, runtime, selection),
    )
    monkeypatch.setattr(
        run_judge,
        "build_application",
        lambda *_args, **_kwargs: (SimpleNamespace(), service, SimpleNamespace()),
    )

    def fail_server_factory(_config):
        raise raised

    with pytest.raises(type(raised)) as caught:
        run_judge.run_server(
            SimpleNamespace(
                host="127.0.0.1",
                port=8000,
                port_attempts=10,
                open_browser=False,
                gui_mode="headless",
                health_timeout=5.0,
                diagnostics=tmp_path / "launcher.json",
            ),
            repo_root=tmp_path,
            server_factory=fail_server_factory,
        )

    payload = json.loads((tmp_path / "launcher.json").read_text(encoding="utf-8"))
    assert caught.value is raised
    assert service.shutdown_waits == [True]
    assert payload["status"] == "failed"
    assert payload["stopped_at"]
    assert type(raised).__name__ in payload["reason"]


def test_preflight_sumo_failure_keeps_detected_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    index = tmp_path / "api" / "static" / "dist" / "index.html"
    index.parent.mkdir(parents=True)
    index.write_text("ok", encoding="utf-8")
    (tmp_path / "output").mkdir()
    sumo = tmp_path / "sumo.exe"
    sumo.write_bytes(b"")
    args = SimpleNamespace(
        host="127.0.0.1",
        port=8000,
        port_attempts=10,
        diagnostics=tmp_path / "launcher.json",
        gui_mode="headless",
    )
    monkeypatch.setattr(run_judge, "resolve_sumo_executable", lambda *_args, **_kwargs: sumo)
    monkeypatch.setattr(
        run_judge,
        "select_runtime",
        lambda *_args, **_kwargs: run_judge.RuntimeSelection("headless", sumo, False),
    )
    monkeypatch.setattr(run_judge, "_executable_version", lambda _path: "1.26.0")

    with pytest.raises(run_judge.PreflightError) as error:
        run_judge.collect_preflight(tmp_path, args, "project_venv")

    assert error.value.checks["sumo"]["version"] == "1.26.0"
    assert error.value.checks["sumo"]["status"] == "fail"


def test_run_server_publishes_stable_preflight_sections_at_top_level(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = run_judge.RuntimeSelection("headless", tmp_path / "sumo.exe", False)
    selection = run_judge.PortSelection(8000, 8002, (8000, 8001))
    checks = {
        "python": {"status": "pass", "source": "project_venv"},
        "dependencies": {"status": "pass", "packages": {"fastapi": "1.0"}},
        "sumo": {"status": "pass", "version": "1.27.1"},
        "assets": {"status": "pass", "index": "api/static/dist/index.html"},
        "output": {"status": "pass", "run_dir": "output/runs"},
        "network": {
            "requested_port": selection.requested,
            "selected_port": selection.selected,
            "conflicts": list(selection.conflicts),
        },
    }

    class _FakeService:
        def shutdown(self, wait: bool = True) -> None:
            del wait

    monkeypatch.setattr(run_judge, "collect_preflight", lambda *_args: (checks, runtime, selection))
    monkeypatch.setattr(
        run_judge,
        "build_application",
        lambda *_args, **_kwargs: (SimpleNamespace(), _FakeService(), SimpleNamespace()),
    )

    class _FakeServer:
        should_exit = False

        def run(self) -> None:
            self.should_exit = True

    code = run_judge.run_server(
        SimpleNamespace(
            host="127.0.0.1",
            port=8000,
            port_attempts=10,
            open_browser=False,
            gui_mode="headless",
            health_timeout=1.0,
            diagnostics=tmp_path / "launcher.json",
        ),
        repo_root=tmp_path,
        server_factory=lambda _config: _FakeServer(),
        health_opener=lambda *_args, **_kwargs: _FakeResponse(200, {"status": "ok"}),
    )

    assert code == 0
    payload = json.loads((tmp_path / "launcher.json").read_text(encoding="utf-8"))
    for section in ("python", "dependencies", "sumo", "assets", "output", "network", "health", "browser"):
        assert section in payload
    assert payload["python"]["source"] == "project_venv"
    assert payload["assets"]["index"] == "api/static/dist/index.html"
    assert payload["network"]["selected_port"] == 8002
    assert payload["network"]["scan_count"] == 3
    assert payload["output"]["diagnostics_dir"] == "."


def test_run_server_writes_container_gui_runtime_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = run_judge.RuntimeSelection("container-gui", tmp_path / "sumo-gui", False)
    selection = run_judge.PortSelection(8000, 8000, ())
    checks = {
        "sumo": {
            "status": "pass",
            "mode": "container-gui",
            "native_gui": False,
        },
        "output": {"status": "pass", "run_dir": "output/runs"},
    }

    class _FakeService:
        def shutdown(self, wait: bool = True) -> None:
            del wait

    monkeypatch.setattr(
        run_judge,
        "collect_preflight",
        lambda *_args: (checks, runtime, selection),
    )
    monkeypatch.setattr(
        run_judge,
        "build_application",
        lambda *_args, **_kwargs: (SimpleNamespace(), _FakeService(), SimpleNamespace()),
    )

    class _FakeServer:
        should_exit = False

        def run(self) -> None:
            self.should_exit = True

    code = run_judge.run_server(
        SimpleNamespace(
            host="127.0.0.1",
            port=8000,
            port_attempts=1,
            open_browser=False,
            gui_mode="container-gui",
            health_timeout=1.0,
            diagnostics=tmp_path / "launcher.json",
        ),
        repo_root=tmp_path,
        server_factory=lambda _config: _FakeServer(),
        health_opener=lambda *_args, **_kwargs: _FakeResponse(200, {"status": "ok"}),
    )

    payload = json.loads((tmp_path / "launcher.json").read_text(encoding="utf-8"))
    assert code == 0
    assert payload["runtime"] == {
        "mode": "container-gui",
        "native_gui": False,
        "sumo_binary": "sumo-gui",
    }


def test_main_forwards_interpreter_source_to_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(run_judge, "ensure_project_interpreter", lambda *_args, **_kwargs: "project_venv")
    monkeypatch.setattr(
        run_judge,
        "run_server",
        lambda args, **kwargs: captured.update(args=args, **kwargs) or 0,
    )

    assert run_judge.main(["--no-browser"]) == 0
    assert captured["interpreter_source"] == "project_venv"


def test_runner_registry_injects_selected_binary_and_registers_run(tmp_path: Path) -> None:
    created: list[dict[str, object]] = []

    class _FakeRunner:
        def __init__(self, **kwargs):
            created.append(kwargs)
            self.artifacts = kwargs["artifacts"]
            self.bridge = SimpleNamespace(process_id=41005)

    runtime = run_judge.RuntimeSelection("native", tmp_path / "sumo-gui.exe", True)
    registry = run_judge.RunnerRegistry(runtime, runner_type=_FakeRunner)
    artifacts = SimpleNamespace(run_id="run-owned")

    runner = registry.create_runner(scene=object(), algorithm=object(), artifacts=artifacts)

    assert created[0]["sumo_binary"] == str(runtime.sumo_binary)
    assert registry.runner_for("run-owned") is runner


def test_show_native_gui_uses_only_requested_runs_owned_pid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _FakeRunner:
        def __init__(self, artifacts, **_kwargs):
            pids = {"run-a": 41005, "run-b": 41006}
            self.artifacts = artifacts
            self.process = SimpleNamespace(poll=lambda: None, pid=pids[artifacts.run_id])
            self.bridge = SimpleNamespace(
                process_id=pids[artifacts.run_id],
                _owned_process=self.process,
            )

    registry = run_judge.RunnerRegistry(
        run_judge.RuntimeSelection("native", tmp_path / "sumo-gui.exe", True),
        runner_type=_FakeRunner,
    )
    registry.create_runner(artifacts=SimpleNamespace(run_id="run-a"))
    registry.create_runner(artifacts=SimpleNamespace(run_id="run-b"))
    focused: list[int] = []
    monkeypatch.setattr(
        run_judge,
        "focus_window_for_pid",
        lambda pid, **_kwargs: focused.append(pid) or (True, "focused"),
    )

    assert registry.show_native_gui("run-a") == (True, "focused")
    assert focused == [41005]


def test_show_native_gui_rejects_stale_runner_after_child_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _ExitedRunner:
        def __init__(self, artifacts, **_kwargs):
            self.bridge = SimpleNamespace(
                process_id=41005,
                _owned_process=SimpleNamespace(poll=lambda: 0, pid=41005),
            )

    registry = run_judge.RunnerRegistry(
        run_judge.RuntimeSelection("native", tmp_path / "sumo-gui.exe", True),
        runner_type=_ExitedRunner,
    )
    registry.create_runner(artifacts=SimpleNamespace(run_id="run-exited"))
    monkeypatch.setattr(run_judge, "focus_window_for_pid", lambda *_args, **_kwargs: pytest.fail("must not focus stale PID"))

    assert registry.show_native_gui("run-exited") == (False, "SUMO process is not ready")


class _FakeUser32:
    def __init__(self, windows: dict[int, dict[str, object]]) -> None:
        self.windows = windows
        self.restored: list[int] = []
        self.raised: list[int] = []
        self.foreground: list[int] = []
        self.current_foreground: int | None = None

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

    def BringWindowToTop(self, hwnd):
        self.raised.append(hwnd)
        return True

    def SetForegroundWindow(self, hwnd):
        self.foreground.append(hwnd)
        self.current_foreground = hwnd
        return True

    def GetForegroundWindow(self):
        return self.current_foreground or 0


def test_focus_window_enumerates_exact_pid_and_restores_only_that_window() -> None:
    user32 = _FakeUser32(
        {
            101: {"pid": 41005, "visible": True},
            202: {"pid": 99999, "visible": True},
        }
    )

    shown, reason = run_judge.focus_window_for_pid(
        41005,
        platform_name="win32",
        user32=user32,
    )

    assert shown is True
    assert reason == "focused SUMO process 41005"
    assert user32.restored == [101]
    assert user32.foreground == [101]


def test_focus_window_reports_when_windows_refuses_keyboard_focus() -> None:
    class _ForegroundRestrictedUser32(_FakeUser32):
        def SetForegroundWindow(self, hwnd):
            self.foreground.append(hwnd)
            return False

    user32 = _ForegroundRestrictedUser32(
        {101: {"pid": 41005, "visible": True}}
    )

    shown, reason = run_judge.focus_window_for_pid(
        41005,
        platform_name="win32",
        user32=user32,
    )

    assert shown is False
    assert reason == "could not foreground SUMO process 41005"
    assert user32.restored == [101]
    assert user32.raised == [101]
    assert user32.foreground == [101]


def test_focus_window_reports_headless_and_unknown_windows() -> None:
    assert run_judge.focus_window_for_pid(41005, platform_name="linux") == (
        False,
        "native GUI is supported only on Windows",
    )
    user32 = _FakeUser32({101: {"pid": 99999, "visible": True}})
    assert run_judge.focus_window_for_pid(41005, platform_name="win32", user32=user32) == (
        False,
        "no visible window for SUMO process 41005",
    )


def test_powershell_wrapper_executes_project_launcher_help() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    wrapper = repo_root / "scripts" / "start_judge.ps1"

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
            "--help",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert "--gui-mode" in result.stdout
    assert "--no-browser" in result.stdout


def test_batch_wrapper_executes_project_launcher_help() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    wrapper = repo_root / "scripts" / "start_judge.bat"

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(wrapper), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert "--gui-mode" in result.stdout


def test_batch_wrapper_preserves_nonzero_launcher_exit_code(tmp_path: Path) -> None:
    wrapper = tmp_path / "start_judge.bat"
    wrapper.write_text(
        "@echo off\r\n"
        "powershell.exe -NoProfile -Command \"exit 7\"\r\n"
        "exit /b %ERRORLEVEL%\r\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(wrapper)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 7


def test_root_powershell_frontend_launcher_runs_from_any_working_directory(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    wrapper = repo_root / "start_frontend.ps1"

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
            "--help",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert "--gui-mode" in result.stdout
    assert "--no-browser" in result.stdout


def test_root_batch_frontend_launcher_runs_from_any_working_directory(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    wrapper = repo_root / "start_frontend.bat"

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(wrapper), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert "--gui-mode" in result.stdout
