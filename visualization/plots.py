"""可视化图表生成。

基于 CSV 实验数据绘制对比曲线、热力图和统计图表。
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import pandas as pd


def plot_algorithm_comparison(
    csv_files: List[Path],
    labels: List[str],
    output_file: Path,
    metric: str = "avg_queue_length",
) -> None:
    """对比不同算法在同一指标上的时序曲线。"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 6))

    for csv_file, label in zip(csv_files, labels):
        df = pd.read_csv(csv_file)
        if metric in df.columns and "step" in df.columns:
            plt.plot(df["step"], df[metric], label=label)

    plt.xlabel("Simulation Step")
    plt.ylabel(metric)
    plt.title(f"Algorithm Comparison: {metric}")
    plt.legend()
    plt.grid(True)
    plt.savefig(output_file)
    plt.close()


def plot_heatmap(results_csv: Path, output_file: Path) -> None:
    """绘制路口-算法指标热力图。"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(results_csv)
    # TODO: 成员7 根据实际汇总表格式完善热力图。
    plt.figure(figsize=(8, 6))
    plt.title("Heatmap Placeholder")
    plt.savefig(output_file)
    plt.close()
