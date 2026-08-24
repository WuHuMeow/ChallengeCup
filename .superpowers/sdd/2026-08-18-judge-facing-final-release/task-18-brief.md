### Global Task 18: Implement native one-click startup and diagnostics

This brief is the task-specific specification for Global Task 18. Numbered items such as
18.1 and 18.2 are implementation subtasks inside Global Task 18; they are not new global
tasks in the 24-task judge-final-release plan.

## PDF and project basis

- The competition PDF, page 7, requires a runnable simulation system, complete source,
  detailed deployment instructions, and reproduction of a complete control flow for a
  representative scene.
- Page 10 awards the strongest system-integration score only when the algorithm and
  simulation platform are integrated, stable, and reproducible without crashes or stalls.
- Page 16 requires the demonstration to cover environment adaptation, algorithm deployment,
  execution, and visible results as one understandable flow.
- The current project already provides the FastAPI application, `RunService`, the React
  production build in `api/static/dist`, exact per-run SUMO ownership through
  `TraCIBridge.process_id`, and lifespan cleanup through `RunService.shutdown(wait=True)`.

## Files in scope

- Create: `scripts/run_judge.py`
- Create: `scripts/start_judge.ps1`
- Create: `scripts/start_judge.bat`
- Create: `tests/test_judge_launcher.py`
- Modify: `docs/deployment.md`
- Modify: `README.md`
- Update after verification: `.superpowers/sdd/2026-08-18-judge-facing-final-release/progress.md`

No other source file is changed unless a failing test proves that an existing public contract
cannot support the launcher. In particular, the launcher composes the existing `RunService`,
`SimulationRunner`, `create_app`, and FastAPI lifespan instead of duplicating lifecycle code.

## Selected design

1. `scripts/run_judge.py` is both the native launcher and the future Task 19 container
   entrypoint. When a repository `.venv` exists and the script was invoked by another
   interpreter, it re-executes itself with the project interpreter. In an environment without
   a repository virtual environment, such as the future container image, the current
   interpreter is accepted only after the same dependency preflight passes.
2. The requested TCP port is the start of a bounded ten-port scan. Diagnostics preserve both
   requested and selected ports and every conflict encountered; an exhausted scan is a clear
   preflight failure.
3. The launcher creates one `RunService`, injects it into `api.server.create_app`, and starts
   programmatic Uvicorn in the main thread so native signal handling remains available.
   FastAPI lifespan remains the single owner of RunService and SUMO child cleanup.
4. A bounded background readiness worker requests `/api/health` and accepts only a JSON body
   whose `status` is exactly `ok`. The browser is opened only after that check passes. A failed
   readiness deadline requests Uvicorn shutdown and records the failure.
5. `--gui-mode auto|native|headless` controls the SUMO executable used for runs. On Windows,
   `auto` chooses `sumo-gui` when available and otherwise chooses `sumo`; on other systems it
   chooses `sumo`. `native` requires Windows and `sumo-gui`; `headless` requires `sumo`.
6. A launcher-owned runner registry wraps `RunService.runner_factory`, passes the selected
   SUMO binary to `SimulationRunner`, and maps the run's own `artifacts.run_id` to that runner.
   The native-GUI API focuses only the window whose process ID equals
   `runner.bridge.process_id`. It never searches by title, executable name, or an unrelated
   SUMO process.
7. `output/evidence/judge-launch/launcher.json` is replaced atomically after every meaningful
   state transition. It records Python, TraCI, SUMO/SUMO-GUI, static assets, output
   writability, GUI selection, requested/selected port, health, browser action, timestamps,
   final status, and reason without storing personal absolute paths.
8. `scripts/start_judge.ps1` resolves the repository-local interpreter and forwards all
   launcher arguments. `scripts/start_judge.bat` delegates to PowerShell and preserves its
   exit code. Both fail nonzero with an actionable message when the project interpreter is
   absent.

## Command contract

```text
scripts/run_judge.py --host 127.0.0.1 --port 8000 \
  --open-browser --gui-mode auto
```

Supported launcher arguments:

- `--host HOST`, default `127.0.0.1`.
- `--port PORT`, default `8000`, valid range `1..65535`.
- `--port-attempts COUNT`, default and maximum `10`.
- `--open-browser` / `--no-browser`, default open.
- `--gui-mode auto|native|headless`, default `auto`.
- `--health-timeout SECONDS`, default `30.0`, finite and positive.
- `--diagnostics PATH`, default `output/evidence/judge-launch/launcher.json`.

## Diagnostics contract

The JSON document uses schema `judge-launcher.v1`. Preflight checks use the existing project
vocabulary `pass`, `fail`, and `not_run`. Top-level launcher status progresses through
`starting`, `ready`, and `stopped`, or terminates as `failed`. A normal operator stop after a
healthy launch is `stopped`, not `failed`.

The document must contain these stable sections:

- `schema`, `status`, `reason`, `started_at`, `ready_at`, `stopped_at`.
- `python`: version, implementation, interpreter source, and repository-relative identity.
- `dependencies`: FastAPI, Uvicorn, TraCI, and sumolib versions/status.
- `sumo`: detected headless and GUI versions/status plus selected mode/binary identity.
- `assets`: `api/static/dist/index.html` status.
- `output`: diagnostics directory and run-output directory writability status.
- `network`: host, requested port, selected port, scan count, and conflicted ports.
- `health`: URL, status, attempt count, and detail.
- `browser`: requested, status, and detail.

## Acceptance gates

- Unit tests prove interpreter selection, bounded port fallback, preflight failures, atomic
  diagnostics, exact health semantics, browser ordering, Uvicorn cleanup, GUI-mode selection,
  PID-scoped focus, PowerShell forwarding, and batch exit-code preservation.
- A real PowerShell smoke starts the launcher without a browser, reaches `/api/health`, runs a
  short representative API simulation, and stops without leaving the launcher or SUMO child
  alive.
- On this Windows workstation, a native-GUI smoke uses the installed SUMO 1.27.1
  `sumo-gui.exe`, starts one short run, and confirms the API can focus that run's exact SUMO
  PID. If the environment changes before execution, the check is recorded as `not_run` or
  `fail` according to whether the requirement is unavailable or broken; it is never simulated.
- The production Web console is opened through the Codex in-app browser only after launcher
  health passes and is checked for the existing four-view Task 17 contract.
- Affected Python tests, the full Python baseline, frontend build/Playwright gates,
  `compileall`, and `git diff --check` pass.
- `赛题资料.7z` remains byte-identical; `data/intersection_data` remains unchanged; scratch
  directories, historical evidence, and `node_modules` are not cleaned or staged.
