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

## Task 7 review fix round 2

- 状态：修复实现与现场验证完成；保持 Task 7，不开始 Task 8。
- Python 环境复核：系统 `python`/`py` 指向 Python 3.14.7（`C:/Users/peng/AppData/Local/Programs/Python/Python314/python.exe`）；项目 `.venv/Scripts/python.exe` 为 Python 3.12.13。项目 pytest 使用虚拟环境，系统 Python 用于 compileall 兼容性检查。
- 根因修复：完整校验嵌套 demand、引用、区间、from/to/depart、route 连通性、rerouter/calibrator/closing/stop 目标和 sumocfg 实际路径；拒绝配置内 additional-files。
- 强度语义：event_demand 保留完整声明时间窗并仅缩放流率；construction 与 vehicle_failure 分别缩放封道/停车时长。
- 运行链路：派生配置名保留 `demo_<id>`，RunService -> SimulationRunner -> TraCIBridge 可恢复 edge mapping；父 `<output>` 原样保留，scene 11 queue-output 继续重定向至运行 artifacts。
- TDD RED/GREEN：首轮 `12 failed, 18 passed` -> `30 passed`；配置/映射轮 `4 failed` -> `4 passed`；端点/depart/连通性轮 `4 failed, 30 deselected` -> disturbances 完整 `34 passed`。
- 真实 SUMO：施工车道权限在窗口内激活并在期后恢复；活动 calibrator 在旧缩短窗口之后仍保持 `180 veh/h` 至声明 end；故障车辆真实进入 stopped 状态；`3 passed`。
- 最终验证：聚焦 `74 passed in 47.23s`；全量 `354 passed in 74.28s`；系统 Python 3.14.7 compileall exit 0；`git diff --check` 通过。
- 保护输入：压缩包 SHA-256 不变并保持未跟踪/未暂存；官方数据仍为 163 个 Git 跟踪文件且无任务差异。
- 修复提交：`08b7be1` (`fix: validate executable disturbance bundles`)。
- Task 7 fix round 2/5：3 项 ADDRESSED，3 项开放。仍开放：缺失 route/完整时间字段、负 begin、重复中间 flow ID 和空 rerouter edges 可绕过校验；对应测试覆盖不足；vehicle depart 校验错误拒绝 SUMO 合法符号值。修复范围 `3d5eb1a..0ef4826`。
- Task 7 fix round 3/5 已派回 `/root/task7_implementer`；必须先用失败测试复现全部剩余边界和合法符号 depart，再做最小修复并重新执行聚焦、全量、真实 SUMO smoke、Python 3.14.7 compileall 与保护输入校验。

## Task 7 review fix round 3

- 状态：修复实现与现场验证完成；保持 Task 7，不开始 Task 8。
- 校验闭环：拒绝 calibrator flow 缺失 route/区间、负 begin、重复中间 demand ID 和空 rerouter edges。
- SUMO 1.27.1 schema 裁定：合法符号 depart 为 `triggered`、`containerTriggered`、`split`、`begin`；复审举例中的 `now` 不属于本机版本 `departType`，未接受。
- TDD RED/GREEN：旧基线重放 `9 failed, 9 passed, 29 deselected`；当前 `tests/test_disturbances.py` 为 `47 passed`。
- 最终验证：聚焦 `87 passed in 60.24s`；全量 `367 passed in 86.35s`；系统 Python 3.14.7 compileall exit 0；SUMO/jtrrouter 1.27.1；diff check 通过。
- 保护输入：压缩包 SHA-256 不变并保持未跟踪/未暂存；官方数据仍为 163 个 Git 跟踪文件且无任务差异。
- 修复提交：`e5e9d44` (`fix: close disturbance validation gaps`)。
- Task 7 fix round 3/5：3 项 ADDRESSED，0 项开放；未发现新的 Critical、Important 或 Minor 问题；提交范围 `e0411e5..314fe00`。
- Task 7：完成（提交范围 `6e3d148..314fe00`，独立复审 clean；聚焦 `87 passed`，全量 `367 passed`）。

## Task 8 implementation

- 状态：进行中；从提交 `9ba0a61` 开始，先执行 movement 状态、安全事件和指标单位的 TDD RED。
- TODOLIST 8/24：实现 movement 到合法 phase 的映射与正容量快照，采集碰撞、红灯违规、非法相位转换、急减速、瞬移和潜在冲突，并严格分离完成/未完成车辆；燃油固定为 ml、CO2 固定为 g。
- Task 8 旧基线：`tests/test_movements.py tests/test_metrics.py tests/test_traci_outputs.py tests/test_vehicles.py` 为 `46 passed`。
- TDD RED/GREEN 1：接口骨架后的行为级 RED 为 `11 failed, 18 passed`；实现 movement 拓扑缓存/动态快照、六类安全事件、完成车辆指标和体积燃油开关后为 `29 passed`。
- TDD RED/GREEN 2：真实 TraCI、事件和元数据接线 RED 为 `5 failed, 28 passed`；接入精确仿真时间、安全快照、turn.xml、runner 事件与容量参数后为 `33 passed`。
- TDD RED/GREEN 3：占有率单位、车辆观测转向、内部车道红灯穿越和不可变安全字段 RED 为 `4 failed, 34 passed`；修复后相关回归为 `42 passed`。
- 单位裁定：本机 SUMO 1.27.1 文档确认 `CO2_abs` 为 mg，汇总除以 1000 转为 g；运行命令显式设置 `--emissions.volumetric-fuel true`，将 `fuel_abs` 冻结为 ml。
- 真实 SUMO movement 预检：20/20 官方场景均可启动并读取 movement 快照；所有含绿灯相位均有 movement，所有 movement 的进口与下游容量均大于零。
- TDD RED/GREEN 4：唯一 movement 比例回退、缺失信号状态和跨 run_id 事件保护为 `3 failed, 19 passed`，最小修复后为 `22 passed`。
- 计划指定聚焦验证：`tests/test_movement_state.py tests/test_safety_metrics.py tests/test_traci_outputs.py tests/test_vehicles.py` 为 `40 passed in 1.76s`。
- 全量验证：首次发现 3 个旧 TraCI 启动替身未镜像新 movement 查询，补全真实结构后全量为 `389 passed in 90.79s`。
- 真实 RunService 冒烟：路口 1、fixed_time、100 步、seed 42 完成；run_id `43745c374ed1`，容量参数与 events.csv 安全字段落盘，tripinfo 非空。
- Task 8 自审修复第 1 轮：真实 fixed_time 冒烟的 4 条红灯记录均发生在相位同一步由红转绿，确认为误报；另发现最后一个仿真步的安全状态未刷新。回归 RED `3 failed, 18 passed`，修复前后相位双重校验与终态补采后为 `21 passed`。
- Task 8 修复后真实冒烟：路口 1、fixed_time、100 步、seed 42 完成；run_id `67e3a3add44f`，`red_light=0`，急减速和潜在冲突观察事件继续落盘。
- Task 8 自审修复验证：扩展聚焦 `70 passed in 2.15s`；全量 `392 passed in 89.63s`；系统 Python 3.14.7 compileall 与 diff check 均为 exit 0；保护输入保持不变。

## Task 8 review fix round 1

- 状态：独立审查未通过，修复第 1 轮进行中；保持 Task 8，不开始 Task 9。
- 审查结论：0 项 Critical、7 项 Important、2 项 Minor；其中未完成车辆 raw output 分离按计划属于 Task 13，本轮不越界修改，其余 8 项均为 Task 8 开放问题。
- 开放 1：按每条 incoming lane 对唯一合法 movement 的 turn ratio 归一化；官方场景 19 的 `-E2.41_0` 当前比例和为 1.4，且其余场景也存在比例和不为 1。
- 开放 2：为动作拒绝增加结构化 reason code，不能把 TLS ID/索引等普通参数错误记成非法相位转换；同时从真实前后信号状态独立检测绿到绿非法跳转。
- 开放 3：红灯检测排除黄色，并使用 `speed * elapsed + margin` 的跨线窗口覆盖 1.0 秒和 0.1 秒步长。
- 开放 4：从 `.net.xml` 的 junction `request/foes` 建立冲突 movement 对，并对连续 potential-conflict 按 episode 去重。
- 开放 5：增加 run-scoped `collisions.xml`，使用 `traci.simulation.getCollisions()` 保留 collider/victim 配对。
- 开放 6：区分 teleport starting/ending，同一车辆同一 episode 只计一次。
- 开放 7：`SafetyEvent` 保存真实 simulation step，避免 0.1 秒场景的 `1.2 s` 被错误记录为 step 1。
- 开放 8：成功 `set_program` 后原子重建 movement builder，避免 program 切换后拓扑过期。
- Task 8 fix round 1/5：严格执行逐项 TDD RED/GREEN；修复后必须重新运行计划聚焦、扩展聚焦、全量测试、20 场景 movement 预检、100 步真实 RunService 冒烟、Python 3.14.7 compileall、保护输入校验和原审查者 scoped 复审。
- TDD RED 1：movement 比例、碰撞配对/原始文件、teleport episode、结构化拒绝原因、真实 step、黄灯/动态跨线窗口、foes 冲突去重和 program 重建共 `33 failed, 29 passed`。
- TDD GREEN 1：实现首轮修复后同组测试为 `62 passed`；扩展聚焦为 `114 passed`。
- 全量回归 1：`399 passed, 4 failed`；4 项均为旧实验完成性夹具未生成新增必需的 `collisions.xml`，更新完整产物夹具后相关回归 `32 passed`。
- TDD RED/GREEN 2：为无 internal-link 网络、无几何交点的 foes、真实合法 phase 图、当前 phase 查询失败、program 重建回滚及切换后观测边界增加行为测试；失败均按预期复现，最小修复后的边界回归通过。
- 官方 `.net.xml` 冲突预检：20/20 场景均从 junction `request/foes` 生成非空冲突定义；路口 11 无 internal links，使用进口停止线到出口起点的只读几何回退。
- 2026-08-20 接续验证：计划聚焦 `58 passed in 1.75s`；扩展聚焦 `119 passed in 3.01s`；全量 `408 passed in 77.33s`。
- 2026-08-20 加严 20 场景预检在场景 13 发现 request/foes 到 TLS link 的索引映射缺口：`junction/request@index` 按 `intLanes` 编号，而该场景受控 `connection@linkIndex` 为 `0,2..9`，当前实现错误假定两者恒等，导致涉及实际 linkIndex 9 的 5 个 foes 对未生成并可能错配其他定义。
- Task 8 fix round 1 补充 RED/GREEN：先用场景 13 风格网络夹具证明 request 内部车道索引必须映射回受控 linkIndex，再做最小修复；完成后重跑聚焦、全量、20 场景全部可映射 foes 覆盖、真实 RunService 冒烟及保护输入校验。
- Task 8 request/linkIndex TDD：新增两段内部连接链且 request 索引 `0,1` 对应受控 linkIndex `7,9` 的行为夹具；修复前 `1 failed, 30 deselected`，最小映射修复后 `1 passed, 30 deselected`，相关聚焦 `55 passed`。
- Task 8 控制器最终验证：计划聚焦 `59 passed in 1.73s`；扩展聚焦 `120 passed in 2.98s`；全量 `409 passed in 86.28s`。
- Task 8 真实 20 场景 TraCI 预检：20/20 均启动成功，全部 movement 容量为正、每条 incoming lane 的 turn ratio 和为 1、每场景冲突定义非空；独立映射的 797 个 request/foes 对与 797 个 `ConflictDefinition` 完全一致，所有 SUMO 输出均重定向到 `.t8-controller-preflight-final` 的 run-scoped 目录。
- Task 8 真实 RunService 冒烟：路口 1、`fixed_time`、100 步、seed 42，run_id `a9aaca9ee48b`，状态 `completed`，终态 100.0 秒；`collisions.xml` 2064 bytes、`events.csv` 4730 bytes，安全事件 step 均与真实步对应，`red_light=0`、`illegal_transition=0`，急减速 27、潜在冲突 9 作为观察事件保留。
- Task 8 最终兼容/保护校验：系统 Python 3.14.7 `compileall` exit 0；`git diff --check` exit 0；`赛题资料.7z` SHA-256 仍为 `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`；官方数据仍为 163 个 Git 跟踪文件且保护路径无 diff。
- Task 8 fix round 1 scoped 独立复审：9 项开放问题全部 ADDRESSED，0 项开放，未发现新的 Critical/Important breakage；未完成车辆 raw output 分离明确保留给 Task 13，不阻塞本任务；审查者只读环境因无可写临时目录未能额外执行 pytest，控制器在同一 HEAD 上的计划聚焦 `59 passed`、扩展聚焦 `120 passed`、全量 `409 passed` 证据继续有效。
- Task 8: fix round 1/5 (9 addressed, 0 open; commits `76f76d6..335bc3d`).
- Task 8: complete (commits `9ba0a61..335bc3d`, scoped re-review clean; 20/20 official TraCI preflight and controller verification clean).

