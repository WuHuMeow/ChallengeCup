import json
import xml.etree.ElementTree as ET

import pytest

from core.run_models import VariantSpec
from core.types import TrafficLevel
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator


def _normalized_xml(path):
    root = ET.parse(path).getroot()
    return ET.tostring(root, encoding="unicode")


def test_bundle_scales_flow_vehicle_and_signal_without_touching_source(tmp_path):
    meta = SceneRegistry().get_scene("1").meta
    original_flow = meta.sumo_flow.read_bytes()
    original_net = meta.sumo_net.read_bytes()

    bundle = VariantGenerator().generate_bundle(
        meta,
        1.5,
        VariantSpec(
            vehicle_type_overrides={"car": {"sigma": "0.2"}},
            signal_duration_scale=1.1,
        ),
        tmp_path,
    )

    assert len(bundle.additional_files) == 1
    assert bundle.manifest["flow_multiplier"] == 1.5
    assert bundle.manifest["signal_duration_scale"] == 1.1
    assert json.loads(
        (tmp_path / "variant_manifest.json").read_text(encoding="utf-8")
    ) == bundle.manifest
    assert meta.sumo_flow.read_bytes() == original_flow
    assert meta.sumo_net.read_bytes() == original_net

    flow_root = ET.parse(bundle.flow_file).getroot()
    assert flow_root.find("vType").get("sigma") == "0.2"
    assert int(flow_root.find("flow").get("number")) == round(366 * 1.5)

    signal_root = ET.parse(bundle.additional_files[0]).getroot()
    assert signal_root.find("tlLogic").get("programID") == "variant_x1.1"
    phases = signal_root.findall("./tlLogic/phase")
    assert float(phases[0].get("duration")) == pytest.approx(35 * 1.1)
    assert float(phases[1].get("duration")) == 3.0


def test_runtime_config_preserves_scene_identity_and_parent_output(tmp_path):
    meta = SceneRegistry().get_scene("11").meta
    original_config = meta.sumo_cfg.read_bytes()
    source_output = ET.tostring(
        ET.parse(meta.sumo_cfg).getroot().find("output"),
        encoding="unicode",
    )

    bundle = VariantGenerator().generate_bundle(meta, 1.0, None, tmp_path)

    derived_output_node = ET.parse(bundle.sumo_cfg).getroot().find("output")
    assert derived_output_node is not None
    derived_output = ET.tostring(derived_output_node, encoding="unicode")
    assert bundle.sumo_cfg.name == "demo_11_variant.sumocfg"
    assert derived_output == source_output
    assert meta.sumo_cfg.read_bytes() == original_config


def test_variant_generator_uses_seconds_first_high_level_fallback(monkeypatch):
    from scenes import variant

    class EmptyConfig:
        def get(self, key, default=None):
            return {}

    monkeypatch.setattr(variant, "get_config", lambda: EmptyConfig())

    generator = variant.VariantGenerator()

    assert generator.levels[TrafficLevel.NORMAL] == 1.0
    assert generator.levels[TrafficLevel.HIGH] == 1.25


def test_lane_closure_additional_is_bounded_and_reproducible(tmp_path):
    meta = SceneRegistry().get_scene("1").meta
    spec = VariantSpec(
        closed_lanes=("E0_0",),
        closure_begin=600,
        closure_end=1200,
    )

    first = VariantGenerator().generate_bundle(meta, 1.0, spec, tmp_path / "a")
    second = VariantGenerator().generate_bundle(meta, 1.0, spec, tmp_path / "b")

    assert len(first.additional_files) == 2
    assert _normalized_xml(first.additional_files[-1]) == _normalized_xml(
        second.additional_files[-1]
    )
    root = ET.parse(first.additional_files[-1]).getroot()
    interval = root.find("./rerouter/interval")
    closing = interval.find("closingLaneReroute")
    assert interval.get("begin") == "600"
    assert interval.get("end") == "1200"
    assert closing.get("id") == "E0_0"
    assert closing.get("allow") == "authority"


def test_bundle_scales_probability_and_vehicles_per_hour(tmp_path):
    source = tmp_path / "source.flow.xml"
    source.write_text(
        "<routes><vType id='car'/>"
        "<flow id='a' type='car' probability='0.2'/>"
        "<flow id='b' type='car' vehsPerHour='100'/></routes>",
        encoding="utf-8",
    )
    meta = SceneRegistry().get_scene("1").meta
    meta.sumo_flow = source

    output = VariantGenerator().generate_scaled(meta, 1.5, tmp_path / "bundle")

    root = ET.parse(output).getroot()
    flows = root.findall("flow")
    assert float(flows[0].get("probability")) == pytest.approx(0.3)
    assert float(flows[1].get("vehsPerHour")) == pytest.approx(150.0)


def test_bundle_rejects_invalid_closure_window(tmp_path):
    meta = SceneRegistry().get_scene("1").meta

    with pytest.raises(ValueError, match="closure_end"):
        VariantGenerator().generate_bundle(
            meta,
            1.0,
            VariantSpec(
                closed_lanes=("edge_0_0",),
                closure_begin=1200,
                closure_end=600,
            ),
            tmp_path,
        )


def test_variant_signal_program_preserves_all_red_clearance(tmp_path):
    meta = SceneRegistry().get_scene("1").meta
    bundle = VariantGenerator().generate_bundle(
        meta, 1.0, VariantSpec(signal_duration_scale=1.0), tmp_path
    )
    signal_root = ET.parse(bundle.additional_files[0]).getroot()
    phases = signal_root.findall("./tlLogic/phase")
    greens = [
        i for i, p in enumerate(phases)
        if "G" in p.get("state") and "y" not in p.get("state")
    ]
    assert len(greens) >= 2
    for a, b in zip(greens, greens[1:]):
        between = phases[a + 1 : b]
        all_red = [
            p for p in between
            if p.get("state") and set(p.get("state")) <= {"r"}
        ]
        assert all_red, f"no all-red clearance between green phases {a}->{b}"
        assert sum(float(p.get("duration")) for p in all_red) >= 1.0
