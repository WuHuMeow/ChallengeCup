# Task 19 Docker Judge Deployment Design

Date: 2026-08-24

## 1. Purpose and governing requirements

Global Task 19 packages the existing judge-facing FastAPI/Web/SUMO application for a
reproducible Linux container route. It does not replace the Windows native launcher as the
judge's primary entrypoint. The container must run the same `scripts/run_judge.py` composition,
serve the same `/api/health` and Web console, preserve all run/evidence contracts, and never
present static Docker configuration as live Docker proof.

This design is governed by:

- `docs/superpowers/specs/2026-08-18-judge-facing-final-release-design.md`;
- Global Task 19 in `docs/superpowers/plans/2026-08-18-judge-facing-final-release.md`;
- the completed Task 18 launcher contract and exact implementation commit
  `6a149ef5561d3f365cd519577454c4e430e91891`;
- the immutable-input rules for `赛题资料.7z` and `data/intersection_data`;
- the evidence states `pass`, `fail`, and `not_run`.

## 2. Current-state findings

The existing `docker/Dockerfile` and `docker-compose.yml` run one
`python3 -m experiments.runner` simulation. They do not expose the judge API, healthcheck,
production Web build, or optional GUI profile. The existing PPA install is rolling and does not
prove SUMO 1.27.1. `tests/test_docker_static.py` intentionally freezes the old runner contract and
must be migrated.

On the 2026-08-24 controller machine, the Docker CLI is absent and WSL is not installed. Live
build, container health, image save/load, GUI capture, and container cleanup therefore have
status `not_run`, reason `docker_cli_unavailable`. Static tests, host regressions, configuration
review, and protected-input checks remain executable and must pass.

## 3. Selected architecture

### 3.1 Supported release target

The frozen Task 19 image target is Linux `amd64`, Python 3.12, and SUMO 1.27.1. Dockerfiles,
Compose services, documented build/run/save-load commands, dependency resolution, and evidence
all explicitly use `linux/amd64`; a multi-architecture index digest alone is not treated as a
platform constraint. No Task 19 claim is made for ARM64, Windows containers, Kubernetes, GPU
acceleration, or a remote registry. Task 23 may add evidence from another compatible environment
without changing this contract.

The base images are immutable OCI manifest references resolved from Docker Hub on 2026-08-24:

- `python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2`;
- `node:20.19.5-bookworm-slim@sha256:9e70124bd00f47dd023e349cd587132ae61892acc0e47ed641416c3e18f401c3`.

Changing either digest is an explicit reviewed dependency update. It must not happen implicitly
during a release build.

### 3.2 Python and SUMO dependency lock

`docker/requirements.in` references the repository `requirements.txt` and adds exact
`eclipse-sumo==1.27.1`, `traci==1.27.1`, and `sumolib==1.27.1` constraints.
`docker/requirements.lock` is generated for CPython 3.12 and
`x86_64-manylinux_2_28` with hashes and binary wheels only:

```powershell
uv pip compile docker/requirements.in `
  --python-version 3.12 `
  --python-platform x86_64-manylinux_2_28 `
  --only-binary :all: `
  --generate-hashes `
  --exclude-newer 2026-08-24T00:00:00Z `
  --output-file docker/requirements.lock
```

The Python build stage installs with `pip --require-hashes --only-binary :all:`. The runtime image
copies that environment rather than resolving dependencies again. The official `eclipse-sumo`
wheel supplies the Linux applications; the build sets the wheel's discovered `SUMO_HOME`, creates
stable executable links on `PATH`, and verifies `sumo --version`, `sumo-gui --version`, `traci`,
and `sumolib` all report 1.27.1. A version mismatch is a build failure, never a warning.

### 3.3 Production Web build

A named Node stage copies only `web/package.json`, `web/package-lock.json`, and the `web/` source,
runs `npm ci` and `npm run build`, and produces `api/static/dist`. The runtime stage does not copy
host-built `api/static/dist`; it copies only the builder's production output. This proves that the
image is reproducible from the lockfile and prevents stale host assets from entering the image.

### 3.4 Headless runtime image

The default `docker/Dockerfile`:

