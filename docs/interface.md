# 接口与运行契约

本文是功能一、功能二和功能三赛道 B 的活跃接口说明。代码契约以
`core/run_models.py`、`core/types.py`、`engine/run_service.py` 和 `api/server.py`
为准。

## 1. 统一运行链路

```text
RunRequest
  -> RunService（单 worker，保护全局 TraCI 客户端）
  -> SceneRegistry
  -> VariantGenerator.generate_bundle()
  -> VariantBundle
  -> SimulationRunner
  -> TraCIBridge / SUMO
  -> RunResult + summary.json
```

`RunService.submit()` 用于 REST API 异步排队，`run_sync()` 用于 CLI、矩阵和验收脚本。
两者走同一执行路径。`RunService.max_workers == 1`，避免多个线程并发使用全局 TraCI
客户端。

### RunRequest

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `intersection_id` | `str` | 必填 | 路口 `1..20` |
| `algorithm` | `str` | 必填 | `fixed_time` / `actuated` / `ca_maxpressure` |
| `steps` | `int` | `36000` | 仿真步数，必须大于 0 |
| `flow_multiplier` | `float` | `1.0` | `1.0` 原始流量，`1.5` 压力流量 |
| `seed` | `int` | `42` | 非负 SUMO 随机种子 |
| `output_root` | `Path?` | 服务默认值 | 运行产物根目录 |
| `edge_delay_steps` | `int` | `0` | 边缘通道固定延迟 |
| `edge_directions` | `tuple[str, ...]` | 空 | 边缘通道方向过滤 |
| `variant` | `VariantSpec` | 空变体 | 车型、信号时长、封道参数 |
| `algorithm_params` | `dict[str, float]` | 空 | 仅 CA-MP 可用 |

CA-MP 参数只允许：

- `overflow_occupancy_threshold`
- `prediction_weight`
- `base_green`

### VariantBundle

`VariantGenerator.generate_bundle()` 在当前运行目录的 `variants/` 内生成流量、信号或封道
附加文件，并返回：

- `additional_files`: 传给 SUMO 的附加文件列表；
- `manifest`: 输入、参数、哈希与生成文件来源。

原始 `data/intersection_data/` 是只读输入，不允许在原目录原地修改。

### SceneManifest

`SceneRegistry.list_scenes(formal_only=False)` 返回不可变的
`tuple[SceneManifest, ...]`，提供正式场景的只读审计元数据；运行时调用继续使用
`get_scene()` 和 `get_meta()`，其 `SceneMeta` 接口不变。每个 `SceneManifest` 包含：

- `scene_id`、仓库相对的 `source_files` 及其流式计算的 `sha256`；
- `step_length`（未在 `.sumocfg` 显式配置时为 SUMO 默认 `1.0`）、`tls_ids`、
  `lane_ids` 和受控有效 lane-to-lane `movement_count`；
- `validation_status`（`pass` 或 `fail`）与不被吞没的 `warnings`。

`SceneValidator.validate(scene_root)` 使用 XML 和 Excel 的结构化解析预检 net、flow、
route、turn、sumocfg 和配时输入。不存在合法受控 movement、无效步长、断开的路线或
引用不存在的车道/边/信号程序时返回 `fail`。官方源已知的 `.sumocfg` 未直接引用
flow/turn 输入会保留为 `source warning`，不作为没有告警的成功声明。

`SceneImporter.import_scene(source_root, destination_root)` 先完成验证，只有 `pass` 时才
将完整场景树复制为 `<destination_root>/<scene_id>/`；失败时抛出
`SceneValidationError`，不会创建部分包，也绝不写回 `source_root`。

## 2. 运行状态与产物

`RunArtifacts.required_output_names()` is the single completed-run checker
contract. A `completed` run must retain non-empty `metrics.csv`,
`simulation_log.csv`, `events.csv`, `tripinfo.xml`, `stats.xml`, `traj.xml`,
and `summary.json`. The three XML files are raw SUMO provenance outputs;
`queues.xml` remains optional when the source configuration enables it.

