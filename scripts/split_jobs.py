"""按路口把实验任务拆分到两台机器（IA W3 Day 3，如有第二台机器）。

实验矩阵：20 路口 × 3 算法 × 2 流量档位 × 3 种子 = 360 组。
机器 A 分 1s 步长路口（1-10、14），机器 B 分 0.1s 步长路口（其余），
两侧计算量大体相当（0.1s 路口单步计算量约为 1s 路口的 10 倍）。

用法：
    python scripts/split_jobs.py            # 打印分配汇总
    python scripts/split_jobs.py --machine a   # 输出 A 机的任务清单（每行一条）
"""

from __future__ import annotations

import argparse

ALGOS = ["fixed_time", "actuated", "ca_maxpressure"]
FLOW_MULTIPLIERS = [1.0, 1.5]
SEEDS = [42, 123, 456]
ONE_SECOND_INTERSECTIONS = set(range(1, 11)) | {14}

JOBS = [
    (n, algo, flow, seed)
    for n in range(1, 21)
    for algo in ALGOS
    for flow in FLOW_MULTIPLIERS
    for seed in SEEDS
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", choices=["a", "b"], help="输出指定机器的任务清单")
    args = parser.parse_args()

    machine_a = [j for j in JOBS if j[0] in ONE_SECOND_INTERSECTIONS]
    machine_b = [j for j in JOBS if j[0] not in ONE_SECOND_INTERSECTIONS]

    if args.machine:
        jobs = machine_a if args.machine == "a" else machine_b
        for n, algo, flow, seed in jobs:
            print(f"--intersection {n} --algo {algo} --flow-multiplier {flow} --seed {seed}")
    else:
        print(f"总任务: {len(JOBS)}（= 20 路口 × 3 算法 × 2 流量 × 3 种子）")
        print(f"A: {len(machine_a)} jobs（1s 步长路口 {sorted(ONE_SECOND_INTERSECTIONS)}）")
        print(f"B: {len(machine_b)} jobs（0.1s 步长路口）")


if __name__ == "__main__":
    main()
