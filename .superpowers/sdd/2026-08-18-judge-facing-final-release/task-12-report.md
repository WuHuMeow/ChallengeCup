# Task 12 Implementation Report

Date: 2026-08-21

Branch: `codex/judge-final-release`

Baseline: `71bd4b05acc866d79e96bcecb2cb703fedbaa8ec`

Commit message: `fix: make run lifecycle and scene switching safe`

## Current Code Evidence Head

The current code evidence head for this report is
`e9b2715dedb60438f80b741fef69fb2fffaed4ee`. The current Task 12 additive fixes
are preserved as follows:

- `3b7847db6d251efe239376767d7123fa79151c5c` — `fix: close lifecycle review findings`
- `574f199fc6dd5725a0f02e07b9dc0ed2e6aa67fc` — `fix: harden lifecycle startup cleanup`
- `e9b2715dedb60438f80b741fef69fb2fffaed4ee` — `fix: close lifecycle ownership regressions`

Earlier Task 12 commits remain in history and are not rewritten. All earlier
59, 592, 90, 602, 106, and 610 pass counts, old PIDs 17416, 25052, 19276,
and 10928, and the previous `574f199` latest-evidence addendum are historical
and superseded by the e9b2715 evidence below.

## Outcome

Implemented the lifecycle-safe `RunService` and `SimulationRunner` contract.
Runs now follow a monotonic `queued -> starting -> running -> stopping ->
terminal` graph, preserve terminal results, use `interrupted` for new user-stop
evidence, wait for each run's owned work during stop and scene switch, derive
runner termination from `SimulationWindow` seconds, and atomically persist
`manifest.json` and `status.json` alongside compatible `run_metadata.json`.

`TraCIBridge` records the exact `Popen` object and PID created by TraCI. Cleanup
closes TraCI, waits for that process, and applies terminate/kill fallback only to
that exact handle. No process-name scan or process-name kill exists in production
code. Task 11's `SafetyExecutor.apply()` path and action/event evidence remain
unchanged.

## TDD Evidence

### RED

Command:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py tests/test_run_service.py tests/test_runner_channel.py tests/test_artifacts.py -q
```

Expected failure observed before production implementation:

```text
ERROR tests/test_run_lifecycle.py
ModuleNotFoundError: No module named 'engine.run_state'
1 error in 0.84s
```

The repository's configured `output/tmp` pytest base directory is ACL-blocked.
Subsequent runs therefore used explicit `.task12-pytest-*` base-temp paths. One
attempt using the configured directory produced fixture setup `PermissionError`
only and was not treated as a behavioral result.

### GREEN and race expansion

Initial required focused GREEN:

```text
55 passed in 22.28s
```

Affected suite including lifecycle, service, runner, artifacts, models,
timebase, resilience, seed, and events:

```text
92 passed in 23.14s
```

Race-focused tests then deterministically covered:

- stop between a queued observation and the worker's starting transition;
- two concurrent stop callers;
- scene switch while another caller already owns stopping;
- canceling a queued run without signaling or starting the active run.

The first final full run exposed the stale queued-observation race as
`stopping -> starting`, producing `failed`. After re-reading the lifecycle on a
rejected starting transition, the race suite returned:

```text
14 passed in 12.88s
```

The historical final focused command returned 59 passes; this result is
superseded by the latest code-head verification below:

```text
59 passed in 18.45s
```

## Final Verification (Historical — Superseded)

The following full-suite result is historical and superseded by the latest
code-head verification below.

Historical full suite command:

```text
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.task12-pytest-commit-full
```

Historical result:

```text
592 passed, 1 warning in 94.77s
```

The warning is pytest's cache provider being unable to write the pre-existing
ACL-blocked `.pytest_cache`; the explicit test base directory worked and all
tests passed.

Additional gates:

```text
python -m compileall -q algorithms api cloud core engine experiments ml scenes scripts tests visualization
COMPILEALL_OK

git diff --check
exit 0