- creates an explicit UID/GID 10001 `judge` user;
- copies only required runtime Python packages, configuration, standard scenes, official scene
  inputs, scripts, and the production Web assets;
- makes application code and `data/intersection_data` non-writable;
- creates `/app/output` owned by `judge`;
- sets `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, and safe temporary/cache paths;
- declares `EXPOSE 8000`;
- uses `python scripts/run_judge.py` as the application entrypoint;
- defaults to `--host 0.0.0.0 --port 8000 --port-attempts 1 --no-browser
  --gui-mode headless --diagnostics /app/output/evidence/docker/launcher.json`.

`--port-attempts 1` is mandatory in a container: silently moving to 8001 would make the fixed host
port mapping and healthcheck lie. The same launcher owns `RunService`, Uvicorn, SUMO children,
readiness, diagnostics, and shutdown exactly as on the native route.

### 3.5 Compose headless service

The default Compose service is named `judge`. It:

- builds `docker/Dockerfile` as `${JUDGE_IMAGE:-ca-mp:latest}`; the default is for manual use,
  while the live verifier must inject an invocation-scoped image reference;
- sets `platform: linux/amd64` and publishes `127.0.0.1:8000:8000` by default, with an
  environment-overridable host binding;
- mounts the Docker-managed named volume `judge-output:/app/output`; Compose namespaces the
  actual volume with its project name;
- uses `init: true`, `read_only: true`, `tmpfs: /tmp`, `restart: "no"`, and a bounded
  `stop_grace_period`;
- performs an exact JSON `/api/health` check with the installed Python runtime;
- does not enable a display or GUI dependency.

An empty named volume inherits the image's UID/GID 10001 ownership at first mount, so launcher
preflight can atomically create `/app/output/evidence/docker` and `/app/output/runs` as the final
non-root user. This avoids the unprovable ownership of a host bind mount. Evidence is exported with
the documented `docker compose cp` command rather than by weakening container permissions.
Persistent project writes are allowed only below `/app/output`. Ephemeral interpreter, X11, and
Matplotlib state may use the `/tmp` tmpfs and is never release evidence.

### 3.6 Optional container GUI profile

Task 18's `native` mode is Windows-only and retains exact PID window-focus behavior. It must not be
reused for Linux. The launcher gains one explicit CLI value, `container-gui`:

- valid only when `sys.platform != "win32"`;
- requires a non-empty `DISPLAY` and a resolvable `sumo-gui` 1.27.1;
- selects `sumo-gui` for `SimulationRunner`;
- records runtime mode `container-gui` and `native_gui=false`;
- keeps `/api/runs/{run_id}/native-gui` disabled, because Xvfb has no Windows focus contract;
- leaves `auto`, `native`, and `headless` behavior unchanged.

`docker/Dockerfile.gui` uses `FROM judge_base`; Compose supplies that named build context through
`additional_contexts: {judge_base: "service:judge"}`. This creates an explicit dependent-image
relationship and never resolves a mutable `ca-mp:latest` inside the Dockerfile. The GUI derivative
adds only packages from the fixed Debian Bookworm snapshot
`20260824T000000Z`: `xvfb=2:21.1.7-3+deb12u12`, `xauth=1:1.1.2-1`, and
`libglu1-mesa=9.0.2-1.1`; their transitive packages resolve from the same snapshot. The build runs
`ldd` on `sumo-gui` and fails on every `not found` library.

The Compose service `judge-gui` is gated by `profiles: ["gui"]`, sets
`platform: linux/amd64`, maps host port 8001 to its internal strict port 8000, and uses its own
`judge-gui-output` named volume. Both top-level volumes carry an optional invocation label supplied
by the verifier. Its image field is `${JUDGE_GUI_IMAGE:-ca-mp-gui:latest}`. `docker compose
--profile gui up --build` explicitly adds the GUI
service to the always-on headless service without a port or output-writer collision. The GUI image
invokes the same `scripts/run_judge.py` through `xvfb-run` with software GL. A live GUI pass requires
at least two non-empty PNG frames with increasing sequence/timestamp values, not merely a running
Xvfb process. GUI availability is independent from headless correctness and is `not_run` on the
current machine.

### 3.7 Build-context and secret boundary

`.dockerignore` excludes at least:

- `.git`, `.venv`, caches, scratch directories, test/browser reports, and `web/node_modules`;
- all `output` runtime results and evidence;
- `.superpowers`, `.agents`, `.worktrees`, local environment files, keys, and certificates;
- the exact protected archive `赛题资料.7z` and other local archives;
- host-built `api/static/dist`.

It must not exclude the runtime source packages, `web/` source and lockfile, configuration,
standard scenes, or `data/intersection_data`. Sending the protected archive or runtime evidence to
the build context is a release failure even if the Dockerfile never copies it.

## 4. Evidence and status contract

`scripts/release/docker_status.py` performs only safe detection, schema construction/validation,
and atomic writes to `output/evidence/docker/docker-status.json`. It never builds, starts, stops,
removes, or prunes Docker resources.

`scripts/release/docker_verify.py` owns the live workflow. It runs only with an explicit
`--execute-live` flag and generates a cryptographically random 12-hex invocation ID. The Compose
project is `ca-mp-task19-<id>`; image tags, imported tags, containers, networks, volumes, evidence
directory, and labels carry the same ID. It injects
`JUDGE_IMAGE=ca-mp-task19-<id>-headless:local`,
`JUDGE_GUI_IMAGE=ca-mp-task19-<id>-gui:local`, and later uses
`ca-mp-task19-<id>-imported:local` for the loaded image.

Before the first mutation, the verifier performs a name-collision inventory. Any exact expected
container, network, volume, image tag, or Compose project resource causes a fail-closed result,
regardless of whether its label is missing, different, or equal to the new invocation label. It
never recreates, stops, removes, or adopts a pre-existing same-name resource.

The verifier may stop and remove only resources whose exact expected name and
`io.challengecup.task19.invocation=<id>` label both match. It exports run/diagnostics evidence to
the ignored host directory `output/evidence/docker/live/<id>` before teardown, then removes the
two invocation-namespaced volumes and invocation image tags individually after rechecking their
labels. It never uses `docker system prune`, `docker volume prune`, broad image/container filters,
or unrelated Docker state; `compose down -v` is also forbidden because the verifier performs
label-checked volume removal itself. It performs build, health, quick smoke, controlled shutdown,
save, load under an independent tag, repeated health/smoke, and owned-resource cleanup. On the
current machine it is not invoked because the detector proves the CLI absent.

The stable schema is `judge-docker-evidence.v1` and contains:

- `checked_at`, `status`, `reason`, and `platform` with exact `os` and `architecture`;
- `cli.status`, `daemon.status`, and sanitized version fields;
- `static_contract`, `headless_build`, `headless_health`, `headless_smoke`, `save_load`,
  `gui_build`, `gui_smoke`, and `cleanup` using only `pass`, `fail`, or `not_run`;
- for every phase: `started_at`, `finished_at`, sanitized argv, exit code, stdout/stderr SHA-256,
  and a bounded detail string;
- invocation ID, unique Compose project, image references, image ID, repository/config/content
  digests, platform, and ownership labels only after real execution;
- quick-smoke `evidence_class=quick_smoke`, fixed `requested_steps=100`, run ID, terminal status,
  and output path relative to `/app/output`; this path cannot be a formal evidence root;
- a `name_collisions.before` inventory of every exact expected name/tag/project regardless of
  label, plus `owned_resources.before_cleanup` and `owned_resources.after_cleanup` inventories
  requiring exact names and the current invocation label; `pass` requires the collision inventory
  and final owned-resource inventory to be empty;
- no username, absolute personal path, environment dump, secret, or unrelated process list.

Classification rules:

1. Docker executable absent: overall `not_run`, reason `docker_cli_unavailable`.
2. CLI present but daemon unreachable before any build: overall `not_run`, reason
   `docker_daemon_unavailable`.
3. A real build/run/check starts and fails because of project or image behavior: overall `fail`
   with the failed command and sanitized diagnostic.
4. Overall `pass` requires actual `linux/amd64` headless build, health, 100-step API quick smoke,
   controlled shutdown, save/load into an independent image name, repeated health/smoke, and
   owned-resource cleanup. The schema validator rejects a `pass` lacking any phase evidence, a
   unique invocation ID, a zero-collision preflight, exported evidence, or a zero-resource final
   owned inventory.
5. GUI is an independent axis. Its absence cannot convert a headless pass to fail, and a static
   profile cannot convert GUI `not_run` to pass.

The current machine must generate the first classification. No `docker system prune`,
`docker volume prune`, `compose down -v`, broad removal, non-invocation volume deletion, or
mutation of unrelated Docker state is authorized. The only authorized volume deletion is the
individual removal described above after both exact invocation name and label have been rechecked.

## 5. Testing and review

TDD starts by replacing the old static assertions and adding `tests/test_docker_release.py`.
Tests cover:

- exact base references, `linux/amd64`, dependency lock, SUMO version gates, Web builder, runtime
  copy set, non-root user, port, launcher command, named-volume ownership, and writable paths;
- parsed Compose service/profile/health/read-only/volume/stop contracts;
- `.dockerignore` inclusion and exclusion boundaries;
- `container-gui` argument, platform/DISPLAY/binary validation, diagnostics, and disabled native
  focus behavior;
- Docker detector/verifier evidence `not_run`/`fail`/`pass` classification, per-phase completeness,
  unique-invocation resource ownership/collision/cleanup, quick-smoke/non-formal boundary, and
  protected diagnostics path;
- active documentation commands and honest unavailable wording.

After focused GREEN, run launcher/API/lifecycle affected tests, the full Python suite, Web
typecheck/build/Playwright, compileall, targeted flake8, diff checks, archive hash, official-data
counts, and protected worktree/index checks. Terra reviews standards/security/maintainability; Sol
reviews this specification and Global Task 19 compliance. Every Critical or Important finding is
fixed test-first and returned to the original reviewer.

## 6. Deliverables and commit boundary

This task-specific design is an explicit amendment to the illustrative Global Task 19 file list.
It retains the parent plan's Node.js 20 requirement. The expanded allowlist is required because
the parent plan's optional Linux GUI cannot be expressed by Task 18's Windows-only `native` mode,
reproducibility requires lock inputs, and truthful live status requires separately testable
detector/verifier owners. No other global-task boundary changes.

Expected tracked Task 19 paths are:

- `docker/Dockerfile`, `docker/Dockerfile.gui`, `docker/requirements.in`,
  `docker/requirements.lock`, `docker/README.md`;
- `docker-compose.yml`, `.dockerignore`;
- `scripts/run_judge.py`, `scripts/release/docker_status.py`,
  `scripts/release/docker_verify.py`;
- `tests/test_judge_launcher.py`, `tests/test_docker_static.py`,
  `tests/test_docker_release.py`;
- minimal Task 19 deployment documentation, this design, its implementation plan,
  Task 19 brief/report, and `progress.md`.

Runtime JSON, Docker tar files, images, containers, logs, scratch directories, `web/node_modules`,
the protected archive, and official scene data are never staged. Task 19 completion records live
Docker as `not_run` on this machine and does not claim Task 20 documentation cleanup, Task 21
release cleanup, Task 22 formal evidence generation, Task 23 second-environment verification, or
Task 24 submission materials.

## 7. Source basis

- Docker multi-stage builds:
  <https://docs.docker.com/build/building/multi-stage/>
- Docker build best practices:
  <https://docs.docker.com/build/building/best-practices/>
- Docker Compose services and profiles:
  <https://docs.docker.com/reference/compose-file/services/>
  and <https://docs.docker.com/reference/compose-file/profiles/>
- Docker Compose dependent images:
  <https://docs.docker.com/compose/how-tos/dependent-images/>
- Debian Bookworm Xvfb and X authentication packages:
  <https://packages.debian.org/bookworm/xvfb> and
  <https://packages.debian.org/bookworm/amd64/xauth>
- SUMO 1.27.1 downloads and Python application wheels:
  <https://eclipse.dev/sumo/docs/Downloads.html>
- SUMO GUI behavior:
  <https://eclipse.dev/sumo/docs/sumo-gui.html>