## Task 9 implementation and review

- 状态：独立审查未通过，修复第 1 轮准备派回原实现单元；保持 Task 9，不开始 Task 10。
- TODOLIST 9/24：冻结可追溯且实际生效的 fixed timing baseline，并实现独立、可执行且不混入容量感知增强的 classic MaxPressure。
- Task 9 基线 `8b49d25`；实现提交 `30f8ca8` (`feat: freeze fixed timing and classic MaxPressure baselines`)。
- TDD 证据：行为 RED `5 failed, 2 passed`；首轮 GREEN `7 passed`；非法 Excel、来源可移植性和注册表边界补强后聚焦 `28 passed, 1 warning`；实现单元最终全量 `420 passed, 1 warning in 79.94s`，系统 Python 3.14.7 compileall exit 0。
- 控制器聚焦验证：`tests/test_fixed_time_plan.py tests/test_classic_max_pressure.py tests/test_algorithms.py tests/test_algorithm_registry.py tests/test_api.py` 为 `39 passed in 9.13s`；20/20 官方场景均解析为 `official_excel` 且 source hash、program ID、phase 非空。
- 控制器 fixed_time 真实冒烟：路口 1、100 步、seed 42，run_id `3e1c8d002d81`，状态 completed；但 resolver 声明 Excel 逻辑 phase 时长 `[43, 37, 37, 43]`，SUMO 实际仍运行 net program `0` 的 6 个 phase `[42, 3, 15, 3, 38, 3]`，证明 provenance 与实际 baseline 脱节。
- 控制器 classic 真实冒烟：长审查目录首次因 Windows 派生配置路径过长而在算法启动前失败；改用短目录 `.t9c` 后路口 1、100 步、seed 42，run_id `8b7032241468`，状态 completed，但 action applied 12、action rejected 88、illegal_transition 88，当前实现不能作为有效安全基线。
- Task 9 独立审查：2 Critical、2 Important、1 Minor。Critical：resolved fixed plan 仅写 manifest、未应用到 SUMO；Runner 在 `bridge.start()` 后才 `algorithm.init()`，非法计划不是启动前失败。Important：classic 每 tick 重发 `set_phase` 且忽略 elapsed time，真实执行大量非法拒绝；删除 fixed_time init 的旧测试使断言空泛。Minor：全量输出含 1 个受保护 cache warning，不是 pristine。
- Task 9 fix round 1/5 要求：先以行为测试复现 fixed provenance/实际 program 脱节、启动前验证、classic 真实合法执行和非空 fixed init 契约；再做最小修复，重新运行聚焦、全量、20 场景 resolver、fixed/classic 100 步真实 SUMO、Python 3.14.7 compileall、保护输入校验和 scoped re-review。

## Task 9 review fix round 1

- 修复提交：`ca5b003` (`fix: apply frozen fixed timing baselines`)。fixed_time 通过共享 `set_program` 动作安装冻结 program definition，TraCI 使用 `setProgramLogic` 激活并原子重建 movement 拓扑；算法初始化前移到 SUMO 启动之前；classic 仅在非当前、直接合法且当前 phase 已满足 nominal duration 时发出切换动作。
- TDD RED/GREEN：覆盖空 Excel state、fixed 不发动作、classic 自相位/过早动作、缺失 program payload 与 runner 晚初始化，RED 为 `6 failed, 63 passed`；最小修复后同组 `69 passed`。
- 实现单元最终验证：全量 `424 passed in 122.74s`、无 warning；20/20 官方场景均解析为 `official_excel`；fixed/classic 各 100 步真实 SUMO 完成且均为 0 rejected、0 illegal transition；系统 Python 3.14.7 compileall 通过。
- 控制器 fresh 聚焦验证：`tests/test_fixed_time_plan.py tests/test_classic_max_pressure.py tests/test_algorithms.py tests/test_traci_outputs.py tests/test_runner_channel.py` 为 `69 passed in 1.89s`。
- 控制器 fresh 全量验证：`pytest -q -p no:cacheprovider --basetemp=.t9c/controller-pytest-full` 为 `424 passed in 81.98s`，无 warning。
- 控制器 20 场景与直接 TraCI：20/20 resolver 均为 `official_excel` 且 hash/program/phases 非空；路口 1 fixed 运行 100 步后 active program ID 和全部 12 个 `(duration, state)` 与冻结 plan 完全一致，1 applied、0 rejected；classic 100 次决策目标覆盖 `{0,2,4}`，1 applied、0 rejected。
- 控制器 RunService 真实冒烟：fixed run `bbb2b8e36219`、classic run `6c70ae4c0e02`，均为 `completed`、终态 100.0 秒、1 applied、0 rejected、0 `illegal_transition`。
- 控制器兼容/保护校验：系统 Python 3.14.7 compileall 与 `git diff --check` 均为 exit 0；`赛题资料.7z` SHA-256 仍为 `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`；官方数据仍为 163 个 Git 跟踪文件、232 个磁盘文件且保护路径无 diff。
- Task 9 fix round 1 scoped 独立复审：原 2 项 Critical、2 项 Important 和 1 项输出质量问题全部 ADDRESSED，0 项开放；未发现新的 Critical/Important breakage，也无 out-of-scope observation。
- Task 9: fix round 1/5 (5 addressed, 0 open; commits `30f8ca8..ca5b003`).
- Task 9: complete (commits `8b49d25..ca5b003`, scoped re-review clean; controller focused/full/20-scene/real-SUMO verification clean).

## Task 10 implementation

- 状态：进行中；基线为 `ca5be1b`，先为 M0-M4 分层得分、动态绿灯、预测单位/默认关闭和云边消息信封执行逐项 TDD RED。
- TODOLIST 10/24：将容量感知 MaxPressure 拆为可归因的 M0 经典压力、M1 容量归一化、M2 下游溢出保护、M3 共享安全执行边界和 M4 可选预测；输出逐 phase 得分明细，并冻结带 run/time/version/expiry 的云边消息合同。
- Ruling: Task 10 可最小修改 `algorithms/classic_max_pressure.py`，只增加计划明确要求的 `score_breakdown()` M0 对照接口 — Task 10 的接口清单要求该方法，但 Files 列表漏列该文件 — if wrong, 仅需把该小接口移回 Task 9 兼容提交并重放 Task 10 对照测试。
- Ruling: Task 10 必须把现有 `SimulationRunner` 的真实 EdgeChannel 调用迁移到 `EdgeMessage`，不得用 bare `JointState` 生产兼容分支绕过 run/time/version/expiry 合同 — 设计目标要求真实云边逻辑边界而非仅有未消费的数据类 — if wrong, runner 适配可回退为边界 adapter，但消息集成测试需要相应调整。
- Ruling: Task 10 的 M3 负责冻结可归因配置并继续通过现有共享 action/validation 通道输出动作，不在本任务复制完整 phase transition/fallback executor；该单一安全执行器仍由 Task 11 独占 — 计划的 Task 10 -> Task 11 handoff 明确后者拥有统一写信号路径 — if wrong, Task 11 需提前拆分并重新界定两项任务的审查范围。
- Task 10 实现提交：`4428ce3` (`feat: layer capacity-aware MaxPressure ablations`)；实现单元聚焦 `46 passed`、全量 `435 passed`、真实 100 步 SUMO completed，系统 Python 3.14.7 compileall 与保护项校验通过。
- Task 10 控制器验证：聚焦 `46 passed in 1.13s`；全量 `435 passed in 88.22s`、无 warning；带 EdgeMessage 延迟的真实 RunService run `fe7b8c7562e4` completed、2 次 channel wait、0 rejected、0 illegal；M0-M4/default flags、manifest、Python 3.14.7 与保护项均通过。
- Task 10 独立审查未通过：0 Critical、4 Important、0 Minor；规范 Issues found，质量 Needs fixes。开放项：容量仅在 live movement snapshot 时失败而非 capacity-aware 正式预检；动态绿灯分母把零/负 phase 计入“正压力平均”；EdgeMessage 不校验 active run_id/payload_version；M2/M3 manifest 不可区分且缺少逐 movement 分量、阻塞原因、选择理由和最终动作的可序列化审计记录。
- Task 10 reviewer `Cannot verify` 经控制器确认成为第 5 个 Important：`RunService` 把 `edge_delay_steps` 原样作为 `delay_seconds`。0.5 秒步长、2-step 延迟、5 tick 行为探针实际只交付 `[0]`，应交付 `[0,1,2]`；必须按实际 step length 换算并增加非 1.0 秒步长覆盖。
- Task 10 fix round 1/5：已准备派回原实现单元；必须逐项 TDD RED/GREEN，并重跑聚焦、全量、非单位步长 EdgeMessage、真实 SUMO、Python 3.14.7、保护项校验及 scoped 独立复审。保持 Task 10，不开始 Task 11。

## Task 10 review fix round 1

