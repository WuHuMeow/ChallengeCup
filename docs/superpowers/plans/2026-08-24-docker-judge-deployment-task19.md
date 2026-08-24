# Task 19 Docker Judge Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Each implementation task also requires `superpowers:test-driven-development`; the closeout requires `superpowers:verification-before-completion`.

**Goal:** Package the existing judge-facing FastAPI/Web/SUMO application as reproducible Linux amd64 headless and optional Xvfb GUI images, while preserving the native launcher as the primary judge route and recording unavailable Docker execution honestly as `not_run`.

**Architecture:** Keep `scripts/run_judge.py` as the only application composition root. Build Web assets in a pinned Node 20 stage, resolve Python/SUMO wheels into a hash-locked Python 3.12 environment, and run the final image as UID/GID 10001 with `/app/output` as its only persistent writable path. Compose owns one default headless service and one explicit `gui` profile. A read-only detector writes the stable evidence schema; a separately gated live verifier owns invocation-scoped Docker mutations and may clean up only exact resources that carry the current invocation label.

**Tech Stack:** Python 3.12, SUMO/TraCI/sumolib 1.27.1, FastAPI, React 18, TypeScript 5.6, Node.js 20, Docker/Compose, Xvfb, pytest, PyYAML, uv, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-24-docker-judge-deployment-design.md`

## Global Constraints

- Work only in `D:\WorkPlace\challenge-cup\.worktrees\judge-final-release` on `codex/judge-final-release`.
- The design baseline is commit `68e3401936261ca2372cb5636966640a770d3d41`; do not silently weaken it during implementation.
- Never modify, delete, move, or stage `赛题资料.7z` or tracked files under
  `data/intersection_data`. The archive and runtime evidence must never enter the Docker build
  context. The tracked official scene data is intentionally read into the context and copied
  unchanged into the read-only image because the judge runtime needs it; this read-only inclusion
  grants no authority to mutate the source, and hash/count/diff gates run before and after.
- Preserve archive SHA-256 `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F` and the official-data baseline of 163 tracked files / 232 files on disk.
- Runtime JSON, Docker tar files, Docker resources, `output/`, scratch directories, `web/node_modules`, Playwright reports, and pre-existing user files are never staged.
- The controller currently has neither a Docker CLI nor WSL. Do not install either and do not claim live build/run/save-load/GUI checks passed. The expected controller result is `not_run` with reason `docker_cli_unavailable`.
- Never run `docker system prune`, `docker volume prune`, `docker compose down -v`, broad filters, or removal against resources not proven to have both the exact invocation name and current invocation label.
- Use one implementation writer at a time. The controller owns exact staging and commits. Review agents are read-only unless explicitly reassigned a bounded test-first fix.
- Before every commit, run `git diff --check`, inspect `git diff --cached --name-status`, and require both protected worktree and index diffs to be empty.
- A RED step is valid only when the new assertion fails for the intended missing behavior. Import errors, syntax errors, fixture failures, and unrelated failures do not count.
- A GREEN claim requires rerunning the exact RED command and the named adjacent regression command from that task.
- Do not mark Task 19 `complete` before final verification and both independent reviews are
  CLEAN. The only earlier ledger update allowed is Task 19.F Step 6's explicit
  `verification_pending` state.

## SDD Routing and Commit Boundaries

| Implementation unit | Single writer | Independent review | Commit boundary |
|---|---|---|---|
| 19.A launcher `container-gui` | Terra | independent Terra standards reviewer | launcher source + launcher tests |
| 19.B detector/schema | Terra | Sol specification | detector source + detector tests |
| 19.C live verifier safety | Sol | Terra security/maintainability | verifier source + verifier tests |
| 19.D locks/headless/Compose | Terra | Sol specification | Docker configuration + static tests |
| 19.E GUI/ignore/docs | Terra | independent Terra standards and Sol specification reviewers | GUI/config/docs + static tests |
| 19.F closeout | controller | Terra and Sol read-only final reviews | report/progress only after implementation commit |

Only Terra and Sol are available for this project. The named model is a preferred routing choice,
not permission for concurrent writes. Writer and reviewer must be distinct agents even when both
use Terra. If a named route is temporarily unavailable, the controller may choose the other
available model without changing interfaces, acceptance criteria, or review independence.

---

## Task 19.0: Freeze the brief and baseline evidence

**Files:**

- Create: `.superpowers/sdd/2026-08-18-judge-facing-final-release/task-19-brief.md`
- Read: `docs/superpowers/specs/2026-08-24-docker-judge-deployment-design.md`
- Read: `docs/superpowers/plans/2026-08-18-judge-facing-final-release.md:1032`

- [ ] **Step 1: Record the implementation contract**

Write the exact Task 19 purpose, allowed tracked paths, protected inputs, controller limitation, evidence vocabulary, destructive-command prohibitions, TDD commands, reviewers, and stop conditions. State explicitly that the native launcher remains primary and the Docker route is secondary.
Reference the design by its real path
`docs/superpowers/specs/2026-08-24-docker-judge-deployment-design.md`; do not refer to it as being
in the plan directory. For every RED, the brief/report template requires the failing test nodeid,
the new assertion being exercised, the observed failure reason, and an explicit statement that
collection, import, syntax, and fixture setup succeeded.

- [ ] **Step 2: Capture a read-only baseline**

Run:

```powershell
git rev-parse HEAD
git status --short --untracked-files=no
git diff --name-only -- "赛题资料.7z" data/intersection_data
git diff --cached --name-only -- "赛题资料.7z" data/intersection_data
Get-FileHash -Algorithm SHA256 "赛题资料.7z"
git ls-files data/intersection_data | Measure-Object -Line
(Get-ChildItem data/intersection_data -Recurse -File | Measure-Object).Count
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
& $Py -c "import sys; print(sys.executable); print(sys.version)"
uv --version
Get-Command docker -ErrorAction SilentlyContinue
if (Get-Command wsl.exe -ErrorAction SilentlyContinue) { wsl.exe --status } else { "wsl_cli_unavailable" }
```

Expected: HEAD contains design commit `68e3401` plus this committed plan; record its exact hash in
the brief. Tracked status is clean; both protected diffs are empty; archive hash and counts equal
the frozen values; the Docker CLI is absent and `wsl.exe --status` confirms that no Linux
distribution/runtime is installed.

The interpreter must be the repository `.venv` CPython 3.12.13 and `uv` must be available with
its version recorded. Every later PowerShell command block resolves `$Py` again instead of using
a global `python`. Every pytest invocation uses a specifically named external base directory under
`<repository-drive>:\Temp`: it stays outside the worktree but on the same drive as official scene
inputs, because `scenes.variant` must generate relative SUMO paths. Never use C-drive system TEMP
for this D-drive worktree, and never use repository `output/tmp`, whose inherited ACL is known to
produce invalid `WinError 5` fixture failures. If `uv` is unavailable, dependency locking is a
recorded blocker and hashes must not be written manually.

- [ ] **Step 3: Confirm the implementation allowlist**

The only prospective tracked paths are the ones listed by the design plus this plan, the Task 19
brief/report, minimal deployment documentation, and
`.superpowers/sdd/2026-08-18-judge-facing-final-release/progress.md`. Stop if any unrelated tracked
change appears.

- [ ] **Step 4: Commit the ignored brief by exact forced path**

`.superpowers/` is ignored for scratch containment, but the historical Task 18 brief/report and
the SDD progress ledger are explicitly tracked release-process records. Force-add only the new
brief, verify the one-path index, then commit:

```powershell
git add -f -- .superpowers/sdd/2026-08-18-judge-facing-final-release/task-19-brief.md
git diff --cached --name-status
git diff --cached --check
git diff --cached --name-only -- "赛题资料.7z" data/intersection_data
git commit -m "docs: record Task 19 implementation brief"
```

---

## Task 19.A: Add the Linux-only `container-gui` launcher mode

**Files:**

- Modify: `tests/test_judge_launcher.py`
- Modify: `scripts/run_judge.py`

- [ ] **Step 1: Add argument and runtime-policy tests**

Add focused tests with these contracts:

```python
def test_parse_args_accepts_container_gui() -> None:
    args = run_judge.parse_args(["--gui-mode", "container-gui", "--no-browser"])
    assert args.gui_mode == "container-gui"


