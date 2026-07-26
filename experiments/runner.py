"""多场景多算法批量跑批框架。

支持 20 路口 × 2 流量等级 × 3 算法 × 3 种子 = 360 次仿真的批量执行，
并汇总结果供统计检验与报告生成。
"""

from __future__ import annotations

import argparse
import itertools
import logging
from pathlib import Path
from typing import Dict, List

from algorithms.base import BaseControlAlgorithm
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from core.config import get_config
from core.run_models import RunRequest, RunResult
from core.types import TrafficLevel
from engine.artifacts import RunArtifacts
from engine.run_service import RunService
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
    steps: int = 36000,
    output_root: Path | None = None,
    run_service: RunService | None = None,
) -> List[RunResult]:
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
    variant_gen = VariantGenerator()

    if intersection_ids is None:
        intersection_ids = [str(index) for index in range(1, 21)]
    if algorithms is None:
        algorithms = list(ALGORITHM_MAP.keys())
    if levels is None:
        levels = [TrafficLevel.NORMAL, TrafficLevel.HIGH]
    if seeds is None:
        seeds = [42, 123, 456]
    if output_root is None:
        output_root = get_config().path("paths.output_root") / "runs"
    service = run_service or RunService(output_root=output_root)

    results: List[RunResult] = []
    total = len(intersection_ids) * len(algorithms) * len(levels) * len(seeds)
    logger.info("计划跑批 %d 次实验", total)

    for intersection_id, algo_name, level, seed in itertools.product(
        intersection_ids, algorithms, levels, seeds
    ):
        results.append(
            service.run_sync(
                RunRequest(
                    intersection_id=intersection_id,
                    algorithm=algo_name,
                    steps=steps,
                    flow_multiplier=variant_gen.levels[level],
                    seed=seed,
                    output_root=output_root,
                )
            )
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
    p.add_argument("--steps", type=int, default=36000, help="仿真步数")
    p.add_argument("--algorithm", choices=list(ALGORITHM_MAP), default="fixed_time",
                   help="控制算法")
    args = p.parse_args(argv)
    try:
        intersection = int(args.intersection)
    except (TypeError, ValueError):
        p.error("--intersection must be an integer in 1..20")
    if not 1 <= intersection <= 20:
        p.error("--intersection must be in 1..20")
    if args.steps <= 0:
        p.error("--steps must be > 0")
    if args.seed < 0:
        p.error("--seed must be >= 0")
    if args.flow_multiplier <= 0:
        p.error("--flow-multiplier must be > 0")
    return args


def build_artifacts(args: argparse.Namespace) -> RunArtifacts:
    """Create the deterministic, run-scoped output layout for CLI arguments."""
    root = (
        Path(args.output_dir)
        if args.output_dir
        else get_config().path("paths.output_root") / "runs"
    )
    return RunArtifacts.create(
        root,
        args.intersection,
        args.algorithm,
        args.flow_multiplier,
        args.seed,
    )


def run_single(
    args: argparse.Namespace,
    run_service: RunService | None = None,
) -> RunResult:
    """按 CLI 参数跑一次仿真，返回输出 CSV 路径。

    Args:
        args: parse_args() 的解析结果。

    Returns:
        输出指标 CSV 路径。

    Raises:
        ValueError: --flow-multiplier <= 0。
    """
    # Keep direct callers safe even when they bypass parse_args().
    if args.flow_multiplier <= 0:
        raise ValueError("--flow-multiplier must be > 0")

    output_root = (
        Path(args.output_dir)
        if args.output_dir
        else get_config().path("paths.output_root") / "runs"
    )
    service = run_service or RunService(output_root=output_root)
    result = service.run_sync(
        RunRequest(
            intersection_id=args.intersection,
            algorithm=args.algorithm,
            steps=args.steps,
            flow_multiplier=args.flow_multiplier,
            seed=args.seed,
            output_root=output_root,
        )
    )
    logger.info("Run finished: %s status=%s", result.run_dir, result.status.value)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    result = run_single(parse_args())
    print(f"Done -> {result.run_dir} [{result.status.value}]")


if __name__ == "__main__":
    main()
