# Global Task 18 Report: Native Judge Launcher

Date: 2026-08-24 08:46 Asia/Shanghai

## Status

Global Task 18 is complete. Implementation, real smoke, browser acceptance, current regression
gates, the final scoped Terra/Sol fix re-review, the exact implementation commit, and its
post-commit verification are recorded below. Numbered items 18.1-18.6 are subtasks of Global
Task 18, not new global tasks.

18.1 launcher contract and project-interpreter selection: implemented and verified.
18.2 bounded port selection, SUMO/dependency/assets/output preflight, and atomic diagnostics:
implemented and verified, including the protected diagnostics-path fix round.
18.3 health-gated browser and single-app composition: implemented and verified.
18.4 PowerShell/BAT wrappers and deployment documentation: implemented and verified.
18.5 real lifecycle, native GUI, browser, regression, and protected-input verification:
implemented and verified through the evidence recorded below.
18.6 dual review, ledger, final gates, exact implementation commit, and post-commit
verification: complete; Terra and Sol found no open Critical or Important finding.

## Verification Evidence

- Fresh launcher test after all review fixes: 47 passed in 4.39 seconds.
- Formatting-only follow-up (`test_judge_launcher.py`, `test_seed.py`,
  `test_run_lifecycle.py`): 83 passed in 21.15 seconds; targeted flake8 exit code 0.
- Current affected suite (`test_judge_launcher.py`, `test_judge_api.py`,
  `test_api_contract.py`, `test_run_service.py`, `test_run_lifecycle.py`): 151 passed in
  122.82 seconds, exit code 0.
- Current full Python suite: 951 passed in 582.53 seconds, exit code 0.
- Web `npm ci`: exit code 0. npm reported the existing deprecated `recharts@2` notice and four
  dependency audit findings (one moderate, three high); these remain dependency/release work,
  not a silent clean claim.
- Web `npm run typecheck`: exit code 0.
- Web `npm run build`: exit code 0; Vite transformed 2388 modules. The existing bundle-size
  warning remains because the main JavaScript chunk is 544.65 kB after minification.
- Web Playwright Chromium gate: 15 passed in 7.4 seconds, exit code 0. Expected disconnected-
  state proxy `ECONNREFUSED` messages and `NO_COLOR`/`FORCE_COLOR` notices were present.
- Final targeted `compileall`, flake8 with `--ignore=E501,W503`, staged diff check, and
  protected-path checks: exit code 0 after correcting two whitespace-only flake8 findings.

## Real Smoke

Headless smoke used the repository `.venv`, SUMO 1.27.1, port 8775, and diagnostics
`output/evidence/judge-launch/launcher.json`. `/api/health` returned `ok`; run
`dc8f3a8b5260` reached `completed`; Ctrl+C produced diagnostics `status=stopped`,
`health.status=pass`, `reason=server stopped`; no launcher-owned Python/SUMO process remained.

Native GUI smoke used `sumo-gui.exe` 1.27.1 on port 8778. Run `cb0eaa2916d5` was observed in
`running`; `POST /api/runs/cb0eaa2916d5/native-gui` returned HTTP 200 and
`{"status":"shown"}`. The exact SUMO child PID was observed from the run command line, and
after shutdown no launcher-owned Python/SUMO process remained. The compact machine-readable
record is `output/evidence/judge-launch/native-smoke.json` (runtime evidence is not staged).

## Codex In-App Browser

The local console was opened only after launcher health passed at `http://127.0.0.1:8779/`.
The Simulation, Comparison, History, and Scene views were inspected through the in-app
browser. Simulation exposed 20 scenes, 3 formal algorithms, duration/warmup/disturbance and
run controls; Comparison and History clearly described sealed individual-run evidence; Scene
reported `All manifests pass` with source files and SHA-256. The Simulation tab was marked as
the deliverable.

## Protection Invariants

