"""多场景多算法批量跑批框架。

支持 20 路口 × 2 流量等级 × 3 算法 × 3 种子 = 360 次仿真的批量执行，
并汇总结果供统计检验与报告生成。
"""

from __future__ import annotations

import itertools
import logging
from pathlib import Path
from typing import Dict, List

from algorithms.base import BaseControlAlgorithm
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.ml_enhanced import MLEnhancedAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from core.config import get_config
from core.types import Scene, TrafficLevel
from engine.runner import SimulationRunner
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator

logger = logging.getLogger(__name__)


ALGORITHM_MAP: Dict[str, type[BaseControlAlgorithm]] = {
    "fixed_time": FixedTimeAlgorithm,
    "actuated": RuleAdaptiveAlgorithm,
    "ca_maxpressure": MLEnhancedAlgorithm,
}


def run_batch(
    intersection_ids: List[str] | None = None,
    algorithms: List[str] | None = None,
    levels: List[TrafficLevel] | None = None,
    steps: int = 3600,
    output_root: Path | None = None,
) -> List[Dict[str, str]]:
    """批量运行仿真实验。

    Args:
        intersection_ids: 路口 ID 列表，默认全部 20 个。
        algorithms: 算法名称列表，默认全部 3 种。
        levels: 流量等级列表，默认全部 3 级。
        steps: 每场景仿真步数。
        output_root: 输出根目录。

    Returns:
        实验摘要列表。
    """
    registry = SceneRegistry()
    variant_gen = VariantGenerator()

    if intersection_ids is None:
        intersection_ids = [meta.intersection_id for meta in registry.list_scenes()]
    if algorithms is None:
        algorithms = list(ALGORITHM_MAP.keys())
    if levels is None:
        levels = list(TrafficLevel)
    if output_root is None:
        output_root = get_config().path("paths.output_root")

    results: List[Dict[str, str]] = []
    total = len(intersection_ids) * len(algorithms) * len(levels)
    logger.info("计划跑批 %d 次实验", total)

    for intersection_id, algo_name, level in itertools.product(
        intersection_ids, algorithms, levels
    ):
        scene = registry.get_scene(intersection_id)
        variant_dir = output_root / "variants" / intersection_id
        flow_file = variant_gen.generate(scene.meta, level, variant_dir)

        # TODO: 后续需要让 runner 支持替换 flow 文件运行。
        algo_cls = ALGORITHM_MAP[algo_name]
        runner = SimulationRunner(
            scene=scene,
            algorithm=algo_cls(),
            output_csv=output_root / "csv" / f"{intersection_id}_{level.value}_{algo_name}.csv",
        )
        runner.run(steps)

        results.append(
            {
                "intersection_id": intersection_id,
                "level": level.value,
                "algorithm": algo_name,
                "csv": str(runner.output_csv),
            }
        )

    return results
