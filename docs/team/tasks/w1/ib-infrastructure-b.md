# 仿真基础设施 B（IB） W1 任务书

> 周期：7/20（周日）- 7/26（周六） | 核心目标：实现 TraCIBridge 与 SimulationRunner，封装 TraCI 接口并产出稳定的 JointState 流

## 本周背景

你负责的是整个系统的"地基"：所有算法（AA/AB）都通过 `engine/traci_bridge.py` 获取仿真状态、通过 `engine/runner.py` 驱动主循环。本周需要熟悉 SUMO TraCI Python 接口，并把 `JointState`（来自 `core/types.py`）从仿真器里完整地"采"出来。W1 结束前必须让单路口（路口 1）能通过 Python 脚本跑通 3600 步，否则 AA/AB 的算法没有载体。

需要重点掌握的 TraCI API：

- `traci.start([sumoBinary, "-c", config_path])` — 启动仿真
- `traci.simulationStep()` — 推进一步
- `traci.vehicle.getIDList() / getPosition / getSpeed / getLaneID` — 车辆级状态
- `traci.lane.getLastStepHaltingNumber(lane_id)` — 车道排队数
- `traci.trafficlight.setPhase / setPhaseDuration / getPhase` — 信号控制

## 每日任务

### Day 1（7/20 周日）

- [ ] 阅读 SUMO TraCI 文档（https://sumo.dlr.de/docs/TraCI.html），重点过一遍 vehicle / lane / trafficlight 三个域
- [ ] 设置 `SUMO_HOME` 环境变量，验证 `python -c "import traci; print(traci.__version__)"` 可运行
- [ ] 用路口 1 写一个最简测试脚本：启动仿真 → 跑 100 步 → 每步打印车辆数 → 关闭
- [ ] 用 `sumo-gui -c demo_1.sumocfg` 打开路口 1，对照 net.xml 中的 `<tlLogic>` 确认相位定义

```python
# scripts/traci_smoke.py
import os, sys, traci

cfg = "data/intersection_data/1/sumo工程/demo_1.sumocfg"
traci.start(["sumo", "-c", cfg, "--no-step-log"])
for step in range(100):
    traci.simulationStep()
    vehs = traci.vehicle.getIDList()
    print(f"step={step} vehicles={len(vehs)}")
traci.close()
```

**验证：** `python scripts/traci_smoke.py` 输出 100 行 `step=N vehicles=...`，无异常退出。

### Day 2（7/21 周一）

- [ ] 创建 `engine/traci_bridge.py`，定义 `TraCIBridge` 类骨架（`__init__ / get_state / apply_actions / tick / close`）
- [ ] 实现 `get_state(step) -> JointState`：采集各进口道排队、当前相位索引/名称、检测器流量，组装为 `JointState`
- [ ] 实现 `apply_actions(List[ControlAction])`：按 `action_type` 分发到 `setPhase / setPhaseDuration / setProgram`
- [ ] 实现 `get_lane_capacity(lane_id) = lane_length / 7.5`（5m 车长 + 2.5m 间距，CA-MP 后续要用）
- [ ] TraCI 连接失败时给出清晰报错（提示检查 `SUMO_HOME`）

```python
# engine/traci_bridge.py
import traci
from typing import List
from core.types import ControlAction, JointState, QueueState, Scene


class TraCIBridge:
    """封装 TraCI：启动仿真、采集 JointState、应用 ControlAction。"""

    def __init__(self, scene: Scene, sumo_binary: str = "sumo", gui: bool = False):
        self.scene = scene
        binary = "sumo-gui" if gui else sumo_binary
        traci.start([binary, "-c", scene.meta.sumo_cfg, "--no-step-log"])

    def get_state(self, step: int) -> JointState:
        queues = [QueueState(lane_id=lid,
                             queue_length=traci.lane.getLastStepHaltingNumber(lid),
                             occupancy=traci.lane.getLastStepOccupancy(lid))
                  for lid in self._inbound_lanes()]
        return JointState(step=step, time=self.current_time, queues=queues,
                          phase=traci.trafficlight.getPhase(self._tls_id),
                          flows=self._read_flows())

    def apply_actions(self, actions: List[ControlAction]) -> None:
        for a in actions:
            if a.action_type == "set_phase":
                traci.trafficlight.setPhase(a.tls_id, int(a.value))
            elif a.action_type == "set_phase_duration":
                traci.trafficlight.setPhaseDuration(a.tls_id, float(a.value))
            elif a.action_type == "set_program":
                traci.trafficlight.setProgram(a.tls_id, str(a.value))

    def tick(self) -> None:
        traci.simulationStep()
```

