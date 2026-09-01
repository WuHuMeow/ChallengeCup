# 工作区修复进度与剩余工作交接（2026-08-31）

> 目标：全面检查项目可运行性，保留最新未提交修改（以新文件为准补齐旧文件）。
> 本文件记录已修复链路与剩余契约缺口，供后续会话继续收尾。

## 已完成（本轮）

| 模块 | 修复内容 | 验证 |
| --- | --- | --- |
| ML 训练闭环 | `ml/dataset.py`（新）、`ml/train.py` 真实训练、`ml/evaluate.py` EWMA 对比、`cloud/cloud_policy.py` 模型优先/回退、`scripts/train_ml.py` | `tests/test_ml_pipeline.py` 12 绿 + `test_ml/test_cloud` 回归 12 绿；真实数据训练完成：留出 n=25,584，GBR MAE 3,810 vs EWMA 4,885（-22%），证据 `output/evidence/ml/evaluation.json` |
| `core/run_models.py` | 加 `RunStatus.STARTING/STOPPING`、`DisturbanceSpec`（校验 end>begin、0<intensity≤1、kind 三类）、`RunRequest.duration_seconds/warmup_seconds/disturbance/steps=None`、`RunResult.algorithm`、`VariantSpec.disturbance` | `test_run_models` 5 绿 |
| `engine/artifacts.py` | `status.json` + `write_status()` + `manifest` + `write_manifest()` + `read_status()` + `CorruptStatusArtifactError` | lifecycle + formal matrix 部分验证 |
| `engine/runner.py` | `run()` 支持 `SimulationWindow`（秒优先，返回 `RunResult`、写 manifest/status.json）与 legacy int 步数（返回 list）双模式；warmup 步不记指标 | lifecycle runner 组全绿 |
| `engine/traci_bridge.py` | 进程所有权（`_owned_process`/`process_id`/连接 label）、`process_factory` 注入、失败清理只动自己的连接/进程、sumo-gui 窗口关闭请求 `_request_gui_window_close`、宽限 reap | lifecycle bridge 组 11 绿 |
| `engine/run_service.py` | 重写：`RunStateMachine` 集成（`_states`/`_done`/per-run 锁）、STOPPING 中间态、stop 返回"是否实际 INTERRUPTED"、`switch_scene`、`EvidenceWriter.finalize/seal`、`_finalize_cancelled_queued` 容错终态化 | `test_run_lifecycle.py` 29 绿 |
| `core/types.py` | `JointState.phase_movements/legal_phase_transitions`、`ControlAction.issued_at/expires_at` + `for_simulation_time()`、`_require_number()` | movements 链路可导入 |
| `engine/action_validation.py` | `validate_phase_change_timing/clearance_duration/action_window/plan_program_safety` | `test_action_validation` 13 绿 |
| `api/models.py` | `DisturbanceSpecModel`、`MovementStateModel`、`PhaseMovementStateModel`（StrictInt 拒 bool） | movements/disturbances 收集通过 |
| `algorithms/ca_max_pressure.py` | `LegacyDecisionPlan`/`_LegacyPlanningProfile`/`plan_decision/_validate_legacy_plan/commit_plan`，`step()` 重构为 plan+commit（行为等价） | `classic_max_pressure` 收集+多数通过 |
| `cloud/cloud_policy.py` | `CloudPolicyPlan`/`plan()/validate_plan()/commit()`、`joint_state_fingerprint`、`configured_prediction_weight` | capacity 链路可导入 |

修复前基线：**361 通过 / 79 失败 / 12 个测试模块 ImportError**。

## 剩余缺口（按优先级）

### 1. `core/types.py` 缺 `MetricSummary` / `SafetyEvent`（阻塞面最大）

- 需要：`MetricSummary`（含 `from_raw_outputs(run_dir, warmup_seconds)` 工厂，解析
  tripinfo.xml/stats.xml/queues.xml 得精确指标）、`SafetyEvent`（碰撞/闯红灯事件）。
- 规格文件：`tests/test_evidence_contract.py`（~870 行，全部契约在此）。
- 消费方：`experiments/evidence.py`（EvidenceReader）、`experiments/matrix.py`。
- 预计工作量：半天。

### 2. `experiments/matrix.py` + CLI（58 failed）

- 依赖上面 `MetricSummary`；另有 `scripts/run_pdf_matrix.py` CLI 契约
  （smoke/quick/formal 三档、种子/窗口覆盖拒绝规则，见
  `tests/test_formal_matrix.py` 的 CLI 测试组）。
- 核心矩阵逻辑（FormalMatrix.normal=360/disturbance=180、run_key 规范化）
  已大体在，失败多链自 evidence 缺失。

### 3. `scenes/disturbances.py`（46 failed）

- `write_disturbance` 已实现；失败集中在 SUMO 实跑类测试（需要本机 SUMO 1.27.1）
  与 `validate_variant` 细节。先确认 `SUMO_HOME` 环境，再按
  `tests/test_disturbances.py` 逐个收敛。

