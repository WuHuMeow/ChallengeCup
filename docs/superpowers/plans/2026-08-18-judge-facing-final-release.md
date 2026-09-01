# 评委视角终审发行版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前 SUMO 车路云项目实现为可一键启动、可切换场景、可替换算法、可视化演示、可批量复现且不含内部协作材料的评委终审发行版。

**Architecture:** 保留现有 Python 顶层平铺模块，以 FastAPI 作为唯一后端入口，用算法注册表、标准场景包、运行状态机和单次运行证据合同收紧模块边界。评委端使用 `web/` 下的 React + TypeScript + Vite 静态构建，由 FastAPI 同源提供；SUMO-GUI 由 TraCI 所属运行线程采集最新画面，Web 只显示有界帧缓存，正式批量实验默认使用无界面 SUMO。

**Tech Stack:** Python 3.10+、SUMO 1.27.1、TraCI、FastAPI、Pydantic、React 18、TypeScript 5、Node.js 20、Vite、Recharts、Lucide React、pytest、Playwright、Docker。

**Spec:** `docs/superpowers/specs/2026-08-18-judge-facing-final-release-design.md`

## Global Constraints

- 官方原始数据和 `赛题资料.7z` 只读，不覆盖、不重写、不改哈希。
- 终审包不显示成员代号、项目分工、周任务、内部进度、开发路线或内部验证脚本。
- 正式矩阵为 `20 × 3 × 2 × 3 = 360` 正常运行，加 `20 × 3 × 3 × 1 = 180` 扰动运行，共 540 个唯一组合。
- 正式运行时长为 3600 仿真秒，预热期为 600 仿真秒；步数按场景 `step-length` 换算。
- 算法正式标识为 `fixed_time`、`classic_maxpressure`、`capacity_aware_maxpressure`；旧标识只能在迁移层映射，不能出现在正式矩阵或评委界面。
- 安全硬门槛为碰撞、红灯违规、非法相位转换均为 0；急减速、瞬移、潜在冲突为观察指标。
- 未完成车辆不计入完成车辆的吞吐量、行程时间、延误、停车、燃油和 CO2 均值。
- Web 画面目标为 5–10 FPS、目标机器端到端延迟不高于 500 ms；画面流失败不能中断控制和证据记录。
- 生产前端构建资源随仓库发布，评委运行时不要求 Node.js 或公网 CDN。
- 每个验收项只允许 `pass`、`fail`、`not_run`；没有当前真实证据不得写 `pass`。
- 代码、配置、场景或指标口径改变后，受影响的实验、统计、图表和材料必须重新生成。

---

## 阶段 0：基线、环境和安全边界

### Task 1: 建立当前状态快照和可写工作区

**Files:**
- Create: `output/evidence/release-baseline/README.md`
- Create: `output/evidence/release-baseline/environment.json`
- Create: `scripts/release/preflight.py`
- Create: `tests/test_release_preflight.py`

**Interfaces:**
- `scripts/release/preflight.py` exposes `collect_environment(repo_root: Path) -> dict[str, object]` and `run_preflight(repo_root: Path) -> list[dict[str, object]]`.
- `environment.json` records Python, SUMO, TraCI, dependency, OS, Git commit and source archive hash; no user name or absolute personal path is written to the release evidence.
- `collect_worktree_inventory(repo_root: Path) -> dict[str, object]` records changed/untracked path names and content hashes so existing user changes can be recognized and preserved without copying their content into public evidence.

- [ ] **Step 1: Write the failing preflight tests**

```python
def test_preflight_requires_sumo_1_27_1(monkeypatch, tmp_path):
    monkeypatch.setattr("release.preflight.detect_sumo_version", lambda: "1.26.0")
    result = run_preflight(tmp_path)
    assert result[0]["status"] == "fail"
    assert "1.27.1" in result[0]["detail"]


def test_preflight_does_not_record_personal_absolute_paths(tmp_path):
    payload = collect_environment(tmp_path)
    assert "Users" not in json.dumps(payload)
    assert "environment" in payload
```

- [ ] **Step 2: Run the focused tests and record the expected failure**

Run: `python -m pytest tests/test_release_preflight.py -q`

Expected: FAIL because `release.preflight` and its environment contract do not exist.

- [ ] **Step 3: Implement deterministic environment collection**

Create `scripts/release/__init__.py` and implement `collect_environment()` with subprocess calls for `python --version`, `sumo --version`, `git rev-parse HEAD`, and package versions. Normalize path fields to repository-relative paths before writing JSON. Make `run_preflight()` return explicit `pass`/`fail` records for Python floor, SUMO version, source archive, writable output, and importability. Record the existing dirty worktree inventory before any implementation edit; never reset, overwrite or silently drop those changes.

- [ ] **Step 4: Run the focused tests and the real preflight**

Run: `python -m pytest tests/test_release_preflight.py -q`

Expected: PASS. Then run `python scripts/release/preflight.py --repo-root . --output output/evidence/release-baseline/environment.json`; a missing Docker CLI is recorded as `not_run`, not `pass` or `fail` for the native baseline.

- [ ] **Step 5: Commit the baseline contract**

```bash
git add scripts/release tests/test_release_preflight.py output/evidence/release-baseline/README.md
git commit -m "test: establish release preflight contract"
```

### Task 2: Freeze clean-output and preservation rules

**Files:**
- Create: `scripts/release/output_policy.py`
- Create: `tests/test_output_policy.py`
- Modify: `.gitignore`
- Modify: `output/README.md`

**Interfaces:**
- `is_release_path(path: Path) -> bool` returns whether a path is allowed in the final package.
- `preserved_source_paths(repo_root: Path) -> tuple[Path, ...]` returns the archive and official scene roots that cleanup may never mutate.
- `audit_output_tree(root: Path) -> list[dict[str, object]]` reports cache, internal, stale, release and preserved classes without deleting anything.

- [ ] **Step 1: Write tests for preservation and classification**

```python
def test_official_archive_is_always_preserved(tmp_path):
    archive = tmp_path / "赛题资料.7z"
    archive.write_bytes(b"official")
    assert archive in preserved_source_paths(tmp_path)
    assert is_release_path(archive) is True


def test_pytest_cache_and_personal_venv_are_not_release_paths(tmp_path):
    assert is_release_path(tmp_path / ".pytest_cache") is False
    assert is_release_path(tmp_path / ".venv-native") is False
```

- [ ] **Step 2: Implement a read-only output audit**

Classify `output/runs`, `output/tmp`, `output/pytest-*`, old route evidence, current evidence, deliverables, caches, virtual environments and the official archive. The audit must output reasons and referenced files; it must not call a delete command.

- [ ] **Step 3: Run policy tests and inspect the report**

Run: `python -m pytest tests/test_output_policy.py -q`

Expected: PASS, with the current worktree's user modifications untouched and official data listed as preserved.

- [ ] **Step 4: Commit the policy only**

```bash
git add scripts/release/output_policy.py tests/test_output_policy.py .gitignore output/README.md
git commit -m "chore: define final release preservation policy"
```

---

## 阶段 1：公共契约和算法注册表

### Task 3: Replace hard-coded algorithm factories with a registry

**Files:**
- Create: `algorithms/registry.py`
- Create: `tests/test_algorithm_registry.py`
- Modify: `core/run_models.py`
- Modify: `api/models.py`
- Modify: `api/server.py`
- Modify: `engine/run_service.py`
- Modify: `experiments/runner.py`
- Modify: `engine/events.py`

**Interfaces:**
- `AlgorithmSpec(key: str, display_name: str, factory: Callable[..., BaseControlAlgorithm], formal: bool, aliases: tuple[str, ...])`.
- `AlgorithmRegistry.register(spec: AlgorithmSpec) -> None`.
- `AlgorithmRegistry.get(key: str) -> AlgorithmSpec` and `AlgorithmRegistry.list(formal_only: bool = False) -> tuple[AlgorithmSpec, ...]`.
- `get_algorithm_registry() -> AlgorithmRegistry` returns the process-wide read-only registry after built-ins are registered.
- Canonical keys are `fixed_time`, `classic_maxpressure`, and `capacity_aware_maxpressure`; `ca_maxpressure` maps only to the capacity-aware implementation for migration, while `actuated` remains non-formal and is excluded from the formal list.

- [ ] **Step 1: Add failing registry and contract tests**

