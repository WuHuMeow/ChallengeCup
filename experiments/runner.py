"""多场景多算法批量跑批框架。

支持 20 路口 × 2 流量等级 × 3 算法 × 3 种子 = 360 次仿真的批量执行，
并汇总结果供统计检验与报告生成。
"""

from __future__ import annotations

import argparse
import itertools
import logging
import math
from pathlib import Path
from typing import List

from algorithms.registry import get_algorithm_registry
from core.config import get_config
from core.run_models import RunRequest, RunResult
from core.types import TrafficLevel
from engine.artifacts import RunArtifacts
from engine.run_service import RunService
from experiments.matrix import FORMAL_ALGORITHMS, FORMAL_SEEDS
from scenes.variant import VariantGenerator

logger = logging.getLogger(__name__)


def run_batch(
    intersection_ids: List[str] | None = None,
    algorithms: List[str] | None = None,
    levels: List[TrafficLevel] | None = None,
    seeds: List[int] | None = None,
    steps: int | None = None,
    duration_seconds: float = 3600.0,
    warmup_seconds: float = 600.0,
    output_root: Path | None = None,
    run_service: RunService | None = None,
) -> List[RunResult]:
    """批量运行仿真实验。

    Args:
        intersection_ids: 路口 ID 列表，默认全部 20 个。
        algorithms: 算法名称列表，默认全部 3 种。
        levels: 流量等级列表，默认全部 3 级。
        seeds: 随机种子列表，默认 [42, 43, 44]。
        steps: 显式兼容步数，仅供测试/烟测。
        duration_seconds: 每场景仿真时长（秒）。
        warmup_seconds: 预热时长（秒）。
        output_root: 输出根目录。

    Returns:
        实验摘要列表。
    """
    variant_gen = VariantGenerator()

    if intersection_ids is None:
        intersection_ids = [str(index) for index in range(1, 21)]
    if algorithms is None:
        algorithms = list(FORMAL_ALGORITHMS)
    if levels is None:
        levels = [TrafficLevel.NORMAL, TrafficLevel.HIGH]
    if seeds is None:
        seeds = list(FORMAL_SEEDS)
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
                    duration_seconds=duration_seconds,
                    warmup_seconds=warmup_seconds,
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
                   help="流量倍率：1.0=原始流量，1.25=高流量")
    p.add_argument("--output-dir", type=str, default=None,
                   help="输出根目录（CSV/变体写入其下），默认 config 的 paths.output_root")
    p.add_argument("--intersection", type=str, default="1", help="路口编号 1-20")
    p.add_argument(
        "--steps", type=int, default=None,
        help="显式兼容步数（仅测试/烟测；正式请求使用秒）",
    )
    p.add_argument(
        "--duration-seconds", type=float,
        default=get_config().get("simulation.duration_seconds", 3600.0),
        help="仿真时长（秒）",
    )
    p.add_argument(
        "--warmup-seconds", type=float,
        default=get_config().get("simulation.warmup_seconds", 600.0),
        help="预热时长（秒）",
    )
    p.add_argument(
        "--algorithm",
        choices=[spec.key for spec in get_algorithm_registry().list()],
        default="fixed_time",
        help="控制算法")
    args = p.parse_args(argv)
    try:
        intersection = int(args.intersection)
    except (TypeError, ValueError):
        p.error("--intersection must be an integer in 1..20")
    if not 1 <= intersection <= 20:
        p.error("--intersection must be in 1..20")
    if args.steps is not None and args.steps <= 0:
        p.error("--steps must be > 0")
    if not math.isfinite(args.duration_seconds) or args.duration_seconds <= 0:
        p.error("--duration-seconds must be > 0")
    if (
        not math.isfinite(args.warmup_seconds)
        or args.warmup_seconds < 0
        or args.warmup_seconds >= args.duration_seconds
    ):
        p.error("--warmup-seconds must be >= 0 and less than duration")
    if args.seed < 0:
        p.error("--seed must be >= 0")
    if not math.isfinite(args.flow_multiplier) or args.flow_multiplier <= 0:
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
        get_algorithm_registry().get(args.algorithm).key,
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
            duration_seconds=args.duration_seconds,
            warmup_seconds=args.warmup_seconds,
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