python -m flake8 <Task 12 production and test files> --ignore=E501,W503
exit 0
```

A production-path search for `taskkill`, `pkill`, `killall`, process-name SUMO
enumeration, and name-based SUMO kill logic returned no matches.

## Real SUMO and PID Evidence

Executed a real fixed-time scene 1 run through `RunService` with the explicit
legacy smoke request `steps=100`. The service adapted it to a
`SimulationWindow`, while the runner and evidence remained seconds-based.

Historical run (superseded by the 2026-08-22 latest evidence below):

```text
run_id: 5b1b4d404815
run_dir: output/evidence/task-12-lifecycle-smoke-20260821/i1/fixed_time/x1/s42/5b1b4d404815
result status: completed
status.json: completed
run_metadata.json: completed
requested_seconds: 100.0
derived_steps: 100
step_length: 1.0
final_simulation_time: 100.0
owned SUMO PID: 17416
exact PID alive after runner cleanup: false
SUMO PIDs before: []
SUMO PIDs after: []
```

The historical verification queried PID `17416` exactly after cleanup and
separately compared read-only pre/post SUMO inventories. It did not terminate
or kill by name. PID `17416` is historical and superseded by the current
run's PID `20164`.

## Protected Inputs

```text
赛题资料.7z SHA-256:
12a6f2fd69acbcbbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f

data/intersection_data tracked files: 163
data/intersection_data files on disk: 232
```

`git diff --name-only -- data/intersection_data .t9c .t10 .t11` returned no
paths. `赛题资料.7z`, `.t9c`, `.t10`, `.t11`, and official scene data were not
modified. Task 10's parked CloudPolicy compatibility finding was not touched.

## Files Changed

Production:

- `core/run_models.py`
- `engine/artifacts.py`
- `engine/run_state.py`
- `engine/run_service.py`
- `engine/runner.py`
- `engine/traci_bridge.py`

Tests:

- `tests/test_artifacts.py`
- `tests/test_run_lifecycle.py`
- `tests/test_run_models.py`
- `tests/test_run_service.py`
- `tests/test_runner_channel.py`

Report:

- `.superpowers/sdd/2026-08-18-judge-facing-final-release/task-12-report.md`

The pre-existing modification to `progress.md` and pre-existing untracked
archive/scratch paths are intentionally excluded from the Task 12 commit.

## Self-Review

- State transitions are serialized inside `RunStateMachine`; skipped,
  backward, unknown, and terminal-overwriting transitions raise.
- `RunArtifacts.write_status()` independently validates on-disk transitions,
  and `write_metadata()` checks terminal `status.json` before replacement so
  the compatibility and canonical status files cannot diverge after terminal.
- Atomic JSON writes use a unique same-directory temporary file followed by
  `Path.replace()`; no temporary files remained in artifact tests.
- `stop()` returns `True` only to the caller that initiates stopping, but an
  idempotent concurrent caller still waits for the owned run to finish before
  returning `False`.
- `switch_scene()` cannot submit the replacement until the old run's done event
  is set. Queued cancellation finalizes without constructing or starting SUMO.
- The runner distinguishes `completed`, `interrupted`, `disconnected`,
  `ended_early`, and `failed`; the legacy `stopped` value is read-mapped to
  `interrupted` and is not a permitted new state-machine transition.
- Formal service calls pass `SimulationWindow`; integer and `steps=` forms are
  retained only as the narrow smoke compatibility adapter.
- Exact-process cleanup retains the PID after reaping for manifest/metadata
  evidence and never enumerates or kills SUMO by name.

## Concerns

- The worktree's existing `.pytest_cache` and configured `output/tmp` are
  ACL-blocked. Verification used explicit Task 12 base-temp directories and all
  tests passed.
- Recursive cleanup of generated `.task12-pytest-*` directories was blocked by
  the command safety policy. They remain untracked and are not staged. A
  separately present `.task12-pytest-final-full-ours` and
  `.task12-real-sumo-100` directories were not created or modified by this
  implementation.
- Task 10's parked same-observation `CloudPolicy.predict()` /
  `dispatch_params()` compatibility finding remains intentionally out of scope.

## Re-entry Verification Addendum (Historical — Superseded)

The single-writer recovery session reran the required race and verification
matrix on the then-current tree. Its focused result, `59 passed in 18.09s`, is
historical and superseded by the latest code-head verification below.
The three deterministic recovery tests returned `3 passed in 3.34s`; the first
RED run had reproduced `stopping -> starting` becoming `failed`. The recovery
handoff's concurrent-stop and already-stopping switch fixes were already
present when reread and were preserved rather than overwritten.

The historical no-cache, repo-local full command returned `592 passed in
121.79s (0:02:01)`. Its same-volume real SUMO run produced run ID
`7c69507a6cba`, completed 100 steps at final simulation time `100.0`, and
recorded exact PID `25052` in both `manifest.json` and `run_metadata.json`.
Immediately afterward PID `25052` was absent and the remaining SUMO process
count was `0`; this historical PID evidence is superseded by the current
run's PID `20164` below.

Fresh static gates were `COMPILEALL PASS` for
`algorithms api cloud core engine experiments ml scenes scripts tests` and
`DIFF CHECK PASS`. The protected archive hash was
`12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`;
official data remained `163` tracked / `232` on disk, with no protected-path
diff. The installed SUMO binary is `1.27.1`; the existing metadata extractor
still records server version `22`, which remains outside this Task 12 scope.

## Fix-Round Addendum (2026-08-21; Historical — Superseded)

This follow-up closes the lifecycle compatibility review gaps without changing
the existing controller changes in `progress.md` or this report's earlier
evidence.

### RED evidence

Lifecycle race tests were added first and failed as expected:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-fix-red-lifecycle
2 failed, 14 passed in 12.26s
```