`variants/` contains generated per-run inputs and is not an original-data
directory. No intermediate file is written under `data/intersection_data/`
or `engine/configs/`. `run_metadata.json` records the terminal lifecycle
state and the actual existing names in `generated_files`; optional or cleaned
files are not claimed there. Formal acceptance evidence is separate under
`output/evidence/` and is never a run artifact.

每次运行生成随机、碰撞安全的 `run_id`，目录固定为：

```text
<root>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/
```

目录内文件：

| 文件 | 内容 |
|---|---|
| `metrics.csv` | 周期队列与实时状态快照 |
| `simulation_log.csv` | 每步相位、队列与压力 |
| `events.csv` | 生命周期、控制动作、接受/拒绝结果 |
| `tripinfo.xml` | SUMO 每车精确行程数据 |
| `stats.xml` | SUMO 全网 summary |
| `traj.xml` | SUMO FCD 轨迹 |
| `queues.xml` | 可选 SUMO 队列输出 |
| `summary.json` | 精确运行级指标和来源文件 |
| `run_metadata.json` | 终态、原因、版本、时间和生成文件 |
| `variants/` | 本次运行的参数化场景文件及 manifest |

`RunStatus` 取值：

```text
queued, starting, running, stopping, completed, interrupted,
ended_early, disconnected, failed, stopped
```

`starting` 和 `stopping` 是运行中的生命周期状态。用户停止运行的规范终态是
`interrupted`；`stopped` 仅用于读取旧产物的兼容，不会作为新的停止结果写入。
只有 `completed` 表示正常完成。验收层另使用 `pass`、`fail`、`not_run`，其中
`not_run` 表示环境或证据未执行，不能解释成通过。

Runner 使用 SUMO 仿真时钟判断配置终点：到达 `.sumocfg` 的 `<end>` 后自然耗尽记为
`completed`；在配置终点前无活动/预期车辆才记为 `ended_early`。这样可兼容 1.0s 与
0.1s 两类步长，而不会把正常的一小时仿真误报为提前结束。

## 3. 算法契约

所有算法实现 `algorithms/base.py::BaseControlAlgorithm`：

```python
class BaseControlAlgorithm(ABC):
    def init(self, scene: Scene) -> None: ...
    def step(self, state: JointState) -> list[ControlAction]: ...
    def reset(self) -> None: ...

    @property
    def name(self) -> str: ...
```

- `step()` 只做决策，不启动 SUMO、不写文件、不直接调用 TraCI。
- 返回 `[]` 表示本步不干预。
- 控制动作统一由 `SafetyExecutor.apply()` 验证和执行，并逐项返回与算法原始请求关联的
  `ActionResult`；算法和 Runner 不直接调用 bridge 的私有信号写入端。

### JointState

| 字段 | 类型 | 说明 |
|---|---|---|
| `step` | `int` | 仿真步编号 |
| `timestamp` | `float` | SUMO 时间（秒） |
| `tls_id` | `str` | 信号灯 ID |
| `current_phase` | `int` | 当前合法相位索引 |
| `current_phase_name` | `str` | 当前相位名 |
| `elapsed_phase_time` | `float` | 当前相位持续时间 |
| `queues` | `list[QueueState]` | 进口道排队状态 |
| `flows` | `dict[str, float]` | 方向或车道流量 |
| `detector_values` | `dict[str, float]` | 检测器扩展值 |
| `vehicles` | `list[VehicleState]` | 采样车辆，硬上限 500 |
| `arrival_history` | `list[int]` | 最近 300 步到达历史 |
| `phase_states` | `list[PhaseTrafficState]` | 合法相位的上下游交通状态 |
| `phase_movements` | `tuple[PhaseMovementState, ...]` | 唯一用于 movement pressure 的相位-转向状态；默认空元组 |

### QueueState

`QueueState` 包含 `direction`、`queue_length`、`waiting_time`、
`vehicle_count` 和 `capacity`。容量按车道长度除以 7.5m 估算；未知容量为 `0.0`。

### PhaseTrafficState

