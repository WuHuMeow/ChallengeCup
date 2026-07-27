# IA/IB Verification Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing IA/IB acceptance gate enforce the approved 3600-second, legal-action, and reproducible-evidence requirements without rerunning valid matrix artifacts unnecessarily.

**Architecture:** Keep runtime facts in `run_metadata.json`, derive native final time from SUMO `stats.xml`, and make matrix reuse depend on both facts. Keep action validation shared, but supply each bridge's real phase/program domain. Generate provenance and evidence axes from repository and check results so a fresh verifier run reproduces the report.

**Tech Stack:** Python 3.12, pytest, SUMO XML, TraCI, Git CLI.

## Global Constraints

- Preserve the existing unified `RunRequest -> RunService -> SimulationRunner -> RunArtifacts` path.
- Do not modify source competition data under `data/intersection_data/`.
- Preserve the pre-existing uncommitted `docs/reports/ia-ib-final-verification.md` change.
- Docker and second-machine checks remain truthful `not_run` until external evidence exists.
- Every behavior change follows red-green-refactor and all repository checks must pass before completion.

---

### Task 1: Enforce Full-Horizon Matrix Evidence

**Files:**
- Modify: `engine/artifacts.py`
- Modify: `engine/runner.py`
- Modify: `engine/run_service.py`
- Modify: `scripts/run_pdf_matrix.py`
- Test: `tests/test_artifacts.py`
- Test: `tests/test_tuning.py`

**Interfaces:**
- Produces: metadata keys `requested_steps`, `final_simulation_time`, and `step_length`.
- Produces: `read_final_sumo_time(stats_path: Path) -> float | None` and `is_complete(result_dir: Path, request: RunRequest | None = None) -> bool`.
- Consumes: native SUMO `<step time="3599.90">` entries from `stats.xml`.

- [ ] **Step 1: Write failing metadata and matrix-resume tests**

```python
def make_complete_run(root, final_time, requested_steps):
    run_dir = root / "run"
    run_dir.mkdir()
    write_required_artifacts(run_dir)
    write_metadata(run_dir, status="completed", requested_steps=requested_steps)
    (run_dir / "stats.xml").write_text(
        f'<summary><step time="{final_time}"/></summary>', encoding="utf-8"
    )
    return run_dir


def test_is_complete_rejects_short_native_sumo_run(tmp_path):
    request = RunRequest("1", "fixed_time", steps=36000)
    run_dir = make_complete_run(tmp_path, final_time=3598.0, requested_steps=36000)
    assert is_complete(run_dir, request) is False


def test_is_complete_accepts_full_native_sumo_run(tmp_path):
    request = RunRequest("1", "fixed_time", steps=36000)
    run_dir = make_complete_run(tmp_path, final_time=3599.9, requested_steps=36000)
    assert is_complete(run_dir, request) is True
```

- [ ] **Step 2: Run the focused tests and confirm they fail because duration is unchecked**

Run: `.venv/Scripts/python.exe -m pytest tests/test_artifacts.py tests/test_tuning.py -q`

Expected: the short-run rejection and new metadata assertions fail.

- [ ] **Step 3: Persist runtime facts and validate native horizon**

```python
payload.update({
    "requested_steps": requested_steps,
    "final_simulation_time": final_simulation_time,
    "step_length": step_length,
})
```

Parse the last SUMO statistics step, compute `target_time = requested_steps * step_length`, and accept only when both metadata and native time reach `target_time - step_length - 1e-9`.

- [ ] **Step 4: Run the focused tests and confirm they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_artifacts.py tests/test_tuning.py tests/test_runner_channel.py -q`

Expected: all selected tests pass.

### Task 2: Enforce Legal Action Domains

**Files:**
- Modify: `engine/action_validation.py`
- Modify: `engine/mock_bridge.py`
- Modify: `engine/traci_bridge.py`
- Test: `tests/test_traci_outputs.py`
- Test: `tests/test_mock_bridge.py`

**Interfaces:**
- Produces: `validate_control_action(action, tls_id, *, phase_count=None, program_ids=None)`.
- Consumes: TraCI active program phase count and all available program IDs.

- [ ] **Step 1: Write failing boundary and bridge-parity tests**

```python
@pytest.mark.parametrize("value", [True, -1, 4])
def test_phase_rejects_bool_and_out_of_range(value):
    action = ControlAction("tls", "set_phase", value)
    assert validate_control_action(action, "tls", phase_count=4)[1]


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_duration_rejects_non_finite(value):
    action = ControlAction("tls", "set_phase_duration", value)
    assert validate_control_action(action, "tls")[1]