- 修复提交：`de258cd` (`fix: validate edge message evidence timing`)；修复范围 `4428ce3..de258cd`，包含启动前容量预检、严格正压力平均、消息 run/version 合同、M2/M3 归因审计、step 到仿真秒换算，以及消息时间/事件证据时间补强。
- 双轨 scoped 复审：原 5 个 Important 中容量预检和严格正压力平均为 ADDRESSED；run/version 绑定、可复原算法审计、非单位步长 override 行为仍为 NOT ADDRESSED。新增 3 个 Important：容量感知配置缺少有限值/安全区间校验、并列选择原因不可解释、非有限 EdgeMessage 时间可进入通道。
- 控制器复现：已绑定后的现有测试为 `3 passed`；未绑定 channel 先缓存 `run_id=stale` 再绑定 active run 后仍交付旧消息且无拒绝事件；`sent_at=-Inf` 和 `expires_at=+Inf` 均可交付；原 sumocfg 步长 1.0、override 0.5、delay 2 时 channel 为 1.0 秒但真实配置仍为 1.0 秒，实际只等待 1 tick；M4 的 `step()` 后预测调用为 1 次，随后生成 audit 增至 2 次，audit phase 0 总分 `0.775` 与记录的 movement pressure 和 `0.4` 不一致。
- 审计最终动作缺口：当前 algorithm audit 在 `apply_actions()` 前写入，不能记录共享执行边界的实际 applied/rejected 结果；round 2 只接线现有执行结果，不提前实现 Task 11 的统一安全执行器。
- Task 10: fix round 1/5 (2 addressed, 6 open; commits `4428ce3..de258cd`).
- Task 10 fix round 2/5：保持单一实现写轨；对 6 个开放 Important 逐项行为级 TDD RED/GREEN，随后执行控制器聚焦/全量/真实 SUMO/保护项门禁和双域 scoped 复审。Task 11 继续等待。

## Task 10 review fix round 2

- 修复提交：`273c9eb` (`fix: close capacity-aware review findings`)；实现单元聚焦 `104 passed`、全量 `484 passed`、20/20 官方容量预检、真实 100 步 EdgeMessage/SUMO run `bcf313da0b32` completed，Python 3.14.7 compileall 与保护项校验通过。
- 双域 scoped 复审：预绑定 run/version、真实 step override、配置有限值/安全区间和非有限 EdgeMessage 时间 4 项 ADDRESSED；legacy `phase_states` fallback 使可复原算法审计和并列理由 2 项 NOT ADDRESSED。消息/时间域未发现新的 Critical/Important。
- 控制器聚焦复跑：`104 passed in 10.43s`；但最小 legacy 探针复现同一 tick EWMA 从应有 `300` 二次推进到 `450`，实际 `set_phase=1` 而 audit 误记 `safe_fallback_all_blocked/no_action`。
- Task 10: fix round 2/5 (4 addressed, 2 open; commits `de258cd..273c9eb`).
- Task 10 fix round 3/5：恢复原实现单元，用单一 legacy fallback 根因测试同时锁定单次预测更新、真实动作审计和 deterministic tie 解释；不进入 Task 11。

## Task 10 review fix round 3

- 修复提交：`e792a1f` (`fix: freeze legacy capacity-aware decision snapshots`)；实现单元 RED 为 3 项预期失败，GREEN 为 3 项通过，扩大聚焦 `107 passed`、全量 `487 passed`、20/20 官方容量预检、真实 100 步 EdgeMessage/SUMO run `826f71073922` completed，Python 3.14.7 compileall 与保护项校验通过。
- scoped 独立复审：上一轮 legacy 单次 EWMA、真实动作/ActionResult 审计、deterministic tie 归因均为 ADDRESSED；新增 2 个 Important：公开观察接口通过父类 `step()` 提前提交控制状态，以及 pending transition wait/complete 的顶层原因无法精确区分。另有 1 个 Minor：无 phase states、无 green 与 all blocked 被压成同一原因。
- 控制器与三路只读交叉复核稳定复现观察污染：仅调用 `score_breakdown()` 或 `audit_record()` 就可令 `pending_target_phase` 从 `None` 变为 `2`，并推进 CloudPolicy EWMA/下发缓存；observer-first 与直接 `step()` 的后继动作不同，因此不是无害缓存。
- 控制器确认两个同源 Task 10 规范缺口：M3 manifest 为 `prediction_enabled=false`，legacy fallback 却写入预测历史；冻结 `max_green=30.0`，legacy audit 动作时长却为 `56.75675675675675` 且实例上限被父类下发改成 `90.0`。
- Task 10: minor (deferred): legacy 无 phase states、无 green 与 all blocked 的顶层原因折叠；交由最终 whole-branch review 复核是否必须在发布前关闭。
- Task 10: fix round 3/5 (2 addressed, 4 open; commits `273c9eb..e792a1f`).
- Task 10 fix round 4/5：切换到全新高能力实现单元；以纯 decision plan 和显式、幂等 commit 分离观察与提交，统一关闭 observer 污染、pending 原因、M3 预测开关越界和绿灯上限/manifest 漂移；先做行为级 RED，再做最小实现，不进入 Task 11。
- Ruling: Round 4 采用不可变 decision/cloud plan、内容指纹、owner + epoch + revision 和显式 commit；区分 pending/committed plan，`step()` 是唯一内部提交点，stale/跨 reset/跨 owner plan 必须拒绝 �� Round 3 的根因是观察接口执行有副作用状态机，保存恢复或继续复制判断树无法证明完整性 �� if wrong, 需要回退 `ca_max_pressure.py`/`cloud_policy.py` 的内部 seam 并重做 Round 4 行为测试，但不得把 bridge 动作去重提前放入 Task 10。

## Task 10 review fix round 4

- 修复提交：`45d92a6` (`fix: make capacity-aware planning transactional`)；7 组行为 RED 均按预期失败后 GREEN，最终 amended focused `74 passed`、expanded focused `125 passed`、全量 `505 passed`、20/20 官方容量预检、真实 SUMO run `d89343774b4f` completed（wait=2、audit=98、rejected=0、illegal=0），Python 3.14.7 与保护项门禁通过。
- 双域 scoped re-review：Round 4 的 4 个原始 Important 全部 ADDRESSED；新增 5 个 Important，分别是：更新 pending 存在时已提交 plan 的重复 commit 不再幂等；CloudPolicy/直接 CAMax 可在较新 commit 后重建旧历史；复合 cache 命中未验证嵌套 policy owner/epoch/revision；直接 `CAMaxPressureAlgorithm.step()` 重复同状态时重放旧动作而非保留旧兼容行为；planner 绕过公开可覆盖的 `phase_pressure()` 扩展 seam。
- 控制器源码核对确认 validator 顺序、history guard 缺失、nested cache 快返和静态 `_phase_pressure_for()` 调用均与审查证据一致；不提前进入 Task 11。
- Task 10: fix round 4/5 (4 addressed, 5 open; commits `e792a1f..45d92a6`).
- Ruling: supersede Round 4 中“同语义状态重复 `step()` 必须重复返回相同动作”的宽泛条款，仅对直接 `CAMaxPressureAlgorithm.step()` 保留修复前公开行为；内部重复 `commit_plan(plan)` 仍必须幂等，但 `step()` 可以基于已提交 controller state 重新规划并返回原本的 no-action �� Task 10 明确要求父控制器兼容，bridge 级重复动作控制仍属于 Task 11 �� if wrong, 只需调整 direct parent step 的 committed-plan reuse 策略，不得引入 executor 去重。
- Task 10 fix round 5/5：恢复 Round 4 的高能力实现单元，以 5 个新 Important 的行为 RED 补齐 validator 顺序、历史单调性、嵌套 policy 有效性、父 step 兼容和 scoring override seam；完成后必须再做 scoped 双域复审，Task 11 继续等待。
- Task 10 Round 5 实现提交：`3941a55` (`fix: close final max-pressure transaction gaps`)；实现报告记录 GREEN `9 passed`、amended focused `83 passed`、expanded focused `134 passed`、全量 `514 passed`、20/20 官方容量预检、真实 100 步 EdgeMessage/SUMO run `0af71d81ce6a` completed、Python 3.14.7 compileall、完整性和保护项门禁通过。恢复控制器在同一 HEAD 上重跑九项目标行为测试为 `9 passed in 0.49s`，提交范围与保护输入复核无变化。
- Task 10 Round 5 双域 scoped re-review：五个原始 Important 均为 ADDRESSED；事务/历史/嵌套生命周期复审未发现新 breakage。兼容/回归复审发现 1 个新的 Important：`CloudPolicy.predict(state)` 与 `dispatch_params(state)` 在同一 observation 上顺序调用时，第二个公共操作被 Round 5 历史 guard 误判为 `cloud_history_unavailable`。控制器双向探针稳定复现，且 `45d92a6` 无此限制；根因是 Cloud 层用包含 prediction/dispatch flags 的完整 plan key 判断历史变化，而 legacy 层只用 observation fingerprint。
- Task 10: fix round 5/5 (5 addressed, 1 new Important open — same-observation cross-operation CloudPolicy history regression; commits `45d92a6..3941a55`).
- Task 10: parked — same-observation sequential `CloudPolicy.predict()`/`dispatch_params()` raises `cloud_history_unavailable` — Ruling: this is a real public compatibility regression introduced by Round 5, but no Task 11 interface or current production algorithm depends on separate same-tick prediction and dispatch (production requests combined or one operation); the five-round breaker forbids a sixth Task 10 fix dispatch, so carry it explicitly to the final whole-branch review/fix wave rather than widening Task 11 — if wrong, a direct CloudPolicy consumer can fail before the final fix wave and must be repaired by narrowing the history guard to changed observation fingerprints while retaining the old-history tests.
- Task 10: complete (commits `ca5be1b..3941a55`, 1 parked; 1 prior deferred Minor remains for final review).

## Task 11 implementation

- 状态：进行中；基线为 `3941a55`，先从现有 `engine.action_validation`、`TraCIBridge.apply_actions()`、Runner 直接写入和 CA-MP transition 逻辑建立行为 RED，再集中到 `SafetyExecutor`。
- Ruling: Task 11 新建 `tests/test_action_validation.py`；计划 Files 表漏列该文件，但验收命令和 commit 清单都明确要求它，现有 validator 行为测试主要散落在 `tests/test_traci_outputs.py` — if wrong, 可把新增专属测试合并回现有测试文件而不改变生产接口。
- Ruling: Task 11 可最小修改 `engine/runner.py` 及其直接覆盖测试，把生产动作写入从 `bridge.apply_actions()` 改为 `SafetyExecutor.apply()` — `SafetyExecutor.apply()` 被定义为唯一信号写入路径，且计划的 Task 11 -> Task 12 handoff 明确要求 Runner 调用该路径 — if wrong, Runner 适配可单独回退，但“唯一生产写入路径”合同将无法成立。
- Ruling: Task 11 可最小修改 `algorithms/ca_max_pressure.py`；Step 2 明确要求移出其中的 transition sequencing，虽然 Files 表只列 classic/capacity wrappers — if wrong, 该迁移可回退为 executor 仅编排算法候选动作，但会保留重复 transition ownership。
- Task 11 实现提交：`ead4672` (`feat: enforce one safe signal action path`)；实现报告记录 required focused `35 passed`、affected `175 passed`、全量 `543 passed`、classic/capacity-aware 两个 100-step 真实 SUMO run、Python 3.14.7 compileall、唯一生产写入搜索和保护项门禁通过。
- Task 11 独立审查未通过：3 Critical、4 Important、0 Minor；规范 Issues found，质量 Needs fixes。Critical：绿色 `set_phase_duration` 可缩短最小绿；`set_program` 绕过全部时序/拓扑校验且抑制一次观察检查；合法图中的直接绿边可跳过黄灯/全红。Important：timing rejection 被写成 `illegal_transition` 硬门槛事件；`ControlAction` 无创建/到期合同；不安全 duration 被静默改写却对原动作返回 accepted；Runner 固定使用 10 秒而未接入权威场景/算法最小绿。
- Reviewer 的三个 `Cannot verify from diff` 项由控制器解决：实现报告中的 focused/affected/full 命令与结果完整可读；两个真实 run 的产物目录、run_id 和事件内容已读取；保护归档 SHA-256、官方数据 163/232 计数及保护路径零 diff 已在同一 HEAD 复核。这些不是额外规范缺口。
- 控制器真实证据核对：classic run `4706f6b5aaaa` 的 `events.csv` 含 70 条 `illegal_transition`，capacity-aware run `9b98fe664dfd` 含 72 条，均由 minimum-green/yellow timing rejection 派生；因此报告中“`illegal_phase_transition=0`”不能满足全局 `illegal_transition=0` 硬门槛，独立审查对应 Important 已确认。
- Task 11 fix round 1/5：恢复原实现单元；对 7 项开放 finding 逐项行为级 TDD RED/GREEN，补齐动作时效、绿色 duration、program 安全初始化、clearance 路径、fallback/审计语义和权威最小绿接线；修复后必须重跑 focused、affected、全量、fixed/classic/capacity-aware 真实 SUMO、Python 3.14.7、保护门禁和 scoped 独立复审。Task 12 继续等待。