| 字段 | 说明 |
|---|---|
| `phase_index` | SUMO 合法整数相位索引 |
| `signal_state` | 原始相位灯色字符串 |
| `nominal_duration` | 原程序相位时长 |
| `incoming_lanes` / `outgoing_lanes` | 本相位服务的上下游车道 |
| `incoming_queue` / `outgoing_queue` | 上下游排队 |
| `incoming_capacity` / `outgoing_capacity` | 上下游容量 |
| `outgoing_occupancy` | 下游占用率，范围 `0..1` |

### PhaseMovementState 与 MovementState

`JointState.phase_movements` 是 movement pressure 的唯一算法输入；`queues` 保留用于兼容和展示。
每个 `PhaseMovementState` 对应一个合法相位，包含 `phase_index`、`signal_state`、
`nominal_duration`（仿真秒）及其 `movements`。每个 `MovementState` 以不可变的
`MovementKey(incoming_lane, outgoing_lane)` 标识，包含：

| 字段 | 说明 |
|---|---|
| `queue_vehicles` / `downstream_queue_vehicles` | 上游和下游排队，单位为车辆 |
| `incoming_capacity` / `downstream_capacity` | 上游和下游容量，单位为车辆，必须大于 `0` |
| `downstream_occupancy` | 下游占用率，范围 `0..1` |
| `saturation_rate` | 饱和流率，单位为车辆/仿真秒 |
| `turn_ratio` | 转向比例 |

### ControlAction 与 ActionResult

`ControlAction` 字段为 `tls_id`、`action_type`、`value`、`reason`，以及可选的
`issued_at`、`expires_at` 仿真秒有效期。两个有效期字段同时省略时保持历史调用兼容；
生产算法按 `state.timestamp` 签发动作，并使用 60 仿真秒有效期。执行时刻满足
`current >= expires_at` 的动作以 `stale_action` 拒绝。

| `action_type` | `value` | TraCI 调用 |
|---|---|---|
| `set_phase` | 合法整数相位 | `trafficlight.setPhase` |
| `set_phase_duration` | 秒数 | `trafficlight.setPhaseDuration` |
| `set_program` | 含 `program_id` 和相位定义的固定配时程序 | `trafficlight.setProgramLogic` + `trafficlight.setProgram` |

`SafetyExecutor.apply(actions, state, bridge) -> tuple[ActionResult, ...]` 是唯一的信号
动作写入入口。执行器验证动作有效期和仿真秒边界、从算法当前配置读取最小绿灯、拒绝
会缩短当前或新进入绿灯的时长，并只沿可达黄灯/全红路径切换绿灯，再调用 bridge 的
私有低层写入端。`set_program` 只接受通过结构校验且在 `step`、仿真时间、当前相位
已持续时间均为零时安装的固定配时定义；定义中的每个服务绿灯和循环转换还必须独立
满足当前最小绿灯、配置黄灯和纯全红清空时长。每个结果仍包含算法原始动作、
`accepted`、`detail` 和结构化 `reason_code`；拒绝动作会写入事件日志，调用方不需要
从 warning 文本猜测结果。只有非法拓扑边才生成 `illegal_transition` 安全事件，最小
绿灯、黄灯和全红计时拒绝仅保留为结构化 `action_rejected`。

`events.csv` keeps the legacy `step`, `type`, and `detail` columns and adds
`run_id`, `intersection_id`, `algorithm`, `status`, `reason`, `accepted`,
and action fields. Lifecycle events use `status`/`reason`; action rows use
`accepted` plus the validation detail. This makes `run_start`,
`action_applied`, `action_rejected`, `channel_wait`, `disconnected`, and
`terminal` auditable without parsing warning text.

## 4. CA-MP 行为

`CAMaxPressureAlgorithm` 只从 `JointState.phase_states` 中选择合法整数相位：

1. 上游排队和下游排队分别按容量归一化；
2. 将 `CloudPolicy.predict()` 的预测到达量按 `prediction_weight` 加入压力；
3. 当 `outgoing_occupancy >= overflow_occupancy_threshold` 时阻断该相位，避免向已饱和下游继续放行；
4. 在 `max_green` 到期时选择可行替代相位，并把最终绿灯请求交给共享安全执行器；
5. `SafetyExecutor` 按仿真秒执行 `min_green`，并插入真实 SUMO 黄灯/全红相位；
6. 绿灯时长按相对压力动态计算，并限制在 `min_green..max_green`；
7. `reset()` 清理控制器配置和云策略状态。

