# Task 10 Report: Capacity-Aware MaxPressure Ablations and Edge Envelope

## Implementation

- Added `CapacityAwareConfig` frozen M0-M4 layer configurations and a movement-level `CapacityAwareMaxPressureAlgorithm`.
- M0 exposes the exact classic raw movement pressure scores. M1 adds capacity normalization. M2 gates only movements whose downstream occupancy is at or above the configured threshold and preserves a no-action current-phase fallback when no demanded movement remains viable. M3 freezes the attributable settings and emits ordinary `ControlAction` values through the existing Runner validation path. M4 alone enables cloud prediction.
- Added serializable `PhaseScore` score breakdowns, movement and blocked-movement IDs, per-score logging, minimum/maximum dynamic-green clamping, and run metadata provenance.
- Added `ClassicMaxPressureAlgorithm.score_breakdown()` without adding capacity, spillback, EWMA, or cloud behavior to classic control.
- Converted EWMA input/output units: source flow is veh/h; each prediction is vehicles over `horizon_seconds`. EWMA history remains in veh/h so later predictions keep the same unit.
- Replaced the production bare `JointState` EdgeChannel path with `EdgeMessage(run_id, simulation_time, sent_at, expires_at, payload_version, payload)`. The Runner constructs and consumes the envelope. The channel releases by simulation time, drops expiry, rejects forbidden directions, and records structured events.
- Registered the layered controller for `capacity_aware_maxpressure`; retained `ca_max_pressure.py` only as a documented legacy phase-state compatibility implementation.

## TDD Evidence

All behavior tests use hand-derived literal expectations and real state/control behavior.

1. RED 1:
   `./.venv/Scripts/python.exe -m pytest tests/test_capacity_aware_max_pressure.py tests/test_edge_channel.py tests/test_runner_channel.py -q -p no:cacheprovider --basetemp=.t10/pytest-red-1`
   Result: collection failed as expected: `ModuleNotFoundError: algorithms.capacity_aware_max_pressure` and `ImportError: cannot import name EdgeMessage`.
2. GREEN 1:
   `./.venv/Scripts/python.exe -m pytest tests/test_capacity_aware_max_pressure.py tests/test_edge_channel.py tests/test_runner_channel.py -q -p no:cacheprovider --basetemp=.t10/pytest-green-2`
   Result: `25 passed in 0.76s`.
3. RED 2:
   `./.venv/Scripts/python.exe -m pytest tests/test_capacity_aware_max_pressure.py::test_prediction_keeps_ewma_history_in_hourly_flow_units -q -p no:cacheprovider --basetemp=.t10/pytest-red-2`
   Result: failed as expected; repeated 600 veh/h incorrectly forecast `17.916666666666668` rather than 50 vehicles in 300 seconds.
4. GREEN 2:
   `./.venv/Scripts/python.exe -m pytest tests/test_capacity_aware_max_pressure.py -q -p no:cacheprovider --basetemp=.t10/pytest-green-3`
   Result: `9 passed in 0.58s`.
5. RED 3:
   full regression first found `test_run_service_injects_frozen_ca_mp_parameters` failing before Runner construction because the new factory rejected the established frozen CA parameters.
6. GREEN 3:
   `./.venv/Scripts/python.exe -m pytest tests/test_run_service.py::test_run_service_injects_frozen_ca_mp_parameters tests/test_capacity_aware_max_pressure.py -q -p no:cacheprovider --basetemp=.t10/pytest-green-4`
   Result: `11 passed in 1.90s`.
7. RED 4:
   `./.venv/Scripts/python.exe -m pytest tests/test_runner_channel.py::test_capacity_aware_run_metadata_records_the_frozen_prediction_manifest -q -p no:cacheprovider --basetemp=.t10/pytest-red-3`
   Result: failed as expected with `KeyError: algorithm_manifest`.
8. GREEN 4:
   `./.venv/Scripts/python.exe -m pytest tests/test_runner_channel.py::test_capacity_aware_run_metadata_records_the_frozen_prediction_manifest tests/test_capacity_aware_max_pressure.py tests/test_edge_channel.py -q -p no:cacheprovider --basetemp=.t10/pytest-green-5`
   Result: `14 passed in 0.69s`.