```

Also assert unknown programs are rejected without calling TraCI and the Mock bridge returns the same reasons.

- [ ] **Step 2: Run the focused tests and confirm they fail for the missing domain checks**

Run: `.venv/Scripts/python.exe -m pytest tests/test_traci_outputs.py tests/test_mock_bridge.py -q`

Expected: bool, non-finite, out-of-range, and unknown-program cases fail.

- [ ] **Step 3: Add minimal shared validation and bridge context lookup**

```python
if isinstance(value, bool) or not isinstance(value, int):
    return None, "set_phase value must be an integer"
if phase_count is not None and not 0 <= value < phase_count:
    return None, "set_phase value is outside the active program"
if not math.isfinite(duration):
    return None, "set_phase_duration value must be finite"
```

TraCI reads program logic before validation; Mock uses a deterministic four-phase, one-program domain.

- [ ] **Step 4: Run the focused tests and confirm they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_traci_outputs.py tests/test_mock_bridge.py tests/test_runner_channel.py -q`

Expected: all selected tests pass and no rejected action is applied.

### Task 3: Generate Reproducible Acceptance Evidence

**Files:**
- Modify: `scripts/verify_ia_ib.py`
- Modify: `docs/ia-ib-final-verification.md` by running the verifier
- Test: `tests/test_validation_scripts.py`

**Interfaces:**
- Extends: `CheckResult` with real command evidence rather than inferred exit values.
- Produces: generated repository provenance, evidence axes, matrix artifact path, and execution/audit mode.

- [ ] **Step 1: Write failing report and exit-code provenance tests**

```python
def test_render_markdown_generates_evidence_axes():
    report = render_markdown(results, docker_status, provenance)
    assert "## Evidence axes" in report
    assert provenance["commit"] in report


def test_failed_command_preserves_real_exit_code(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 7, "", "bad"),
    )
    result = run_command_check("quality", [[sys.executable, "-m", "flake8"]])
    assert result.exit_code == 7
```

Assert a fresh render contains no hard-coded old commit and identifies the matrix evidence path and audit mode.

- [ ] **Step 2: Run the report tests and confirm they fail for missing generated evidence**

Run: `.venv/Scripts/python.exe -m pytest tests/test_validation_scripts.py -q`

Expected: evidence-axis, provenance, and real-exit-code assertions fail.

- [ ] **Step 3: Generate provenance and evidence from current facts**

```python
provenance = {
    "commit": git("rev-parse", "HEAD"),
    "dirty": bool(git("status", "--porcelain")),
    "matrix_evidence": str(matrix_root),
    "matrix_mode": "executed" if executed else "audited",
}
```

Render all evidence axes automatically. Do not claim Docker or second-machine success without their manifests.

- [ ] **Step 4: Run report tests and regenerate acceptance output**

Run: `.venv/Scripts/python.exe -m pytest tests/test_validation_scripts.py -q`

Expected: all selected tests pass; a second render is byte-for-byte stable except durations.

### Task 4: Final Verification and Commit

**Files:**
- Verify all modified production, test, documentation, and generated report files.

**Interfaces:**
- Consumes: all three completed tasks.
- Produces: one locally committed `main` state plus truthful external-validation status.

- [ ] **Step 1: Audit all existing 360 matrix artifacts with the hardened gate**

Run the matrix verifier against `output/verification/final-sharded` without creating duplicate run data.

Expected: 360 completed runs, every native final time reaches the configured horizon, zero failures.

- [ ] **Step 2: Run the complete repository verification**

Run: `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider`

Run: `.venv/Scripts/python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization`

Run: `.venv/Scripts/python.exe -m flake8 algorithms api cloud core engine experiments scenes scripts visualization --max-line-length=100`

Run: `git diff --check`

Expected: all commands exit 0.

- [ ] **Step 3: Review the final diff and preserve unrelated work**

Confirm `docs/reports/ia-ib-final-verification.md` remains unstaged and unchanged by this task.

- [ ] **Step 4: Commit the verified correction**

```text
fix: harden IA and IB acceptance evidence
```
