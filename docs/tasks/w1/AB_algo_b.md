# W1 任务书：算法 B（AB）

> 周期：7/20（周日）- 7/26（周六）
> 核心目标：实现 CAMaxPressureAlgorithm 核心逻辑（容量归一化 + 溢出门控）

---

## 背景

你是整个项目的核心——CA-MP（Capacity-Aware MaxPressure）算法是团队的创新点，直接决定"方案设计与创新性"25 分的得分。W1 的目标是在路口 1 上跑通 CA-MP 核心逻辑（先不接云端策略，直接通过 SimulationRunner 验证算法正确性）。

---

## CA-MP 算法原理

### 原版 MaxPressure
- 每个相位有一个"压力" = 上游进口道排队 - 下游出口道排队
- 每个决策时刻，选择压力最大的相位放行
- 理论性质：对任意网络吞吐量最优（Varaiya 2013）

### CA-MP 三项改进

**改进 1：容量归一化**
```
原版: pressure = upstream_queue - downstream_queue
改进: pressure = upstream_queue / upstream_capacity - downstream_queue / downstream_capacity
```
- 为什么：24m 短车道排 3 辆车 = 75% 占用；100m 长车道排 12 辆车 = 75% 占用
- 效果：短车道自动获得更高优先级，防止"几个车就堵死"

**改进 2：溢出门控**
```
if any lane occupancy > 90%:
    强制给该方向绿灯（不管压力差）
```
- 为什么：窄路上一旦堵死就无法恢复，必须预防性放行
- 阈值 90% 是初始值，后续实验组会调优

**改进 3：云端动态绿灯时长**（W2 接入）
```
duration = base_green * (phase_pressure / avg_pressure)
duration = clip(duration, min_green, max_green)
```
- 压力大的方向给更长绿灯，压力小的方向缩短

---

## 每日任务

### Day 1（7/20 周日）

**理解 MaxPressure 算法**
1. 阅读 MaxPressure 原始论文摘要（Varaiya 2013）：
   - 搜索："Max pressure control of a network of signalized intersections"
   - 重点理解：pressure 的定义、为什么选最大压力相位、稳定性证明
2. 阅读 CSDN 上的 SUMO 实现示例：
   - https://blog.csdn.net/weixin_48557841/article/details/126948935
   - 理解 `NetworkData` 类如何解析路网、如何计算压力
3. 阅读 TL 发布的 `core/types.py` 和 `algorithms/base.py`
4. 理解 `JointState` 中你能获取的信息：
   - `queues: List[QueueState]` — 各进口道排队状态（direction, queue_length, waiting_time, vehicle_count）
   - `current_phase: int` — 当前相位索引
   - `elapsed_phase_time: float` — 当前相位已持续时间
   - `flows: Dict[str, float]` — 各检测器流量
   - `detector_values: Dict[str, float]` — 检测器原始值

### Day 2（7/21 周一）

**实现 CA-MP 核心**
1. 创建 `algorithms/ca_max_pressure.py`：

