### Global Task 19: Build and verify Docker judge deployment

This brief is the task-specific execution contract for Global Task 19. Subtasks 19.0 and
19.A–19.F belong to this one global task; they do not add tasks to the 24-task final-release plan.

## Goal and current baseline

Package the existing judge-facing FastAPI/Web/SUMO application as a reproducible Linux amd64
headless image plus an optional Xvfb GUI derivative. Both routes reuse `scripts/run_judge.py`, the
same health/API/Web contracts, and the same run/evidence lifecycle. The Windows native launcher
remains the primary judge entrypoint; Docker is a secondary reproducibility route.

Execution starts from:

- branch `codex/judge-final-release`;
- implementation-plan HEAD `d7ca03ffe12f484a7880f1d5fa8dd20abb281081`;
- approved design commit `68e3401936261ca2372cb5636966640a770d3d41`;
- Task 18 launcher implementation `6a149ef5561d3f365cd519577454c4e430e91891`;
- repository `.venv` CPython 3.12.13;
- `uv 0.12.5`;
- no Docker CLI on the controller;
- `wsl.exe` present as a Windows component but `wsl.exe --status` exits 50 because no Linux
  distribution/runtime is installed.

Tracked worktree/index status was clean at brief creation. Existing ignored/untracked scratch,
runtime evidence, `web/node_modules`, browser reports, and user files are not Task 19 inputs and
must not be cleaned or staged.

## PDF and project basis

- The competition PDF page 7 requires a runnable simulation system, complete source, detailed
  deployment instructions, and reproduction of a complete representative control flow.
- Page 10 rewards stable, reproducible integration of the algorithm and simulation platform.
- Page 16 requires environment adaptation, algorithm deployment, execution, and visible results
  to form one understandable demonstration flow.
- The repository implements track B around CA-MP algorithm optimization, but Docker must expose
  the same algorithm registry, 20 standard scenes, FastAPI endpoints, Web console, safety
  evidence, and shutdown ownership as the native judge route. It must not revert to the old
  one-shot `experiments.runner` container.

The approved implementation references are:

- `docs/superpowers/specs/2026-08-24-docker-judge-deployment-design.md`;
- `docs/superpowers/plans/2026-08-24-docker-judge-deployment-task19.md`;
- parent Global Task 19 in
  `docs/superpowers/plans/2026-08-18-judge-facing-final-release.md`.

## Frozen technical decisions

1. Target Linux `amd64`, Python 3.12, SUMO/TraCI/sumolib 1.27.1, and Node.js 20. No Task 19
   support claim is made for ARM64, Windows containers, Kubernetes, GPUs, or a remote registry.
2. Pin the exact Python and Node OCI manifest digests from the approved design. Every Dockerfile
   `FROM`, Compose service, dependency-resolution target, and documented build command explicitly
   selects `linux/amd64`.
3. Generate `docker/requirements.lock` with `uv pip compile`, binary wheels only, hashes, CPython
   3.12, `x86_64-manylinux_2_28`, and the 2026-08-24 cutoff. Never hand-write a missing hash.
4. Build production Web assets from `web/package-lock.json` in the pinned Node stage. The runtime
   copies builder output into `api/static/dist` and never accepts host-built assets.
5. Run the final image as UID/GID 10001. Application code and official scene inputs are
   read-only; `/app/output` is the only persistent writable path and `/tmp` is ephemeral.
6. Compose provides default `judge` headless service on host port 8000 and optional `judge-gui`
   profile on host port 8001. Both have strict internal port 8000, named output volumes,
   read-only roots, health checks, controlled stopping, and no restart loop.
7. `container-gui` is Linux-only, requires `DISPLAY` and SUMO-GUI 1.27.1, selects `sumo-gui`,
   records `native_gui=false`, and never enables Windows PID focus.
8. The GUI image derives from Compose `judge_base`, uses the fixed Debian snapshot
   `20260824T000000Z`, exact Xvfb/Xauth/GLU package versions, and an `ldd` no-missing-library gate.
9. The detector is non-mutating. The live verifier requires `--execute-live`, generates a random
   12-hex invocation ID, injects it into image build args and image/container/network/volume
   labels, rejects all same-name collisions before mutation, and cleans only exact current-label
   resources.
10. Docker CLI/daemon capability alone is never live proof. Missing CLI, unavailable daemon, or
    available capability without a completed gated verifier all remain `not_run` with distinct
    reasons. Only real project/image behavior after mutation may be `fail`; only the full
    headless build/health/100-step smoke/save-load/repeat/cleanup chain may be `pass`.

## Files in scope

Expected tracked Task 19 paths are limited to:

- `docker/Dockerfile`;
- `docker/Dockerfile.gui`;
- `docker/requirements.in`;
- `docker/requirements.lock`;
- `docker/README.md`;
- `docker-compose.yml`;
- `.dockerignore`;
- `scripts/run_judge.py`;
- `scripts/release/docker_status.py`;
- `scripts/release/docker_verify.py`;
- `tests/test_judge_launcher.py`;
- `tests/test_docker_static.py`;
- `tests/test_docker_release.py`;
- minimal Task 19 changes in `docs/deployment.md`;
- the Task 19 design and implementation plan;
- this brief, the later Task 19 report, and
  `.superpowers/sdd/2026-08-18-judge-facing-final-release/progress.md`.