```python
def test_formal_registry_has_exactly_three_algorithms():
    assert [item.key for item in get_algorithm_registry().list(formal_only=True)] == [
        "fixed_time",
        "classic_maxpressure",
        "capacity_aware_maxpressure",
    ]


def test_legacy_ca_name_resolves_without_being_public():
    registry = get_algorithm_registry()
    assert registry.get("ca_maxpressure").key == "capacity_aware_maxpressure"
    assert "ca_maxpressure" not in {item.key for item in registry.list(formal_only=True)}
```

- [ ] **Step 2: Implement the registry and canonical request validation**

Move algorithm construction into `algorithms/registry.py`. Change `SUPPORTED_ALGORITHMS` and Pydantic request validation to accept canonical keys; add a migration function used only by legacy endpoints and old artifact readers. Replace `ALGORITHM_FACTORIES` and `experiments.runner.ALGORITHM_MAP` lookups with `registry.get(key).factory`.

- [ ] **Step 3: Update event names and API list output**

Ensure `events.csv`, `/api/algorithms`, OpenAPI, and Web-facing payloads use canonical keys and display names. Legacy API routes can accept the alias but must return the canonical key in the result.

- [ ] **Step 4: Run focused contract tests**

Run: `python -m pytest tests/test_algorithm_registry.py tests/test_api.py tests/test_events.py -q`

Expected: PASS with no formal result containing `actuated` or `ca_maxpressure`.

- [ ] **Step 5: Commit the registry migration**

```bash
git add algorithms/registry.py core/run_models.py api/models.py api/server.py engine/run_service.py experiments/runner.py engine/events.py tests/test_algorithm_registry.py tests/test_api.py tests/test_events.py
git commit -m "refactor: centralize algorithm registration"
```

### Task 4: Add movement-level state contracts

**Files:**
- Create: `core/movements.py`
- Create: `tests/test_movements.py`
- Modify: `core/types.py`
- Modify: `api/models.py`
- Modify: `docs/interface.md`

**Interfaces:**
- `MovementKey(incoming_lane: str, outgoing_lane: str)` is immutable and serializable.
- `MovementState(key: MovementKey, queue_vehicles: float, downstream_queue_vehicles: float, incoming_capacity: float, downstream_capacity: float, downstream_occupancy: float, saturation_rate: float, turn_ratio: float)` validates finite non-negative measurements.
- `PhaseMovementState(phase_index: int, signal_state: str, movements: tuple[MovementState, ...], nominal_duration: float)` contains only one legal phase's measurements.
- `JointState.phase_movements: tuple[PhaseMovementState, ...]` is the only algorithm input for movement pressure; existing `queues` remains for compatibility and display.
- `MovementStateModel` and `PhaseMovementStateModel` are Pydantic adapters with the same fields and `to_domain()` methods.

- [ ] **Step 1: Write tests for movement validation and serialization**

```python
def test_movement_rejects_zero_capacity():
    with pytest.raises(ValueError, match="incoming_capacity"):
        MovementState(MovementKey("in", "out"), 1, 0, 0, 1, 0, 1, 1)


def test_phase_movement_payload_round_trips_through_api_model():
    payload = PhaseMovementStateModel(
        phase_index=0,
        signal_state="Gr",
        nominal_duration=30.0,
        movements=[MovementStateModel(
            incoming_lane="in_0",
            outgoing_lane="out_0",
            queue_vehicles=2.0,
            downstream_queue_vehicles=1.0,
            incoming_capacity=20.0,
            downstream_capacity=20.0,
            downstream_occupancy=0.1,
            saturation_rate=0.5,
            turn_ratio=1.0,
        )],
    )
    assert payload.to_domain().phase_index == payload.phase_index
```

- [ ] **Step 2: Implement the immutable contracts and Pydantic adapters**

Use `dataclass(frozen=True)` for movement keys and phase state. Add explicit units in field docstrings: queues/capacity are vehicles, occupancy is `0..1`, saturation is vehicles per simulation second, and timestamps are simulation seconds.

- [ ] **Step 3: Update interface documentation and run tests**

Run: `python -m pytest tests/test_movements.py tests/test_types_fields.py -q`

Expected: PASS; invalid capacity, occupancy, service rate and phase index are rejected before an algorithm sees them.

- [ ] **Step 4: Commit the state contract**

```bash
git add core/movements.py core/types.py api/models.py docs/interface.md tests/test_movements.py tests/test_types_fields.py
git commit -m "feat: add movement-level traffic state contract"
```

### Task 5: Normalize time and run request contracts

**Files:**
- Create: `core/timebase.py`
- Create: `tests/test_timebase.py`
- Modify: `core/run_models.py`
- Modify: `api/models.py`
- Modify: `config/default.yaml`
- Modify: `experiments/tuning.py`

**Interfaces:**
- `SimulationWindow(duration_seconds: float, warmup_seconds: float)` validates `duration_seconds > warmup_seconds >= 0`.
- `steps_for_seconds(duration_seconds: float, step_length: float) -> int` returns a deterministic ceiling that never ends before the requested simulation time.
- `seconds_for_steps(steps: int, step_length: float) -> float` returns the recorded simulation duration.
- `RunRequest` stores `duration_seconds`, `warmup_seconds`, `seed`, and `step_length_override: float | None`; `steps` becomes a derived compatibility property, not the primary public setting.

- [ ] **Step 1: Write time conversion tests**

```python
def test_one_second_scene_uses_3600_steps_for_formal_window():
    assert steps_for_seconds(3600, 1.0) == 3600


def test_tenth_second_scene_uses_36000_steps_for_formal_window():
    assert steps_for_seconds(3600, 0.1) == 36000


def test_warmup_cannot_equal_or_exceed_duration():
    with pytest.raises(ValueError):
        SimulationWindow(600, 600)
```

- [ ] **Step 2: Implement the timebase and update configuration**

Set `normal` and `high` to `1.0` and `1.25`, default duration to 3600 seconds, warmup to 600 seconds, quick duration to 600 seconds, smoke to 100 steps, and formal seeds to `(42, 43, 44)`. Preserve a CLI `--steps` compatibility option only when explicitly supplied by a test or smoke command.

- [ ] **Step 3: Update API and experiment request construction**

Run requests with no explicit duration use the scene configuration's step length and convert seconds to steps in the runner. Persist both the requested seconds and derived steps in `manifest.json`.

- [ ] **Step 4: Run focused tests and commit**

Run: `python -m pytest tests/test_timebase.py tests/test_run_models.py tests/test_experiments.py -q`

Expected: PASS, with no default `1.5` flow or universal `36000`-step assumption remaining in formal request construction.

```bash
git add core/timebase.py core/run_models.py api/models.py config/default.yaml experiments/tuning.py tests/test_timebase.py tests/test_run_models.py tests/test_experiments.py
git commit -m "fix: express simulation windows in simulation seconds"
```

---

## 阶段 2：官方场景、变体和真实 TraCI 状态

### Task 6: Build validated standard scene manifests

**Files:**
- Create: `scenes/models.py`
- Create: `scenes/validator.py`
- Create: `scenes/importer.py`
- Create: `tests/test_scene_validation.py`
- Modify: `scenes/registry.py`
- Modify: `scenes/__init__.py`
- Modify: `docs/interface.md`

**Interfaces:**
- `SceneManifest` contains `scene_id`, `source_files`, `sha256`, `step_length`, `tls_ids`, `lane_ids`, `movement_count`, `validation_status`, and `warnings`.
- `SceneValidator.validate(scene_root: Path) -> SceneManifest` parses XML structurally, checks required files, signal phases, route references, step length and movement mappings, and returns `fail` for unusable scenes.
- `SceneImporter.import_scene(source_root: Path, destination_root: Path) -> SceneManifest` writes a self-contained standardized package only after validation succeeds.
- `SceneRegistry.list_scenes(formal_only: bool = False) -> tuple[SceneManifest, ...]` returns read-only metadata.

- [ ] **Step 1: Write scene fixture tests**

```python
def test_official_scene_manifest_contains_all_required_inputs(official_scene_root):
    manifest = SceneValidator().validate(official_scene_root)
    assert manifest.validation_status == "pass"
    assert {"net", "flow", "route", "turn", "sumocfg"} <= set(manifest.source_files)


def test_import_rejects_missing_movement_mapping(tmp_path):
    with pytest.raises(SceneValidationError, match="movement"):
        SceneImporter().import_scene(tmp_path / "broken", tmp_path / "packages")
```

- [ ] **Step 2: Implement read-only source discovery and hashes**

Resolve both `高精地图` and `高清地图`, record repository-relative paths, compute SHA-256 in streaming mode, and never write inside `data/intersection_data`.

