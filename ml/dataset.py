"""从 formal 矩阵的 metrics.csv 遥测构建方向级流量预测数据集。

每个 run 的 metrics.csv 是按采样步的时间序列（flow_* / queue_* 按车道列）。
数据集把每个 (run, 方向) 展开为带滞后特征的样本：

    特征 = [flow_t, flow_lag1, queue_t, queue_lag1, avg_queue_t, phase]
    标签 = 下一采样步的 flow（与云端 600s 参数下发周期同尺度）

首个采样步没有滞后特征、末个采样步没有下一时刻目标，均被丢弃。
提供 matrix.csv 时只保留 matrix_kind == "normal" 的 run，排除扰动 run。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from ml.features import FEATURE_NAMES, build_flow_feature_row


@dataclass(frozen=True)
class RunSeries:
    """一个 run 的遥测序列及溯源信息。"""

    scene_id: str
    algorithm: str
    flow_multiplier: str
    seed: int
    run_id: str
    matrix_kind: str
    path: Path


def iter_run_directories(run_root: Path) -> Iterator[RunSeries]:
    """扫描 output/runs/<...>/runs/i{scene}/{algorithm}/x{flow}/s{seed}/{run_id} 结构。"""
    run_root = Path(run_root)
    if not run_root.is_dir():
        raise FileNotFoundError(f"run root not found: {run_root}")
    for scene_dir in sorted(p for p in run_root.iterdir() if p.is_dir()):
        if not scene_dir.name.startswith("i"):
            continue
        for algorithm_dir in sorted(p for p in scene_dir.iterdir() if p.is_dir()):
            for flow_dir in sorted(p for p in algorithm_dir.iterdir() if p.is_dir()):
                if not flow_dir.name.startswith("x"):
                    continue
                for seed_dir in sorted(p for p in flow_dir.iterdir() if p.is_dir()):
                    if not seed_dir.name.startswith("s"):
                        continue
                    seed = int(seed_dir.name[1:])
                    for run_dir in sorted(p for p in seed_dir.iterdir() if p.is_dir()):
                        if not (run_dir / "metrics.csv").is_file():
                            continue
                        yield RunSeries(
                            scene_id=scene_dir.name[1:],
                            algorithm=algorithm_dir.name,
                            flow_multiplier=flow_dir.name[1:],
                            seed=seed,
                            run_id=run_dir.name,
                            matrix_kind="normal",
                            path=run_dir / "metrics.csv",
                        )


def _load_matrix_kinds(matrix_csv: Path) -> dict[Path, str]:
    """run_dir（规范化后的绝对路径）-> matrix_kind。"""
    kinds: dict[Path, str] = {}
    with Path(matrix_csv).open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            run_dir = Path(row["run_dir"]).resolve()
            kinds[run_dir] = row["matrix_kind"]
    return kinds


def _direction_columns(fieldnames: Iterable[str]) -> dict[str, tuple[str, str]]:
    """返回 {方向: (flow 列名, queue 列名)}，按首次出现顺序。"""
    columns: dict[str, tuple[str, str]] = {}
    for name in fieldnames:
        if name.startswith("flow_"):
            suffix = name[len("flow_"):]
            direction, _, lane = suffix.rpartition("_")
            if not direction:
                continue
            queue_column = f"queue_{suffix}"
            if queue_column not in fieldnames:
                continue
            columns.setdefault(direction, (name, queue_column))
    return columns


def _series_samples(series: RunSeries) -> Iterator[dict]:
    """把单个 run 的时间序列展开为方向级样本（去首尾行）。"""
    with series.path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        direction_columns = _direction_columns(reader.fieldnames or [])
        rows = list(reader)
    if len(rows) < 3 or not direction_columns:
        return

    per_direction: dict[str, list[tuple[float, float]]] = {
        direction: [] for direction in direction_columns
    }
    parsed: list[dict[str, float]] = []
    for row in rows:
        parsed.append({
            "step": float(row["step"]),
            "phase": float(row["current_phase"]),
            "avg_queue_length": float(row["avg_queue_length"] or 0.0),
        })
        for direction, (flow_column, queue_column) in direction_columns.items():
            flow = float(row[flow_column] or 0.0)
            queue = float(row[queue_column] or 0.0)
            per_direction[direction].append((flow, queue))

    for direction, observations in per_direction.items():
        for index in range(1, len(parsed) - 1):
            current = observations[index]
            previous = observations[index - 1]
            target = observations[index + 1][0]
            features = build_flow_feature_row(
                flow_t=current[0],
                flow_lag1=previous[0],
                queue_t=current[1],
                queue_lag1=previous[1],
                avg_queue_t=parsed[index]["avg_queue_length"],
                phase=int(parsed[index]["phase"]),
            )
            yield {
                "scene_id": series.scene_id,
                "algorithm": series.algorithm,
                "flow_multiplier": series.flow_multiplier,
                "seed": series.seed,
                "run_id": series.run_id,
                "matrix_kind": series.matrix_kind,
                "step": int(parsed[index]["step"]),
                "direction": direction,
                "features": features,
                "target": target,
            }


def build_dataset(run_root: Path, matrix_csv: Path | None = None) -> dict:
    """构建方向级流量预测数据集。

    Args:
        run_root: 含 i{scene}/{algorithm}/x{flow}/s{seed}/{run_id}/metrics.csv 的根目录。
        matrix_csv: 可选的 matrix.csv，用于过滤 matrix_kind == "normal"。

    Returns:
        {"feature_names": [...], "rows": [...], "run_count": int}
    """
    kinds: dict[Path, str] | None = (
        _load_matrix_kinds(matrix_csv) if matrix_csv is not None else None
    )
    rows: list[dict] = []
    run_count = 0
    for series in iter_run_directories(run_root):
        if kinds is not None:
            # matrix.csv 的 run_dir 指向 run 目录本身（不含 metrics.csv）。
            kind = kinds.get(series.path.parent.resolve())
            if kind is None or kind != "normal":
                continue
            series = RunSeries(
                scene_id=series.scene_id,
                algorithm=series.algorithm,
                flow_multiplier=series.flow_multiplier,
                seed=series.seed,
                run_id=series.run_id,
                matrix_kind=kind,
                path=series.path,
            )
        run_count += 1
        rows.extend(_series_samples(series))
    return {
        "feature_names": list(FEATURE_NAMES),
        "rows": rows,
        "run_count": run_count,
    }


def split_by_seed(
    dataset: dict,
    calibration_seeds: tuple[int, ...] = (42,),
) -> tuple[list[dict], list[dict]]:
    """按种子分割：校准（训练）种子 vs 其余全部（留出）。

    与 experiments/tuning.py 的校准/留出口径一致，避免同一种子的
    相邻采样步跨训练/测试泄漏。
    """
    train_rows = [
        row for row in dataset["rows"] if row["seed"] in calibration_seeds
    ]
    test_rows = [
        row for row in dataset["rows"] if row["seed"] not in calibration_seeds
    ]
    return train_rows, test_rows
