"""Fail-closed paired statistics and default selection."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
import pandas as pd
from scipy.stats import t as student_t


PAIR_KEYS = ("scene_id", "flow_multiplier", "seed")
HARD_SAFETY_COLUMNS = (
    "collision_count",
    "red_light_count",
    "illegal_transition_count",
)
OBSERVATIONAL_SAFETY_COLUMNS = (
    "harsh_braking_count",
    "teleport_count",
    "potential_conflict_count",
)


@dataclass(frozen=True)
class PairedResult:
    candidate: str
    baseline: str
    differences: tuple[float, ...]
    mean_difference: float
    relative_change: float
    cohen_dz: float | None
    confidence_interval: tuple[float, float]
    improved_unit_count: int
    worst_unit: dict[str, object]
    safety_eligible: bool
    eligible: bool
    flags: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "candidate": self.candidate,
            "baseline": self.baseline,
            "differences": list(self.differences),
            "mean_difference": self.mean_difference,
            "relative_change": self.relative_change,
            "cohen_dz": self.cohen_dz,
            "confidence_interval": list(self.confidence_interval),
            "improved_unit_count": self.improved_unit_count,
            "worst_unit": self.worst_unit,
            "safety_eligible": self.safety_eligible,
            "eligible": self.eligible,
            "flags": list(self.flags),
        }


@dataclass(frozen=True)
class DefaultSelection:
    algorithm: str
    improvement_claim: bool
    results: tuple[PairedResult, ...]


def _normal_rows(frame: pd.DataFrame, algorithm: str) -> pd.DataFrame:
    required = {*PAIR_KEYS, "algorithm", "matrix_kind", "avg_travel_time"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"paired frame missing columns: {missing}")
    return frame[
        (frame["algorithm"] == algorithm) & (frame["matrix_kind"] == "normal")
    ].copy()


def _validate_pairs(rows: pd.DataFrame, label: str) -> None:
    if rows.duplicated(list(PAIR_KEYS), keep=False).any():
        raise ValueError(f"duplicate paired unit for {label}")
    if len(rows) != 120:
        raise ValueError(f"missing paired unit for {label}: expected 120, got {len(rows)}")
    keys = {
        (str(row.scene_id), float(row.flow_multiplier), int(row.seed))
        for row in rows.itertuples()
    }
    expected = {
        (str(scene), flow, seed)
        for scene in range(1, 21)
        for flow in (1.0, 1.25)
        for seed in (42, 43, 44)
    }
    if keys != expected:
        raise ValueError("missing paired unit in frozen 20x2x3 design")


def _strict_zero(value: object) -> bool:
    return (
        isinstance(value, (int, np.integer))
        and not isinstance(value, (bool, np.bool_))
        and int(value) == 0
    )


def _finite_scalar(value: object, label: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{label} must remain finite")
    return numeric


def _finite_array(values: np.ndarray, label: str) -> np.ndarray:
    if not np.isfinite(values).all():
        raise ValueError(f"{label} must remain finite")
    return values


def _safety_eligible(frame: pd.DataFrame, candidate: str) -> bool:
    missing = sorted(set(HARD_SAFETY_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"paired frame missing safety columns: {missing}")
    rows = frame[
        (frame["algorithm"] == candidate)
        & (frame["matrix_kind"].isin(("normal", "disturbance")))
    ]
    # Candidate coverage is 120 normal plus 60 disturbance runs.
    if len(rows) != 180:
        return False
    disturbance = rows[rows["matrix_kind"] == "disturbance"]
    identity_columns = {
        "run_key",
        "scene_id",
        "algorithm",
        "flow_multiplier",
        "seed",
        "matrix_kind",
        "disturbance_kind",
        "disturbance_begin_seconds",
        "disturbance_end_seconds",
        "disturbance_target",
        "disturbance_intensity",
        "duration_seconds",
        "warmup_seconds",
    }
    if not identity_columns.issubset(disturbance.columns):
        return False
    from experiments.matrix import FormalMatrix

    expected = {
        spec.run_key: spec
        for spec in FormalMatrix.disturbance()
        if spec.algorithm == candidate
    }
    if len(disturbance) != 60 or len(expected) != 60:
        return False
    seen: set[str] = set()
    for row in disturbance.itertuples():
        run_key = str(row.run_key)
        spec = expected.get(run_key)
        if spec is None or run_key in seen:
            return False
        seen.add(run_key)
        disturbance_spec = spec.disturbance
        if disturbance_spec is None:
            return False
        try:
            row_seed = float(row.seed)
            matches = (
                str(row.scene_id) == spec.scene_id
                and str(row.algorithm) == spec.algorithm
                and float(row.flow_multiplier) == spec.flow_multiplier
                and math.isfinite(row_seed)
                and row_seed.is_integer()
                and int(row_seed) == spec.seed
                and str(row.matrix_kind) == spec.matrix_kind
                and str(row.disturbance_kind) == disturbance_spec.kind
                and float(row.disturbance_begin_seconds)
                == disturbance_spec.begin_seconds
                and float(row.disturbance_end_seconds) == disturbance_spec.end_seconds
                and str(row.disturbance_target) == disturbance_spec.target
                and float(row.disturbance_intensity) == disturbance_spec.intensity
                and float(row.duration_seconds) == spec.duration_seconds
                and float(row.warmup_seconds) == spec.warmup_seconds
            )
        except (TypeError, ValueError):
            return False
        if not matches:
            return False
    if seen != set(expected):
        return False
    return all(
        _strict_zero(value)
        for column in HARD_SAFETY_COLUMNS
        for value in rows[column].tolist()
    )


def paired_statistics(
    frame: pd.DataFrame,
    candidate: str,
    baseline: str,
) -> PairedResult:
    """Compute the frozen candidate-minus-baseline travel-time contract."""
    candidate_rows = _normal_rows(frame, candidate)
    baseline_rows = _normal_rows(frame, baseline)
    _validate_pairs(candidate_rows, candidate)
    _validate_pairs(baseline_rows, baseline)
    merged = candidate_rows.merge(
        baseline_rows,
        on=list(PAIR_KEYS),
        suffixes=("_candidate", "_baseline"),
        validate="one_to_one",
    ).sort_values(
        list(PAIR_KEYS),
        key=lambda values: pd.to_numeric(values, errors="raise"),
        kind="stable",
    )
    if len(merged) != 120:
        raise ValueError("missing paired unit after exact pairing")

    candidate_values = pd.to_numeric(
        merged["avg_travel_time_candidate"], errors="coerce"
    ).to_numpy(dtype=float)
    baseline_values = pd.to_numeric(
        merged["avg_travel_time_baseline"], errors="coerce"
    ).to_numpy(dtype=float)
    if not np.isfinite(baseline_values).all() or not (baseline_values > 0).all():
        raise ValueError("baseline values must be finite and > 0")
    if not np.isfinite(candidate_values).all():
        raise ValueError("candidate values must be finite")

    try:
        with np.errstate(over="raise", divide="raise", invalid="raise"):
            differences = _finite_array(
                np.subtract(candidate_values, baseline_values),
                "paired differences",
            )
            mean_difference = _finite_scalar(
                differences.mean(), "mean difference"
            )
            relative_values = _finite_array(
                np.divide(differences, baseline_values),
                "relative changes",
            )
            relative_change = _finite_scalar(
                np.mean(relative_values), "relative change"
            )
            sample_sd = _finite_scalar(
                np.std(differences, ddof=1), "sample standard deviation"
            )
    except FloatingPointError as exc:
        raise ValueError("paired statistics must remain finite") from exc
    flags: list[str] = []
    if sample_sd == 0.0:
        confidence_interval = (mean_difference, mean_difference)
        cohen_dz = None
        flags.append("zero_standard_deviation")
    else:
        try:
            margin = _finite_scalar(
                student_t.ppf(0.975, len(differences) - 1)
                * sample_sd
                / math.sqrt(len(differences)),
                "confidence interval margin",
            )
            confidence_interval = (
                _finite_scalar(
                    mean_difference - margin,
                    "confidence interval lower bound",
                ),
                _finite_scalar(
                    mean_difference + margin,
                    "confidence interval upper bound",
                ),
            )
            cohen_dz = _finite_scalar(
                mean_difference / sample_sd,
                "Cohen's dz",
            )
        except (FloatingPointError, OverflowError) as exc:
            raise ValueError("paired statistics must remain finite") from exc

    grouped = merged.assign(difference=differences).groupby(
        ["scene_id", "flow_multiplier"], sort=False
    )["difference"].mean()
    units = [
        (float(value), int(str(scene)), float(load))
        for (scene, load), value in grouped.items()
    ]
    improved_unit_count = sum(value < 0 for value, _, _ in units)
    worst_value, worst_scene, worst_load = max(
        units, key=lambda item: (item[0], -item[1], -item[2])
    )
    del worst_value
    safety_eligible = _safety_eligible(frame, candidate)
    eligible = (
        safety_eligible
        and confidence_interval[1] < 0
        and improved_unit_count >= 21
    )
    return PairedResult(
        candidate=candidate,
        baseline=baseline,
        differences=tuple(float(value) for value in differences),
        mean_difference=mean_difference,
        relative_change=relative_change,
        cohen_dz=cohen_dz,
        confidence_interval=confidence_interval,
        improved_unit_count=improved_unit_count,
        worst_unit={"scene_id": str(worst_scene), "flow_multiplier": worst_load},
        safety_eligible=safety_eligible,
        eligible=eligible,
        flags=tuple(flags),
    )


def select_default(
    frame: pd.DataFrame,
    *,
    candidates: Sequence[str] = (
        "classic_maxpressure",
        "capacity_aware_maxpressure",
    ),
    baseline: str = "fixed_time",
) -> DefaultSelection:
    results = tuple(
        paired_statistics(frame, candidate, baseline) for candidate in candidates
    )
    eligible = [result for result in results if result.eligible]
    if not eligible:
        return DefaultSelection(baseline, False, results)
    winner = min(eligible, key=lambda result: (result.mean_difference, result.candidate))
    return DefaultSelection(winner.candidate, True, results)