- `赛题资料.7z` SHA-256:
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`.
- `data/intersection_data`: 163 tracked files and 232 files on disk.
- Protected worktree and index diffs: empty.
- Scratch directories, historical evidence, `web/node_modules`, the protected archive, and
  official scene data were not cleaned or staged.

## Review Verdicts

Terra standards review initially found lifecycle and diagnostics issues. Its final scoped fix
re-review found the premature-closeout inconsistency ADDRESSED, the diagnostics and cleanup
changes sound, and no new Critical or Important breakage.

Sol specification review found the protected diagnostics-path Critical, the pre-start cleanup
Important, and the same premature-closeout inconsistency. Its final scoped fix re-review marked
all three findings ADDRESSED with no new Critical or Important breakage. Both reviewers recorded
the report file-list wording below as a Minor; that wording is corrected here. Their CLEAN verdicts
cover the scoped fix diff. The controller independently completed the full, frontend, runtime,
post-commit, and protection gates recorded in this report.

## Known Limitations and Boundaries

Docker live build/run, second-machine reproduction, the 540-run formal matrix, final release
packaging, judge-facing stale-claim cleanup, and PPT/Word/video materials remain deferred to
Global Tasks 19-24. Task 18 evidence intentionally does not present the individual smoke runs
as formal matrix conclusions.

## Fix Round — 2026-08-24

### Findings addressed

- Critical: an arbitrary `--diagnostics` target reached `DiagnosticsWriter` and its atomic
  `os.replace` before any immutable-input protection. The launcher now canonicalizes the
  requested path before writer construction and rejects the repository archive or any target
  resolving inside `data/intersection_data`, including `..` traversal and a Windows directory
  junction. Legal repository-relative and absolute targets remain writable.
- Important: a `RunService` created by `build_application` leaked when `create_app` failed,
  and `server.run()` cleanup covered neither ordinary failures nor `BaseException` exits.
  Application construction now shuts down the created service on every `BaseException`.
  Server exit always cancels and joins readiness and calls `service.shutdown(wait=True)`;
  diagnostics reach a terminal state, healthy Ctrl+C remains `stopped`, and `SystemExit`
  retains its original exit code and propagation semantics.
- Follow-up Important: Uvicorn config/server construction still used an `Exception`-only
  cleanup handler. `SystemExit` or `KeyboardInterrupt` from `server_factory` now shuts down
  the already-created service, records failed terminal diagnostics, and re-raises the exact
  original `BaseException` without changing its exit semantics.
- Closeout consistency: `progress.md` was first restored to the truthful pending state and is
  marked complete only by the closeout after all controller gates below passed.

### RED evidence

- The first diagnostics command using the configured `output/tmp` basetemp stopped in fixture
  setup because of its pre-existing ACL, so it was not counted as behavioral RED evidence.
  Re-running with an external `--basetemp` produced the valid RED:
  `.\.venv\Scripts\python.exe -m pytest --basetemp <system-temp> tests/test_judge_launcher.py::test_run_server_rejects_protected_diagnostics_targets_before_writing -q`
  — 3 failed because no protected-target rejection was emitted and the old writer path was
  reached.
- `.\.venv\Scripts\python.exe -m pytest --basetemp <system-temp> tests/test_judge_launcher.py::test_build_application_shuts_down_created_service_when_create_app_fails -q`
  — 1 failed: observed shutdown waits `[]`, expected `[True]`.
- Focused `server.run()` exception, `SystemExit`, healthy `KeyboardInterrupt`, and early-return
  command — 4 failed: every owned service observed shutdown waits `[]`, expected `[True]`.
- `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp <system-temp> tests/test_judge_launcher.py::test_run_server_cleans_service_and_preserves_baseexception_from_server_factory -q`
  — 2 failed: both Uvicorn-construction `BaseException` branches observed shutdown waits `[]`,
  expected `[True]`; diagnostics had not reached the required failed terminal state.

### GREEN evidence

- Protected archive/data/traversal focused command: 3 passed.
- `build_application → create_app` focused command: 1 passed.
- `server.run()` lifecycle focused command, including the existing healthy-launch case:
  5 passed.
- Junction plus legal relative/absolute diagnostics command: 3 passed.
- `.\.venv\Scripts\python.exe -m pytest --basetemp <system-temp> tests/test_judge_launcher.py -q`:
  45 passed; the only warning was the pre-existing repository `.pytest_cache` ACL.
- Fresh final command with `-p no:cacheprovider` and an external `--basetemp`: 45 passed in
  3.26 seconds with no warning.
- Uvicorn-construction `BaseException` focused GREEN: 2 passed in 0.16 seconds.
- Fresh launcher file after the construction follow-up, with `-p no:cacheprovider` and an
  external `--basetemp`: 47 passed in 4.39 seconds.
- Formatting-only flake8 follow-up changed only two blank lines; the exact targeted flake8
  command then passed, and the related launcher/lifecycle/seed command passed 83 tests.
- `.\.venv\Scripts\python.exe -m compileall -q scripts/run_judge.py`: exit code 0.
- `git diff --check -- scripts/run_judge.py tests/test_judge_launcher.py <Task-18-report>`:
  exit code 0; Git emitted only its configured LF-to-CRLF notices.
- Protected paths retained empty worktree/index diffs. The archive SHA-256 remained
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`, and
  `data/intersection_data` remained 232 files on disk.

