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
   - `src/__init__.py`
   - `src/common/__init__.py`
   - `src/platform/__init__.py`
   - `src/algorithm/__init__.py`
   - `src/visualization/__init__.py`
6. 首次 commit：`git add -A && git commit -m "init: project skeleton"`

**下午：定义核心接口文件**
1. 编写 `src/common/messages.py`（完整代码见下方）
2. 编写 `src/algorithm/base.py`（完整代码见下方）
3. Commit：`git commit -m "feat: define core interfaces (messages + base controller)"`
4. 将接口文件发给全员（微信群/邮件），通知："接口已冻结，各组基于此开发，不得自行修改"

### Day 2（7/21 周一）

**上午：编写主循环骨架**
1. 编写 `src/platform/main.py` 骨架（能解析命令行参数、启动仿真、调用算法、退出）
2. 此时算法用 placeholder（直接 `traci.trafficlight.setPhase()` 固定相位即可）
3. 验证：`python src/platform/main.py --intersection 1 --algo fixed_time --steps 100` 能跑通

**下午：协调各组**
1. 确认 IA 已开始 SUMO 版本迁移
2. 确认 IB 已开始 SumoSimulator 封装
3. 确认 AA/AB 已开始算法实现
4. 解答各组对接口的疑问（但不得修改接口）

### Day 3（7/22 周二）

1. Review IA 提交的迁移结果（抽查 3 个路口能否跑通）
2. Review IB 提交的 SumoSimulator 初版
3. 如果发现接口设计有缺陷，**唯一修改窗口**：今天之内修改并通知全员
4. 编写 `docs/interface.md`（接口文档，描述每个数据类的字段含义和使用方式）

### Day 4（7/23 周三）

1. **接口冻结截止日**——此后 `messages.py` 和 `base.py` 不再修改
2. 集成测试：将 IB 的 SumoSimulator + AA 的 FixedTimeController 合入主分支
3. 验证：`python src/platform/main.py --intersection 1 --algo fixed_time --steps 3600` 完整跑通
4. Commit：`git commit -m "feat: integrate simulator + fixed-time controller, intersection 1 runs"`

### Day 5（7/24 周四）

1. 集成 AB 的 CAMaxPressureController
2. 验证：`python src/platform/main.py --intersection 1 --algo ca_maxpressure --steps 3600` 完整跑通
3. 对比两次运行的 stats.xml 输出，确认 CA-MP 有输出差异
4. Commit：`git commit -m "feat: integrate CA-MP controller, intersection 1 comparison ready"`

### Day 6（7/25 周五）

1. 合入 EX 的实验配置框架
2. 合入 DA 的报告模板
3. 检查全员代码是否能无冲突合入
4. 编写 W1 周报（发给导师/团队）：完成了什么、下周计划、风险点

### Day 7（7/26 周六）

1. 最终集成测试：确保 `main.py` 在路口 1 上两种算法都能跑
2. 打 tag：`git tag v0.1-w1-complete`
3. 确认 W2 各组任务无阻塞

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `.gitignore` | 7/20 | 排除 `__pycache__/`, `*.pyc`, `experiments/results/`, `.env` |
| 2 | `requirements.txt` | 7/20 | 包含 traci, sumolib, pandas, numpy, matplotlib, pyyaml |
| 3 | `src/common/messages.py` | 7/20 | 4 个 dataclass 定义完整，有类型注解 |
| 4 | `src/algorithm/base.py` | 7/20 | BaseController ABC，含 update/decide/on_cloud_command |
| 5 | `src/platform/main.py` | 7/21 | 命令行入口，支持 --intersection/--algo/--steps 参数 |
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

### src/common/messages.py

```python
from dataclasses import dataclass, field


@dataclass
class V2XMessage:
    """车→边缘 上报消息（模拟 V2X 通信）"""
    vehicle_id: str
    position: tuple[float, float]
    speed: float
    lane_id: str
    timestamp: float


@dataclass
class EdgeStatus:
    """边缘→云 状态回传"""
    intersection_id: int
    queue_lengths: dict[str, int]
    current_phase: str
    pressure: dict[str, float]
    timestamp: float


@dataclass
class CloudCommand:
    """云→边缘 指令下发"""
    intersection_id: int
    strategy_params: dict = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class SignalAction:
    """边缘→信号机 控制指令"""
    next_phase: int
    duration: float = -1.0  # -1 表示使用默认时长
```

### src/algorithm/base.py

```python
from abc import ABC, abstractmethod
from src.common.messages import EdgeStatus, SignalAction, CloudCommand


class BaseController(ABC):
    """标准化算法插件接口（PDF 原文要求）"""

    @abstractmethod
    def update(self, status: EdgeStatus) -> None:
        """接收边缘节点状态，更新内部模型"""
        ...

    @abstractmethod
    def decide(self) -> SignalAction:
        """输出信号控制决策"""
        ...

    def on_cloud_command(self, cmd: CloudCommand) -> None:
        """接收云端参数调整（可选覆写）"""
        pass
```

---

## 注意事项

- 你是唯一有权修改 `messages.py` 和 `base.py` 的人
- 7/23 之后接口冻结，即使发现不完美也只能在 W2 通过向后兼容方式扩展
- 不要替其他人写代码——你的职责是定义接口、集成、review
- 每天花 30 分钟检查各组进度，发现阻塞立即协调