The failures reproduced an early terminal `stop()` return and a terminal
`status.json` overwrite exception. Legacy return tests then failed before the
predicate change:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-fix-red-legacy -k "integer_runner_calls_return_legacy_list_with_artifacts or formal_simulation_window_returns_run_result_with_artifacts"
2 failed, 1 passed, 16 deselected in 2.59s
```

The API contract comparison failed against the stale checked-in enum:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_api_contract.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-fix-red-api
1 failed, 15 passed in 13.16s
```

### GREEN evidence

The combined lifecycle and API tests passed after the minimal fixes:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py tests/test_api.py tests/test_api_contract.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-fix-green-core2
35 passed in 25.22s
```

The required focused verification passed:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py tests/test_runner_channel.py tests/test_run_service.py tests/test_artifacts.py tests/test_run_models.py tests/test_api.py tests/test_api_contract.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-fix-focused
87 passed in 34.98s
```

`git diff --check` passed. The fix-round changes are limited to
`engine/run_service.py`, `engine/runner.py`, `tests/test_run_lifecycle.py`,
`tests/test_api.py`, `tests/test_api_contract.py`, `docs/api/openapi.json`,
`docs/interface.md`, and this report.

Remaining concerns are unchanged from the prior report: the configured
pytest/output directories are ACL-blocked, generated `.task12-*` paths remain
untracked and unstaged, and Task 10's parked CloudPolicy compatibility finding
is out of scope.

## Validated Scene Timebase Supplemental Fix (2026-08-21; Historical — Superseded)

This additive fix requires `RunService` to resolve an exact passing manifest
through `SceneRegistry.list_scenes(formal_only=True)` before constructing the
runtime scene. The validated manifest supplies the base step length; an
explicit request override remains authoritative. Missing and failed manifests
now fail before runner construction. The two lifecycle wait tests use observed
`_wait_until_done` entry/return events instead of scheduling delays.

