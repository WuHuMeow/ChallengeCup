"""seed 复现性验证（IB W2）：同 seed 两次运行结果一致，异 seed 有差异。"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from algorithms.fixed_time import FixedTimeAlgorithm
from engine.runner import SimulationRunner
from scenes.registry import SceneRegistry

STEPS = 300


def run_once(seed: int, out: Path) -> list[dict]:
    scene = SceneRegistry().get_scene("1")
    runner = SimulationRunner(scene, FixedTimeAlgorithm(), output_csv=out, seed=seed)
    runner.run(STEPS)
    return list(csv.DictReader(open(out, encoding="utf-8")))


def main() -> None:
    out = ROOT / "output" / "seed_check"
    a = run_once(42, out / "a.csv")
    b = run_once(42, out / "b.csv")
    c = run_once(7, out / "c.csv")
    assert a == b, "同 seed 两次运行应完全一致"
    assert a != c, "异 seed 应有差异"
    print(f"OK: seed=42 两次一致（{len(a)} 行），seed=7 有差异")


if __name__ == "__main__":
    main()
