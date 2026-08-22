# Task 14 implementation report

## Outcome

- Implemented the frozen `360 normal + 180 disturbance = 540` formal matrix.
- Added deterministic, validated scene-network disturbance targets and complete
  disturbance identity in every run key and matrix manifest spec.
- Added fail-closed resume, immutable strict completed evidence, retry attempt
  chains, atomic matrix publications, and a non-blocking per-output-root OS lock.
- Added paired candidate-minus-baseline travel-time statistics, relative change,
  paired Cohen's dz, two-sided 95% t-CI, 40-unit improvement/worst-unit rules,
  strict integer-zero safety eligibility, and fixed-time fallback selection.
- Replaced formal CLI and analysis assumptions with profiles and the strict 540
  schema. Migrated the direct tuning, verifier, and split-job consumers only
  where they encoded the old `1.5 / 123 / 456 / 360-row` assumptions.

## TDD evidence

All commands used `D:\WorkPlace\challenge-cup\.worktrees\judge-final-release\.venv\Scripts\python.exe`.

1. Module availability
   - RED: `python -m pytest tests/test_formal_matrix.py -q --basetemp=.task14-red-module`
   - Output: `1 failed`; `experiments.matrix` was absent.
   - GREEN: same test with `.task14-green-module` -> `1 passed`.
2. Frozen factors, target selection, statistics, and selection
   - RED: `python -m pytest tests/test_formal_matrix.py -q --basetemp=.task14-red-contracts`
   - Output: `17 failed, 1 passed`; the requested APIs were absent.
   - GREEN: same test with `.task14-green-contracts` -> `18 passed`.
3. Resume, retry lineage, completed integrity, and lock
   - RED: same file with `.task14-red-resume` -> `4 failed, 18 passed`;
     `run_matrix` and its integrity/lock types were absent.
   - GREEN: `.task14-green-resume` -> `22 passed`.
4. Formal CLI profiles and strict analyzer
   - RED: `python -m pytest tests/test_formal_matrix.py tests/test_analyze_matrix.py -q --basetemp=.task14-red-cli-analysis`
   - Output: `8 failed, 25 passed`; profile APIs were absent and the legacy
     analyzer conflated disturbance rows with duplicate normal pairs.
   - GREEN: `.task14-green-cli-analysis` -> `33 passed`.
5. Direct-consumer migration
   - First affected run: tuning/validation/evidence/RunService -> `2 failed,
     150 passed`; failures were the explicit old `1.5 / 123 / 456` expectation
     and removed `--quick --tune` CLI test.
   - After minimal migration: `.task14-affected-green` -> `151 passed`.
6. Formal release auditor
   - RED: seconds-first RunSpec CSV audit -> `1 failed` because
     `expected_specs` was unsupported.
   - GREEN: four focused verifier/auditor tests -> `4 passed`.
7. Mutation/self-review fail-closed gaps
   - RED: duplicate disturbance coverage, outside-root attempt directory, and
     unique unexpected run key -> `3 failed`.
   - GREEN: `.task14-green-self-review` -> `3 passed`.
8. Task 13/14 seconds-first boundary
   - RED: a real sealed formal fixture with `steps=None` -> `1 failed` because
     `is_complete` multiplied `None * step_length`.
   - GREEN: seconds-first plus three explicit-step lifecycle checks -> `4 passed`.
9. Quick profile consistency
   - RED: quick default seed test -> `1 failed` (`18 != 54`).
   - GREEN: quick/smoke/formal profile group -> `3 passed`.

## Final verification

- Brief focused command:
  `python -m pytest tests/test_formal_matrix.py tests/test_analyze_matrix.py tests/test_experiments.py -q --basetemp=.task14-focused-final`
  -> `64 passed`.
- Expanded affected command:
  `python -m pytest tests/test_tuning.py tests/test_validation_scripts.py tests/test_evidence_contract.py tests/test_run_service.py -q --basetemp=.task14-affected-final`
  -> `152 passed`.
- Fresh combined final command after all fixes:
  `python -m pytest tests/test_formal_matrix.py tests/test_analyze_matrix.py tests/test_experiments.py tests/test_tuning.py tests/test_validation_scripts.py tests/test_evidence_contract.py tests/test_run_service.py -q --basetemp=.task14-final-pytest2`
  -> `218 passed, 1 warning in 109.93s`. The warning is the pre-existing denied
  `.pytest_cache` write; isolated `--basetemp` outputs and test results are valid.
