# W1 任务书：Tech Lead（TL）

> 周期：7/20（周日）- 7/26（周六）
> 核心目标：冻结接口、搭建仓库骨架、确保单路口可运行

---

## 每日任务

### Day 1（7/20 周日）

**上午：初始化仓库**
1. 在项目根目录执行 `git init`
2. 创建 `.gitignore`（内容见下方）
3. 创建 `requirements.txt`（内容见下方）
4. 创建 `README.md`（项目简介 + 目录说明 + 快速开始）
5. 创建所有 `__init__.py` 空文件：
   - `core/__init__.py`
   - `algorithms/__init__.py`
   - `engine/__init__.py`
   - `cloud/__init__.py`
   - `visualization/__init__.py`
6. 首次 commit：`git add -A && git commit -m "init: project skeleton"`

**下午：定义核心接口文件**
1. 编写 `core/types.py`（完整代码见下方）
2. 编写 `algorithms/base.py`（完整代码见下方）
3. Commit：`git commit -m "feat: define core interfaces (types + base algorithm)"`
4. 将接口文件发给全员（微信群/邮件），通知："接口已冻结，各组基于此开发，不得自行修改"

### Day 2（7/21 周一）

**上午：编写主循环骨架**
1. 编写 `engine/runner.py` 骨架（SimulationRunner 类，能启动仿真、调用算法、记录指标、退出）
2. 此时算法用 placeholder（直接 `traci.trafficlight.setPhase()` 固定相位即可）
3. 验证：`python examples/run_fixed_time.py 1` 能跑通

**下午：协调各组**
1. 确认 IA 已开始 SUMO 版本迁移
2. 确认 IB 已开始 TraCI Bridge 封装
3. 确认 AA/AB 已开始算法实现
4. 解答各组对接口的疑问（但不得修改接口）

### Day 3（7/22 周二）

1. Review IA 提交的迁移结果（抽查 3 个路口能否跑通）
2. Review IB 提交的 TraCIBridge 初版
3. 如果发现接口设计有缺陷，**唯一修改窗口**：今天之内修改并通知全员
4. 编写 `docs/interface.md`（接口文档，描述每个数据类的字段含义和使用方式）

### Day 4（7/23 周三）

1. **接口冻结截止日**——此后 `core/types.py` 和 `algorithms/base.py` 不再修改
2. 集成测试：将 IB 的 TraCIBridge + AA 的 FixedTimeAlgorithm 合入主分支
3. 验证：`python examples/run_fixed_time.py 1` 完整跑通 3600 步
4. Commit：`git commit -m "feat: integrate traci bridge + fixed-time algorithm, intersection 1 runs"`

### Day 5（7/24 周四）

1. 集成 AB 的 CAMaxPressureAlgorithm
2. 验证：`python examples/run_ca_max_pressure.py 1` 完整跑通 3600 步
3. 对比两次运行的输出 CSV，确认 CA-MP 有输出差异
4. Commit：`git commit -m "feat: integrate CA-MP algorithm, intersection 1 comparison ready"`

### Day 6（7/25 周五）

1. 合入 EX 的实验配置框架
2. 合入 DA 的报告模板
3. 检查全员代码是否能无冲突合入
4. 编写 W1 周报（发给导师/团队）：完成了什么、下周计划、风险点

### Day 7（7/26 周六）

1. 最终集成测试：确保 `engine/runner.py` 在路口 1 上两种算法都能跑
2. 打 tag：`git tag v0.1-w1-complete`
3. 确认 W2 各组任务无阻塞

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `.gitignore` | 7/20 | 排除 `__pycache__/`, `*.pyc`, `experiments/results/`, `.env` |
| 2 | `requirements.txt` | 7/20 | 包含 traci, sumolib, pandas, numpy, matplotlib, pyyaml |
| 3 | `core/types.py` | 7/20 | 核心数据类定义完整（SceneMeta, Scene, JointState, QueueState, ControlAction, SimulationMetrics），有类型注解 |
| 4 | `algorithms/base.py` | 7/20 | BaseControlAlgorithm ABC，含 init/step/reset/name |
| 5 | `engine/runner.py` | 7/21 | SimulationRunner 类，支持单路口仿真循环 |
| 6 | `docs/interface.md` | 7/22 | 接口文档，每个字段有中文说明 |
| 7 | 集成验证通过 | 7/25 | 路口 1 两种算法跑通 3600 步 |

---

## 关键代码

### .gitignore

```
__pycache__/
*.pyc
*.pyo
.env
experiments/results/
*.egg-info/
dist/
build/
.venv/
venv/
```

### requirements.txt

```
traci>=1.16.0
sumolib>=1.16.0
pandas>=1.5.0
numpy>=1.23.0
matplotlib>=3.6.0
pyyaml>=6.0
openpyxl>=3.0.0
```

### core/types.py

```python
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SceneMeta:
    """路口场景元数据"""
    intersection_id: int
    name: str
    sumo_net: str       # .net.xml 路径
    sumo_rou: str       # .rou.xml 路径
    sumo_flow: str      # .flow.xml 路径
    sumo_turn: str      # .turn.xml 路径
    sumo_cfg: str       # .sumocfg 路径
    timing_xlsx: str    # 配时方案 xlsx 路径
    map_png: str        # 高精地图 png 路径


@dataclass
class Scene:
    """仿真场景：元数据 + 运行配置"""
    meta: SceneMeta
    config: dict = field(default_factory=dict)


@dataclass
class QueueState:
    """单进口道排队状态"""
    direction: str
    queue_length: float
    waiting_time: float
    vehicle_count: int


@dataclass
class JointState:
    """每仿真步传给算法的联合状态"""
    step: int
    timestamp: float
    tls_id: str
    current_phase: int
    current_phase_name: str
    elapsed_phase_time: float
    queues: List[QueueState]
    flows: Dict[str, float]
    detector_values: Dict[str, float]


@dataclass
class ControlAction:
    """算法输出的信号控制指令"""
    tls_id: str
    action_type: str    # "set_phase" / "set_phase_duration" / "set_program"
    value: float
    reason: str = ""


@dataclass
class SimulationMetrics:
    """单步仿真指标"""
    step: int
    avg_queue_length: float
    max_queue_length: float
    avg_delay: float
    total_throughput: int
    avg_travel_time: float
    total_stops: int
    fuel_consumption: float
```

### algorithms/base.py

```python
from abc import ABC, abstractmethod
from typing import List

from core.types import ControlAction, JointState, Scene


class BaseControlAlgorithm(ABC):
    """标准化算法插件接口——所有控制算法必须继承此类"""

    @abstractmethod
    def init(self, scene: Scene) -> None:
        """根据场景元数据初始化算法内部状态（解析路网、配时等）"""
        ...

    @abstractmethod
    def step(self, state: JointState) -> List[ControlAction]:
        """每仿真步调用：接收联合状态，返回控制动作列表"""
        ...

    @abstractmethod
    def reset(self) -> None:
        """重置算法内部状态（用于多次实验）"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """算法名称标识"""
        ...
```

---

## 注意事项

- 你是唯一有权修改 `core/types.py` 和 `algorithms/base.py` 的人
- 7/23 之后接口冻结，即使发现不完美也只能在 W2 通过向后兼容方式扩展
- 不要替其他人写代码——你的职责是定义接口、集成、review
- 每天花 30 分钟检查各组进度，发现阻塞立即协调
