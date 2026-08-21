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

## Fix Round 1: Safety Executor Review Gaps

### Status

DONE_WITH_CONCERNS. All three Critical and four Important review findings are
closed on top of reviewed base `ead46720749236afee9cf171ec2a75cf6d02701a`.
Task 12 was not started. The parked Task 10 same-observation `CloudPolicy`
compatibility issue remains unchanged and out of scope.

### Review Finding Closure

- Green `set_phase_duration` requests now preserve the remaining minimum green.
  Paired durations for newly selected greens must satisfy the full live minimum,
  and unpaired or unavoidable intermediate greens require a safe nominal
  duration before they can be entered.
- `set_program` accepts only a validated program definition at clean startup,
  where step, simulation time, and elapsed phase time are all zero. Mid-run and
  string-only program switches are rejected as `unsafe_program_switch`.
- A green-to-green request must have a reachable yellow/all-red path. A direct
  graph edge does not authorize a direct write, and a missing path rejects as
  `clearance_path_unavailable`.
- Timing rejections remain structured `action_rejected` rows. Only an actual
  illegal graph edge can produce the `illegal_transition` hard-gate event.
- `ControlAction` now has backward-compatible optional `issued_at` and
  `expires_at` fields. Production algorithms issue actions at the observation's
  simulation timestamp with the same 60-second horizon as `EdgeMessage`; an
  action is stale when `current >= expires_at`.
- Stale actions reject as `stale_action` and report the deterministic no-write
  fallback (`preserve_current_phase` or `fixed_timing_unchanged`). Delayed but
  unexpired edge actions remain executable.
- A requested direct-clearance duration below the nominal interval rejects as
  `clearance_duration_corrected`; any nominal duration written to the private
  bridge is represented as an internal fallback rather than acceptance of the
  unsafe original duration.
- Runner gives `SafetyExecutor` a live provider for the algorithm's current
  `min_green`, so dynamic cloud/controller changes and non-default configured
  values are read for every action batch.

### TDD Evidence

The resumed implementation retained the following behavior-level RED/GREEN
results from its isolated `.t11` checkpoints:

- Critical 1 green durations: RED `2 failed, 19 passed`; GREEN `21 passed`.
- Critical 2 startup-only program installation: RED `1 failed, 1 passed`;
  GREEN `9 passed`.
- Critical 3 reachable clearance path: RED `2 failed`; GREEN `25 passed`.
- Important 1 event semantics: RED `4 failed`; GREEN `22 passed`.
- Important 2 action validity contract: RED `4 failed`; GREEN `10 passed`.
- Production validity metadata: RED `4 failed`; GREEN `5 passed`.
- Important 3 clearance reporting: corrected RED `1 failed, 1 passed`; GREEN
  `26 passed`.
- Important 4 dynamic minimum green: RED `2 failed`; GREEN `28 passed`.
- Unpaired nominal green coverage: RED `1 failed`; executor GREEN `28 passed`.
- Clean-startup elapsed gate: RED `1 failed`; GREEN `36 passed`.
- Delayed validity horizon: RED `7 failed`; GREEN `7 passed`.
- Pre-self-review expanded affected suite: `238 passed in 2.12s`.

Final self-review found that a legal path could substitute an unavoidable
intermediate green whose nominal duration was below the live minimum. The exact
TDD cycle was:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_safety_executor.py::test_unavoidable_intermediate_green_requires_a_safe_nominal_duration -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\red-intermediate-green-minimum-fix1-20260821-1
```

- RED: `1 failed in 0.12s`; both original actions were incorrectly accepted.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_safety_executor.py::test_unavoidable_intermediate_green_requires_a_safe_nominal_duration -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\green-intermediate-green-minimum-fix1-20260821-1
```

- GREEN: `1 passed in 0.05s`.
- Executor regression after the fix: `30 passed in 0.06s`.

### Final Verification

All commands in this section ran on the final implementation and documentation
tree prepared for the fix commit.

