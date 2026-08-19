"""Movement-level traffic state contracts."""

from __future__ import annotations

from dataclasses import dataclass

from core.types import _require_number


@dataclass(frozen=True)
class MovementKey:
    """Immutable, serializable identifier for one allowed lane movement."""

    incoming_lane: str
    outgoing_lane: str


@dataclass(frozen=True)
class MovementState:
    """Measurements for one incoming-to-outgoing lane movement."""

    key: MovementKey
    queue_vehicles: float  #: Queue length in vehicles.
    downstream_queue_vehicles: float  #: Downstream queue length in vehicles.
    incoming_capacity: float  #: Incoming lane capacity in vehicles.
    downstream_capacity: float  #: Downstream lane capacity in vehicles.
    downstream_occupancy: float  #: Downstream occupancy in the range 0..1.
    saturation_rate: float  #: Saturation rate in vehicles per simulation second.
    turn_ratio: float

    def __post_init__(self) -> None:
        _require_number("queue_vehicles", self.queue_vehicles, minimum=0)
        _require_number(
            "downstream_queue_vehicles", self.downstream_queue_vehicles, minimum=0
        )
        _require_number(
            "incoming_capacity", self.incoming_capacity, minimum=0, strict_minimum=True
        )
        _require_number(
            "downstream_capacity", self.downstream_capacity, minimum=0, strict_minimum=True
        )
        _require_number("downstream_occupancy", self.downstream_occupancy, minimum=0, maximum=1)
        _require_number("saturation_rate", self.saturation_rate, minimum=0)
        _require_number("turn_ratio", self.turn_ratio, minimum=0)


@dataclass(frozen=True)
class PhaseMovementState:
    """Movement measurements for one legal signal phase."""

    phase_index: int
    signal_state: str
    movements: tuple[MovementState, ...]
    nominal_duration: float  #: Phase duration in simulation seconds.

    def __post_init__(self) -> None:
        _require_number("phase_index", self.phase_index, minimum=0)
        _require_number("nominal_duration", self.nominal_duration, minimum=0)