## Task 11 review fix round 1

- 修复提交：`f7a823d` (`fix: close safety executor review gaps`)；实现报告记录 focused `115 passed`、affected `239 passed`、全量 `563 passed`，三路 100 步真实 SUMO 均完成，adaptive `illegal_transition=0`，Python 3.14.7 compileall、唯一生产写入搜索和保护项门禁通过。
- scoped 独立复审：原 7 项中 6 项 ADDRESSED；`set_program` 虽限制为启动阶段，但 program definition 仅校验正时长、信号字符和 state 长度，仍可安装短绿、直接绿到绿或缺少/过短黄灯与全红清空的计划，因此 1 项 Critical 仍 OPEN；未发现其他 Important/Minor。
- Task 11: fix round 1/5 (6 addressed, 1 open — startup program definition lacks independent minimum-green/yellow/all-red validation; commits `ead4672..f7a823d`).
- Task 11 fix round 2/5：恢复原实现单元，以短绿、缺失清空相位、黄灯/全红不足为行为 RED，完成 startup program 的独立安全校验并重跑覆盖测试、全量回归、fixed 真实 SUMO和保护项门禁；Task 12 继续等待。

## Task 11 review fix round 2

- 修复提交：`376689d` (`fix: validate startup signal programs`)；实现报告记录 focused `121 passed`、affected `245 passed`、全量 `569 passed`，Python 3.14.7 compileall、唯一生产写入搜索和保护输入门禁通过；fixed-time 100 步真实 SUMO run `baa105b06e08` completed，`action_rejected=0`、`illegal_transition=0`。
- TDD RED/GREEN 覆盖短绿、直接绿到绿、缺失/过短黄灯和缺失/过短全红，共 `6 failed` → `6 passed`；独立 program 校验现在在任何 bridge 写入和 observation suppress 之前拒绝不安全定义。
- Task 11: fix round 2/5 (1 addressed, 0 open; commit `376689d`). 等待 scoped 独立复审后再标记 Task 11 complete；Task 12 继续等待。

## Task 11 review fix round 3

- Round 2 scoped 独立复审发现 2 个 Critical：variant additional signal program
  直接绕过 `SafetyExecutor` 写入，以及 startup yellow 只检查任意 signal、未按
  departing movement 对齐。两项均以行为级 RED 锁定。
- Task 11 fix round 3 实现提交：`5a727d2` (`fix: close startup signal safety boundary gaps`)；
  variant program 现在只生成 startup `ControlAction`，由 `SafetyExecutor` 在初始
  启动/重连统一校验、写入和记录；yellow duration 按 departing green 的 signal index
  逐项累计；fixed-time 对不安全 source variant 记录拒绝后继续安装自身 frozen plan。
- Round 3 实现报告证据：focused `132 passed`、affected `273 passed`、full
  `574 passed`、两路真实 SUMO smoke、Python 3.14.7 compileall、diff-check、归档
  SHA-256 和官方数据 163/232 保护门禁通过。主 agent 独立 affected 回归为 `320 passed`，
  full 回归为 `574 passed in 95.76s`。
- Round 3 当前状态：等待独立 scoped re-review；Task 11 不得在 reviewer verdict 前标记
  complete，Task 12 继续冻结。review package 为
  `review-376689d..5a727d2.diff`。
- 主 agent 独立复核：当前 HEAD 全量 `574 passed in 95.76s`，受影响扩展集 `320 passed`，
  compileall 与 diff-check 通过；fixed smoke `b6a87220fc60` 完成 100 步/100.0 秒，事件含
  1 个 `unsafe_startup_program` source-variant rejection、1 个 accepted frozen fixed plan、
  0 `illegal_transition`；variant smoke `ff429e382183` 完成 100 步/10.0 秒（0.1 秒步长），
  variant startup program 通过安全边界，0 `illegal_transition`，SUMO 进程退出。
- Round 3 scoped 双轨复审：spec reviewer 判定两个原 Critical 均 ADDRESSED 且 PASS；
  quality reviewer 新发现 1 个 Important：`TraCIBridge.start()` 仅为 `tls_ids[0]`
  生成 variant startup action，旧实现会处理全部已发现 TLS，因而其他 TLS 的
  `variant_*` program 被静默丢弃，既未通过 `SafetyExecutor` 也无 ActionResult/event。
- Task 11: fix round 3/5 (2 addressed, 1 new Important open - multi-TLS variant
  programs are silently discarded; commits `376689d..5a727d2`).
- Task 11 fix round 4/5：切换到全新高能力实现单元；先以多 TLS additional file 建立
  行为 RED，要求每个匹配的 variant program 生成 startup action、逐 TLS 使用真实
  startup state 通过共享 `SafetyExecutor`、并为每个 accepted/rejected 结果记录带 TLS
  关联的事件；不得用首 TLS 的 `JointState` 校验其他 TLS，也不得静默丢弃。Task 12
  继续冻结。
- 主 agent Round 4 根因与基线探针：当前 bridge 双 TLS additional fixture 只返回
  `ACTION_COUNT=1`、`TLS_IDS=tls_a`；`SafetyExecutor` 又以传入 `JointState.tls_id`
  校验 action，因此仅把发现循环扩到全部 TLS 仍会把非首 TLS 误拒为 `unknown_tls`。
  20 个官方 `.net.xml` 均为单 TLS（`MAX_TLS=1`、`MULTI_TLS_FILES=0`），故本轮用
  构造的多 TLS 真实组件测试证明回归闭合，并保留官方单 TLS SUMO smoke 作兼容门禁。
- Task 11 Round 4 实现提交：`71bd4b0` (`fix: preserve multi-TLS variant startup actions`)；
  `TraCIBridge` 记录当前进程全部 TLS、逐 TLS 构造 startup state，Runner 逐 action
  经过 `SafetyExecutor`，secondary sink 不污染 primary movement builder，事件携带
  TLS `entity_ids`。
- Task 11 Round 4 主代理验证：关键集 `94 passed`；full `577 passed in 83.85s`；
  compileall、diff-check、唯一生产写入扫描通过；fixed/classic 两路真实 SUMO smoke
  均完成 100 步且 `illegal_transition=0`；归档 SHA-256 为
  `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`，官方数据仍
  为 163 tracked / 232 disk，保护路径无 diff。
- Task 11 Round 4 双域 scoped re-review：spec 与 quality 均 PASS；原 multi-TLS
  Important、fallback/direct-write/event 合同均 ADDRESSED，未发现新的
  Critical/Important/Minor。证据文件为 `task-11-r4-spec-rereview.md` 与
  `task-11-r4-quality-rereview.md`。
- Task 11: complete (commits `5a727d2..71bd4b0`, scoped re-review clean; 2 reviewers
  PASS; Task 10 parked compatibility finding remains for final whole-branch wave).

## Task 12 implementation

- 状态：进行中；基线为 `71bd4b0`。新生命周期必须按
  `queued -> starting -> running -> stopping -> terminal` 单向迁移，terminal 不可覆盖。
- Ruling: 用户 stop 的新证据统一使用 `interrupted`；`stopped` 仅保留 legacy 读取兼容
  — Task 12 批准的 handoff 已明确该 canonical 状态，计划样例中的 STOPPED 集合不是
  新写入合同 — if wrong, 只需在序列化兼容层映射，不得恢复双重 terminal 语义。
- Ruling: stop/switch_scene 必须等待该 run 自己的 future/runner/process，且只作用于其
  精确 PID；禁止按进程名或全局 SUMO 扫描清理 — 计划要求 never kill another run —
  if wrong, 只能放宽等待超时策略，不能放宽 ownership。
- Ruling: 保留 `run_metadata.json` 兼容消费者，同时新增原子 `manifest.json` 与
  `status.json`；Runner 迁移到 `SimulationWindow`/仿真秒，但保留 legacy integer smoke
  caller adapter — if wrong, 后续报告/可视化任务会出现不必要的大范围迁移。

## Task 12 implementation and review recovery

- Task 12 原始实现提交为 `d4ab93b` (`fix: make run lifecycle and scene switching safe`)；
  后续按审查逐步追加 `1a97e8a`、`e0c8ca9`、`3b7847d`、`574f199`、`e9b2715`，
  未 reset、rebase 或 amend。报告绑定提交为 `f7e0c8d` 与纠正提交 `c5e2223`。
- 已闭合的生命周期边界包括：validated scene/timebase 及 source/hash identity、formal
  warmup 与 explicit steps 的进程内区分、malformed status 终态恢复、exact child PID
  回收、stop/switch 等待所属 future/process、existing TraCI connection preflight 拒绝。
- `e9b2715` 上主代理最新代码门禁：focused `127 passed`；repo-local canonical full
  `631 passed in 123.84s`；compileall 与 diff-check 通过；真实 SUMO run
  `b7f105be2545` 完成 100 steps / 100.0 simulation seconds，manifest/metadata PID
  `20164` 一致，PID 已退出且无残留 SUMO。
