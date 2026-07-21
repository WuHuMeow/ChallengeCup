# 算法 B（AB） W1 任务书

> 周期：7/20（周日）- 7/26（周六） | 核心目标：在路口 1 跑通 CA-MP 核心逻辑（容量归一化压力 + 溢出门控）

## 本周背景

你是整个项目的核心——CA-MP（Capacity-Aware MaxPressure）算法是团队的创新点，直接决定"方案设计与创新性"25 分的得分。W1 的目标是在路口 1 上跑通 CA-MP 核心逻辑（先不接云端策略，直接通过 SimulationRunner 验证算法正确性）。

**原版 MaxPressure**（Varaiya 2013）：每个相位压力 = 上游进口道排队 − 下游出口道排队，每个决策时刻选压力最大的相位放行；对任意网络吞吐量最优。

**CA-MP 三项改进**（W1 实现前两项，第三项 W2 接入）：

1. **容量归一化压力**：`pressure = queue / capacity`（原版是 `queue_up − queue_down`）。24m 短车道排 3 辆车 = 75% 占用，100m 长车道排 12 辆车也是 75% 占用——归一化后短车道自动获得更高优先级，防止"几个车就堵死"。
2. **溢出门控**：任一进口道占用率 > 90% 时强制给该方向绿灯（不管压力差）。窄路一旦堵死无法恢复，必须预防性放行。阈值 0.9 是初始值，调优是实验组 W4 的事。
3. **云端动态绿灯时长**（W2 接入）：`duration = base_green × (phase_pressure / avg_pressure)`，再 `clip(duration, min_green, max_green)`，压力大的方向给更长绿灯。

你能从 `JointState`（见 `core/types.py`）获取：`queues: List[QueueState]`（direction / queue_length / waiting_time / vehicle_count）、`current_phase`、`elapsed_phase_time`、`flows: Dict[str, float]`、`detector_values`。

## 每日任务

### Day 1（7/20 周日）

- [ ] 阅读 MaxPressure 原始论文摘要（Varaiya 2013，搜索 "Max pressure control of a network of signalized intersections"），重点理解 pressure 定义、为何选最大压力相位、稳定性证明
- [ ] 阅读 CSDN 的 SUMO 实现示例（https://blog.csdn.net/weixin_48557841/article/details/126948935），理解 `NetworkData` 如何解析路网、如何计算压力
- [ ] 阅读 TL 发布的 `core/types.py` 与 `algorithms/base.py`，确认 `BaseControlAlgorithm` 的四个抽象成员（`init` / `step` / `reset` / `name`）
- [ ] 打开 `data/intersection_data/1/sumo工程/demo_1.net.xml`，定位 `<tlLogic>` 与 `<connection>` 节点，弄清相位 state 字符串含义

```xml
<!-- demo_1.net.xml 中的信号灯定义片段（你要解析的对象） -->
<tlLogic id="J1" type="static" programID="0" offset="0">
    <phase duration="30" state="GGGGgrrrrGGGGgrrrr"/>  <!-- 东西直行+左转 -->
    <phase duration="3"  state="yyyyyrrrryyyyyrrrr"/>  <!-- 黄灯，需跳过 -->
    <phase duration="30" state="rrrrrGGGGrrrrrGGGG"/>  <!-- 南北 -->
    <phase duration="3"  state="rrrrryyyyrrrrryyyy"/>  <!-- 黄灯，需跳过 -->
</tlLogic>
<connection from="1_e" to="1_w" fromLane="0" toLane="0" tl="J1" linkIndex="0"/>
```

**验证：** `grep -c "<phase" data/intersection_data/1/sumo工程/demo_1.net.xml` 应输出路口 1 的相位总数（含黄灯，预期 6）。

### Day 2（7/21 周一）

