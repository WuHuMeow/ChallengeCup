# 算法 A（AA） W1 任务书

> 周期：7/20（周日）- 7/26（周六） | 核心目标：实现 FixedTimeAlgorithm 与 RuleAdaptiveAlgorithm 两个基线算法，跑通路口 1 的 3600 步仿真

## 本周背景

本周首次接触项目的核心接口契约与基线算法定位，需要先建立以下概念：

- **基线算法的角色**：FixedTime（固定配时）与 RuleAdaptive（感应控制）是 CA-MP 创新算法的对照组——没有稳定基线，就无法证明 CA-MP 的优越性。
- **`BaseControlAlgorithm` 契约**（`algorithms/base.py`）：所有算法必须实现 `init(scene)` / `step(state) -> List[ControlAction]` / `reset()` / `name`，由 `engine/runner.py` 统一调度。
- **`JointState`**（`core/types.py`）：算法 `step()` 的输入，包含 `tls_id`、`current_phase`、`elapsed_phase_time`、`queues: List[QueueState]`、`flows: Dict[str, float]`。
- **`ControlAction`**：算法输出，`action_type ∈ {"set_phase", "set_phase_duration", "set_program"}`，由 `engine/traci_bridge.py` 写入 SUMO；返回空列表表示"本步不干预"。
- **SUMO 信号灯 API**：`traci.trafficlight.getPhase / setPhase / setPhaseDuration / getCompleteRedYellowGreenDefinition`。

---

## 每日任务

### Day 1（7/20 周日）

**熟悉数据与接口**

- [ ] 阅读 `core/types.py` 与 `algorithms/base.py`，理解 `JointState` / `ControlAction` / `BaseControlAlgorithm` 的字段含义
- [ ] 用 pandas 打开路口 1 配时文件 `data/intersection_data/1/路口数据/demo_1流量和交叉口配时方案.xlsx`，确认周期、各相位绿/黄灯时长结构
- [ ] 打开路口 1 路网 `data/intersection_data/1/sumo工程/demo_1.net.xml`，找到 `<tlLogic>` 节点，理解 6 相位 state 字符串（如 `GGGGgrrrrGGGGgrrrr`）
- [ ] 通读 SUMO 信号灯 API：`getPhase` / `setPhase` / `setPhaseDuration` / `getCompleteRedYellowGreenDefinition`

```python
# algorithms/base.py —— 所有算法必须实现的契约
class BaseControlAlgorithm(ABC):
    @abstractmethod
    def init(self, scene: Scene) -> None: ...

    @abstractmethod
    def step(self, state: JointState) -> List[ControlAction]:
        """返回空列表 = 本步不干预 SUMO（固定配时基线即如此）。"""
        ...

    @abstractmethod
    def reset(self) -> None: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
```

**验证：** `python -c "from algorithms.base import BaseControlAlgorithm; from core.types import JointState, ControlAction; print('ok')"` → 输出 `ok`

### Day 2（7/21 周一）

**实现 FixedTimeAlgorithm**

- [ ] 创建 `algorithms/fixed_time.py`，继承 `BaseControlAlgorithm`，`name` 返回 `"fixed_time"`
- [ ] 采用方式 A（推荐）：`step()` 返回空列表，让 SUMO 按 `net.xml` 默认配时运行——这就是"传统固定配时"的真实含义
- [ ] 预留 `use_excel_timing` 开关：`init()` 中若开启则调用 `scenes/timing_loader.parse_timing_excel` 写入 SUMO（W1 可先留接口）
- [ ] 接入 IB 的 `engine/runner.py`，跑路口 1 的 3600 步

```python
# algorithms/fixed_time.py —— 固定配时基线的"形状"
class FixedTimeAlgorithm(BaseControlAlgorithm):
    """固定配时对照组：默认使用 SUMO 默认程序，可选读取 Excel 配时方案。"""

    def __init__(self, use_excel_timing: bool = False) -> None:
        self.use_excel_timing = use_excel_timing
        self.scene: Scene | None = None

    def init(self, scene: Scene) -> None:
        self.scene = scene
        if self.use_excel_timing:
            self._apply_excel_timing(scene)  # 调用 scenes/timing_loader

    def step(self, state) -> List:
        """固定配时不输出控制动作，完全依赖 SUMO 当前程序。"""
        return []

    @property
    def name(self) -> str:
        return "fixed_time"
```

**验证：** `python examples/run_fixed_time.py 1` → 输出 `仿真完成，共记录 N 条指标快照`，且 `output/csv/1_fixed_time.csv` 存在

### Day 3（7/22 周二）

**实现 RuleAdaptiveAlgorithm**

- [ ] 创建 `algorithms/rule_adaptive.py`，参数 `min_green` / `max_green` / `queue_threshold` 从 `config/default.yaml` 的 `algorithms.actuated` 读取（默认 10 / 60 / 5）
- [ ] 实现感应核心逻辑：`elapsed < min_green` 保持；排队 > 阈值且未达 `max_green` 延长绿灯（`set_phase_duration`）；否则切换下一相位（`set_phase`）
- [ ] `ControlAction.tls_id` 必须取自 `state.tls_id`，`reason` 写明触发原因（便于日志排查）
- [ ] 跑路口 1，确认绿灯时长在 `min_green ~ max_green` 之间动态变化

```python
# algorithms/rule_adaptive.py —— 感应控制核心逻辑
def step(self, state: JointState) -> List[ControlAction]:
    if state.elapsed_phase_time < self.min_green:
        return []  # 最小绿灯内强制保持

    max_queue = max((q.queue_length for q in state.queues), default=0.0)
    if max_queue > self.queue_threshold and state.elapsed_phase_time < self.max_green:
        return [ControlAction(tls_id=state.tls_id, action_type="set_phase_duration",
                              value=5.0, reason="queue_high_extend_green")]

    next_phase = (state.current_phase + 1) % max(len(state.queues), 2)
    return [ControlAction(tls_id=state.tls_id, action_type="set_phase",
                          value=next_phase, reason="queue_low_next_phase")]
```