### RED evidence

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-validated-scene-red -k "uses_validated_manifest_timebase or rejects_scene_without_passing_validated_manifest"
3 failed, 11 deselected in 3.27s
```

The timebase case wrote raw XML `step_length == 1.0` instead of the passing
manifest's `0.25`. The missing- and failed-manifest cases both completed and
constructed a runner instead of failing at the validated-scene boundary.

### GREEN evidence

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-validated-scene-green -k "uses_validated_manifest_timebase or rejects_scene_without_passing_validated_manifest"
3 passed, 11 deselected in 2.57s

.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_run_lifecycle.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-validated-scene-core-green
33 passed in 23.14s

.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_run_lifecycle.py tests/test_runner_channel.py tests/test_artifacts.py tests/test_run_models.py tests/test_api.py tests/test_api_contract.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-validated-scene-focused
90 passed in 37.99s
```

The supplemental commit hash is reported in the post-commit handoff because a
commit cannot contain its own final hash without changing that hash.

## Validated Scene Review Fix Round 2 (2026-08-21; Historical — Superseded)

This additive round closes the five scoped review findings while preserving the
controller's `progress.md` change and all protected inputs. The validated
manifest step length is now carried into `SimulationRunner`, used for tick
derivation and final metadata, and applied to the generated SUMO config. Formal
requests retain declared warmup when compatibility steps are synthesized, while
explicit `steps=` requests retain legacy semantics. Runtime scene paths and
hashes are checked against the passing manifest before runner construction.
Malformed status artifacts recover to an explicit terminal failure. TraCI now
owns its child `Popen` from creation through `traci.init(proc=...)`, including
startup failure cleanup, with no process-name enumeration or termination.

### RED evidence

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_run_lifecycle.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-fix-round2-red -k "runner_keeps_validated_step_length_authoritative_over_bridge or formal_override_retains_declared_warmup or manifest_runtime_scene_identity_mismatch_fails_closed or corrupt_status_artifact_still_reaches_terminal_failed_result or bridge_start_failure_reaps_process_created_during_traci_start"
5 failed, 33 deselected in 6.23s
```

Failures were the expected raw-bridge timebase (`1` tick instead of `4`),
dropped warmup (`0.0` instead of `600`), accepted identity mismatch, escaped
`JSONDecodeError`, and missing startup process-capture seam. A second focused
RED check after making the compatibility flag idempotent isolated the remaining
authoritative runner failure:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-fix-round2-red-authoritative -k "runner_keeps_validated_step_length_authoritative_over_bridge or formal_override_retains_declared_warmup"
1 failed, 1 passed, 16 deselected in 2.59s
```

### GREEN evidence

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_run_lifecycle.py tests/test_resilience.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-fix-round2-green-core-full2
46 passed in 27.45s

.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_run_lifecycle.py tests/test_runner_channel.py tests/test_artifacts.py tests/test_run_models.py tests/test_api.py tests/test_api_contract.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-validated-scene-focused-round2-final
95 passed in 39.67s

.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .superpowers\tmp\task12-round2-full-final
607 passed in 193.96s
```

Static gates after the final code and report edits:

```text
.\.venv\Scripts\python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts tests visualization
COMPILEALL_OK

git diff --check
DIFF_CHECK_OK
```

The historical external `D:\Temp` full-suite attempt produced four unrelated fixed-time
plan path failures because those tests require a repo-local `tmp_path`; the
repo-local rerun above is the authoritative full result. The configured
`output/tmp` and existing scratch directories remain ACL-blocked/untracked and
were not staged. The statement that a fresh real SUMO run was left for a
controller handoff is historical and superseded by the latest run below.

## Startup Ownership and Request Reconstruction Fix Round 3 (2026-08-21; Historical — Superseded)

The controller re-review found two additional lifecycle boundary defects in the
fix-round tree. A request reconstructed with `dataclasses.replace()` could
reinterpret compatibility-generated `steps` as explicit and drop its declared
warmup. Startup cleanup caught only `Exception`, so an interrupt after the child
was recorded could leak it; an already-active global TraCI connection was also
not rejected before launch.

### RED evidence

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r3-red -k replacing_compatibility_request_preserves_declared_warmup
1 failed, 7 deselected in 0.60s

.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r3-red-interrupt -k bridge_start_interrupt_reaps_recorded_process
1 failed, 21 deselected in 0.81s

.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r3-red-existing -k bridge_start_rejects_existing_connection_before_launch
1 failed, 21 deselected in 0.76s
```