9. A subsequent full run correctly exposed that the old `CountingAlgorithm` test double inherited `FixedTimeAlgorithm` without the required `resolved_timing_plan` state. The test fixture was made a valid subclass state; no production behavior was relaxed.

## Verification

- Required focused command:
  `./.venv/Scripts/python.exe -m pytest tests/test_capacity_aware_max_pressure.py tests/test_cloud.py tests/test_algorithms.py -q -p no:cacheprovider --basetemp=.t10/pytest-focused-required`
  Result: `28 passed in 0.74s`.
- Final focused integration command:
  `./.venv/Scripts/python.exe -m pytest tests/test_runner_channel.py tests/test_capacity_aware_max_pressure.py tests/test_edge_channel.py tests/test_cloud.py tests/test_algorithms.py -q -p no:cacheprovider --basetemp=.t10/pytest-focused-final`
  Result: `46 passed in 1.04s`.
- Full project interpreter suite:
  `./.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.t10/pytest-full-final3`
  Result: `435 passed in 84.67s`; no warnings.
- System Python compile:
  `python --version; python -m compileall algorithms cloud engine`
  Result: Python `3.14.7`, exit 0.
- Real SUMO/RunService smoke (not a formal experiment):
  `./.venv/Scripts/python.exe -m experiments.runner --intersection 1 --algorithm capacity_aware_maxpressure --steps 100 --seed 42 --output-dir .t10/smoke-final`
  Result: completed, run_id `82139da25979`, `rejected=0`, `illegal=0`, `applied=0`. Metadata contains the prediction manifest with false/300/0.15.
- `git diff --check`: exit 0.
- Protected archive SHA-256: `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`.
- `data/intersection_data` tracked count: 163; protected-path diff exit 0. The archive remains untracked and was not modified.

## Files

- Added: `algorithms/capacity_aware_max_pressure.py`, `tests/test_capacity_aware_max_pressure.py`, `task-10-report.md`.
- Modified: `algorithms/ca_max_pressure.py`, `algorithms/classic_max_pressure.py`, `algorithms/registry.py`, `cloud/cloud_policy.py`, `config/default.yaml`, `engine/artifacts.py`, `engine/edge_channel.py`, `engine/runner.py`, `tests/test_edge_channel.py`, `tests/test_runner_channel.py`.

## Self Review and Concerns

- Classic remains independent and raw-score-only. M0 comparison uses identical classic arithmetic.
- Message tests cover delayed release at time 12, expiry, forbidden direction rejection event, all envelope identity/time/version fields, and actual Runner consumption.
- M3 deliberately does not implement a separate transition or fallback executor. It emits through the existing action validation channel as required; Task 11 retains ownership of the unified safety executor.
- The 100-step smoke made no applied phase actions because its legal phase graph rejected non-direct targets; this is intentional safe no-action fallback and produced no rejected/illegal actions. It is not formal experimental evidence.

## Review Fix Round 1

### TDD Evidence

1. RED capacity preflight:
   `./.venv/Scripts/python.exe -m pytest tests/test_capacity_preflight.py tests/test_runner_channel.py::test_capacity_aware_invalid_lane_capacity_fails_before_starting_bridge -q -p no:cacheprovider --basetemp=.t10/fix1-red-capacity`
   Result: collection failed as expected with `ModuleNotFoundError: No module named 'scenes.capacity_preflight'`.
2. GREEN capacity preflight:
   `./.venv/Scripts/python.exe -m pytest tests/test_capacity_preflight.py tests/test_runner_channel.py::test_capacity_aware_invalid_lane_capacity_fails_before_starting_bridge -q -p no:cacheprovider --basetemp=.t10/fix1-green-capacity`
   Result: `2 passed in 0.84s`.
3. RED dynamic-green average:
   `./.venv/Scripts/python.exe -m pytest tests/test_capacity_aware_max_pressure.py::test_dynamic_green_averages_only_strictly_positive_phase_scores -q -p no:cacheprovider --basetemp=.t10/fix1-red-duration`
   Result: failed as expected: hand-derived expected duration `30.0`, actual `90.0`; zero and negative scores diluted the divisor.