**验证：** `pytest tests/test_algorithms.py::test_rule_adaptive_returns_control_actions -q` → `1 passed`

### Day 4（7/23 周三）

**测试与调试**

- [ ] 路口 1 跑 FixedTime：`python examples/run_fixed_time.py 1`，检查 CSV 中 `total_throughput > 0`、有排队记录
- [ ] 参照 `run_fixed_time.py` 创建 `examples/run_rule_adaptive.py`，跑路口 1 的 3600 步
- [ ] 从日志/CSV 验证感应逻辑：绿灯时长在 `min_green ~ max_green` 间变化，排队低于阈值时提前切换
- [ ] 对比两者输出：感应控制的平均行程时间应略优于固定配时

```python
# examples/run_rule_adaptive.py —— 参照 run_fixed_time.py 的结构
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from engine.runner import SimulationRunner
from scenes.registry import SceneRegistry

registry = SceneRegistry()
scene = registry.get_scene(sys.argv[1] if len(sys.argv) > 1 else "1")
algorithm = RuleAdaptiveAlgorithm()  # 参数从 config/default.yaml 读取
runner = SimulationRunner(scene, algorithm)
metrics = runner.run(steps=3600)
print(f"仿真完成，共记录 {len(metrics)} 条指标快照")
```

**验证：** `python examples/run_rule_adaptive.py 1` → 输出 `仿真完成`，`output/csv/1_rule_adaptive.csv` 存在且非空

### Day 5（7/24 周四）

**适配多路口**

- [ ] 确认两个算法均从 `net.xml` 动态读取相位方案，不硬编码相位数量（路口 1 是 6 相位，其他路口可能不同）
- [ ] 处理步长差异：路口 11-13、15-20 步长 0.1s，`elapsed_phase_time` 由 `JointState` 提供，算法不要自己累加时间
- [ ] 在路口 11（0.1s 步长）上跑通 FixedTime 与 RuleAdaptive
- [ ] 在路口 16（5 进口道）上跑通两个算法

```python
# 多路口适配的关键：相位数量从 state 动态获取，不硬编码
next_phase = (state.current_phase + 1) % max(len(state.queues), 2)
# 步长差异由 JointState.elapsed_phase_time 自动反映：
#   1s 步长路口：elapsed 每秒 +1；0.1s 步长路口：每步 +0.1
# 算法只比较 elapsed 与 min_green / max_green，无需感知步长
```

**验证：** `python examples/run_fixed_time.py 11 && python examples/run_fixed_time.py 16` → 两条命令均输出 `仿真完成`，无异常退出

### Day 6（7/25 周五）

**与 AB 协调**

- [ ] 与 AB 确认 CA-MP 的 `step()` 返回值格式与基线一致（都是 `List[ControlAction]`，`tls_id` 取自 `state.tls_id`）
- [ ] 确保 `examples/` 中三个入口脚本（`run_fixed_time.py` / `run_rule_adaptive.py` / `run_ca_max_pressure.py`）可通过参数切换路口
- [ ] 协助 TL 做集成测试：三种算法在 `experiments/runner.py` 的 `ALGORITHM_MAP` 中均可调度

```python
# experiments/runner.py —— 三种算法统一注册，AA 负责前两个
ALGORITHM_MAP: Dict[str, type[BaseControlAlgorithm]] = {
    "fixed_time": FixedTimeAlgorithm,        # AA
    "actuated": RuleAdaptiveAlgorithm,       # AA
    "ca_maxpressure": CAMaxPressureAlgorithm,  # AB
}
```

**验证：** `pytest tests/test_algorithms.py::test_algorithm_names_unique -q` → `1 passed`（三个算法 name 互不相同）

### Day 7（7/26 周六）

**Buffer / 文档**

- [ ] 为 `fixed_time.py` / `rule_adaptive.py` 补全 docstring：算法原理、参数含义、返回值约定
- [ ] 跑一遍 `pytest tests/test_algorithms.py -q`，确保接口契约测试全绿
- [ ] （可选）开始阅读 Webster 公式，作为第三基线候选
- [ ] 提交代码给 TL

```python
"""规则自适应算法。

根据实时排队长度动态调整绿灯时长：
- 当前相位绿灯时间不足最小绿灯时，强制保持；
- 当前方向排队超过阈值且未达最大绿灯时，延长绿灯；
- 否则切换至下一相位。
参数 min_green / max_green / queue_threshold 来自 config/default.yaml。
"""
```

**验证：** `pytest tests/test_algorithms.py -q` → 全部 passed，无 failure / error

---

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `algorithms/fixed_time.py` | 7/21 | 路口 1 跑通 3600 步，`step()` 返回空列表 |
| 2 | `algorithms/rule_adaptive.py` | 7/22 | 路口 1 跑通，绿灯时长在 min~max 间变化 |
| 3 | 多路口适配 | 7/24 | 路口 11（0.1s）和路口 16（5 进口道）可运行 |
| 4 | `examples/` 入口脚本 | 7/25 | `run_fixed_time.py` / `run_rule_adaptive.py` / `run_ca_max_pressure.py` 三个入口 |

## 协作对接

- 与 **IB** 对接 `engine/runner.py` 与 `traci_bridge` 的接入方式，确认 `step()` 调用时机。
- 与 **AB** 对齐 `ControlAction` 输出格式，确保三种算法可公平对比。
- 不修改 `algorithms/base.py` / `core/types.py`，接口问题找 **TL**。