- `python -m compileall -q experiments scripts tests` -> exit 0.
- `python -m flake8 ... --ignore=E501,E131,W391,W503` over every modified Python
  file -> exit 0. Ignored rules are repository-existing line-layout/style noise;
  semantic/import errors were not ignored.
- `git diff --check` -> exit 0 after removing the one added trailing blank line.
- No real 540-run SUMO execution was performed, as required.

## Self-review

- Plan alignment: all six frozen rulings are represented in executable tests.
- Disk truth: completed attempts call Task 13 `is_complete` with the exact
  RunRequest and load canonical disk summaries; in-memory summaries are not
  trusted. Completed evidence is never written by matrix resume.
- Identity: matrix digest covers ordered canonical specs only; attempt mutation
  does not alter the frozen design digest. JSON writes reject NaN.
- Atomicity: manifest/results/CSV use same-directory UUID temporary files,
  flush, `fsync`, and replace. Duplicate keys are rejected before root creation,
  manifest writing, or RunService construction.
- Safety: only collision/red-light/illegal-transition are hard gates; observed
  harsh-braking/teleport/potential-conflict remain reported but non-gating.
- Review skill deviation: the requested-review skill normally dispatches a
  reviewer subagent, but the Task14 contract explicitly prohibited subagents;
  the main writer performed the template's plan/code/testing/production audit.
- Known limitation: attempts are recorded atomically after RunService returns;
  a process/power loss between RunService allocation and return can leave an
  unreferenced run directory. The full frozen spec manifest is still persisted
  before service construction, completed evidence remains immutable, and the
  next resume safely retries the missing spec. RunService was not expanded with
  caller-supplied preallocated IDs because the brief did not require crash-level
  pre-registration.

## Scope and protection audit

- `progress.md` was already modified by the coordinator and was not edited or
  staged by this writer.
- `赛题资料.7z` and `data/intersection_data` were read-only and never modified,
  deleted, repacked, or staged.
- Scratch/basetemp directories were not staged.
- Staging uses explicit file names only; no `git add -A` or `git add .`.

## Pre-review correction

- Controller pre-review reproduced one strict style failure with
  `python -m flake8 <all Task14 changed Python files> --max-line-length=100`:
  `experiments/runner.py:129:20 E131 continuation line unaligned for hanging
  indent`.
- Corrected only the `help=` keyword indentation in the existing
  `ArgumentParser.add_argument` call; behavior and interfaces are unchanged.
- Re-ran the exact strict flake8 command -> exit 0 with no output.
- Re-ran the controller-focused equivalent:
  `python -m pytest tests/test_formal_matrix.py tests/test_analyze_matrix.py
  tests/test_experiments.py -q --basetemp=.task14-prereview-focused`
  -> `65 passed, 1 warning in 17.47s`. The warning remains the pre-existing
  denied `.pytest_cache` write; the isolated basetemp run passed.

## Fix round 1: sealed formal analysis and immutable retry lineage

### RED evidence

1. Completed manifest state and retry uniqueness
   - `python -m pytest tests/test_formal_matrix.py -q -k
     "manifest_completed_attempt_never_degrades_into_retry or
     retry_rejects_reused_run_id" --basetemp=.task14-fix1-red-resume`
     -> `4 failed`: missing run directory, missing status, non-completed disk
     status, and a reused retry ID all degraded into retry/append behavior.
2. Exact disturbance safety identity
   - `python -m pytest tests/test_formal_matrix.py -q -k
     "candidate_safety" --basetemp=.task14-fix1-red-safety`
     -> `7 failed, 5 passed`: flow, seed, begin/end, target, intensity, and
     run-key mutations incorrectly passed the safety gate.
   - Fractional seed follow-up in `.task14-fix1-red-fractional-seed2`
     -> `1 failed`: seed `42.5` was truncated to `42`.
3. Sealed analysis and strata
   - `python -m pytest tests/test_analyze_matrix.py -q -k
     "accepts_only or swapped_identity or relative_run"
     --basetemp=.task14-fix1-red-sealed-analysis`
     -> `6 failed`: descriptive output mixed normal/disturbance samples, and
     swapped key/run ID, forged metric/safety, and escaped run directory were
     accepted.
   - Explicit normalized parent traversal in `.task14-fix1-red-parent-path2`
     -> `1 failed` because `runs/../runs/...` was accepted.
