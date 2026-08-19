"""场景变体生成。

根据基准流量文件生成 1.0x / 1.25x 流量等级变体，
用于对比实验（原始流量 vs 1.25 倍高流量）。
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict

from core.config import get_config
from core.run_models import DisturbanceSpec, VariantBundle, VariantSpec
from core.types import SceneMeta, TrafficLevel
from scenes.disturbances import validate_variant, write_disturbance
from scenes.models import SceneManifest


class VariantGenerator:
    """基于基准 .flow.xml 生成流量变体。"""

    def __init__(self, levels: Dict[TrafficLevel, float] | None = None) -> None:
        if levels is None:
            cfg = get_config()
            raw = cfg.get("scene.default_traffic_levels", {})
            levels = {
                TrafficLevel.NORMAL: raw.get("normal", 1.0),
                TrafficLevel.HIGH: raw.get("high", 1.25),
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
            probability_attr = flow.get("probability")
            if probability_attr is not None:
                scaled = min(1.0, float(probability_attr) * factor)
                flow.set("probability", f"{scaled:g}")
            per_hour_attr = flow.get("vehsPerHour")
            if per_hour_attr is not None:
                flow.set("vehsPerHour", f"{float(per_hour_attr) * factor:g}")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _apply_vehicle_overrides(
        root: "ET.Element",
        overrides: dict[str, dict[str, str]],
    ) -> None:
        remaining = set(overrides)
        for vehicle_type in root.findall("vType"):
            vehicle_id = vehicle_type.get("id")
            if vehicle_id not in overrides:
                continue
            for name, value in sorted(overrides[vehicle_id].items()):
                vehicle_type.set(name, value)
            remaining.remove(vehicle_id)
        if remaining:
            names = ", ".join(sorted(remaining))
            raise ValueError(f"unknown vehicle type override: {names}")

    @staticmethod
    def _write_signal_additional(
        scene_meta: SceneMeta,
        scale: float,
        output_file: Path,
    ) -> None:
        source_root = ET.parse(scene_meta.sumo_net).getroot()
        output_root = ET.Element("additional")
        logics = source_root.findall("tlLogic")
        if not logics:
            raise ValueError(f"no tlLogic found in {scene_meta.sumo_net}")
        for source_logic in logics:
            logic_attributes = dict(source_logic.attrib)
            logic_attributes["programID"] = f"variant_x{scale:g}"
            logic = ET.SubElement(output_root, "tlLogic", logic_attributes)
            for source_phase in source_logic.findall("phase"):
                attributes = dict(source_phase.attrib)
                state = attributes.get("state", "")
                if any(value in state for value in "Gg") and not any(
                    value in state for value in "yY"
                ):
                    attributes["duration"] = (
                        f"{float(attributes['duration']) * scale:g}"
                    )
                ET.SubElement(logic, "phase", attributes)
        ET.ElementTree(output_root).write(
            output_file,
            encoding="utf-8",
            xml_declaration=True,
        )

    @staticmethod
    def _write_closure_additional(
        spec: VariantSpec,
        output_file: Path,
    ) -> None:
        lanes = tuple(sorted(set(spec.closed_lanes)))
        edges = tuple(sorted({lane.rsplit("_", 1)[0] for lane in lanes}))
        root = ET.Element("additional")
        rerouter = ET.SubElement(
            root,
            "rerouter",
            {"id": "incident_rerouter", "edges": " ".join(edges)},
        )
        interval = ET.SubElement(
            rerouter,
            "interval",
            {
                "begin": f"{spec.closure_begin:g}",
                "end": f"{spec.closure_end:g}",
            },
        )
        for lane in lanes:
            ET.SubElement(
                interval,
                "closingLaneReroute",
                {"id": lane, "allow": "authority"},
            )
        ET.ElementTree(root).write(
            output_file,
            encoding="utf-8",
            xml_declaration=True,
        )

    @staticmethod
    def _coerce_meta(scene: SceneMeta | SceneManifest) -> SceneMeta:
        """Keep the Task 6 manifest surface usable without breaking runtime metadata."""
        if isinstance(scene, SceneMeta):
            return scene
        files = scene.source_files
        try:
            return SceneMeta(
                scene.scene_id,
                scene.name,
                Path(files["net"]),
                Path(files["route"]),
                Path(files["flow"]),
                Path(files["turn"]),
                Path(files["sumocfg"]),
                Path(files["timing"]),
                description=scene.description,
            )
        except KeyError as exc:
            raise ValueError(f"scene manifest is missing source file: {exc.args[0]}") from exc

    @staticmethod
    def _lane_ids(scene_meta: SceneMeta) -> set[str]:
        return {
            lane.get("id")
            for lane in ET.parse(scene_meta.sumo_net).getroot().findall(".//lane")
            if lane.get("id")
        }

    @staticmethod
    def _validate_disturbance_target(
        disturbance: DisturbanceSpec,
        lane_ids: set[str],
    ) -> None:
        if disturbance.kind in {"construction", "vehicle_failure"}:
            if disturbance.target not in lane_ids:
                raise ValueError(f"disturbance target is not an accessible lane: {disturbance.target}")
        else:
            edge = disturbance.target
            if not any(lane.rsplit("_", 1)[0] == edge for lane in lane_ids):
                raise ValueError(f"disturbance target is not an accessible edge: {edge}")

    def generate_bundle(
        self,
        scene_meta: SceneMeta | SceneManifest,
        flow_multiplier: float,
        spec: VariantSpec | DisturbanceSpec | None,
        output_dir: Path,
    ) -> VariantBundle:
        """Generate a deterministic, source-preserving SUMO variant bundle."""
        scene_meta = self._coerce_meta(scene_meta)
        disturbance = (
            spec
            if isinstance(spec, DisturbanceSpec)
            else getattr(spec, "disturbance", None)
        )
        variant = spec if isinstance(spec, VariantSpec) else VariantSpec()
        if flow_multiplier <= 0:
            raise ValueError(f"flow multiplier must be > 0, got {flow_multiplier}")
        if variant.signal_duration_scale <= 0:
            raise ValueError("signal_duration_scale must be > 0")
        if variant.closed_lanes and variant.closure_end <= variant.closure_begin:
            raise ValueError("closure_end must be greater than closure_begin")
        lane_ids = self._lane_ids(scene_meta)
        if disturbance is not None:
            self._validate_disturbance_target(disturbance, lane_ids)

        output_dir.mkdir(parents=True, exist_ok=True)
        flow_tree = ET.parse(scene_meta.sumo_flow)
        flow_root = flow_tree.getroot()
        self._apply_vehicle_overrides(flow_root, variant.vehicle_type_overrides)
        self._scale_tree(flow_root, flow_multiplier, f"_x{flow_multiplier:g}")
        flow_file = output_dir / f"{scene_meta.sumo_flow.stem}_variant.flow.xml"
        flow_tree.write(flow_file, encoding="utf-8", xml_declaration=True)

        signal_file = output_dir / "signal_program.add.xml"
        self._write_signal_additional(
            scene_meta,
            variant.signal_duration_scale,
            signal_file,
        )
        additional_files = [flow_file, signal_file]

        if variant.closed_lanes:
            closure_file = output_dir / "lane_closure.add.xml"
            self._write_closure_additional(variant, closure_file)
            additional_files.append(closure_file)

        if disturbance is not None:
            disturbance_file = output_dir / f"disturbance_{disturbance.kind}.add.xml"
            write_disturbance(disturbance, disturbance_file)
            additional_files.append(disturbance_file)

        manifest: dict[str, object] = {
            "flow_multiplier": flow_multiplier,
            "vehicle_type_overrides": variant.vehicle_type_overrides,
            "signal_duration_scale": variant.signal_duration_scale,
            "closed_lanes": list(variant.closed_lanes),
            "closure_begin": variant.closure_begin,
            "closure_end": variant.closure_end,
            "parent_sha256": self._sha256(scene_meta.sumo_flow),
            "lane_ids": sorted(lane_ids),
            "sources": {
                "flow": {
                    "path": str(scene_meta.sumo_flow),
                    "sha256": self._sha256(scene_meta.sumo_flow),
                },
                "network": {
                    "path": str(scene_meta.sumo_net),
                    "sha256": self._sha256(scene_meta.sumo_net),
                },
            },
            "additional_files": [path.name for path in additional_files],
        }
        if disturbance is not None:
            manifest["disturbance"] = {
                "kind": disturbance.kind,
                "begin_seconds": disturbance.begin_seconds,
                "end_seconds": disturbance.end_seconds,
                "target": disturbance.target,
                "intensity": disturbance.intensity,
            }
        (output_dir / "variant_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        bundle = VariantBundle(tuple(additional_files), manifest, flow_file)
        issues = validate_variant(bundle)
        if issues:
            for path in [*additional_files, output_dir / "variant_manifest.json"]:
                path.unlink(missing_ok=True)
            raise ValueError("invalid variant bundle: " + "; ".join(issues))
        return bundle

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
