"""edge_mapping 结构化生成与 TraCIBridge 进口道筛选测试（IB W1 Day 5）。"""
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine.traci_bridge import TraCIBridge, traci


def test_edge_mapping_json_exists_and_structured():
    import json
    path = Path("data/intersection_data/metadata/edge_mapping.json")
    assert path.exists(), "先运行 python scripts/generate_edge_mapping.py"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "1" in data and "edges" in data["1"]
    entry = {e: i for e, i in data["1"]["edges"].items() if i["kind"] == "entry"}
    assert entry, "路口 1 应有进口边"
    for info in entry.values():
        assert info["lanes"] >= 1 and info["direction"]


def test_apply_edge_mapping_filters_inbound():
    bridge = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"))
    bridge._controlled_lanes = ["-E2_0", "-E2_1", "E4_0"]
    bridge._apply_edge_mapping({
        "-E2": {"direction": "东", "kind": "entry", "lanes": 2},
        "E4": {"direction": "西", "kind": "exit", "lanes": 1},
    })
    assert bridge._inbound_lanes == ["-E2_0", "-E2_1"]
    assert bridge.lane_directions == {"-E2_0": "东", "-E2_1": "东"}


def test_apply_edge_mapping_no_entry_falls_back(caplog):
    bridge = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"))
    bridge._controlled_lanes = ["E4_0"]
    with caplog.at_level(logging.WARNING):
        bridge._apply_edge_mapping({"E4": {"direction": "西", "kind": "exit", "lanes": 1}})
    assert bridge._inbound_lanes is None  # 无进口边 → 回退 getControlledLanes
    assert any("回退" in r.message for r in caplog.records)


def test_build_phase_states_uses_controlled_links_and_lane_measurements():
    bridge = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"))
    program = SimpleNamespace(
        phases=[
            SimpleNamespace(state="Gr", duration=30.0),
            SimpleNamespace(state="yr", duration=3.0),
            SimpleNamespace(state="rG", duration=25.0),
        ]
    )
    controlled_links = [
        (("in_0", "out_0", "via_0"),),
        (("in_1", "out_1", "via_1"),),
    ]
    queues = {"in_0": 8, "out_0": 1, "in_1": 4, "out_1": 2}
    lengths = {"in_0": 75, "out_0": 150, "in_1": 75, "out_1": 75}
    occupancies = {"out_0": 95.0, "out_1": 20.0}

    with (
        patch.object(
            traci.lane,
            "getLastStepHaltingNumber",
            side_effect=lambda lane: queues[lane],
        ),
        patch.object(
            traci.lane,
            "getLength",
            side_effect=lambda lane: lengths[lane],
        ),
        patch.object(
            traci.lane,
            "getLastStepOccupancy",
            side_effect=lambda lane: occupancies[lane],
        ),
    ):
        phases = bridge._build_phase_states(program, controlled_links)

    assert phases[0].phase_index == 0
    assert phases[0].incoming_lanes == ("in_0",)
    assert phases[0].outgoing_lanes == ("out_0",)
    assert phases[0].incoming_queue == 8.0
    assert phases[0].incoming_capacity == 10.0
    assert phases[0].outgoing_capacity == 20.0
    assert phases[0].outgoing_occupancy == 0.95
    assert phases[1].incoming_lanes == ()
    assert phases[2].incoming_lanes == ("in_1",)
