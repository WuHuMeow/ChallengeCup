"""多场景多算法批量跑批框架。

支持 20 路口 × 2 流量等级 × 3 算法 × 3 种子 = 360 次仿真的批量执行，
并汇总结果供统计检验与报告生成。
"""

from __future__ import annotations

import argparse
import itertools
import logging
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms.base import BaseControlAlgorithm  # noqa: E402
from algorithms.fixed_time import FixedTimeAlgorithm  # noqa: E402
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm  # noqa: E402
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm  # noqa: E402
from core.config import get_config  # noqa: E402
from core.types import TrafficLevel  # noqa: E402
from engine.runner import SimulationRunner  # noqa: E402
from scenes.registry import SceneRegistry  # noqa: E402
from scenes.variant import VariantGenerator  # noqa: E402

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
            output_csv=(
                output_root / "csv"
                / f"{intersection_id}_{level.value}_{algo_name}_s{seed}.csv"
            ),
            additional_files=additional_files,
            seed=seed,
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数（IB W2：--seed/--flow-multiplier/--output-dir）。

    Args:
        argv: 参数列表；None 时使用 sys.argv。

    Returns:
        解析后的命名空间，含 seed/flow_multiplier/output_dir/intersection/
        steps/algorithm。
    """
    p = argparse.ArgumentParser(description="单次/批量仿真实验入口")
    p.add_argument("--seed", type=int, default=42,
                   help="SUMO 随机种子（传入 traci.start --seed，保证可复现）")
    p.add_argument("--flow-multiplier", type=float, default=1.0,
                   help="流量倍率：1.0=原始流量，1.5=压力测试")
    p.add_argument("--output-dir", type=str, default=None,
                   help="输出根目录（CSV/变体写入其下），默认 config 的 paths.output_root")
    p.add_argument("--intersection", type=str, default="1", help="路口编号 1-20")
    p.add_argument("--steps", type=int, default=3600, help="仿真步数")
    p.add_argument("--algorithm", choices=list(ALGORITHM_MAP), default="fixed_time",
                   help="控制算法")
    return p.parse_args(argv)


def run_single(args: argparse.Namespace) -> Path:
    """按 CLI 参数跑一次仿真，返回输出 CSV 路径。

    Args:
        args: parse_args() 的解析结果。

    Returns:
        输出指标 CSV 路径。

    Raises:
        ValueError: --flow-multiplier <= 0。
    """
    if args.flow_multiplier <= 0:
        raise ValueError(f"--flow-multiplier 必须 > 0，收到: {args.flow_multiplier}")

    registry = SceneRegistry()
    scene = registry.get_scene(args.intersection)
    output_root = (
        Path(args.output_dir) if args.output_dir
        else get_config().path("paths.output_root")
    )

    additional_files: List[Path] = []
    if args.flow_multiplier != 1.0:
        flow_file = VariantGenerator().generate_scaled(
            scene.meta, args.flow_multiplier,
            output_root / "variants" / args.intersection,
        )
        additional_files.append(flow_file)

    runner = SimulationRunner(
        scene=scene,
        algorithm=ALGORITHM_MAP[args.algorithm](),
        output_csv=output_root / "csv"
        / f"{args.intersection}_x{args.flow_multiplier:g}_{args.algorithm}_s{args.seed}.csv",
        step_log_csv=(
            output_root / "logs"
            / f"{args.intersection}_x{args.flow_multiplier:g}"
              f"_{args.algorithm}_s{args.seed}_simulation_log.csv"
        ),
        events_csv=output_root / "logs"
        / f"{args.intersection}_x{args.flow_multiplier:g}_{args.algorithm}_s{args.seed}_events.csv",
        additional_files=additional_files,
        seed=args.seed,
    )
    runner.run(args.steps)
    logger.info("实验完成: %s", runner.output_csv)
    return runner.output_csv


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    csv_path = run_single(parse_args())
    print(f"Done -> {csv_path}")


if __name__ == "__main__":
    main()