### Files and concerns

- Changed in this fix round: `scripts/run_judge.py`, `tests/test_judge_launcher.py`,
  `progress.md`, and this report.
- Terra/Sol scoped fix re-review is CLEAN. The controller then ran the current 151-test affected
  suite, 951-test full suite, frontend typecheck/build/Playwright gates, exact scoped staging,
  implementation commit, and post-commit verification.

## Exact Commit and Post-Commit Verification

- Exact implementation evidence HEAD: `6a149ef5561d3f365cd519577454c4e430e91891`
  (`feat: add native judge launcher`). Its 11-path allowlist contains only the Task 18 brief,
  plan, launcher/wrappers, required lifecycle support, tests, and minimal README/deployment docs.
- Post-commit focused suite (`test_judge_launcher.py`, `test_judge_api.py`,
  `test_run_lifecycle.py`): 90 passed in 42.18 seconds, exit code 0.
- Post-commit real PowerShell smoke used port 8785, project Python 3.12.13, headless SUMO
  1.27.1, and `output/evidence/judge-launch/postcommit-launcher-6a149ef.json`. `/api/health`
  returned `{"status":"ok","run_workers":1}`; after Ctrl+C diagnostics were `stopped`, health
  was `pass`, reason was `server stopped`, server PID 28560 was gone, and port 8785 was closed.
  The PTY wrapper reported exit 1 because the console interrupt also interrupted its PowerShell
  host; as with the earlier native smoke, terminal diagnostics and owned-process cleanup are the
  authoritative launcher lifecycle evidence.
- Post-commit Web production build/typecheck: exit code 0, 2388 modules transformed; the known
  544.65 kB chunk warning remains.
- Post-commit targeted compileall, flake8, `git diff --check HEAD^..HEAD`, empty index check,
  protected archive hash, official-data counts, and owned-process check all passed. The first
  process query matched its own command line; the corrected query excluded the current checker
  PID and found zero launcher-owned matches, with the exact server PID absent and port closed.
- Reproducibility ruling: a tracked report cannot embed the hash of the commit that contains
  itself because changing the hash text changes that commit. Therefore this report freezes the
  exact implementation HEAD verified above; the following docs-only report/ledger closeout hash
  is authoritative in Git history and is separately checked for diff hygiene and protected-input
  invariants.

## Closeout

Task 18 implementation was committed by the exact 11-path allowlist, and this report plus
`progress.md` form the separate docs-only closeout. Runtime evidence remains ignored and unstaged.
Global Tasks 19-24 remain not started by this closeout.