- 保护输入门禁：`赛题资料.7z` SHA-256 为
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`；
  `data/intersection_data` 为 163 tracked / 232 disk；Task 12 提交与 index 均不得包含
  这两个保护目标。
- Round 4 formal scoped review：Spec PASS；Quality 为 NEEDS FIXES，0 Critical、
  2 Important、3 Minor。两个 Important 分别是 `_CompatibilitySteps(int)` provenance
  不可持久化导致 JSON replay 丢 formal warmup，以及 `traci.init()` TOCTOU cleanup
  可能通过 global `traci.close()` 关闭另一 owner。`frame_sink` 与另外两个 API/test
  观察保持 deferred Minor。
- Task 12: fix round 4/5 (先前 lifecycle/timebase finding 已闭合；Round 4 scoped quality
  新增 2 Important；commits `e0c8ca9..c5e2223`).

## Task 12 review fix round 5

- 状态：进行中；基线 `c5e2223`。第 5/5 轮采用唯一 Sol/xhigh writer，主代理与
  Terra/Sol 只读审计并行；writer 只能显式暂存 Task 12 文件，必须排除本 ledger、
  scratch/evidence 目录、保护归档和官方数据。
- Round 5 I1 RED：`tests/test_run_models.py` 初始 provenance/JSON 合同为
  `10 failed, 10 passed`；失败覆盖 formal/explicit equality、缺失 `steps_origin`、
  缺失 `to_payload/from_payload`、两类 window round-trip、嵌套/Path 恢复、
  inconsistent origin fail-closed 与 legacy plain-int fallback。
- Round 5 I2 RED：partial-init RuntimeError、KeyboardInterrupt 与 TOCTOU other-owner
  三个 lifecycle 测试均按预期失败：label 仍为 `default` 或 exact own handle 未关闭；
  exact child cleanup 断言已通过。目标实现为模块内 single-active lifecycle gate、
  unique attempt label、exact Connection handle close 和 exact child PID cleanup，禁止
  global `traci.close()`，但不把本轮扩张为多 bridge 并发重构。
- Round 5 补充 closure：`RunRequest` payload 必须含 versioned、可持久化的
  `steps_origin`，矛盾 origin/value fail closed，manifest 记录 provenance；
  `scripts/run_pdf_matrix.py` semantic request key 必须纳入 origin 与实际 window 输入，
  formal/explicit 同值不得碰撞。
- Round 5 只读 payload 审计补充 Important：显式 `schema_version=1` 的 payload 若缺少
  `steps_origin` 必须 fail closed，只有完全无 schema version 的 legacy payload 才允许
  推断 provenance；否则 formal JSON 会静默降为 explicit 并丢失 warmup。
- Task 12: minor (deferred): `scripts/run_pdf_matrix.request_key()` 尚未纳入
  `edge_delay_steps`、`edge_directions` 与 variant；canonical PDF matrix 当前不产生这些
  值，故不延长 Round 5，但最终 whole-branch review 必须判断该函数是否应收紧为 canonical
  matrix-only identity 或扩展为完整 RunRequest semantic identity。
- Task 12 fix round 5/5：实现、GREEN、追加提交、最新 HEAD 主代理门禁与 scoped
  Spec/Quality 双域复审尚未完成；在这些流程节点闭环前不得标记 Task 12 complete，
  不得进入 Task 13。

### Round 5 code head and controller gates

- Round 5 实现提交：`fc1a4d7` (`fix: preserve request and connection identity`)；提交仅含
  9 个授权 code/test 文件，未包含本 ledger、报告、scratch、保护归档或官方数据，index
  为空。writer expanded focused 为 `151 passed in 30.19s`，compileall/diff-check 通过。
- 主代理 latest-HEAD 验证：expanded focused `151 passed in 31.36s`；repo-local full
  `655 passed in 112.08s`；venv Python 3.12.13 与系统 Python 3.14.7 compileall 均 exit 0；
  `git diff --check 71bd4b0..fc1a4d7` 和 `c5e2223..fc1a4d7` 通过。
- 主代理真实 SUMO：run `ca1cabbf7800`，目录
  `D:\Temp\judge-task12-r5-controller-real-20260822-0924\i1\fixed_time\x1\s42\ca1cabbf7800`；
  status/metadata/result 均 completed，100 derived steps / 100.0 requested seconds /
  100.0 final simulation seconds，`steps_origin=explicit`；manifest/metadata PID 均为
  `16632`，PID 已退出，SUMO before/after 均为 0。
- latest protected gate：`赛题资料.7z` SHA-256 仍为
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`；
  官方数据仍为 163 tracked / 232 disk；branch/worktree/index 的保护路径 diff 均为空。
- Round 5 pre-review breaker candidates（尚待 formal scoped 双域复审裁定）：
  1) startup 原始 failure 后 exact handle close 若再抛 KeyboardInterrupt，会以 cleanup
  BaseException 作为最终异常；child/state 仍已清理；
  2) 同一 bridge 的 unsupported concurrent/repeated `start()` 会在 lifecycle lock 外先清空
  discovery state 再拒绝；当前生产 Runner 不并发调用同一 bridge start；
  3) FatalTraCIError restart 路径若 exact handle close 本身再抛 FatalTraCIError，会阻断
  restart；SUMO 1.27.1 的常规“Connection closed by SUMO”路径先把 socket 置 None，随后
  exact close 可正常注销，但非常规 close failure 仍有窄风险。
- 上述候选不得静默丢弃；若 Round 5 formal re-review 判为 Critical/Important，则按五轮
  breaker 逐项记录 Ruling/park 或 load-bearing handoff，不再派第 6 轮 Task 12 fix。

### Round 5 formal re-review and breaker closure

- scoped review package 为 `review-c5e2223..c8c64b7.diff`，58,527 bytes / 1,529 lines，
  SHA-256 `7F3DECBC415D6BD8EE2903302270C9D0973C9942BD380FD79171DF266EC3B79E`；
  包含 code/test 提交 `fc1a4d7` 与 report-only 提交 `c8c64b7`。
- Spec reviewer：I1/I2 均 ADDRESSED，无新 Critical/Important；把同实例重复/并发 start
  与非常规 exact-handle close failure 归为非阻塞 Minor。
- Quality reviewer：I1 ADDRESSED；I2 的 unique label、exact partial handle、exact child、
  no global close 与现有 owner/TOCTOU/restart 合同均已闭合；仍保留 1 个 Important：
  同一运行中 `TraCIBridge` 的重复/并发 `start()` 会在 lifecycle lock/precondition 前
  清空 discovery state，随后才拒绝第二次启动。
- Task 12: fix round 5/5（原 I1 已闭合；I2 exact ownership 主缺陷已闭合，1 个 scoped
  Important 仍开放；commits `c5e2223..c8c64b7`）。
- Task 12: parked — same-instance repeated/concurrent `TraCIBridge.start()` clears discovery
  state before rejection — Ruling: 这是一个真实 direct-API robustness gap，保留 Quality
  严重度；但当前 `RunService`/`SimulationRunner` 为单 worker、单 bridge、单次启动，受支持
  restart 先 `close()` 后 `start()`，scene switch 也等待旧 run/process 完成，故不承载
  Tasks 13–24 的生产路径。五轮 breaker 将其移交最终 whole-branch review 的单一最终修复波；
  if wrong，直接调用者重复或并发 start 可破坏 live discovery state，最小修复应把 reset
  移入 lifecycle gate/precondition 之后，并添加真实同实例 repeated/concurrent 行为测试。
- Task 12 deferred Minor：非常规 exact `Connection.close()` 二次失败可中断 fatal restart；
  `request_key()` 的非 canonical edge/variant 字段；既有未使用 `frame_sink`；直接调用
  `write_status()` 可接受 unknown status。全部保留到最终 whole-branch review，不得静默丢弃。
- breaker 裁决已写入 report-only 提交 `87885c6` (`docs: record task 12 breaker
  adjudication`)；没有代码变化，不使 `fc1a4d7` 上的 151 focused / 655 full / 真实 SUMO
  latest-HEAD 证据失效。
- Task 12: complete（commits `71bd4b0..87885c6`，1 个 parked Important 与上述 deferred
  Minor 已显式移交最终 whole-branch wave；Round 5 breaker 已裁决，最新代码证据绑定
  `fc1a4d7`）。

## Task 13 implementation

- 状态：进行中；基线 `ea8b1a9`。Task 13 冻结 run-scoped evidence 与 metric semantics，
  是 Task 8 completed/unfinished 与 safety fields、Task 12 artifacts/terminal states 到
  Task 14/22 formal matrix 的 load-bearing 交接点。
- Ruling: brief 的 `RunSummary` 为类型笔误；复用既有 `core.types.MetricSummary`，允许最小
  修改 `core/types.py` 增加 `from_raw_outputs()` 与安全汇总字段，不创建同名并行 summary
  类型 — if wrong，后续 Task 14/16/17 会出现互不兼容的两套指标合同。
- Ruling: 计划 Files 表未列但生产接线必需的 `engine/runner.py`、`engine/run_service.py` 与
  直接回归测试可最小扩展；不得重构 Task 8 safety collector、Task 10 CloudPolicy、Task 12
  lifecycle/process ownership — if wrong，可从提交中剥离接线适配，但孤立 EvidenceWriter
  将无法满足“每次生产 run 都写同一证据合同”。
- Ruling: 证据为 additive contract；保留 `manifest.json`、`status.json` 与
  `run_metadata.json` 兼容，新建 versioned `provenance.json` 与 `hashes.json`。hash manifest
  使用 run-relative path -> SHA-256，不自哈希，所有 JSON/CSV 采用同目录临时文件原子替换
  — if wrong，只需迁移 hash envelope，不得破坏已冻结的 Task 12 identity/status 写入。
- Ruling: 保留既有 `required_output_names()` 作为 legacy raw/stable 列表，新增严格
  `evidence_required_output_names()`；Task 13 起 canonical resume/validation 必须使用后者或
  `EvidenceReader`，因此旧 fixture/API 不突变，但缺 provenance/hash 的旧 run 不能冒充新
  completed evidence — if wrong，可在 Task 14 迁移消费者，但正式矩阵开始前必须关闭。
- Ruling: `hashes.json` 只能在最终 `status.json` 与 `run_metadata.json` 落盘后生成，覆盖
  最终 manifest/provenance/status/metadata/raw/metrics/events/summary 并显式排除自身；
  `EvidenceWriter.finalize()` 不得重写 Task 12 status — if wrong，后续同终态同步会令刚生成
  的 hash 立即失效。
- Ruling: completed/ended_early 的可发布证据必须具有完整非空 raw/metrics/events/summary 与
  有效 hash；failed/interrupted/disconnected 等 terminal 必须保留 manifest、provenance、
  status、failure reason 和当时已有文件，但不得伪造完整 SUMO output 或 completed summary
  — if wrong，Task 14 resume 可能把失败 run 误判为有效完成证据。
- Ruling: warmup 按 simulation seconds；time-series/event 只聚合
  `simulation_seconds >= warmup_seconds`，tripinfo 只把 `depart >= warmup_seconds` 的完成车辆
  纳入 throughput/完成车辆均值，unfinished 单独计数且永不进入完成车辆指标。fuel 为 ml、
  CO2 从 mg 独立换算为 g；summary 必须显式包含 collision、red_light、
  illegal_transition、harsh_braking、teleport、potential_conflict 六类计数 — if wrong，
  formal matrix 会混入 warmup 全旅程或把未完成车辆/能源/安全口径混合。
- TDD 边界：先覆盖 completed/unfinished、warmup、fuel/CO2、六类 safety、manifest/provenance
  必填、terminal 分层、run_id/hash/空文件、原子写无 tmp 与 legacy visualization/metadata
  兼容，再运行计划 focused、affected、full、compileall、diff-check 和真实 SUMO evidence
  smoke；保护归档与官方数据始终零修改/零暂存。
