# SDD ledger — plan: docs/superpowers/plans/2026-08-18-judge-facing-final-release.md

## Recovery checkpoint (2026-08-19)

- Worktree: `D:/WorkPlace/challenge-cup/.worktrees/judge-final-release`
- Branch: `codex/judge-final-release`
- Recovered runtime checkpoint: `eb32507`
- Task 1 implementation commit: `c408917`
- Task 1 historical fresh evidence on this recovered branch: focused `11 passed`; full suite `215 passed`; Python 3.12.13, SUMO/TraCI 1.27.1 and the protected archive hash matched; Docker was `not_run` because no CLI was available.
- Task 1 independent review was not completed before interruption; it is the current gate.
- Task 2 RED was observed as missing `scripts.release.output_policy`; its minimal implementation and tests are uncommitted, and GREEN was interrupted before a result was obtained.
- Protected inputs remain outside implementation scope: `赛题资料.7z` is untracked and `data/intersection_data/` has 163 tracked files.

## Preflight plan scan

### Per-task internal consistency

| Task | Produced contract vs specified tests/consumers | Finding |
|---|---|---|
| 1 | Environment/preflight JSON, source hash and worktree inventory | Coherent. Generated `environment.json` is runtime evidence and the commit step intentionally stages only code, tests and README. |
| 2 | Pure release classification and read-only audit | Coherent; no deletion belongs in this task. |
| 3 | Canonical algorithm registry used by API, events and runners | Coherent; legacy names remain migration-only. |
| 4 | Immutable movement contracts plus API adapters | Coherent; `JointState` compatibility queue fields remain display-only for movement pressure. |
| 5 | Seconds-first windows and derived steps | Coherent if scene step length is resolved before deriving steps; an explicit CLI smoke-step override must not become a public API default. |
| 6 | Validated, read-only scene manifests and importer | Coherent; imported packages are separate from official source roots. |
| 7 | Single-source demand scaling and deterministic disturbances | Coherent; generated variants must never amend parent SUMO configuration in place. |
| 8 | TraCI movement state, safety observations and completed/unfinished split | Coherent; observation fields must retain units and run identity. |
| 9 | Traceable fixed timing and independent classic MaxPressure | Coherent; classic scoring must not import capacity-aware enhancements. |
| 10 | Layered capacity-aware ablations and cloud-edge envelope | Coherent, but M3 and message-envelope behavior need explicit coverage in addition to the examples. |
| 11 | One signal-writing safety executor | Coherent if transition sequencing can represent both yellow and all-red rather than treating the example tuple as the whole transition plan. |
| 12 | Run state machine, process ownership and atomic terminal evidence | Plan example mentions `STOPPED`, while the binding spec defines `interrupted` as the stop terminal. See ruling below. |
| 13 | Atomic run-scoped evidence and metric semantics | Coherent; unfinished vehicles are separated from every completed-vehicle aggregate. |
| 14 | Exact 360 + 180 matrix, resume and paired statistics | Coherent; completed valid runs remain immutable and retries use new run IDs. |
| 15 | Capacity-one frame publisher and independent realtime events | Coherent; FPS/latency remain measured acceptance targets, not unit-test claims. |
| 16 | Judge API, WebSocket, frame endpoint and static serving | Coherent when `api/static.py` serves the spec-owned `web/dist` directory. |
| 17 | React console, typed client and Playwright workflow | Build destination and test invocation conflict with Task 16/Windows paths; see rulings below. |
| 18 | Project-interpreter native launcher and diagnostics | Coherent; health must succeed before opening a browser. |
| 19 | Same application entrypoint in headless and optional GUI Docker profiles | Coherent; live Docker status cannot be `pass` without a real CLI/build/run. |
| 20 | Judge-facing documentation and stale-claim checker | Coherent; internal source documents may remain in development history but must not enter the release copy. |
| 21 | Recoverable cleanup plan and allowlisted release copy | Coherent; no cleanup API may target protected inputs. |
| 22 | Staged real verification and 540 valid formal outputs | Coherent; short runs are preflight only and failures retain evidence plus new retry IDs. |
| 23 | Release-copy, browser, Docker and second-environment verification | Coherent; unavailable external environments remain `not_run`. |
| 24 | Report/PPT/video generated only from frozen evidence | Coherent; every numeric claim must trace to Task 22 outputs. |