- Required focused suite:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_safety_executor.py tests/test_action_validation.py tests/test_safety_metrics.py tests/test_runner_channel.py tests/test_fixed_time_plan.py tests/test_algorithms.py -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\focused-fix-round1-final-20260821-1
```

  Result: `115 passed in 1.24s`, no warnings.

- Expanded executor/runner/algorithm/bridge/channel suite:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_safety_executor.py tests/test_action_validation.py tests/test_safety_metrics.py tests/test_runner_channel.py tests/test_fixed_time_plan.py tests/test_algorithms.py tests/test_classic_max_pressure.py tests/test_capacity_aware_max_pressure.py tests/test_mock_bridge.py tests/test_traci_outputs.py tests/test_events.py tests/test_edge_channel.py -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\affected-239-fix-round1-final-20260821-1
```

  Result: `239 passed in 2.13s`, no warnings.

- Full project suite:

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\full-fix-round1-final-20260821-1
```

  Result: `563 passed in 91.40s`, no warnings. A fresh `--collect-only` also
  reported exactly `563 tests collected`; there are no duplicate top-level test
  names. The handoff estimate of at least 564 was one high: the committed base
  report recorded 543 tests and this diff adds 20 discovered cases.

- `python --version; python -m compileall algorithms cloud core engine
  experiments scenes`: Python `3.14.7`, exit 0.
- `git diff --check`: exit 0.
- `rg --pcre2 -n "(?<!_)apply_actions\(" algorithms cloud core engine
  experiments scenes scripts -g '*.py'`: no matches.

### Final-Tree Real SUMO Evidence

These are fresh 100-step intersection 1 runs with seed 42 on the final code
tree. All completed at simulation time `100.0`, used SUMO version field `22`,
and wrote 100 `simulation_log.csv` rows.

- Fixed time:

```powershell
.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm fixed_time --steps 100 --seed 42 --output-dir .t11\real-smoke-fixed-fix1-20260821-2
```

  Run `f542685ab3a0`, `completed`, 35 event rows. The only action was an
  accepted `set_program` at step 0 / simulation time 0.0 with reason
  `install frozen fixed-time plan`; rejections `0`, `illegal_transition=0`.

- Classic MaxPressure:

```powershell
.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm classic_maxpressure --steps 100 --seed 42 --output-dir .t11\real-smoke-classic-fix1-20260821-2
```

  Run `c766e0765a05`, `completed`, 119 event rows. `action_applied=14`,
  `action_rejected=70`: `minimum_green_violation=56` and
  `yellow_clearance_violation=14`; `illegal_transition=0`.

- Capacity-aware MaxPressure:

```powershell
.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm capacity_aware_maxpressure --steps 100 --seed 42 --output-dir .t11\real-smoke-capacity-fix1-20260821-2
```

  Run `d49718b3e634`, `completed`, 307 event rows including 100 audit rows.
  `action_applied=28`, `action_rejected=144`:
  `minimum_green_violation=58`, `yellow_clearance_violation=14`, and paired
  `phase_change_rejected=72`; `illegal_transition=0`.

### Protected Inputs and Scope

- `赛题资料.7z` SHA-256 remains
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`.
- `data/intersection_data` remains 163 tracked files and 232 disk files.
- Worktree and staged protected-path diff counts are both zero.
- `progress.md`, `.t9c`, `.t10`, `.t11`, the archive, output/cache files, and
  official data are excluded from the fix commit.

### Files Changed in Fix Round 1

- Production contract and safety: `core/types.py`,
  `engine/action_validation.py`, `engine/safety_executor.py`,
  `engine/safety.py`, and `engine/runner.py`.
- Production algorithms: `algorithms/fixed_time.py`,
  `algorithms/rule_adaptive.py`, `algorithms/classic_max_pressure.py`,
  `algorithms/ca_max_pressure.py`, and
  `algorithms/capacity_aware_max_pressure.py`.
- Live docs: `algorithms/README.md`, `docs/interface.md`, and
  `docs/architecture/interface.md`.
- Tests: `tests/test_action_validation.py`, `tests/test_algorithms.py`,
  `tests/test_capacity_aware_max_pressure.py`,
  `tests/test_classic_max_pressure.py`, `tests/test_fixed_time_plan.py`,
  `tests/test_runner_channel.py`, `tests/test_safety_executor.py`, and
  `tests/test_safety_metrics.py`.

### Self Review and Concerns

- Reviewed original-action/result mapping when the executor inserts an internal
  phase or duration; every algorithm action retains its own result and reason.
- Reviewed current, target, and substituted intermediate greens against the
  same live minimum-green snapshot for each action batch.
- Reviewed startup program installation, action expiry at the exact boundary,
  delayed unexpired delivery, graph reachability, and timing-event separation.
