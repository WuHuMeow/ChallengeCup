import json
import xml.etree.ElementTree as ET

import pytest

from core.run_models import VariantSpec
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

    assert len(bundle.additional_files) == 2
    assert bundle.manifest["flow_multiplier"] == 1.5
    assert bundle.manifest["signal_duration_scale"] == 1.1
    assert json.loads(
        (tmp_path / "variant_manifest.json").read_text(encoding="utf-8")
    ) == bundle.manifest
    assert meta.sumo_flow.read_bytes() == original_flow
    assert meta.sumo_net.read_bytes() == original_net

    flow_root = ET.parse(bundle.additional_files[0]).getroot()
    assert flow_root.find("vType").get("sigma") == "0.2"
    assert int(flow_root.find("flow").get("number")) == round(366 * 1.5)

    signal_root = ET.parse(bundle.additional_files[1]).getroot()
    assert signal_root.find("tlLogic").get("programID") == "variant_x1.1"
    phases = signal_root.findall("./tlLogic/phase")
    assert float(phases[0].get("duration")) == pytest.approx(42 * 1.1)
    assert float(phases[1].get("duration")) == 3.0


def test_lane_closure_additional_is_bounded_and_reproducible(tmp_path):
    meta = SceneRegistry().get_scene("1").meta
    spec = VariantSpec(
        closed_lanes=("edge_0_0",),
        closure_begin=600,
        closure_end=1200,
    )

    first = VariantGenerator().generate_bundle(meta, 1.0, spec, tmp_path / "a")
    second = VariantGenerator().generate_bundle(meta, 1.0, spec, tmp_path / "b")

    assert len(first.additional_files) == 3
    assert _normalized_xml(first.additional_files[-1]) == _normalized_xml(
        second.additional_files[-1]
    )
    root = ET.parse(first.additional_files[-1]).getroot()
    interval = root.find("./rerouter/interval")
    closing = interval.find("closingLaneReroute")
    assert interval.get("begin") == "600"
    assert interval.get("end") == "1200"
    assert closing.get("id") == "edge_0_0"
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

    bundle = VariantGenerator().generate_bundle(
        meta,
        1.5,
        VariantSpec(),
        tmp_path / "bundle",
    )

    root = ET.parse(bundle.additional_files[0]).getroot()
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