### Shared-file and interface handoffs

| Tasks | Producer / consumer relationship | Finding |
|---|---|---|
| 1 -> 18 | Preflight contract feeds native launcher | Compatible; launcher must consume statuses without rewriting evidence. |
| 1 -> 23 | Baseline provenance feeds final package verification | Compatible; final verifier must use fresh output. |
| 2 -> 20 | `output/README.md` policy is rewritten for judges | Compatible; Task 20 must retain preservation semantics. |
| 2 -> 21 | `output_policy.py` is extended by cleanup tooling | Compatible; pure classification remains reusable. |
| 2 -> 23 | Release allowlist constrains package verification | Compatible. |
| 3 -> 5 | `core/run_models.py` and `api/models.py` gain canonical IDs then seconds | Compatible if migrations stay at boundaries. |
| 3 -> 7 | Run/API models gain disturbance fields after canonical IDs | Compatible. |
| 3 -> 12 | `core/run_models.py` and `engine/run_service.py` become lifecycle-safe | Compatible; registry construction remains the only algorithm factory. |
| 3 -> 14 | `experiments/runner.py` consumes canonical registry IDs | Compatible. |
| 3 -> 16 | `api/server.py` and `api/models.py` expose the registry contract | Compatible. |
| 3 -> 8 | `engine/events.py` canonical IDs precede safety events | Compatible; event schema changes require downstream evidence refresh. |
| 4 -> 5 | `api/models.py` movement adapters coexist with seconds request fields | Compatible; separate payload sections. |
| 4 -> 6 | `docs/interface.md` adds scene contracts after movement contracts | Compatible. |
| 4 -> 7 | `api/models.py` adds variant adapters after movement adapters | Compatible. |
| 4 -> 8 | Movement contracts are populated by TraCI extraction | Compatible and load-bearing. |
| 4 -> 9 | Classic pressure consumes only `phase_movements` | Compatible and load-bearing. |
| 4 -> 10 | Capacity-aware pressure consumes the same movement contract | Compatible and load-bearing. |
| 4 -> 16 | API movement types coexist with judge endpoints | Compatible. |
| 5 -> 7 | `core/run_models.py`, `api/models.py` and config add disturbances without reverting seconds | Compatible. |
| 5 -> 10 | Shared config adds algorithm parameters without reverting formal windows | Compatible. |
| 5 -> 12 | Lifecycle runner derives steps from seconds plus scene step length | Compatible and load-bearing. |
| 5 -> 13 | Evidence manifest records requested seconds and derived steps | Compatible and load-bearing. |
| 5 -> 14 | Formal matrix uses seconds-first requests and frozen seeds | Compatible and load-bearing. |
| 5 -> 16 | Judge run API exposes duration seconds, not formal steps | Compatible. |
| 6 -> 7 | Validated `SceneManifest` is the parent of every variant | Compatible and load-bearing. |
| 6 -> 8 | Validated lanes/TLS/movements feed TraCI state extraction | Compatible and load-bearing. |
| 6 -> 9 | Scene timing provenance feeds fixed-time resolver | Compatible. |
| 6 -> 12 | Scene step length and source identity feed runner lifecycle | Compatible. |
| 6 -> 14 | Formal scene registry must enumerate exactly scenes 1..20 | Compatible. |
| 6 -> 16 | Scene manifests are exposed read-only through the API | Compatible. |
| 6 -> 17 | Scene view consumes validation warnings and hashes | Compatible. |
| 7 -> 12 | Run requests resolve temporary variants before process start | Compatible. |
| 7 -> 14 | Three deterministic disturbance kinds feed the 180-run matrix | Compatible and load-bearing. |
| 7 -> 16 | API accepts validated disturbance specifications | Compatible. |
| 7 -> 17 | UI selectors consume disturbance metadata | Compatible. |
| 8 -> 10 | Extracted movement measurements feed capacity-aware scoring | Compatible and load-bearing. |
| 8 -> 11 | Safety observations consume action results from the executor | Compatible. |
| 8 -> 13 | Completed/unfinished and safety fields feed evidence aggregation | Compatible and load-bearing. |
| 8 -> 15 | Metric/safety snapshots feed realtime publication | Compatible. |
| 8 -> 16 | Judge API exposes run-scoped safety/metric data | Compatible. |
| 8 -> 17 | Web metrics and safety badges consume the same semantics | Compatible. |
| 9 -> 10 | M0 capacity-aware ablation must match independent classic scores | Compatible and explicitly tested. |
| 9 -> 11 | Both formal adaptive algorithms route through one safety executor | Compatible and load-bearing. |
| 9 -> 14 | Fixed/classic canonical algorithms enter the formal matrix | Compatible. |
| 9 -> 16 | Registry-backed algorithm metadata enters API | Compatible. |
| 10 -> 11 | Capacity-aware candidate actions route through safety executor | Compatible and load-bearing. |
| 10 -> 14 | Capacity-aware default/ablations feed experiments | Compatible; only frozen default enters formal matrix. |
| 10 -> 16 | Score breakdown feeds judge inspection APIs | Compatible. |
| 10 -> 17 | Web decision display consumes score and blocked-movement reasons | Compatible. |
| 11 -> 12 | Runner must invoke the sole action-writing path | Compatible and load-bearing. |
| 11 -> 13 | Accepted/rejected action records feed evidence | Compatible. |
| 12 -> 13 | `engine/artifacts.py` and terminal states feed evidence finalization | Compatible and load-bearing. |
| 12 -> 15 | `engine/runner.py`, `run_service.py` add frame/event sinks without changing ownership | Compatible. |
| 12 -> 16 | API controls idempotent lifecycle operations | Compatible. |
| 12 -> 18 | Launcher owns service shutdown, not individual SUMO processes directly | Compatible. |
| 13 -> 14 | Matrix validates and aggregates only complete evidence contracts | Compatible and load-bearing. |
| 13 -> 16 | Results endpoints expose validated summaries only | Compatible. |
| 13 -> 17 | Comparison/history consume provenance-bearing summaries | Compatible. |
| 13 -> 20 | Public evidence documentation derives from frozen fields/units | Compatible. |
| 13 -> 22 | Formal runs write the same per-run evidence contract | Compatible and load-bearing. |
| 13 -> 24 | Submission figures may consume only frozen evidence summaries | Compatible. |
| 14 -> 16 | Results APIs expose frozen matrix summaries | Compatible. |
| 14 -> 17 | Comparison view consumes paired statistics and run IDs | Compatible. |
| 14 -> 20 | Experiment protocol documents exact executable matrix | Compatible. |
| 14 -> 22 | Task 22 executes and freezes Task 14's matrix | Compatible and load-bearing. |
| 14 -> 24 | Report conclusions consume paired statistics | Compatible. |
| 15 -> 16 | FramePublisher and RealtimeHub back frame/WebSocket endpoints | Compatible and load-bearing. |
| 15 -> 17 | Web frame polling and event subscription consume sequence/time metadata | Compatible. |
| 16 -> 17 | Typed frontend client consumes judge API/OpenAPI | Compatible except build-path ruling below. |
| 16 -> 18 | Native launcher health-checks and serves the same FastAPI app | Compatible. |
| 16 -> 19 | Docker launches the same FastAPI app and health endpoint | Compatible. |
| 17 -> 18 | Native launcher serves prebuilt Web assets | Compatible. |
| 17 -> 19 | Docker Node build produces the same prebuilt assets | Compatible. |
| 17 -> 23 | Playwright validates the release-copy console | Compatible. |
| 18 -> 19 | Docker reuses `scripts/run_judge.py` | Compatible and prevents duplicate business entrypoints. |
| 18 -> 20 | README/deployment docs use real launcher commands | Compatible. |
| 18 -> 23 | Release verification exercises native launcher | Compatible. |
| 19 -> 23 | Release verification exercises Docker only when available | Compatible. |
| 20 -> 21 | Public reference inventory precedes quarantine/release copy | Compatible and load-bearing. |
| 20 -> 23 | Package verifier checks public docs and links | Compatible. |
| 20 -> 24 | Submission materials must follow judge-facing terminology | Compatible. |
| 21 -> 23 | `build_release_copy` supplies the clean candidate under verification | Compatible and load-bearing. |
| 22 -> 23 | Frozen formal/quick evidence is included by manifest policy | Compatible. |
| 22 -> 24 | Frozen evidence is the only numeric input to materials | Compatible and load-bearing. |
| 23 -> 24 | Final release manifest supplies verified deployment status | Compatible. |