- Task 13 fresh baseline：repo-local full 为 `655 passed in 107.88s`，RED 前 tracked code
  零改动。首批 collection RED 为 `ModuleNotFoundError: experiments.evidence`；添加仅抛
  `NotImplementedError` 的接口骨架后，7 个证据/指标行为测试为 `7 failed in 0.54s`。
- Ruling: evidence terminalization 使用两阶段：`finalize()` 在 Task 12 terminal commit 前原子
  物化 summary/snapshots，使 would-be completed 的物化失败仍可变为 failed；Task 12 落盘
  最终 metadata/status 后再 `seal()` hashes。seal 失败只让 `EvidenceReader` fail closed，
  不得覆盖已终态 status；原 body/BaseException 始终保持 primary — if wrong，hash 顺序或
  cleanup 二次异常会制造不可验证的 completed run 或掩盖真实失败。
- 首批 GREEN：7 个核心 evidence contract 为 `7 passed in 0.53s`；扩大到 metrics、
  artifacts、safety 为 `56 passed in 0.96s`。
- 第二批 schema/parser RED 为 `9 failed, 8 deselected`，seal RED 为
  `1 failed, 16 deselected`；逐项补齐 request dimensions、strict depart/arrival、identity/
  stopped 拒绝、semantic validation、unsafe hash path、partial summary 与 sealed guard 后，
  分别 GREEN `9 passed`、`1 passed`，完整 evidence 集 `17 passed in 0.66s`。
- consumer RED/GREEN：legacy completed run 与未验证 summary 原会被 resume/visualization
  接受，`2 failed`；接入 `EvidenceReader` 后为 `2 passed`，canonical completed contract
  从 Task 13 起 fail closed。
- atomic CSV RED/GREEN：MetricsCollector/EventLogger 写入失败会截断旧 snapshot，
  `2 failed`；同目录 temp+replace 后 `2 passed`，失败保留旧 snapshot 且无 tmp 残留。
- lifecycle production RED：direct Runner completed/malformed、Service early scene failure、
  Service normal 与 KeyboardInterrupt 共 `6 failed in 4.49s`；根因分别为缺 seal、
  service-only path 缺 begin/finalize/seal，以及 KI 内存/磁盘停留 running。当前进入生产
  ownership 接线与异常优先级 GREEN。
- Task 13 strict-reader breaker RED/GREEN：首轮 `8 failed, 21 passed, 1 skipped`，补齐
  direct/ancestor reparse、events 全行 identity/time、四类 XML、hash 算法/覆盖/路径、JSON
  exact type/finiteness、manifest/provenance/status/metadata identity/timebase 与 canonical
  summary/raw 对照后，复审集为 `41 passed`；`evidence_error` 另以 `1 failed` 锁定后 GREEN。
- Task 13 lifecycle breaker RED/GREEN：secondary finalize/seal/status/metadata failure、
  Runner/Service `BaseException` primary preservation、cancelled future terminalization 与持久
  status failure 共先后出现 `10 failed`、`2 failed`；修复后对应为 `10 passed`、`2 passed`。
  自定义非 evidence-managed runner 可保持 lifecycle compatibility，但 `EvidenceReader` 与
  `is_complete()` 必须永久拒绝其作为 canonical publishable evidence。
- Task 13 提交：`c9da80b` (`feat: define run-scoped evidence and metric semantics`)；19 个
  production/test 文件显式暂存，未包含本 ledger、scratch、保护归档或官方数据，index 随后
  为空。latest affected 为 `246 passed in 57.69s`。
- Task 13 首次 post-commit 真实 SUMO 门禁捕获 server-version tuple bug：run
  `3223b1418723` / PID `15488` 的其他 evidence/PID 检查通过，但 manifest/metadata 误记
  TraCI protocol `22`，因此仅作为 historical RED；单测先得到 `1 failed`，随后提交
  `5ee5a66` (`fix: record SUMO server version`) 并以 tuple index 1 记录 `1.27.1`。
- Task 13 latest code-head 门禁：SUMO-version focused `75 passed in 29.90s`；full
  `720 passed in 130.19s`；venv Python 3.12.13 与系统 Python 3.14.7 均 compileall 122 files/
  exit 0；`git diff --check ea8b1a9..5ee5a66` 通过。
- Task 13 latest 真实 SUMO：run `968823f6861e`，目录
  `D:\Temp\t13-real-sumo-100-final2\i1\fixed_time\x1\s42\968823f6861e`；
  result/status/metadata completed，`EvidenceReader issues=[]`，13 个 required artifacts 均
  non-empty，manifest code commit exact `5ee5a667...`，SUMO version `1.27.1`，100 steps /
  100.0 requested/final seconds / 100 simulation rows；hash 覆盖完整，PID `22312` 已退出，
  SUMO before/after 均为空。
- Task 13 latest protected gate：归档 SHA-256 仍为
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`；官方数据仍为
  163 tracked / 232 disk；baseline..HEAD、worktree 与 index 的保护路径 diff 均为空。
- Task 13：代码/测试/门禁已完成；scoped Spec/Quality/Mutation 三域并行终审、报告提交与
  ledger 闭环进行中。在三域 Critical/Important 清零且报告/ledger 提交前不得标记 complete。
- Task 13 scoped Mutation review：唯一 finding 为 `EvidenceReader.validate()` 的临时文件
  `glob()` 枚举未捕获 OSError/PermissionError，valid artifact 上可直接抛出；其余独立
  hash/CSV/XML/JSON/metadata/evidence_error/symlink-junction/stat/seal/custom-runner harness
  均 fail closed。此 finding 与 Quality P2 重合，已进入 TDD fix。
- Task 13 scoped Quality review：NEEDS FIXES。可复现 findings 为：custom runner 抛
  `SystemExit` 后 done=True 但 state/status 留 running；Python >=3.10 声明下 3.10/3.11 无
  `Path.is_junction()` 导致 Windows junction/reparse fail-open；events row 的 step/confidence/
  entity_ids/source/context 校验不足；temporary glob IO 外泄。Terra writer 正按 RED/GREEN
  处理，任何代码变化后旧 `5ee5a66` latest-HEAD 门禁必须全部重跑。
- Task 13 Quality 另报“raw+summary+hashes 协调改写可通过”的外部可信根 P1。当前进入
  Spec/主代理 threat-model 裁决：brief 只冻结 run-scoped SHA-256 self-consistency，未提供
  签名密钥、外部 digest、只读账本或不可变存储；在无外部信任锚时本地代码无法证明
  adversarial authenticity。不得静默降级：若 Spec 判定现合同要求 authenticity，则必须
  新增可信根接口并延长 Task 13；否则报告必须显式声明仅检测意外损坏，并把发布级外部
  digest/signing anchor 移交 Task 22/24 final evidence packaging。
- Task 13 scoped Spec 初审：FAIL。Critical 为 generic `SystemExit` 未终态化且 Runner cleanup
  可覆盖 primary；Important 为 matrix live、tuning、single-run visualization、API summary
  consumers fail-open，events SafetyEvent 字段/context 不严格，Python 3.10/3.11 junction
  fail-open，RunManifest 4 个额外字段无默认，manifest/status/metadata failure_reason 不自洽；
  legacy aliases 缺 units 为 Minor。Spec 裁定同目录 hashes 仅保证损坏检测/自洽，协调改写的
  adversarial authenticity 不属于当前 brief；外部 trust anchor 显式移交 Task 22/24。
- Task 13 final-findings TDD RED：evidence/reparse/events `11 failed`；RunService SystemExit
  `1 failed` 且 status=running；matrix/tuning consumers `2 failed`；single-run visualization
  `1 failed`；主代理另锁定 API submit `1 failed` 与“strict but wrong request live result”
  `1 failed`。不得把这些初审前的 720/full 或真实 SUMO 证据继续称 latest。
- Task 13 final-findings GREEN：API `14 passed`、evidence `55`、RunService `34`、runner
  channel `36`、lifecycle `28`、tuning/matrix `20`、visualization `4`、events/artifacts/
  metrics `39`；主代理 fresh affected `230 passed in 72.77s`，compileall/diff-check 通过。
- Task 13 fix commit：`9b74a61` (`fix: close task 13 final review findings`)；14 个 code/test
  文件显式暂存，未包含本 ledger、报告、scratch 或保护输入，index 随后为空。修复 generic
  BaseException primary/terminal、所有 Windows reparse 属性、Reader glob I/O、canonical
  events/context、reason/units/RunManifest compatibility，并把 matrix live identity、tuning、
  visualization 与 API 所有 summary 出口收束到严格 evidence 边界。
- Task 13 latest full 首次使用 `D:\Temp` basetemp 得到 `4 failed, 738 passed`；四项全为
  `FixedTimePlanResolver` 按既有合同拒绝仓库外 pytest timing fixture，不是 Task 13 行为失败。
  改用 fresh repo-local basetemp 后 authoritative full 为 `742 passed in 138.32s`。
- Task 13 latest static/protected：venv Python 3.12.13 与系统 Python 3.14.7 对 122 files
  compileall 均 exit 0；`git diff --check ea8b1a9..9b74a61` 通过；归档 SHA-256 仍为
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`；官方数据仍为
  163 tracked / 232 disk；baseline/worktree/index 保护 diff 均为空，index 为空。
- Task 13 latest 真实 SUMO：run `074551e3bdc5`，目录
  `D:\Temp\t13-real-sumo-100-9b74a61-20260822-112328\i1\fixed_time\x1\s42\074551e3bdc5`；
  result/status/metadata completed，Reader issues=[]，13/13 required non-empty，manifest
  commit exact `9b74a61c...`，SUMO version `1.27.1`，100 steps / 100.0 seconds / 100 rows，
  hash coverage exact；PID `17200` 已退出，SUMO before/after 均为空。
- Task 13：原 Spec/Quality/Mutation 三位 reviewer 正在 `ea8b1a9..9b74a61` latest-HEAD
  scoped 复审；三域结果、report-only commit 与 ledger commit 闭环前仍不得标记 complete。
- Task 13 latest-HEAD Spec 复审：旧 Critical/Important/Minor 全部 ADDRESSED，无新 Critical；
  仍 FAIL 于 1 个新 Important：`verify_ia_ib.verify_ca_mp_smoke/exact_metrics` 未调用 Reader，
  可把 completed+summary 但 seal-invalid 的 run 判 PASS。Quality 同样确认此 finding。
- Task 13 latest-HEAD Quality 复审：SystemExit、Windows reparse、glob never-throw、events、
  API/visual/PDF matrix 均 ADDRESSED；NEEDS FIXES 于 2 个 Important：上述 IA/IB verifier；
  tuning 虽把 invalid evidence 转为 inf，但全 inf 仍按参数排序选 winner 并写
  selected_params/holdout，必须在 invalid/non-finite calibration 时中止且不产成功交付物。
