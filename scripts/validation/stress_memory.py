"""1.5 倍流量压力测试 + 内存峰值测量（IB W4 Day 1）。

用法: python scripts/validation/stress_memory.py [intersection] [steps]
验收: 完整跑完，tracemalloc 峰值 < 1GB。
"""
import sys
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiments.runner import parse_args, run_single


def main() -> None:
    intersection = sys.argv[1] if len(sys.argv) > 1 else "1"
    steps = sys.argv[2] if len(sys.argv) > 2 else "3600"
    tracemalloc.start()
    args = parse_args([
        "--intersection", intersection, "--steps", steps,
        "--flow-multiplier", "1.5", "--output-dir", str(ROOT / "output" / "stress"),
        "--algorithm", "ca_maxpressure", "--seed", "42",
    ])
    csv_path = run_single(args)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"tracemalloc peak: {peak / 1024 / 1024:.1f} MiB (Python 侧，不含 SUMO 进程)")
    assert peak < 1024**3, "峰值内存超 1GB"
    print(f"csv: {csv_path}")


if __name__ == "__main__":
    main()
