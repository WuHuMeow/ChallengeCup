# 如何实现新算法

## 目的

添加一个新的信号控制算法（如改进版 Actuated、强化学习基线等），使其可被实验框架调度。

## 前置条件

- 了解算法标准接口（参见 `docs/architecture/interface.md`）
- 已安装项目依赖：`pip install -e .`

## 操作步骤

### 1. 创建算法文件

在 `ca_mp/algorithms/` 下新建文件，如 `my_algorithm.py`：

```python
from typing import List

from ca_mp.algorithms.base import BaseControlAlgorithm
from ca_mp.core.types import ControlAction, JointState, Scene


class MyAlgorithm(BaseControlAlgorithm):
    def init(self, scene: Scene) -> None:
        self.tls_id = f"J{scene.meta.intersection_id}"

    def step(self, state: JointState) -> List[ControlAction]:
        if state.elapsed_phase_time >= 30.0:
            next_phase = (state.current_phase + 1) % 4
            return [ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=next_phase,
                reason="定时切换",
            )]
        return []

    def reset(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "my_algorithm"
```

### 2. 注册到实验框架

编辑 `ca_mp/experiments/runner.py`，在 `ALGORITHM_MAP` 中添加：

```python
from ca_mp.algorithms.my_algorithm import MyAlgorithm

ALGORITHM_MAP: Dict[str, type[BaseControlAlgorithm]] = {
    "fixed_time": FixedTimeAlgorithm,
    "actuated": RuleAdaptiveAlgorithm,
    "ca_maxpressure": CAMaxPressureAlgorithm,
    "my_algorithm": MyAlgorithm,  # 新增
}
```

### 3. 测试

```bash
# 快速验证
python examples/run_demo.py 1 my_algorithm

# 真实仿真
python examples/run_demo.py 16 my_algorithm --sumo

# CLI 实验入口
python -m ca_mp.experiments.runner --intersection 16 --algorithm my_algorithm --steps 3600
```

### 4. 写单元测试

在 `tests/unit/` 下新建或扩展测试文件：

```python
from ca_mp.algorithms.my_algorithm import MyAlgorithm
from ca_mp.core.types import JointState, Scene

def test_my_algorithm_returns_action():
    algo = MyAlgorithm()
    # 构造 mock state，验证 step() 返回预期 ControlAction
    ...
```

运行：
```bash
python -m pytest tests/unit/ -v -k "my_algorithm"
```

## 接口约束

- `step()` 必须是纯决策，不要在里面启动 SUMO 或写文件
- 返回的 `ControlAction` 由引擎负责写入 SUMO
- 返回空列表 `[]` = 本步不干预
- `reset()` 必须清空所有内部状态

## 常见问题

**Q: 需要云端预测数据怎么办？**
A: 通过构造函数注入 CloudPolicy 对象，在 `step()` 中调用 `self.cloud_policy.predict(state)`。参见 `ca_mp/algorithms/ca_max_pressure.py` 的实现。

**Q: 需要读取路口拓扑（车道数、长度）？**
A: 在 `init(scene)` 中通过 `scene.meta.sumo_net` 获取路网文件路径，用 `sumolib` 解析。