- [ ] **Step 3: Implement structural XML and SUMO preflight validation**

Parse `.net.xml`, `.flow.xml`, `.rou.xml`, `.turn.xml`, `.sumocfg` and timing input with structured parsers. Verify referenced vehicle types, lanes, TLS programs, `step-length`, route connectivity, controlled links and outgoing lanes. Return warnings for known source-data warnings without converting them to success claims.

- [ ] **Step 4: Update the registry and run all scene tests**

Run: `python -m pytest tests/test_scene_validation.py tests/test_scenes.py tests/test_variants.py -q`

Expected: PASS for all 20 official scenes and explicit `fail` for malformed fixtures; no generated files appear under the official source root.

- [ ] **Step 5: Commit the scene contract**

```bash
git add scenes/models.py scenes/validator.py scenes/importer.py scenes/registry.py scenes/__init__.py docs/interface.md tests/test_scene_validation.py tests/test_scenes.py tests/test_variants.py
git commit -m "feat: validate and package SUMO scenes"
```

### Task 7: Fix source-preserving traffic and disturbance variants

**Files:**
- Create: `scenes/disturbances.py`
- Create: `tests/test_disturbances.py`
- Modify: `scenes/variant.py`
- Modify: `core/run_models.py`
- Modify: `api/models.py`
- Modify: `config/default.yaml`

**Interfaces:**
- `DisturbanceSpec(kind: Literal["construction", "event_demand", "vehicle_failure"], begin_seconds: float, end_seconds: float, target: str, intensity: float)`.
- `VariantGenerator.generate_bundle(scene_manifest, flow_multiplier, variant, output_dir) -> VariantBundle` scales the source demand exactly once, writes one closure/failure/event additional file when requested, and records parent hashes.
- `validate_variant(bundle: VariantBundle) -> list[str]` rejects duplicate demand IDs, missing routes, invalid intervals, inaccessible lanes and conflicting additional files.

- [ ] **Step 1: Write regression tests for duplicate flow and disturbance contracts**

```python
def test_flow_multiplier_does_not_duplicate_original_flows(scene_fixture, tmp_path):
    bundle = VariantGenerator().generate_bundle(scene_fixture, 1.25, None, tmp_path)
    assert count_vehicle_definitions(bundle.flow_file) == count_vehicle_definitions(scene_fixture.flow_file)
    assert flow_probability_sum(bundle.flow_file) == pytest.approx(1.25 * flow_probability_sum(scene_fixture.flow_file))


def test_construction_variant_records_parent_hash_and_interval(scene_fixture, tmp_path):
    spec = DisturbanceSpec("construction", 600, 1200, "E0_0", 1.0)
    bundle = VariantGenerator().generate_bundle(scene_fixture, 1.0, spec, tmp_path)
    assert bundle.manifest["parent_sha256"]
    assert bundle.manifest["disturbance"]["kind"] == "construction"
```

- [ ] **Step 2: Remove the duplicate-flow path**

Refactor `_scale_tree()` and `generate_bundle()` so each original `<flow>` or `<vehicle>` definition is transformed in place into one derived definition. Do not append a second unscaled source file to the SUMO configuration.

- [ ] **Step 3: Add the three required disturbance generators**

Implement lane closure for construction, demand distribution changes for large events, and a stopped vehicle or lane blockage for vehicle failure. Each generated additional file has a deterministic name and is included in `variant_manifest.json`.

- [ ] **Step 4: Run focused variant tests and commit**

Run: `python -m pytest tests/test_disturbances.py tests/test_variants.py -q`

Expected: PASS with one demand population per variant and no deliberate collision injection.

```bash
git add scenes/disturbances.py scenes/variant.py core/run_models.py api/models.py config/default.yaml tests/test_disturbances.py tests/test_variants.py
git commit -m "fix: make traffic and disturbance variants source preserving"
```

### Task 8: Add movement state extraction and safety observations

**Files:**
- Create: `engine/movement_state.py`
- Create: `engine/safety.py`
- Create: `tests/test_movement_state.py`
- Create: `tests/test_safety_metrics.py`
- Modify: `engine/traci_bridge.py`
- Modify: `engine/collector.py`
- Modify: `engine/events.py`
- Modify: `core/types.py`

**Interfaces:**
- `MovementStateBuilder.from_traci(bridge: TraCIBridge, tls_id: str) -> tuple[PhaseMovementState, ...]` builds movement-to-phase mappings once per run.
- `SafetyObservationCollector.observe(previous: JointState | None, current: JointState, action_results: tuple[ActionResult, ...]) -> tuple[SafetyEvent, ...]` emits collision, red-light, illegal-transition, harsh-braking, teleport and potential-conflict events.
- `MetricSummary.completed_vehicle_count`, `unfinished_vehicle_count`, `fuel_ml`, and `co2_g` are explicit fields with units; `MetricSummary.from_tripinfo(completed, unfinished)` is a deterministic fixture/parser entrypoint.

- [ ] **Step 1: Write MockBridge movement and safety tests**

```python
def test_controlled_links_build_phase_movements(mock_bridge):
    phases = MovementStateBuilder.from_traci(mock_bridge, "tls0")
    assert all(phase.movements for phase in phases if "G" in phase.signal_state)


def test_unfinished_vehicles_are_not_throughput():
    summary = MetricSummary.from_tripinfo(completed=[{"id": "a"}], unfinished=[{"id": "b"}])
    assert summary.completed_vehicle_count == 1
    assert summary.throughput == 1
```

- [ ] **Step 2: Implement movement extraction from controlled links**

Use `getControlledLinks()`, lane lengths, lane vehicle counts, lane occupancy and outgoing lanes. Resolve turn ratios from `.turn.xml` or current route observations. Compute capacity from a frozen vehicle length plus minimum gap and record the calculation inputs in the run manifest.

- [ ] **Step 3: Implement safety event collection and units**

Use SUMO collision output and TraCI vehicle/lane transitions for collisions, red-light violations and teleports; use speed deltas for harsh braking and spatial/time proximity for potential conflicts. Keep all events run-scoped and include `run_id`, simulation seconds, entity IDs, source and confidence.

- [ ] **Step 4: Run state and metric tests**

Run: `python -m pytest tests/test_movement_state.py tests/test_safety_metrics.py tests/test_traci_outputs.py tests/test_vehicles.py -q`

Expected: PASS with completed and unfinished vehicles separated and all movement capacities positive for validated official scenes.

- [ ] **Step 5: Commit the TraCI state layer**

```bash
git add engine/movement_state.py engine/safety.py engine/traci_bridge.py engine/collector.py engine/events.py core/types.py tests/test_movement_state.py tests/test_safety_metrics.py tests/test_traci_outputs.py tests/test_vehicles.py
git commit -m "feat: collect movement and safety evidence from TraCI"
```

---

## 阶段 3：算法和运行生命周期

### Task 9: Freeze traceable fixed timing and implement independent classic MaxPressure

**Files:**
- Create: `algorithms/classic_max_pressure.py`
- Create: `algorithms/fixed_time_plan.py`
- Create: `tests/test_classic_max_pressure.py`
- Create: `tests/test_fixed_time_plan.py`
- Modify: `algorithms/base.py`
- Modify: `algorithms/ca_max_pressure.py`
- Modify: `algorithms/fixed_time.py`
- Modify: `algorithms/__init__.py`

**Interfaces:**
- `FixedTimePlanResolver.resolve(scene: Scene) -> ResolvedTimingPlan` selects a standardized scene timing plan, official Excel plan, or source `.net.xml` plan in that order and records source path/hash/program ID; no arbitrary fallback is allowed.
- `FixedTimeAlgorithm.name == "fixed_time"` and its manifest contains the resolved timing provenance.
- `ClassicMaxPressureAlgorithm.init(scene: Scene) -> None`.
- `ClassicMaxPressureAlgorithm.step(state: JointState) -> list[ControlAction]` computes `P0(p) = sum(s_m * (q_i - q_j))` over legal green phases and emits a deterministic target phase.
- `ClassicMaxPressureAlgorithm.reset() -> None` clears current target and decision history.
- `ClassicMaxPressureAlgorithm.name == "classic_maxpressure"`.

- [ ] **Step 1: Write formula and tie-break tests**

