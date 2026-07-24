"""车辆采样/上限与到达历史测试（IB W4）。"""
from engine.mock_bridge import MockBridge


def test_mock_vehicles_deterministic():
    bridge = MockBridge()
    bridge.start()
    bridge.step()
    state = bridge.get_state()
    assert state.vehicles, "应有车辆快照"
    assert all(v.lane_id for v in state.vehicles)


def test_mock_vehicle_sample_rate():
    full = MockBridge(vehicle_sample_rate=1)
    sampled = MockBridge(vehicle_sample_rate=3)
    full.start(); sampled.start()
    full.step(); sampled.step()
    n_full = len(full.get_state().vehicles)
    n_sampled = len(sampled.get_state().vehicles)
    assert n_sampled < n_full


def test_mock_arrival_history_rolls():
    bridge = MockBridge()
    bridge.start()
    for _ in range(5):
        bridge.step()
    state = bridge.get_state()
    assert state.arrival_history == [1, 1, 1, 1, 1]  # Mock: 每步 1 辆进入


def test_traci_collect_vehicles_cap_prefers_inbound():
    from pathlib import Path
    from unittest.mock import patch
    from engine.traci_bridge import TraCIBridge, traci

    bridge = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"))
    bridge._controlled_lanes = ["-E2_0"]
    ids = [f"v{i}" for i in range(600)]

    def lane_of(vid: str) -> str:
        return "-E2_0" if int(vid[1:]) < 100 else "E9_0"  # 前 100 辆在进口道

    with patch.object(traci.vehicle, "getLaneID", side_effect=lane_of), \
         patch.object(traci.vehicle, "getSpeed", return_value=5.0):
        vehicles = bridge._collect_vehicles(ids)
    assert len(vehicles) == 500
    inbound = [v for v in vehicles if v.lane_id == "-E2_0"]
    assert len(inbound) == 100  # 进口道车辆全部保留
