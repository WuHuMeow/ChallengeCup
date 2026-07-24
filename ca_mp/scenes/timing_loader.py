"""从 Excel 读取路口信号配时方案。

解析 `demo_X流量和交叉口配时方案.xlsx` 中的 `信号配时方案` 工作表，
输出按时段（早高峰/平峰/晚高峰）组织的 `TimingPlan`。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from core.types import PhaseInfo, TimingPlan

logger = logging.getLogger(__name__)


def parse_timing_excel(xlsx_path: Path, sheet_index: int = 1) -> Dict[str, TimingPlan]:
    """解析 Excel 中的信号配时方案。

    Args:
        xlsx_path: 流量与配时方案 Excel 路径。
        sheet_index: 配时方案所在工作表索引，默认第 2 个工作表（索引 1）。

    Returns:
        时段名称到 TimingPlan 的映射，例如：
        {"早高峰": TimingPlan(...), "平峰": TimingPlan(...), "晚高峰": TimingPlan(...)}。
    """
    df = pd.read_excel(xlsx_path, sheet_name=sheet_index, header=None)

    # 跳过标题行和表头行，从第 3 行开始读取。
    records = df.iloc[2:].reset_index(drop=True)

    periods: Dict[str, List[PhaseInfo]] = {}
    current_period: Optional[str] = None

    for _, row in records.iterrows():
        # 第 0 列非空表示新时段开始。
        raw_period = row.get(0)
        if pd.notna(raw_period):
            current_period = str(raw_period).strip()
            periods[current_period] = []

        if current_period is None:
            continue

        phase_index = row.get(2)
        phase_name = row.get(3)
        green = row.get(4)
        yellow = row.get(5)
        all_red = row.get(6)

        # 跳过不完整行。
        if pd.isna(phase_index) or pd.isna(phase_name) or pd.isna(green):
            continue

        periods[current_period].append(
            PhaseInfo(
                phase_index=int(phase_index) - 1,  # Excel 从 1 开始，内部从 0 开始。
                phase_name=str(phase_name).strip(),
                green_time=float(green),
                yellow_time=float(yellow) if pd.notna(yellow) else 3.0,
                red_time=float(all_red) if pd.notna(all_red) else 2.0,
            )
        )

    result: Dict[str, TimingPlan] = {}
    for period_name, phases in periods.items():
        if not phases:
            continue
        # 周期时长取最后一个相位的累计，或 Excel 中的周期时长列。
        cycle = sum(p.green_time + p.yellow_time + p.red_time for p in phases)
        result[period_name] = TimingPlan(cycle_length=cycle, phases=phases)

    logger.info("从 %s 解析到 %d 个时段配时方案", xlsx_path, len(result))
    return result


def get_default_period_name(available_periods: List[str]) -> str:
    """返回默认使用的时段名称。优先使用早高峰，其次第一个可用时段。"""
    priorities = ["早高峰", "高峰", "平峰"]
    for name in priorities:
        for period in available_periods:
            if name in period:
                return period
    return available_periods[0]