```python
import copy
import dataclasses


def test_fixed_time_plan_records_source_hash(scene):
    plan = FixedTimePlanResolver().resolve(scene)
    assert plan.source_sha256
    assert plan.program_id


def test_fixed_time_rejects_scene_without_a_legal_plan(scene_without_timing):
    with pytest.raises(FixedTimePlanError, match="timing plan"):
        FixedTimePlanResolver().resolve(scene_without_timing)


def test_classic_pressure_uses_downstream_queue_and_service_rate(state):
    actions = ClassicMaxPressureAlgorithm().step(state)
    assert actions[0].value == 1


def test_classic_pressure_does_not_use_capacity_prediction_or_spillback(state):
    baseline = ClassicMaxPressureAlgorithm().step(state)
    changed = copy.deepcopy(state)
    changed.phase_movements = tuple(
        dataclasses.replace(
            phase,
            movements=tuple(
                dataclasses.replace(movement, downstream_occupancy=1.0)
                for movement in phase.movements
            ),
        )
        for phase in changed.phase_movements
    )
    assert ClassicMaxPressureAlgorithm().step(changed) == baseline
```

- [ ] **Step 2: Implement the traceable fixed-time resolver and independent classic baseline**

Resolve and record one deterministic fixed timing program before the run starts. For classic MaxPressure, use only `phase_movements`, current phase, elapsed phase time and the shared safety executor. Do not import `CloudPolicy`, EWMA, capacity-normalized fields or capacity-aware thresholds into the classic module.

- [ ] **Step 3: Run algorithm tests and commit**

Run: `python -m pytest tests/test_fixed_time_plan.py tests/test_classic_max_pressure.py tests/test_algorithms.py -q`

Expected: PASS; the baseline is independently attributable and has no CA-MP enhancement flags.

```bash
git add algorithms/fixed_time_plan.py algorithms/fixed_time.py algorithms/classic_max_pressure.py algorithms/ca_max_pressure.py algorithms/base.py algorithms/__init__.py tests/test_fixed_time_plan.py tests/test_classic_max_pressure.py tests/test_algorithms.py
git commit -m "feat: freeze fixed timing and classic MaxPressure baselines"
```

### Task 10: Refactor capacity-aware MaxPressure into layered ablations

**Files:**
- Create: `algorithms/capacity_aware_max_pressure.py`
- Create: `tests/test_capacity_aware_max_pressure.py`
- Modify: `algorithms/ca_max_pressure.py`
- Modify: `cloud/cloud_policy.py`
- Modify: `engine/edge_channel.py`
- Modify: `config/default.yaml`

**Interfaces:**
- `CapacityAwareConfig(capacity_normalization: bool, spillback_gate: bool, prediction: bool, min_green: float, max_green: float, overflow_threshold: float)`.
- `CapacityAwareConfig.m0()`, `.m1()`, `.m2()`, `.m3()`, and `.default()` return frozen configurations for the ablation layers.
- `CapacityAwareMaxPressureAlgorithm(config: CapacityAwareConfig, cloud_policy: CloudPolicy | None = None)`.
- `phase_score(state: PhaseMovementState, config: CapacityAwareConfig) -> float` implements `P1(p)`, optional downstream blocking, and optional prediction in separate branches.
- `PhaseScore(score: float, movement_ids: tuple[str, ...], blocked_movements: tuple[str, ...])` is the serializable score breakdown.
- `CapacityAwareMaxPressureAlgorithm.score_breakdown(state: JointState) -> dict[int, PhaseScore]` returns score, selected movement IDs and blocked movement IDs for Web/evidence inspection.
- `ClassicMaxPressureAlgorithm.score_breakdown(state: JointState) -> dict[int, float]` exposes the unmodified M0 phase scores for comparison tests.
- `CapacityAwareMaxPressureAlgorithm.name == "capacity_aware_maxpressure"`.
- `EdgeMessage(run_id: str, simulation_time: float, sent_at: float, expires_at: float, payload_version: str, payload: JointState)` is the cloud-edge envelope; `EdgeChannel.send(message)` and `receive(now: float)` drop expired or direction-disallowed messages.

- [ ] **Step 1: Write M0–M4 ablation tests**

```python
def test_m0_matches_classic_without_capacity_spillback_or_prediction(state):
    assert CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m0()).score_breakdown(state) == ClassicMaxPressureAlgorithm().score_breakdown(state)


def test_m1_prefers_lower_capacity_for_equal_queue(state):
    actions = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m1()).step(state)
    assert actions[0].value == 1


def test_m2_blocks_only_movements_with_full_downstream_lane(state):
    scores = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m2()).score_breakdown(state)
    assert scores[0].blocked_movements == ("in_a->out_a",)


def test_m4_prediction_is_disabled_by_default(state):
    assert CapacityAwareConfig.default().prediction is False
```

- [ ] **Step 2: Implement formula, overflow protection and dynamic green**

Compute normalized movement pressure only when both capacities are positive. Set blocked movement service to zero at the threshold, keep a phase viable when it has an unblocked demanded movement, and return a safe current-phase fallback if all candidates are blocked. Clamp dynamic green to configured minimum and maximum. Log every score component and reason.

- [ ] **Step 3: Move EWMA behind an explicit feature flag**

Correct the prediction unit to vehicles over a horizon, not `veh/h` divided directly by capacity. Record `prediction_enabled`, `horizon_seconds`, and `prediction_weight` in the manifest. Default it to false until ablation results authorize enabling it.

- [ ] **Step 4: Test the cloud-edge message envelope and delay**

Add tests to `tests/test_edge_channel.py` that assert a message sent at simulation time 10 with delay 2 is received at time 12, an expired message is dropped, and a message with a disallowed direction is rejected with an event record.

- [ ] **Step 5: Run focused tests and commit**

Run: `python -m pytest tests/test_capacity_aware_max_pressure.py tests/test_cloud.py tests/test_algorithms.py -q`

Expected: PASS with each M0–M4 layer attributable and prediction disabled by default.

```bash
git add algorithms/capacity_aware_max_pressure.py algorithms/ca_max_pressure.py cloud/cloud_policy.py engine/edge_channel.py config/default.yaml tests/test_capacity_aware_max_pressure.py tests/test_cloud.py tests/test_edge_channel.py tests/test_algorithms.py
git commit -m "feat: layer capacity-aware MaxPressure ablations"
```

### Task 11: Centralize safety execution and action fallback

**Files:**
- Create: `engine/safety_executor.py`
- Create: `tests/test_safety_executor.py`
- Modify: `engine/action_validation.py`
- Modify: `engine/traci_bridge.py`
- Modify: `algorithms/classic_max_pressure.py`
- Modify: `algorithms/capacity_aware_max_pressure.py`

**Interfaces:**
- `SafetyExecutor.apply(actions: Sequence[ControlAction], state: JointState, bridge: TraCIBridge) -> tuple[ActionResult, ...]` is the only code path that writes signal actions.
- `SafetyExecutor.next_transition(current_phase: int, target_phase: int, phases: Sequence[PhaseMovementState]) -> tuple[int, float] | None` returns a legal yellow/all-red transition.
- `SafetyExecutor.fallback(state: JointState) -> list[ControlAction]` preserves the current safe phase or fixed timing.

- [ ] **Step 1: Write tests for minimum green, yellow, all-red and illegal action rejection**

```python
def test_phase_change_before_min_green_is_rejected(state, bridge):
    result = SafetyExecutor().apply([set_phase(2)], state, bridge)
    assert result[0].accepted is False
    assert "min_green" in result[0].detail


def test_phase_change_inserts_yellow_and_all_red(state, bridge):
    transition = SafetyExecutor().next_transition(state.current_phase, 2, state.phase_movements)
    assert transition is not None
    assert transition[1] in {3.0, 1.0}
```

- [ ] **Step 2: Implement the executor and remove algorithm-specific transition code**

Move transition sequencing out of `ca_max_pressure.py`. The executor records accepted and rejected actions, uses simulation seconds, and returns a deterministic fallback on invalid phase or duration.

- [ ] **Step 3: Run safety tests and commit**

Run: `python -m pytest tests/test_safety_executor.py tests/test_action_validation.py tests/test_events.py -q`

Expected: PASS with no algorithm able to bypass the executor.

```bash
git add engine/safety_executor.py engine/action_validation.py engine/traci_bridge.py algorithms/classic_max_pressure.py algorithms/capacity_aware_max_pressure.py tests/test_safety_executor.py tests/test_action_validation.py tests/test_events.py
git commit -m "feat: enforce one safe signal action path"
```

### Task 12: Make RunService and SimulationRunner lifecycle-safe

**Files:**
- Create: `engine/run_state.py`
- Create: `tests/test_run_lifecycle.py`
- Modify: `engine/run_service.py`
- Modify: `engine/runner.py`
- Modify: `engine/artifacts.py`
- Modify: `core/run_models.py`