### GREEN evidence

The three regressions pass after the minimal fixes:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r3-green -k replacing_compatibility_request_preserves_declared_warmup
1 passed, 7 deselected in 0.60s

.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r3-green-start -k "bridge_start_interrupt_reaps_recorded_process or bridge_start_rejects_existing_connection_before_launch"
2 passed, 20 deselected in 0.59s

.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_run_lifecycle.py tests/test_runner_channel.py tests/test_artifacts.py tests/test_run_models.py tests/test_api.py tests/test_api_contract.py tests/test_resilience.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r3-focused
106 passed in 39.76s

.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .superpowers\tmp\task12-round3-full
610 passed in 143.96s
```

The changed request marker is an internal, hidden init field so
`dataclasses.replace()` carries the original explicitness decision. TraCI
startup now rejects an active connection before `Popen` and catches
`BaseException` while preserving the original error after best-effort exact
child cleanup. No process-name enumeration or unrelated-process cleanup was
introduced. The earlier statement that a fresh real SUMO run remained a
controller handoff gate is historical and superseded by the latest run below.

## Latest Code-HEAD Verification (2026-08-22, 574f199; Historical — Superseded)

All verification in this historical addendum targeted the then-current code
evidence head `574f199fc6dd5725a0f02e07b9dc0ed2e6aa67fc`; it is superseded by
the e9b2715 verification below.

### Fresh automated verification

Full suite:

```text
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .superpowers\tmp\task12-resume-20260822-full
610 passed in 111.99s (0:01:51)
```

Focused lifecycle/API/artifact/resilience suite:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_run_lifecycle.py tests/test_runner_channel.py tests/test_artifacts.py tests/test_run_models.py tests/test_api.py tests/test_api_contract.py tests/test_resilience.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-resume-20260822-focused
106 passed in 42.53s
```

Complete compile gate and protected code-range diff check:

```text
.\.venv\Scripts\python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts tests visualization
COMPILEALL_OK

git diff --check 71bd4b0..HEAD
DIFF_CHECK_OK
```

### Fresh real SUMO and exact-PID evidence

```text
run_id: a0ae899b0598
run_dir: D:\Temp\judge-task12-resume-20260822-real\i1\fixed_time\x1\s42\a0ae899b0598
status: completed
derived_steps: 100
requested_seconds: 100.0
final_simulation_time: 100.0
manifest PID: 10928
run_metadata PID: 10928
PID alive after cleanup: false
remaining SUMO processes: 0
```

The manifest and metadata identify the same exact child PID; cleanup left no
remaining SUMO process. This latest PID evidence supersedes historical PIDs
`17416` and `25052`.

### Protected inputs and worktree scope

```text
赛题资料.7z SHA-256:
12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F

data/intersection_data tracked files: 163
data/intersection_data files on disk: 232
base-to-code-head protected diff: empty
index protected diff: empty
```

The archive is untracked/unstaged and is outside the `71bd4b0..574f199`
commits. The protected `data/intersection_data` files and the `.t9c`, `.t10`,
and `.t11` paths were not modified. Before this report write, the only tracked
worktree modification was the controller's `progress.md`; pre-existing
untracked protection/evidence directories were outside this report and were
not staged.

The fresh tests and gates above are evidence for code head `574f199...`; this
report-only evidence commit is not itself claimed to have undergone code tests.
Its commit SHA is supplied in the handoff after commit creation.

## Round 4 Review Findings (2026-08-22; e9b2715)

The Round 4 review findings were closed by the additive e9b2715 code head. The
review buckets and their RED/GREEN evidence are recorded without rewriting the
earlier rounds:

- A — `RunRequest` replacement and compatibility-step semantics. RED reproduced
  `2 failed`; GREEN A returned `4 passed`.
