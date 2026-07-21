"""完整链路演示：加载配置 → 注册场景 → 启动仿真 → 调用算法 → 输出结果。

运行方式：
    python examples/run_demo.py [intersection_id] [algorithm]

示例：
    python examples/run_demo.py 1 fixed_time
    python examples/run_demo.py 16 ca_maxpressure

默认使用 MockBridge（无需 SUMO），加 --sumo 参数使用真实仿真。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import get_config
from scenes.registry import SceneRegistry
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ALGORITHM_MAP = {
    "fixed_time": FixedTimeAlgorithm,
    "actuated": RuleAdaptiveAlgorithm,
    "ca_maxpressure": CAMaxPressureAlgorithm,
}


def demo_offline(intersection_id: str, algo_name: str) -> None:
    """离线演示：使用 MockBridge 走通完整调用链，无需 SUMO。"""
    from engine.mock_bridge import MockBridge
    from engine.runner import SimulationRunner

    print("=" * 60)
    print("  XH-202613 车路云协同管控算法平台 - 全链路演示 (Mock)")
    print("=" * 60)

    # 1. 配置加载
    cfg = get_config()
    print(f"\n[1/6] 配置加载: {cfg.get('project.name')}")
    print(f"      运行模式: Mock (无 SUMO)")
    logger.info("场景=%s 算法=%s 模式=Mock", intersection_id, algo_name)

    # 2. 场景注册
    registry = SceneRegistry()
    scenes = registry.list_scenes()
    print(f"\n[2/6] 场景注册: 发现 {len(scenes)} 个路口")
    scene = registry.get_scene(intersection_id)
    print(f"      当前路口: {scene.meta.name}")

    # 3. 算法初始化
    algo_cls = ALGORITHM_MAP[algo_name]
    algorithm = algo_cls()
    print(f"\n[3/6] 算法初始化: {algorithm.name}")

    # 4. 引擎启动 (MockBridge)
    directions = ["E0", "E1", "E2", "E3"]
    bridge = MockBridge(tls_id="tls_0", directions=directions)
    runner = SimulationRunner(scene=scene, algorithm=algorithm, bridge=bridge)
    print(f"\n[4/6] 引擎启动: MockBridge (directions={directions})")

    # 5. 运行仿真 (10 步演示)
    logger.info("阶段=仿真运行 开始")
    metrics = runner.run(steps=10)
    logger.info("阶段=仿真运行 结束")
    print(f"\n[5/6] 仿真运行: 完成 10 步，采集 {len(metrics)} 条指标快照")
    if metrics:
        last = metrics[-1]
        print(f"      最终指标: avg_queue={last['avg_queue_length']:.2f}, "
              f"max_queue={last['max_queue_length']:.2f}, "
              f"avg_delay={last['avg_delay']:.2f}")

    # 6. 输出结果
    print(f"\n[6/6] 链路验证完成")
    print(f"      调用链: Config → SceneRegistry → SimulationRunner(MockBridge)")
    print(f"              → {algorithm.name}.step() → CloudPolicy.predict()")
    print(f"              → MetricsCollector → compute_metrics → CSV")
    print(f"      CSV 输出: {runner.output_csv}")
    print("\n" + "=" * 60)
    print("  如需运行真实仿真，请确保 SUMO 已安装后执行:")
    print(f"  python examples/run_fixed_time.py {intersection_id}")
    print("=" * 60)
    logger.info("运行摘要: 场景=%s 算法=%s 模式=Mock 步数=10 状态=成功",
                intersection_id, algo_name)


def demo_with_sumo(intersection_id: str, algo_name: str) -> None:
    """在线演示：启动 SUMO 运行完整仿真。"""
    from engine.runner import SimulationRunner

    registry = SceneRegistry()
    scene = registry.get_scene(intersection_id)
    algo_cls = ALGORITHM_MAP[algo_name]
    algorithm = algo_cls()

    print(f"运行路口 {intersection_id}，算法: {algo_name}")
    runner = SimulationRunner(scene, algorithm)
    metrics = runner.run(steps=3600)
    print(f"仿真完成，共 {len(metrics)} 条指标快照")
    print(f"CSV 输出: {runner.output_csv}")


def main() -> None:
    intersection_id = sys.argv[1] if len(sys.argv) > 1 else "1"
    algo_name = sys.argv[2] if len(sys.argv) > 2 else "ca_maxpressure"

    if algo_name not in ALGORITHM_MAP:
        print(f"未知算法: {algo_name}，可选: {list(ALGORITHM_MAP.keys())}")
        sys.exit(1)

    use_sumo = "--sumo" in sys.argv
    if use_sumo:
        try:
            import traci  # noqa: F401
            demo_with_sumo(intersection_id, algo_name)
        except ImportError:
            print("SUMO/traci 未安装，回退到 Mock 模式")
            demo_offline(intersection_id, algo_name)
    else:
        demo_offline(intersection_id, algo_name)


if __name__ == "__main__":
    main()