**Interfaces:**
- `RunStateMachine.transition(run_id: str, new_status: RunStatus, reason: str) -> RunResult` rejects invalid transitions.
- `RunService.submit(request: RunRequest) -> RunResult`, `get(run_id: str) -> RunResult | None`, `stop(run_id: str) -> bool`, and `switch_scene(run_id: str, request: RunRequest) -> tuple[RunResult, RunResult]` are thread-safe.
- `SimulationRunner.run(window: SimulationWindow, stop_event: threading.Event, frame_sink: Callable[[FrameRecord], None] | None = None) -> RunResult` owns the SUMO process and emits terminal metadata on every exit.
- `RunArtifacts.write_manifest(payload: Mapping[str, object])` and `write_status(status, reason)` atomically write `manifest.json` and `status.json`.

- [ ] **Step 1: Write lifecycle and process cleanup tests**

```python
def test_stop_is_idempotent_and_terminal_status_is_preserved(fake_runner, request):
    service = RunService(runner_factory=fake_runner)
    queued = service.submit(request)
    assert service.stop(queued.run_id) is True
    assert service.stop(queued.run_id) is False
    assert service.get(queued.run_id).status in {
        RunStatus.COMPLETED, RunStatus.STOPPED, RunStatus.INTERRUPTED, RunStatus.FAILED
    }


def test_switch_scene_marks_old_run_interrupted_and_starts_new_scene(fake_runner, service, active_id, request_for_scene):
    old, new = service.switch_scene(active_id, request_for_scene("2"))
    assert old.status == RunStatus.INTERRUPTED
    assert new.run_dir.name != old.run_dir.name
```

- [ ] **Step 2: Implement the state machine and registry-backed construction**

Remove the hard-coded factory map. Allocate one run directory and one `run_id` before scheduling, write `queued`, and transition through `starting`, `running`, `stopping`, and a single terminal state. Stop must signal the runner, wait for its owned process, and never kill another run.

- [ ] **Step 3: Add seconds-based runner termination and process cleanup**

Read `step-length` from the validated scene, derive target steps from `SimulationWindow`, stop at simulation seconds, and distinguish `completed`, `interrupted`, `disconnected`, `ended_early` and `failed`. Always close TraCI and terminate the exact child PID recorded in the manifest.

- [ ] **Step 4: Run lifecycle tests and a 100-step real SUMO smoke run**

Run: `python -m pytest tests/test_run_lifecycle.py tests/test_run_service.py tests/test_runner_channel.py tests/test_artifacts.py -q`

Then run: `python examples/run_fixed_time.py 1 --steps 100` or the new smoke entrypoint and verify no SUMO process remains after exit.

- [ ] **Step 5: Commit lifecycle changes**

```bash
git add engine/run_state.py engine/run_service.py engine/runner.py engine/artifacts.py core/run_models.py tests/test_run_lifecycle.py tests/test_run_service.py tests/test_runner_channel.py tests/test_artifacts.py
git commit -m "fix: make run lifecycle and scene switching safe"
```

---

## 阶段 4：证据、实验矩阵和统计

### Task 13: Freeze run-scoped evidence and metric semantics

**Files:**
- Create: `experiments/evidence.py`
- Create: `tests/test_evidence_contract.py`
- Modify: `engine/artifacts.py`
- Modify: `experiments/metrics.py`
- Modify: `experiments/summary.py`
- Modify: `visualization/report.py`

**Interfaces:**
- `RunManifest(run_id, code_commit, scene_manifest_sha256, algorithm, parameters, flow_multiplier, seed, duration_seconds, warmup_seconds, derived_steps, sumo_version, python_version, prediction_enabled)`.
- `EvidenceWriter.begin(manifest: RunManifest) -> None`, `record_event(event: SafetyEvent) -> None`, `finalize(status: RunStatus, summary: RunSummary) -> None`.
- `MetricSummary.from_raw_outputs(run_dir: Path, warmup_seconds: float) -> MetricSummary` excludes unfinished vehicles from completed-vehicle metrics and preserves their counts separately.
- `EvidenceReader.validate(run_dir: Path) -> list[EvidenceIssue]` checks hashes, required fields, terminal status and non-empty outputs.

- [ ] **Step 1: Write evidence contract tests**

```python
def test_completed_and_unfinished_tripinfo_are_separate(tmp_path):
    summary = MetricSummary.from_raw_outputs(tmp_path, warmup_seconds=600)
    assert summary.completed_vehicle_count == 2
    assert summary.unfinished_vehicle_count == 1
    assert summary.throughput == 2


def test_manifest_contains_code_scene_and_environment_provenance(tmp_path):
    issues = EvidenceReader.validate(tmp_path)
    assert issues == []
    required_fields = {"run_id", "code_commit", "scene_manifest_sha256", "sumo_version"}
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert required_fields <= set(manifest)
```

- [ ] **Step 2: Implement atomic manifest, status and summary writing**

Write `manifest.json`, `provenance.json`, `status.json`, `events.csv`, `metrics.csv`, `summary.json` and hashes atomically. Include source file hashes, actual step length, requested seconds, derived steps, run state, failure reason and all metric units.

- [ ] **Step 3: Correct tripinfo, fuel, CO2 and safety aggregation**

Parse SUMO outputs by completion status. Record fuel and CO2 independently. Exclude warmup samples by simulation seconds. Add collision, red-light, illegal-transition, harsh-braking, teleport and potential-conflict counts to every summary.

- [ ] **Step 4: Run evidence tests and commit**

Run: `python -m pytest tests/test_evidence_contract.py tests/test_metrics.py tests/test_analyze_matrix.py -q`

Expected: PASS with no unfinished vehicle counted as throughput and no generated summary lacking provenance.

```bash
git add experiments/evidence.py experiments/metrics.py experiments/summary.py engine/artifacts.py visualization/report.py tests/test_evidence_contract.py tests/test_metrics.py tests/test_analyze_matrix.py
git commit -m "feat: define run-scoped evidence and metric semantics"
```

### Task 14: Implement the frozen 540-run experiment matrix

**Files:**
- Create: `experiments/matrix.py`
- Create: `experiments/statistics.py`
- Create: `tests/test_formal_matrix.py`
- Modify: `experiments/runner.py`
- Modify: `scripts/run_pdf_matrix.py`
- Modify: `scripts/analyze_matrix.py`
- Modify: `config/default.yaml`

**Interfaces:**
- `FormalMatrix.normal() -> tuple[RunSpec, ...]` returns exactly 360 specs for algorithms `fixed_time`, `classic_maxpressure`, `capacity_aware_maxpressure`, flows `1.0`, `1.25`, seeds `42`, `43`, `44`, and scenes `1..20`.
- `FormalMatrix.disturbance() -> tuple[RunSpec, ...]` returns exactly 180 specs with construction, event demand and vehicle failure, seed `42`.
- `run_matrix(matrix: Sequence[RunSpec], output_root: Path, resume: bool) -> MatrixReport` refuses duplicate IDs, resumes only missing/failed specs, and never overwrites a completed run.
- `paired_statistics(frame: DataFrame, candidate: str, baseline: str) -> PairedResult` returns differences, relative change, effect size, 95% confidence interval, improved unit count, worst unit and safety eligibility.

- [ ] **Step 1: Write exact matrix tests**

```python
def test_normal_matrix_has_360_unique_specs():
    specs = FormalMatrix.normal()
    assert len(specs) == 360
    assert len({item.run_key for item in specs}) == 360
    assert {item.algorithm for item in specs} == {"fixed_time", "classic_maxpressure", "capacity_aware_maxpressure"}
    assert {item.flow_multiplier for item in specs} == {1.0, 1.25}
    assert {item.seed for item in specs} == {42, 43, 44}


def test_disturbance_matrix_has_180_specs_and_fixed_seed():
    specs = FormalMatrix.disturbance()
    assert len(specs) == 180
    assert {item.disturbance.kind for item in specs} == {"construction", "event_demand", "vehicle_failure"}
    assert {item.seed for item in specs} == {42}
```

- [ ] **Step 2: Implement deterministic matrix and resume behavior**

Persist `matrix_manifest.json` before execution. Derive each run key from scene, algorithm, load, seed and disturbance parameters. On resume, load `status.json`; completed valid runs are immutable, failed runs are retried into a new run ID with a parent failure reference.

- [ ] **Step 3: Implement paired statistics and default selection**

