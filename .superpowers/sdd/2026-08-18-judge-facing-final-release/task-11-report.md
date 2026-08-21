# Task 11 Report: One Safe Signal Action Path

## Status

DONE_WITH_CONCERNS. Task 11 is implemented and verified on branch
`codex/judge-final-release` from base `3941a55`. Runner, classic MaxPressure,
capacity-aware MaxPressure, the legacy CA-MP compatibility controller, and both
bridge implementations now have one production signal-write boundary.

The parked Task 10 same-observation `CloudPolicy` compatibility issue remains
out of scope and was not changed. Task 12 was not started.

## Implementation

- Added `engine.safety_executor.SafetyExecutor` with:
  - `apply()` as the only production path that writes signal actions;
  - finite, strictly positive minimum-green configuration validation;
  - action/domain validation before bridge access;
  - minimum-green, yellow, and all-red timing enforcement in simulation seconds;
  - legal transition insertion using `JointState.legal_phase_transitions` and
    complete phase topology;
  - routing through unavoidable intermediate green phases in sequential SUMO
    programs without losing the algorithm's final target;
  - nominal-duration enforcement for directly requested yellow/all-red phases;
  - deterministic `fallback()` and `next_transition()` APIs;
  - one `ActionResult` per original algorithm action, including when the bridge
    receives inserted transition actions instead.
- Added pure timing helpers in `engine/action_validation.py` for phase-change
  boundaries and remaining clearance duration.
- Routed every Runner action batch, including empty batches, through one
  `SafetyExecutor`. Action events now retain exact simulation seconds plus
  structured action, accepted, and reason-code fields.
- Renamed the bridge write methods to private `_apply_actions()` sinks. A
  repository production search finds no public `apply_actions(...)` caller.
  The private TraCI sink retains domain validation as defense in depth.
- Removed minimum-green and transition sequencing ownership from classic,
  capacity-aware, and legacy CA-MP decision code. Controllers select and emit
  final green decisions; the executor owns legal writes and clearance timing.
- Updated M3/M4 provenance to `safety_boundary=safety_executor` and kept audit
  result rows correlated with the exact original controller actions.
- Updated the live algorithm/interface documentation. Historical plans and task
  records were intentionally left unchanged.

## TDD Evidence

The initial implementation portion was resumed from retained `.t11` checkpoints
and the prior tool handoff. The checkpoint evidence predates the final fresh
verification below.

1. Baseline on `3941a55`:
   - Existing controller/action baseline: `62 passed`.
   - Retained basetemps: `baseline-3941a55-green` and
     `controller-baseline-existing`.
2. Validator and executor behavior RED/GREEN cycles covered invalid actions,
   minimum green, transition selection, yellow/all-red insertion, fallback,
   original-action result correlation, and private bridge ownership.
   - Task-focused checkpoint: `25 passed`.
   - Directly affected checkpoint: `158 passed`.
3. Runner/event/boundary cycles were retained as
   `red-runner-boundary` -> `green-runner-boundary*`,
   `red-action-events` -> `green-action-events`, and
   `red-manifest-boundary` -> `green-manifest-boundary`.
   The RED cases showed direct bridge routing, missing structured event timing,
   and stale M3/M4 boundary identity respectively.
4. Algorithm ownership regression after removing controller transition state:
   `99 passed`. The tests require classic and capacity-aware algorithms to emit
   selected final greens and require legacy CA-MP snapshots to delegate all
   transition states to the executor.
5. Clearance-duration RED/GREEN:
   - RED: `3 failed`; standalone yellow/all-red durations could shorten the
     remaining simulation-second clearance.
   - GREEN: `3 passed` after `validate_clearance_duration()` was applied at the
     central boundary.
6. Invalid constructor configuration RED:
   `pytest tests/test_safety_executor.py::test_executor_rejects_an_invalid_minimum_green_configuration -q -p no:cacheprovider --basetemp ...red-invalid-config...`
   - Result: `5 failed`; zero, negative, NaN, positive infinity, and negative
     infinity did not raise.
   - GREEN: same isolated test with a fresh basetemp, `5 passed in 0.05s` after
     finite/positive validation.
7. Runner clearance/audit integration:
   - The first isolated run failed with a test-fixture `IndexError` because
     Runner performs one final safety observation. This was not counted as a
     behavioral RED and required no production change.
   - After adding the final observed state, the test passed. It proves the
     controller requests green `3`, the bridge receives yellow `1`, all-red `2`,
     then green `3`, and all audit/result rows retain original target `3`.
8. Real-SUMO-driven intermediate-green RED:
   `pytest tests/test_safety_executor.py::test_completed_yellow_routes_through_an_unavoidable_intermediate_green -q -p no:cacheprovider --basetemp ...red-intermediate-green...`
   - Result: `1 failed`; results were `[False, True]` because a sequential SUMO
     program rejected a yellow-to-nonadjacent-green jump.
   - GREEN: `1 passed in 0.04s`. The executor now follows the state's legal edge
     through the unavoidable intermediate green and retains the final request.
