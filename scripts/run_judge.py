"""Start the judge-facing FastAPI, Web, and SUMO runtime with diagnostics."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import importlib.metadata
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Any
import urllib.error
import urllib.request
from uuid import uuid4
import webbrowser


REQUIRED_SUMO_VERSION = "1.27.1"


class LauncherError(RuntimeError):
    """Raised when the native launcher cannot satisfy a required contract."""

    def __init__(self, message: str, *, details: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.details = dict(details or {})


class PreflightError(LauncherError):
    """Raised when a required runtime preflight check fails."""

    def __init__(
        self,
        message: str,
        *,
        checks: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message, details={"checks": dict(checks or {})})
        self.checks = dict(checks or {})


@dataclass(frozen=True)
class RuntimeSelection:
    mode: str
    sumo_binary: Path
    native_gui: bool


@dataclass(frozen=True)
class HealthResult:
    status: str
    attempts: int
    detail: str


class PortSelection(tuple):
    """Immutable requested/selected port record with encountered conflicts."""

    __slots__ = ()

    def __new__(
        cls,
        requested: int,
        selected: int,
        conflicts: tuple[int, ...],
    ) -> "PortSelection":
        return tuple.__new__(cls, (requested, selected, conflicts))

    @property
    def requested(self) -> int:
        return self[0]

    @property
    def selected(self) -> int:
        return self[1]

    @property
    def conflicts(self) -> tuple[int, ...]:
        return self[2]


def repo_root_from_script(script_path: Path) -> Path:
    """Return the repository root containing the ``scripts`` directory."""
    return Path(script_path).resolve().parent.parent


def _bounded_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be in 1..65535")
    return port


def _bounded_attempts(value: str) -> int:
    attempts = int(value)
    if not 1 <= attempts <= 10:
        raise argparse.ArgumentTypeError("port attempts must be in 1..10")
    return attempts


def _positive_finite(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("health timeout must be finite and > 0")
    return number


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the stable judge-launcher command contract."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=_bounded_port, default=8000)
    parser.add_argument("--port-attempts", type=_bounded_attempts, default=10)
    browser = parser.add_mutually_exclusive_group()
    browser.add_argument(
        "--open-browser",
        dest="open_browser",
        action="store_true",
    )
    browser.add_argument(
        "--no-browser",
        dest="open_browser",
        action="store_false",
    )
    parser.set_defaults(open_browser=True)
    parser.add_argument(
        "--gui-mode",
        choices=("auto", "native", "headless", "container-gui"),
        default="auto",
    )
    parser.add_argument("--health-timeout", type=_positive_finite, default=30.0)
    parser.add_argument(
        "--diagnostics",
        type=Path,
        default=Path("output/evidence/judge-launch/launcher.json"),
    )
    return parser.parse_args(argv)


def project_interpreter(
    repo_root: Path,
    platform_name: str | None = None,
) -> Path | None:
    """Return the repository virtual-environment interpreter when present."""
    platform_name = platform_name or sys.platform
    relative = (
        Path(".venv") / "Scripts" / "python.exe"
        if platform_name == "win32"
        else Path(".venv") / "bin" / "python"
    )
    candidate = Path(repo_root) / relative
    return candidate if candidate.is_file() else None


def _same_interpreter(left: Path, right: Path, platform_name: str) -> bool:
    left_value = str(left.resolve())
    right_value = str(right.resolve())
    if platform_name == "win32":
        return left_value.casefold() == right_value.casefold()
    return left_value == right_value


def ensure_project_interpreter(
    repo_root: Path,
    argv: Sequence[str],
    *,
    executable: Path | None = None,
    platform_name: str | None = None,
    script_path: Path | None = None,
    execv: Callable[[str, list[str]], object] = os.execv,
) -> str:
    """Re-execute with the repository interpreter when one is available."""
    platform_name = platform_name or sys.platform
    selected = project_interpreter(repo_root, platform_name)
    if selected is None:
        return "current_runtime"

    selected = selected.resolve()
    current = Path(executable or sys.executable).resolve()
    if _same_interpreter(selected, current, platform_name):
        return "project_venv"

    script = Path(script_path or __file__).resolve()
    command = [str(selected), str(script), *map(str, argv)]
    execv(str(selected), command)
    return "project_venv"


def select_port(
    host: str,
    requested: int,
    attempts: int = 10,
    *,
    socket_factory: Callable[..., socket.socket] = socket.socket,
) -> PortSelection:
    """Choose the first bindable port in a bounded consecutive range."""
    if not 1 <= int(requested) <= 65535:
        raise LauncherError("requested port must be in 1..65535")
    if not 1 <= int(attempts) <= 10:
        raise LauncherError("port attempts must be in 1..10")

    first = int(requested)
    last = min(65535, first + int(attempts) - 1)
    conflicts: list[int] = []
    for candidate in range(first, last + 1):
        try:
            with socket_factory(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind((host, candidate))
        except OSError:
            conflicts.append(candidate)
            continue
        return PortSelection(first, candidate, tuple(conflicts))
    raise LauncherError(
        f"no free port in {first}..{last}",
        details={
            "network": {
                "requested_port": first,
                "selected_port": None,
                "scan_count": len(conflicts),
                "conflicts": list(conflicts),
            }
        },
    )


def resolve_sumo_executable(
    name: str,
    *,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> Path | None:
    """Resolve a SUMO binary from SUMO_HOME, PATH, or the Windows install path."""
    environ = environ or os.environ
    executable_name = name
    sumo_home = environ.get("SUMO_HOME")
    if sumo_home:
        candidate = Path(sumo_home) / "bin" / executable_name
        if candidate.is_file():
            return candidate.resolve()
    located = which(executable_name)
    if located:
        return Path(located).resolve()
    if sys.platform == "win32":
        candidate = (
            Path("C:/Program Files (x86)/Eclipse/Sumo") / "bin" / executable_name
        )
        if candidate.is_file():
            return candidate.resolve()
    return None


def select_runtime(
    gui_mode: str,
    *,
    platform_name: str = sys.platform,
    environ: Mapping[str, str] | None = None,
    sumo: Path | None,
    sumo_gui: Path | None,
) -> RuntimeSelection:
    """Apply the explicit auto/native/headless SUMO selection policy."""
    if gui_mode not in {"auto", "native", "headless", "container-gui"}:
        raise LauncherError(f"unknown gui mode: {gui_mode}")
    if gui_mode == "container-gui":
        if platform_name == "win32":
            raise LauncherError("container GUI requires a non-Windows platform")
        environment = os.environ if environ is None else environ
        if not environment.get("DISPLAY", "").strip():
            raise LauncherError("container GUI requires DISPLAY")
        if sumo_gui is None:
            raise LauncherError("container GUI requires sumo-gui")
        return RuntimeSelection("container-gui", Path(sumo_gui), False)
    if gui_mode == "native":
        if platform_name != "win32":
            raise LauncherError("native GUI requires Windows")
        if sumo_gui is None:
            raise LauncherError("native GUI requires sumo-gui")
        return RuntimeSelection("native", Path(sumo_gui), True)
    if gui_mode == "auto" and platform_name == "win32" and sumo_gui is not None:
        return RuntimeSelection("native", Path(sumo_gui), True)
    if sumo is None:
        raise LauncherError("headless SUMO executable unavailable")
    return RuntimeSelection("headless", Path(sumo), False)


def _version_from_output(output: str | None) -> str | None:
    if not output:
        return None
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", output)
    return match.group(1) if match else None


def _executable_version(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return _version_from_output(completed.stdout or completed.stderr)


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _package_import_error(module_name: str) -> str | None:
    """Return an import failure reason without masking unexpected launcher errors."""
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _repo_relative_identity(path: Path, repo_root: Path) -> str:
    """Return a non-sensitive repository-relative runtime identity."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def resolve_diagnostics_path(repo_root: Path, requested: Path) -> Path:
    """Resolve a diagnostics target while protecting immutable judge inputs."""
    try:
        root = Path(repo_root).resolve()
        candidate = Path(requested)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
        archive = (root / "赛题资料.7z").resolve()
        official_data = (root / "data" / "intersection_data").resolve()
    except (OSError, RuntimeError) as exc:
        raise LauncherError(
            f"diagnostics path cannot be resolved safely: {type(exc).__name__}"
        ) from exc
    if (
        candidate == archive
        or candidate == official_data
        or candidate.is_relative_to(official_data)
    ):
        raise LauncherError("diagnostics path targets protected judge input")
    return candidate