- B — malformed status-artifact validation, recovery, and terminal metadata
  ownership. RED reproduced `9 failed, 10 passed`; GREEN B returned `19 passed`.
- C — TraCI connection ownership and partial-start cleanup. RED reproduced
  `1 failed`; GREEN C returned `5 passed`.

The writer's expanded focused verification returned `111 passed in 28.05s`.
The main agent's independent targeted verification returned `27 passed in
3.02s`. Terra's post-fix code audit returned `PASS` with no new Critical or
Important findings. The pre-existing deferred `frame_sink` issue remains a
Minor finding and is not claimed as fixed by this round.

## Latest Code-HEAD Verification (2026-08-22, e9b2715)

All current verification in this addendum targets code evidence head
`e9b2715dedb60438f80b741fef69fb2fffaed4ee`. The report-only commit created
after this addendum is documentation evidence and is not represented as a
code-test target.

### Focused and full-suite verification

The exact eight-file focused command was:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_run_lifecycle.py tests/test_runner_channel.py tests/test_artifacts.py tests/test_run_models.py tests/test_api.py tests/test_api_contract.py tests/test_resilience.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r4-controller-focused
127 passed in 42.75s
```

The first full-suite attempt used external basetemp
`D:\Temp\judge-task12-r4-controller-full` and returned `627 passed` with four
fixed-time source-boundary environment failures. Those
four failures were environmental consequences of the external basetemp, not
the canonical contract result. The required repo-local canonical rerun was
green:

```text
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .superpowers\tmp\task12-r4-controller-full-inrepo
631 passed in 123.84s
```

The external attempt is recorded transparently and is not presented as a
canonical failure; the in-repo rerun above is the authoritative full result.

### Static gates and protected inputs

```text
.\.venv\Scripts\python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts tests visualization
exit 0

git diff --check 71bd4b0..e9b2715
PASS

赛题资料.7z on-disk SHA-256:
12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F

data/intersection_data tracked files: 163
data/intersection_data files on disk: 232
base-to-code-head protected diff: empty
protected index diff: empty
```

The archive hash is an on-disk integrity observation; the archive remains
untracked and unstaged and is outside the `71bd4b0..e9b2715` commits. That
hash is distinct from the empty Git protected-path diff evidence. The official
`data/intersection_data` files and `.t9c`, `.t10`, and `.t11` paths were not
modified or staged.

### Fresh real SUMO and exact-PID evidence

```text
run_id: b7f105be2545
run_dir: D:\Temp\judge-task12-r4-controller-real\i1\fixed_time\x1\s42\b7f105be2545
status: completed
derived_steps: 100
requested_seconds: 100.0
final_simulation_time: 100.0
manifest PID: 20164
run_metadata PID: 20164
PID_ALIVE: False
SUMO before: 0
SUMO after: 0
```

The manifest and metadata identify the same exact child PID, and the
before/after SUMO inventories both contain zero processes. This fresh run is
the current real-SUMO evidence and supersedes historical PIDs `17416`,
`25052`, `19276`, and `10928`.

### Worktree scope

The controller's `progress.md` remains an unstaged ledger modification.
Pre-existing scratch and protected evidence paths remain untracked. At the
code commit boundary the protected index was empty; only this explicitly
allowed report is staged for the evidence-only follow-up commit. No code,
tests, `.t*` paths, `赛题资料.7z`, or `data/intersection_data/**` are part of
that staging allowlist.

The current code-head evidence above is the source of truth for this report.
The report commit SHA is supplied after creating the requested
`docs: bind task 12 evidence to latest code head` commit.

## Round 5 Request and Connection Identity Closure (2026-08-22; fc1a4d7)

This additive section supersedes the e9b2715 section as the latest code-head
evidence. All code verification below targets
`fc1a4d7a66c749252daff6440e51bc3fcac8b5a0` (`fix: preserve request and
connection identity`). It does not rewrite or invalidate the historical
commands above.