### 4. `engine/safety_executor.py`（40 failed）

- 678 行实现已在；失败集中在 `SafetyExecutor` 与 CA-MP 的 clearance 委派
  （`tests/test_capacity_aware_max_pressure.py` 的 M3/M4 组）以及
  `validate_action_window` 集成。与 capacity 侧 `audit_record` 的
  action_results 联动需要对齐。

### 5. 零散

- `test_classic_max_pressure` 5、`test_run_service` 4、`test_frame_publisher` 4
  （api/websocket 或 frame_sink 契约）、`test_resilience` 3、其余各 1-2。
- 收集错误：`test_evidence_contract`、`test_safety_metrics`、`test_judge_api`、
  `test_docker_release`（多为 MetricSummary/SafetyEvent 链）。

## 追加修复记录（2026-09-01）

- `algorithms/classic_max_pressure.py`：60s 动作窗口（expires_at）、manifest 契约 → **6/6 绿**
- `core/types.py`：`JointState.queues/flows` 默认值、`ControlAction.issued_at/expires_at` + `for_simulation_time(..., expires_at)`
- `cloud/cloud_policy.py`：预测输出改为 horizon 内车辆数（veh/h×horizon/3600），EWMA 历史保存在 `_prev_hourly_flow`（veh/h 域）；`predict()` 重写为 plan→commit 单事务；`_runtime_revision`（reset 后拒绝旧 plan）；注入策略不再被 falsy 替换
- `algorithms/capacity_aware_max_pressure.py`：动作带 60s 窗口（min_green 执行委派安全执行器）、legacy plan 挂载云端快照
- `tests/conftest.py`（新增）：autouse 隔离默认 `ml/model.pkl` 加载（单元测试不再被真模型干扰）
- capacity 套件 31 错误/失败 → **45/50 通过**

## 2026-09-01 四次收尾（MetricSummary 落地 + matrix 链路打通）

- **test_evidence_contract 56/56 全绿**：`core/types.py` 新增 `MetricSummary`
  （`from_raw_outputs` 严格解析 tripinfo/metrics/events，warmup 过滤、未完成
  分离、畸形 depart/arrival 抛错）与 `SafetyEvent`；`engine/events.py` 新增
  `EVENT_FIELDS`（含 accepted/action_value 共 12 列）；`experiments/summary.py`
  重写为 `metric_summary_payload`（canonical 七段 schema + legacy 别名键）+
  原子 `write_run_summary`；`engine/artifacts.py` 恢复 8 件套 required outputs、
  `collisions/hashes/provenance` 属性与 `evidence_required_output_names()`；
  `EvidenceWriter.seal()` 以 metadata 终态收敛 status.json；`begin()` 绑定
  run_id/algorithm 身份；`finalize` 拒绝 STOPPED 并维护 run_manifest.json；
  `scripts.run_pdf_matrix.is_complete` 要求严格证据（manifest+hashes）。
- **matrix 链路打通**：`SceneRegistry.list_scenes(formal_only=)`、
  `core.types.SceneMeta.scene_id/lane_ids` 别名、`config/default.yaml` 冻结
  扰动默认（construction 1.0 / event_demand 1.25 / vehicle_failure 1.0，
  600–1200s）、`DisturbanceSpec.intensity` 按 kind 分离校验
  （event_demand 是需求倍率允许 (0,2]，其余 (0,1]）。

### 下一会话最高优先级：variant.py 扰动融合重写（~46 个 disturbances 失败）

规格在 `tests/test_disturbances.py`（60–135、379–560 行）：
- `generate_bundle(meta, flow, spec, out)` 的 `spec` 接受 **None / VariantSpec /
  DisturbanceSpec**；None = 纯流量缩放。
- 新 `VariantBundle` 字段：`flow_file`、`route_file`、`sumo_cfg`、
  `additional_files`、`manifest["parent_sha256"]`（源 flow 字节哈希）。
- flow→route 转换：runtime config 只挂派生 route（不挂中间 flow 与原 rou），
  TraCI `-c` 用 bundle.sumo_cfg；SUMO 实跑须 returncode 0。
- 缩放语义：flow number×倍率、id 加 `_x{multiplier:g}` 后缀、vType 同步重命名；
  源文件字节不变。
- 扰动 spec 时经 `scenes/disturbances.write_disturbance(spec, out, network_file=)`
  追加 additional，`validate_variant(bundle)` 校验 additional 引用完整性。

## 2026-09-01 三次收尾（run_service 全绿 + 最终基线）

- **run_service + lifecycle 34 全绿**：恢复被删的 `_result_from_artifacts`；
  legacy runner（返回 list 的替身）从 run_metadata 读终态；状态机允许
  STOPPING→STOPPED；stop() 生效语义 = INTERRUPTED 或 STOPPED。