- The earlier report's concern that timing failures appear as
  `illegal_transition` is superseded by this fix and by the final real runs.
- The only retained product concern is the explicitly parked Task 10
  `CloudPolicy.predict()` / `dispatch_params()` compatibility issue. Fix Round 1
  was self-reviewed only, as required; no subagent or independent reviewer was
  dispatched.

## Fix Round 2: Startup Signal Program Safety

### Status

DONE_WITH_CONCERNS. The remaining Critical startup-program finding is closed on
top of reviewed base `f7a823dd466541819bb4603a8f931f5dac303b02`. Task 12 was
not started. The parked Task 10 same-observation `CloudPolicy` compatibility
issue remains unchanged and out of scope.

### Review Finding Closure

- Clean-startup `set_program` definitions now pass an independent timing policy
  check after schema and startup-coordinate validation and before the private
  bridge sink.
- A service-green phase contains `G/g` and no `Y/y`; every such phase must meet
  the live algorithm minimum green. A mixed green/yellow phase remains yellow
  clearance so continuing greens in official programs are preserved.
- Every cyclic transition between service-green phases must contain configured
  yellow clearance followed by pure all-red clearance, with each accumulated
  duration meeting the configured threshold. Direct green transitions,
  missing clearance, undersized clearance, and yellow after all-red reject as
  `unsafe_startup_program` without a signal write.
- Runner passes the configured `yellow_duration` and `all_red_duration` policy
  to the executor; the existing live minimum-green provider remains dynamic.
- Live safety-boundary documentation now records the independent startup-program
  minimum-green, yellow, and all-red checks.

### TDD Evidence

The behavior-level RED command was:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_safety_executor.py::test_startup_program_rejects_a_green_shorter_than_the_live_minimum tests/test_safety_executor.py::test_startup_program_rejects_a_direct_green_to_green_transition tests/test_safety_executor.py::test_startup_program_requires_configured_clearance -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\red-startup-program-policy-fix2-20260821-1
```

- RED: `6 failed in 0.19s`; all unsafe definitions were accepted and written.
- The six discovered cases cover a short green, direct green-to-green, missing
  yellow, short yellow, missing all-red, and short all-red program.

The exact GREEN command used a fresh basetemp:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_safety_executor.py::test_startup_program_rejects_a_green_shorter_than_the_live_minimum tests/test_safety_executor.py::test_startup_program_rejects_a_direct_green_to_green_transition tests/test_safety_executor.py::test_startup_program_requires_configured_clearance -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\green-startup-program-policy-fix2-20260821-1
```

- GREEN: `6 passed in 0.06s`.
- Full executor regression after implementation: `36 passed in 0.06s`.
- Full executor regression after live-doc updates: `36 passed in 0.06s`.

### Final Verification

All commands below ran on the final implementation and live-documentation tree
prepared for the Round 2 commit.

- Required focused suite:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_safety_executor.py tests/test_action_validation.py tests/test_safety_metrics.py tests/test_runner_channel.py tests/test_fixed_time_plan.py tests/test_algorithms.py -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\focused-fix-round2-final-20260821-1
```

  Result: `121 passed in 1.53s`, no warnings.

- Expanded executor/runner/algorithm/bridge/channel suite:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_safety_executor.py tests/test_action_validation.py tests/test_safety_metrics.py tests/test_runner_channel.py tests/test_fixed_time_plan.py tests/test_algorithms.py tests/test_classic_max_pressure.py tests/test_capacity_aware_max_pressure.py tests/test_mock_bridge.py tests/test_traci_outputs.py tests/test_events.py tests/test_edge_channel.py -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\affected-fix-round2-final-20260821-1
```

  Result: `245 passed in 2.53s`, no warnings.