Use paired differences by scene/load/seed. Candidate eligibility requires all safety gates zero, a mean travel-time CI upper bound below zero, and at least 21 of 40 normal scene/load units with lower three-seed mean than the baseline. If no candidate is eligible, select `fixed_time` as default and report no improvement claim.

- [ ] **Step 4: Replace legacy matrix assumptions**

Rewrite `scripts/run_pdf_matrix.py` to expose `--profile smoke|quick|formal`, `--duration-seconds`, `--warmup-seconds`, `--output-root`, `--resume`, and `--seed`. Rewrite `scripts/analyze_matrix.py` to reject old `actuated`, old `1.5` matrices and incomplete outputs instead of silently normalizing them.

- [ ] **Step 5: Run matrix contract tests and commit**

Run: `python -m pytest tests/test_formal_matrix.py tests/test_analyze_matrix.py tests/test_experiments.py -q`

Expected: PASS; old matrices fail with an explicit schema error and the new matrix reports 540 unique expected keys.

```bash
git add experiments/matrix.py experiments/statistics.py experiments/runner.py scripts/run_pdf_matrix.py scripts/analyze_matrix.py config/default.yaml tests/test_formal_matrix.py tests/test_analyze_matrix.py tests/test_experiments.py
git commit -m "feat: freeze the 540-run formal experiment matrix"
```

---

## 阶段 5：评委端后端、SUMO 画面和前端

### Task 15: Add runtime event and frame publication

**Files:**
- Create: `visualization/frame_publisher.py`
- Create: `api/realtime.py`
- Create: `tests/test_frame_publisher.py`
- Modify: `engine/runner.py`
- Modify: `engine/traci_bridge.py`
- Modify: `engine/run_service.py`

**Interfaces:**
- `FrameRecord(run_id: str, sequence: int, simulation_time: float, png: bytes, captured_at: float)`.
- `FramePublisher.publish(record: FrameRecord) -> None`, `latest(run_id: str) -> FrameRecord | None`, `clear(run_id: str) -> None` stores at most one frame per run.
- `RealtimeHub.publish(run_id: str, message: Mapping[str, object]) -> None` and `subscribe(run_id: str) -> AsyncIterator[dict[str, object]]` publish status, metrics and action events without owning TraCI.
- `SimulationRunner` calls `capture_gui_frame()` only from its TraCI-owning thread; the API never calls TraCI directly.

- [ ] **Step 1: Write frame and event tests**

```python
def test_frame_publisher_drops_old_frame():
    publisher = FramePublisher()
    publisher.publish(FrameRecord("r", 1, 1.0, b"old", 1.0))
    publisher.publish(FrameRecord("r", 2, 2.0, b"new", 2.0))
    assert publisher.latest("r").sequence == 2
    assert publisher.size("r") == 1


def test_realtime_hub_does_not_block_when_frame_is_slow():
    hub = RealtimeHub()
    hub.publish("r", {"type": "metrics", "simulation_time": 1.0})
    assert hub.latest("r")["type"] == "metrics"
```

- [ ] **Step 2: Implement SUMO-GUI screenshot capture**

Add `TraciBridge.capture_gui_frame(view_id: str, output: BinaryIO) -> FrameRecord | None`. Use `traci.gui.screenshot()` to a run-scoped temporary PNG, read it into memory, replace the single latest frame, and delete the temporary file. Capture adaptively between 5 and 10 FPS; skip capture while the frame slot is occupied by a newer frame.

- [ ] **Step 3: Publish independent metrics and action events**

Emit status, signal action result, metric snapshot, safety event and frame metadata as separate messages containing `run_id` and simulation seconds. On stream failure, continue the runner and retain evidence.

- [ ] **Step 4: Run focused tests and commit**

Run: `python -m pytest tests/test_frame_publisher.py tests/test_runner_channel.py tests/test_run_lifecycle.py -q`

Expected: PASS; frame storage is bounded to one and no API thread imports or calls TraCI.

```bash
git add visualization/frame_publisher.py api/realtime.py engine/runner.py engine/traci_bridge.py engine/run_service.py tests/test_frame_publisher.py tests/test_runner_channel.py tests/test_run_lifecycle.py
git commit -m "feat: publish bounded SUMO frames and runtime events"
```

### Task 16: Extend FastAPI for judge workflows

**Files:**
- Create: `api/static.py`
- Create: `api/websocket.py`
- Create: `tests/test_judge_api.py`
- Modify: `api/server.py`
- Modify: `api/models.py`
- Modify: `docs/api/openapi.json`

**Interfaces:**
- `GET /api/algorithms` returns canonical formal and optional algorithms from the registry.
- `GET /api/scenes` returns validated scene manifests and warnings.
- `POST /api/runs` accepts canonical algorithm, scene, duration seconds, flow, seed and disturbance.
- `GET /api/runs/{run_id}/frame?sequence=N` returns `image/png` with `X-Run-Id`, `X-Frame-Sequence` and `X-Simulation-Time` headers.
- `WS /api/runs/{run_id}/events` sends status, metrics, action, safety and frame metadata messages.
- `POST /api/runs/{run_id}/native-gui` requests the desktop launcher to show/focus the owned SUMO-GUI window or returns 409 with a clear unsupported-environment reason.
- `GET /api/results` and `GET /api/results/{run_id}` expose only validated evidence summaries, not arbitrary filesystem paths.

- [ ] **Step 1: Write API contract tests**

```python
def test_algorithm_endpoint_excludes_legacy_formal_names(client):
    payload = client.get("/api/algorithms").json()
    assert {item["key"] for item in payload["formal"]} == {
        "fixed_time", "classic_maxpressure", "capacity_aware_maxpressure"
    }


def test_frame_endpoint_returns_latest_png(client, frame_publisher):
    response = client.get("/api/runs/r/frame")
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-frame-sequence"] == "2"
```

- [ ] **Step 2: Implement static serving and API lifespan cleanup**

Mount built `web/dist` at `/`, serve `index.html`, and shut down the RunService, RealtimeHub and frame publisher during FastAPI lifespan shutdown. Preserve legacy API routes as explicit aliases returning canonical data.

- [ ] **Step 3: Implement WebSocket and frame endpoints**

Use an async adapter around `RealtimeHub`; do not perform blocking file or TraCI work on the event loop. Return 404 for unknown run IDs, 409 for unavailable native GUI, and structured error payloads for invalid requests.

- [ ] **Step 4: Run API tests and commit**

Run: `python -m pytest tests/test_judge_api.py tests/test_api.py tests/test_api_contract.py -q`

Expected: PASS with OpenAPI matching route schemas and no filesystem path traversal in result endpoints.

```bash
git add api/static.py api/websocket.py api/server.py api/models.py docs/api/openapi.json tests/test_judge_api.py tests/test_api.py tests/test_api_contract.py
git commit -m "feat: expose judge runtime and evidence APIs"
```

### Task 17: Build the Web console and one-click judge demo