- `FixedTimeAlgorithm` 冻结方案接线完成（test_fixed_time_plan 7/7）。
- **最终基线：543 通过 / 114 失败 / 4 收集错误**（起点 361/79/12）。
- 赛道 B 全套件（capacity/classic/ML/action_validation/lifecycle/run_models/
  run_service/safety_executor/fixed_time/tuning/experiments/api/variants）
  **全绿**。
- 剩余 114 失败 + 4 收集错误全部指向一个缺失契约：`core/types.py` 的
  `MetricSummary`/`SafetyEvent`（规格 = tests/test_evidence_contract.py ~870 行，
  `MetricSummary.from_raw_outputs(run_dir, warmup_seconds)` 解析
  tripinfo.xml/stats.xml/queues.xml）。它阻塞 experiments/matrix.py、
  evidence 链与 formal_matrix CLI 测试。disturbances 的失败多为 SUMO
  实跑类（本机 SUMO 1.27.1 已在位，可直接迭代）。

## 2026-09-01 二次收尾（safety_executor 与 fixed_time 清零）

- **safety_executor 40/40 全绿**：`engine/action_validation.py` 实现严格启动程序校验
  `validate_startup_program_safety(program, *, min_green/yellow/all_red)`——逐信号
  黄灯清空（missing/short）、全红清空（missing/short）、min_green 服务绿下限、
  direct green-to-green、无关信号黄灯；`validate_control_action` 对 dict 型
  set_program 值保留结构（不再强转字符串触发启动守卫误拒）。
- **fixed_time_plan 7/7 全绿**：`FixedTimeAlgorithm` 升级——init 解析冻结方案
  （`FixedTimePlanResolver`，失败回退网络程序并告警），step 0 发一次
  `plan_derived` set_program（60s 窗口），`manifest["timing_plan"]` 暴露
  source_kind/path/sha256/program_id 四元组。
- **可运行性验证**：SUMO 1.27.1 在位、traci OK、`api.server` 可导入、
  `scripts/run_pdf_matrix.py --help` 正常；`experiments.matrix` 仍被
  `MetricSummary` 缺失阻塞（见下）。
- 全项目基线：**539 通过 / 118 失败 / 4 收集错误**。

## 2026-09-01 收尾进展

- **capacity 50/50 全绿**（窄路密网适配完成）：prediction=None 安全化、tie 的
  equal_score_* reason 对齐、`_LegacyPlanningProfile.delegation_mode`（min_green/
  clearance 等待全部委派安全执行器）、`cloud_plan_post_reset` 拒绝。
- `core/types.py`：`ActionResult.reason_code` 字段；`engine/safety_executor.py`
  解包修复；`engine/mock_bridge.py` 增加 `_apply_actions` 私有钩子。
- 全项目基线：**525 通过 / 132 失败 / 4 收集错误**；赛道 B 核心套件
  （capacity+classic+ML+action_validation+lifecycle）**全绿**。

### 已清零：test_safety_executor 启动程序安全校验（2026-09-01 完成）

- 双 reason_code 语义并存：非启动时刻切换 = `unsafe_program_switch`（已恢复）；
  启动程序安全 = `unsafe_startup_program`（detail 需含逐相位黄灯清空校验：
  "yellow clearance=2.9 requires 3"、"signal_index=0"、"missing yellow clearance"、
  "min_green=10"）。建议扩展 `validate_startup_program_safety`（action_validation）
  输出这些 detail，executor 在 set_program 分支调用它而非通用开关判断。
- 另 2 处 `False is True` 待查（疑似同一分支的 accepted 语义）。

## 原 5 个 capacity 失败（已全部清零）

1-4. `test_legacy_phase_states_audit_*` / `test_m3_legacy_disables_prediction_*` / `test_legacy_audit_delegates_clearance_*`：
   `NoneType.predicted_flows` —— legacy（phase_states-only）路径的 audit/step 期望云端快照在
   `_DecisionSnapshot` 可达；挂载 `cloud_plan=legacy.cloud_plan` 后仍 3-4 处 None，
   需读测试 269-360、622-690 行精确定位（疑似 audit_record 或 step 的重规划路径丢快照）。
5. `test_capacity_cached_plan_rejects_an_injected_policy_reset`（Regex/DID NOT RAISE）：
   注入 policy 的 reset 后缓存 plan 必须抛 RuntimeError——需要 capacity 的
   plan_decision/validate 在 `cloud_policy._runtime_revision` 变化时 fail-closed。

## 复验命令

```bash
python -m pytest tests/ -q --continue-on-collection-errors --tb=no
python -m pytest tests/test_run_lifecycle.py tests/test_action_validation.py tests/test_ml_pipeline.py tests/test_ml.py tests/test_cloud.py tests/test_run_models.py -q
python scripts/train_ml.py   # 重生成 ML 证据
```
