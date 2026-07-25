"""固定配时基线算法。

默认使用 SUMO 路网中自带的信号配时程序；
可通过 `use_excel_timing=true` 从 Excel 读取配时方案并写入 SUMO。
"""

from __future__ import annotations

import logging
from typing import List

from algorithms.base import BaseControlAlgorithm
from core.types import Scene

logger = logging.getLogger(__name__)


try:
    import traci
except ImportError:  # pragma: no cover
    traci = None  # type: ignore


class FixedTimeAlgorithm(BaseControlAlgorithm):
    """固定配时对照组：默认使用 SUMO 默认程序，可选读取 Excel 配时方案。"""

    def __init__(self, use_excel_timing: bool = False) -> None:
        self.use_excel_timing = use_excel_timing
        self.scene: Scene | None = None

    def init(self, scene: Scene) -> None:
        self.scene = scene
        if self.use_excel_timing:
            self._apply_excel_timing(scene)

    def _apply_excel_timing(self, scene: Scene) -> None:
        """读取 Excel 配时方案并写入 SUMO。"""
        if traci is None:
            logger.warning("traci 未安装，无法应用 Excel 配时方案")
            return

        from scenes.timing_loader import get_default_period_name, parse_timing_excel

        try:
            periods = parse_timing_excel(scene.meta.timing_xlsx)
        except Exception as exc:
            logger.warning("读取 Excel 配时失败: %s，将使用默认配时", exc)
            return

        if not periods:
            logger.warning("Excel 中未解析到配时方案，将使用默认配时")
            return

        period_name = get_default_period_name(list(periods.keys()))
        timing = periods[period_name]
        logger.info("使用 Excel 配时方案: %s, 周期 %.0fs", period_name, timing.cycle_length)

        tls_ids = traci.trafficlight.getIDList()
        if not tls_ids:
            logger.warning("场景中无信号灯，跳过 Excel 配时写入")
            return

        tls_id = tls_ids[0]
        logics = traci.trafficlight.getAllProgramLogics(tls_id)
        if not logics:
            logger.warning("无法读取信号灯原始程序")
            return

        original = logics[0]
        original_phases = list(original.phases)

        # 假设原始程序按 "绿-黄-绿-黄-..." 排列，将 Excel 中每个逻辑相位映射到一对绿/黄相位。
        new_phases: List[traci.trafficlight.Phase] = []
        for idx, phase_info in enumerate(timing.phases):
            green_idx = idx * 2
            yellow_idx = idx * 2 + 1
            if green_idx >= len(original_phases):
                logger.warning(
                    "Excel 相位 %d 超出 SUMO 原始相位数量 (%d)，停止映射",
                    idx,
                    len(original_phases),
                )
                break
            green_state = original_phases[green_idx].state
            new_phases.append(
                traci.trafficlight.Phase(phase_info.green_time, green_state)
            )
            if yellow_idx < len(original_phases):
                yellow_state = original_phases[yellow_idx].state
                new_phases.append(
                    traci.trafficlight.Phase(phase_info.yellow_time, yellow_state)
                )

        if not new_phases:
            logger.warning("未生成新相位，使用默认配时")
            return

        new_logic = traci.trafficlight.Logic(
            programID="excel_fixed_time",
            type=0,
            currentPhaseIndex=0,
            phases=new_phases,
        )
        traci.trafficlight.setCompleteRedYellowGreenDefinition(tls_id, new_logic)
        traci.trafficlight.setProgram(tls_id, "excel_fixed_time")
        logger.info("已将 Excel 配时写入信号灯 %s", tls_id)

    def step(self, state) -> List:
        """固定配时不输出控制动作，完全依赖 SUMO 当前程序。"""
        return []

    def reset(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "fixed_time"
