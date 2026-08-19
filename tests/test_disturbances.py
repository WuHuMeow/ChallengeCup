from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from api.models import DisturbanceSpecModel
from core.run_models import DisturbanceSpec, RunRequest, VariantSpec
from core.types import SceneMeta
from scenes.disturbances import validate_variant
from scenes.variant import VariantGenerator


def _scene(tmp_path: Path) -> SceneMeta:
    flow = tmp_path / "demo.flow.xml"
    flow.write_text(
        "<routes><vType id='car'/><flow id='f0' type='car' number='10' from='e0' to='e1'/></routes>",
        encoding="utf-8",
    )
    net = tmp_path / "demo.net.xml"
    net.write_text(
        "<net><edge id='e0' from='n0' to='n1'><lane id='e0_0' index='0' speed='10' length='100'/></edge>"
        "<edge id='e1' from='n1' to='n2'><lane id='e1_0' index='0' speed='10' length='100'/></edge>"
        "<tlLogic id='tls' type='static' programID='0' offset='0'><phase duration='30' state='Gr'/></tlLogic>"
        "</net>",
        encoding="utf-8",
    )
    rou = tmp_path / "demo.rou.xml"
    rou.write_text("<routes><route id='r0' edges='e0 e1'/></routes>", encoding="utf-8")
    turn = tmp_path / "demo.turn.xml"
    turn.write_text("<turns/>", encoding="utf-8")
    cfg = tmp_path / "demo.sumocfg"
    cfg.write_text("<configuration><input><net-file value='demo.net.xml'/><route-files value='demo.rou.xml'/></input></configuration>", encoding="utf-8")
    return SceneMeta("1", "test", net, rou, flow, turn, cfg, tmp_path / "timing.xlsx")


def test_disturbance_spec_validates_and_api_round_trips():
    domain = DisturbanceSpec("construction", 10, 20, "e0_0", 1.0)
    model = DisturbanceSpecModel.model_validate(domain.__dict__)
    assert model.to_domain() == domain
    with pytest.raises(ValueError, match="end_seconds"):
        DisturbanceSpec("event_demand", 20, 10, "e0", 1.0)
    with pytest.raises(ValueError, match="intensity"):
        DisturbanceSpec("vehicle_failure", 0, 10, "e0_0", 0)


def test_run_request_exposes_disturbance_through_existing_variant_contract():
    disturbance = DisturbanceSpec("construction", 10, 20, "e0_0", 1.0)
    request = RunRequest("1", "fixed_time", steps=10, disturbance=disturbance)
    assert request.variant.disturbance == disturbance


def test_flow_is_scaled_once_and_source_is_untouched(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    scene = _scene(source)
    source_bytes = scene.sumo_flow.read_bytes()
    bundle = VariantGenerator().generate_bundle(scene, 1.5, None, tmp_path / "bundle")
    flow_root = ET.parse(bundle.flow_file).getroot()
    assert len(flow_root.findall("flow")) == 1
    assert int(flow_root.find("flow").get("number")) == 15
    assert scene.sumo_flow.read_bytes() == source_bytes
    assert bundle.manifest["parent_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert validate_variant(bundle) == []


@pytest.mark.parametrize("kind,target", [("construction", "e0_0"), ("event_demand", "e0"), ("vehicle_failure", "e0_0")])
def test_disturbance_outputs_are_deterministic_and_auditable(tmp_path, kind, target):
    source = tmp_path / "source"
    source.mkdir()
    scene = _scene(source)
    disturbance = DisturbanceSpec(kind, 100, 200, target, 0.5)
    first = VariantGenerator().generate_bundle(scene, 1.0, disturbance, tmp_path / "a")
    second = VariantGenerator().generate_bundle(scene, 1.0, disturbance, tmp_path / "b")
    assert first.manifest["disturbance"]["kind"] == kind
    assert first.manifest["disturbance"]["begin_seconds"] == 100.0
    assert first.manifest["parent_sha256"] == second.manifest["parent_sha256"]
    assert [p.name for p in first.additional_files] == [p.name for p in second.additional_files]
    assert [p.read_bytes() for p in first.additional_files] == [p.read_bytes() for p in second.additional_files]
    if kind == "event_demand":
        root = ET.parse(first.additional_files[-1]).getroot()
        assert root.find("route").get("id") == "event_demand_route"
        assert root.find("./calibrator/flow").get("route") == "event_demand_route"
    assert validate_variant(first) == []


def test_disturbance_rejects_unknown_lane_and_invalid_bundle(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    scene = _scene(source)
    with pytest.raises(ValueError, match="target"):
        VariantGenerator().generate_bundle(scene, 1.0, DisturbanceSpec("construction", 0, 10, "missing", 1), tmp_path / "bad")
    bundle = VariantGenerator().generate_bundle(scene, 1.0, None, tmp_path / "ok")
    bundle.manifest["additional_files"] = ["same.xml", "same.xml"]
    assert any("conflict" in issue for issue in validate_variant(bundle))