class DiagnosticsWriter:
    """Publish complete launcher diagnostics through atomic file replacement."""

    def __init__(self, path: Path, initial: Mapping[str, object]) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._payload: dict[str, Any] = deepcopy(dict(initial))
        self._write(self._payload)

    def _write(self, payload: Mapping[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def update(self, **changes: object) -> dict[str, Any]:
        """Atomically replace the document and return the committed snapshot."""
        with self._lock:
            candidate = deepcopy(self._payload)
            candidate.update(deepcopy(changes))
            self._write(candidate)
            self._payload = candidate
            return deepcopy(self._payload)

    def snapshot(self) -> dict[str, Any]:
        """Return an isolated copy of the latest committed diagnostics."""
        with self._lock:
            return deepcopy(self._payload)


def collect_preflight(
    repo_root: Path,
    args: argparse.Namespace,
    interpreter_source: str,
) -> tuple[dict[str, object], RuntimeSelection, PortSelection]:
    """Collect required native checks before constructing the web server."""
    repo_root = Path(repo_root).resolve()
    static_index = repo_root / "api" / "static" / "dist" / "index.html"
    output_root = repo_root / "output" / "runs"
    diagnostics_path = Path(args.diagnostics)
    if not diagnostics_path.is_absolute():
        diagnostics_path = repo_root / diagnostics_path
    diagnostics_identity = _repo_relative_identity(
        diagnostics_path.resolve().parent,
        repo_root,
    )

    python_version = sys.version.split()[0]
    python_ok = sys.version_info >= (3, 10)
    checks: dict[str, object] = {
        "python": {
            "status": "pass" if python_ok else "fail",
            "version": python_version,
            "implementation": sys.implementation.name,
            "source": interpreter_source,
            "identity": _repo_relative_identity(Path(sys.executable), repo_root),
            "required": ">=3.10",
        },
        "dependencies": {"status": "not_run", "packages": {}, "versions": {}},
        "sumo": {
            "status": "not_run",
            "mode": args.gui_mode,
            "headless": {"status": "not_run", "version": None},
            "gui": {"status": "not_run", "version": None},
        },
        "assets": {
            "status": "pass" if static_index.is_file() else "fail",
            "index": "api/static/dist/index.html",
        },
        "output": {
            "status": "not_run",
            "diagnostics_dir": diagnostics_identity,
            "run_dir": "output/runs",
        },
        "network": {
            "host": args.host,
            "requested_port": args.port,
            "selected_port": None,
            "scan_count": 0,
            "conflicts": [],
        },
    }

    if not python_ok:
        raise PreflightError(
            f"Python {python_version} is unsupported; requires >=3.10",
            checks=checks,
        )
    if not static_index.is_file():
        raise PreflightError(
            "web build unavailable: api/static/dist/index.html is missing",
            checks=checks,
        )

    try:
        diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
        diagnostics_probe = diagnostics_path.parent / ".judge-launch-diagnostics-write-test"
        diagnostics_probe.write_text("ok", encoding="utf-8")
        diagnostics_probe.unlink()
        output_root.mkdir(parents=True, exist_ok=True)
        output_probe = output_root / ".judge-launch-write-test"
        output_probe.write_text("ok", encoding="utf-8")
        output_probe.unlink()
    except OSError as exc:
        checks["output"] = {
            **dict(checks["output"]),
            "status": "fail",
            "detail": f"output or diagnostics is not writable: {type(exc).__name__}",
        }
        raise PreflightError(str(checks["output"]["detail"]), checks=checks) from exc
    checks["output"] = {**dict(checks["output"]), "status": "pass", "writable": True}

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM):
            pass
    except OSError as exc:
        raise PreflightError(f"network preflight unavailable: {type(exc).__name__}", checks=checks) from exc

    sumo = resolve_sumo_executable("sumo.exe" if sys.platform == "win32" else "sumo")
    sumo_gui = (
        resolve_sumo_executable(
            "sumo-gui.exe" if sys.platform == "win32" else "sumo-gui"
        )
        if sys.platform == "win32" or args.gui_mode == "container-gui"
        else None
    )
    try:
        runtime = select_runtime(
            args.gui_mode,
            platform_name=sys.platform,
            environ=os.environ,
            sumo=sumo,
            sumo_gui=sumo_gui,
        )
    except LauncherError as exc:
        checks["sumo"] = {
            "status": "fail",
            "mode": args.gui_mode,
            "headless": {
                "status": "fail" if sumo is None else "not_run",
                "version": _executable_version(sumo),
            },
            "gui": {
                "status": "fail"
                if args.gui_mode in {"native", "container-gui"} and sumo_gui is None
                else "not_run",
                "version": _executable_version(sumo_gui),
            },
            "selected": None,
        }
        raise PreflightError(str(exc), checks=checks) from exc
    selected_version = _executable_version(runtime.sumo_binary)
    headless_version = _executable_version(sumo)
    gui_version = _executable_version(sumo_gui)
    checks["sumo"] = {
        "status": "pass" if selected_version == REQUIRED_SUMO_VERSION else "fail",
        "mode": runtime.mode,
        "native_gui": runtime.native_gui,
        "selected": runtime.sumo_binary.name,
        "binary": runtime.sumo_binary.name,
        "version": selected_version,
        "headless": {
            "status": "pass" if headless_version == REQUIRED_SUMO_VERSION else "not_run",
            "version": headless_version,
        },
        "gui": {
            "status": "pass" if gui_version == REQUIRED_SUMO_VERSION else "not_run",
            "version": gui_version,
        },
        "headless_version": headless_version,
        "gui_version": gui_version,
    }
    if selected_version != REQUIRED_SUMO_VERSION:
        raise PreflightError(
            f"SUMO version mismatch: detected {selected_version or 'unavailable'}; "
            f"requires {REQUIRED_SUMO_VERSION}",
            checks=checks,
        )

    dependency_modules = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "traci": "traci",
        "sumolib": "sumolib",
    }
    dependency_versions = {
        package: _package_version(package)
        for package in dependency_modules
    }
    dependency_errors = {
        package: _package_import_error(module)
        for package, module in dependency_modules.items()
    }
    dependency_packages = {
        package: {
            "status": "pass" if version is not None and error is None else "fail",
            "version": version,
            "import": "pass" if error is None else "fail",
            **({"detail": error} if error is not None else {}),
        }
        for package, (version, error) in (
            (package, (dependency_versions[package], dependency_errors[package]))
            for package in dependency_modules
        )
    }
    checks["dependencies"] = {
        "status": "pass" if all(item["status"] == "pass" for item in dependency_packages.values()) else "fail",
        "packages": dependency_packages,
        "versions": dependency_versions,
    }
    missing = [
        package
        for package, item in dependency_packages.items()
        if item["status"] != "pass"
    ]
    if missing:
        raise PreflightError(
            f"required Python packages unavailable or not importable: {', '.join(missing)}",
            checks=checks,
        )
    try:
        port = select_port(args.host, args.port, args.port_attempts)
    except LauncherError as exc:
        network = exc.details.get("network")
        if isinstance(network, Mapping):
            checks["network"] = {"host": args.host, **dict(network)}
        raise PreflightError(str(exc), checks=checks) from exc
    python_path = Path(sys.executable).resolve()
    checks["python"] = {**dict(checks["python"]), "identity": _repo_relative_identity(python_path, repo_root)}
    checks["network"] = {
        "host": args.host,
        "requested_port": port.requested,
        "selected_port": port.selected,
        "scan_count": len(port.conflicts) + 1,
        "conflicts": list(port.conflicts),
    }
    return checks, runtime, port