Any additional tracked path requires a failing test plus controller review before it enters the
allowlist. Task 20 README/release-document replacement, Task 21 cleanup, Task 22 formal evidence,
Task 23 second-environment verification, and Task 24 materials remain out of scope.

## Immutable inputs and build-context boundary

- `赛题资料.7z` is never modified, deleted, moved, staged, copied into a Docker build context, or
  included in an image. Frozen SHA-256:
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`.
- Tracked files under `data/intersection_data` are never modified, deleted, moved, or staged.
  Frozen counts are 163 tracked files and 232 files on disk.
- Official scene inputs are intentionally read from the working tree into the Docker context and
  copied unchanged into a read-only image because judge simulations require them. This limited
  read authority does not authorize source mutation.
- Runtime evidence, Docker tar files, `.superpowers`, `.agents`, `.worktrees`, local environments,
  secrets, caches, browser results, and `web/node_modules` never enter the Docker context.
- Before every commit, the archive hash, official counts, protected worktree diff, and protected
  index diff must match this baseline.

## TDD and evidence rules

- Use the repository `.venv\Scripts\python.exe`; do not use a global Python command.
- Use a named pytest base directory under the system temporary directory. Repository
  `output/tmp` has an inherited ACL that can produce invalid `WinError 5` fixture failures.
- Every RED record names the failing test node ID, the new assertion reached, the observed missing
  behavior, and confirms collection/import/syntax/fixture setup succeeded. An unrelated failure
  is not RED evidence.
- Every GREEN record reruns the exact RED command and its named adjacent regression command.
- New detector/verifier modules may begin with importable signatures whose bodies raise
  `NotImplementedError`; only a test that reaches such a public interface counts as behavioral
  RED.
- Static Docker tests prove configuration only. They never change Docker live status to `pass`.
- Runtime evidence uses only `pass`, `fail`, and `not_run`, schema
  `judge-docker-evidence.v1`, bounded diagnostics, relative paths, and no personal or secret data.

## Docker mutation and cleanup prohibitions

No agent or script may run or generate:

- `docker system prune`;
- `docker volume prune`;
- `docker compose down -v`;
- broad container/image/network/volume filters;
- removal based only on a name prefix, Compose project label, or stale invocation ID;
- mutation or adoption of any pre-existing same-name resource.

The live verifier may mutate Docker only with explicit `--execute-live`. It inventories all exact
expected names before the first mutation. Every build/start/health/smoke/stop/save/load/GUI/export
failure or interruption enters `finally`; cleanup rechecks exact name plus
`io.challengecup.task19.invocation=<current-id>` before individual removal. Refused/failed cleanup
or a non-empty final owned inventory forces overall `fail` and never broadens deletion.

## Single-writer execution route

- 19.A launcher: Luna writes; Terra reviews.
- 19.B detector/schema: Terra writes; Sol reviews.
- 19.C live verifier: Sol writes; Terra reviews.
- 19.D lock/headless/Compose: Terra writes; Sol reviews.
- 19.E GUI/context/docs: Luna writes; Terra and Sol review.
- 19.F verification/closeout: controller writes; Terra and Sol review.

Only one implementation writer is active at a time. The controller owns exact staging, protected
checks, and commits. Review agents are read-only unless reassigned a bounded test-first fix.

## Required commits and stop conditions

The design and plan are already separate commits. This brief is committed alone. Each 19.A–19.E
unit is reviewed and committed with only its exact file allowlist. Closeout uses two metadata
commits: first a `verification_pending` report/progress record, then post-commit focused/protection
gates, then a Terra/Sol-reviewed two-file `complete` diff.

Stop and diagnose rather than improvise if:

- a protected input hash/count/diff changes;
- an unrelated tracked file changes;
- a RED fails during collection/import/fixture setup;
- the repository interpreter or `uv` is unavailable;
- Docker becomes newly available but its state has not been inventoried;
- a same-name Docker resource exists;
- cleanup ownership cannot be proven;
- a test, review, or evidence schema would require claiming an unexecuted live check passed.

## Acceptance gates

- launcher `container-gui` focused and adjacent suites pass without regressing existing modes;
- detector/verifier schema, path protection, classification, collision, labeling, partial-failure,
  cleanup, privacy, and atomic-write tests pass;
- Dockerfile/Compose/GUI/ignore/documentation static contracts pass;
- repository interpreter compileall, targeted flake8, affected tests, full Python suite, Web
  typecheck/build/Playwright, placeholder checks, diff checks, and protected-input gates pass;
- `docker_status.py` writes current-host evidence as `not_run/docker_cli_unavailable` unless the
  environment genuinely changes;
- Docker live build, health, smoke, save/load, GUI frames, and cleanup remain explicitly
  `not_run` on this controller and are not simulated;
- Terra and Sol return CLEAN on the complete implementation and closeout wording;
- no runtime evidence, tar, scratch, protected input, or unrelated user file is staged.
