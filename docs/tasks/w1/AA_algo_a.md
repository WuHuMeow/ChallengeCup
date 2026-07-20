# W1 任务书：算法 A（AA）

> 周期：7/20（周日）- 7/26（周六）
> 核心目标：实现 FixedTimeAlgorithm 和 RuleAdaptiveAlgorithm 两个基线算法

---

## 背景

你需要实现两个基线算法，用于与核心创新算法 CA-MP 做对比实验。这两个基线是实验评估的前置条件——没有基线就无法证明 CA-MP 的优越性。

- **FixedTimeAlgorithm**：读取路口原始配时方案（.xlsx），按固定周期切换相位
- **RuleAdaptiveAlgorithm**：基于检测器（排队长度）延长/缩短绿灯，经典自适应方法

---

## 每日任务

### Day 1（7/20 周日）

**熟悉数据与接口**
1. 阅读 TL 发布的 `core/types.py` 和 `algorithms/base.py`，理解接口定义
2. 打开路口 1 的配时文件：`data/intersection_data/1/路口数据/demo_1流量和交叉口配时方案.xlsx`
   - 用 pandas 读取，理解配时方案的结构（周期、各相位绿灯时长、黄灯时长）
3. 打开路口 1 的路网文件：`data/intersection_data/1/sumo工程/demo_1.net.xml`
   - 找到 `<tlLogic>` 节点，理解相位定义（state 字符串含义）
   - 路口 1 有 6 个相位：`GGGGgrrrrGGGGgrrrr`（东西直行+左转）→ 黄灯 → `rrrrrrrrGrrrrrrrrG`（南北）→ 黄灯 → ...
4. 阅读 SUMO 信号灯 API：
   - `traci.trafficlight.getPhase(tls_id)` — 当前相位索引
   - `traci.trafficlight.setPhase(tls_id, index)` — 设置相位
   - `traci.trafficlight.setPhaseDuration(tls_id, seconds)` — 设置当前相位剩余时长
   - `traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id)` — 获取完整配时方案

### Day 2（7/21 周一）

**实现 FixedTimeAlgorithm**
1. 创建 `algorithms/fixed_time.py`：

```python
from typing import List

from algorithms.base import BaseControlAlgorithm
from core.types import ControlAction, JointState, Scene


class FixedTimeAlgorithm(BaseControlAlgorithm):
    """固定配时控制器（基线）：按原始 .sumocfg 中的配时方案运行"""

    def __init__(self):
        self._scene: Scene | None = None

    def init(self, scene: Scene) -> None:
        """
        从 scene.meta 中获取配时方案路径。
        实际上 SUMO 本身就有默认配时，这个算法只是"不做任何干预"。
        """
        self._scene = scene

    def step(self, state: JointState) -> List[ControlAction]:
        """按固定周期切换：不做任何自适应调整，让 SUMO 按默认配时运行"""
        # 返回空列表表示"不操作"，让 SUMO 按 net.xml 中的默认配时运行
        return []

    def reset(self) -> None:
        self._scene = None

    @property
    def name(self) -> str:
        return "fixed_time"
```

2. **关键设计决策**：FixedTimeAlgorithm 有两种实现方式：
   - **方式 A（推荐）**：完全不干预信号机，让 SUMO 按 net.xml 中的默认配时运行。`step()` 返回空列表表示"不操作"。
   - **方式 B**：主动按计划表切换相位，完全接管信号机。
   - 推荐方式 A，因为这就是"传统固定配时"的真实含义——SUMO 默认行为。

3. 验证：将 FixedTimeAlgorithm 接入 IB 的 runner.py，跑路口 1 的 3600 步

### Day 3（7/22 周二）

**实现 RuleAdaptiveAlgorithm**
1. 创建 `algorithms/rule_adaptive.py`：

