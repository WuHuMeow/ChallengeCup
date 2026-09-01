"""Movement extraction tests for the run-scoped TraCI adapter."""

from types import SimpleNamespace

import pytest

from core.movements import MovementKey
from engine.movement_state import MovementStateBuilder


class FakeMovementBridge:
    def __init__(self) -> None:
        self.controlled_link_reads = 0
        self.queues = {"in_0": 3.0, "in_1": 2.0, "out_a_0": 1.0, "out_b_0": 0.0}
        self.controlled_links = (
            (("in_0", "out_a_0", ":via_0"),),
            (("in_1", "out_b_0", ":via_1"),),
        )
        self.program = SimpleNamespace(
            phases=(
                SimpleNamespace(state="Gr", duration=30.0),
                SimpleNamespace(state="rG", duration=25.0),
                SimpleNamespace(state="yy", duration=3.0),
            )
        )

    def get_controlled_links(self, tls_id: str):
        assert tls_id == "tls0"
        self.controlled_link_reads += 1
        return self.controlled_links

    def get_signal_program(self, tls_id: str):
        assert tls_id == "tls0"
        return self.program

    def get_lane_length(self, lane_id: str) -> float:
        return {"in_0": 75.0, "in_1": 90.0, "out_a_0": 60.0, "out_b_0": 45.0}[lane_id]

    def get_lane_halting_number(self, lane_id: str) -> float:
        return self.queues[lane_id]

    def get_lane_occupancy(self, lane_id: str) -> float:
        return {"out_a_0": 25.0, "out_b_0": 0.4}.get(lane_id, 0.0)

    def get_turn_ratio(self, incoming_lane: str, outgoing_lane: str) -> float | None:
        return {
            ("in_0", "out_a_0"): 0.6,
            ("in_1", "out_b_0"): 0.4,
        }.get((incoming_lane, outgoing_lane))


def test_controlled_links_build_phase_movements_with_positive_capacities():
    phases = MovementStateBuilder.from_traci(FakeMovementBridge(), "tls0")

    assert [phase.phase_index for phase in phases] == [0, 1, 2]
    assert [movement.key for movement in phases[0].movements] == [
        MovementKey("in_0", "out_a_0")
    ]
    assert [movement.key for movement in phases[1].movements] == [
        MovementKey("in_1", "out_b_0")
    ]
    assert phases[2].movements == ()
    movement = phases[0].movements[0]
    assert movement.incoming_capacity == 10.0
    assert movement.downstream_capacity == 8.0
    assert movement.downstream_occupancy == 0.25
    assert movement.turn_ratio == 1.0
    assert movement.saturation_rate == pytest.approx(0.5)


def test_builder_caches_topology_but_refreshes_measurements():
    bridge = FakeMovementBridge()
    builder = MovementStateBuilder(bridge, "tls0")

    first = builder.snapshot()
    bridge.queues["in_0"] = 7.0
    second = builder.snapshot()

    assert first[0].movements[0].queue_vehicles == 3.0
    assert second[0].movements[0].queue_vehicles == 7.0
    assert bridge.controlled_link_reads == 1


def test_green_phase_without_a_controlled_movement_is_rejected():
    bridge = FakeMovementBridge()
    bridge.controlled_links = ()

    with pytest.raises(ValueError, match="green phase 0"):
        MovementStateBuilder.from_traci(bridge, "tls0")


def test_uniform_turn_ratio_counts_unique_movements_across_phases():
    bridge = FakeMovementBridge()
    bridge.controlled_links = (
        (("in_0", "out_a_0", ":via_0"),),
        (("in_0", "out_b_0", ":via_1"),),
    )
    bridge.program = SimpleNamespace(
        phases=(
            SimpleNamespace(state="Gr", duration=30.0),
            SimpleNamespace(state="rG", duration=25.0),
            SimpleNamespace(state="Gr", duration=30.0),
        )
    )
    bridge.get_turn_ratio = lambda incoming, outgoing: None

    phases = MovementStateBuilder.from_traci(bridge, "tls0")

    assert phases[0].movements[0].turn_ratio == 0.5
    assert phases[1].movements[0].turn_ratio == 0.5
    assert phases[2].movements[0].turn_ratio == 0.5


def test_configured_turn_ratios_are_normalized_per_incoming_lane():
    bridge = FakeMovementBridge()
    bridge.controlled_links = tuple(
        (("in_0", outgoing, f":via_{index}"),)
        for index, outgoing in enumerate(
            ("out_a_0", "out_a_1", "out_b_0", "out_c_0")
        )
    )
    bridge.queues.update({"out_a_1": 0.0, "out_c_0": 0.0})
    bridge.program = SimpleNamespace(
        phases=(SimpleNamespace(state="GGGG", duration=30.0),)
    )
    raw = {
        "out_a_0": 0.3,
        "out_a_1": 0.4,
        "out_b_0": 0.4,
        "out_c_0": 0.3,
    }
    bridge.get_turn_ratio = lambda incoming, outgoing: raw[outgoing]
    bridge.get_lane_length = lambda lane: 75.0
    bridge.get_lane_occupancy = lambda lane: 0.0

    phase = MovementStateBuilder.from_traci(bridge, "tls0")[0]
    ratios = {movement.key.outgoing_lane: movement.turn_ratio for movement in phase.movements}

    assert sum(ratios.values()) == pytest.approx(1.0)
    assert ratios == {
        "out_a_0": pytest.approx(3 / 14),
        "out_a_1": pytest.approx(4 / 14),
        "out_b_0": pytest.approx(4 / 14),
        "out_c_0": pytest.approx(3 / 14),
    }
