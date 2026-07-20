"""标准算法接口（ABC）。

所有交通管控算法（固定配时、规则自适应、ML 增强）必须实现该接口，
以便 engine/runner.py 和 experiments/runner.py 统一调度。
"""

from abc import ABC, abstractmethod
from typing import List

from core.types import ControlAction, JointState, Scene


class BaseControlAlgorithm(ABC):
    """算法基类，定义云-边协同框架中边缘控制器的标准契约。"""

    @abstractmethod
    def init(self, scene: Scene) -> None:
        """初始化算法，绑定场景信息（路口 ID、信号灯 ID、相位等）。

        在仿真启动前调用一次。
        """
        ...

    @abstractmethod
    def step(self, state: JointState) -> List[ControlAction]:
        """每个仿真步调用一次，根据当前联合状态返回控制动作列表。

        返回空列表表示本步不干预 SUMO（例如固定配时基线）。
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """重置算法内部状态，用于重复运行同一场景或切换场景。"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """算法名称，用于实验报告和对比。"""
        ...