```python
from typing import Dict, List, Optional

from algorithms.base import BaseControlAlgorithm
from core.types import ControlAction, JointState, QueueState, Scene


class CAMaxPressureAlgorithm(BaseControlAlgorithm):
    """容量感知最大压力控制器（核心创新）"""

    def __init__(self,
                 overflow_threshold: float = 0.9,
                 min_green: float = 10.0,
                 max_green: float = 60.0,
                 base_green: float = 30.0):
        self.overflow_threshold = overflow_threshold
        self.min_green = min_green
        self.max_green = max_green
        self.base_green = base_green

        self._lane_capacities: Dict[str, float] = {}  # lane_id -> capacity
        self._phase_to_lanes: Dict[int, List[str]] = {}  # phase_index -> [lane_ids]
        self._green_phases: List[int] = []  # 非黄灯相位列表
        self._tls_id: str = ""

    def init(self, scene: Scene) -> None:
        """从 scene.meta 解析路网：
        1. 各车道长度 → 计算容量 (length / 7.5)
        2. 各相位对应哪些车道
        3. 哪些相位是绿灯相位（跳过黄灯）
        """
        net_path = scene.meta.sumo_net
        self._tls_id = f"J{scene.meta.intersection_id}"
        self._parse_network(net_path)

    def step(self, state: JointState) -> List[ControlAction]:
        """每仿真步调用：容量归一化压力 + 溢出门控 + 动态绿灯时长"""
        self._tls_id = state.tls_id

        # === 改进 2：溢出门控 ===
        overflow_phase = self._check_overflow(state)
        if overflow_phase is not None:
            return [ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=float(overflow_phase),
                reason="overflow gating",
            )]

        # === 改进 1：容量归一化压力 ===
        pressures = self._compute_normalized_pressures(state)

        # 选择压力最大的绿灯相位
        best_phase = max(
            (p for p in self._green_phases),
            key=lambda p: pressures.get(p, 0.0)
        )

        # 如果最佳相位就是当前相位且压力为 0，不操作
        if pressures.get(best_phase, 0.0) == 0.0:
            return []

        # === 改进 3：动态绿灯时长 ===
        avg_pressure = sum(pressures.values()) / max(len(pressures), 1)
        if avg_pressure > 0:
            duration = self.base_green * (pressures[best_phase] / avg_pressure)
            duration = max(self.min_green, min(self.max_green, duration))
        else:
            duration = self.base_green

        actions = []
        # 切换相位（如果不同于当前相位）
        if best_phase != state.current_phase:
            actions.append(ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=float(best_phase),
                reason=f"max pressure phase={best_phase}",
            ))
        # 设置绿灯时长
        actions.append(ControlAction(
            tls_id=state.tls_id,
            action_type="set_phase_duration",
            value=duration,
            reason=f"dynamic green={duration:.1f}s",
        ))
        return actions

    def reset(self) -> None:
        """重置内部状态（保留路网解析结果）"""
        pass

    @property
    def name(self) -> str:
        return "ca_max_pressure"

    def _parse_network(self, net_path: str) -> None:
        """从 net.xml 解析：
        1. 各车道长度 → 计算容量 (length / 7.5)
        2. 各相位对应哪些车道（通过 <connection> 和 tlLogic state）
        3. 哪些相位是绿灯相位（state 中含 G/g 的相位）
        """
        import sumolib
        net = sumolib.net.readNet(net_path)
        # 解析 tlLogic 和 connection 节点
        # 建立 phase_index → [lane_ids] 映射
        # 计算每个 lane 的容量 = length / 7.5
        ...

    def _check_overflow(self, state: JointState) -> Optional[int]:
        """检查是否有车道占用率 > overflow_threshold，返回对应相位"""
        for q in state.queues:
            capacity = self._lane_capacities.get(q.direction, 1.0)
            if capacity > 0 and q.queue_length / capacity > self.overflow_threshold:
                # 找到该方向对应的绿灯相位
                for phase, lanes in self._phase_to_lanes.items():
                    if q.direction in lanes and phase in self._green_phases:
                        return phase
        return None

    def _compute_normalized_pressures(self, state: JointState) -> Dict[int, float]:
        """计算各绿灯相位的容量归一化压力"""
        # 将 state.queues 转为 direction -> queue_length 字典
        queue_map = {q.direction: q.queue_length for q in state.queues}

        pressures: Dict[int, float] = {}
        for phase in self._green_phases:
            p = 0.0
            for lane_id in self._phase_to_lanes.get(phase, []):
                queue = queue_map.get(lane_id, 0.0)
                capacity = self._lane_capacities.get(lane_id, 1.0)
                p += queue / max(capacity, 1.0)
            pressures[phase] = p
        return pressures
```

2. 重点实现 `_parse_network()`（在 `init(scene)` 中调用）：
   - 解析 `scene.meta.sumo_net` 指向的 `demo_N.net.xml` 中的 `<tlLogic>` 和 `<connection>` 节点
   - 建立 phase_index → [lane_ids] 的映射
   - 计算每个 lane 的容量 = length / 7.5

### Day 3（7/22 周二）

