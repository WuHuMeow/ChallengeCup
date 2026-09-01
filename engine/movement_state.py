"""Movement-level state extraction from TraCI adapters."""

from __future__ import annotations

from dataclasses import dataclass

from core.movements import MovementKey, MovementState, PhaseMovementState


@dataclass(frozen=True)
class _PhaseTopology:
    phase_index: int
    signal_state: str
    nominal_duration: float
    movements: tuple[MovementKey, ...]


class MovementStateBuilder:
    """Cache signal topology once and refresh lane measurements per snapshot."""

    DEFAULT_VEHICLE_LENGTH_M = 5.0
    DEFAULT_MINIMUM_GAP_M = 2.5
    DEFAULT_SATURATION_RATE = 0.5

    def __init__(
        self,
        bridge: object,
        tls_id: str,
        *,
        vehicle_length_m: float = DEFAULT_VEHICLE_LENGTH_M,
        minimum_gap_m: float = DEFAULT_MINIMUM_GAP_M,
    ) -> None:
        self.bridge = bridge
        self.tls_id = tls_id
        self.vehicle_length_m = float(vehicle_length_m)
        self.minimum_gap_m = float(minimum_gap_m)
        self.capacity_spacing_m = self.vehicle_length_m + self.minimum_gap_m
        if self.capacity_spacing_m <= 0:
            raise ValueError("vehicle length plus minimum gap must be positive")
        self._topology = self._build_topology()

    @classmethod
    def from_traci(
        cls,
        bridge: object,
        tls_id: str,
    ) -> tuple[PhaseMovementState, ...]:
        return cls(bridge, tls_id).snapshot()

    def snapshot(self) -> tuple[PhaseMovementState, ...]:
        phases = []
        turn_ratios = self._normalized_turn_ratios()

        for phase in self._topology:
            movements = []
            for key in phase.movements:
                turn_ratio = turn_ratios[key]
                occupancy = float(
                    self.bridge.get_lane_occupancy(key.outgoing_lane)
                )
                if occupancy > 1.0:
                    occupancy /= 100.0
                occupancy = min(1.0, max(0.0, occupancy))
                movements.append(
                    MovementState(
                        key=key,
                        queue_vehicles=float(
                            self.bridge.get_lane_halting_number(key.incoming_lane)
                        ),
                        downstream_queue_vehicles=float(
                            self.bridge.get_lane_halting_number(key.outgoing_lane)
                        ),
                        incoming_capacity=self._capacity(key.incoming_lane),
                        downstream_capacity=self._capacity(key.outgoing_lane),
                        downstream_occupancy=occupancy,
                        saturation_rate=(
                            self.DEFAULT_SATURATION_RATE * float(turn_ratio)
                        ),
                        turn_ratio=float(turn_ratio),
                    )
                )
            phases.append(
                PhaseMovementState(
                    phase_index=phase.phase_index,
                    signal_state=phase.signal_state,
                    movements=tuple(movements),
                    nominal_duration=phase.nominal_duration,
                )
            )
        return tuple(phases)

    def _normalized_turn_ratios(self) -> dict[MovementKey, float]:
        """Normalize configured or observed weights over each lane's legal moves."""
        by_incoming: dict[str, list[MovementKey]] = {}
        for key in self.movement_keys:
            by_incoming.setdefault(key.incoming_lane, []).append(key)

        normalized: dict[MovementKey, float] = {}
        for keys in by_incoming.values():
            raw = {
                key: self.bridge.get_turn_ratio(
                    key.incoming_lane,
                    key.outgoing_lane,
                )
                for key in keys
            }
            weights = {
                key: max(0.0, float(value)) if value is not None else 0.0
                for key, value in raw.items()
            }
            total = sum(weights.values())
            if total <= 0:
                uniform = 1.0 / len(keys)
                normalized.update({key: uniform for key in keys})
                continue
            normalized.update({key: weights[key] / total for key in keys})
        return normalized

    @property
    def capacity_inputs(self) -> dict[str, float]:
        return {
            "vehicle_length_m": self.vehicle_length_m,
            "minimum_gap_m": self.minimum_gap_m,
            "capacity_spacing_m": self.capacity_spacing_m,
        }

    @property
    def movement_keys(self) -> tuple[MovementKey, ...]:
        return tuple(
            dict.fromkeys(
                key
                for phase in self._topology
                for key in phase.movements
            )
        )

    def _capacity(self, lane_id: str) -> float:
        return float(self.bridge.get_lane_length(lane_id)) / self.capacity_spacing_m

    def _build_topology(self) -> tuple[_PhaseTopology, ...]:
        controlled_links = tuple(self.bridge.get_controlled_links(self.tls_id))
        program = self.bridge.get_signal_program(self.tls_id)
        topology = []
        for phase_index, phase in enumerate(program.phases):
            signal_state = str(phase.state)
            keys: list[MovementKey] = []
            for signal_index, signal in enumerate(signal_state):
                if signal not in "Gg" or signal_index >= len(controlled_links):
                    continue
                for link in controlled_links[signal_index] or ():
                    if not link or len(link) < 2:
                        continue
                    key = MovementKey(str(link[0]), str(link[1]))
                    if key not in keys:
                        keys.append(key)
            if any(signal in "Gg" for signal in signal_state) and not keys:
                raise ValueError(
                    f"green phase {phase_index} has no controlled movement"
                )
            topology.append(
                _PhaseTopology(
                    phase_index=phase_index,
                    signal_state=signal_state,
                    nominal_duration=float(phase.duration),
                    movements=tuple(keys),
                )
            )
        return tuple(topology)
