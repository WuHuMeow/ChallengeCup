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
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
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
    "ca_maxpressure": CAMaxPressureAlgorithm,
}


def run_batch(
    intersection_ids: List[str] | None = None,
    algorithms: List[str] | None = None,
    levels: List[TrafficLevel] | None = None,
    seeds: List[int] | None = None,
    steps: int = 3600,
    output_root: Path | None = None,
) -> List[Dict[str, str]]:
    """批量运行仿真实验。

    Args:
        intersection_ids: 路口 ID 列表，默认全部 20 个。
        algorithms: 算法名称列表，默认全部 3 种。
        levels: 流量等级列表，默认全部 3 级。
        seeds: 随机种子列表，默认 [42, 123, 456]。
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
        levels = [TrafficLevel.NORMAL, TrafficLevel.HIGH]
    if seeds is None:
        seeds = [42, 123, 456]
    if output_root is None:
        output_root = get_config().path("paths.output_root")

    results: List[Dict[str, str]] = []
    total = len(intersection_ids) * len(algorithms) * len(levels) * len(seeds)
    logger.info("计划跑批 %d 次实验", total)

    for intersection_id, algo_name, level, seed in itertools.product(
        intersection_ids, algorithms, levels, seeds
    ):
        scene = registry.get_scene(intersection_id)
        variant_dir = output_root / "variants" / intersection_id

        additional_files: List[Path] = []
        if level != TrafficLevel.NORMAL:
            flow_file = variant_gen.generate(scene.meta, level, variant_dir)
            additional_files.append(flow_file)

        algo_cls = ALGORITHM_MAP[algo_name]
        runner = SimulationRunner(
            scene=scene,
            algorithm=algo_cls(),
            output_csv=output_root / "csv" / f"{intersection_id}_{level.value}_{algo_name}_s{seed}.csv",
            additional_files=additional_files,
        )
        runner.run(steps)

        results.append(
            {
                "intersection_id": intersection_id,
                "level": level.value,
                "algorithm": algo_name,
                "seed": str(seed),
                "csv": str(runner.output_csv),
            }
        )

    return results