def test_container_gui_selects_sumo_gui_without_native_focus(tmp_path: Path) -> None:
    selection = run_judge.select_runtime(
        "container-gui",
        platform_name="linux",
        environ={"DISPLAY": ":99"},
        sumo=None,
        sumo_gui=tmp_path / "sumo-gui",
    )
    assert selection == run_judge.RuntimeSelection(
        "container-gui", tmp_path / "sumo-gui", False
    )


@pytest.mark.parametrize(
    ("platform_name", "environ", "sumo_gui", "message"),
    [
        ("win32", {"DISPLAY": ":99"}, Path("sumo-gui"), "non-Windows"),
        ("linux", {}, Path("sumo-gui"), "DISPLAY"),
        ("linux", {"DISPLAY": ":99"}, None, "sumo-gui"),
    ],
)
def test_container_gui_rejects_invalid_runtime(
    platform_name, environ, sumo_gui, message
) -> None:
    with pytest.raises(run_judge.LauncherError, match=message):
        run_judge.select_runtime(
            "container-gui",
            platform_name=platform_name,
            environ=environ,
            sumo=None,
            sumo_gui=sumo_gui,
        )
```

Also extend the preflight/diagnostics assertion so the recorded mode is `container-gui` and `native_gui` is `false`; assert `RunnerRegistry.show_native_gui()` remains disabled.

- [ ] **Step 2: Run RED and inspect the reason**

Run:

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-launcher-red"
& $Py -m pytest tests/test_judge_launcher.py -q --basetemp=$BaseTemp
```

Expected: only the new cases fail because argparse and `select_runtime()` do not yet accept `container-gui`. If an existing test fails, stop and diagnose it separately.

- [ ] **Step 3: Make the smallest launcher change**

Change the parser choices and inject the environment into the pure selection function:

```python
def select_runtime(
    gui_mode: str,
    *,
    platform_name: str = sys.platform,
    environ: Mapping[str, str] | None = None,
    sumo: Path | None,
    sumo_gui: Path | None,
) -> RuntimeSelection:
    environment = os.environ if environ is None else environ
    if gui_mode == "container-gui":
        if platform_name == "win32":
            raise LauncherError("container GUI requires a non-Windows platform")
        if not environment.get("DISPLAY", "").strip():
            raise LauncherError("container GUI requires DISPLAY")
        if sumo_gui is None:
            raise LauncherError("container GUI requires sumo-gui")
        return RuntimeSelection("container-gui", Path(sumo_gui), False)
```

Keep existing `auto`, `native`, and `headless` ordering and messages unchanged. Pass `os.environ` from preflight; do not add Linux native-window focus behavior.

- [ ] **Step 4: Run GREEN and adjacent regression**