校准使用 `experiments/tuning.py`：

- 校准交叉口：`1, 11, 16`；
- 校准种子：`42`；
- 严格留出种子：`123, 456`；
- 赢家写入 `selected_params.json`，留出评估写入 `holdout_summary.json`。

## 5. 精确指标与 null 语义

`experiments/summary.py` 从完成后的 SUMO 文件生成 `summary.json`：

| 指标 | 来源 |
|---|---|
| `avg_travel_time` | `tripinfo.duration` |
| `avg_delay` | `tripinfo.timeLoss` |
| `throughput` | 完成的 `tripinfo` 条目数 |
| `total_stops` | `tripinfo.waitingCount` |
| `fuel_consumption` | `tripinfo` 的 `fuel_abs` / emissions |
| `avg_queue_length` / `max_queue_length` | `metrics.csv` |

如果 SUMO 没有提供完整字段，精确指标为 JSON `null`。禁止用 `0` 代替缺失值，因为
`0` 会被误解为真实的零延误、零停车或零油耗。

`core.types.SimulationMetrics` 中 `avg_travel_time`、`total_stops`、
`fuel_consumption` 因此是可空值。

## 6. REST API

启动：

```powershell
uvicorn api.server:app --host 127.0.0.1 --port 8000
```

规范端点：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 服务状态和 worker 数 |
| GET | `/api/scenes` | 20 路口列表 |
| POST | `/api/runs` | 排队一个运行，返回 `run_id` |
| GET | `/api/runs/{run_id}` | 查询运行状态 |
| GET | `/api/runs/{run_id}/metrics` | 查询完成后的精确指标 |
| POST | `/api/runs/{run_id}/stop` | 请求停止运行 |
| POST | `/api/cloud/predict` | 云端预测契约 |
| POST | `/api/edge/control` | 边缘 CA-MP 控制契约 |

静态交付：

- `docs/api/openapi.json`
- `docs/api/postman_collection.json`

旧的 `/health`、`/scenes`、`/run`、`/status` 和 `/api/simulation/*` 仅保留为
deprecated 兼容端点。

## 7. CLI、矩阵与离线包

单次运行：

```powershell
python -m experiments.runner --intersection 1 --algorithm ca_maxpressure `
  --flow-multiplier 1.25 --seed 42 --steps 7200 `
  --output-dir output/runs
```

PDF 矩阵：

```powershell
python scripts/run_pdf_matrix.py --profile quick `
  --output-root output/runs/matrix-quick
python scripts/run_pdf_matrix.py --profile formal --duration-seconds 3600 `
  --output-root output/runs/matrix-full
```

完整矩阵为 `20 路口 x 3 算法 x 2 流量 x 3 种子 = 360` 次。脚本使用
`matrix_state.json` 和逐运行完整性检查恢复中断，不重复已完成运行。需要校准时使用
`--tune`，或确保矩阵根目录已有对应 `selected_params.json`。

离线包：

```powershell
python scripts/package_offline.py --output-dir output/offline
```

离线 manifest 包含源码压缩包、依赖清单、SHA-256，以及 Docker 和第二机器两条独立证据轴。
Docker 不可用、镜像不存在或未提供第二机器证据时，对应状态为 `not_run`。

## 8. 验收边界

```powershell
python scripts/verify_ia_ib.py --quick --output-root output/runs/ia-ib-quick
python scripts/verify_ia_ib.py --output-root output/runs/ia-ib-full
```

最终报告必须区分：

1. repository implementation；
2. automated verification；
3. local SUMO verification；
4. Docker live verification；
5. second-machine reproduction。

主办方原始 J2 信号方案产生的 unsafe/unused-state warning 必须保留为源数据警告。
PPT、Word 实验报告和演示视频属于独立交付，不包含在 IA/IB 仓库实现完成度内。
上述输出根目录均由命令运行时创建；历史大型矩阵产物和压缩包已删除。Dockerfile、Compose
配置和静态契约已检查，但 Docker live 与第二机器复现没有真实证据，均保持 `not_run`。