**验证：** `python -c "from engine.traci_bridge import TraCIBridge; print('ok')"` 输出 `ok`，无 ImportError。

### Day 3（7/22 周二）

- [ ] 创建 `engine/runner.py`，实现 `SimulationRunner.run(steps)` 主循环：`tick → get_state → algorithm.step → apply_actions → 记录指标`
- [ ] 创建 `cloud/cloud_policy.py`，实现 `CloudPolicy.predict(state)` 骨架（默认每 60 步下发一次参数）
- [ ] `_tick()` 中组装 `SimulationMetrics` 并返回 dict，便于上层聚合
- [ ] 与 TL 对齐 `BaseControlAlgorithm` 接口（`init / step / reset / name`），确保 runner 调用方式一致

```python
# engine/runner.py
from typing import List
from algorithms.base import BaseControlAlgorithm
from core.types import Scene
from engine.traci_bridge import TraCIBridge


class SimulationRunner:
    """仿真主循环：驱动 TraCIBridge + 算法 + 指标记录。"""

    def __init__(self, scene: Scene, algorithm: BaseControlAlgorithm,
                 sumo_binary: str = "sumo", output_csv: str = "output.csv",
                 snapshot_interval: int = 10):
        self.scene, self.algorithm = scene, algorithm
        self.bridge = TraCIBridge(scene, sumo_binary=sumo_binary)
        self.output_csv, self.snapshot_interval = output_csv, snapshot_interval

    def run(self, steps: int) -> List[dict]:
        self.algorithm.init(self.scene)
        results = []
        for step in range(steps):
            self.bridge.tick()
            state = self.bridge.get_state(step)
            actions = self.algorithm.step(state)
            self.bridge.apply_actions(actions)
            results.append(self._record(step, state))
        self.bridge.close()
        return results
```

**验证：** `python -c "from engine.runner import SimulationRunner; from cloud.cloud_policy import CloudPolicy; print('ok')"` 输出 `ok`。

### Day 4（7/23 周三）

- [ ] 与 TL 协调，创建 `examples/run_fixed_time.py`：从命令行接收 `intersection_id` 与 `steps`
- [ ] 在脚本中根据路口编号拼装 `SceneMeta`（`sumo_net / sumo_rou / sumo_cfg / timing_xlsx` 等路径）
- [ ] AA 的 `FixedTimeAlgorithm` 若未完成，先用 placeholder（返回空动作列表）跑通框架
- [ ] 确认 `output/` 目录存在，CSV 写入路径正确

```python
# examples/run_fixed_time.py
import sys
from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import Scene, SceneMeta
from engine.runner import SimulationRunner


def main():
    iid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 3600
    base = f"data/intersection_data/{iid}"
    meta = SceneMeta(
        intersection_id=iid, name=f"intersection_{iid}",
        sumo_net=f"{base}/sumo工程/demo_{iid}.net.xml",
        sumo_rou=f"{base}/sumo工程/demo_{iid}.rou.xml",
        sumo_cfg=f"{base}/sumo工程/demo_{iid}.sumocfg",
        timing_xlsx=f"{base}/路口数据/demo_{iid}流量和交叉口配时方案.xlsx",
    )
    runner = SimulationRunner(Scene(meta=meta), FixedTimeAlgorithm(),
                              output_csv=f"output/fixed_time_{iid}.csv")
    results = runner.run(steps)
    print(f"Done: {len(results)} steps -> {runner.output_csv}")


if __name__ == "__main__":
    main()
```

**验证：** `python examples/run_fixed_time.py 1 100` 输出 `Done: 100 steps -> output/fixed_time_1.csv`，且 CSV 文件存在。

### Day 5（7/24 周四）

- [ ] 与 AA 联调：把真正的 `FixedTimeAlgorithm` 接入 runner，跑通路口 1 的 3600 步
- [ ] 完善 `get_state()` 的进口道筛选逻辑（参考 IA 的 `docs/reference/edge-mapping.md`，区分进口/出口边）
- [ ] 完善 `flows` 字典采集：从检测器或 lane 流量读取
- [ ] 校对 `get_lane_capacity()` 实现，确保 7.5m 系数有注释说明

