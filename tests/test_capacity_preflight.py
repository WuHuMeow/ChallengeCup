"""Capacity-aware static scene preflight tests."""

from pathlib import Path

import pytest

from scenes.capacity_preflight import validate_capacity_aware_scene
from scenes.registry import SceneRegistry


def test_preflight_reports_every_required_non_positive_movement_lane(tmp_path):
    """The error must be attributable without starting a SUMO process."""
    net = tmp_path / "scene.net.xml"
    net.write_text(
        "<net><edge id='in'><lane id='in_0' length='0'/></edge>"
        "<edge id='out'><lane id='out_0' length='-1'/></edge>"
        "<connection from='in' to='out' fromLane='0' toLane='0' tl='tls' linkIndex='0'/></net>",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"in_0.*out_0"):
        validate_capacity_aware_scene(net)


def test_all_official_scenes_have_positive_required_movement_capacities():
    """The static boundary must accept all 20 untouched official networks."""
    scenes = SceneRegistry()
    official = [scenes.get_scene(str(index)) for index in range(1, 21)]

    for scene in official:
        validate_capacity_aware_scene(scene.meta.sumo_net)

    assert len(official) == 20