def wait_for_health(
    url: str,
    timeout: float,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    stop_event: threading.Event | None = None,
) -> HealthResult:
    """Wait until the health endpoint returns a JSON status exactly equal to ``ok``."""
    started = monotonic()
    attempts = 0
    detail = "health endpoint did not become ready"
    while monotonic() - started < timeout:
        if stop_event is not None and stop_event.is_set():
            return HealthResult("fail", attempts, "health wait cancelled")
        attempts += 1
        try:
            response = opener(url, timeout=min(2.0, max(0.1, timeout)))
            with response:
                status_code = getattr(response, "status", None)
                if status_code is None:
                    status_code = response.getcode()
                body = json.loads(response.read().decode("utf-8"))
            if status_code == 200 and isinstance(body, dict) and body.get("status") == "ok":
                return HealthResult("pass", attempts, "health status ok")
            detail = f"unexpected health response: status={status_code!r} body={body!r}"
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            detail = f"health request failed: {type(exc).__name__}"
        if stop_event is not None:
            stop_event.wait(0.25)
        else:
            sleep(0.25)
    return HealthResult("fail", attempts, detail)


def perform_readiness(
    server: object,
    writer: DiagnosticsWriter,
    health_url: str,
    browser_url: str,
    *,
    timeout: float,
    open_browser: bool,
    wait_for_health_fn: Callable[..., HealthResult] = wait_for_health,
    browser_open: Callable[..., bool] = webbrowser.open,
    stop_event: threading.Event | None = None,
) -> HealthResult:
    """Publish readiness and only then open the browser."""
    if stop_event is None:
        result = wait_for_health_fn(health_url, timeout)
    else:
        result = wait_for_health_fn(health_url, timeout, stop_event=stop_event)
    if stop_event is not None and stop_event.is_set() and result.status == "pass":
        result = HealthResult("fail", result.attempts, "health readiness cancelled")
    writer.update(
        health={
            "url": health_url,
            "status": result.status,
            "attempts": result.attempts,
            "detail": result.detail,
        }
    )
    if result.status != "pass":
        setattr(server, "should_exit", True)
        writer.update(status="failed", reason=result.detail)
        return result
    writer.update(status="ready", ready_at=_timestamp())
    if not open_browser:
        writer.update(browser={"requested": False, "status": "not_run", "detail": "disabled"})
        return result
    try:
        opened = bool(browser_open(browser_url, new=2))
    except Exception as exc:
        opened = False
        detail = f"browser open failed: {type(exc).__name__}"
    else:
        detail = "browser opened" if opened else "browser open returned false"
    writer.update(
        browser={"requested": True, "status": "pass" if opened else "fail", "detail": detail}
    )
    return result


