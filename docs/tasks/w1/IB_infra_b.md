# W1 任务书：仿真基础设施 B（IB）

> 周期：7/20（周日）- 7/26（周六）
> 核心目标：实现 SumoSimulator 类，封装 TraCI 接口，产出 V2XMessage 流

---

## 背景

你需要实现 `src/platform/simulator.py`，这是整个系统的底层——所有算法都通过它获取仿真状态、下发信号控制。你的代码是算法组（AA/AB）的前置依赖，W1 结束前必须让单路口能通过 Python 脚本跑起来。

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

**实现 SumoSimulator 核心**
1. 创建 `src/platform/simulator.py`，实现以下类：

```python
import traci
import sumolib
from src.common.messages import V2XMessage, EdgeStatus, SignalAction


class SumoSimulator:
    def __init__(self, config_path: str, gui: bool = False):
        """启动 SUMO 仿真"""
        ...

    def run_step(self) -> list[V2XMessage]:
        """推进一个仿真步，返回所有车辆的 V2X 消息"""
        ...

    def apply_signal(self, tls_id: str, action: SignalAction) -> None:
        """将算法决策应用到信号机"""
        ...

    def get_state(self, intersection_id: int) -> EdgeStatus:
        """获取路口当前状态（排队、相位、压力）"""
        ...

    def get_lane_capacity(self, lane_id: str) -> int:
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

2. 重点实现 `run_step()`：
   - 调用 `traci.simulationStep()`
   - 遍历所有车辆，构造 `V2XMessage` 列表
   - 返回消息列表

3. 重点实现 `get_state()`：
   - 获取各进口道排队长度
   - 获取当前相位
   - 计算各进口道压力（queue_upstream - queue_downstream）

### Day 3（7/22 周二）

**实现 EdgeNode 和 CloudCoordinator 骨架**
1. 创建 `src/platform/edge_node.py`：

```python
from src.common.messages import V2XMessage, EdgeStatus, SignalAction, CloudCommand
from src.algorithm.base import BaseController


class EdgeNode:
    def __init__(self, controller: BaseController, intersection_id: int, tls_id: str):
        self.controller = controller
        self.intersection_id = intersection_id
        self.tls_id = tls_id
        self._last_messages: list[V2XMessage] = []

    def on_v2x_receive(self, msgs: list[V2XMessage]) -> None:
        """接收 V2X 消息，过滤属于本路口的"""
        self._last_messages = msgs

    def decide(self, status: EdgeStatus) -> SignalAction:
        """调用算法插件做决策"""
        self.controller.update(status)
        return self.controller.decide()

    def report_status(self, status: EdgeStatus) -> EdgeStatus:
        """上报状态给云端"""
        return status

    def on_cloud_command(self, cmd: CloudCommand) -> None:
        """接收云端指令，转发给算法"""
        self.controller.on_cloud_command(cmd)
```

2. 创建 `src/platform/cloud.py`：

```python
from src.common.messages import EdgeStatus, CloudCommand


class CloudCoordinator:
    def __init__(self, update_interval: int = 60):
        """update_interval: 每隔多少仿真步下发一次参数"""
        self.update_interval = update_interval
        self._step_count = 0
        self._params = {"min_green": 10.0, "max_green": 60.0, "base_green": 30.0}

    def on_status_receive(self, statuses: list[EdgeStatus]) -> None:
        """接收各路口状态"""
        self._step_count += 1

    def issue_commands(self) -> list[CloudCommand]:
        """周期性下发参数"""
        if self._step_count % self.update_interval != 0:
            return []
        return [CloudCommand(intersection_id=s.intersection_id,
                           strategy_params=self._params.copy(),
                           timestamp=self._step_count)
                for s in self._last_statuses]
```

### Day 4（7/23 周三）

**编写主循环 main.py**
1. 与 TL 协调，完善 `src/platform/main.py`：

```python
import argparse
from src.platform.simulator import SumoSimulator
from src.platform.edge_node import EdgeNode
from src.platform.cloud import CloudCoordinator
from src.algorithm.fixed_time import FixedTimeController
from src.algorithm.ca_max_pressure import CAMaxPressureController


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intersection", type=int, required=True)
    parser.add_argument("--algo", choices=["fixed_time", "ca_maxpressure"], required=True)
    parser.add_argument("--steps", type=int, default=3600)
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()

    config_path = f"intersection_data/{args.intersection}/sumo工程/demo_{args.intersection}.sumocfg"
    sim = SumoSimulator(config_path, gui=args.gui)

    # 根据算法选择 controller
    if args.algo == "fixed_time":
        controller = FixedTimeController(config_path)
    else:
        controller = CAMaxPressureController(config_path)

    edge = EdgeNode(controller, intersection_id=args.intersection, tls_id="J1")
    cloud = CloudCoordinator()

    for step in range(args.steps):
        msgs = sim.run_step()
        edge.on_v2x_receive(msgs)
        status = sim.get_state(args.intersection)
        action = edge.decide(status)
        sim.apply_signal(edge.tls_id, action)
        cloud.on_status_receive([edge.report_status(status)])
        for cmd in cloud.issue_commands():
            edge.on_cloud_command(cmd)

    sim.close()


if __name__ == "__main__":
    main()
```

2. 此时 AA 的 FixedTimeController 可能还没完成——用 placeholder 先跑通框架
3. 验证：`python src/platform/main.py --intersection 1 --algo fixed_time --steps 100` 不报错

### Day 5（7/24 周四）

**联调 + 压力计算**
1. 与 AA 联调：将 FixedTimeController 接入 main.py，跑通 3600 步
2. 完善 `get_state()` 中的压力计算逻辑：
   - 压力 = 上游进口道排队 - 下游出口道排队
   - 需要知道哪些边是进口、哪些是出口（参考 IA 的 edge_mapping.md）
3. 添加 `get_lane_capacity()` 实现：
   - 容量 = lane_length / 7.5（7.5m = 5m 车长 + 2.5m 间距）
   - 这个值后续 CA-MP 算法要用

### Day 6（7/25 周五）

**与 AB 联调**
1. 将 CA-MP 算法接入 main.py
2. 验证：`python src/platform/main.py --intersection 1 --algo ca_maxpressure --steps 3600`
3. 检查输出：stats.xml 中是否有合理的统计数据
4. 修复联调中发现的 bug

### Day 7（7/26 周六）

**Buffer / 文档**
1. 编写 `src/platform/` 模块的内联文档（每个类的 docstring）
2. 如果时间充裕，开始调研 Docker 部署方案（W4 任务前置）
3. 提交代码给 TL 合入

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `src/platform/simulator.py` | 7/22 | SumoSimulator 类完整实现 |
| 2 | `src/platform/edge_node.py` | 7/22 | EdgeNode 类完整实现 |
| 3 | `src/platform/cloud.py` | 7/22 | CloudCoordinator 骨架（W4 再完善） |
| 4 | `src/platform/main.py` | 7/23 | 命令行入口可运行 |
| 5 | 路口 1 联调通过 | 7/25 | 两种算法跑通 3600 步 |

---

## 注意事项

- 你是算法组的前置依赖——W1 结束前 simulator.py 必须可用
- `get_state()` 返回的 EdgeStatus 是算法的唯一输入，字段必须完整
- 不要自己实现算法逻辑——那是 AA/AB 的事
- TraCI 连接失败时要有清晰的错误提示（检查 SUMO_HOME 环境变量）
- 步长差异（1s vs 0.1s）不需要特殊处理——`run_step()` 每次调用就是一个仿真步
