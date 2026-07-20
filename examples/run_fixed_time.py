"""最小可运行示例：路口 1 固定配时基线仿真。

运行前请确保：
1. 已安装 SUMO 并设置 SUMO_HOME；
2. 已安装 requirements.txt 中的依赖；
3. config/default.yaml 中的 paths.data_root 指向本地 `路口数据/`。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# 兼容直接运行示例脚本
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms.fixed_time import FixedTimeAlgorithm
from core.config import get_config
from engine.runner import SimulationRunner
from scenes.registry import SceneRegistry

logging.basicConfig(level=logging.INFO)


def main() -> None:
    registry = SceneRegistry()
    scenes = registry.list_scenes()
    if not scenes:
        print("未找到任何场景，请检查 config/default.yaml 中的 paths.data_root")
        sys.exit(1)

    # 默认运行路口 1，可通过命令行参数指定
    intersection_id = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene = registry.get_scene(intersection_id)
    print(f"运行路口 {scene.meta.intersection_id}: {scene.meta.name}")
    print(f"SUMO 配置: {scene.meta.sumo_cfg}")

    use_excel = get_config().get("algorithms.fixed_time.use_excel_timing", False)
    algorithm = FixedTimeAlgorithm(use_excel_timing=use_excel)
    mode = "Excel 配时" if use_excel else "SUMO 默认配时"
    print(f"使用模式: {mode}")

    runner = SimulationRunner(scene, algorithm)
    metrics = runner.run(steps=3600)

    print(f"仿真完成，共记录 {len(metrics)} 条指标快照")
    print(f"CSV 输出: {runner.output_csv}")


if __name__ == "__main__":
    main()
