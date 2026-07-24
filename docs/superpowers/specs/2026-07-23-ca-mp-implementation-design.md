# CA-MP 算法完整实现设计

- 日期：2026-07-23
- 状态：待评审
- 负责人：AB（算法 B），TL 评审接口变更
- 关联里程碑：W1 M1（接口冻结）/ W2 M2（CA-MP 对比数据）

## 1. 背景与问题

`algorithms/ca_max_pressure.py` 当前为 MVI 骨架：选择排队最长方向输出 `set_phase`。
代码内三个 TODO 指出了完整实现的阻塞点：

1. `QueueState` 缺少 `capacity` 与占用率字段 → 容量归一化压力、溢出门控无法实现；
2. 算法无法获得"相位 ↔ 车道"映射 → MVI 把车道名当相位值传给 `set_phase`，
   `TraCIBridge.apply_actions` 中 `int(action.value)` 会对 `"E0_0"` 这类值抛异常（隐藏 bug）；
3. `CloudPolicy.dispatch_base_green` 返回固定配置值 → 云端动态绿灯未实现。

## 2. 方案选型

| 方案 | 做法 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A 最小侵入 | 算法 `init()` 直接调 traci 查车道长度与受控链接 | 不改数据契约 | 算法层依赖 traci，云-边-端分层被破坏；MockBridge 离线测试覆盖不到核心逻辑 | 否决 |
| **B 契约扩展（采纳）** | 扩展 `QueueState`/`JointState`，由 TraCIBridge 与 MockBridge 统一填充 | 算法纯数据驱动；符合"接口冻结、契约统一"架构定位；离线可测 | 需改动 `core/types.py` 与两个 bridge | **采纳** |
| C 静态配置 | 容量从 metadata 读，相位映射手工配置 | 实现最简单 | 20 路口相位结构各异，维护不可扩展；occupancy 拿不到，溢出门控做不了 | 否决 |

## 3. 架构与组件

```
SUMO ──TraCI──> TraCIBridge ──JointState(+capacity/occupancy/phase_lanes)──> CAMaxPressureAlgorithm
                     ▲                                                              │
                     │                         CloudPolicy.predict / dispatch_base_green
                     └──────────────────── ControlAction(set_phase/set_phase_duration)
```

组件职责：

- `core/types.py`：数据契约扩展（唯一接口变更点）。
- `engine/traci_bridge.py`：填充 capacity、occupancy、phase_lanes。
- `engine/mock_bridge.py`：同步填充确定性数据，保证离线测试与 CI 可用。
- `algorithms/ca_max_pressure.py`：完整 CA-MP 决策逻辑（三项改进）。
- `cloud/cloud_policy.py`：`dispatch_base_green` 按全局压力动态调整。

## 4. 数据契约变更（core/types.py）

```python
@dataclass
class QueueState:
    direction: str
    queue_length: float
    waiting_time: float
    vehicle_count: int
    capacity: float = 0.0    # 车道 jam 容量（辆），0 表示未知 → 算法回退绝对排队
    occupancy: float = 0.0   # 进口道占用率 0~1

@dataclass
class JointState:
    ...                      # 既有字段不变
    phase_lanes: Dict[int, List[str]] = field(default_factory=dict)  # 相位索引 → 放行进口车道
```

默认值保证既有构造调用与测试不破坏（向后兼容）。

## 5. Bridge 填充逻辑

### TraCIBridge

- `start()` 时构建 `phase_lanes` 并缓存：遍历 `getControlledLinks(tls_id)`，
  对每个相位，信号状态串中该 link 为 `G`/`g` 时，将对应进口 lane 加入该相位集合。
- `capacity = traci.lane.getLength(lane) / 7.5`（7.5 m/辆 jam 间距）。
- `occupancy = traci.lane.getLastStepOccupancy(lane) / 100.0`（TraCI 返回百分比）。
- 单项 traci 查询异常：记 warning 日志，该字段回退默认值，不中断仿真。

### MockBridge

- 按既有确定性数据风格填充：`capacity = 20.0`，
  `occupancy = queue_length / capacity`（截断到 1.0），
  `phase_lanes = {i: [directions[i]] for i in range(len(directions))}`。

## 6. CA-MP 决策逻辑（algorithms/ca_max_pressure.py）

每个决策点（见决策节拍）按以下优先级执行：

