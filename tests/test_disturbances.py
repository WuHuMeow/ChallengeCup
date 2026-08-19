from __future__ import annotations

import hashlib
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

from api.models import DisturbanceSpecModel
from core.run_models import DisturbanceSpec, RunRequest, VariantSpec
from core.types import SceneMeta
from scenes.disturbances import validate_variant
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator
from engine.traci_bridge import TraCIBridge


def _scene(tmp_path: Path) -> SceneMeta:
    base = SceneRegistry().get_scene("1").meta
    flow = tmp_path / "demo.flow.xml"
    flow.write_bytes(base.sumo_flow.read_bytes())
    return replace(base, sumo_flow=flow)


def test_disturbance_spec_validates_and_api_round_trips():
    domain = DisturbanceSpec("construction", 10, 20, "E0_0", 1.0)
    model = DisturbanceSpecModel.model_validate(domain.__dict__)
    assert model.to_domain() == domain
    with pytest.raises(ValueError, match="end_seconds"):
        DisturbanceSpec("event_demand", 20, 10, "e0", 1.0)
    with pytest.raises(ValueError, match="intensity"):
        DisturbanceSpec("vehicle_failure", 0, 10, "E0_0", 0)
    with pytest.raises(ValueError, match="intensity"):
        DisturbanceSpec("construction", 0, 10, "E0_0", 1.01)


def test_run_request_exposes_disturbance_through_existing_variant_contract():
    disturbance = DisturbanceSpec("construction", 10, 20, "E0_0", 1.0)
    request = RunRequest("1", "fixed_time", steps=10, disturbance=disturbance)
    assert request.variant.disturbance == disturbance


