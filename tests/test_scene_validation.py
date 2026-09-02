"""Validated SUMO scene manifest contract tests."""

from pathlib import Path
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET

import pytest

from scenes.importer import SceneImporter, SceneValidationError
from scenes.registry import SceneRegistry
from scenes.validator import SceneValidator


@pytest.fixture
def official_scene_root() -> Path:
    return Path("data/intersection_data/1")


def _copy_official_scene(official_scene_root: Path, tmp_path: Path) -> Path:
    copied_root = tmp_path / "1"
    shutil.copytree(official_scene_root, copied_root)
    return copied_root


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_official_scene_manifest_contains_all_required_inputs(official_scene_root):
    """Removing a required official input must make the manifest unusable."""
    manifest = SceneValidator().validate(official_scene_root)

    assert manifest.validation_status == "pass"
    assert {"net", "flow", "route", "turn", "sumocfg", "timing", "map"} <= set(
        manifest.source_files
    )
    assert manifest.step_length == 1.0
    assert manifest.tls_ids
    assert manifest.lane_ids
    assert manifest.movement_count > 0
    assert all(path.startswith("data/intersection_data/1/") for path in manifest.source_files.values())
    assert all(len(digest) == 64 for digest in manifest.sha256.values())


def test_validation_fails_when_no_controlled_movement_is_available(tmp_path):
    """A net without a valid controlled lane-to-lane connection is not formal."""
    root = tmp_path / "broken"
    sumo_dir = root / "sumo工程"
    data_dir = root / "路口数据"
    map_dir = root / "高精地图"
    sumo_dir.mkdir(parents=True)
    data_dir.mkdir()
    map_dir.mkdir()
    prefix = "demo_broken"
    (sumo_dir / f"{prefix}.net.xml").write_text(
        "<net><edge id='in'><lane id='in_0'/></edge><edge id='out'><lane id='out_0'/></edge>"
        "<tlLogic id='tls' programID='0'><phase duration='30' state='r'/></tlLogic></net>",
        encoding="utf-8",
    )
    (sumo_dir / f"{prefix}.flow.xml").write_text(
        "<routes><vType id='car'/><flow id='f' type='car' from='in'/></routes>",
        encoding="utf-8",
    )
    (sumo_dir / f"{prefix}.rou.xml").write_text(
        "<routes><vType id='car'/><vehicle id='v' type='car'><route edges='in out'/></vehicle></routes>",
        encoding="utf-8",
    )
    (sumo_dir / f"{prefix}.turn.xml").write_text(
        "<edgeRelations><interval><edgeRelation from='in' to='out' probability='1'/></interval></edgeRelations>",
        encoding="utf-8",
    )
    (sumo_dir / f"{prefix}.sumocfg").write_text(
        "<configuration><input><net-file value='demo_broken.net.xml'/></input></configuration>",
        encoding="utf-8",
    )
    (data_dir / f"{prefix}流量和交叉口配时方案.xlsx").touch()
    (map_dir / f"{prefix}.png").touch()

    manifest = SceneValidator(repository_root=tmp_path).validate(root)

    assert manifest.validation_status == "fail"
    assert any("movement" in warning for warning in manifest.warnings)


def test_import_rejects_missing_movement_mapping_without_creating_package(tmp_path):
    """Importer must not leave a partial package for a failed validation."""
    with pytest.raises(SceneValidationError, match="movement"):
        SceneImporter(repository_root=tmp_path).import_scene(
            tmp_path / "broken", tmp_path / "packages"
        )

    assert not (tmp_path / "packages").exists()


def test_import_copies_validated_scene_without_writing_source(official_scene_root, tmp_path):
    """Import must preserve official bytes and package every manifest input."""
    source_net = official_scene_root / "sumo工程" / "demo_1.net.xml"
    before = source_net.read_bytes()

    manifest = SceneImporter().import_scene(official_scene_root, tmp_path / "packages")

    package_root = tmp_path / "packages" / "1"
    assert manifest.validation_status == "pass"
    assert source_net.read_bytes() == before
    assert (package_root / "sumo工程" / "demo_1.net.xml").read_bytes() == before
    assert (package_root / "路口数据" / "demo_1流量和交叉口配时方案.xlsx").exists()
    assert (package_root / "高精地图" / "demo_1.png").exists()
    package_manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    assert package_manifest["scene_id"] == manifest.scene_id
    assert package_manifest["source_files"] == dict(manifest.source_files)
    assert package_manifest["sha256"] == dict(manifest.sha256)
    assert package_manifest["source_provenance"]["net"].startswith(
        "data/intersection_data/1/"
    )
    for key, relative_path in manifest.source_files.items():
        packaged_file = package_root / relative_path
        assert packaged_file.is_file(), key
        assert _sha256(packaged_file) == manifest.sha256[key]


def test_validation_fails_when_a_vehicle_references_an_unknown_named_route(
    official_scene_root, tmp_path
):
    """A broken named route reference would otherwise reach SUMO unnoticed."""
    copied_root = _copy_official_scene(official_scene_root, tmp_path)
    route_path = copied_root / "sumo工程" / "demo_1.rou.xml"
    route_root = ET.parse(route_path)
    vehicle = route_root.find("vehicle")
    vehicle.set("route", "missing-route")
    vehicle.remove(vehicle.find("route"))
    route_root.write(route_path, encoding="utf-8", xml_declaration=True)

    manifest = SceneValidator(repository_root=tmp_path).validate(copied_root)

    assert manifest.validation_status == "fail"
    assert any("unknown named route" in warning for warning in manifest.warnings)