- Full project suite:

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\full-fix-round2-final-20260821-1
```

  Result: `569 passed in 131.35s (0:02:11)`, no warnings.

- `python --version`: Python `3.14.7`.
- `python -m compileall algorithms cloud core engine experiments scenes`:
  exit 0.
- `git diff --check`: exit 0.
- `rg --pcre2 -n "(?<!_)apply_actions\(" algorithms cloud core engine
  experiments scenes scripts -g '*.py'`: no matches.

### Final-Tree Real SUMO Evidence

The required fresh 100-step intersection 1 fixed-time run used seed 42:

```powershell
.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm fixed_time --steps 100 --seed 42 --output-dir .t11\real-smoke-fixed-fix2-20260821-1
```

- Run `baa105b06e08` completed with requested steps `100`, final simulation time
  `100.0`, SUMO version field `22`, and exactly 100 `simulation_log.csv` rows.
- The only signal action was an accepted `set_program` at step `0` / simulation
  time `0.0`, with reason `install frozen fixed-time plan`.
- Events contain one `action_applied`, zero `action_rejected`, and zero
  `illegal_transition` rows.

### Protected Inputs and Scope

- `赛题资料.7z` SHA-256 remains
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`.
- `data/intersection_data` remains 163 tracked files and 232 disk files.
- Official-data and output worktree/staged diff checks are empty; the complete
  staged set was also empty before final scoped staging.
- Pre-existing `progress.md`, `.t9c`, `.t10`, `.t11`, the archive, output/cache
  files, parked Task 10 code, and official data remain excluded from this fix.

### Files Changed in Fix Round 2

- Production safety: `engine/action_validation.py`, `engine/safety_executor.py`,
  and `engine/runner.py`.
- Regression coverage: `tests/test_safety_executor.py`.
- Live docs: `algorithms/README.md`, `docs/interface.md`, and
  `docs/architecture/interface.md`.
- Evidence: this report.

### Self Review and Concerns

- Reviewed the normalized program type boundary before timing validation; schema
  validation guarantees a non-empty list of finite-duration, equal-width phase
  mappings before the policy reads states or durations.
- Reviewed cyclic behavior for both multiple and single service-green programs.
  A single service green scans every intervening phase before returning to
  itself, while a lone green with no clearance rejects as a direct cyclic
  transition.
- Reviewed official mixed green/yellow phase semantics: mixed phases count as
  yellow clearance rather than new service greens, and pure all-red is required
  after yellow before the next service green.
- Reviewed rejection ordering and confirmed unsafe definitions cannot reach the
  private bridge sink or suppress the next safety observation.
- The only retained product concern is the explicitly parked Task 10
  `CloudPolicy.predict()` / `dispatch_params()` compatibility issue. Fix Round 2
  was self-reviewed only as required; no subagent or independent reviewer was
  dispatched.

## Fix Round 3: Variant Boundary and Movement-Aligned Clearance

### Status

IMPLEMENTED_PENDING_INDEPENDENT_RE-REVIEW. This round addresses both Critical
findings from `task-11-r2-rereview.md`; Task 12 was not started. The parked Task
10 same-observation `CloudPolicy.predict()` / `dispatch_params()` compatibility
issue remains unchanged and must stay in the final whole-branch fix wave.

### Critical Closure

- `TraCIBridge.start()` no longer calls `traci.trafficlight.setProgram()` for a
  `variant_*` additional signal file. It parses the source `tlLogic` into a
  run-time `ControlAction` queue consumed once by `take_startup_actions()`.
- `SimulationRunner` consumes queued startup actions before the first tick and
  after an automatic bridge reconnect. Both paths call the existing
  `SafetyExecutor.apply()` with a zero-time startup state and record normal
  `action_applied` / `action_rejected` rows, including action payload, reason,
  and simulation seconds. Rejected variant startup programs fail fast for
  controller algorithms. `fixed_time` records the rejection and continues so
  its own validated Excel `set_program` action can supersede an unsafe source
  variant, preserving the pre-existing fixed-time workflow without a bypass.
- `validate_startup_program_safety()` now tracks every signal index that is green
  in the departing service phase and accumulates yellow duration only when that
  same signal index is yellow. A mismatched yellow on another signal is rejected
  with `signal_index=<n>` evidence; every departing green must meet the yellow
  threshold before pure all-red clearance.

### TDD Evidence