```python
from typing import List

from algorithms.base import BaseControlAlgorithm
from core.types import ControlAction, JointState, QueueState, Scene


class RuleAdaptiveAlgorithm(BaseControlAlgorithm):
    """感应控制器（基线）：基于排队长度延长/缩短绿灯"""

    def __init__(self,
                 min_green: float = 10.0,
                 max_green: float = 60.0,
                 extension: float = 3.0,
                 gap_threshold: int = 2):
        """
        min_green: 最小绿灯时长
        max_green: 最大绿灯时长
        extension: 每次延长的时长
        gap_threshold: 排队车辆数低于此值时结束绿灯
        """
        self.min_green = min_green
        self.max_green = max_green
        self.extension = extension
        self.gap_threshold = gap_threshold
        self._scene: Scene | None = None
        self._green_phases: List[int] = []  # 非黄灯相位列表
        self._current_phase_index = 0  # 当前在 _green_phases 中的索引

    def init(self, scene: Scene) -> None:
        """从 scene.meta.sumo_net 解析可用相位（跳过黄灯相位）"""
        self._scene = scene
        # 解析 net.xml 中的 <tlLogic> 节点
        # 提取绿灯相位列表 → self._green_phases
        ...

    def step(self, state: JointState) -> List[ControlAction]:
        """感应逻辑：
        1. 绿灯时间 < min_green → 保持当前相位（不操作）
        2. 绿灯时间 > max_green → 强制切换到下一绿灯相位
        3. 当前相位对应进口道排队 < gap_threshold → 切换
        4. 否则 → 延长绿灯（set_phase_duration = extension）
        """
        elapsed = state.elapsed_phase_time

        if elapsed < self.min_green:
            return []  # 保持当前相位

        if elapsed >= self.max_green:
            next_phase = self._next_green_phase(state.current_phase)
            return [ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=float(next_phase),
                reason="max_green reached",
            )]

        # 检查当前相位方向的排队
        current_queue = self._get_phase_queue(state)
        if current_queue < self.gap_threshold:
            next_phase = self._next_green_phase(state.current_phase)
            return [ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=float(next_phase),
                reason="gap out",
            )]

        # 延长绿灯
        return [ControlAction(
            tls_id=state.tls_id,
            action_type="set_phase_duration",
            value=self.extension,
            reason="extension",
        )]

    def reset(self) -> None:
        self._scene = None
        self._current_phase_index = 0

    @property
    def name(self) -> str:
        return "rule_adaptive"

    def _next_green_phase(self, current_phase: int) -> int:
        """切换到下一个绿灯相位（跳过黄灯）"""
        ...

    def _get_phase_queue(self, state: JointState) -> float:
        """获取当前相位对应方向的排队长度"""
        ...
```

2. 感应控制的核心逻辑：
   - 每个绿灯相位有最小/最大绿灯时长
   - 如果当前方向还有车（排队 > 阈值），延长绿灯
   - 如果当前方向没车了（排队 < 阈值），提前切换
   - 这比固定配时"聪明"，但不如 MaxPressure 全局最优

### Day 4（7/23 周三）

**测试与调试**
1. 在路口 1 上测试 FixedTimeAlgorithm：
   - `python examples/run_fixed_time.py 1 3600`
   - 检查输出 CSV 是否合理（有车辆通过、有排队）
2. 在路口 1 上测试 RuleAdaptiveAlgorithm：
   - 创建 `examples/run_rule_adaptive.py`（参照 run_fixed_time.py 结构）
   - 验证感应逻辑：绿灯时长应该在 min_green ~ max_green 之间变化
3. 对比两者输出：感应控制的平均行程时间应该略优于固定配时

### Day 5（7/24 周四）

**适配多路口**
1. 不同路口的相位数量不同（路口 1 有 6 相位，其他可能不同）
2. 确保 FixedTimeAlgorithm 和 RuleAdaptiveAlgorithm 能自动适配：
   - 从 net.xml 动态读取相位方案，不硬编码
   - 处理步长差异：路口 11-13、15-20 步长 0.1s，`elapsed_phase_time` 由 JointState 提供
3. 在路口 11（0.1s 步长）和路口 16（5 进口道）上测试

### Day 6（7/25 周五）

**与 AB 协调**
1. 与 AB 确认 CA-MP 的 `step()` 返回值格式与你的基线一致（都是 `List[ControlAction]`）
2. 确保三种算法在 examples/ 中可以通过不同脚本切换
3. 协助 TL 做集成测试

### Day 7（7/26 周六）

**Buffer / 文档**
1. 为两个基线算法写 docstring（说明算法原理、参数含义）
2. 如果时间充裕，开始阅读 Webster 公式（可选的第三基线）
3. 提交代码给 TL

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `algorithms/fixed_time.py` | 7/21 | 路口 1 跑通 3600 步 |
| 2 | `algorithms/rule_adaptive.py` | 7/22 | 路口 1 跑通，绿灯时长在 min~max 间变化 |
| 3 | 多路口适配 | 7/24 | 路口 11（0.1s）和路口 16（5 进口道）可运行 |
| 4 | examples/ 入口脚本 | 7/25 | `run_fixed_time.py` / `run_rule_adaptive.py` / `run_ca_max_pressure.py` 三个入口 |

---

## 注意事项

- 你的两个基线是实验对比的基础——必须稳定可靠
- FixedTimeAlgorithm 越简单越好——"不做任何事"就是最好的固定配时
- RuleAdaptiveAlgorithm 的参数（min_green/max_green/extension）后续实验组会调优
- 不要修改 `algorithms/base.py` 或 `core/types.py`——有问题找 TL
- 步长差异由 JointState.elapsed_phase_time 自动反映，不需要算法自己计算