## Rulings

- Ruling: Task 16/17 static asset destination is `web/dist`, served by `api/static.py` — the spec and Task 16 both name `web/dist`, while `api/static.py` and `api/static/dist` cannot coexist on Windows — if wrong, Task 17's Vite configuration and Task 19's copy path require a small coordinated change.
- Ruling: Task 12 uses `interrupted` as the canonical terminal status for a user stop; `STOPPED` may exist only as a legacy migration alias, never as new public evidence — the binding spec enumerates `interrupted` and demands one stable state machine — if wrong, lifecycle/API compatibility tests need an alias adjustment.
- Ruling: Task 1's generated `environment.json` remains runtime evidence and is not part of commit `c408917` — the plan's own commit command excludes it and current-evidence rules require regeneration — if wrong, the file can be allowlisted and committed after sanitization.
- Ruling: When Task 17 commands run from `web/`, Playwright's plan-relative path is `tests/judge-flow.spec.ts`, while repository-root invocation may use `web/tests/judge-flow.spec.ts` — this preserves the intended test rather than the contradictory working-directory spelling — if wrong, only the package script/test command needs adjustment.

## Task 1 review loop

- Task 1 review: spec failed with two Important findings: canonical `output/evidence/release-baseline/environment.json` absent from the review diff; nested archive metadata used `present`/`missing` values under a field named `status`.
- Ruling: supersede the earlier Task 1 snapshot ruling after independent review — commit the canonical `environment.json` in a separate evidence commit after the code fix commit, so `environment.git_commit` points to stable generating code rather than attempting an impossible self-referential commit — if wrong, the snapshot commit can be removed while retaining the reproducible generation command.
- Task 1: fix round 1/5 (2 addressed, 0 open; commits `c408917..b8576f5`).
- Task 1: complete (commits `eb32507..b8576f5`, review clean).