**Files:**
- Create: `web/package.json`
- Create: `web/package-lock.json`
- Create: `web/tsconfig.json`
- Create: `web/vite.config.ts`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/api/client.ts`
- Create: `web/src/state/runStore.ts`
- Create: `web/src/components/SimulationView.tsx`
- Create: `web/src/components/ComparisonView.tsx`
- Create: `web/src/components/HistoryView.tsx`
- Create: `web/src/components/SceneView.tsx`
- Create: `web/src/components/MetricPanel.tsx`
- Create: `web/src/components/SumoFrame.tsx`
- Create: `web/src/components/ErrorBanner.tsx`
- Create: `web/src/styles.css`
- Create: `web/tests/judge-flow.spec.ts`

**Interfaces:**
- `api/client.ts` defines typed `listScenes()`, `listAlgorithms()`, `startRun()`, `stopRun()`, `getMetrics()`, `getFrame()`, `openNativeGui()` and `subscribeEvents()` functions.
- `runStore` exposes `selectedScene`, `selectedAlgorithm`, `selectedLoad`, `selectedDisturbance`, `activeRun`, `metrics`, `events`, `frameSequence` and `error`.
- `SimulationView` implements quick demo sequence `scene -> fixed_time -> capacity_aware_maxpressure -> comparison` and labels quick output separately from formal evidence.

- [ ] **Step 1: Create the frontend build and typed client**

Use React 18, TypeScript 5, Vite, `recharts`, `lucide-react`, and Playwright. Configure Vite output to `api/static/dist`, proxy `/api` to FastAPI during development, and use no external CDN. Fail the build on TypeScript errors.

- [ ] **Step 2: Implement the real-time simulation view**

Render the actual SUMO PNG frame with sequence and simulation-time labels, algorithm and scene selectors, run/stop/switch controls, signal phase status, safety badges, metric cards, and a button to show native SUMO-GUI. Use bounded polling for frame updates and WebSocket for metrics/events. Show explicit loading, disconnected, unsupported GUI and failed-run states.

- [ ] **Step 3: Implement comparison, history and scene management views**

Comparison view renders travel time, queue, throughput, safety, fuel and CO2 with uncertainty and source run IDs. History view filters validated runs and opens their manifest/summary. Scene view displays source, hash, step length, validation warnings and import status; it never offers editing of official raw files.

- [ ] **Step 4: Implement the one-click judge demo and accessible controls**

Use icon buttons with Lucide icons, labels/tooltips for unfamiliar icons, stable layout dimensions and responsive desktop widths. The demo must run only a representative quick scene, then display formal precomputed evidence only when marked as such. A stale frame cannot overwrite a newer sequence.

- [ ] **Step 5: Run frontend typecheck, build and browser tests**

Run from `web/`: `npm install`, `npm run typecheck`, `npm run build`; after the lock file exists, clean installs use `npm ci`. Then run `npx playwright test web/tests/judge-flow.spec.ts` against a local FastAPI fixture.

Expected: PASS; the browser reaches the four views, starts/stops a mocked run, handles a disconnected WebSocket and shows a nonblank SUMO frame placeholder with metrics.

- [ ] **Step 6: Commit the Web console**

```bash
git add web api/static.py api/websocket.py tests/test_judge_api.py
git commit -m "feat: add judge-facing Web console"
```

---

## 阶段 6：原生启动、Docker 和发布包

### Task 18: Implement native one-click startup and diagnostics

**Files:**
- Create: `scripts/run_judge.py`
- Create: `scripts/start_judge.ps1`
- Create: `scripts/start_judge.bat`
- Create: `tests/test_judge_launcher.py`
- Modify: `docs/deployment.md`
- Modify: `README.md`

**Interfaces:**
- `scripts/run_judge.py --host 127.0.0.1 --port 8000 --open-browser --gui-mode auto` performs preflight, starts Uvicorn, and writes `output/evidence/judge-launch/launcher.json`.
- `scripts/start_judge.ps1` invokes the repository-selected Python interpreter, never assumes a global `python` path, and returns a nonzero exit code on preflight failure.
- `scripts/start_judge.bat` forwards arguments to PowerShell and preserves the exit code.

- [ ] **Step 1: Write launcher tests**

```python
def test_launcher_uses_project_interpreter_and_selected_port(monkeypatch):
    command = build_launch_command(Path(".venv-native/Scripts/python.exe"), 8765)
    assert command[0].endswith("python.exe")
    assert "8765" in command


def test_launcher_reports_port_conflict_without_hiding_error(monkeypatch):
    result = preflight_port("127.0.0.1", 8000)
    assert result.status in {"pass", "fail"}
```

- [ ] **Step 2: Implement preflight, browser opening and native GUI focus**

Locate Python and SUMO using explicit repository/environment rules, choose the first free port in a bounded list, launch Uvicorn, open the browser only after `/api/health` returns `ok`, and provide a Windows-only native GUI focus operation with a clear unsupported response elsewhere.

- [ ] **Step 3: Run launcher tests and a real quick launch**

Run: `python -m pytest tests/test_judge_launcher.py -q`; then run `powershell -ExecutionPolicy Bypass -File scripts/start_judge.ps1 --port 8765 --no-browser`, request `/api/health`, and stop it cleanly.

- [ ] **Step 4: Commit native startup**

```bash
git add scripts/run_judge.py scripts/start_judge.ps1 scripts/start_judge.bat tests/test_judge_launcher.py docs/deployment.md README.md
git commit -m "feat: add native judge launcher"
```

### Task 19: Build and verify Docker deployment

**Files:**
- Modify: `docker/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `.dockerignore`
- Modify: `docker/README.md`
- Create: `docker/Dockerfile.gui`
- Create: `tests/test_docker_release.py`

**Interfaces:**
- Default image starts the same FastAPI app in headless mode and exposes port 8000.
- `docker compose --profile gui up` adds the virtual display profile for SUMO-GUI frame capture; core headless reproduction does not require a display.
- Both images use the same `scripts/run_judge.py` entrypoint and write only to `/app/output`.

- [ ] **Step 1: Write static Docker contract tests**

```python
def test_default_docker_command_is_judge_server():
    dockerfile = Path("docker/Dockerfile").read_text()
    assert "scripts/run_judge.py" in dockerfile
    assert "EXPOSE 8000" in dockerfile


def test_dockerignore_excludes_internal_and_runtime_outputs():
    ignored = Path(".dockerignore").read_text()
    assert "output/runs" in ignored
    assert ".venv" in ignored
```

- [ ] **Step 2: Implement reproducible multi-stage build**

Install SUMO 1.27.1 and Python dependencies in the runtime image; build `web/` in a Node stage and copy only `web/dist` into the runtime. Keep a GUI profile with Xvfb dependencies separate from the default image.

- [ ] **Step 3: Build, run, and export/import the image**

Run: `docker compose build --no-cache`; `docker compose up -d`; `curl http://127.0.0.1:8000/api/health`; run a 100-step smoke request; `docker save ca-mp:latest -o output/evidence/docker/ca-mp.tar`; load into a clean Docker daemon and repeat the health and smoke checks.

Expected: PASS if each command exits 0 and the imported image returns the same API contract; otherwise record `fail` with logs.

- [ ] **Step 4: Run Docker tests and commit**

Run: `python -m pytest tests/test_docker_release.py tests/test_docker_static.py -q`

```bash
git add docker/Dockerfile docker/Dockerfile.gui docker-compose.yml .dockerignore docker/README.md tests/test_docker_release.py
git commit -m "feat: package native and Docker judge deployments"
```

---

## 阶段 7：清理、正式实验和最终验收

### Task 20: Replace the internal root README and release documentation

**Files:**
- Create: `docs/release/README.md`
- Create: `docs/release/experiment-protocol.md`
- Create: `docs/release/evidence-contract.md`
- Create: `docs/release/algorithm-extension.md`
- Create: `scripts/release/check_docs.py`
- Create: `tests/test_release_docs.py`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/deployment.md`
- Modify: `output/README.md`

**Interfaces:**
- The root README starts with judge quick start, supported algorithms, scene import, quick demo, formal experiment command, evidence location, native deployment and Docker deployment.
- `docs/release/experiment-protocol.md` contains the exact 540-run matrix, duration/warmup, seeds, metrics, safety gates and statistical decision rule.
- `docs/release/evidence-contract.md` documents `manifest.json`, `provenance.json`, `status.json`, events, metrics and summary fields with units.

- [ ] **Step 1: Generate a documentation link inventory**

Run a repository search for `docs/tasks`, role codes, `verify_route`, old algorithms, old flows and stale completion claims. Write the inventory to `output/evidence/release-cleanup/reference-inventory.json` before changing links.

- [ ] **Step 2: Rewrite public documentation**

Remove internal progress tables, team assignment navigation, old `actuated` formal claims, `1.5` matrix claims and historical “completed” statements from public README and deployment instructions. Replace them with current commands that target canonical algorithm IDs and seconds-based windows.

- [ ] **Step 3: Verify links and claims**

Write tests in `tests/test_release_docs.py`, then run `python -m pytest tests/test_release_docs.py -q` and `python scripts/release/check_docs.py --root .`; both must fail on internal role terms in public files, stale formal algorithm names, missing local links, unsupported success claims and personal absolute paths.

- [ ] **Step 4: Commit documentation boundary**

```bash
git add README.md docs/README.md docs/deployment.md docs/release scripts/release/check_docs.py tests/test_release_docs.py output/README.md output/evidence/release-cleanup/reference-inventory.json
git commit -m "docs: publish judge-facing release guidance"
```

### Task 21: Remove stale internal artifacts without touching official sources

**Files:**
- Create: `scripts/release/clean_release.py`
- Create: `tests/test_release_cleanup.py`
- Modify: `scripts/release/output_policy.py`

**Interfaces:**
- `plan_cleanup(repo_root: Path) -> CleanupPlan` returns exact paths, reason, reference status and recoverability for each removal.
- `apply_cleanup(plan: CleanupPlan, mode: Literal["quarantine", "release_copy"]) -> CleanupReport` never deletes official sources and defaults to moving generated files to a recoverable quarantine.
- `build_release_copy(repo_root: Path, destination: Path) -> ReleaseManifest` copies only allowed files and writes SHA-256 entries.

- [ ] **Step 1: Write cleanup safety tests**

```python
def test_cleanup_plan_never_targets_official_archive(repo_root):
    plan = plan_cleanup(repo_root)
    assert Path("赛题资料.7z") not in plan.targets
    assert all("data/intersection_data" not in str(path) for path in plan.targets)


