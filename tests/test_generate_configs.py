from pathlib import Path
from xml.etree import ElementTree

from scripts.generate_configs import generate_configs, relative_input_path


def test_relative_input_path_uses_config_directory(tmp_path):
    out = tmp_path / "engine" / "configs"
    source = (
        tmp_path
        / "data"
        / "intersection_data"
        / "1"
        / "sumo工程"
        / "demo_1.net.xml"
    )
    assert (
        relative_input_path(source, out)
        == "../../data/intersection_data/1/sumo工程/demo_1.net.xml"
    )


def test_generate_configs_writes_twenty_resolvable_configs(tmp_path):
    data = Path("data/intersection_data").resolve()
    out = tmp_path / "engine" / "configs"
    written = generate_configs(data_root=data, output_dir=out)

    assert len(written) == 20
    text = written[0].read_text(encoding="utf-8")
    assert "demo_1.net.xml" in text
    root = ElementTree.fromstring(text)
    for tag in ("net-file", "route-files"):
        value = root.find(f"input/{tag}").attrib["value"]
        assert (written[0].parent / value).resolve().is_file()


def test_generate_configs_preserves_original_step_length(tmp_path):
    written = generate_configs(
        data_root=Path("data/intersection_data").resolve(),
        output_dir=tmp_path / "configs",
    )

    route_1 = written[0].read_text(encoding="utf-8")
    route_11 = written[10].read_text(encoding="utf-8")
    assert "<step-length" not in route_1
    assert '<step-length value="0.1"/>' in route_11