Run:

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-launcher-green"
& $Py -m pytest tests/test_judge_launcher.py -q --basetemp=$BaseTemp
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-launcher-adjacent"
& $Py -m pytest tests/test_api.py tests/test_run_service.py tests/test_runner_channel.py -q --basetemp=$BaseTemp
& $Py scripts/run_judge.py --help
```

Expected: all tests pass and help lists `container-gui` without changing wrapper behavior.

- [ ] **Step 5: Review and commit the launcher unit**

Ask Terra to review the launcher diff for policy regressions and disabled native-focus behavior. Fix Critical/Important findings test-first, rerun Step 4, then stage only:

```powershell
git add -- scripts/run_judge.py tests/test_judge_launcher.py
git diff --cached --name-status
git diff --cached --check
git commit -m "feat: add container GUI launcher mode"
```

---

## Task 19.B: Implement the non-mutating Docker detector and evidence schema

**Files:**

- Create: `scripts/release/docker_status.py`
- Create: `tests/test_docker_release.py`

- [ ] **Step 1: Add an importable interface shell, then write schema and unavailable-state tests**

Create `docker_status.py` with only the public constants and function signatures used by the
tests; each unimplemented function raises `NotImplementedError`. This is interface scaffolding,
not a behavioral implementation, and prevents an import/collection error from being misreported
as a valid RED.

Create tests for:

- `new_evidence()` returning `schema == "judge-docker-evidence.v1"` and every phase in `not_run`;
- missing CLI producing overall `not_run` / `docker_cli_unavailable` without calling `subprocess.run`;
- present CLI plus unreachable daemon producing `not_run` / `docker_daemon_unavailable`;
- CLI and daemon both available but no gated verifier evidence producing overall `not_run` /
  `live_verification_not_run`, with `cli.status == "pass"`, `daemon.status == "pass"`, and every
  live phase still `not_run`; capability detection alone can never produce overall `pass`;
- phase/status validation rejecting booleans, unknown values, a `pass` without every required headless phase, a non-empty collision inventory, missing exported evidence, or a non-empty final owned-resource inventory;
- sanitized commands containing argv lists but no environment dump, username, or absolute repository path;
- atomic JSON replacement preserving the previous file if `os.replace` fails.
- output resolution rejecting the exact archive, every official-data descendant, `..` traversal
  into either protected input, and a Windows junction/symlink that reparses into official data;
- both relative and absolute legal JSON outputs resolving successfully before an atomic writer is
  constructed.

Use an injected command runner rather than invoking real Docker in unit tests:

```python
def test_detector_marks_missing_cli_not_run(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(docker_status.shutil, "which", lambda _name: None)
    payload = docker_status.detect(tmp_path)
    assert payload["status"] == "not_run"
    assert payload["reason"] == "docker_cli_unavailable"
    assert payload["cli"]["status"] == "not_run"
    docker_status.validate_evidence(payload)
```

- [ ] **Step 2: Run RED**

Run:

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-status-red"
& $Py -m pytest tests/test_docker_release.py -q --basetemp=$BaseTemp
```

Expected: tests collect successfully and fail on `NotImplementedError` or a wrong returned
contract. Retain one behavioral RED before implementing each validator branch; an import,
syntax, or fixture error is invalid and must be fixed before continuing.

- [ ] **Step 3: Implement pure builders and strict validation**

Define constants for schema, statuses, phases, reasons, and platform target. Keep evidence data relative and bounded. Representative interface:

```python
SCHEMA = "judge-docker-evidence.v1"
VALID_STATUSES = frozenset({"pass", "fail", "not_run"})
PHASES = (
    "static_contract",
    "headless_build",
    "headless_health",
    "headless_smoke",
    "save_load",
    "gui_build",
    "gui_smoke",
    "cleanup",
)


def detect(
    repo_root: Path,
    *,
    which: Callable[[str], str | None] = shutil.which,
    command_runner: CommandRunner = run_command,
) -> dict[str, object]:
    """Detect Docker capability without changing Docker state."""
```

The only detector subprocesses allowed are version/info queries. Bound stdout/stderr details, hash full streams, reject NaN, and use a sibling `.tmp` file plus `os.replace()` for atomic output.

Implement `resolve_protected_output_path(repo_root, requested)` in `docker_status.py`. Resolve the
repository root, requested candidate, archive, and official-data root canonically; reject the
archive, the official-data root, every descendant, traversal that resolves there, and
junction/symlink reparsing there. Catch resolution errors and fail closed. Both the detector CLI
and `docker_verify.py` must call this shared function before creating a directory, temporary file,
tar path, or atomic writer.

- [ ] **Step 4: Add and verify the CLI entrypoint**

Support:

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
& $Py scripts/release/docker_status.py --repo-root . --output output/evidence/docker/docker-status.json
```

Exit 0 for valid `pass` or `not_run` evidence and nonzero for invalid schema or real `fail`. On this controller expect overall `not_run`, reason `docker_cli_unavailable`, and all live phases `not_run`.

- [ ] **Step 5: Run GREEN and adjacent preflight tests**

Run:

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-status-green"
& $Py -m pytest tests/test_docker_release.py tests/test_release_preflight.py tests/test_validation_scripts.py -q --basetemp=$BaseTemp
& $Py scripts/release/docker_status.py --repo-root . --output output/evidence/docker/docker-status.json
```

Inspect the generated JSON but do not stage it. Ask Sol to review schema classification and privacy rules. Fix Critical/Important findings test-first.

- [ ] **Step 6: Commit the detector unit**

```powershell
git add -- scripts/release/docker_status.py tests/test_docker_release.py
git diff --cached --name-status
git diff --cached --check
git commit -m "feat: add Docker release status evidence"
```

---

## Task 19.C: Implement the explicitly gated live verifier

**Files:**

- Modify: `tests/test_docker_release.py`
- Create: `scripts/release/docker_verify.py`

- [ ] **Step 1: Add an importable verifier interface shell, then write invocation-identity and fail-closed RED tests**

Create `docker_verify.py` with immutable public type/function signatures and
`NotImplementedError` bodies. It must not execute Docker at import time. This allows the tests to
reach the intended behavioral assertions before any workflow implementation exists.

Cover these pure contracts before any workflow code:

```python
def test_invocation_resources_are_unique_and_namespaced() -> None:
    first = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    second = docker_verify.InvocationResources.from_id("001122334455")
    assert first.compose_project == "ca-mp-task19-a1b2c3d4e5f6"
    assert first.label == "io.challengecup.task19.invocation=a1b2c3d4e5f6"
    assert first.headless_image != second.headless_image
    assert first.imported_image.endswith("-imported:local")


def test_collision_preflight_rejects_same_name_with_wrong_label(fake_runner) -> None:
    fake_runner.inventory_result = [{"name": "expected", "labels": {}}]
    with pytest.raises(docker_verify.SafetyError, match="collision"):
        docker_verify.assert_no_name_collisions(fake_runner, expected={"expected"})


def test_cleanup_requires_exact_name_and_invocation_label(fake_runner) -> None:
    candidate = {"name": "expected", "labels": {"other": "value"}}
    assert docker_verify.is_owned(candidate, name="expected", invocation_id="a1b2c3d4e5f6") is False
```

Also test that `main([])` and `main(["--repo-root", "."])` refuse mutation because `--execute-live` is absent. Test `--evidence-root` with the same
archive/data/traversal/junction and legal relative/absolute cases as the detector. Assert rejection
occurs before the command runner, directory creation, tar creation, or writer construction.

- [ ] **Step 2: Run the safety RED subset**

Run:

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-verifier-red"
& $Py -m pytest tests/test_docker_release.py -q -k "invocation or collision or cleanup or execute_live or evidence_root" --basetemp=$BaseTemp
```

Expected: tests collect successfully and fail on the shell's `NotImplementedError` or wrong
contract, never on a live Docker dependency, import error, syntax error, or fixture defect.

- [ ] **Step 3: Implement immutable identities and command records**

Generate exactly 12 lowercase hexadecimal characters with `secrets.token_hex(6)`. Construct explicit image tags, Compose project, expected containers/network/volumes, and the ownership label. The command runner must accept argv arrays, never `shell=True`, capture bounded details plus complete SHA-256 digests, and redact repository-absolute paths before serialization.

- [ ] **Step 4: Implement pre-mutation inventory and cleanup authorization**

Inventory every exact expected container, network, volume, image tag, and Compose project resource before the first build. Reject any same name regardless of label. Cleanup must re-inventory each candidate and require both its exact expected name and:

```text
io.challengecup.task19.invocation=<current-id>
```

Use individual resource removal only. Represent a cleanup refusal as `fail`; do not broaden the command to force success.

- [ ] **Step 5: Write RED tests for phase ordering and classification**

Using a scripted fake command runner, assert the order:

1. collision inventory;
2. Compose headless build/start;
3. exact `/api/health` JSON;
4. API-created fixed 100-step quick smoke and exported relative evidence;
5. controlled stop;
6. `docker image save` to the invocation evidence directory;
7. `docker image load`, independent imported tag, repeated health/smoke;
8. optional GUI build/start and two increasing non-empty PNG frames;
9. evidence export before teardown;
10. exact label-checked resource cleanup and empty owned inventory.

Assert that a missing CLI/daemon before mutation is `not_run`, while any failure after a real build/run begins is `fail`. Assert GUI `not_run` does not downgrade a valid headless pass.

Add a parameterized partial-failure matrix that injects a failure or interruption immediately
after each mutation boundary: build, start, health, quick smoke, controlled stop, save, load,
imported start/smoke, GUI build/start/smoke, and evidence export. Every case must enter `finally`,
inventory only exact expected resources, remove only exact current-label owners, and record both
the primary failure and cleanup result. A refused cleanup, cleanup command failure, or non-empty
final owned inventory forces `cleanup=fail` and overall `fail`; it must never trigger broader
deletion. Include one `KeyboardInterrupt`/`BaseException` case so normal-exception-only cleanup
cannot satisfy the contract.

- [ ] **Step 6: Implement the workflow without running it locally**

Inject these Compose variables on every call:

```text
COMPOSE_PROJECT_NAME=ca-mp-task19-<id>
JUDGE_IMAGE=ca-mp-task19-<id>-headless:local
JUDGE_GUI_IMAGE=ca-mp-task19-<id>-gui:local
TASK19_INVOCATION_ID=<id>
```

Use `--project-name` explicitly as well. Never infer ownership from a prefix alone. The tar path and exported evidence directory must be under ignored `output/evidence/docker/live/<id>/`.
Resolve that root through `docker_status.resolve_protected_output_path()` before the first
filesystem or Docker mutation. Never reconstruct a weaker verifier-specific guard.

- [ ] **Step 7: Run GREEN and source-level destructive-command guards**

Run:

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-verifier-green"
& $Py -m pytest tests/test_docker_release.py -q --basetemp=$BaseTemp
rg -n "system prune|volume prune|down.*-v|shell=True" scripts/release/docker_verify.py tests/test_docker_release.py
& $Py scripts/release/docker_verify.py --repo-root .
```

Expected: tests pass; forbidden strings occur only in negative tests/documentation assertions; the ungated CLI exits nonzero before any Docker command. Do **not** pass `--execute-live` on this controller.

- [ ] **Step 8: Review and commit the verifier unit**

Ask Terra for a read-only security/maintainability review, emphasizing collision adoption, wrong-label cleanup, partial-failure cleanup, command injection, and secret/path leakage. Fix all Critical/Important findings test-first, then:

```powershell
git add -- scripts/release/docker_verify.py tests/test_docker_release.py
git diff --cached --name-status
git diff --cached --check
git commit -m "feat: add safe Docker live verifier"
```

---

## Task 19.D: Lock dependencies and build the headless judge image

**Files:**

- Create: `docker/requirements.in`
- Create: `docker/requirements.lock`
- Modify: `tests/test_docker_static.py`
- Modify: `tests/test_docker_release.py`
- Modify: `docker/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Replace the obsolete runner assertions with release-contract tests**

Tests must parse Compose with `yaml.safe_load()` and inspect Dockerfile stages. Require:

- exact Python and Node base references from the design;
- every `FROM` uses `--platform=linux/amd64` and documented direct build commands also pass
  `--platform linux/amd64`;
- Node stage uses `npm ci` and `npm run build` from the committed lockfile;
- Python install uses `--require-hashes --only-binary :all:`;
- exact SUMO/TraCI/sumolib 1.27.1 build gates;
- UID/GID 10001 and final `USER judge`;
- final launcher command uses host `0.0.0.0`, port 8000, attempts 1, no browser, headless mode, and `/app/output` diagnostics;
- runtime Web assets come from the Node builder, never host `api/static/dist`;
- Compose default service is `judge`, `platform` is `linux/amd64`, `image` is `${JUDGE_IMAGE:-ca-mp:latest}`, and health checks exact JSON;
- the Dockerfile declares `ARG TASK19_INVOCATION_ID=manual` plus an image label, Compose forwards
  the build arg, and the headless service, default network, and named volume all carry
  `io.challengecup.task19.invocation=${TASK19_INVOCATION_ID:-manual}`;
- named output volume, read-only root, `/tmp` tmpfs, `init`, no restart, and bounded stop grace.

- [ ] **Step 2: Run static RED**

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-headless-red"
& $Py -m pytest tests/test_docker_static.py tests/test_docker_release.py -q -k "dockerfile or compose or lock or headless" --basetemp=$BaseTemp
```

Expected: failures point to the old Ubuntu/PPA/`experiments.runner` image and bind-mounted `simulation` service.

- [ ] **Step 3: Create lock input and generate the frozen lock**

`docker/requirements.in` must contain:

```text
-r ../requirements.txt
eclipse-sumo==1.27.1
traci==1.27.1
sumolib==1.27.1
```

Generate mechanically with:

```powershell
uv --version
uv pip compile docker/requirements.in --python-version 3.12 --python-platform x86_64-manylinux_2_28 --only-binary :all: --generate-hashes --exclude-newer 2026-08-24T00:00:00Z --output-file docker/requirements.lock
```

Run the same command to a separate ignored temporary path and byte-compare it with the tracked lock. If resolution cannot complete, record the exact error and do not hand-write hashes.

- [ ] **Step 4: Implement the multi-stage headless Dockerfile**

Use these named stages and immutable bases:

```dockerfile
FROM --platform=linux/amd64 node:20.19.5-bookworm-slim@sha256:9e70124bd00f47dd023e349cd587132ae61892acc0e47ed641416c3e18f401c3 AS web-builder
FROM --platform=linux/amd64 python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS python-builder
FROM --platform=linux/amd64 python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS runtime
```

Copy only required repository paths. Discover the wheel `SUMO_HOME` at build time, create stable `sumo`/`sumo-gui` links, and fail the build unless executables and Python packages report exactly 1.27.1. Set safe cache/temp variables. Create and own `/app/output`, then change to `USER judge` before `ENTRYPOINT`/`CMD`.
In the final stage declare `ARG TASK19_INVOCATION_ID=manual` and
`LABEL io.challengecup.task19.invocation=$TASK19_INVOCATION_ID`; the verifier overrides the arg
with the unique ID. The imported image keeps the same image-config label.

- [ ] **Step 5: Implement the default Compose service**

Use a Docker-managed named volume rather than a host bind. Add exact image-variable, platform,
localhost port mapping, `init`, `read_only`, `/tmp` tmpfs, healthcheck, restart, stop grace, and
invocation labels. Compose must forward `TASK19_INVOCATION_ID` as a build arg and apply the exact
label to the `judge` service container, top-level default network, and output volume. The service
must use the Dockerfile launcher defaults rather than reintroducing `experiments.runner`.

- [ ] **Step 6: Run headless GREEN and lock consistency checks**

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-headless-green"
& $Py -m pytest tests/test_docker_static.py tests/test_docker_release.py -q -k "dockerfile or compose or lock or headless" --basetemp=$BaseTemp
& $Py -m pip install --dry-run --ignore-installed --require-hashes --only-binary :all: --platform manylinux_2_28_x86_64 --python-version 3.12 --implementation cp --abi cp312 -r docker/requirements.lock
```

The second command is a resolver/download-plan check, not Docker live proof. If local pip cannot perform the cross-platform dry run, record `not_run` for that supplemental check; the lock structural tests must still pass.

- [ ] **Step 7: Review and commit the headless unit**

Ask Sol to compare the configuration against design Sections 3.1–3.5. Fix Critical/Important findings test-first. Stage only:

```powershell
git add -- docker/requirements.in docker/requirements.lock docker/Dockerfile docker-compose.yml tests/test_docker_static.py tests/test_docker_release.py
git diff --cached --name-status
git diff --cached --check
git commit -m "feat: build reproducible headless judge image"
```

---

## Task 19.E: Add the GUI derivative, context boundary, and operator documentation

**Files:**

- Create: `docker/Dockerfile.gui`
- Modify: `docker-compose.yml`
- Modify: `.dockerignore`
- Modify: `tests/test_docker_static.py`
- Modify: `tests/test_docker_release.py`
- Modify: `docker/README.md`
- Modify: `docs/deployment.md`

- [ ] **Step 1: Add GUI/profile and build-context RED tests**

Require:

- `Dockerfile.gui` begins `FROM --platform=linux/amd64 judge_base` and has no mutable release tag;
- Debian `debian` and `debian-security` snapshot URLs both use timestamp
  `20260824T000000Z`, suites are Bookworm-only, and validity checking is explicitly disabled for
  the frozen snapshot rather than falling back to rolling sources;
- exact Xvfb, xauth, and GLU package versions are requested;
- build fails if `ldd` reports `not found`;
- GUI entrypoint uses `xvfb-run` plus the same `scripts/run_judge.py` in `container-gui` mode;
- Compose `judge-gui` is gated by `profiles: ["gui"]`, uses `additional_contexts` with `judge_base: service:judge`, injects `${JUDGE_GUI_IMAGE:-ca-mp-gui:latest}`, maps host 8001 to container 8000, and owns a separate labeled named volume;
- GUI Dockerfile overrides `ARG TASK19_INVOCATION_ID`/image `LABEL`; Compose forwards the GUI
  build arg and applies the same exact invocation label to the GUI service container. Together
  with the Task 19.D assertions, images, both containers, default network, and both volumes are
  all label-covered;
- `.dockerignore` excludes the protected archive, archives, output/evidence, `.superpowers`, `.agents`, `.worktrees`, environments, keys/certificates, caches, browser reports, `web/node_modules`, and host `api/static/dist`;
- `.dockerignore` still permits required Python runtime packages, `web/package*.json`, Web source, configuration, scenes, scripts, and `data/intersection_data`.

- [ ] **Step 2: Run GUI/context RED**

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-gui-red"
& $Py -m pytest tests/test_docker_static.py tests/test_docker_release.py -q -k "gui or dockerignore or build_context or documentation" --basetemp=$BaseTemp
```

Expected: missing GUI Dockerfile/profile and incomplete ignore rules fail for the intended reasons.

- [ ] **Step 3: Implement the GUI derivative**

Use the exact snapshot and package versions from the spec. Replace the base image's rolling
Deb822 sources before `apt-get update`; do not leave a second active source that can win package
resolution. The installation block must implement this shape:

```dockerfile
USER root
RUN set -eux; \
    rm -f /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' \
      'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20260824T000000Z bookworm main' \
      'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20260824T000000Z bookworm-updates main' \
      'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/20260824T000000Z bookworm-security main' \
      > /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends \
      xvfb=2:21.1.7-3+deb12u12 \
      xauth=1:1.1.2-1 \
      libglu1-mesa=9.0.2-1.1 \
    && command -v sumo-gui > /tmp/sumo-gui-path.txt \
    && ldd "$(cat /tmp/sumo-gui-path.txt)" > /tmp/sumo-gui-ldd.txt \
    && ! grep -F 'not found' /tmp/sumo-gui-ldd.txt \
    && rm -rf /var/lib/apt/lists/* /tmp/sumo-gui-path.txt /tmp/sumo-gui-ldd.txt
USER judge
```

Static tests assert every URL/suite/option/version and the `ldd` failure gate. The GUI stage also declares `ARG TASK19_INVOCATION_ID=manual` and resets
`LABEL io.challengecup.task19.invocation=$TASK19_INVOCATION_ID` after `FROM`; inherited base
metadata alone is not accepted because the GUI build receives its own explicit invocation arg.
Keep the base runtime's non-root user and add only Xvfb/Xauth/GLU runtime dependencies. Use
software GL and an Xvfb display. The container command must be equivalent to:

```text
xvfb-run -a python scripts/run_judge.py --host 0.0.0.0 --port 8000 --port-attempts 1 --no-browser --gui-mode container-gui --diagnostics /app/output/evidence/docker/launcher.json
```

Do not claim that Xvfb alone proves frame capture; live evidence requires two increasing non-empty PNG frames.

- [ ] **Step 4: Tighten `.dockerignore` without excluding runtime inputs**

Use anchored rules where ambiguity could exclude `data/intersection_data` or Web sources. Add tests for both excluded secrets/internal files and required-in-context inputs before changing patterns.

- [ ] **Step 5: Update active operator documentation**

Document:

- native launcher first, Docker as secondary;
- default headless Compose command and `gui` profile command;
- exact platform target, ports 8000/8001, named output volumes, evidence export with `docker compose cp`, and controlled shutdown;
- direct `docker build --platform linux/amd64` and Compose commands, plus the fact that verifier
  injects the invocation ID into image build args and container/network/volume labels;
- dependency-lock regeneration command and immutable-base update policy;
- detector command usable on all hosts;
- verifier command requiring `--execute-live`, its invocation-scoped resource policy, and forbidden cleanup commands;
- current controller outcome `not_run` / `docker_cli_unavailable`;
- save/load and GUI acceptance as commands to run only on a Docker-capable host, with no claim that they ran here.

Do not rewrite Task 20 release-document cleanup or Task 23 second-machine claims.

- [ ] **Step 6: Run GREEN plus documentation checks**

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-gui-green"
& $Py -m pytest tests/test_docker_static.py tests/test_docker_release.py tests/test_judge_launcher.py -q --basetemp=$BaseTemp
$Docs = @("docker/README.md", "docs/deployment.md")
$Required = @("docker_cli_unavailable", "not_run", "--execute-live", "container-gui", "linux/amd64", "8001", "compose cp")
foreach ($Pattern in $Required) {
    if (-not (Select-String -Path $Docs -SimpleMatch -Pattern $Pattern -Quiet)) {
        throw "missing required Docker documentation term: $Pattern"
    }
}
$Unsupported = rg -n "Docker live verification:\s*pass|gui_smoke:\s*pass|save_load:\s*pass" README.md docker/README.md docs/deployment.md
if ($LASTEXITCODE -eq 0) { $Unsupported; throw "unsupported Docker live pass claim" }
if ($LASTEXITCODE -gt 1) { throw "documentation scan failed with exit $LASTEXITCODE" }
```

Expected: tests pass, required honest wording exists, and the final search finds no unsupported current-machine pass claim.

- [ ] **Step 7: Review and commit GUI/docs unit**

Ask Terra to review maintainability/context safety and Sol to review spec/documentation truthfulness. Fix Critical/Important findings test-first, rerun Step 6, then:

```powershell
git add -- docker/Dockerfile.gui docker-compose.yml .dockerignore docker/README.md docs/deployment.md tests/test_docker_static.py tests/test_docker_release.py
git diff --cached --name-status
git diff --cached --check
git commit -m "feat: add optional container GUI deployment"
```

---

## Task 19.F: Verify, independently review, and close out

**Files:**

- Create: `.superpowers/sdd/2026-08-18-judge-facing-final-release/task-19-report.md`
- Modify: `.superpowers/sdd/2026-08-18-judge-facing-final-release/progress.md`

- [ ] **Step 1: Run focused Task 19 tests**

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-final-focused"
& $Py -m pytest tests/test_docker_release.py tests/test_docker_static.py tests/test_judge_launcher.py -q --basetemp=$BaseTemp
```

Record exact passed/failed counts and exit code.

- [ ] **Step 2: Run affected backend regressions**

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-final-affected"
& $Py -m pytest tests/test_release_preflight.py tests/test_validation_scripts.py tests/test_api.py tests/test_run_service.py tests/test_runner_channel.py tests/test_traci_bridge.py -q --basetemp=$BaseTemp
& $Py -m compileall -q scripts/run_judge.py scripts/release tests/test_docker_release.py tests/test_docker_static.py
& $Py -m flake8 scripts/run_judge.py scripts/release/docker_status.py scripts/release/docker_verify.py tests/test_judge_launcher.py tests/test_docker_release.py tests/test_docker_static.py
```

- [ ] **Step 3: Run the full Python and Web gates**

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-final-full"
& $Py -m pytest tests -q --basetemp=$BaseTemp
npm run typecheck --prefix web
npm run build --prefix web
npm run test:e2e --prefix web
```

Do not collapse reruns into a claim about an earlier failed run. Record every rerun and its reason.

- [ ] **Step 4: Generate current-host Docker status honestly**

```powershell
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
& $Py scripts/release/docker_status.py --repo-root . --output output/evidence/docker/docker-status.json
```

Expected on this controller: exit 0, overall `not_run`, reason `docker_cli_unavailable`. Do not run `docker_verify.py --execute-live`. If Docker unexpectedly becomes available, rerun the detector, inspect the state, and only then execute the live verifier under the spec; never assume availability from stale output.

- [ ] **Step 5: Run repository and protection gates**

```powershell
git diff --check
$Placeholders = rg -n "TODO|TBD|FIXME|PLACEHOLDER|待定|待补|稍后" docker scripts/release tests/test_docker_release.py tests/test_docker_static.py docker-compose.yml .dockerignore docker/README.md docs/deployment.md
if ($LASTEXITCODE -eq 0) { $Placeholders; throw "release placeholder found" }
if ($LASTEXITCODE -gt 1) { throw "placeholder scan failed with exit $LASTEXITCODE" }
$ArchiveHash = (Get-FileHash -Algorithm SHA256 "赛题资料.7z").Hash
if ($ArchiveHash -ne "12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F") { throw "archive hash changed" }
$TrackedOfficial = (git ls-files data/intersection_data | Measure-Object -Line).Lines
if ($TrackedOfficial -ne 163) { throw "tracked official-data count changed: $TrackedOfficial" }
$DiskOfficial = (Get-ChildItem data/intersection_data -Recurse -File | Measure-Object).Count
if ($DiskOfficial -ne 232) { throw "on-disk official-data count changed: $DiskOfficial" }
$ProtectedWorktree = git diff --name-only -- "赛题资料.7z" data/intersection_data
if ($ProtectedWorktree) { $ProtectedWorktree; throw "protected worktree diff detected" }
$ProtectedIndex = git diff --cached --name-only -- "赛题资料.7z" data/intersection_data
if ($ProtectedIndex) { $ProtectedIndex; throw "protected index diff detected" }
```

Expected: no whitespace or placeholder defect; exact frozen hash/counts; both protected diffs empty.

- [ ] **Step 6: Prepare a pending closeout draft and exact diff package**

Write the Task 19 report with status `verification_pending` and update the progress ledger to
`verification_pending`, not complete. Include all available RED/GREEN/gate evidence, exact unit
commit hashes, current detector status, unexecuted live axes, and review slots marked pending.
Then inspect:

```powershell
git log --oneline 68e3401936261ca2372cb5636966640a770d3d41..HEAD
git diff --stat 68e3401936261ca2372cb5636966640a770d3d41..HEAD
git diff --name-status 68e3401936261ca2372cb5636966640a770d3d41..HEAD
git diff -- .superpowers/sdd/2026-08-18-judge-facing-final-release/progress.md
git status --short --untracked-files=no
```

Expected: only Task 19 allowlisted paths changed; no runtime evidence is tracked.

- [ ] **Step 7: Obtain two independent final reviews over implementation and draft closeout**

Terra reviews standards, maintainability, Docker safety, test quality, secret/build-context
boundaries, and the pending report/progress wording. Sol reviews the Task 19 design and parent
Global Task 19 line by line, including evidence-state honesty, file-boundary amendments, and the
pending report/progress wording. Each reports Critical/Important/Minor findings with file
locations. Fix every Critical/Important test-first and return the changes to the original reviewer
until CLEAN. Minor findings are either fixed or explicitly recorded with rationale.

- [ ] **Step 8: Re-run gates after review fixes and freeze CLEAN verdicts**

Rerun the exact focused command and every affected/full gate touched by a review fix. Update the
pending report with actual rerun results and both CLEAN verdicts. Do not change the progress state
from `verification_pending` yet.

- [ ] **Step 9: Commit the pending verification record exactly**

The pending report must include:

- design and implementation commit hashes;
- RED commands and intended failure summaries for 19.A–19.E;
- GREEN, affected, full Python, typecheck, build, and Playwright results;
- detector JSON path and exact `not_run` reason;
- explicit live checks not run: build, health, smoke, save/load, GUI frames, cleanup;
- Terra and Sol verdicts plus resolved findings;
- archive hash, official-data counts, worktree/index protection results;
- exact tracked allowlist and any remaining limitations delegated to Tasks 20–24.

Never translate static test success into Docker live success. Force-add only the ignored report;
the progress ledger is already tracked:

```powershell
git add -f -- .superpowers/sdd/2026-08-18-judge-facing-final-release/task-19-report.md
git add -- .superpowers/sdd/2026-08-18-judge-facing-final-release/progress.md
git diff --cached --name-status
git diff --cached --check
git diff --cached --name-only -- "赛题资料.7z" data/intersection_data
git commit -m "docs: prepare Task 19 verification record"
```

- [ ] **Step 10: Verify the committed pending record and exact implementation HEAD**

```powershell
git status --short --untracked-files=no
$Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$BaseTemp = Join-Path ([System.IO.Path]::GetPathRoot((Resolve-Path ".").Path)) "Temp\challenge-cup-task19-postcommit-focused"
& $Py -m pytest tests/test_docker_release.py tests/test_docker_static.py tests/test_judge_launcher.py -q --basetemp=$BaseTemp
git diff HEAD^ --name-status
$ProtectedWorktree = git diff --name-only -- "赛题资料.7z" data/intersection_data
if ($ProtectedWorktree) { $ProtectedWorktree; throw "protected worktree diff detected" }
$ProtectedIndex = git diff --cached --name-only -- "赛题资料.7z" data/intersection_data
if ($ProtectedIndex) { $ProtectedIndex; throw "protected index diff detected" }
```

Expected: focused tests pass; tracked status is clean; `HEAD^..HEAD` contains only the pending
report/progress paths; protected diffs are empty. A failure keeps Task 19 pending.

- [ ] **Step 11: Write and independently review the final completion state**

Only after Step 10 passes, add its exact commit hash, test count, exit code, status/diff/protection
results to the report. Change both report and progress from `verification_pending` to `complete`.
Ask Terra and Sol to read the final two-file diff and confirm that completion wording matches the
actual evidence and that every Docker live axis is still `not_run` unless the gated verifier truly
ran. Resolve every Critical/Important finding and obtain CLEAN from both before staging.

- [ ] **Step 12: Commit final completion metadata**

```powershell
git add -- .superpowers/sdd/2026-08-18-judge-facing-final-release/task-19-report.md .superpowers/sdd/2026-08-18-judge-facing-final-release/progress.md
git diff --cached --name-status
git diff --cached --check
$ProtectedIndex = git diff --cached --name-only -- "赛题资料.7z" data/intersection_data
if ($ProtectedIndex) { $ProtectedIndex; throw "protected index diff detected" }
git commit -m "docs: close out Task 19 Docker deployment"
```

- [ ] **Step 13: Audit the final metadata commit without adding a new completion prerequisite**

```powershell
git status --short --untracked-files=no
git diff HEAD^ --name-status
$ProtectedWorktree = git diff --name-only -- "赛题资料.7z" data/intersection_data
if ($ProtectedWorktree) { $ProtectedWorktree; throw "protected worktree diff detected" }
```

All gate-setting tests run against the exact pending-record HEAD in Step 10, before the completion
diff is written. Step 11 obtains two CLEAN reviews of that final metadata-only diff, and Step 12
commits it; no source or test changes are allowed between Steps 10 and 12. Step 13 merely confirms
that Git recorded the already-reviewed two-file metadata commit and does not introduce a later
runtime gate. Task 19 is complete when Step 12 succeeds from that verified state, the final commit
contains only report/progress paths, and Docker live remains truthfully `not_run` unless actual
gated live evidence exists. Any unexpected Step 13 discrepancy is a new repository-integrity
defect and must be corrected, not retroactively described as a passed Task 19 gate.

---

## Handoff to Global Task 20

After Task 19 is complete, return to `docs/superpowers/plans/2026-08-18-judge-facing-final-release.md` and expand Global Task 20 into its own task-specific brief, design/implementation plan as needed, RED/GREEN sequence, real verification, independent reviews, protection checks, and exact commits. Do not implement Task 20 inside a Task 19 commit.