Round 5 made request-step provenance a versioned, persisted contract and made
TraCI cleanup target the exact labeled connection handle. `RunRequest` now
persists `steps_origin`, distinguishes formal compatibility-derived steps from
equal-valued explicit steps in equality and JSON, normalizes compatibility
steps after `dataclasses.replace()`, and validates version/origin/value
consistency fail-closed. The run manifest and PDF-matrix semantic key preserve
the same identity boundary. TraCI startup now uses an internal lifecycle gate,
a unique label, the exact registered connection handle, and the already
recorded exact child process; production cleanup no longer calls module-global
`traci.close()`.

### Round 5 TDD RED evidence

The writer recorded the following commands before their corresponding
production changes. Each failure was caused by the missing behavior named in
the heading rather than a collection or syntax error.

1. Initial provenance and codec contract:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-red-i1
10 failed, 10 passed in 0.79s
```

2. Manifest provenance:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_service.py::test_run_manifest_records_request_steps_origin -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-red-i1-manifest
2 failed in 2.49s
```

3. Unique TraCI label and exact partial-init handle:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py::test_bridge_start_failure_reaps_process_created_during_connection_setup tests/test_run_lifecycle.py::test_bridge_start_interrupt_reaps_recorded_process tests/test_run_lifecycle.py::test_bridge_init_race_does_not_close_another_owners_connection -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-red-i2
3 failed in 0.75s
```

4. Exact close and restart ownership:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_resilience.py::test_step_restarts_when_allowed tests/test_resilience.py::test_close_idempotent -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-red-i2-close-restart
2 failed in 0.82s
```

5. Provenance consistency, schema, and semantic request key:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py::test_request_payload_rejects_inconsistent_steps_origin tests/test_run_models.py::test_request_payload_schema_version_is_explicit_and_validated tests/test_tuning.py::test_request_key_includes_step_origin_and_seconds_window_inputs -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-red-i1-schema-key
3 failed, 5 passed in 0.70s
```

6. Exact handle close interrupted by `BaseException`:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py::test_bridge_close_reaps_child_when_connection_close_is_interrupted -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-red-i2-baseexception
1 failed in 0.72s
```

7. Strict schema-version type:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py::test_request_payload_schema_version_is_explicit_and_validated -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-red-i1-version-type
1 failed, 2 passed in 0.67s
```

8. Compatibility-step normalization after replacement:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py::test_replacing_compatibility_duration_rederives_replayable_steps tests/test_run_models.py::test_removing_compatibility_override_removes_derived_steps_for_replay -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-red-i1-replace-codec
2 failed in 0.66s
```

9. Versioned payload missing required provenance:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py::test_versioned_request_payload_requires_steps_origin -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-red-i1-v1-origin
1 failed in 0.63s
```

### Round 5 GREEN and writer verification

The final request-model group, including versioned missing-origin rejection,
returned:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-green-i1-v1-origin
29 passed in 0.61s
```

The final exact-handle group, including partial RuntimeError, partial
KeyboardInterrupt, other-owner TOCTOU, interrupted handle close, restart, and
idempotent close, returned:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_lifecycle.py::test_bridge_close_reaps_child_when_connection_close_is_interrupted tests/test_run_lifecycle.py::test_bridge_start_failure_reaps_process_created_during_connection_setup tests/test_run_lifecycle.py::test_bridge_start_interrupt_reaps_recorded_process tests/test_run_lifecycle.py::test_bridge_init_race_does_not_close_another_owners_connection tests/test_resilience.py::test_step_restarts_when_allowed tests/test_resilience.py::test_close_idempotent -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-green-i2-final
6 passed in 0.60s
```

The writer's final submitted-tree expanded focused command was:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py tests/test_run_service.py tests/test_run_lifecycle.py tests/test_resilience.py tests/test_artifacts.py tests/test_runner_channel.py tests/test_tuning.py -q -p no:cacheprovider --basetemp D:\Temp\judge-task12-r5-writer-focused
151 passed in 30.19s
```