4. GREEN dynamic-green average:
   `./.venv/Scripts/python.exe -m pytest tests/test_capacity_aware_max_pressure.py::test_dynamic_green_averages_only_strictly_positive_phase_scores -q -p no:cacheprovider --basetemp=.t10/fix1-green-duration`
   Result: `1 passed in 0.62s`.
5. RED envelope identity/version:
   `./.venv/Scripts/python.exe -m pytest tests/test_edge_channel.py::test_stale_run_and_incompatible_payload_version_are_rejected -q -p no:cacheprovider --basetemp=.t10/fix1-red-channel`
   Result: failed as expected with `TypeError: EdgeChannel.__init__() got an unexpected keyword argument 'expected_run_id'`.
6. GREEN envelope identity/version:
   `./.venv/Scripts/python.exe -m pytest tests/test_edge_channel.py::test_stale_run_and_incompatible_payload_version_are_rejected -q -p no:cacheprovider --basetemp=.t10/fix1-green-channel`
   Result: `1 passed in 0.08s`.
7. RED audit attribution and non-unit delay:
   `./.venv/Scripts/python.exe -m pytest tests/test_capacity_aware_max_pressure.py::test_m2_m3_have_distinct_boundary_identity_and_serializable_audit tests/test_run_service.py::test_run_service_converts_edge_delay_steps_to_scene_seconds -q -p no:cacheprovider --basetemp=.t10/fix1-red-audit-delay`
   Result: `2 failed in 2.32s`: missing `audit_record`, and delay was `2.0` seconds instead of the required `1.0` seconds for two 0.5-second steps.
8. GREEN audit attribution and non-unit delay:
   `./.venv/Scripts/python.exe -m pytest tests/test_capacity_aware_max_pressure.py::test_m2_m3_have_distinct_boundary_identity_and_serializable_audit tests/test_run_service.py::test_run_service_converts_edge_delay_steps_to_scene_seconds -q -p no:cacheprovider --basetemp=.t10/fix1-green-audit-delay`
   Result: `2 passed in 1.76s`.

### Verification

- Required plan command:
  `./.venv/Scripts/python.exe -m pytest tests/test_capacity_aware_max_pressure.py tests/test_cloud.py tests/test_algorithms.py -q -p no:cacheprovider --basetemp=.t10/fix1-plan-focused-final2`
  Result: `30 passed in 0.82s`.
- Expanded amended-code coverage:
  `./.venv/Scripts/python.exe -m pytest tests/test_capacity_preflight.py tests/test_runner_channel.py tests/test_run_service.py tests/test_edge_channel.py tests/test_capacity_aware_max_pressure.py -q -p no:cacheprovider --basetemp=.t10/fix1-focused-expanded-final2`
  Result: `45 passed in 10.31s`; includes the 20/20 official-scene static capacity preflight and a real Runner 0.5-second, two-tick delayed delivery test (`[0, 1, 2]`).
- Final full suite:
  `./.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.t10/fix1-full-final2`
  Result: `443 passed in 83.95s`, no warnings.
- Real 100-step RunService/SUMO capacity-aware smoke with an `EdgeMessage` path:
  `RunService(...).run_sync(RunRequest('1', 'capacity_aware_maxpressure', steps=100, seed=42, edge_delay_steps=2))`
  Result: run ID `f80de5c025b6`, `completed`, `applied=0`, `rejected=0`, `illegal_transition=0`, `channel_wait=2`, and `algorithm_audit=98`. Manifest records `layer=M3`, `safety_boundary=shared_action_validation`, and `prediction_enabled=false`; audit events contain those identities, per-movement components/block reasons, selection reason, and final decision. This is smoke evidence, not formal results.
- Python compatibility:
  `python --version` reported `Python 3.14.7`; `python -m compileall algorithms cloud engine scenes` exited 0.
- Integrity:
  `git diff --check` exited 0. `赛题资料.7z` SHA-256 remained `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`; protected inputs remain 163 tracked files and 232 disk files, with no protected-path diff or staging.

### Files Changed

- Added `scenes/capacity_preflight.py` and `tests/test_capacity_preflight.py`.
- Modified `algorithms/capacity_aware_max_pressure.py`, `engine/edge_channel.py`, `engine/runner.py`, `engine/run_service.py`, `tests/test_capacity_aware_max_pressure.py`, `tests/test_edge_channel.py`, `tests/test_runner_channel.py`, and `tests/test_run_service.py`.

