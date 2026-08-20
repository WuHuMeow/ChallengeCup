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