- Task 13 latest-HEAD Mutation 复审：另有 1 个 Important integrity gap：API 与 tuning 只验证
  run_dir，却继续使用调用方传入的 `RunResult.summary`；custom runner 可让磁盘 strict summary
  throughput=1 而内存 summary=999999，并被 API/tuning 消费。matrix live 也必须在
  `is_complete` 后从磁盘 reload，不能把未绑定内存 summary 写入 matrix。
- Task 13 fix round 2 已派 Terra writer：TDD 收束 tuning workflow、IA/IB verifier 与所有
  in-memory/disk summary binding；新提交、latest full/compile/protected/real-SUMO 及三域复审
  全部完成前不得关闭 Task 13。
- Task 13 fix round 2/5 RED→GREEN：tuning/matrix canonical/fail-closed 为
  `6 failed, 20 deselected`，IA/IB seal gate 为 `2 failed, 19 deselected`，API 伪内存
  summary 为 `1 failed, 13 deselected`，RunService 伪 runner summary 为
  `1 failed, 34 deselected`；修复后 tuning `27 passed`、API `14 passed`、IA/IB
  validation `21 passed`、evidence contract `55 passed`、RunService `35 passed`。提交
  `b1a1ec7` (`fix: bind task 13 consumers to sealed evidence`) 把 API、tuning、live
  matrix、IA/IB verifier、RunService summary 全部绑定到 Reader 验证的 sealed disk
  snapshot，并让 invalid/non-finite tuning 与 publication failure fail closed。
- Task 13 fix round 3/5 RED→GREEN：主代理以 `2 failed` 锁定 seal 后 raw summary 与
  tuning 成功标志边界，并以另一个 `2 failed` 锁定单运行/聚合 figure source change、swap
  failure 的半发布风险；GREEN 后 exact affected 为 `103 passed in 26.71s`。提交
  `d1edd10` (`fix: publish validated figure sets atomically`) 让 run/aggregate 图集在同卷
  staging 中生成、发布前复验、整目录原子换位，并在失败时恢复旧 public set。
- Task 13 exact code-head `d1edd109916a3372cab5dfcbd367df7f7b10dbb3` 最终门禁：
  full `771 passed in 158.25s`；venv Python 3.12.13 与系统 Python 3.14.7 compileall
  均 exit 0；targeted flake8 exit 0；`git diff --check ea8b1a9..d1edd109` clean；归档
  SHA-256 仍为 `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`，
  官方数据仍为 163 tracked / 232 disk，baseline/worktree/index 保护 diff 均为空。
- Task 13 exact code-head 真实 SUMO：run `28f57c800100`，目录
  `D:\Temp\t13-real-sumo-100-d1edd10-20260822-122630\i1\fixed_time\x1\s42\28f57c800100`；
  result/status/metadata completed，Reader issues=[]，canonical summary loaded，13/13
  required non-empty，hash coverage exact，manifest commit exact `d1edd109...`，SUMO
  manifest/metadata version `1.27.1`，100 requested/derived steps、100.0 requested/final
  seconds、step 1.0、warmup 0、100 simulation rows，`is_complete=true`；manifest/metadata
  exact PID `24348` 已退出，SUMO before/after 均为空，未使用进程名终止。
- Task 13 exact-HEAD 三域终审：Spec CLEAN（关键回归 `10 passed`，同补丁 affected
  `103 passed`）；Contract CLEAN（`103 passed`）；Mutation CLEAN（`4 passed` 加原子
  publication/rollback/manual mutation probes）。Critical/Important 均为零。
- Task 13 minor (deferred)：`EvidenceReader.validate()` 体量偏大；其 fail-closed 行为与
  Task 13 契约已验证，本轮不阻塞，显式移交 final whole-branch review 评估受控重构。
- Task 13 报告提交：`4b6e0ea` (`docs: record task 13 evidence contract`)；措辞澄清追加
  `db51125` (`docs: clarify task 13 code evidence head`)。两次均仅显式暂存 Task 13 report，
  progress、scratch、保护归档和官方数据未进入提交，index 随后为空。
- Task 13: complete (commits `ea8b1a9..db51125`, review clean；权威代码证据 head
  `d1edd109`，报告 `4b6e0ea` + `db51125`，最新 771/full 与真实 SUMO/PID 门禁已记录)。
- Task 14: in progress；BASE `f87adcf4b0d6516f11d9786def7d64cb7985ef84`。已生成
  `task-14-brief.md`，两路只读 preflight 冻结 540=360 normal+180 disturbance、seconds-first
  正式时窗、strict sealed-evidence resume、paired statistics、CLI/profile 与 direct-consumer
  回归地图；writer 必须按 TDD RED→GREEN 实现并提交，progress/保护输入不得进入其 index。
- Task 14 Ruling: disturbance 180 项固定 `flow_multiplier=1.0`；每 scene 从已验证 source
  manifest/network 确定性选择首个可达正式 lane/edge target，并把 kind/begin/end/target/
  intensity 全部写入 run key 与 matrix manifest — 规格的 180 计数没有负载维度，动态但可哈希
  绑定的 source-derived target 比伪造跨场景常量安全 — if wrong，正式扰动可能不代表预实验后
  人工冻结的业务位置，Task 22/24 冻结材料前需用 manifest target 表复核。
- Task 14 Ruling: paired 主差固定为 candidate-baseline（负 travel 差为改善），relative 为
  配对 `(C-B)/B` 的均值，effect size 为 paired Cohen's dz，95% 双侧 t-CI；baseline<=0、
  缺配对、重复、non-finite 一律 fail closed，零方差 CI 可退化而 dz 以 JSON-safe null+flag
  表达 — 这些定义补足计划未指定的统计细节 — if wrong，效应量/相对变化会与评委采用的另一
  公式不一致，但原始配对差与全部 source run IDs 仍可重算。
- Task 14 Ruling: improved unit 是 40 个 scene/load 单元各自三 seed travel 均值差 `<0`，
  `>=21` 才过门；worst unit 取 signed travel difference 最大者并以 numeric scene/load 稳定
  tie-break。candidate safety 读取该算法全部 formal normal+disturbance 行的 collision/red-light/
  illegal-transition 三硬门，final release 另要求全 540 行均安全为零；观察型 harsh/teleport/
  conflict 不作硬门 — if wrong，候选资格的安全作用域需在 Task 24 final gate 收紧。
- Task 14 Ruling: failed retry 的 parent reference 存在 matrix manifest attempt chain，不改写
  已 seal 的单次 run manifest；corrupt completed evidence 作为 integrity error 停止而非当 failed
  静默重跑。formal profile 只接受冻结 3600/600 和 seeds 42/43/44，`--seed` 仅覆盖
  smoke/quick；并发同一 output root 必须 fail closed 或由独占锁串行 — if wrong，CLI override
  或并发恢复可能制造冒充 formal 的缩水矩阵或丢失 attempt lineage。
- Task 14 initial TDD/commit：9 组 RED→GREEN 覆盖 matrix cardinality/target/statistics、resume/
  lock、CLI/analyzer、direct audit、seconds-first 与 quick seeds；final affected `218 passed`，
  compileall/diff-check 通过。提交 `f68b3dc` (`feat: freeze the 540-run formal experiment matrix`)；
  主代理 strict flake 捕获 `experiments/runner.py:129 E131` 后由原 writer 追加 `670083d`
  (`style: align formal runner continuation`)，主代理 fresh focused `65 passed`、strict flake exit 0。
- Task 14 首轮 review（exact package `f87adcf..670083d`）：Spec/Quality NOT CLEAN、Mutation
  FAIL、Integration NOT CLEAN。Critical：manifest 已记 completed 的 attempt 若 status 缺失或被
  篡改为 non-completed，可被当 failed/missing 静默重跑；analyzer 只信 CSV key set/status/metrics，
  未绑定 exact RunSpec 与 sealed disk summary。Important：IA/IB 同样缺 key-row/metric binding；
  normal 与 disturbance 描述统计混合；retry run_id/parent/旧 bytes 唯一性不足；disturbance safety
  coverage 未锁 flow=1.0、seed42 和完整 identity。
- Task 14 minor (deferred)：release-facing README/scripts guide 仍使用已移除的 `--quick`/`--steps`
  和旧 360/state-file 口径；Task 20 已有专门 public-doc boundary/checker，移交其统一修订。
- Task 14 minor (deferred)：IA/IB relative `run_dir` 当前相对 repository root，而非 matrix CSV
  parent；fix round 1 的 sealed-summary input containment 若自然覆盖则由 re-review确认，否则移交
  Task 22 portable evidence audit，不单独延长本轮。
- Task 14 fix round 1/5：已恢复原 Sol writer，以 TDD 修复 completed-corruption、exact key/spec +
  sealed-summary analysis/audit、disturbance 独立 strata、retry lineage 与完整 disturbance safety
  identity；新 commit/report/scoped re-review 前 Task 14 保持 open。
- Task 14 fix round 1/5 已实现：追加代码/测试/报告提交 `160c230`
  (`fix: bind formal analysis to sealed evidence`)；completed attempt corruption、全局 retry
  lineage、exact RunSpec/manifest/request、canonical sealed summary、normal/disturbance 分层和
  disturbance safety 完整 identity 均已逐项 RED→GREEN。最终 covering `118 passed`，提交后
  whole suite `838 passed in 299.65s`，Python 3.12/3.14 compileall、strict changed-file flake、
  `git diff --check f87adcf..160c230` 与保护输入门禁均通过。
- Task 14 fix round 1 scoped 复审（exact package `670083d..160c230`）：Formal Spec/Quality、
  Mutation、Integration 三域均 CLEAN；首轮 Critical/Important 全部 ADDRESSED，无新增
  Critical/Important。首轮 IA/IB relative `run_dir` minor 已由 matrix-root containment 自然关闭，
  不再移交；旧 public docs 口径仍按原决定移交 Task 20。
- Task 14 latest-head real-smoke RED（historical exact head `160c230`）：真实 scene 1 的 validated
  `step_length=1.0`；`--profile smoke` run `738880afb5a2` 虽 completed、Reader issues=[]、SUMO
  `1.27.1`、PID `25072` 精确退出且无残留，但 manifest `derived_steps=10`、requested seconds
  `10.0`，只执行 10 个实际仿真步，违反 brief 的 smoke=100 actual simulation steps。此前把
  scene 1 假设为 0.1 秒步长的预案作废；该 run 只作为 RED 证据，不得充当 Task 14 最终 smoke。
- Task 14 fix round 2/5：Sol 唯一 writer 以 TDD 把 smoke 请求改为跨 scene timebase 均严格
  explicit 100 steps，同时保持 formal seconds-first、quick 600 秒、sealed evidence、resume 和
  analysis/IAIB 契约；Terra/Luna 并行做跨层 contract 与 counterexample 只读审计。新追加提交、
  scoped 多域复审、latest-head full/static/protected 和真实 100-step + immutable-resume 门禁完成前，
  Task 14 保持 open。
- Task 14/15 latest-head pre-commit gate（2026-08-22，HEAD `78cc0c3`）：受影响回归为
  `247 passed, 1 warning`，完整套件为 `862 passed, 1 warning`，两者均 exit 0；警告只有
  pytest 无法写根目录缓存的 WinError 5，不是行为失败。venv Python 3.12.13 与系统 Python
  3.14.7 compileall 均 exit 0；targeted flake8 采用项目既有 `--ignore=E501,W503` 口径 exit 0；
  `git diff --check` exit 0。
