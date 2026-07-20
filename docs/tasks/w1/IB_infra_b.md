# W1 任务书：仿真基础设施 B（IB）

> 周期：7/20（周日）- 7/26（周六）
> 核心目标：实现 TraCIBridge 类和 SimulationRunner，封装 TraCI 接口，产出 JointState 流

---

## 背景

你需要实现 `engine/traci_bridge.py` 和 `engine/runner.py`，这是整个系统的底层——所有算法都通过它获取仿真状态、下发信号控制。你的代码是算法组（AA/AB）的前置依赖，W1 结束前必须让单路口能通过 Python 脚本跑起来。

---

## 每日任务

### Day 1（7/20 周日）

**熟悉 TraCI 接口**
1. 阅读 SUMO TraCI 文档：https://sumo.dlr.de/docs/TraCI.html
2. 重点掌握以下 API：
   - `traci.start([sumoBinary, "-c", config_path])` — 启动仿真
   - `traci.simulationStep()` — 推进一步
   - `traci.vehicle.getIDList()` — 获取所有车辆 ID
   - `traci.vehicle.getPosition(veh_id)` — 车辆位置
   - `traci.vehicle.getSpeed(veh_id)` — 车辆速度
   - `traci.vehicle.getLaneID(veh_id)` — 车辆所在车道
   - `traci.lane.getLastStepHaltingNumber(lane_id)` — 车道排队数
   - `traci.trafficlight.setPhase(tls_id, phase_index)` — 设置信号相位
   - `traci.trafficlight.setPhaseDuration(tls_id, duration)` — 设置相位时长
   - `traci.trafficlight.getPhase(tls_id)` — 获取当前相位
3. 用路口 1 写一个最简测试脚本：
   - 启动仿真 → 跑 100 步 → 每步打印车辆数量 → 关闭
4. 确认能跑通

### Day 2（7/21 周一）

**实现 TraCIBridge 核心**
1. 创建 `engine/traci_bridge.py`，实现以下类：

```python
import traci
import sumolib
from typing import Dict, List

from core.types import ControlAction, JointState, QueueState, Scene


class TraCIBridge:
    """封装 TraCI 接口，负责启动仿真、采集状态、应用控制指令"""

    def __init__(self, scene: Scene, sumo_binary: str = "sumo", gui: bool = False):
        """启动 SUMO 仿真"""
        ...

    def get_state(self, step: int) -> JointState:
        """采集当前仿真步的联合状态（排队、相位、流量、检测器）"""
        ...

    def apply_actions(self, actions: List[ControlAction]) -> None:
        """将算法输出的控制动作列表应用到信号机"""
        ...

    def tick(self) -> None:
        """推进一个仿真步 traci.simulationStep()"""
        ...

    def get_lane_capacity(self, lane_id: str) -> float:
        """计算车道容量 = length / 7.5（平均车长+间距）"""
        ...

    @property
    def current_time(self) -> float:
        """当前仿真时间"""
        ...

    @property
    def running(self) -> bool:
        """仿真是否仍在运行"""
        ...

    def close(self) -> None:
        """关闭仿真"""
        ...
```

2. 重点实现 `get_state()`：
   - 获取各进口道排队长度，构造 `List[QueueState]`
   - 获取当前相位索引和相位名称
   - 获取各检测器/流量数据，填入 `flows` 和 `detector_values`
   - 组装为 `JointState` 返回

3. 重点实现 `apply_actions()`：
   - 遍历 `List[ControlAction]`
   - 根据 `action_type` 调用对应 TraCI API：
     - `"set_phase"` → `traci.trafficlight.setPhase(tls_id, int(value))`
     - `"set_phase_duration"` → `traci.trafficlight.setPhaseDuration(tls_id, value)`
     - `"set_program"` → `traci.trafficlight.setProgram(tls_id, str(value))`

### Day 3（7/22 周二）

**实现 SimulationRunner 和 CloudPolicy 骨架**
1. 创建 `engine/runner.py`：