def test_release_copy_excludes_internal_route_scripts(repo_root, tmp_path):
    manifest = build_release_copy(repo_root, tmp_path / "release")
    names = {entry.relative_path for entry in manifest.entries}
    assert not any("verify_route" in name for name in names)
    assert "README.md" in names
```

- [ ] **Step 2: Inventory references before quarantine**

Resolve references from public docs, tests, package files and launchers. Move old `output/evidence` data and route verification scripts only after replacement contracts and tests pass. Preserve the recoverable quarantine until final release verification completes.

- [ ] **Step 3: Build a release copy instead of mutating the worktree first**

Exclude `.git`, virtual environments, `tmp`, caches, stale runs, manual review material, internal task documents, old route scripts, user-specific files and generated developer artifacts. Include official source archive, official scene data, current source, built Web assets, launcher, Docker files, release docs and formal configuration.

- [ ] **Step 4: Run cleanup tests and commit the tooling**

Run: `python -m pytest tests/test_release_cleanup.py tests/test_output_policy.py -q`

```bash
git add scripts/release/clean_release.py scripts/release/output_policy.py tests/test_release_cleanup.py
git commit -m "chore: add recoverable final release cleanup"
```

### Task 22: Run staged real verification and freeze formal evidence

**Files:**
- Create: `output/evidence/quick-demo/README.md`
- Create: `output/evidence/formal/README.md`
- Create: `output/evidence/formal/matrix-manifest.json`
- Modify: `docs/release/experiment-protocol.md`

- [ ] **Step 1: Run the native smoke and quick demo**

Run the 100-step scene 1 smoke, the 600-second scene 1 quick demo for fixed timing and capacity-aware MaxPressure, and a safe scene switch to scene 2. Verify health, Web frame sequence, metrics, safety event stream, terminal status and no leaked SUMO PID.

- [ ] **Step 2: Run the 20-scene preflight**

Run structural scene validation and a short real SUMO run for each official scene. Record source warnings, step length, TLS IDs, movement counts, generated outputs and terminal status. Do not call this the formal matrix.

- [ ] **Step 3: Freeze parameters and execute the formal matrix**

Run `python scripts/run_pdf_matrix.py --profile formal --duration-seconds 3600 --warmup-seconds 600 --resume --output-root output/runs/formal`. Execute all 360 normal and 180 disturbance specs. For every failure, retain the failure record, diagnose it, and rerun only that run key with a new run ID until all 540 expected keys have successful valid outputs.

- [ ] **Step 4: Analyze and freeze results**

Run `python scripts/analyze_matrix.py --input output/runs/formal --output output/evidence/formal`; verify 540 unique valid outputs, safety gates, unfinished vehicles, energy fields, paired statistics, confidence intervals, worst cells and default selection. Copy no hand-edited number into a report.

- [ ] **Step 5: Commit only frozen configuration metadata**

Do not commit large generated run data unless the release manifest explicitly requires it. Commit the matrix manifest, protocol and small audit summaries; keep full run artifacts in the release evidence archive.

```bash
git add output/evidence/quick-demo/README.md output/evidence/formal/README.md output/evidence/formal/matrix-manifest.json docs/release/experiment-protocol.md
git commit -m "chore: freeze formal experiment evidence"
```

### Task 23: Verify browser, package and second-environment release

**Files:**
- Create: `scripts/release/verify_package.py`
- Create: `tests/test_release_package.py`
- Create: `output/evidence/final/README.md`

**Interfaces:**
- `verify_release_copy(release_root: Path) -> ReleaseVerification` checks manifest hashes, public entrypoints, no internal files, no stale algorithms, official source presence, Web build presence and documentation links.
- `verify_runtime(base_url: str, profile: Literal["native", "docker"]) -> RuntimeVerification` checks health, scene list, algorithm list, quick run, frame, metrics, stop and result retrieval.

- [ ] **Step 1: Create a clean release copy**

Run `python scripts/release/clean_release.py --mode release_copy --destination output/release-candidate`; do not run verification against the dirty development tree.

- [ ] **Step 2: Verify static package invariants**

Run `python -m pytest tests/test_release_package.py -q` and `python scripts/release/verify_package.py output/release-candidate`. Expected: no internal docs, old route scripts, stale formal algorithms, personal paths or missing source hashes.

- [ ] **Step 3: Run Playwright against the native release**

Start the release launcher on a free port and run `npx playwright test web/tests/judge-flow.spec.ts --project=chromium`. Capture desktop screenshots of real-time simulation, comparison, history and scene management; inspect that the SUMO frame is nonblank, labels do not overlap and disconnected/error states are visible.

- [ ] **Step 4: Run Docker and clean-directory verification**

Extract or copy the release candidate to a directory outside the repository, start native and Docker profiles, run `verify_runtime()`, and record Docker build, health, smoke, frame fallback and result evidence. A second environment is `pass` only after a real independent run.

- [ ] **Step 5: Freeze the final manifest and commit verification metadata**

Write `output/evidence/final/release-manifest.json` with package SHA-256, code commit, environment versions, test commands, browser screenshots, Docker status and every `pass`/`fail`/`not_run` result. Commit only the manifest and small verification metadata.

```bash
git add scripts/release/verify_package.py tests/test_release_package.py output/evidence/final
git commit -m "test: verify clean judge release package"
```

### Task 24: Generate later submission materials from frozen evidence

**Files:**
- Create or modify: `report/实验评估报告.md`
- Create or modify: `output/deliverables/答辩PPT.pptx`
- Create or modify: `output/deliverables/demo_video_script.md`
- Create or modify: `output/deliverables/submission-manifest.json`

- [ ] **Step 1: Generate report tables and figures only from frozen summaries**

Use `output/evidence/formal` as the only numeric input. Every table and chart stores its source run IDs, aggregation command and code commit.

- [ ] **Step 2: Produce the 5–8 minute demonstration script**

Cover real scene import, problem/perturbation, fixed timing, capacity-aware control, embedded SUMO-GUI view, live metrics, comparison and evidence-limited conclusion. Do not show internal assignments or claim a metric not present in the frozen evidence.

- [ ] **Step 3: Render and inspect PPT/video deliverables**

Use the document and presentation verification workflows, check Chinese fonts, screen capture clarity, real-time overlays, duration, audio and all local links.

- [ ] **Step 4: Add final submission manifest and commit**

```bash
git add report output/deliverables
git commit -m "docs: generate submission materials from frozen evidence"
```

---

## Spec Coverage Map

| Spec section | Implementation tasks |
|---|---|
| 1–3 文档地位、目标、边界 | 1, 2, 20, 21, 24 |
| 4–5 架构与组件职责 | 3–8, 11, 12, 15, 16 |
| 6 算法方案 | 3, 4, 9, 10, 11 |
| 7 场景与扰动 | 6, 7 |
| 8 实验设计 | 5, 14, 22 |
| 9 指标定义 | 8, 13, 14 |
| 10 Web 与 SUMO 画面 | 15–17, 23 |
| 11 API 与实时通信 | 3, 15, 16 |
| 12 证据合同 | 1, 13, 14, 22, 23 |
| 13 错误处理与恢复 | 6, 7, 11, 12, 15, 16, 18 |
| 14 测试与验收 | every task's focused tests, then 22–23 |
| 15 发布与清理 | 2, 18–21, 23 |
| 16–17 实施顺序与完成定义 | 1–24 and Global Verification Commands |

---

## Global Verification Commands

Run these after the corresponding tasks and again before declaring the goal complete:

```powershell
python -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization
python -m pytest -q -p no:cacheprovider --basetemp=output/pytest-final
python scripts/release/preflight.py --repo-root . --output output/evidence/release-baseline/environment.json
python scripts/release/check_docs.py --root .
python scripts/release/verify_package.py output/release-candidate
git diff --check
```

The goal may be marked complete only after the final manifest proves: 540 successful unique formal outputs, all safety gates, valid completed/unfinished semantics, Web and SUMO frame behavior, native launch, Docker status, clean-package verification, and frozen submission materials. If any external environment remains untested, keep its status `not_run` and keep the goal active.
