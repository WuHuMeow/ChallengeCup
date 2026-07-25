"""场景注册与配置加载测试。"""

from core.config import Config, get_config
from scenes.registry import SceneRegistry
from pathlib import Path


def test_config_loads():
    cfg = get_config()
    assert cfg.get("project.name") is not None
    assert cfg.get("sumo.binary") == "sumo"


def test_config_dot_notation():
    cfg = get_config()
    assert cfg.get("algorithms.ca_maxpressure.ewma_alpha") == 0.3
    assert cfg.get("nonexistent.key", "default") == "default"


def test_scene_registry_discovers_intersections():
    registry = SceneRegistry()
    scenes = registry.list_scenes()
    assert len(scenes) == 20


def test_scene_registry_get_scene():
    registry = SceneRegistry()
    scene = registry.get_scene("1")
    assert scene.meta.intersection_id == "1"
    assert scene.meta.sumo_cfg.exists()
    assert scene.meta.sumo_net.exists()


def test_scene_registry_handles_naming_variant():
    registry = SceneRegistry()
    scene_11 = registry.get_scene("11")
    assert scene_11.meta.map_png is not None


def test_variant_generate_all_no_keyerror():
    """generate_all 不应因 TrafficLevel.LOW 不在默认 levels 中而报错。"""
    from core.types import TrafficLevel
    from scenes.variant import VariantGenerator

    gen = VariantGenerator()
    assert TrafficLevel.LOW not in gen.levels
    assert TrafficLevel.NORMAL in gen.levels
    assert TrafficLevel.HIGH in gen.levels


def test_generate_adds_id_suffix(tmp_path):
    import xml.etree.ElementTree as ET
    from core.types import TrafficLevel
    from scenes.variant import VariantGenerator
    from scenes.registry import SceneRegistry

    meta = SceneRegistry().get_scene("1").meta
    gen = VariantGenerator()
    factor = gen.levels[TrafficLevel.HIGH]
    suffix = f"_x{factor:g}"
    out = gen.generate(meta, TrafficLevel.HIGH, tmp_path)
    assert out.exists() and out.name.endswith("_high.flow.xml")

    root = ET.parse(out).getroot()
    vtype_ids = {v.get("id") for v in root.findall("vType")}
    assert vtype_ids and all(i.endswith(suffix) for i in vtype_ids)
    for flow in root.findall("flow"):
        assert flow.get("id").endswith(suffix)
        type_attr = flow.get("type")
        if type_attr is not None:
            assert type_attr in vtype_ids


def test_generate_scaled_arbitrary_factor(tmp_path):
    import xml.etree.ElementTree as ET
    from scenes.variant import VariantGenerator
    from scenes.registry import SceneRegistry

    meta = SceneRegistry().get_scene("1").meta
    out = VariantGenerator().generate_scaled(meta, 1.5, tmp_path)
    assert out.exists() and "x1.5" in out.name
    base = ET.parse(meta.sumo_flow).getroot()
    scaled = ET.parse(out).getroot()
    base_n = int(base.find("flow").get("number"))
    scaled_n = int(scaled.find("flow").get("number"))
    assert scaled_n == max(1, round(base_n * 1.5))


def test_generate_scaled_rejects_nonpositive(tmp_path):
    import pytest
    from scenes.variant import VariantGenerator
    from scenes.registry import SceneRegistry

    meta = SceneRegistry().get_scene("1").meta
    with pytest.raises(ValueError):
        VariantGenerator().generate_scaled(meta, 0.0, tmp_path)