4. IA/IB canonical evidence binding
   - `python -m pytest tests/test_validation_scripts.py -q -k
     "seconds_first_formal_run_spec or swapped_key_or_forged"
     --basetemp=.task14-fix1-red-iaib`
     -> `4 failed`: the old auditor did not consume the shared sealed formal
     contract and trusted submitted metric/safety values.
5. Whole-manifest lineage integrity
   - `python -m pytest tests/test_formal_matrix.py -q -k
     "entire_attempt_lineage or cross_spec_duplicate"
     --basetemp=.task14-fix1-red-global-lineage`
     -> `4 failed`: duplicate history, forged parent, historical disk-status
     mismatch, and cross-spec duplicate run IDs were not rejected globally
     before service invocation.
   - Live cross-spec duplicate ID in `.task14-fix1-red-live-global` -> `1 failed`.
   - Live non-terminal result in `.task14-fix1-red-live-terminal` -> `1 failed`.

### GREEN implementation and evidence

- `experiments/matrix.py`
  - validates every persisted attempt object, contained canonical directory,
    disk status, global run-ID/directory uniqueness, and exact parent lineage
    before constructing/calling a service;
  - preserves completed manifest state and raises
    `CorruptCompletedRunError` for missing/mismatched/unsealed completed disk
    evidence without appending attempts or rewriting the manifest;
  - accepts retries only after canonical retryable terminal states and requires
    each live result to have a globally new ID/directory and terminal disk status;
  - publishes steps provenance and canonical algorithm parameters in result rows;
  - adds one shared `load_sealed_matrix_rows` boundary that verifies the sibling
    matrix manifest, full `run_key -> RunSpec` row identity, latest attempt,
    controlled path, exact `RunRequest`, strict completion, and the canonical
    `EvidenceReader.load_summary()` metrics/safety values.
- `scripts/analyze_matrix.py` consumes only canonical sealed rows. Normal
  descriptive statistics are exactly 120 rows per algorithm; disturbance
  resilience is emitted independently for each of three kinds with 20 rows per
  algorithm/kind. Paired selection continues to use normal rows only.
- `scripts/verify_ia_ib.py` uses the same shared sealed-row boundary whenever
  `expected_specs` is supplied; the legacy explicit-request audit remains only
  for its non-formal compatibility caller.
- `experiments/statistics.py` requires the exact 20-scene x 3-kind candidate
  disturbance identities, including run key, flow 1.0, integer seed 42,
  duration/warmup, target, window, and intensity.
- Focused GREEN checkpoints:
  - retry/corruption group -> `7 passed`;
  - global lineage group -> `10 passed`, then missing-status coverage remained green;
  - exact safety group -> `15 passed`, fractional-seed follow-up -> `1 passed`;
  - analyzer full group -> `12 passed` before the two final path/run-dir cases;
  - IA/IB focused group -> `4 passed`;
  - live-result focused groups -> `2 passed` each.

### Final verification and self-review

- Fresh covering command after every follow-up fix:
  `python -m pytest tests/test_formal_matrix.py tests/test_analyze_matrix.py
  tests/test_experiments.py tests/test_validation_scripts.py -q
  --basetemp=.task14-fix1-final-covering`
  -> `118 passed, 1 warning in 80.45s`. The warning is the existing denied
  repository `.pytest_cache`; the isolated basetemp and all tests passed.
- Strict changed-file flake8 with `--max-line-length=100` -> exit 0, no output.
- `python -m compileall -q experiments scripts tests` -> exit 0.
- `git diff --check` -> exit 0 (only Git line-ending notices).
- Tests exercise sealed-reader boundaries with controlled summaries so the
  540-row analyzer suite stays bounded; production calls the Task 13 strict
  `is_complete(exact_request)` and `EvidenceReader.load_summary()` paths without
  a CSV fallback.
- Existing failed-attempt bytes are snapshotted in the retry test and remain
  identical after the next attempt. Corrupt completed tests also assert service
  zero calls and byte-identical manifest contents.
- No real 540-run SUMO execution was performed. `progress.md`, `赛题资料.7z`,
  `data/intersection_data`, and all scratch/basetemp directories remain outside
  the explicit staging set.