1. **溢出门控（最高优先）**：任一进口道 `occupancy > overflow_occupancy_threshold`（默认 0.9）
   → 输出 `set_phase` 到放行该车道的相位（`phase_lanes` 反查），reason="溢出门控"。
2. **容量归一化相位压力**：
   `pressure[p] = Σ_{lane ∈ phase_lanes[p]} effective_queue[lane] / capacity[lane]`
   - `effective_queue = queue_length + γ × predicted_flow × horizon / 3600`
     （EWMA 前瞻修正，γ 为配置项 `prediction_weight`，默认 0.5）
   - `capacity` 为 0 或缺失时，该车道的 `queue/capacity` 回退为 `queue_length`（绝对排队）。
3. **选相位**：`best_phase = argmax(pressure)`；若与当前相位相同则仅更新时长，不切换。
4. **动态绿灯**：`duration = base_green × (p_best / p_avg)`，
   其中 `p_avg` 为所有相位压力的算术平均值（均值为 0 时 `duration = base_green`），
   结果 clamp 到 `[min_green, max_green]`。
   输出 `set_phase(int 相位索引)` 与 `set_phase_duration(duration)`。

决策节拍：

- 每 `decision_interval`（默认 5 仿真秒，按场景步长换算成步数）评估一次；
  0.1s 步长路口避免每步抖动与频繁切相。
- 黄灯/全红过渡相位（不在 `phase_lanes` 键中）期间不输出动作。

## 7. 云端动态绿灯（cloud/cloud_policy.py）

- `dispatch_base_green(state)`：全局压力 `G = Σqueue / Σcapacity`（分母为 0 时返回当前值）；
  - `G > high_pressure`（默认 0.6）→ `base_green × 1.2`
  - `G < low_pressure`（默认 0.2）→ `base_green × 0.8`
  - 结果 clamp 到 `[min_green, max_green]`。
- 边缘算法每 `dispatch_interval`（默认 300 仿真秒）调用一次并缓存 `base_green`，
  其余时刻沿用缓存值，模拟"云端周期性下发、边缘自主执行"。

## 8. 配置项（config/default.yaml，algorithms.ca_maxpressure 节）

| 键 | 默认 | 说明 |
|----|------|------|
| overflow_occupancy_threshold | 0.9 | 溢出门控阈值（既有） |
| base_green / min_green / max_green | 30 / 10 / 90 | 绿灯时长边界（既有） |
| ewma_alpha / prediction_horizon | 0.3 / 300 | EWMA 参数（既有） |
| prediction_weight（新增） | 0.5 | 预测流量折算排队的权重 γ |
| decision_interval（新增） | 5 | 决策节拍（仿真秒） |
| dispatch_interval（新增） | 300 | 云端 base_green 下发周期（仿真秒） |
| high_pressure / low_pressure（新增） | 0.6 / 0.2 | 云端全局压力档位阈值 |

## 9. 错误处理

- `state.queues` 为空 → 返回空列表（既有行为，测试保留）。
- `phase_lanes` 为空（bridge 未提供）→ 回退为按车道绝对排队选相位，
  `set_phase` 值取 `current_phase`（不切换）仅更新时长，避免 MVI 的车道名 bug。
- traci 单点查询异常 → warning + 默认值，仿真继续。

## 10. 测试计划

更新 `tests/unit/test_algorithms.py` 与（如需）`tests/unit/test_mock_bridge.py`：

- 替换 `test_ca_maxpressure_mvi_selects_max_queue_phase`（断言 "MVI" 字样，随实现废弃）为：
  - 容量归一化：短车道高 queue/capacity 时优先于长车道低比率方向；
  - 溢出门控：occupancy > 0.9 时输出目标相位且 reason 含"溢出门控"；
  - 动态绿灯：时长被 clamp 到 [min_green, max_green]。
- 保留：接口契约测试、空 queues 返回空、`test_algorithm_names_unique`。
- MockBridge 填充字段的确定性测试（capacity/occupancy/phase_lanes 非空且类型正确）。
- 验证命令：`python -m pytest tests/ -x -q`；
  端到端：`python examples/run_fixed_time.py 1` 回归 + CA-MP 跑通路口 1 共 3600 步。

## 11. 范围外（YAGNI）

- 经典 MaxPressure 的出口道（downstream）压力差：单路口场景出口压力难以定义，按 README 口径只用进口压力。
- XGBoost 云端模型：`CloudPolicy` 已预留 `model.pkl` 加载，本设计仅 EWMA。
- 多路口协调：20 路口各自独立仿真，不做区域协调。