The first round-3 behavior run was intentionally RED:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_resilience.py::test_start_defers_variant_signal_program_to_the_safety_boundary tests/test_runner_channel.py::test_runner_applies_and_records_pending_startup_program_through_safety tests/test_safety_executor.py::test_startup_program_rejects_yellow_on_an_unrelated_signal tests/test_safety_executor.py::test_startup_program_accepts_a_movement_aligned_multi_green_cycle -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\red-fix-round3-20260821-1
```

- RED: `3 failed, 1 passed`; the direct variant write remained, runner did not
  consume pending startup actions, and the movement-mismatched yellow was
  accepted. The positive multi-green case passed as the baseline.

The first implementation GREEN run was:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_resilience.py::test_start_defers_variant_signal_program_to_the_safety_boundary tests/test_runner_channel.py::test_runner_applies_and_records_pending_startup_program_through_safety tests/test_safety_executor.py::test_startup_program_rejects_yellow_on_an_unrelated_signal tests/test_safety_executor.py::test_startup_program_accepts_a_movement_aligned_multi_green_cycle -q -p no:cacheprovider --basetemp D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.t11\green-fix-round3-20260821-1
```

- GREEN: `4 passed`.
- Reconnect lifecycle RED: `1 failed` for
  `test_runner_reapplies_a_variant_program_through_safety_after_reconnect`.
- Reconnect lifecycle GREEN: `5 passed` including the initial four cases.
- Fixed-time fallback RED: `1 failed` for
  `test_fixed_time_continues_after_rejected_variant_startup_program`.
- Fixed-time fallback GREEN: `6 passed` including the movement, startup, and
  reconnect cases.

### Final Verification

- Focused suite: `132 passed in 1.20s`.
- Affected suite (safety, runner, bridge, algorithms, variants, service):
  `273 passed in 14.85s`.
- Full project suite: `574 passed in 84.62s (0:01:24)`, no warnings.
- `python --version`: Python `3.14.7`.
- `python -m compileall -q algorithms cloud core engine experiments scenes`:
  exit 0.
- `git diff --check`: exit 0.
- Protected archive SHA-256 remains
  `12A6F2FD69ACBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`.
- `data/intersection_data` remains `163` Git-tracked files and `232` files on
  disk; working-tree and staged protected-path diffs are empty.
- Production signal writes are confined to `TraCIBridge._apply_actions()`
  (including its same-method rollback). No public `apply_actions(` caller was
  found in algorithms, cloud, core, engine, experiments, scenes, or scripts.

### Final-Tree Real SUMO Evidence

Fixed-time compatibility smoke:

```powershell
.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm fixed_time --steps 100 --seed 42 --output-dir .t11\real-smoke-fixed-fix3-20260821-2
```

- Run `0958b5337c31` completed with requested steps `100`, final simulation
  time `100.0`, SUMO version `22`, and `100` simulation-log rows.
- Events contain one `action_rejected` with reason
  `unsafe_startup_program` for the source variant and one accepted fixed-time
  `set_program` at simulation time `0.0`; `illegal_transition=0`.

Safe variant smoke:

```powershell
.venv\Scripts\python.exe -m experiments.runner --intersection 15 --algorithm classic_maxpressure --flow-multiplier 1.25 --steps 100 --seed 42 --output-dir .t11\real-smoke-variant-fix3-20260821-1
```

- Run `1df38e46cd3b` completed with `requested_steps=100`, final simulation
  time `10.0` under the scene's `0.1`-second step length, SUMO version `22`,
  and `100` simulation-log rows.
- The variant `set_program` was accepted at step 0 / simulation time `0.0`
  through the safety boundary. Later rejections were only structured
  `minimum_green_violation` controller timing outcomes; no
  `illegal_transition` event was produced.

### Files Changed in Fix Round 3

- Production: `engine/action_validation.py`, `engine/runner.py`,
  `engine/traci_bridge.py`.
- Regression coverage: `tests/test_safety_executor.py`,
  `tests/test_resilience.py`, `tests/test_runner_channel.py`.
- Evidence: this report.

### Self Review and Remaining Gate

- Startup actions are consumed exactly once, and reconnect startup actions are
  consumed before the next controller decision with a refreshed state after
  program installation.
- Startup action evidence follows the lifecycle order `run_start`, structured
  action result, then `terminal`.
- Source XML is only parsed into a domain action; structural, startup-coordinate,
  minimum-green, movement-specific yellow, and all-red checks happen in the
  shared executor path before the private bridge sink.
- Fixed-time's explicit fallback is limited to its own algorithm name and still
  records the rejected source variant; other algorithms fail on an unsafe
  startup variant instead of silently running a requested-but-uninstalled
  program.
- This report is awaiting an independent scoped re-review of
  `f7a823d..HEAD`. The Task 10 parked compatibility finding remains open.