### Self Review and Concerns

- Static capacity preflight is read-only, runs from capacity-aware `init()` before `bridge.start()`, names every unavailable/non-positive required lane, and leaves `MovementState` validation unchanged.
- M2 and M3 now freeze different layer and safety-boundary provenance. The existing shared action validator remains the only executor; this change records its boundary rather than implementing Task 11 behavior.
- The direct channel `delay_seconds` API remains available for explicit simulation-time tests. `RunService` alone converts the public `edge_delay_steps` using the resolved scene step length.
- The smoke selects only no-action fallbacks for this short legal phase graph; no safety-executor behavior was added here.

### Review Fix Round 1 Continuation: Edge Message Evidence Timing

9. RED envelope time consistency:
   `./.venv/Scripts/python.exe -m pytest tests/test_edge_channel.py::test_inconsistent_message_times_are_rejected_before_buffering -q -p no:cacheprovider --basetemp=.t10/fix1-red-time-contract`
   Result: `4 failed in 0.14s` as expected. Each malformed message was incorrectly buffered and later produced `message_expired` instead of an immediate stable `message_rejected` reason.
10. GREEN envelope time consistency:
    `./.venv/Scripts/python.exe -m pytest tests/test_edge_channel.py::test_inconsistent_message_times_are_rejected_before_buffering -q -p no:cacheprovider --basetemp=.t10/fix1-green-time-contract`
    Result: `4 passed in 0.06s`. `send()` now rejects payload timestamp mismatch, sent-after-simulation, expiration-not-after-sent, and expiration-not-after-simulation before buffering.
11. RED channel event evidence time:
    `./.venv/Scripts/python.exe -m pytest tests/test_runner_channel.py::test_runner_records_rejected_channel_event_at_message_simulation_time -q -p no:cacheprovider --basetemp=.t10/fix1-red-event-time`
    Result: `1 failed in 0.85s` as expected: the rejected CSV row's `simulation_seconds` was empty rather than the message time `12.5`.
12. GREEN channel event evidence time:
    `./.venv/Scripts/python.exe -m pytest tests/test_runner_channel.py::test_runner_records_rejected_channel_event_at_message_simulation_time -q -p no:cacheprovider --basetemp=.t10/fix1-green-event-time`
    Result: `1 passed in 0.73s`. Runner now forwards `EdgeChannelEvent.simulation_time` to `EventLogger` as `simulation_seconds`.

### Continuation Verification

- New focused tests:
  `./.venv/Scripts/python.exe -m pytest tests/test_edge_channel.py::test_inconsistent_message_times_are_rejected_before_buffering tests/test_runner_channel.py::test_runner_records_rejected_channel_event_at_message_simulation_time -q -p no:cacheprovider --basetemp=.t10/fix1-new-focused`
  Result: `5 passed in 0.69s`.
- Task 10 expanded focused tests:
  `./.venv/Scripts/python.exe -m pytest tests/test_capacity_preflight.py tests/test_runner_channel.py tests/test_run_service.py tests/test_edge_channel.py tests/test_capacity_aware_max_pressure.py tests/test_cloud.py tests/test_algorithms.py -q -p no:cacheprovider --basetemp=.t10/fix1-expanded-final`
  Result: `68 passed in 10.97s`.
- Final project suite:
  `./.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.t10/fix1-full-edge-timing`
  Result: `448 passed in 85.61s`, no warnings.
- Real 100-step RunService/SUMO EdgeMessage smoke:
  `RunService(...).run_sync(RunRequest('1', 'capacity_aware_maxpressure', steps=100, seed=42, edge_delay_steps=2))`
  Result: run ID `f7ad671f045f`, `completed`, `applied=0`, `rejected=0`, `illegal_transition=0`, `channel_wait=2`, and `algorithm_audit=98`; manifest continues to record `layer=M3` and `safety_boundary=shared_action_validation`.
- Compatibility and integrity:
  `python --version` reported `Python 3.14.7`; `python -m compileall algorithms cloud engine scenes` exited 0; `git diff --check` exited 0. Protected archive SHA-256 remained `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`, with 163 protected tracked files and 232 protected disk files, no protected-path diff or staging.