## Task 2 implementation

- Task 2 recovered RED: import failed because `scripts.release.output_policy` did not exist.
- Task 2 initial GREEN attempt: `15 passed, 7 failed`. Six failures came from positive test paths being nested under pytest's repository-local `output/tmp` root, so the outer disposable-output prefix contaminated classification; the seventh was a fixture error calling `read_bytes()` on dictionary string keys.
- Ruling: `is_release_path()` classifies repository-relative policy paths (plus the absolute protected paths returned by `preserved_source_paths`); positive non-protected policy examples in tests use `Path(relative_path)` rather than a pytest temp-root prefix — adding test-runner-specific path stripping to production would make the release boundary ambiguous — if wrong, Task 21 should deepen the API to `is_release_path(repo_root, path)` and migrate callers explicitly.
- Ruling: Task 3 registers `classic_maxpressure` as a canonical formal identity with an explicit unavailable factory/capability until Task 9 supplies the independent algorithm; it must never alias to `actuated` or the capacity-aware implementation — Task 3 mandates the identity before Task 9 implements the behavior, and false substitution would corrupt every later result — if wrong, Task 3/9 registry tests and the API availability field require coordinated revision.
- Task 2: fix round 1/5 (3 addressed, 1 open — `development-route` remains releasable; commits `91b468e..0beddac`).
- Task 2: fix round 2/5 (1 addressed, 0 open — `development-route` excluded and regression-tested; commits `0beddac..b09a958`).
- Task 2: complete (commits `b8576f5..b09a958`, scoped re-review clean; fresh focused `27 passed`, full suite `243 passed`).
- Task 2 regression re-opened by Python rerun: Task 1-6 focused suite produced `1 failed, 186 passed`; `node_modules/package/index.js` was misclassified because `_normalized_parts()` converts `_` to `-` while `_CACHE_COMPONENTS` retained `node_modules`.
- Task 2 regression fix: changed the normalized cache component to `node-modules`; focused `tests/test_output_policy.py` returned `27 passed`; commit `7c15d82` (`fix: classify normalized node modules cache`).

