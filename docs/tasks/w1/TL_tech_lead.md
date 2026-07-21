# Tech Lead W1 任务书

> 周期：7/20–7/26 | 核心目标：冻结核心接口，路口 1 固定配时 + CA-MP 跑通 3600 步

## 本周背景

本项目采用云-边-端三层架构：云端（`cloud/cloud_policy.py`）做流量预测，边缘（`algorithms/`）做信号决策，车端/路侧（`engine/traci_bridge.py`）执行控制并反馈状态。三层通过 `core/types.py` 中的共享数据类（JointState、ControlAction、PredictionResult）交互。W1 的核心是把这些接口定死，让 8 个人能并行开发。

## 每日任务

### Day 1（7/20）

- [ ] 初始化仓库：创建 `.gitignore`（排除 `__pycache__/`、`*.pyc`、`.env`、`experiments/results/`、`.venv/`）
- [ ] 创建 `requirements.txt`（traci, sumolib, pandas, numpy, matplotlib, pyyaml, openpyxl）
- [ ] 编写 `core/types.py`：定义全部数据类，全部带类型注解
- [ ] 编写 `algorithms/base.py`：BaseControlAlgorithm ABC
- [ ] 首次 commit 并将接口文件通知全员

`core/types.py` 需要定义的数据类（完整实现见仓库 `core/types.py`）：

```python
@dataclass
class SceneMeta:
    intersection_id: str
    name: str
    sumo_net: Path       # .net.xml 路径
    sumo_rou: Path       # .rou.xml 路径
    sumo_flow: Path      # .flow.xml 路径
    sumo_turn: Path      # .turn.xml 路径
    sumo_cfg: Path       # .sumocfg 路径
    timing_xlsx: Path    # 配时方案 xlsx 路径
    map_png: Optional[Path] = None

@dataclass
class QueueState:
    direction: str       # "north", "south", "east", "west"
    queue_length: float
    waiting_time: float
    vehicle_count: int

@dataclass
class JointState:
    step: int
    timestamp: float
    tls_id: str
    current_phase: int
    current_phase_name: str
    elapsed_phase_time: float
    queues: List[QueueState]
    flows: Dict[str, float]          # 方向 -> vehicles/hour
    detector_values: Dict[str, float] = field(default_factory=dict)

@dataclass
class ControlAction:
    tls_id: str
    action_type: str  # "set_phase" / "set_phase_duration" / "set_program"
    value: Any
    reason: str = ""

@dataclass
class SimulationMetrics:
    step: int
    avg_queue_length: float
    max_queue_length: float
    avg_delay: float
    total_throughput: int
    avg_travel_time: float
    total_stops: int
    fuel_consumption: float
```

`algorithms/base.py` 的标准接口：

```python
class BaseControlAlgorithm(ABC):
    @abstractmethod
    def init(self, scene: Scene) -> None: ...
    @abstractmethod
    def step(self, state: JointState) -> List[ControlAction]: ...
    @abstractmethod
    def reset(self) -> None: ...
    @property
    @abstractmethod
    def name(self) -> str: ...
```

**验证：** `python -c "from core.types import JointState, ControlAction; from algorithms.base import BaseControlAlgorithm; print('接口导入成功')"` → 输出 `接口导入成功`

### Day 2（7/21）

- [ ] 编写 `engine/runner.py` 骨架：SimulationRunner 类
- [ ] 编写 `engine/traci_bridge.py` 骨架：TraCIBridge 类
- [ ] 确认 IA 已开始 SUMO 版本迁移、IB 已开始 TraCI 封装、AA/AB 已开始算法实现
- [ ] 解答各组对接口的疑问

`engine/runner.py` 的核心循环（完整实现见仓库 `engine/runner.py`）：

```python
class SimulationRunner:
    def run(self, steps: int = 3600) -> List[dict]:
        self.bridge.start()
        self.algorithm.init(self.scene)
        for step in range(steps):
            self._tick(step)
        self.bridge.close()

    def _tick(self, step: int) -> None:
        state = self.bridge.get_state()              # SUMO → JointState
        actions = self.algorithm.step(state)         # JointState → List[ControlAction]
        self.bridge.apply_actions(actions)           # ControlAction → SUMO
        self.bridge.step()                           # 推进仿真一步
        if step % self.snapshot_interval == 0:       # 每 60 步记录一次
            metrics = compute_metrics(step, state)
            self.collector.record(step, state, metrics)
```

`engine/traci_bridge.py` 需要封装的方法：

```python
class TraCIBridge:
    def start(self) -> None: ...           # 启动 SUMO 进程
    def get_state(self) -> JointState: ... # 读取当前仿真状态
    def apply_actions(self, actions: List[ControlAction]) -> None: ...  # 写入控制指令
    def step(self) -> None: ...            # 推进仿真一步
    def close(self) -> None: ...           # 关闭 SUMO 进程
```

**验证：** `python -c "from engine.runner import SimulationRunner; print('runner 导入成功')"` → 输出 `runner 导入成功`

### Day 3（7/22）

