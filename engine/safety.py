"""Run-scoped traffic safety observations."""

from __future__ import annotations

import math

from core.movements import MovementKey
from core.types import ActionResult, JointState, SafetyEvent, SafetyVehicleState


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
    ) -> None:
        self.run_id = run_id
        self.harsh_braking_mps2 = harsh_braking_mps2
        self.conflict_distance_m = conflict_distance_m
        self.conflict_ttc_delta_seconds = conflict_ttc_delta_seconds
        self.conflict_horizon_seconds = conflict_horizon_seconds
        self.red_light_crossing_distance_m = red_light_crossing_distance_m

    def observe(
        self,
        previous: JointState | None,
        current: JointState,
        action_results: tuple[ActionResult, ...],
    ) -> tuple[SafetyEvent, ...]:
        events: list[SafetyEvent] = []
        if current.collision_vehicle_ids:
            events.append(
                self._event(
                    current,
                    "collision",
                    current.collision_vehicle_ids,
                    "sumo_collision",
                    1.0,
                )
            )
        if previous is not None:
            events.extend(self._red_light_events(previous, current))
        for result in action_results:
            if not result.accepted and result.action.action_type == "set_phase":
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
        if current.teleport_vehicle_ids:
            events.append(
                self._event(
                    current,
                    "teleport",
                    current.teleport_vehicle_ids,
                    "sumo_teleport",
                    1.0,
                )
            )
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
            simulation_seconds=float(state.timestamp),
            event_type=event_type,
            entity_ids=tuple(sorted(set(entity_ids))),
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

    def _red_light_events(
        self,
        previous: JointState,
        current: JointState,
    ) -> list[SafetyEvent]:
        before = {vehicle.vehicle_id: vehicle for vehicle in previous.safety_vehicles}
        all_movements = {
            movement.key
            for phase in previous.phase_movements
            for movement in phase.movements
        }
        active_movements = {
            movement.key
            for phase in previous.phase_movements
            if phase.phase_index == previous.current_phase
            for movement in phase.movements
        }
        current_active_movements = {
            movement.key
            for phase in current.phase_movements
            if phase.phase_index == current.current_phase
            for movement in phase.movements
        }
        teleports = set(current.teleport_vehicle_ids)
        events = []
        for vehicle in current.safety_vehicles:
            prior = before.get(vehicle.vehicle_id)
            if prior is None or vehicle.vehicle_id in teleports:
                continue
            transition = MovementKey(prior.lane_id, vehicle.lane_id)
            if (
                transition in all_movements
                and transition not in active_movements
                and transition not in current_active_movements
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
            crossed_red_signal = (
                prior.next_tls_id == previous.tls_id
                and prior.next_tls_state in {"r", "R"}
                and self._signal_state(current, prior.next_tls_link_index)
                in {"r", "R"}
                and prior.distance_to_tls_m is not None
                and prior.distance_to_tls_m <= self.red_light_crossing_distance_m
                and prior.lane_id != vehicle.lane_id
                and vehicle.next_tls_id != prior.next_tls_id
            )
            if crossed_red_signal:
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
        for index, first in enumerate(candidates):
            for second in candidates[index + 1 :]:
                if not self._is_potential_conflict(first, second):
                    continue
                events.append(
                    self._event(
                        current,
                        "potential_conflict",
                        (first.vehicle_id, second.vehicle_id),
                        "derived_spatial_time_proximity",
                        0.5,
                    )
                )
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
        spatial_distance = math.dist(first.position_xy, second.position_xy)
        first_ttc = float(first.distance_to_tls_m) / first.speed_mps
        second_ttc = float(second.distance_to_tls_m) / second.speed_mps
        return (
            spatial_distance <= self.conflict_distance_m
            and max(first_ttc, second_ttc) <= self.conflict_horizon_seconds
            and abs(first_ttc - second_ttc) <= self.conflict_ttc_delta_seconds
        )