- [ ] 创建 `algorithms/ca_max_pressure.py`，继承 `BaseControlAlgorithm`，实现 `init` / `step` / `reset` / `name`
- [ ] 实现 `_parse_network()`：从 `scene.meta.sumo_net` 解析 `<tlLogic>` 与 `<connection>`，建立 `phase_index → [lane_ids]` 映射，并按 `车道容量 = length / 7.5` 计算容量
- [ ] 实现改进 1（容量归一化压力）与改进 2（溢出门控），`name` 返回 `"ca_maxpressure"`
- [ ] 动态绿灯时长（改进 3）先留 TODO，W2 接入 CloudPolicy 后补全

```python
# algorithms/ca_max_pressure.py（W1 核心形状）
from __future__ import annotations
from typing import List
from algorithms.base import BaseControlAlgorithm
from core.config import get_config
from core.types import ControlAction, JointState, Scene


class CAMaxPressureAlgorithm(BaseControlAlgorithm):
    """容量感知最大压力控制器（CA-MP，核心创新）。"""

    def __init__(self) -> None:
        cfg = get_config().get("algorithms.ca_maxpressure", {})
        self.overflow_threshold = cfg.get("overflow_occupancy_threshold", 0.9)
        self.base_green = cfg.get("base_green", 30)
        self.min_green = cfg.get("min_green", 10)
        self.max_green = cfg.get("max_green", 90)
        self._lane_capacities: dict[str, float] = {}   # lane_id -> length/7.5
        self._phase_to_lanes: dict[int, list[str]] = {}
        self._green_phases: list[int] = []             # 跳过黄灯相位

    def step(self, state: JointState) -> List[ControlAction]:
        if not state.queues:
            return []
        overflow = self._check_overflow(state)         # 改进 2
        if overflow is not None:
            return [ControlAction(state.tls_id, "set_phase", float(overflow), "overflow gating")]
        pressures = self._normalized_pressures(state)  # 改进 1: queue / capacity
        best = max(self._green_phases, key=lambda p: pressures.get(p, 0.0))
        return [ControlAction(state.tls_id, "set_phase", float(best), f"max pressure phase={best}")]
```

**验证：** `python -m pytest tests/test_algorithms.py -k ca_maxpressure -q` 应全部通过（接口契约 + 空排队返回 `[]`）。

### Day 3（7/22 周二）

- [ ] 用 `examples/run_demo.py` 在路口 1 上跑 CA-MP（Mock 模式，无需 SUMO），确认调用链贯通
- [ ] 检查相位切换是否合理（不会一直卡在同一相位）、绿灯时长是否在 `min_green ~ max_green` 范围内
- [ ] 与固定配时对比：CA-MP 输出 CSV 的平均行程时间应更低（有 SUMO 时用 `--sumo` 跑真仿真）

```python
# examples/run_demo.py 已注册 CA-MP，直接调用即可（ALGORITHM_MAP 片段）
ALGORITHM_MAP = {
    "fixed_time": FixedTimeAlgorithm,
    "actuated": RuleAdaptiveAlgorithm,
    "ca_maxpressure": CAMaxPressureAlgorithm,
}
# 离线演示走 MockBridge：Config → SceneRegistry → SimulationRunner
#   → CAMaxPressureAlgorithm.step() → CloudPolicy.predict() → MetricsCollector → CSV
```

**验证：** `python examples/run_demo.py 1 ca_maxpressure` 应打印 `链路验证完成` 与 `CSV 输出: .../1_ca_maxpressure.csv`。

### Day 4（7/23 周三）

- [ ] 处理边界：压力全为 0（无车）时返回空列表，不切换
- [ ] 多个相位压力相同时选当前相位，避免频繁切换
- [ ] 黄灯相位处理：`_green_phases` 只收录含 `G/g` 的相位，跳过黄灯
- [ ] 步长差异：路口 11-13、15-20 步长 0.1s，与 TL/IB 确认决策频率方案（每 10 步=1s 决策一次，或 duration 以仿真步为单位）

```python
def _check_overflow(self, state: JointState):
    """占用率 > overflow_threshold 时返回对应绿灯相位，否则 None。"""
    for q in state.queues:
        cap = self._lane_capacities.get(q.direction, 1.0)
        if cap > 0 and q.queue_length / cap > self.overflow_threshold:
            for phase, lanes in self._phase_to_lanes.items():
                if q.direction in lanes and phase in self._green_phases:
                    return phase
    return None
```