9. Direct-clearance duration RED:
   `pytest tests/test_safety_executor.py::test_direct_yellow_request_uses_the_nominal_clearance_duration -q -p no:cacheprovider --basetemp ...red-direct-clearance...`
   - Result: `1 failed`; the private sink received `0.1` seconds instead of the
     yellow phase's nominal `3.0` seconds.
   - GREEN: `1 passed in 0.04s`. Direct yellow/all-red targets now use the
     topology's nominal safety interval; direct green targets keep their
     controller-requested green duration.

## Final Verification

All final commands below ran on the exact tree prepared for the Task 11 commit.

- Required focused suite:
  `.venv\Scripts\python.exe -m pytest tests/test_safety_executor.py tests/test_action_validation.py tests/test_events.py -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\focused-commit-tree-20260821-1`
  - Result: `35 passed in 0.82s`.
- Directly affected bridge/runner/algorithm suite:
  `.venv\Scripts\python.exe -m pytest tests/test_safety_executor.py tests/test_action_validation.py tests/test_events.py tests/test_mock_bridge.py tests/test_traci_outputs.py tests/test_runner_channel.py tests/test_algorithms.py tests/test_classic_max_pressure.py tests/test_capacity_aware_max_pressure.py -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\affected-commit-tree-20260821-1`
  - Result: `175 passed in 1.96s`.
- Full project suite:
  `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\full-commit-tree-20260821-1`
  - Result: `543 passed in 136.53s (0:02:16)`, no warnings.
- System Python compatibility:
  `python --version; python -m compileall algorithms cloud core engine experiments scenes`
  - Result: Python `3.14.7`, exit 0.
- `git diff --check`: exit 0.
- Production search:
  `rg --pcre2 -n "(?<!_)apply_actions\(" algorithms cloud core engine experiments scenes scripts -g '*.py'`
  - Result: no matches. Only `SafetyExecutor` calls private `_apply_actions()`.

## Real SUMO Smoke Evidence

These are 100-step scene 1 smokes with seed 42, not formal experiment results.

- Classic MaxPressure:
  `.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm classic_maxpressure --steps 100 --seed 42 --output-dir .t11\real-smoke-classic-final-20260821`
  - Run ID `4706f6b5aaaa`, `completed`, requested steps `100`, final simulation
    time `100.0`, SUMO server version field `22`.
  - `action_applied=14`, `action_rejected=70`.
  - Rejections were only `minimum_green_violation=56` and
    `yellow_clearance_violation=14`; `illegal_phase_transition=0`.
- Capacity-aware MaxPressure:
  `.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm capacity_aware_maxpressure --steps 100 --seed 42 --output-dir .t11\real-smoke-capacity-final-20260821`
  - Run ID `9b98fe664dfd`, `completed`, requested steps `100`, final simulation
    time `100.0`, SUMO server version field `22`, `algorithm_audit=100`.
  - `action_applied=28`, `action_rejected=144`.
  - Rejections were only `minimum_green_violation=58`,
    `yellow_clearance_violation=14`, and paired
    `phase_change_rejected=72`; `illegal_phase_transition=0`.

## Protected Inputs and Scope

- `Get-FileHash -Algorithm SHA256 -LiteralPath '赛题资料.7z'` remains
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`.
- `data/intersection_data` remains `163` tracked files and `232` disk files.
- Worktree and staged protected-path diffs are both zero.
- Pre-existing `progress.md`, `.t9c`, `.t10`, generated `.t11` evidence,
  caches, the archive, and official data are excluded from the commit.

## Files

- Added: `engine/safety_executor.py`, `tests/test_action_validation.py`,
  `tests/test_safety_executor.py`, and this report.
- Modified production: `engine/action_validation.py`, `engine/mock_bridge.py`,
  `engine/runner.py`, `engine/traci_bridge.py`, `algorithms/ca_max_pressure.py`,
  `algorithms/classic_max_pressure.py`, and
  `algorithms/capacity_aware_max_pressure.py`.
- Modified tests: `tests/test_algorithms.py`,
  `tests/test_capacity_aware_max_pressure.py`,
  `tests/test_classic_max_pressure.py`, `tests/test_events.py`,
  `tests/test_mock_bridge.py`, `tests/test_runner_channel.py`, and
  `tests/test_traci_outputs.py`.
- Modified live docs: `algorithms/README.md`, `docs/interface.md`, and
  `docs/architecture/interface.md`.

## Self Review and Concerns

- Verified phase topology and `legal_phase_transitions` drive executor writes;
  controllers do not duplicate pending-target or clearance state.
- Verified inserted yellow, all-red, and intermediate-green actions are private
  execution details while events and capacity audits retain original controller
  actions and exact simulation seconds.
- Verified direct clearance requests cannot shorten nominal yellow/all-red
  intervals, invalid minimum-green settings fail fast, and current-phase fallback
  is deterministic.
- The real smokes intentionally contain repeated structured timing rejections
  while a controller keeps requesting its preferred green. The safety collector's
  legacy `illegal_transition` event type is coarser than the action-result reason
  codes; consumers must use `reason_code` to distinguish minimum-green and
  clearance timing from an illegal graph edge.
- Parked concern from Task 10: separate same-observation sequential
  `CloudPolicy.predict()` / `dispatch_params()` calls may raise
  `cloud_history_unavailable`. Production uses the combined plan path and the
  final `543`-test suite is green, but this public compatibility concern remains
  for the final whole-branch fix wave.
- Review was self-review only as required; no subagent or independent reviewer
  was dispatched.
