"""实验输出文件完整性检查（IA W3 Day 4 / W4 Day 5）。

检查实验结果目录下每个实验目录是否 `tripinfo.xml + stats.xml + traj.xml`
三件齐全且非空，输出缺失/空文件清单。

用法：
    python scripts/check_outputs.py                              # 默认检查 experiments/results
    python scripts/check_outputs.py --root experiments/results/stress_1.5x
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "run_metadata.json",
    "metrics.csv",
    "simulation_log.csv",
    "events.csv",
    "tripinfo.xml",
    "stats.xml",
    "traj.xml",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="experiments/results", help="结果根目录")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_absolute():
        root = ROOT / root
    if not root.exists():
        print(f"结果目录不存在: {root}")
        return 1

    missing: list[str] = []
    run_dirs: set[Path] = set()
    for metadata in root.rglob("run_metadata.json"):
        if not metadata.is_file():
            continue
        run_dir = metadata.parent
        run_dirs.add(run_dir)
        for filename in REQUIRED:
            path = run_dir / filename
            if not path.is_file() or path.stat().st_size == 0:
                missing.append(str(path))

    if not run_dirs:
        print(f"未发现包含 run_metadata.json 的实验目录: {root}")
        return 1

    print(f"检查目录: {root}（{len(run_dirs)} 个实验目录）")
    print(f"缺失/空文件: {len(missing)}")
    for m in missing[:50]:
        print(" -", m)
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