**验证算法正确性**
1. 在路口 1 上运行 CA-MP：
   - 创建 `examples/run_ca_max_pressure.py`：
   ```python
   """示例：用 CA-MP 算法跑路口 N"""
   import sys
   from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
   from core.types import Scene, SceneMeta
   from engine.runner import SimulationRunner


   def main():
       intersection_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
       steps = int(sys.argv[2]) if len(sys.argv) > 2 else 3600

       meta = SceneMeta(
           intersection_id=intersection_id,
           name=f"intersection_{intersection_id}",
           sumo_net=f"data/intersection_data/{intersection_id}/sumo工程/demo_{intersection_id}.net.xml",
           sumo_rou=f"data/intersection_data/{intersection_id}/sumo工程/demo_{intersection_id}.rou.xml",
           sumo_flow=f"data/intersection_data/{intersection_id}/sumo工程/demo_{intersection_id}.flow.xml",
           sumo_turn=f"data/intersection_data/{intersection_id}/sumo工程/demo_{intersection_id}.turn.xml",
           sumo_cfg=f"data/intersection_data/{intersection_id}/sumo工程/demo_{intersection_id}.sumocfg",
           timing_xlsx=f"data/intersection_data/{intersection_id}/路口数据/demo_{intersection_id}流量和交叉口配时方案.xlsx",
           map_png=f"data/intersection_data/{intersection_id}/高精地图/demo_{intersection_id}.png",
       )
       scene = Scene(meta=meta)

       algorithm = CAMaxPressureAlgorithm()
       runner = SimulationRunner(scene, algorithm, output_csv=f"output/ca_mp_{intersection_id}.csv")
       results = runner.run(steps)
       print(f"Done: {len(results)} steps, output saved to {runner.output_csv}")


   if __name__ == "__main__":
       main()
   ```
2. 检查：
   - 相位切换是否合理（不会一直卡在同一个相位）
   - 溢出门控是否触发（在高流量时应该触发）
   - 绿灯时长是否在 min~max 范围内
3. 与固定配时对比：CA-MP 的输出 CSV 中平均行程时间应该更低

### Day 4（7/23 周三）

**处理边界情况**
1. 压力全为 0 时（无车）：返回空列表，不切换
2. 多个相位压力相同时：选当前相位（避免频繁切换）
3. 黄灯相位处理：`_green_phases` 只包含绿灯相位，跳过黄灯
4. 步长差异：路口 11-13、15-20 步长 0.1s，决策频率需要调整
   - 方案：每 10 步（= 1s）做一次决策，中间步返回空列表
   - 或者：每步都决策，但 duration 单位是仿真步而非秒
   - 与 TL/IB 确认方案

### Day 5（7/24 周四）

**多路口测试**
1. 在路口 16（5 进口道、24m 短边）上测试：
   - 溢出门控应该频繁触发（24m 只能排 3-4 辆车）
   - 容量归一化应该让短边获得高优先级
2. 在路口 11（0.1s 步长）上测试：
   - 确认决策频率正确
3. 记录各路口的表现差异，为实验组提供调参建议

### Day 6（7/25 周五）

**与 IB 联调**
1. 将 CA-MP 接入 IB 的 SimulationRunner 完整流程
2. 验证完整流程：
   - SimulationRunner.run() → TraCIBridge.get_state() → JointState
   - algorithm.step(state) → List[ControlAction]
   - TraCIBridge.apply_actions(actions) → 信号机执行
3. 验证 CloudPolicy 集成（W2 正式接入，W1 先确认接口兼容）：
   - CloudPolicy.predict(state) 返回参数 → 算法更新 min_green/max_green/base_green
4. 修复联调 bug

### Day 7（7/26 周六）

**Buffer / EWMA 预研**
1. 如果核心算法稳定，开始预研 EWMA 流量预测（W4 正式接入）：
   - EWMA 公式：`predicted = alpha * current + (1 - alpha) * last_predicted`
   - 思考：预测值如何融入压力计算（利用 JointState.flows）
   - 不写代码，只写设计笔记
2. 提交代码给 TL

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `algorithms/ca_max_pressure.py` | 7/22 | 核心逻辑完整（归一化 + 门控 + 动态时长） |
| 2 | `examples/run_ca_max_pressure.py` | 7/22 | 示例入口脚本，路口 1 跑通 |
| 3 | 路口 1 对比数据 | 7/23 | CA-MP vs FixedTime 的输出 CSV 对比 |
| 4 | 路口 16 测试通过 | 7/24 | 溢出门控在短边路口触发 |
| 5 | SimulationRunner 联调通过 | 7/25 | 完整仿真流程跑通 |

---

## 注意事项

- 你是项目创新点的核心实现者——算法正确性是第一优先级
- `_parse_network()` 是最容易出 bug 的地方——不同路口的 tlLogic 结构可能不同
- 不要修改 `algorithms/base.py` 或 `core/types.py`——有问题找 TL
- 溢出门控阈值 0.9 是初始值，不要花时间调优——那是实验组 W4 的事
- W1 不需要实现 EWMA 预测——那是 W4 的任务
- 如果时间不够，优先保证"容量归一化 + 溢出门控"两个改进，"动态时长"可以简化为固定值
- 云端参数调整通过 CloudPolicy.predict() 获取，不再通过 on_cloud_command 回调
