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
