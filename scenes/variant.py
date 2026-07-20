"""场景变体生成。

根据基准流量文件生成 0.5x / 1.0x / 3.0x 等流量等级变体，
用于 ML 训练数据和对比实验。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict

from core.config import get_config
from core.types import SceneMeta, TrafficLevel


class VariantGenerator:
    """基于基准 .flow.xml 生成流量变体。"""

    def __init__(self, levels: Dict[TrafficLevel, float] | None = None) -> None:
        if levels is None:
            cfg = get_config()
            raw = cfg.get("scene.default_traffic_levels", {})
            levels = {
                TrafficLevel.LOW: raw.get("low", 0.5),
                TrafficLevel.NORMAL: raw.get("normal", 1.0),
                TrafficLevel.HIGH: raw.get("high", 3.0),
            }
        self.levels = levels

    def generate(
        self,
        scene_meta: SceneMeta,
        level: TrafficLevel,
        output_dir: Path,
    ) -> Path:
        """生成指定流量等级的 .flow.xml 变体。

        当前实现通过缩放 `<flow>` 标签的 `number` 属性实现；
        后续可扩展为调整 arrival rate、车辆类型比例等。
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        factor = self.levels[level]

        tree = ET.parse(scene_meta.sumo_flow)
        root = tree.getroot()

        for flow in root.findall("flow"):
            number_attr = flow.get("number")
            if number_attr is not None:
                base_number = int(number_attr)
                scaled = max(1, int(round(base_number * factor)))
                flow.set("number", str(scaled))
            # 若未来使用 probability/vehsPerHour，可在此统一缩放。

        output_file = output_dir / f"{scene_meta.sumo_flow.stem}_{level.value}.flow.xml"
        tree.write(output_file, encoding="utf-8", xml_declaration=True)
        return output_file

    def generate_all(
        self,
        scene_meta: SceneMeta,
        output_dir: Path,
    ) -> Dict[TrafficLevel, Path]:
        """为单个路口生成全部流量等级变体。"""
        return {
            level: self.generate(scene_meta, level, output_dir)
            for level in TrafficLevel
        }
