"""Run-scoped traffic safety observations."""

from __future__ import annotations

from dataclasses import dataclass

from core.movements import MovementKey
from core.types import ActionResult, JointState, SafetyEvent, SafetyVehicleState


@dataclass(frozen=True)
class ConflictDefinition:
    """Network foe pair and path distance from each stop line to its conflict."""

    first_link_index: int
    second_link_index: int
    first_distance_after_stopline_m: float
    second_distance_after_stopline_m: float

    def __post_init__(self) -> None:
        if self.first_link_index < 0 or self.second_link_index < 0:
            raise ValueError("conflict link indexes must be non-negative")
        if self.first_link_index == self.second_link_index:
            raise ValueError("conflict link indexes must be distinct")
        if (
            self.first_distance_after_stopline_m < 0
            or self.second_distance_after_stopline_m < 0
        ):
            raise ValueError("conflict distances must be non-negative")


class SafetyObservationCollector:
    def __init__(
        self,
        run_id: str,
        *,
        harsh_braking_mps2: float = 4.5,
        conflict_distance_m: float = 15.0,
        conflict_ttc_delta_seconds: float = 1.0,
        conflict_horizon_seconds: float = 3.0,
        red_light_crossing_distance_m: float = 5.0,
        conflict_definitions: tuple[ConflictDefinition, ...] = (),
    ) -> None:
        self.run_id = run_id
        self.harsh_braking_mps2 = harsh_braking_mps2
        self.conflict_distance_m = conflict_distance_m
        self.conflict_ttc_delta_seconds = conflict_ttc_delta_seconds
        self.conflict_horizon_seconds = conflict_horizon_seconds
        self.red_light_crossing_distance_m = red_light_crossing_distance_m
        self._active_collision_pairs: set[tuple[str, str]] = set()
        self._active_teleports: set[str] = set()
        self._active_conflicts: set[tuple[str, str]] = set()
        self.set_conflict_definitions(conflict_definitions)

    def set_conflict_definitions(
        self,
        definitions: tuple[ConflictDefinition, ...],
    ) -> None:
        self.conflict_definitions = tuple(definitions)
        self._conflict_by_links = {
            frozenset(
                (definition.first_link_index, definition.second_link_index)
            ): definition
            for definition in self.conflict_definitions
        }
        self._active_collision_pairs.clear()
        self._active_teleports.clear()
        self._active_conflicts.clear()

    def observe(
        self,
        previous: JointState | None,
        current: JointState,
        action_results: tuple[ActionResult, ...],
    ) -> tuple[SafetyEvent, ...]:
        events: list[SafetyEvent] = []
        collision_pairs = {
            (collision.collider_id, collision.victim_id)
            for collision in current.collisions
        }
        for collision in current.collisions:
            pair = (collision.collider_id, collision.victim_id)
            if pair in self._active_collision_pairs:
                continue
            events.append(
                self._event(
                    current,
                    "collision",
                    pair,
                    "sumo_collision",
                    1.0,
                    (
                        f"collider={collision.collider_id} "
                        f"victim={collision.victim_id} "
                        f"collision_type={collision.collision_type} "
                        f"lane={collision.lane_id} position_m={collision.position_m}"
                    ).strip(),
                )
            )
        if not current.collisions and current.collision_vehicle_ids:
            legacy_pair = tuple(sorted(set(current.collision_vehicle_ids)))
            collision_pairs.add(legacy_pair)
            if legacy_pair not in self._active_collision_pairs:
                events.append(
                    self._event(
                        current,
                        "collision",
                        legacy_pair,
                        "sumo_collision",
                        1.0,
                    )
                )
        self._active_collision_pairs = collision_pairs
        if previous is not None:
            events.extend(self._red_light_events(previous, current))
            events.extend(self._observed_transition_events(previous, current))
        for result in action_results:
            if (
                not result.accepted
                and result.action.action_type == "set_phase"
                and result.reason_code == "illegal_phase_transition"
            ):
                events.append(
                    self._event(
                        current,
                        "illegal_transition",
                        (result.action.tls_id,),
                        "action_validation",
                        1.0,
                        result.detail,
                    )
                )
        if previous is not None:
            events.extend(self._harsh_braking_events(previous, current))
        for vehicle_id in current.ending_teleport_vehicle_ids:
            self._active_teleports.discard(vehicle_id)
        starting_teleports = current.starting_teleport_vehicle_ids
        if (
            not starting_teleports
            and not current.ending_teleport_vehicle_ids
            and current.teleport_vehicle_ids
        ):
            starting_teleports = current.teleport_vehicle_ids
        for vehicle_id in starting_teleports:
            if vehicle_id in self._active_teleports:
                continue
            events.append(
                self._event(
                    current,
                    "teleport",
                    (vehicle_id,),
                    "sumo_teleport",
                    1.0,
                    "phase=starting",
                )
            )
            self._active_teleports.add(vehicle_id)
        events.extend(self._potential_conflict_events(current))
        return tuple(events)

    def _event(
        self,
        state: JointState,
        event_type: str,
        entity_ids: tuple[str, ...],
        source: str,
        confidence: float,
        detail: str = "",
    ) -> SafetyEvent:
        return SafetyEvent(
            run_id=self.run_id,
            step=int(state.step),
            simulation_seconds=float(state.timestamp),
            event_type=event_type,
            entity_ids=tuple(dict.fromkeys(entity_ids)),
            source=source,
            confidence=confidence,
            detail=detail,
        )

    def _harsh_braking_events(
        self,
        previous: JointState,
        current: JointState,
    ) -> list[SafetyEvent]:
        elapsed = float(current.timestamp) - float(previous.timestamp)
        if elapsed <= 0:
            return []
        before = {vehicle.vehicle_id: vehicle for vehicle in previous.safety_vehicles}
        events = []
        for vehicle in current.safety_vehicles:
            prior = before.get(vehicle.vehicle_id)
            if prior is None:
                continue
            acceleration = (vehicle.speed_mps - prior.speed_mps) / elapsed
            if acceleration <= -self.harsh_braking_mps2:
                events.append(
                    self._event(
                        current,
                        "harsh_braking",
                        (vehicle.vehicle_id,),
                        "derived_speed_delta",
                        1.0,
                        f"acceleration_mps2={acceleration:.6g}",
                    )
                )
        return events

    def _observed_transition_events(
        self,
        previous: JointState,
        current: JointState,
    ) -> list[SafetyEvent]:
        if previous.current_phase == current.current_phase:
            return []
        transition = (previous.current_phase, current.current_phase)
        legal_transitions = set(previous.legal_phase_transitions)
        if not legal_transitions and previous.phase_movements:
            phase_indices = sorted(
                phase.phase_index for phase in previous.phase_movements
            )
            legal_transitions = {
                (phase_index, phase_indices[(index + 1) % len(phase_indices)])
                for index, phase_index in enumerate(phase_indices)
            }
        if transition in legal_transitions:
            return []
        previous_signal = self._phase_signal_state(previous)
        current_signal = self._phase_signal_state(current)
        if not (
            previous_signal
            and current_signal
            and any(signal in "Gg" for signal in previous_signal)
            and any(signal in "Gg" for signal in current_signal)
        ):
            return []
        return [
            self._event(
                current,
                "illegal_transition",
                (current.tls_id,),
                "derived_signal_transition",
                1.0,
                f"phase={previous.current_phase}->{current.current_phase}",
            )
        ]

    @staticmethod
    def _phase_signal_state(state: JointState) -> str | None:
        phase = next(
            (
                candidate
                for candidate in state.phase_movements
                if candidate.phase_index == state.current_phase
            ),
            None,
        )
        return phase.signal_state if phase is not None else None

    def _red_light_events(
        self,
        previous: JointState,
        current: JointState,
    ) -> list[SafetyEvent]:
        before = {vehicle.vehicle_id: vehicle for vehicle in previous.safety_vehicles}
        elapsed = float(current.timestamp) - float(previous.timestamp)
        if elapsed <= 0:
            return []
        all_movements = {
            movement.key
            for phase in previous.phase_movements
            for movement in phase.movements
        }
        teleports = set(current.starting_teleport_vehicle_ids)
        teleports.update(current.ending_teleport_vehicle_ids)
        teleports.update(current.teleport_vehicle_ids)
        events = []
        for vehicle in current.safety_vehicles:
            prior = before.get(vehicle.vehicle_id)
            if prior is None or vehicle.vehicle_id in teleports:
                continue
            transition = MovementKey(prior.lane_id, vehicle.lane_id)
            crossing_window = (
                prior.speed_mps * elapsed + self.red_light_crossing_distance_m
            )
            crossed_while_red = (
                prior.next_tls_id == previous.tls_id
                and prior.next_tls_state in {"r", "R"}
                and self._signal_state(current, prior.next_tls_link_index)
                in {"r", "R"}
                and prior.distance_to_tls_m is not None
                and prior.distance_to_tls_m <= crossing_window
                and prior.lane_id != vehicle.lane_id
                and vehicle.next_tls_id != prior.next_tls_id
            )
            if (
                transition in all_movements
                and crossed_while_red
            ):
                events.append(
                    self._event(
                        current,
                        "red_light",
                        (vehicle.vehicle_id,),
                        "derived_lane_transition",
                        0.9,
                        f"movement={prior.lane_id}->{vehicle.lane_id}",
                    )
                )
                continue
            if crossed_while_red:
                events.append(
                    self._event(
                        current,
                        "red_light",
                        (vehicle.vehicle_id,),
                        "derived_red_signal_crossing",
                        0.9,
                        f"signal_state={prior.next_tls_state}",
                    )
                )
        return events

    @staticmethod
    def _signal_state(state: JointState, link_index: int | None) -> str | None:
        if link_index is None:
            return None
        phase = next(
            (
                candidate
                for candidate in state.phase_movements
                if candidate.phase_index == state.current_phase
            ),
            None,
        )
        if phase is None or link_index < 0 or link_index >= len(phase.signal_state):
            return None
        return phase.signal_state[link_index]

    def _potential_conflict_events(
        self,
        current: JointState,
    ) -> list[SafetyEvent]:
        candidates = [
            vehicle
            for vehicle in current.safety_vehicles
            if vehicle.next_tls_id
            and vehicle.distance_to_tls_m is not None
            and vehicle.next_tls_link_index is not None
            and vehicle.speed_mps > 0
        ]
        events = []
        active_conflicts: set[tuple[str, str]] = set()
        for index, first in enumerate(candidates):
            for second in candidates[index + 1:]:
                if not self._is_potential_conflict(first, second):
                    continue
                pair = tuple(sorted((first.vehicle_id, second.vehicle_id)))
                active_conflicts.add(pair)
                if pair in self._active_conflicts:
                    continue
                events.append(
                    self._event(
                        current,
                        "potential_conflict",
                        (first.vehicle_id, second.vehicle_id),
                        "derived_network_foe_ttc",
                        0.5,
                    )
                )
        self._active_conflicts = active_conflicts
        return events

    def _is_potential_conflict(
        self,
        first: SafetyVehicleState,
        second: SafetyVehicleState,
    ) -> bool:
        if (
            first.next_tls_id != second.next_tls_id
            or first.lane_id == second.lane_id
            or first.next_tls_link_index == second.next_tls_link_index
        ):
            return False
        link_pair = frozenset(
            (first.next_tls_link_index, second.next_tls_link_index)
        )
        definition = self._conflict_by_links.get(link_pair)
        if definition is None:
            return False
        if first.next_tls_link_index == definition.first_link_index:
            first_offset = definition.first_distance_after_stopline_m
            second_offset = definition.second_distance_after_stopline_m
        else:
            first_offset = definition.second_distance_after_stopline_m
            second_offset = definition.first_distance_after_stopline_m
        first_ttc = (
            float(first.distance_to_tls_m) + first_offset
        ) / first.speed_mps
        second_ttc = (
            float(second.distance_to_tls_m) + second_offset
        ) / second.speed_mps
        return (
            max(first_ttc, second_ttc) <= self.conflict_horizon_seconds
            and abs(first_ttc - second_ttc) <= self.conflict_ttc_delta_seconds
        )
