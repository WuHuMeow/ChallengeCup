"""场景变体生成。

根据基准流量文件生成 1.0x / 1.5x 流量等级变体，
用于对比实验（原始流量 vs 1.5 倍压力）。
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
                TrafficLevel.NORMAL: raw.get("normal", 1.0),
                TrafficLevel.HIGH: raw.get("high", 1.5),
            }
        self.levels = levels

    @staticmethod
    def _scale_tree(root: "ET.Element", factor: float, suffix: str) -> None:
        """就地变换 flow.xml 根元素：缩放 <flow number> 并给 id 加后缀。

        变体经 -a 与 route-files 的 .rou.xml 同时加载：.rou.xml 已含同名
        vType/车辆（如 car、EW_car.0），SUMO 对重复 id 直接报错退出；
        且 -a 先于 route-files 加载，变体不能引用 .rou.xml 里的 vType。
        故给 vType/flow 的 id 及 flow 的 type 引用统一加 suffix，避免冲突。
        """
        vtype_map: Dict[str, str] = {}
        for vtype in root.findall("vType"):
            old_id = vtype.get("id")
            if old_id is not None:
                new_id = old_id + suffix
                vtype_map[old_id] = new_id
                vtype.set("id", new_id)
        for flow in root.findall("flow"):
            flow_id = flow.get("id")
            if flow_id is not None:
                flow.set("id", flow_id + suffix)
            type_attr = flow.get("type")
            if type_attr in vtype_map:
                flow.set("type", vtype_map[type_attr])
            number_attr = flow.get("number")
            if number_attr is not None:
                scaled = max(1, int(round(int(number_attr) * factor)))
                flow.set("number", str(scaled))
            # 若未来使用 probability/vehsPerHour，可在此统一缩放。

    def generate(
        self,
        scene_meta: SceneMeta,
        level: TrafficLevel,
        output_dir: Path,
    ) -> Path:
        """生成指定流量等级的 .flow.xml 变体。

        与 generate_scaled 共用同一变换：缩放 `<flow number>` 并给
        vType/flow 的 id 与 type 引用加 `_x{factor:g}` 后缀；
        仅输出文件名按 TrafficLevel 命名（`..._{level}.flow.xml`）。
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        factor = self.levels[level]

        tree = ET.parse(scene_meta.sumo_flow)
        self._scale_tree(tree.getroot(), factor, f"_x{factor:g}")

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
            for level in self.levels
        }

    def generate_scaled(
        self,
        scene_meta: SceneMeta,
        factor: float,
        output_dir: Path,
    ) -> Path:
        """按任意倍率缩放 .flow.xml 的 <flow number> 属性，返回变体文件路径。

        Args:
            scene_meta: 场景元数据（提供基准 sumo_flow 路径）。
            factor: 流量倍率，必须 > 0（1.0 表示原始流量，调用方应直接跳过）。
            output_dir: 变体输出目录。

        Raises:
            ValueError: factor <= 0。
        """
        if factor <= 0:
            raise ValueError(f"流量倍率必须 > 0，收到: {factor}")
        output_dir.mkdir(parents=True, exist_ok=True)

        tree = ET.parse(scene_meta.sumo_flow)
        self._scale_tree(tree.getroot(), factor, f"_x{factor:g}")

        output_file = output_dir / f"{scene_meta.sumo_flow.stem}_x{factor:g}.flow.xml"
        tree.write(output_file, encoding="utf-8", xml_declaration=True)
        return output_file