**验证：** `python -m pytest tests/test_algorithms.py -q` 全部通过，且空排队用例返回 `[]`、非空用例 `action.tls_id == state.tls_id`。

### Day 5（7/24 周四）

- [ ] 在路口 16（5 进口道、24m 短边）测试：溢出门控应频繁触发（24m 只能排 3-4 辆车），容量归一化应让短边获得高优先级
- [ ] 在路口 11（0.1s 步长）测试：确认决策频率正确
- [ ] 记录各路口表现差异，为实验组提供调参建议

```python
# 用同一入口切换路口（Mock 快速验证逻辑，--sumo 跑真实仿真）
# python examples/run_demo.py 16 ca_maxpressure
# python examples/run_demo.py 11 ca_maxpressure
scene = registry.get_scene("16")          # scenes/registry.py 自动适配 5 进口道
algo = CAMaxPressureAlgorithm()
runner = SimulationRunner(scene, algo)    # engine/runner.py
```

**验证：** `python examples/run_demo.py 16 ca_maxpressure` 成功跑完 10 步且无异常退出（有 SUMO 时加 `--sumo` 跑 3600 步）。

### Day 6（7/25 周五）

- [ ] 将 CA-MP 接入 IB 的 SimulationRunner 完整流程：`runner.run()` → `bridge.get_state()` → `JointState` → `algorithm.step()` → `List[ControlAction]` → `bridge.apply_actions()`
- [ ] 确认 CloudPolicy 接口兼容（W2 正式接入）：`CloudPolicy.predict(state)` 返回 `PredictionResult`，算法据此更新 `min_green/max_green/base_green`
- [ ] 修复联调 bug

```python
# engine/runner.py 主循环（你要对接的契约）
self.bridge.start()
self.algorithm.init(self.scene)
for step in range(steps):
    state = self.bridge.get_state()              # -> JointState
    actions = self.algorithm.step(state)         # -> List[ControlAction]
    self.bridge.apply_actions(actions)
    self.bridge.step()
```

**验证：** `python examples/run_demo.py 1 ca_maxpressure` 完整跑通且日志出现 `MockBridge 收到动作: ... type=set_phase`。

### Day 7（7/26 周六）

- [ ] 核心稳定后预研 EWMA 流量预测（W4 正式接入）：公式 `predicted = alpha × current + (1 − alpha) × last_predicted`
- [ ] 思考预测值如何融入压力计算（利用 `JointState.flows`），只写设计笔记不写代码
- [ ] 提交代码给 TL

```python
# EWMA 预研形状（W4 在 cloud/cloud_policy.py 落地，alpha 默认 0.3）
predicted[direction] = alpha * observed + (1 - alpha) * prev_predicted
```

**验证：** `python -m pytest tests/ -q` 全绿后，将 `algorithms/ca_max_pressure.py` 提交给 TL。

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `algorithms/ca_max_pressure.py` | 7/22 | 核心逻辑完整（容量归一化 + 溢出门控），`name == "ca_maxpressure"`，通过 `tests/test_algorithms.py` |
| 2 | 路口 1 跑通 | 7/22 | `python examples/run_demo.py 1 ca_maxpressure` 链路贯通并产出 CSV |
| 3 | 路口 1 对比数据 | 7/23 | CA-MP vs FixedTime 输出 CSV，平均行程时间更低 |
| 4 | 路口 16 测试通过 | 7/24 | 溢出门控在 24m 短边触发 |
| 5 | SimulationRunner 联调通过 | 7/25 | 完整仿真流程跑通无崩溃 |

## 协作对接

- 与 **TL** 确认 `core/types.py` / `algorithms/base.py` 接口冻结，不擅自修改这两个文件；步长差异方案与 **TL/IB** 对齐。
- 与 **IB** 联调 SimulationRunner ↔ TraCIBridge ↔ 算法的消息闭环。
- 与 **AA** 确认三种算法 `step()` 返回格式一致（均为 `List[ControlAction]`）。