def test_flow_is_scaled_once_and_source_is_untouched(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    scene = _scene(source)
    source_bytes = scene.sumo_flow.read_bytes()
    bundle = VariantGenerator().generate_bundle(scene, 1.5, None, tmp_path / "bundle")
    flow_root = ET.parse(bundle.flow_file).getroot()
    source_root = ET.parse(scene.sumo_flow).getroot()
    assert len(flow_root.findall("flow")) == len(source_root.findall("flow"))
    assert int(flow_root.find("flow").get("number")) == round(
        int(source_root.find("flow").get("number")) * 1.5
    )
    assert scene.sumo_flow.read_bytes() == source_bytes
    assert bundle.manifest["parent_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert validate_variant(bundle) == []


def test_bundle_runtime_config_loads_only_the_derived_population(tmp_path):
    meta = __import__("scenes.registry", fromlist=["SceneRegistry"]).SceneRegistry().get_scene("1").meta
    bundle = VariantGenerator().generate_bundle(meta, 1.25, None, tmp_path / "bundle")

    config_root = ET.parse(bundle.sumo_cfg).getroot()
    route_files = config_root.find("./input/route-files").get("value").split(",")
    assert route_files == [bundle.route_file.name]
    assert bundle.flow_file.name not in route_files
    assert meta.sumo_rou.name not in route_files
    result = subprocess.run(
        ["sumo", "-c", str(bundle.sumo_cfg), "--no-step-log", "true", "--quit-on-end", "true"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_traci_command_uses_derived_config_and_excludes_intermediate_flow(tmp_path):
    scene = _scene(tmp_path)
    bundle = VariantGenerator().generate_bundle(scene, 1.0, None, tmp_path / "bundle")
    cmd = TraCIBridge(bundle.sumo_cfg, additional_files=list(bundle.additional_files))._build_cmd()
    assert cmd[cmd.index("-c") + 1] == str(bundle.sumo_cfg)
    assert bundle.flow_file.name not in ",".join(cmd)
    assert scene.sumo_rou.name not in ",".join(cmd)


def test_scaling_mixed_flow_and_vehicle_keeps_one_definition_each(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    scene = _scene(source)
    scene.sumo_flow.write_text(
        "<routes><vType id='car'/><flow id='f0' type='car' number='10' from='E0' to='E1'/>"
        "<vehicle id='v0' type='car' depart='10'><route edges='E0 E1'/></vehicle></routes>",
        encoding="utf-8",
    )
    bundle = VariantGenerator().generate_bundle(scene, 1.5, None, tmp_path / "bundle")
    root = ET.parse(bundle.flow_file).getroot()
    assert [flow.get("id") for flow in root.findall("flow")] == ["f0_x1.5"]
    assert [vehicle.get("id") for vehicle in root.findall("vehicle")] == ["v0_x1.5"]
    assert root.find("vehicle").get("type") == "car_x1.5"


def test_validate_variant_rejects_broken_additional_references(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    scene = _scene(source)
    bundle = VariantGenerator().generate_bundle(
        scene,
        1.0,
        DisturbanceSpec("vehicle_failure", 1, 3, "E0_0", 1.0),
        tmp_path / "bundle",
    )
    bundle.additional_files[-1].write_text(
        "<additional><vehicle id='broken' type='missing' depart='1'><route edges='missing'/></vehicle></additional>",
        encoding="utf-8",
    )
    issues = validate_variant(bundle)
    assert any("unknown vehicle type" in issue for issue in issues)
    assert any("unknown edge" in issue for issue in issues)


def test_validate_variant_rejects_runtime_config_with_parent_population(tmp_path):
    scene = _scene(tmp_path)
    bundle = VariantGenerator().generate_bundle(scene, 1.0, None, tmp_path / "bundle")
    config = ET.parse(bundle.sumo_cfg)
    config.getroot().find("./input/route-files").set("value", scene.sumo_rou.name)
    config.write(bundle.sumo_cfg, encoding="utf-8", xml_declaration=True)

    assert any("runtime route population" in issue for issue in validate_variant(bundle))


def test_variant_manifest_excludes_workspace_absolute_paths(tmp_path):
    scene = _scene(tmp_path)
    bundle = VariantGenerator().generate_bundle(scene, 1.0, None, tmp_path / "bundle")
    serialized = (tmp_path / "bundle" / "variant_manifest.json").read_text(encoding="utf-8")
    assert str(scene.sumo_flow.parent) not in serialized
    assert "data/intersection_data/1" in serialized


@pytest.mark.parametrize("kind,target", [("construction", "E0_0"), ("event_demand", "E0"), ("vehicle_failure", "E0_0")])
def test_disturbance_outputs_are_deterministic_and_auditable(tmp_path, kind, target):
    source = tmp_path / "source"
    source.mkdir()
    scene = _scene(source)
    disturbance = DisturbanceSpec(kind, 100, 200, target, 0.5)
    first = VariantGenerator().generate_bundle(scene, 1.0, disturbance, tmp_path / "a")
    second = VariantGenerator().generate_bundle(scene, 1.0, disturbance, tmp_path / "b")
    assert first.manifest["disturbance"]["kind"] == kind
    assert first.manifest["disturbance"]["begin_seconds"] == 100.0
    assert first.manifest["disturbance"]["intensity_semantics"]
    assert first.manifest["parent_sha256"] == second.manifest["parent_sha256"]
    assert [p.name for p in first.additional_files] == [p.name for p in second.additional_files]
    assert [p.read_bytes() for p in first.additional_files] == [p.read_bytes() for p in second.additional_files]
    if kind == "event_demand":
        root = ET.parse(first.additional_files[-1]).getroot()
        assert root.find("route").get("id") == "event_demand_route"
        assert root.find("./calibrator/flow").get("route") == "event_demand_route"
    assert validate_variant(first) == []


@pytest.mark.parametrize(
    ("kind", "target", "xpath"),
    [
        ("construction", "E0_0", "./rerouter/interval"),
        ("event_demand", "E0", "./calibrator/flow"),
        ("vehicle_failure", "E0_0", "./vehicle/stop"),
    ],
)
def test_disturbance_intensity_changes_distinct_executable_semantics(tmp_path, kind, target, xpath):
    source = tmp_path / "source"
    source.mkdir()
    scene = _scene(source)
    low = VariantGenerator().generate_bundle(scene, 1.0, DisturbanceSpec(kind, 10, 30, target, 0.25), tmp_path / "low")
    high = VariantGenerator().generate_bundle(scene, 1.0, DisturbanceSpec(kind, 10, 30, target, 1.0), tmp_path / "high")
    low_node = ET.parse(low.additional_files[-1]).getroot().find(xpath)
    high_node = ET.parse(high.additional_files[-1]).getroot().find(xpath)
    assert low_node is not None and high_node is not None
    assert low_node.attrib != high_node.attrib
    assert ET.parse(low.additional_files[-1]).getroot().tag == "additional"
    assert validate_variant(low) == []


@pytest.mark.parametrize("kind,target", [("construction", "E0_0"), ("event_demand", "E0"), ("vehicle_failure", "E0_0")])
def test_each_disturbance_starts_real_sumo_within_active_interval(tmp_path, kind, target):
    scene = _scene(tmp_path)
    bundle = VariantGenerator().generate_bundle(
        scene, 1.0, DisturbanceSpec(kind, 1, 3, target, 0.5), tmp_path / kind
    )
    result = subprocess.run(
        ["sumo", "-c", str(bundle.sumo_cfg), "-a", ",".join(map(str, bundle.additional_files)), "--end", "4", "--no-step-log", "true"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_disturbance_rejects_unknown_lane_and_invalid_bundle(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    scene = _scene(source)
    with pytest.raises(ValueError, match="target"):
        VariantGenerator().generate_bundle(scene, 1.0, DisturbanceSpec("construction", 0, 10, "missing", 1), tmp_path / "bad")
    bundle = VariantGenerator().generate_bundle(scene, 1.0, None, tmp_path / "ok")
    bundle.manifest["additional_files"] = ["same.xml", "same.xml"]
    assert any("conflict" in issue for issue in validate_variant(bundle))
