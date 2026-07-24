# 接口文档

> 本文件描述 `core/types.py` 和 `algorithms/base.py` 中所有共享数据类型的字段含义与使用方式。
> 全员开发必须基于本文档中的契约，不得自行修改 `core/types.py`。
> 如有疑问找 TL，不要猜。

---

## 目录

- [算法标准接口（BaseControlAlgorithm）](#算法标准接口)
- [JointState（算法输入）](#jointstate)
- [QueueState（进口道排队）](#queuestate)
- [VehicleState（车辆快照）](#vehiclestate)
- [ControlAction（算法输出）](#controlaction)
- [SceneMeta / Scene（场景）](#scene)
- [PredictionResult（云端预测）](#predictionresult)
- [TimingPlan / PhaseInfo（配时方案）](#timingplan)
- [SimulationMetrics（仿真指标）](#simulationmetrics)
- [TrafficLevel（流量等级）](#trafficlevel)
- [TraCIBridge（SUMO 桥接器）](#tracibridge)
- [EdgeChannel（V2X 边缘通道）](#edgechannel)
- [CloudPolicy.dispatch_params（云端参数下发）](#dispatchparams)
- [SimulationRunner（单次仿真运行器）](#simulationrunner)
- [experiments CLI（单次实验入口）](#experiments-cli)
- [输出文件表](#输出文件表)
- [使用示例](#使用示例)

---

<a id="算法标准接口"></a>

## 算法标准接口（BaseControlAlgorithm）

**文件**：`algorithms/base.py`

所有交通管控算法必须继承此抽象基类。`engine/runner.py` 和 `experiments/runner.py` 通过此接口统一调度算法。

```python
class BaseControlAlgorithm(ABC):
    def init(self, scene: Scene) -> None: ...
    def step(self, state: JointState) -> List[ControlAction]: ...
    def reset(self) -> None: ...
    @property
    def name(self) -> str: ...
```

| 方法 | 调用时机 | 说明 |
|------|----------|------|
| `init(scene)` | 仿真启动前调用**一次** | 绑定场景信息（路口 ID、信号灯 ID、相位结构、车道容量等）。算法应在此解析 `scene.meta.sumo_net` 获取路网拓扑。 |
| `step(state)` | **每个仿真步**调用一次 | 接收当前联合状态，返回控制动作列表。返回空列表 `[]` 表示本步不干预 SUMO（如固定配时基线）。 |
| `reset()` | 重复运行同一场景或切换场景时调用 | 清空算法内部状态，确保下次运行不受上次影响。 |
| `name` | 实验报告和日志中使用 | 返回算法标识字符串，如 `"fixed_time"`、`"ca_maxpressure"`。 |

**关键约束**：
- `step()` 必须是纯决策——不要在里面启动 SUMO 或写文件。
- 返回的 `ControlAction` 由 `engine/traci_bridge.py` 负责写入 SUMO，算法不直接调用 TraCI。
- 云端预测通过构造函数注入 `CloudPolicy` 对象，在 `step()` 内调用 `cloud_policy.predict(state)` 获取。

---

<a id="jointstate"></a>

## JointState（算法输入）

**文件**：`core/types.py`

每个仿真步由 `engine/traci_bridge.py` 从 SUMO 读取并组装，作为 `algorithm.step()` 的唯一输入。

| 字段 | 类型 | 含义 | 示例 |
|------|------|------|------|
| `step` | `int` | 当前仿真步编号（从 0 开始） | `120` |
| `timestamp` | `float` | 仿真时间（秒），= step × step_length | `120.0` |
| `tls_id` | `str` | 信号灯 ID（SUMO 中的 traffic light ID） | `"J1"` |
| `current_phase` | `int` | 当前相位索引（对应 net.xml 中 tlLogic 的 phase 序号） | `2` |
| `current_phase_name` | `str` | 当前相位名称（如有） | `"NS_green"` |
| `elapsed_phase_time` | `float` | 当前相位已持续时间（秒） | `15.0` |
| `queues` | `List[QueueState]` | 各进口道排队状态列表 | 见下方 |
| `flows` | `Dict[str, float]` | 各方向当前流量（辆/小时） | `{"north": 450.0, "south": 380.0}` |
| `detector_values` | `Dict[str, float]` | 检测器原始值（预留扩展，当前可为空） | `{}` |
| `vehicles` | `List[VehicleState]` | 采样后的车辆快照（默认空；高流量下按 `vehicle_sample_rate` 采样，硬上限 500 辆，优先保留进口道车辆） | 见 VehicleState |
| `arrival_history` | `List[int]` | 最近 300 步每步 departed 车辆数（滚动窗口） | `[0, 1, 2, ...]` |

**使用注意**：
- `queues` 列表长度 = 路口进口道数量（4~5 个方向）。
- `flows` 的 key 是方向字符串（`"north"`, `"south"`, `"east"`, `"west"`, 或更细粒度如 `"north_left"`）。
- 步长为 0.1s 的路口（11-13、15-20），`step` 每 10 步 = 1 秒。算法决策频率由算法自行控制。

---

<a id="queuestate"></a>

## QueueState（进口道排队）

| 字段 | 类型 | 含义 | 示例 |
|------|------|------|------|
| `direction` | `str` | 进口道方向 | `"north"` |
| `queue_length` | `float` | 排队长度（米）或排队车辆数（取决于采集方式） | `45.0` |
| `waiting_time` | `float` | 该方向车辆平均等待时间（秒） | `32.5` |
| `vehicle_count` | `int` | 该进口道当前车辆总数 | `6` |
| `capacity` | `float` | 车道容量（辆），= 车道长度 / 7.5m；默认 `0.0` 表示未知 | `20.0` |

**CA-MP 用法**：容量归一化压力 = `queue_length / capacity`。capacity 由 `TraCIBridge.get_lane_capacity()` 实时计算（`traci.lane.getLength / 7.5`，5m 车长 + 2.5m 间距）。

---

<a id="vehiclestate"></a>

## VehicleState（车辆快照）

**文件**：`core/types.py`

单辆车采样快照，组成 `JointState.vehicles`。采集逻辑见 `TraCIBridge._collect_vehicles`。

| 字段 | 类型 | 含义 | 示例 |
|------|------|------|------|
| `vehicle_id` | `str` | 车辆 ID | `"flow_16.12"` |
| `lane_id` | `str` | 所在车道 ID | `"E0_1"` |
| `speed` | `float` | 当前速度（m/s） | `8.3` |

---

<a id="controlaction"></a>

## ControlAction（算法输出）

**文件**：`core/types.py`

算法 `step()` 的返回值。由 `engine/traci_bridge.py` 解析并写入 SUMO。

| 字段 | 类型 | 含义 | 示例 |
|------|------|------|------|
| `tls_id` | `str` | 目标信号灯 ID（必须与 JointState.tls_id 一致） | `"J1"` |
| `action_type` | `str` | 动作类型，见下表 | `"set_phase"` |
| `value` | `Any` | 动作参数，含义取决于 action_type | `3` |
| `reason` | `str` | 决策原因（用于日志和报告，可选） | `"溢出门控触发"` |

**action_type 取值**：

| action_type | value 含义 | TraCI 对应调用 |
|-------------|-----------|----------------|
| `"set_phase"` | 相位索引（int） | `traci.trafficlight.setPhase(tls_id, value)` |
| `"set_phase_duration"` | 绿灯时长（float，秒） | `traci.trafficlight.setPhaseDuration(tls_id, value)` |
| `"set_program"` | 程序 ID（str） | `traci.trafficlight.setProgram(tls_id, value)` |

**约束**：
- 每步可以返回多个 ControlAction（如先 set_phase 再 set_phase_duration），按列表顺序执行。
- 返回空列表 `[]` = 本步不干预，SUMO 按默认程序运行。
- 不要返回矛盾的指令（如同时 set_phase 到两个不同相位）。

---

<a id="scene"></a>

## SceneMeta / Scene（场景）

### SceneMeta

描述一个 SUMO 工程的所有输入文件路径。由 `scenes/registry.py` 自动发现并构建。

| 字段 | 类型 | 含义 | 示例 |
|------|------|------|------|
| `intersection_id` | `str` | 路口编号（1~20） | `"16"` |
| `name` | `str` | 路口名称 | `"demo_16"` |
| `sumo_net` | `Path` | 路网文件路径 | `data/intersection_data/16/sumo工程/demo_16.net.xml` |
| `sumo_rou` | `Path` | 路由文件路径 | `.../demo_16.rou.xml` |
| `sumo_flow` | `Path` | 流量文件路径 | `.../demo_16.flow.xml` |
| `sumo_turn` | `Path` | 转向文件路径 | `.../demo_16.turn.xml` |
| `sumo_cfg` | `Path` | SUMO 配置文件路径 | `.../demo_16.sumocfg` |
| `timing_xlsx` | `Path` | 配时方案 Excel 路径 | `.../demo_16流量和交叉口配时方案.xlsx` |
| `map_png` | `Path?` | 高精地图图片（可选） | `.../demo_16.png` |
| `description` | `str` | 路口描述（可选） | `"5进口道，24m短边"` |

### Scene

运行时场景对象，传递给 `algorithm.init(scene)`。

| 字段 | 类型 | 含义 |
|------|------|------|
| `meta` | `SceneMeta` | 上述元数据 |
| `config` | `Dict[str, Any]` | 附加运行时配置（如流量倍率、随机种子等） |

---

<a id="predictionresult"></a>

## PredictionResult（云端预测）

**文件**：`core/types.py`

由 `cloud/cloud_policy.py` 的 `CloudPolicy.predict(state)` 返回。

| 字段 | 类型 | 含义 | 示例 |
|------|------|------|------|
| `horizon_steps` | `int` | 预测时域（仿真步数） | `300` |
| `horizon_seconds` | `float` | 预测时域（秒） | `300.0` |
| `predicted_flows` | `Dict[str, float]` | 各方向预测流量（辆/小时） | `{"north": 520.0, "east": 310.0}` |

**使用方式**（在 CA-MP 的 `step()` 中）：
```python
pred = self.cloud_policy.predict(state)
# 用 pred.predicted_flows 修正压力计算
# 例如：预测流量高的方向预分配更多绿灯时间
```

**兜底机制**：模型未就绪时，`predicted_flows` = 当前 `state.flows`（即不做预测修正），算法仍可正常运行。

---

<a id="timingplan"></a>

## TimingPlan / PhaseInfo（配时方案）

由 `scenes/timing_loader.py` 从 Excel 读取。

### TimingPlan

| 字段 | 类型 | 含义 |
|------|------|------|
| `cycle_length` | `float` | 信号周期长度（秒） |
| `phases` | `List[PhaseInfo]` | 各相位参数列表 |

### PhaseInfo

| 字段 | 类型 | 含义 |
|------|------|------|
| `phase_index` | `int` | 相位序号 |
| `phase_name` | `str` | 相位名称（如 "南北直行"） |
| `green_time` | `float` | 绿灯时长（秒） |
| `yellow_time` | `float` | 黄灯时长（秒） |
| `red_time` | `float` | 红灯时长（秒） |

---

<a id="simulationmetrics"></a>

## SimulationMetrics（仿真指标）

**文件**：`core/types.py`

由 `experiments/metrics.py` 的 `compute_metrics()` 计算，对应竞赛 PDF 评分中的效率、安全、能耗维度。

| 字段 | 类型 | 含义 | 对应评分维度 |
|------|------|------|-------------|
| `step` | `int` | 采集步编号 | — |
| `avg_queue_length` | `float` | 平均排队长度 | 效率 |
| `max_queue_length` | `float` | 最大排队长度 | 效率 |
| `avg_delay` | `float` | 平均延误（秒/辆） | 效率 |
| `total_throughput` | `int` | 累计通过车辆数 | 效率 |
| `avg_travel_time` | `float` | 平均行程时间（秒） | 效率 |
| `total_stops` | `int` | 累计停车次数 | 安全/舒适 |
| `fuel_consumption` | `float` | 累计油耗（mL） | 能耗 |

---

<a id="trafficlevel"></a>

## TrafficLevel（流量等级）

```python
class TrafficLevel(str, Enum):
    LOW = "low"        # 0.5x 原始流量
    NORMAL = "normal"  # 1.0x 原始流量
    HIGH = "high"      # 1.5x 原始流量（压力测试）
```

由 `scenes/variant.py` 的 `VariantGenerator` 使用，生成不同流量倍率的 `.flow.xml` 变体文件。

---

<a id="tracibridge"></a>

## TraCIBridge（SUMO 桥接器）

**文件**：`engine/traci_bridge.py`

封装 SUMO 进程生命周期与 TraCI 读写，把底层调用转换为 `JointState` / `ControlAction`。

```python
TraCIBridge(
    sumo_cfg: Path,
    binary: str = "sumo",
    additional_files: Optional[List[Path]] = None,
    seed: Optional[int] = None,
    max_restarts: int = 0,
    vehicle_sample_rate: int = 1,
)
```

| 参数 | 说明 |
|------|------|
| `seed` | 随机种子；非 None 时 `_build_cmd` 追加 `--seed <n>` 传入 `traci.start`，保证可复现 |
| `max_restarts` | TraCI 连接断开时的最大自动重连次数（默认 0 = 不重连） |
| `vehicle_sample_rate` | 车辆快照采样率，每 N 辆取 1 辆（默认 1 = 全采） |
| `additional_files` | 追加 SUMO 附加文件（流量变体等），拼入 `-a f1,f2` |

| 方法 / 属性 | 说明 |
|-------------|------|
| `step()` | 推进一个仿真步，返回当前仿真时间；**TraCI 断开（如 SUMO 被杀）时优雅关闭并返回 `None`**；`max_restarts > 0` 时先尝试自动重连 |
| `get_state()` | 读取并组装当前 `JointState`（含 capacity、车辆快照、arrival_history） |
| `apply_actions(actions)` | 写入控制动作；`set_phase` 的 value 无法转为 int 时打 warning 并跳过（容错兜底） |
| `get_lane_capacity(lane_id)` | 车道容量 = `traci.lane.getLength(lane_id) / 7.5`（5m 车长 + 2.5m 间距） |
| `lane_directions` | 属性，`lane_id -> 方位` 映射（由 edge_mapping 进口道筛选建立，供压力映射用） |

---

<a id="edgechannel"></a>

## EdgeChannel（V2X 边缘通道）

**文件**：`engine/edge_channel.py`

模拟 V2X 消息的发送 / 接收 / 固定步数延迟 / 方向过滤。

```python
from engine.edge_channel import EdgeChannel

channel = EdgeChannel(delay_steps=1, allowed_directions=["north", "south"])
channel.send(state)              # allowed_directions 非空时先按方向过滤 queues/flows
delayed = channel.receive()      # 返回 delay_steps 步前发送的 JointState；缓冲不足返回 None
```

| 参数 | 说明 |
|------|------|
| `delay_steps` | 固定延迟步数（默认 1）；`receive()` 返回 `delay_steps` 步前入通道的消息 |
| `allowed_directions` | 允许通过的方向列表；`None` 表示不过滤 |

---

<a id="dispatchparams"></a>

## CloudPolicy.dispatch_params（云端参数下发）

**文件**：`cloud/cloud_policy.py`

云端按全局平均压力分档周期性下发控制参数（min/max/base_green），下发周期 = `algorithms.ca_maxpressure.cloud_update_interval`（默认 60 步）。周期内返回缓存值，每次重新下发打 `logger.info("云端下发参数: ...")`。

全局平均压力 `avg_pressure(state)` = 各进口道 `queue_length / capacity` 均值（capacity 缺失时退化为 `min(1.0, max_queue / 50.0)`）。

`PRESSURE_TIERS` 分档表：

| avg_pressure | min_green | max_green | base_green |
|--------------|-----------|-----------|------------|
| > 0.8（极高） | 20.0 | 120.0 | 45.0 |
| > 0.4（中档） | 15.0 | 90.0 | 35.0 |
| 常规 | 10.0 | 90.0 | 30.0 |

---

<a id="simulationrunner"></a>

## SimulationRunner（单次仿真运行器）

**文件**：`engine/runner.py`

```python
SimulationRunner(
    scene: Scene,
    algorithm: BaseControlAlgorithm,
    sumo_binary: Optional[str] = None,
    output_csv: Optional[Path] = None,        # 指标快照 CSV（每 snapshot_interval 步一行）
    snapshot_interval: Optional[int] = None,
    additional_files: Optional[List[Path]] = None,
    bridge: Optional[object] = None,
    seed: Optional[int] = None,               # 透传 TraCIBridge --seed
    step_log_csv: Optional[Path] = None,      # 每步日志（simulation_log）
    events_csv: Optional[Path] = None,        # 事件日志（events）
)
```

- `run(steps)`：完整仿真循环；`_tick()` 内部捕获 `FatalTraCIError` 或收到 `step() is None` 时返回 False，仿真优雅提前结束（日志 `closing gracefully`）。
- 快照 CSV 默认 `output/csv/{路口}_{算法}.csv`；`step_log_csv` / `events_csv` 传 None 则不产生对应文件。

---

<a id="experiments-cli"></a>

## experiments CLI（单次实验入口）

**文件**：`experiments/runner.py`

```bash
# 单次实验（路口 1，CA-MP，1.5 倍流量，seed=42）
python experiments/runner.py --intersection 1 --algorithm ca_maxpressure \
    --flow-multiplier 1.5 --seed 42 --steps 3600 --output-dir output/exp1
```

`--help` 输出摘要：

| 参数 | 默认 | 说明 |
|------|------|------|
| `--seed` | 42 | SUMO 随机种子（传入 traci.start --seed） |
| `--flow-multiplier` | 1.0 | 流量倍率：1.0=原始流量，1.5=压力测试 |
| `--output-dir` | config `paths.output_root` | 输出根目录 |
| `--intersection` | 1 | 路口编号 1-20 |
| `--steps` | 3600 | 仿真步数 |
| `--algorithm` | fixed_time | 可选 fixed_time / actuated / ca_maxpressure |

编程接口：`parse_args(argv)` 解析参数、`run_single(args)` 跑单次并返回快照 CSV 路径、`run_batch(...)` 批量矩阵。

---

<a id="输出文件表"></a>

## 输出文件表

以 `<output-dir>` = `--output-dir` 为例（命名中 `N`=路口、`x1.5`=流量倍率、`algo`=算法、`s42`=seed）：

| 文件 | 产生者 | 内容 |
|------|--------|------|
| `csv/N_x1.5_algo_s42.csv` | `MetricsCollector`（每 `snapshot_interval` 步快照） | 列：`step, timestamp, tls_id, current_phase, avg_queue_length, max_queue_length, avg_delay, total_throughput, avg_travel_time, total_stops, fuel_consumption`，外加每进口道 `queue_<dir>` / `flow_<dir>` |
| `logs/N_x1.5_algo_s42_simulation_log.csv` | `StepLogger`（每步） | 列：`step, timestamp, current_phase`，外加每进口道 `queue_<dir>` / `pressure_<dir>`（= queue/capacity，capacity=0 时为空） |
| `logs/N_x1.5_algo_s42_events.csv` | `EventLogger` | 列：`step, type, detail`（run_start / run_end / 各控制动作） |
| `variants/N/*.xml` | `VariantGenerator` | 流量变体 rou/flow 文件（`--flow-multiplier != 1.0` 时生成） |

---

<a id="使用示例"></a>

## 使用示例

### 实现一个最简算法

```python
from typing import List
from algorithms.base import BaseControlAlgorithm
from core.types import ControlAction, JointState, Scene


class MyAlgorithm(BaseControlAlgorithm):
    def init(self, scene: Scene) -> None:
        self.tls_id = f"J{scene.meta.intersection_id}"

    def step(self, state: JointState) -> List[ControlAction]:
        # 每 30 秒切换一次相位
        if state.elapsed_phase_time >= 30.0:
            next_phase = (state.current_phase + 1) % 4
            return [ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=next_phase,
                reason="定时切换",
            )]
        return []

    def reset(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "my_algorithm"
```

### 运行单次仿真

```python
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from engine.runner import SimulationRunner
from scenes.registry import SceneRegistry

registry = SceneRegistry()
scene = registry.get_scene("16")  # 路口 16（24m 短边，CA-MP 效果最显著）

algo = CAMaxPressureAlgorithm()
runner = SimulationRunner(scene=scene, algorithm=algo)
metrics = runner.run(steps=3600)

print(f"平均排队: {metrics[-1]['avg_queue_length']:.1f}")
```

### 批量实验

```python
from experiments.runner import run_batch

results = run_batch(
    intersection_ids=["1", "16"],
    algorithms=["fixed_time", "ca_maxpressure"],
    seeds=[42, 123, 456],
    steps=3600,
)
# results: [{"intersection_id": "1", "algorithm": "fixed_time", "seed": "42", "csv": "..."}, ...]
```

---

## 变更记录

| 日期 | 变更 | 操作人 |
|------|------|--------|
| 2026-07-20 | 初始版本，接口冻结 | TL |
| 2026-07-23 | 增补 QueueState.capacity / VehicleState / JointState.vehicles+arrival_history；新增 TraCIBridge / EdgeChannel / CloudPolicy.dispatch_params / SimulationRunner / experiments CLI / 输出文件表小节 | IB |

> **7/23 后接口冻结**。此后 `core/types.py` 和 `algorithms/base.py` 不再修改。
> 如需扩展，只能向后兼容（加字段、加方法），不得删改已有字段。