def focus_window_for_pid(
    pid: int,
    *,
    platform_name: str = sys.platform,
    user32: object | None = None,
) -> tuple[bool, str]:
    """Restore and foreground the first visible window owned by one exact PID."""
    if platform_name != "win32":
        return False, "native GUI is supported only on Windows"
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False, "invalid SUMO process id"
    try:
        import ctypes

        user32 = user32 or ctypes.windll.user32
        pid_value = ctypes.c_ulong()
        matches: list[object] = []

        def callback(hwnd, _lparam):
            if not bool(user32.IsWindowVisible(hwnd)):
                return True
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_value))
            if int(pid_value.value) == pid:
                matches.append(hwnd)
                return False
            return True

        callback_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
        callback_pointer = callback_type(ctypes.c_bool, ctypes.c_void_p, ctypes.c_long)(
            callback
        )
        if not bool(user32.EnumWindows(callback_pointer, 0)) and not matches:
            return False, f"no visible window for SUMO process {pid}"
    except (AttributeError, OSError, TypeError, ValueError):
        return False, f"no visible window for SUMO process {pid}"
    if not matches:
        return False, f"no visible window for SUMO process {pid}"
    hwnd = matches[0]
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        if not bool(user32.SetForegroundWindow(hwnd)):
            return False, f"could not focus SUMO process {pid}"
    except (OSError, TypeError, ValueError):
        return False, f"could not focus SUMO process {pid}"
    return True, f"focused SUMO process {pid}"


