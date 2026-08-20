# Task 9 Report: traceable fixed timing and classic MaxPressure

## Status

DONE_WITH_CONCERNS. The requested implementation, tests, protected-input
checks, and commit are complete. One early full-suite run exposed a stale API
availability assertion; the final full suite passed after that test was updated.
This means two full-suite invocations occurred rather than the requested one.

## Implementation

- Added `algorithms.fixed_time_plan.FixedTimePlanResolver` and immutable
  `ResolvedTimingPlan`. It resolves in this exact order: an explicitly supplied
  standardized scene plan (`timing_plan`, `fixed_time_plan`, or
  `standardized_timing_plan`), the official Excel workbook, then the source
  network `tlLogic`.
- Every resolution records a repository-relative POSIX source path, SHA-256,
  and program ID. An unavailable, empty, malformed, non-portable, or illegal
  plan raises `FixedTimePlanError`; there is no default timing fallback.
- `FixedTimeAlgorithm.init()` freezes the plan before the run and publishes its
  provenance through `manifest["timing_plan"]`.
- Added an independent `ClassicMaxPressureAlgorithm` using only legal green
  `phase_movements`: `sum(saturation_rate * (queue_vehicles -
  downstream_queue_vehicles))`. It selects ties by current phase, then lowest
  index, emits a deterministic `set_phase`, and resets target/history.
- Registered `classic_maxpressure` with its own available factory. Added the
  manifest surface to the base class and explicitly labels CA-MP enhancements;
  classic has no enhancement flags and imports none of the CA-MP/cloud logic.
- Updated former virtual fixed-time test scenes to point at the read-only
  official network, since nonexistent networks are now intentionally rejected.

## TDD Evidence

1. Initial test collection (before modules existed):
   `& .venv\Scripts\python.exe -m pytest tests\test_fixed_time_plan.py tests\test_classic_max_pressure.py -q`
   Result: collection failed with expected missing-module imports. This was not
   accepted as behavioral RED evidence.
2. Behavioral RED after import seams:
   `& .venv\Scripts\python.exe -m pytest tests\test_fixed_time_plan.py tests\test_classic_max_pressure.py -q --basetemp=.test-temp\pytest`
   Result: 5 failed, 2 passed. Resolver raised `timing plan resolution is not
   implemented`; classic returned no action; registry remained unavailable.
3. Green after minimal resolver/classic/registry implementation:
   same command; result `7 passed`.
4. Compatibility RED for mandatory plan resolution:
   `& .venv\Scripts\python.exe -m pytest tests\test_fixed_time_plan.py tests\test_classic_max_pressure.py tests\test_algorithms.py -q --basetemp=.test-temp\pytest`
   Result: old dummy network fixture raised `no legal timing plan is available`.
   Fixture was made a real read-only network source; focused result was
   `26 passed`.
5. Illegal-plan RED/green:
   - Empty official Excel initially fell back to net XML (`Failed: DID NOT
     RAISE`); resolver now raises.
   - Excel with `green=-1` initially passed (`Failed: DID NOT RAISE`); resolver
     now validates every Excel phase.
   - Portable-path RED: absolute source path assertions failed; provenance now
     uses repository-relative POSIX paths.
   Final focused command:
   `& .venv\Scripts\python.exe -m pytest tests\test_fixed_time_plan.py tests\test_classic_max_pressure.py tests\test_algorithms.py tests\test_algorithm_registry.py -q --basetemp=.test-temp\pytest`
   Result: `28 passed, 1 warning`.
6. Runner integration command:
   `& .venv\Scripts\python.exe -m pytest tests\test_events.py tests\test_resilience.py tests\test_runner_channel.py tests\test_seed.py tests\test_step_log.py tests\test_run_service.py -q --basetemp=.test-temp\pytest`
   Result: `44 passed, 1 warning`.

## Final Verification

- Real-scene resolver check: all 20 registered scenes resolved successfully,
  all from `official_excel`, with a source hash and program ID.
- Final full suite:
  `& .venv\Scripts\python.exe -m pytest -q --basetemp=.test-temp\pytest`
  Result: `420 passed, 1 warning in 79.94s`. The warning is the pre-existing
  protected `.pytest_cache` permission warning.
- System compatibility:
  `python --version; python -m compileall -q algorithms core scenes engine`
  Result: `Python 3.14.7`, exit code 0.
- `git diff --check`: exit code 0.
- Protected input checks before and after tests:
  - `data/intersection_data`: 232 files, aggregate SHA-256
    `bdfaab9b4d511a5d0af55a9e49f41ad222058abe29923609ff0e5a2ca22e9c1a`
  - `赛题资料.7z`: SHA-256
    `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`
  - `git diff --exit-code -- data/intersection_data`: exit code 0.

## Files

- Added: `algorithms/classic_max_pressure.py`, `algorithms/fixed_time_plan.py`,
  `tests/test_classic_max_pressure.py`, `tests/test_fixed_time_plan.py`.
- Modified: `algorithms/base.py`, `algorithms/ca_max_pressure.py`,
  `algorithms/fixed_time.py`, `algorithms/registry.py`, `algorithms/__init__.py`,
  and affected algorithm/API/runner tests.

## Self-review and concerns

- Confirmed classic does not import or reference `CloudPolicy`, prediction,
  occupancy, capacity normalization, spillback, or EWMA behavior.
- Confirmed fixed timing does not mutate source inputs and errors before runner
  control steps when a valid source cannot be resolved.
- The final full suite is clean. The only concern is the additional early full
  suite invocation described above; it was needed to locate a stale test that
  contradicted the new required registry availability.
