"""最小可运行示例：路口 1 CA-MP（容量感知最大压力）仿真。

用法: python examples/run_ca_max_pressure.py [intersection_id] [steps]
"""

from __future__ import annotations

import logging
import sys

from ca_mp.algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from ca_mp.engine.runner import SimulationRunner
from ca_mp.scenes.registry import SceneRegistry

logging.basicConfig(level=logging.INFO)


def main() -> None:
    intersection_id = sys.argv[1] if len(sys.argv) > 1 else "1"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 36000

    registry = SceneRegistry()
    scene = registry.get_scene(intersection_id)
    print(f"运行路口 {scene.meta.intersection_id}: {scene.meta.name} (CA-MP)")

    runner = SimulationRunner(scene, CAMaxPressureAlgorithm())
    metrics = runner.run(steps=steps)

    print(f"仿真完成，共记录 {len(metrics)} 条指标快照")
    print(f"CSV 输出: {runner.output_csv}")


if __name__ == "__main__":
    main()
