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

REQUIRED = ["tripinfo.xml", "stats.xml", "traj.xml"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="experiments/results", help="结果根目录")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"结果目录不存在: {root}")
        return 1

    missing: list[str] = []
    n_dirs = 0
    for d in root.glob("*/*/*"):  # intersection/algo/seed
        if not d.is_dir():
            continue
        n_dirs += 1
        for f in REQUIRED:
            p = d / f
            if not p.exists() or p.stat().st_size == 0:
                missing.append(f"{d}/{f}")

    print(f"检查目录: {root}（{n_dirs} 个实验目录）")
    print(f"缺失/空文件: {len(missing)}")
    for m in missing[:50]:
        print(" -", m)
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
