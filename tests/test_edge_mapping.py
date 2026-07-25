"""edge_mapping 结构化生成与 TraCIBridge 进口道筛选测试（IB W1 Day 5）。"""
import logging
from pathlib import Path

from engine.traci_bridge import TraCIBridge


def test_edge_mapping_json_exists_and_structured():
    import json
    path = Path("data/intersection_data/metadata/edge_mapping.json")
    assert path.exists(), "先运行 python scripts/data/generate_edge_mapping.py"
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