@pytest.mark.parametrize(
    ("route_xml", "expected_warning"),
    [
        ("<routes><flow id='f' route='missing-route'/></routes>", "unknown named route"),
        (
            "<routes><flow id='f'><route edges='-E1 missing-edge'/></flow></routes>",
            "unknown edge",
        ),
        (
            "<routes><flow id='f'><route edges='-E1 E1'/></flow></routes>",
            "disconnected edges",
        ),
    ],
)
def test_validation_rejects_invalid_flow_route_reference(
    official_scene_root, tmp_path, route_xml, expected_warning
):
    """Flow route definitions must be validated just like route-file vehicles."""
    copied_root = _copy_official_scene(official_scene_root, tmp_path)
    flow_path = copied_root / "sumo工程" / "demo_1.flow.xml"
    flow_path.write_text(route_xml, encoding="utf-8")

    manifest = SceneValidator(repository_root=tmp_path).validate(copied_root)

    assert manifest.validation_status == "fail"
    assert any(expected_warning in warning for warning in manifest.warnings)


@pytest.mark.parametrize(
    ("link_index", "state", "expected_warning"),
    [
        ("-1", None, "invalid linkIndex"),
        ("not-an-index", None, "invalid linkIndex"),
        ("99", None, "not covered"),
        ("0", "", "not covered"),
    ],
)
def test_validation_rejects_controlled_movement_without_valid_phase_coverage(
    official_scene_root, tmp_path, link_index, state, expected_warning
):
    """A connection is usable only when every TLS phase has a valid state bit."""
    copied_root = _copy_official_scene(official_scene_root, tmp_path)
    net_path = copied_root / "sumo工程" / "demo_1.net.xml"
    net_root = ET.parse(net_path)
    connection = net_root.find("connection[@tl='J1']")
    connection.set("linkIndex", link_index)
    if state is not None:
        for phase in net_root.findall("./tlLogic[@id='J1']/phase"):
            phase.set("state", state)
    net_root.write(net_path, encoding="utf-8", xml_declaration=True)

    manifest = SceneValidator(repository_root=tmp_path).validate(copied_root)

    assert manifest.validation_status == "fail"
    assert any(expected_warning in warning for warning in manifest.warnings)


def test_validation_turns_corrupt_timing_workbook_into_fail_manifest(
    official_scene_root, tmp_path
):
    """An unreadable xlsx is reported in the manifest instead of escaping validation."""
    copied_root = _copy_official_scene(official_scene_root, tmp_path)
    timing_path = next((copied_root / "路口数据").glob("*.xlsx"))
    timing_path.write_bytes(b"not an xlsx")

    manifest = SceneValidator(repository_root=tmp_path).validate(copied_root)

    assert manifest.validation_status == "fail"
    assert any("invalid timing workbook" in warning for warning in manifest.warnings)


def test_validation_turns_unexpected_timing_parser_error_into_fail_manifest(
    official_scene_root, monkeypatch
):
    """A parser implementation error must not escape the validation boundary."""
    monkeypatch.setattr(
        "scenes.validator.parse_timing_excel",
        lambda _: (_ for _ in ()).throw(RuntimeError("broken parser")),
    )

    manifest = SceneValidator().validate(official_scene_root)

    assert manifest.validation_status == "fail"
    assert any("invalid timing workbook" in warning for warning in manifest.warnings)


def test_official_route_generation_provenance_clears_source_warnings(
    official_scene_root,
):
    """The embedded jtrrouter recipe proves how flow and turn produced rou.xml."""
    manifest = SceneValidator().validate(official_scene_root)

    assert manifest.route_generation_verified is True
    assert manifest.warnings == ()


def test_missing_route_generation_provenance_keeps_source_warning(
    official_scene_root, tmp_path
):
    copied_root = _copy_official_scene(official_scene_root, tmp_path)
    route_path = copied_root / "sumo工程" / "demo_1.rou.xml"
    route_text = route_path.read_text(encoding="utf-8")
    route_path.write_text(
        route_text.replace(
            '<turn-ratio-files value="demo_1.turn.xml"/>',
            '<turn-ratio-files value="unverified.turn.xml"/>',
        ),
        encoding="utf-8",
    )

    manifest = SceneValidator(repository_root=tmp_path).validate(copied_root)

    assert manifest.route_generation_verified is False
    assert (
        "source warning: sumocfg does not explicitly reference turn input"
        in manifest.warnings
    )


def test_all_official_scenes_have_verified_route_generation():
    manifests = SceneRegistry().list_scenes(formal_only=True)

    assert len(manifests) == 20
    assert all(manifest.route_generation_verified for manifest in manifests)
    assert all(manifest.warnings == () for manifest in manifests)


def test_registry_lists_immutable_manifests_without_breaking_runtime_scene():
    """Changing registry metadata must not change get_scene/get_meta contracts."""
    registry = SceneRegistry()

    manifests = registry.list_scenes(formal_only=True)

    assert isinstance(manifests, tuple)
    assert len(manifests) == 20
    assert all(manifest.validation_status == "pass" for manifest in manifests)
    assert registry.get_scene("1").meta.intersection_id == "1"
    assert registry.get_meta("11").map_png is not None