- [ ] Review IA 提交的迁移结果：抽查路口 1、11、16 能否被 SUMO 正常加载
- [ ] Review IB 提交的 TraCIBridge 初版：确认 `get_state()` 返回的 JointState 字段完整
- [ ] 如发现接口设计缺陷，今天内修改并通知全员（唯一修改窗口）
- [ ] 编写 `docs/interface.md`：每个数据类的字段含义和使用方式

Review 时确认 SceneRegistry 能发现全部路口：

```python
from scenes.registry import SceneRegistry
r = SceneRegistry()
scenes = r.list_scenes()  # 应返回 20 个 SceneMeta
# 检查每个 SceneMeta 的 sumo_cfg 路径是否存在
for meta in scenes:
    assert meta.sumo_cfg.exists(), f"路口 {meta.intersection_id} 缺少 sumocfg"
```

**验证：** `python -c "from scenes.registry import SceneRegistry; r = SceneRegistry(); print(len(r.list_scenes()), '个路口已注册')"` → 输出 `20 个路口已注册`

### Day 4（7/23）

- [ ] 接口冻结：此后 `core/types.py` 和 `algorithms/base.py` 不再修改
- [ ] 集成 IB 的 TraCIBridge + AA 的 FixedTimeAlgorithm 到主分支
- [ ] 在路口 1 上运行固定配时仿真 3600 步
- [ ] 确认输出 CSV 包含 avg_queue_length、avg_delay、total_throughput 列

集成后确认数据流闭环：

```python
# 固定配时算法的 step() 应返回空列表（不干预 SUMO 自带配时）
# 或返回 set_program 动作写入 Excel 配时方案
from algorithms.fixed_time import FixedTimeAlgorithm
from scenes.registry import SceneRegistry

scene = SceneRegistry().get_scene("1")
algo = FixedTimeAlgorithm()
# SimulationRunner 会自动调用 algo.init(scene) 和 algo.step(state)
```

**验证：** `python examples/run_fixed_time.py 1` → 无报错，`output/csv/` 下生成 CSV 文件

### Day 5（7/24）

- [ ] 集成 AB 的 CAMaxPressureAlgorithm
- [ ] 在路口 1 上运行 CA-MP 仿真 3600 步
- [ ] 对比两次运行的输出 CSV，确认 CA-MP 有输出差异（至少 avg_queue_length 不同）
- [ ] 如有集成冲突，协调 AB 修复

CA-MP 集成后的对比方式：

```python
import pandas as pd
ft = pd.read_csv("output/csv/1_fixed_time.csv")
ca = pd.read_csv("output/csv/1_ca_maxpressure.csv")
print(f"FixedTime 平均排队: {ft['avg_queue_length'].mean():.2f}")
print(f"CA-MP 平均排队:    {ca['avg_queue_length'].mean():.2f}")
# 两者应有差异，否则 CA-MP 未生效
```

**验证：** `python examples/run_demo.py 1` → 两种算法均跑通，输出两个不同的 CSV

### Day 6（7/25）

- [ ] 合入 EX 的实验配置框架（`experiments/runner.py`）
- [ ] 合入 DA 的报告模板
- [ ] 检查全员代码能否无冲突合入主分支
- [ ] 编写 W1 周报：完成了什么、下周计划、风险点

合入后确认 experiments/runner.py 的算法注册表：

```python
from experiments.runner import ALGORITHM_MAP
print(list(ALGORITHM_MAP.keys()))
# 应输出 ['fixed_time', 'actuated', 'ca_maxpressure']
```

**验证：** `git log --oneline -10` → 所有组员的 commit 已在主分支

### Day 7（7/26）

- [ ] 最终集成测试：路口 1 上固定配时和 CA-MP 都能跑通 3600 步
- [ ] 打 tag：`git tag v0.1-w1-complete`
- [ ] 确认 W2 各组任务无阻塞（experiments/runner.py 能调用三种算法）

**验证：** `git tag -l "v0.1*"` → 输出 `v0.1-w1-complete`

## 交付物

| 文件 | 截止 | 验收标准 |
|------|------|----------|
| `core/types.py` | Day 1 | 包含 SceneMeta、Scene、JointState、QueueState、ControlAction、PredictionResult、SimulationMetrics，全部有类型注解，`python -c "from core.types import *"` 无报错 |
| `algorithms/base.py` | Day 1 | BaseControlAlgorithm ABC 含 init/step/reset/name，`python -c "from algorithms.base import BaseControlAlgorithm"` 无报错 |
| `engine/runner.py` | Day 2 | SimulationRunner 类可实例化，`run(steps)` 方法签名存在 |
| `docs/interface.md` | Day 3 | 每个数据类字段有中文说明 |
| 集成验证 | Day 5 | 路口 1 两种算法跑通 3600 步，输出 CSV 有数据 |

## 协作对接

- Day 1 将 `core/types.py` 和 `algorithms/base.py` 发给全员，通知接口冻结时间（7/23）
- Day 2-3 与 IA/IB/AA/AB 确认各自开发无阻塞
- Day 6 收集全员代码合入主分支