- Task 14 latest real smoke（exact head `78cc0c3`）：命令
  `.venv\\Scripts\\python.exe scripts\\run_pdf_matrix.py --profile smoke --output-root
  D:\\Temp\\t14-15-real-smoke-78cc0c3` 产生 run `e6170417424e`；manifest 为 explicit
  `derived_steps=100`、`requested_seconds=100.0`、`step_length=1.0`，metadata 为
  `status=completed`、`final_simulation_time=100.0`，simulation log 为 100 rows，SUMO
  `1.27.1`，`EvidenceReader.validate()` 为 `[]`，记录 PID `23088` 已退出且无 SUMO 残留。
  command-line SUMO 的 GUI screenshot unsupported warning 被 frame capture fail-soft 处理，
  不影响 headless evidence。
- Task 15 terminal-event correction（exact head `78cc0c3`）：realtime `terminal` event 在
  runner cleanup、metadata 写入和 evidence seal 完成后发布；terminal cleanup/log failure
  通过 `tests/test_runner_channel.py::test_terminal_event_uses_final_status_after_cleanup_failure`
  锁定最终 `failed` 状态与原因。FramePublisher 仍按 run 只保留最新一帧，RealtimeHub 为
  bounded non-blocking fan-out，事件 sink/frame sink failure 不改变仿真主流程。
- Task 14/15 manual final review：逐项复核 RunSpec/profile 的 100-tick smoke 与 formal
  seconds-first 边界、RunService/SimulationRunner 的 sink 注入和终端状态优先级、TraCI
  run-scoped 临时 frame 清理、EvidenceReader seal 门禁及测试直接消费者；未发现未处理的
  Critical/Important 行为缺口。Luna 子代理此前因其隔离环境无法读取源码，未提供可采信的
  独立 CLEAN 结论，本条只记录主代理人工复核与 fresh command evidence，不冒充子代理复审。
- Task 14/15：pre-commit gate complete；下一步为显式暂存目标代码/测试、排除 progress、
  scratch、archive 与 official scene data，提交后重跑 post-commit verification，再分别写入
  `Task 14: complete` 与 `Task 15: complete`。
- Task 14/15 implementation commit：`1b5f9ed` (`feat: publish formal matrix runtime events and
  frames`)；index 只包含上述 14 个目标代码/测试文件，progress、scratch、archive 与 official
  scene data 均未进入提交。
- Task 14/15 post-commit gate（exact HEAD `1b5f9ed`）：完整套件重新执行为 `862 passed,
  1 warning`，exit 0；双 Python 3.12/3.14 compileall、targeted flake8（`--ignore=E501,W503`）、
  `git diff --check` 均 exit 0。保护输入 hash 仍为
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`，official scene data
  仍为 `163 tracked / 232 disk`，保护路径 worktree/index diff 均为空。
- Task 14/15 post-commit real smoke：run `0d1f93786ee0`，目录
  `D:\\Temp\\t14-15-real-smoke-1b5f9ed\\runs\\i1\\fixed_time\\x1\\s42\\0d1f93786ee0`；
  manifest `code_commit=1b5f9edab46cb12dae5c94dc527a24fe40beb9be`，explicit `derived_steps=100`、
  `requested_seconds=100.0`、`step_length=1.0`，metadata `completed`/`final_simulation_time=100.0`，
  100 simulation rows，SUMO `1.27.1`，`EvidenceReader.validate()` 为 `[]`，PID `26736` 已退出且
  无 SUMO 残留。GUI 不可用 warning 仍由 capture fail-soft 处理。

## Detailed continuation todo

- [ ] Task 14（实现/门禁完成，review pending）：冻结 540-run matrix；已完成 formal 360 + disturbance 180、seconds-first
  profile、strict sealed-evidence resume、paired statistics、100-step smoke、full/static/protected
  gates；commit `1b5f9ed`，独立 reviewer 回报仍待收取。
- [ ] Task 15（实现/门禁完成，review pending）：完成 bounded FramePublisher、run-scoped TraCI frame capture、RealtimeHub、status/
  metrics/action/safety/frame/terminal events、sink failure isolation 与 final terminal ordering；
  commit `1b5f9ed`，独立 reviewer 回报仍待收取。
- [ ] Task 16：新增 judge API；实现 run submit/status/stop、scene/algorithm/results/metrics/safety
  只读端点、run-scoped frame endpoint、WebSocket realtime stream、OpenAPI contract 和 `web/dist`
  static serving；用 FastAPI contract tests 覆盖 404、terminal evidence、stream backpressure 与
  无效请求，并完成 focused/affected/full/static/protected gates。
- [ ] Task 17：创建 React/Vite console 与 typed API client；实现 scene/algorithm/duration/warmup/
  disturbance 选择、run controls、latest frame、realtime metrics/events、comparison/history；
  配置离线 build 到 `web/dist`，以 Playwright judge-flow 覆盖 health -> run -> frame -> metrics ->
  stop/history，保存浏览器证据并完成 build/test gates。
- [x] Task 18（complete）：实现项目解释器原生 launcher 与 diagnostics；启动同一 FastAPI app，先 health-check
  再打开浏览器，记录 Python/SUMO/TraCI/assets/output status，统一拥有 shutdown/child process
  cleanup；补 launcher unit/integration tests 和 native smoke evidence。2026-08-23/24 当前证据：
  affected 140 passed、full 940 passed、frontend typecheck/build、compileall、diff-check 均通过；
  headless 与 native GUI 真实 smoke、Codex 内置浏览器四视图验收、保护输入核验完成；详见
  `task-18-report.md` 与 `output/evidence/judge-launch/native-smoke.json`。最终 Sol 复审发现的
  diagnostics 保护路径 Critical 与 pre-start cleanup Important 已 TDD 修复，launcher fresh
  `47 passed`、affected `151 passed`、full `951 passed`、Playwright `15 passed`，Terra/Sol scoped
  fix re-review 均 CLEAN；实现 commit `6a149ef` 的 post-commit focused `90 passed`、真实端口
  8785 health/stop/cleanup、frontend build、static 与 protected gates 均通过。
- [ ] Task 19：实现 Docker headless/optional GUI profiles；复用 `scripts/run_judge.py` 与同一
  `/health` 入口，构建 Node assets、声明 volumes/ports、验证 container lifecycle；Docker 不可用
  时明确记录 `not_run`，可用时保存 build/run/health evidence。
- [ ] Task 20：替换评委向 root README 与 release docs；统一 exact commands、formal 540 matrix/
  seconds-first/outputs/limitations/GUI-headless wording，添加 stale-claim checker 和公开引用
  边界测试，消除旧 `--quick`/`--steps`/360 口径。
- [ ] Task 21：实现 recoverable cleanup、quarantine 和 allowlisted release copy；只处理 stale
  internal artifacts，严禁删除/移动/覆盖 `赛题资料.7z` 与 `data/intersection_data`；用 dry-run,
  failure-recovery、allowlist、protected hash/count tests 验证。
- [ ] Task 22：按 staged real verification 先 quick/preflight，再执行并冻结 540 valid formal
  outputs；每次 run 写 sealed evidence、source/provenance/safety/attempt lineage，失败保留 evidence
  并生成新 retry id；运行 analyzer/IA/IB 与 exact cardinality/safety gates，记录真实 SUMO/PID。
- [ ] Task 23：从 clean release copy 验证 native launcher、browser workflow、package allowlist、
  static assets、Docker（若环境可用）和第二 Python/SUMO 环境；所有 unavailable 外部检查写
  `not_run`，不把模拟结果冒充 pass。
- [ ] Task 24：只从 frozen Task 22/23 evidence 生成 report/PPT/video 与 figures；每个数字回链到
  run/matrix/source artifact，标注 assumptions/limitations，完成最终 deliverables integrity、
  stale-claim、package 和 whole-branch review。

## Task 17 closeout (2026-08-23)

- Task 17 主实现提交：`933fd42` (`feat: publish verified judge Web console`)。该提交以精确
  22 文件 allowlist 发布 Web console、sealed manifest-derived 顶层 `scene_id`、同场景结果比较、
  六项安全指标、WebSocket 重连竞态防护、真实 phase metrics、browser client `run_dir` 剥离、
  OpenAPI/静态产物和覆盖测试；未暂存 progress、scratch、保护归档或官方场景数据。
- Task 17 `run_dir` Ruling：保留既有 `RunResultModel.run_dir` 生命周期响应字段。Task 16 明确
  冻结 canonical/deprecated routes 及 response models，且只要求新增 result list items 不序列化
  `run_dir`；Task 17 的 “REST client must not expose run_dir” 边界由 start/get/stop/result typed
  client 在进入 store/UI 前统一剥离满足。直接删除服务端字段会破坏 Task 16 契约。Sol 复审据此
  撤回原 Important，该项 CLEAN。
- Task 17 最终措辞收口提交：`6241182` (`fix: clarify sealed judge evidence labels`)。按 TDD 先令
  2 个 Playwright 用例因旧 Simulation 文案和旧 Comparison aria-label 失败，再把当前单次结果
  统一标为 sealed individual-run / sealed run results；保留 “Formal 95% CI awaits Task 22” 作为
  尚未生成的 540-run 矩阵级结论，并同步 hashed production asset。
- Task 17 最新代码门禁（exact HEAD `6241182`）：typecheck exit 0；Vite build exit 0、2,388 modules；
  Playwright `15 passed`；受影响 Python/API/evidence contract `77 passed in 19.64s`；venv compileall
  exit 0；旧误导文案在 `web/src` 与 `api/static/dist` 为零命中；`git diff --cached --check` 通过。
  主实现 exact HEAD `933fd42` 的完整 Python 基线为 `902 passed in 480.49s`。
- Task 17 内置浏览器验收：Codex in-app browser 保持打开 `http://127.0.0.1:8000/`；Simulation
  显示新的 sealed individual-run 分级，Comparison/History 在真实服务无 sealed results 时正确
  空态，Scene 展示 20 个场景且总状态为 `All manifests pass`。
- Task 17 scoped 双复审（staged closeout diff）：Terra Standards 与 Sol Spec 均为 CLEAN，
  Critical/Important/Minor 全部为零；未发现新增可访问性、数据流、路径泄漏、静态资产引用或
  证据过度宣称问题。
- Task 17 保护门禁：`赛题资料.7z` SHA-256 仍为
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`；官方场景数据仍为
  163 tracked / 232 disk；保护路径 worktree/index diff 均为 0。
- Task 17: complete (implementation `933fd42`, closeout fix `6241182`, dual review CLEAN)。
- Global Task 18: complete；实现 commit `6a149ef`，review-fix affected `151 passed`、full
  `951 passed`、Playwright `15 passed`，Terra/Sol scoped re-review CLEAN；exact HEAD post-commit
  focused `90 passed`、PowerShell health/stop/cleanup、frontend build、static/protected gates 通过。
- Global Task 19-24: not started by this closeout；Docker live/second-machine、540-run formal
  matrix、release packaging and final materials remain deferred to their respective global tasks。