## Task 3 implementation

- Task 3 RED: registry module absent; expanded entrypoint migration RED produced `5 failed, 33 passed`; canonical-request boundary RED produced `1 failed, 21 passed`.
- Task 3 implementation commit: `e265ed7` (`refactor: centralize algorithm registration`), based on `b09a958`.
- Task 3 final focused verification: `86 passed`; final full suite: `261 passed`, no warnings.
- Task 3 protected-input verification: archive SHA-256 remains `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`; official scene data remains 163 tracked files; neither protected path appears in the diff.
- Task 3 review: independent task review dispatched for `b09a958..e265ed7`; completion pending both spec-compliance and task-quality approval.
- Task 3 review finding: reviewer treated canonical optional `actuated` as migration-only and requested removal from new requests and `/api/algorithms`.
- Ruling: retain `actuated` as a canonical optional algorithm in the full registry, optional API list, and explicit non-formal runs, while excluding it from `formal_only`, formal matrices, and the judge quick workflow — Task 3 explicitly says it remains non-formal rather than becoming an alias, and Task 16 explicitly requires `/api/algorithms` to return canonical formal and optional algorithms; `rule_adaptive` is the migration-only alias — if wrong, the optional API response, `RunRequestModel` literal, experiment CLI choices, and related tests must all remove `actuated` together.
- Task 3 review clarification: returned the exact Task 3 and Task 16 plan clauses to the original reviewer; revised verdict pending.
- Task 3 revised review: spec compliant and task quality approved; no Critical, Important, or Minor findings. The reviewer withdrew the `actuated` finding after checking the canonical-optional contract.
- Task 3 controller verification of review caveats: focused `86 passed` and full `261 passed` were executed on `e265ed7`; 540-run evidence, frontend offline assets, and frame-failure isolation are explicitly assigned to Tasks 17/22/23 and are not Task 3 gaps.
- Task 3: complete (commits `b09a958..e265ed7`, independent review clean).

## Task 4 implementation

