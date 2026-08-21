# Task 12 Report: Lifecycle-Safe RunService and SimulationRunner

## Status

IMPLEMENTED. Task 12 was resumed on `codex/judge-final-release` from base
`71bd4b0`. The lifecycle state machine, per-run ownership, seconds-based runner
window, atomic artifacts, exact-PID cleanup, and scene-switch synchronization
are implemented and verified.

## TDD Evidence

The recovered diff's existing Task 12 focused baseline was run first with the
project interpreter and an external same-volume basetemp:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py tests/test_run_service.py tests/test_runner_channel.py tests/test_artifacts.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-baseline-20260821-b
```

Result: `56 passed in 19.35s`.

The three deterministic recovery-race tests were then added at the public
`RunService.submit/get/stop/switch_scene` seam. The first RED run reproduced
the queued-stop race:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py::test_stop_between_queued_observation_and_start_preserves_interrupted tests/test_run_lifecycle.py::test_concurrent_stop_callers_are_serialized_and_idempotent tests/test_run_lifecycle.py::test_switch_scene_waits_when_another_caller_is_already_stopping -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-race-red-20260821-a
```

Result: `F..`; the queued run ended `failed` with `invalid run transition
stopping -> starting` instead of canonical `interrupted`. The recovery handoff
already contained the concurrent-stop and already-stopping switch wait fixes
when they were reread, so those two cases were GREEN on re-entry; the handoff's
prior audit is the retained RED evidence for those defects. The final tests
still force all three interleavings deterministically and assert the public
behavior.

The minimal implementation change closes the same stale-stop window at both
startup transitions. A stop that wins before `starting` or `running` is
committed now finalizes `interrupted`; it cannot fall through to generic
failure. The final race rerun was:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py::test_stop_between_queued_observation_and_start_preserves_interrupted tests/test_run_lifecycle.py::test_concurrent_stop_callers_are_serialized_and_idempotent tests/test_run_lifecycle.py::test_switch_scene_waits_when_another_caller_is_already_stopping -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-race-green-current-20260821-a
```

Result: `3 passed in 3.34s`.

## Verification

Required focused matrix:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py tests/test_run_service.py tests/test_runner_channel.py tests/test_artifacts.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-focused-green-20260821-a
```

Result: `59 passed in 18.09s`.

Full project suite (repo-local basetemp is required by fixed-time provenance
tests):

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .task12-pytest-final-full-ours
```

Result: `592 passed in 121.79s (0:02:01)`.

The same full command with an external basetemp reached `588 passed` but had
four expected fixed-time provenance failures because those tests reject source
files outside the repository. No product failure was inferred from that
environment-only attempt.

## Real SUMO Smoke and Ownership

SUMO `1.27.1` was available. A real scene 1 fixed-time run used
`RunService.run_sync(RunRequest("1", "fixed_time", steps=100,
warmup_seconds=0))` with output root `.task12-real-sumo-100`.

- Run ID: `7c69507a6cba`
- Result: `completed`
- Requested/derived steps: `100` / `100`
- Requested seconds: `100.0`
- Final simulation time: `100.0`
- `manifest.json` exact `sumo_pid`: `25052`
- `run_metadata.json` exact `sumo_pid`: `25052`

Post-run ownership check:

```powershell
Get-Process -Id 25052 -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^sumo(gui)?\.exe$' }
```

Result: exact PID `25052` absent; `0` remaining SUMO processes. Cleanup is
performed by the owning bridge's recorded process object and never by a global
SUMO name scan.

## Static and Protected-Input Checks

- `.venv\Scripts\python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts tests`: `COMPILEALL PASS`.
- `git diff --check`: `DIFF CHECK PASS` (only existing LF/CRLF warnings).
- `赛题资料.7z` SHA-256: `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`.
- `data/intersection_data`: `163` Git-tracked files and `232` files on disk.
- Diff of `赛题资料.7z`, `data/intersection_data`, `.t9c`, `.t10`, and `.t11`: empty.

## Files Changed

Task 12 implementation and tests:

- Added `engine/run_state.py` and `tests/test_run_lifecycle.py`.
- Modified `core/run_models.py`, `engine/artifacts.py`, `engine/run_service.py`,
  `engine/runner.py`, and `engine/traci_bridge.py`.
- Modified `tests/test_artifacts.py`, `tests/test_run_models.py`,
  `tests/test_run_service.py`, and `tests/test_runner_channel.py`.
- Added this report.

The existing controller `progress.md`, protected inputs, `.t9c`, `.t10`,
`.t11`, and generated pytest/SUMO evidence directories are intentionally not
part of the scoped commit.

## Self Review

- `RunStateMachine` owns the monotonic transition graph and rejects terminal
  overwrites. `stopped` is read-compatible only; new user-stop evidence is
  `interrupted`.
- `RunService.stop()` claims a stop through the state-machine lock, treats a
  competing claim as idempotent, and waits on that run's exact future/done
  event. `switch_scene()` waits when another caller already owns `stopping`
  before submitting a replacement.
- Each run allocates a unique directory, stop event, done event, future,
  runner, and artifact set. No cross-run event or process lookup is used.
- `SimulationRunner` accepts `SimulationWindow`, derives steps from the
  validated scene step length, preserves the integer smoke adapter, and writes
  terminal metadata for completed, interrupted, disconnected, ended-early, and
  failed exits.
- `RunArtifacts.write_manifest()` and `write_status()` use atomic replacement;
  terminal status is immutable and `run_metadata.json` remains available for
  legacy consumers.
- `TraCIBridge.close()` closes TraCI and waits/terminates/kills only its
  recorded child process object. The exact PID remains available for evidence
  after cleanup.

## Concerns

- The existing metadata version extraction reports SUMO server version as
  `22` in the smoke artifact even though the installed binary is `1.27.1`;
  this predates Task 12's ownership work and is outside this scoped fix.
- The recovery tree received the concurrent-stop and switch wait corrections
  while this session was auditing the uncommitted diff. They were preserved,
  covered by deterministic tests, and included in the final scoped review.
- No independent reviewer or subagent was dispatched; this was the required
  single-writer self-review.