class RunnerRegistry:
    """Map a public run ID to the exact launcher-created runner instance."""

    def __init__(self, runtime: RuntimeSelection, *, runner_type: type | None = None) -> None:
        if runner_type is None:
            from engine.runner import SimulationRunner

            runner_type = SimulationRunner
        self.runtime = runtime
        self.runner_type = runner_type
        self._runners: dict[str, object] = {}
        self._lock = threading.RLock()

    def create_runner(self, **kwargs: object) -> object:
        artifacts = kwargs.get("artifacts")
        run_id = getattr(artifacts, "run_id", None)
        if not isinstance(run_id, str) or not run_id:
            raise LauncherError("runner artifacts must provide a non-empty run_id")
        parameters = dict(kwargs)
        parameters["sumo_binary"] = str(self.runtime.sumo_binary)
        runner = self.runner_type(**parameters)
        with self._lock:
            self._runners[run_id] = runner
        return runner

    def runner_for(self, run_id: str) -> object | None:
        with self._lock:
            return self._runners.get(run_id)

    def show_native_gui(self, run_id: str) -> tuple[bool, str]:
        if not self.runtime.native_gui:
            return False, "native GUI disabled by launcher mode"
        runner = self.runner_for(run_id)
        if runner is None:
            return False, "unknown run_id"
        bridge = getattr(runner, "bridge", None)
        owned_process = getattr(bridge, "_owned_process", None)
        if owned_process is None:
            return False, "SUMO process is not ready"
        try:
            if owned_process.poll() is not None:
                return False, "SUMO process is not ready"
        except Exception:
            return False, "SUMO process is not ready"
        pid = getattr(bridge, "process_id", None)
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            return False, "SUMO process is not ready"
        owned_pid = getattr(owned_process, "pid", None)
        if isinstance(owned_pid, int) and owned_pid != pid:
            return False, "SUMO process is not ready"
        try:
            return focus_window_for_pid(pid)
        except Exception as exc:
            return False, f"could not focus SUMO process {pid}: {type(exc).__name__}"


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_application(
    repo_root: Path,
    runtime: RuntimeSelection,
    runner_registry: object | None = None,
) -> tuple[object, object, object]:
    """Compose the existing RunService and FastAPI app exactly once."""
    from api.server import create_app
    from engine.run_service import RunService

    registry = runner_registry or RunnerRegistry(runtime)
    service = RunService(
        output_root=Path(repo_root) / "output" / "runs",
        runner_factory=registry.create_runner,
    )
    service.native_gui = registry.show_native_gui
    try:
        application = create_app(
            run_service=service,
            web_dist=Path(repo_root) / "api" / "static" / "dist",
        )
    except BaseException as error:
        try:
            service.shutdown(wait=True)
        except BaseException as cleanup_error:
            add_note = getattr(error, "add_note", None)
            if callable(add_note):
                add_note(
                    "RunService shutdown after application construction failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        raise
    return application, service, registry


def run_server(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    server_factory: Callable[[object], object] | None = None,
    browser_open: Callable[..., bool] = webbrowser.open,
    health_opener: Callable[..., object] = urllib.request.urlopen,
    interpreter_source: str = "current_runtime",
) -> int:
    """Run Uvicorn on the main thread with a health-gated browser worker."""
    root = Path(repo_root or repo_root_from_script(Path(__file__))).resolve()
    try:
        diagnostics_path = resolve_diagnostics_path(root, Path(args.diagnostics))
    except LauncherError as exc:
        print(f"Judge launcher diagnostics rejected: {exc}", file=sys.stderr, flush=True)
        return 2
    diagnostics_identity = _repo_relative_identity(
        diagnostics_path.parent,
        root,
    )
    try:
        writer = DiagnosticsWriter(
            diagnostics_path,
            {
                "schema": "judge-launcher.v1",
                "status": "starting",
                "reason": "",
                "started_at": _timestamp(),
                "ready_at": None,
                "stopped_at": None,
                "python": {"status": "not_run", "source": interpreter_source},
                "dependencies": {"status": "not_run", "packages": {}},
                "sumo": {"status": "not_run", "mode": args.gui_mode},
                "assets": {"status": "not_run", "index": "api/static/dist/index.html"},
                "output": {
                    "status": "not_run",
                    "diagnostics_dir": diagnostics_identity,
                    "run_dir": "output/runs",
                },
                "health": {
                    "status": "not_run",
                    "url": None,
                    "attempts": 0,
                    "detail": "waiting for server",
                },
                "network": {
                    "host": args.host,
                    "requested_port": args.port,
                    "selected_port": None,
                    "scan_count": 0,
                    "conflicts": [],
                },
                "browser": {
                    "requested": bool(args.open_browser),
                    "status": "not_run",
                    "detail": "waiting for health",
                },
            },
        )
    except OSError as exc:
        print(f"Judge launcher diagnostics unavailable: {exc}", file=sys.stderr, flush=True)
        return 2

    def publish_failed_preflight(error: LauncherError) -> None:
        checks = getattr(error, "checks", None)
        if not isinstance(checks, Mapping) or not checks:
            return
        published = {
            key: checks[key]
            for key in ("python", "dependencies", "sumo", "assets", "output", "network")
            if key in checks
        }
        if "output" in published:
            published["output"] = {
                **dict(published["output"]),
                "diagnostics_dir": diagnostics_identity,
            }
        writer.update(preflight=dict(checks), **published)

    try:
        checks, runtime, selection = collect_preflight(root, args, interpreter_source)
        published_checks = {
            key: checks[key]
            for key in ("python", "dependencies", "sumo", "output")
            if key in checks
        }
        if "assets" in checks:
            published_checks["assets"] = checks["assets"]
        elif "static_assets" in checks:
            published_checks["assets"] = checks["static_assets"]
        if "output" in published_checks:
            published_checks["output"] = {
                **dict(published_checks["output"]),
                "diagnostics_dir": diagnostics_identity,
            }
        writer.update(
            preflight=checks,
            **published_checks,
            runtime={
                "mode": runtime.mode,
                "native_gui": runtime.native_gui,
                "sumo_binary": runtime.sumo_binary.name,
            },
            network={
                "host": args.host,
                "requested_port": selection.requested,
                "selected_port": selection.selected,
                "scan_count": len(selection.conflicts) + 1,
                "conflicts": list(selection.conflicts),
            },
        )
        application, service, _registry = build_application(root, runtime)
        try:
            import uvicorn

            config = uvicorn.Config(
                application,
                host=args.host,
                port=selection.selected,
                log_level="info",
                access_log=True,
            )
            server = (server_factory or uvicorn.Server)(config)
        except BaseException as error:
            try:
                service.shutdown(wait=True)
            except BaseException as cleanup_error:
                add_note = getattr(error, "add_note", None)
                if callable(add_note):
                    add_note(
                        "RunService shutdown after server construction failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            raise
    except BaseException as exc:
        publish_failed_preflight(exc)
        reason = str(exc)
        if not isinstance(exc, Exception):
            reason = f"{type(exc).__name__}: {exc}"
        writer.update(status="failed", reason=reason, stopped_at=_timestamp())
        if not isinstance(exc, Exception):
            raise
        return 2

    readiness: list[HealthResult] = []
    health_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    health_url = f"http://{health_host}:{selection.selected}/api/health"
    browser_url = f"http://{health_host}:{selection.selected}/"
    print(f"Judge UI: {browser_url}", flush=True)

    stop_readiness = threading.Event()

    def readiness_worker() -> None:
        try:
            result = perform_readiness(
                server,
                writer,
                health_url,
                browser_url,
                timeout=args.health_timeout,
                open_browser=bool(args.open_browser),
                wait_for_health_fn=lambda url, timeout, **kwargs: wait_for_health(
                    url,
                    timeout,
                    opener=health_opener,
                    **kwargs,
                ),
                browser_open=browser_open,
                stop_event=stop_readiness,
            )
        except Exception as exc:
            result = HealthResult("fail", 0, f"readiness worker failed: {type(exc).__name__}: {exc}")
            writer.update(
                health={
                    "url": health_url,
                    "status": result.status,
                    "attempts": result.attempts,
                    "detail": result.detail,
                },
                status="failed",
                reason=result.detail,
            )
        readiness.append(result)

    worker = threading.Thread(target=readiness_worker, name="judge-health")
    worker.start()
    run_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    try:
        server.run()
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            setattr(server, "should_exit", True)
        run_error = exc
    finally:
        stop_readiness.set()
        worker.join()
        try:
            service.shutdown(wait=True)
        except BaseException as exc:
            cleanup_error = exc
    if cleanup_error is not None:
        if run_error is None:
            run_error = cleanup_error
        else:
            add_note = getattr(run_error, "add_note", None)
            if callable(add_note):
                add_note(
                    "RunService shutdown after server exit failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
    if (
        isinstance(run_error, KeyboardInterrupt)
        and cleanup_error is None
        and readiness
        and readiness[-1].status == "pass"
    ):
        run_error = None
    if run_error is not None:
        detail = (
            "server interrupted before health readiness"
            if isinstance(run_error, KeyboardInterrupt)
            else f"server failed: {type(run_error).__name__}: {run_error}"
        )
        writer.update(status="failed", reason=detail, stopped_at=_timestamp())
        if not isinstance(run_error, Exception) and not isinstance(run_error, KeyboardInterrupt):
            raise run_error
        return 2
    if not readiness:
        writer.update(
            status="failed",
            reason="server stopped before health readiness",
            stopped_at=_timestamp(),
        )
        return 2
    if readiness[-1].status != "pass":
        writer.update(status="failed", reason=readiness[-1].detail, stopped_at=_timestamp())
        return 2
    writer.update(status="stopped", stopped_at=_timestamp(), reason="server stopped")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint used by PowerShell, batch, Docker, and direct invocation."""
    forwarded = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(forwarded)
    root = repo_root_from_script(Path(__file__))
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    source = ensure_project_interpreter(
        root,
        forwarded,
        script_path=Path(__file__),
    )
    return run_server(args, repo_root=root, interpreter_source=source)


if __name__ == "__main__":
    raise SystemExit(main())