```python
from typing import List

from algorithms.base import BaseControlAlgorithm
from core.types import ControlAction, JointState, Scene, SimulationMetrics
from engine.traci_bridge import TraCIBridge


class SimulationRunner:
    """仿真主循环：驱动 TraCIBridge + 算法 + 指标记录"""

    def __init__(self, scene: Scene, algorithm: BaseControlAlgorithm,
                 sumo_binary: str = "sumo", output_csv: str = "output.csv",
                 snapshot_interval: int = 10):
        self.scene = scene
        self.algorithm = algorithm
        self.bridge = TraCIBridge(scene, sumo_binary=sumo_binary)
        self.output_csv = output_csv
        self.snapshot_interval = snapshot_interval

    def run(self, steps: int) -> List[dict]:
        """运行 steps 步仿真，返回每步指标列表"""
        self.algorithm.init(self.scene)
        results = []
        for step in range(steps):
            metrics = self._tick(step)
            results.append(metrics)
        self.bridge.close()
        return results

    def _tick(self, step: int) -> dict:
        """单步：获取状态 → 算法决策 → 应用动作 → 记录指标"""
        self.bridge.tick()
        state = self.bridge.get_state(step)
        actions = self.algorithm.step(state)
        self.bridge.apply_actions(actions)
        # 记录 SimulationMetrics 并返回 dict
        ...
```

2. 创建 `cloud/cloud_policy.py`：

```python
from typing import Dict, Optional

from core.types import JointState


class CloudPolicy:
    """云端策略：周期性根据全局状态调整算法参数"""

    def __init__(self, update_interval: int = 60):
        """update_interval: 每隔多少仿真步下发一次参数"""
        self.update_interval = update_interval
        self._step_count = 0
        self._params: Dict[str, float] = {
            "min_green": 10.0,
            "max_green": 60.0,
            "base_green": 30.0,
        }

    def predict(self, state: JointState) -> Optional[Dict[str, float]]:
        """根据当前状态决定是否下发新参数（周期性）"""
        self._step_count += 1
        if self._step_count % self.update_interval != 0:
            return None
        return self._params.copy()
```

### Day 4（7/23 周三）

**编写示例入口脚本**
1. 与 TL 协调，创建 `examples/run_fixed_time.py`：

```python
"""示例：用固定配时算法跑路口 N"""
import sys
from algorithms.fixed_time import FixedTimeAlgorithm
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

    algorithm = FixedTimeAlgorithm()
    runner = SimulationRunner(scene, algorithm, output_csv=f"output/fixed_time_{intersection_id}.csv")
    results = runner.run(steps)
    print(f"Done: {len(results)} steps, output saved to {runner.output_csv}")


if __name__ == "__main__":
    main()
```

2. 此时 AA 的 FixedTimeAlgorithm 可能还没完成——用 placeholder 先跑通框架
3. 验证：`python examples/run_fixed_time.py 1 100` 不报错

### Day 5（7/24 周四）

**联调 + 压力计算**
1. 与 AA 联调：将 FixedTimeAlgorithm 接入 runner.py，跑通 3600 步
2. 完善 `get_state()` 中的排队和流量采集逻辑：
   - 各进口道排队长度 → `QueueState` 列表
   - 各检测器流量 → `flows` 字典
   - 需要知道哪些边是进口、哪些是出口（参考 IA 的 edge_mapping.md）
3. 添加 `get_lane_capacity()` 实现：
   - 容量 = lane_length / 7.5（7.5m = 5m 车长 + 2.5m 间距）
   - 这个值后续 CA-MP 算法要用

### Day 6（7/25 周五）

**与 AB 联调**
1. 创建 `examples/run_ca_max_pressure.py`，将 CA-MP 算法接入 runner
2. 验证：`python examples/run_ca_max_pressure.py 1 3600`
3. 检查输出：CSV 中是否有合理的统计数据
4. 修复联调中发现的 bug

### Day 7（7/26 周六）

**Buffer / 文档**
1. 编写 `engine/` 模块的内联文档（每个类的 docstring）
2. 如果时间充裕，开始调研 Docker 部署方案（W4 任务前置）
3. 提交代码给 TL 合入

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `engine/traci_bridge.py` | 7/22 | TraCIBridge 类完整实现 |
| 2 | `engine/runner.py` | 7/23 | SimulationRunner 类完整实现 |
| 3 | `cloud/cloud_policy.py` | 7/22 | CloudPolicy 骨架（W4 再完善） |
| 4 | `examples/run_fixed_time.py` | 7/23 | 示例入口可运行 |
| 5 | 路口 1 联调通过 | 7/25 | 两种算法跑通 3600 步 |

---

## 注意事项

- 你是算法组的前置依赖——W1 结束前 traci_bridge.py 必须可用
- `get_state()` 返回的 JointState 是算法的唯一输入，字段必须完整
- 不要自己实现算法逻辑——那是 AA/AB 的事
- TraCI 连接失败时要有清晰的错误提示（检查 SUMO_HOME 环境变量）
- 步长差异（1s vs 0.1s）不需要特殊处理——`tick()` 每次调用就是一个仿真步