```python
# engine/traci_bridge.py（节选：进口道筛选）
def _inbound_lanes(self) -> list[str]:
    """从 edge_mapping 读取本路口的进口边，展开为车道列表。"""
    lanes: list[str] = []
    for edge_id in self.scene.meta.inbound_edges:  # 例如 ["-E1", "-E2", "-E3"]
        lanes.extend(traci.lane.getIDList() and
                     [f"{edge_id}_{i}" for i in range(traci.edge.getLaneNumber(edge_id))])
    return lanes

def get_lane_capacity(self, lane_id: str) -> float:
    """容量 = 车道长度 / 7.5m（5m 车长 + 2.5m 间距）。"""
    return traci.lane.getLength(lane_id) / 7.5
```

**验证：** `python examples/run_fixed_time.py 1 3600` 完整跑完，CSV 行数 ≈ 3600 / snapshot_interval。

### Day 6（7/25 周五）

- [ ] 创建 `examples/run_ca_max_pressure.py`，把 AB 的 CA-MP 算法接入 runner
- [ ] 跑 `python examples/run_ca_max_pressure.py 1 3600`，确认无异常
- [ ] 检查输出 CSV：平均排队、压力值是否在合理范围（不为 0、不发散）
- [ ] 修复联调中发现的 bug（典型：相位索引越界、ControlAction 字段缺失）

```python
# examples/run_ca_max_pressure.py
import sys
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from core.types import Scene, SceneMeta
from engine.runner import SimulationRunner

iid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
steps = int(sys.argv[2]) if len(sys.argv) > 2 else 3600
# SceneMeta 构造同 run_fixed_time.py（提取为公共 helper 更佳）
scene = Scene(meta=build_meta(iid))
runner = SimulationRunner(scene, CAMaxPressureAlgorithm(),
                          output_csv=f"output/ca_mp_{iid}.csv")
print(f"Done: {len(runner.run(steps))} steps")
```

**验证：** `python examples/run_ca_max_pressure.py 1 3600` 退出码 0，`output/ca_mp_1.csv` 中 `avg_queue` 列有非零数值。

### Day 7（7/26 周六）

- [ ] 补全 `engine/` 模块所有类的 docstring（参数、返回、异常）
- [ ] 整理本周代码，提交 PR 给 TL 合入主分支
- [ ] 时间充裕则开始调研 Docker 部署方案（W4 前置）：基础镜像选 `python:3.11-slim` 还是 `eclipse/sumo`
- [ ] 在 `docs/` 下记录本周遇到的 TraCI 坑（连接超时、step 长度差异等）

```python
# engine/traci_bridge.py（docstring 示例）
class TraCIBridge:
    """封装 SUMO TraCI 接口。

    Args:
        scene: 场景对象，提供 sumo_cfg 路径与进口道映射。
        sumo_binary: SUMO 可执行文件名，默认 "sumo"（无 GUI）。
        gui: True 时改用 sumo-gui，便于调试。

    Raises:
        RuntimeError: SUMO_HOME 未设置或 sumocfg 不存在。
    """
```

**验证：** `python -m pydoc engine.traci_bridge.TraCIBridge` 输出完整 docstring，无空字段。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| `engine/traci_bridge.py` | 7/22 | `TraCIBridge` 类完整实现，`get_state` 返回字段完整的 `JointState` |
| `engine/runner.py` | 7/23 | `SimulationRunner.run(steps)` 可驱动算法跑完指定步数 |
| `cloud/cloud_policy.py` | 7/22 | `CloudPolicy.predict` 骨架完成，每 60 步返回一次参数（W4 完善） |
| `examples/run_fixed_time.py` | 7/23 | `python examples/run_fixed_time.py 1 100` 可运行 |
| 路口 1 联调通过 | 7/25 | FixedTime 与 CA-MP 两种算法均能跑通 3600 步 |

## 协作对接

- 与 **TL** 对齐 `core/types.py` 与 `algorithms/base.py` 接口，确认 `SceneMeta` 字段；与 **IA** 对接 `docs/reference/edge-mapping.md`，确保进口道筛选正确。
- 与 **AA / AB** 联调 FixedTime 与 CA-MP 接入 runner，遇到算法侧问题及时反馈。