- Task 4 started from `e265ed7`; brief: `.superpowers/sdd/2026-08-18-judge-facing-final-release/task-4-brief.md`.
- Task 4 boundary: add immutable movement contracts and API adapters only; preserve `queues` and `phase_states` compatibility, and defer TraCI extraction to Task 8.
- Task 4 implementer: `/root/task4_implementer`; TDD implementation and commit in progress.
- Task 4 implementation commit: `597343c` (`feat: add movement-level traffic state contract`), based on `e265ed7`.
- Task 4 implementer verification: focused `14 passed`; full suite `272 passed`; output pristine.
- Task 4 protected-input verification: archive hash unchanged; official scene data remains 163 tracked files; neither protected path appears in `e265ed7..597343c`.
- Task 4 review: independent task review dispatched for `e265ed7..597343c`; completion pending both verdicts.
- Task 4 review: spec failed with two Critical findings and one Important finding: fractional/non-integer `phase_index` accepted; mutable lists can bypass tuple/immutable movement contracts; zero `nominal_duration` accepted.
- Task 4: minor (deferred): direct domain numeric validation accepts float-convertible strings and booleans without normalizing the stored value.
- Task 4: minor (deferred): Ruff is configured but not installed in the project virtual environment, so static lint was not run.
- Task 4 fix round 1/5 dispatched to `/root/task4_implementer`; fix base `597343c`.
- Task 4 fix round 1 implementation: RED `11 failed, 14 passed`; focused GREEN `25 passed`; full suite `283 passed`; commit `7607499` (`fix: enforce movement phase invariants`).
- Task 4 fix round 1 scoped re-review dispatched for `597343c..7607499` with reviewer `/root/task4_rereview`.
- Task 4: fix round 1/5 (3 addressed, 0 open; commits `597343c..7607499`).
- Task 4: complete (commits `e265ed7..7607499`, scoped re-review clean; focused `25 passed`, full suite `283 passed`).

## Task 5 implementation

- Task 5 started from `7607499`; brief: `.superpowers/sdd/2026-08-18-judge-facing-final-release/task-5-brief.md`.
- Ruling: Task 5 establishes the seconds-first time contract, configuration defaults, API/request construction, and explicit step-compatibility behavior, but defers scene-manifest `step-length` resolution, runner termination, and atomic `manifest.json` persistence to Tasks 12-13 - those later tasks own the validated scene, lifecycle, and evidence interfaces that do not yet exist, while Task 5's listed files exclude them - if wrong, Task 12-13 will need to preserve or migrate an earlier provisional manifest/lifecycle implementation.
- Task 5 implementation commit: `2636d16` (`fix: express simulation windows in simulation seconds`), based on `7607499`.
- Task 5 implementer verification: focused `50 passed`; full suite `292 passed`; protected archive hash unchanged; official scene data remains 163 tracked files.
- Task 5 review: spec found one Important issue and two residual issues. The current default request path passes `steps=None` into `RunService`, whose legacy runner silently falls back to 36000 steps instead of deriving from the scene step length; `scenes/variant.py` retains a 1.5 high-traffic fallback; CLI duration validation lets NaN pass the comparison stage. The primary issue is load-bearing because it makes the new seconds-first contract ineffective for real runs.
- Ruling: extend Task 5 by adding the smallest boundary bridge needed to derive explicit steps from the validated scene/config step length (and reject silent universal fallback), while leaving full seconds-based runner termination, lifecycle state, and atomic evidence manifests to Tasks 12-13 - the existing chain is already callable today and otherwise runs the wrong duration; if wrong, the bridge can be removed when the lifecycle contract lands.
- Task 5: fix round 1/5 dispatched to `/root/task5_implementer`; fix base `2636d16`.
- Task 5 fix round 1 implementation: RED `8 failed, 6 passed`; focused GREEN `14 passed`; focused regression `69 passed`; full suite `301 passed`; commit `4d3cb19` (`fix: resolve scene step-length run bridge`).
- Task 5 fix round 1 scoped re-review dispatched for `2636d16..4d3cb19`.
- Task 5: fix round 1/5 (3 addressed, 0 open; commits `2636d16..4d3cb19`).
- Task 5 controller final verification: focused `69 passed`; full suite `301 passed`; `git diff --check` clean; protected archive hash remains `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`; official scene data remains 163 tracked files; neither protected path appears in the task diff.
- Task 5: complete (commits `7607499..4d3cb19`, scoped re-review clean).

## Task 6 implementation

