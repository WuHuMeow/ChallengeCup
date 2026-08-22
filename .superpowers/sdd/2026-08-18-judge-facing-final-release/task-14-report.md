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