The writer also recorded GREEN results of `22 passed in 3.01s` for the initial
I1-plus-manifest group, `8 passed in 0.60s` for the schema/key group, and
`28 passed in 0.57s` after compatibility-replacement normalization. These are
intermediate evidence; the final 29/6/151 results above are authoritative for
the submitted code.

### Latest code-head controller verification

The controller independently reran the expanded focused set on code head
`fc1a4d7` with a new repo-local basetemp:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_run_models.py tests/test_run_service.py tests/test_run_lifecycle.py tests/test_resilience.py tests/test_artifacts.py tests/test_runner_channel.py tests/test_tuning.py -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.superpowers\tmp\task12-r5-main-focused-20260822-0918
151 passed in 31.36s
```

The new canonical repo-local full-suite run returned:

```text
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.superpowers\tmp\task12-r5-main-full-20260822-0919
655 passed in 112.08s (0:01:52)
```

Static and compatibility gates were:

```text
.\.venv\Scripts\python.exe --version
Python 3.12.13

.\.venv\Scripts\python.exe -m compileall -q algorithms api core engine experiments scripts tests
exit 0

py -3.14 --version
Python 3.14.7

py -3.14 -m compileall -q algorithms api cloud core engine experiments ml scenes scripts tests visualization
exit 0

git diff --check 71bd4b0..fc1a4d7
PASS

git diff --check c5e2223..fc1a4d7
PASS
```

### Latest real SUMO and exact-PID evidence

```text
run_id: ca1cabbf7800
run_dir: D:\Temp\judge-task12-r5-controller-real-20260822-0924\i1\fixed_time\x1\s42\ca1cabbf7800
result/status/metadata: completed
derived_steps: 100
requested_seconds: 100.0
steps_origin: explicit
final_simulation_time: 100.0
manifest PID: 16632
run_metadata PID: 16632
PID_ALIVE: False
SUMO before: 0
SUMO after: 0
```

The two PID fields identify the same exact child. That process was absent after
shutdown, and the before/after SUMO inventories were both empty. This run
supersedes `b7f105be2545` / PID `20164` as the latest code-head real-SUMO
evidence.

### Latest protected-input and scope gates

```text
赛题资料.7z on-disk SHA-256:
12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F

data/intersection_data tracked files: 163
data/intersection_data files on disk: 232
71bd4b0..fc1a4d7 protected diff: empty
worktree protected diff: empty
index protected diff: empty
```

Commit `fc1a4d7` contains only the nine authorized production/test files. The
controller's `progress.md` remains unstaged, the index is empty, and existing
untracked `.task12-*`, `.t9c`, `.t10`, `.t11`, and archive paths remain outside
the commit.

### Pre-review breaker candidates

Three read-only pre-review observations remain for the formal Round 5 scoped
review to adjudicate. They are recorded rather than silently discarded:

1. If startup has already failed and exact-handle cleanup itself raises a
   `KeyboardInterrupt`, cleanup completes but the cleanup `BaseException`
   becomes the final visible exception instead of the earlier startup error.
2. Direct concurrent or repeated `start()` calls on the same bridge can clear
   discovery state before the lifecycle lock rejects the second call. The
   production runner does not issue concurrent starts on one bridge, and true
   multi-bridge domain concurrency is outside the Round 5 contract.
3. A nonstandard path where an exact connection handle raises another
   `FatalTraCIError` from `close()` can prevent the existing restart branch from
   reaching `start()`. In SUMO 1.27.1's ordinary "Connection closed by SUMO"
   path, `_sendExact()` first closes the socket and sets it to `None`, so the
   following exact `Connection.close()` skips `CMD_CLOSE` and deregisters the
   label normally. The narrower close-failure case remains for formal severity
   and scope review.

These observations are not represented as closed or dismissed here. Round 5 is
the fifth fix round, so any formal Critical/Important result must be handled by
the recorded breaker/adjudication process rather than an unreviewed sixth Task
12 fix. The pre-existing `frame_sink` issue and non-canonical matrix key fields
remain deferred Minors. Task 12 is not marked complete in this report.