- Task 6 started from `4d3cb19`; brief: `.superpowers/sdd/2026-08-18-judge-facing-final-release/task-6-brief.md`.
- Ruling: `SceneRegistry.list_scenes()` changes to the required immutable tuple of `SceneManifest` values, while `get_scene()` and `get_meta()` remain compatible runtime interfaces; direct current consumers must continue to work until Task 16 replaces the public API response with full manifests - the new registry contract is binding but breaking existing run construction would stall later tasks - if wrong, Task 16 can remove the compatibility display properties/adapters.
- Ruling: Task 6 treats controlled net connections with valid incoming/outgoing lane references as the structural movement mapping and fails scenes with no usable controlled movements; Task 8 remains responsible for live TraCI `getControlledLinks()` extraction and reconciliation - XML is the only available preflight source in this task - if wrong, Task 8 will need to tighten formal eligibility after live reconciliation.
- Task 6 implementer: `/root/task6_implementer`; TDD implementation and commit in progress.
- Task 6 official-source preflight: all 20 scenes contain net/flow/route/turn/sumocfg/timing inputs and at least one TLS plus six controlled connections; scenes 1-10 and 14 use SUMO's default 1.0-second step, while scenes 11-13 and 15-20 declare 0.1 seconds.
- Task 6 implementation commit: `17efada` (`feat: validate and package SUMO scenes`); initial focused suite `20 passed`.
- Task 6 independent review: two Critical findings (flow route references/connectivity and TLS `linkIndex`/phase-state coverage), one Important finding (imported manifest paths were not package-relative), plus two Minor coverage/error-boundary findings.
- Task 6 fix round 1/5: commit `6e3d148` (`fix: harden scene manifest validation`), based on intervening controller regression fix `7c15d82`; all six findings addressed in `scenes/validator.py`, `scenes/importer.py`, and `tests/test_scene_validation.py`.
- Task 6 controller final verification: focused `31 passed`; full suite `317 passed`; 20/20 official scenes pass with exact source warnings; Python 3.14.7 compileall passed; project Python 3.12.13 preflight passed with SUMO/TraCI 1.27.1; Docker remained `not_run` because no CLI was available.
- Task 6 protected-input verification: archive SHA-256 remains `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`; official scene data remains 163 tracked files; no protected path appears in the task range.
- Task 6 scoped fix re-review: all four blocking findings ADDRESSED; no new Critical/Important breakage in `17efada..6e3d148`. The intervening Task 2 regression commit `7c15d82` was correctly treated as out of scope.
- Task 6: complete (commits `4d3cb19..6e3d148`, including separate Task 2 regression commit `7c15d82`; review findings resolved and fresh controller verification clean).

## Task 7 implementation

- 状态：独立审查未通过，修复第 1 轮进行中。
- 2026-08-19 Python 现场复核：系统解释器 `C:/Users/peng/AppData/Local/Programs/Python/Python314/python.exe` 为 Python 3.14.7，但未安装 pytest；项目解释器 `.venv/Scripts/python.exe` 为 Python 3.12.13，pytest 8.4.2 可用。后续项目验证继续显式使用项目解释器，系统解释器用于兼容性检查。
- 2026-08-19 Python 新鲜复验：系统 Python 3.14.7 对 `api core engine scenes scripts experiments tests` 执行 `compileall` 通过；项目 Python 3.12.13 全量 pytest 使用短 basetemp 后为 `324 passed in 33.10s`。
- 2026-08-19 protected/runtime refresh：`赛题资料.7z` SHA-256 仍为 `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f` 且保持未跟踪/未暂存；`data/intersection_data` 仍为 163 个跟踪文件且无任务差异；SUMO 与 jtrrouter 均为 1.27.1。
- Task 7 独立规范/质量审查已派发；在审查通过或修复闭环前保持进行中。
- Task 7 independent review: spec failed with three Critical and four Important findings. Critical: the real run path layers the scaled flow over the parent `.rou.xml`, event demand references undefined vType `passenger` and fails SUMO startup, and construction/vehicle_failure share one lane-closure implementation while ignoring intensity. Important: `validate_variant()` does not structurally validate every additional XML/reference, `<vehicle>` inputs are not transformed, provenance may contain personal absolute paths, and tests do not execute the three disturbances in SUMO or prove distinct intensity semantics.
- Task 7 fix round 1/5 dispatched to `/root/task7_implementer`; fix base `9439f92`. TDD must first reproduce the final one-population configuration, valid event route/vType, distinct intensity-bearing disturbance semantics, all-additional validation, mixed flow/vehicle transformation, and portable provenance; real SUMO short smokes are required before completion.
- TODOLIST 7/24：修复保留源数据的交通与扰动变体。新增三个可审计扰动：施工占道、大型活动需求、车辆故障车道阻塞；维持既有 VariantSpec/RunService 通道兼容。
- TDD RED 1：`tests/test_disturbances.py` 首次收集失败，缺少 `DisturbanceSpecModel`。
- TDD GREEN 1：实现 domain/API 合同、确定性文件生成和变体验证后，`tests/test_disturbances.py tests/test_variants.py` -> `11 passed`。
- TDD RED 2：大型活动 additional 文件回归测试失败，缺少可引用 route。
- TDD GREEN 2：增加确定性 `event_demand_route` 后，指定回归 `tests/test_disturbances.py tests/test_variants.py tests/test_run_models.py tests/test_api.py tests/test_run_service.py` -> `38 passed`。
- 官方预检：20/20 个正式场景均成功生成 1.25 倍施工变体，输出仅在 `.superpowers/.../task7-official-variants`。
- 保护输入：`赛题资料.7z` SHA-256 仍为 `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`；`data/intersection_data` 无 diff。
- 全量回归：`pytest -q -p no:cacheprovider --basetemp=.../pytest-task7-full-final3` -> `324 passed in 35.17s`。
- 提交：`9439f92` (`feat: add auditable traffic disturbances`)。

## Task 7 review fix round 1

- 状态：scoped re-review 未通过，修复第 2 轮进行中。
- 根因：变体 flow 通过 `-a` 叠加到父 sumocfg 的原始 `.rou.xml`，真实 SUMO 同时加载两套需求。
- 修复：从唯一缩放 flow 用 jtrrouter 派生 `derived_demand.rou.xml`；临时 `variant.sumocfg` 仅引用该路由；RunService/Runner 显式使用该配置；flow 不再作为 additional 文件。
- 扰动：construction、event_demand、vehicle_failure 现在是不同且可执行的 XML；强度分别控制封道时长、额外需求率和安全停车时长；活动 vType/route 均可解析。
- 验证：三类真实 SUMO smoke 均 exit 0、stderr 空；聚焦 `73 passed`；全量 `335 passed`；Python 3.14.7 compileall exit 0。
- 保护输入：压缩包 SHA-256 不变，官方数据 163 Git 跟踪文件，保护路径无 diff。
- 提交：`dede66f` (`fix: isolate derived variant demand`)。
- 台账提交：`662b046` (`docs: record task 7 review fix evidence`)。
- Task 7 fix round 1/5：原 7 项发现中 5 项 ADDRESSED、2 项 NOT ADDRESSED；修复 diff 新增 3 项 Important 回归，合计 5 项开放。开放项为：全 additional/runtime XML 验证仍漏掉嵌套 calibrator flow、closingLaneReroute 和配置实际路径；对应测试未覆盖这些语义；event_demand 的 intensity 同时缩短时间窗和缩放流率造成平方缩放；固定 `variant.sumocfg` 使 TraCI 无法恢复路口编号与 edge mapping；删除父配置 `<output>` 使原有 queue-output 场景丢失队列证据。修复范围 `9439f92..dede66f`。
- Task 7 fix round 2/5 已派回 `/root/task7_implementer`；必须先用真实行为测试逐项复现上述 5 个开放问题，再修复并重新执行聚焦、全量、真实 SUMO smoke、Python 3.14.7 compileall 与保护输入校验。
