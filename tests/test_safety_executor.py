import importlib

import pytest

from core.movements import PhaseMovementState
from core.types import ActionResult, ControlAction, JointState
from engine.mock_bridge import MockBridge


def _phases() -> tuple[PhaseMovementState, ...]:
    return (
        PhaseMovementState(0, "Grr", (), 30.0),
        PhaseMovementState(1, "yrr", (), 3.0),
        PhaseMovementState(2, "rrr", (), 1.0),
        PhaseMovementState(3, "rGG", (), 30.0),
    )


def _state(*, current_phase: int = 0, elapsed: float = 30.0) -> JointState:
    return JointState(
        step=100,
        timestamp=12.5,
        tls_id="tls",
        current_phase=current_phase,
        current_phase_name=f"p{current_phase}",
        elapsed_phase_time=elapsed,
        phase_movements=_phases(),
        legal_phase_transitions=((0, 1), (1, 2), (2, 3)),
    )


def _program_action(
    phases: list[dict[str, object]] | None = None,
) -> ControlAction:
    return ControlAction(
        "tls",
        "set_program",
        {
            "program_id": "fixed",
            "phases": phases
            if phases is not None
            else [
                {"duration": 30.0, "state": "Grr"},
                {"duration": 3.0, "state": "yrr"},
                {"duration": 1.0, "state": "rrr"},
            ],
        },
        "install frozen fixed-time plan",
    )


def _executor():
    return importlib.import_module("engine.safety_executor").SafetyExecutor()


def _bridge(*, current_phase: int = 0) -> MockBridge:
    bridge = MockBridge(tls_id="tls", phase_count=4)
    bridge._current_step = current_phase
    return bridge


def _phase_and_duration_actions() -> list[ControlAction]:
    return [
        ControlAction("tls", "set_phase", 3, "higher pressure"),
        ControlAction("tls", "set_phase_duration", 30.0, "dynamic green"),
    ]


class _PrivateSinkBridge:
    def __init__(self):
        self.written = []

    def _apply_actions(self, actions):
        self.written.extend(actions)
        return [ActionResult(action, True, "applied") for action in actions]


def test_next_transition_returns_the_first_yellow_in_simulation_seconds():
    transition = _executor().next_transition(0, 3, _phases())

    assert transition == (1, 3.0)


def test_next_transition_advances_from_yellow_to_all_red():
    transition = _executor().next_transition(1, 3, _phases())

    assert transition == (2, 1.0)


def test_phase_change_before_min_green_is_rejected_without_a_signal_write():
    state = _state(elapsed=9.5)
    bridge = _bridge()
    action = ControlAction("tls", "set_phase", 3, "higher pressure")

    results = _executor().apply([action], state, bridge)

    assert isinstance(results, tuple)
    assert results[0].action is action
    assert results[0].accepted is False
    assert results[0].reason_code == "minimum_green_violation"
    assert "min_green" in results[0].detail
    assert bridge._applied_actions == []


def test_phase_change_inserts_yellow_and_preserves_action_result_correlation():
    state = _state(elapsed=10.0)
    bridge = _bridge()
    actions = _phase_and_duration_actions()

    results = _executor().apply(actions, state, bridge)

    assert [result.action for result in results] == actions
    assert [result.accepted for result in results] == [True, True]
    assert [
        (action.action_type, action.value) for action in bridge._applied_actions
    ] == [
        ("set_phase", 1),
        ("set_phase_duration", 3.0),
    ]


def test_direct_yellow_request_uses_the_nominal_clearance_duration():
    state = _state(elapsed=10.0)
    bridge = _bridge()
    actions = [
        ControlAction("tls", "set_phase", 1, "direct clearance request"),
        ControlAction("tls", "set_phase_duration", 0.1, "unsafe shortcut"),
    ]

    results = _executor().apply(actions, state, bridge)

    assert [result.action for result in results] == actions
    assert [result.accepted for result in results] == [True, False]
    assert results[1].reason_code == "clearance_duration_corrected"
    assert "nominal_duration=3" in results[1].detail
    assert [
        (applied.action_type, applied.value) for applied in bridge._applied_actions
    ] == [
        ("set_phase", 1),
        ("set_phase_duration", 3.0),
    ]


def test_yellow_cannot_be_shortened_before_its_simulation_second_boundary():
    state = _state(current_phase=1, elapsed=2.5)
    bridge = _bridge(current_phase=1)
    action = ControlAction("tls", "set_phase", 3)

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "yellow_clearance_violation"
    assert bridge._applied_actions == []


def test_completed_yellow_inserts_all_red_with_its_own_duration():
    state = _state(current_phase=1, elapsed=3.0)
    bridge = _bridge(current_phase=1)
    action = ControlAction("tls", "set_phase", 3)

    result = _executor().apply([action], state, bridge)[0]

    assert result.action is action
    assert result.accepted is True
    assert [
        (applied.action_type, applied.value) for applied in bridge._applied_actions
    ] == [
        ("set_phase", 2),
        ("set_phase_duration", 1.0),
    ]


def test_completed_yellow_routes_through_an_unavoidable_intermediate_green():
    phases = (
        PhaseMovementState(0, "Grr", (), 30.0),
        PhaseMovementState(1, "yrr", (), 3.0),
        PhaseMovementState(2, "rGr", (), 30.0),
        PhaseMovementState(3, "ryr", (), 3.0),
        PhaseMovementState(4, "rrG", (), 30.0),
    )
    state = JointState(
        step=10,
        timestamp=10.0,
        tls_id="tls",
        current_phase=1,
        current_phase_name="p1",
        elapsed_phase_time=3.0,
        phase_movements=phases,
        legal_phase_transitions=((0, 1), (1, 2), (2, 3), (3, 4)),
    )
    bridge = MockBridge(tls_id="tls", phase_count=5)
    bridge._current_step = 1
    actions = [
        ControlAction("tls", "set_phase", 4, "selected final green"),
        ControlAction("tls", "set_phase_duration", 30.0, "selected duration"),
    ]

    results = _executor().apply(actions, state, bridge)

    assert [result.action for result in results] == actions
    assert [result.accepted for result in results] == [True, True]
    assert [
        (applied.action_type, applied.value) for applied in bridge._applied_actions
    ] == [
        ("set_phase", 2),
        ("set_phase_duration", 30.0),
    ]


def test_unavoidable_intermediate_green_requires_a_safe_nominal_duration():
    phases = (
        PhaseMovementState(0, "Grr", (), 30.0),
        PhaseMovementState(1, "yrr", (), 3.0),
        PhaseMovementState(2, "rGr", (), 9.9),
        PhaseMovementState(3, "ryr", (), 3.0),
        PhaseMovementState(4, "rrG", (), 30.0),
    )
    state = JointState(
        step=10,
        timestamp=10.0,
        tls_id="tls",
        current_phase=1,
        current_phase_name="p1",
        elapsed_phase_time=3.0,
        phase_movements=phases,
        legal_phase_transitions=((0, 1), (1, 2), (2, 3), (3, 4)),
    )
    bridge = MockBridge(tls_id="tls", phase_count=5)
    bridge._current_step = 1
    actions = [
        ControlAction("tls", "set_phase", 4, "selected final green"),
        ControlAction("tls", "set_phase_duration", 30.0, "selected duration"),
    ]

    results = _executor().apply(actions, state, bridge)

    assert [result.accepted for result in results] == [False, False]
    assert [result.reason_code for result in results] == [
        "minimum_green_violation",
        "phase_change_rejected",
    ]
    assert bridge._applied_actions == []


def test_all_red_cannot_be_shortened_before_its_simulation_second_boundary():
    state = _state(current_phase=2, elapsed=0.5)
    bridge = _bridge(current_phase=2)
    action = ControlAction("tls", "set_phase", 3)

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "all_red_clearance_violation"
    assert bridge._applied_actions == []


def test_standalone_duration_cannot_shorten_the_remaining_yellow_clearance():
    state = _state(current_phase=1, elapsed=2.5)
    bridge = _bridge(current_phase=1)
    action = ControlAction("tls", "set_phase_duration", 0.1)

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "yellow_clearance_violation"
    assert bridge._applied_actions == []


def test_standalone_duration_cannot_shorten_the_remaining_all_red_clearance():
    state = _state(current_phase=2, elapsed=0.5)
    bridge = _bridge(current_phase=2)
    action = ControlAction("tls", "set_phase_duration", 0.1)

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "all_red_clearance_violation"
    assert bridge._applied_actions == []


def test_standalone_duration_cannot_shorten_the_remaining_minimum_green():
    state = _state(current_phase=0, elapsed=2.0)
    bridge = _bridge(current_phase=0)
    action = ControlAction("tls", "set_phase_duration", 0.1)

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "minimum_green_violation"
    assert bridge._applied_actions == []


def test_new_green_duration_must_satisfy_the_full_minimum_green():
    state = _state(current_phase=2, elapsed=1.0)
    bridge = _bridge(current_phase=2)
    actions = [
        ControlAction("tls", "set_phase", 3, "enter target green"),
        ControlAction("tls", "set_phase_duration", 9.9, "short target green"),
    ]

    results = _executor().apply(actions, state, bridge)

    assert [result.accepted for result in results] == [False, False]
    assert results[0].reason_code == "invalid_transition_duration"
    assert results[1].reason_code == "minimum_green_violation"
    assert bridge._applied_actions == []


def test_unpaired_new_green_requires_a_safe_nominal_duration():
    phases = (
        PhaseMovementState(0, "rr", (), 1.0),
        PhaseMovementState(1, "Gr", (), 9.9),
    )
    state = JointState(
        step=10,
        timestamp=10.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=1.0,
        phase_movements=phases,
        legal_phase_transitions=((0, 1),),
    )
    bridge = _PrivateSinkBridge()
    action = ControlAction("tls", "set_phase", 1, "short nominal green")

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "minimum_green_violation"
    assert "nominal_duration=9.9" in result.detail
    assert bridge.written == []


def test_program_switch_is_rejected_after_simulation_start():
    state = _state(current_phase=0, elapsed=12.5)
    bridge = _bridge(current_phase=0)
    action = _program_action()

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "unsafe_program_switch"
    assert bridge._applied_actions == []


def test_program_install_requires_a_clean_zero_elapsed_startup_state():
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=1.0,
        phase_movements=_phases(),
        legal_phase_transitions=((0, 1), (1, 2), (2, 3)),
    )
    bridge = _bridge(current_phase=0)

    result = _executor().apply([_program_action()], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "unsafe_program_switch"
    assert bridge._applied_actions == []


def test_frozen_program_definition_is_accepted_only_at_simulation_start():
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=0.0,
        phase_movements=_phases(),
        legal_phase_transitions=((0, 1), (1, 2), (2, 3)),
    )
    bridge = _bridge(current_phase=0)
    action = _program_action()

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is True
    assert bridge._applied_actions == [action]


def test_startup_program_rejects_a_green_shorter_than_the_live_minimum():
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=0.0,
    )
    bridge = _PrivateSinkBridge()
    action = _program_action([
        {"duration": 9.9, "state": "Grr"},
        {"duration": 3.0, "state": "yrr"},
        {"duration": 1.0, "state": "rrr"},
        {"duration": 30.0, "state": "rGr"},
        {"duration": 3.0, "state": "ryr"},
        {"duration": 1.0, "state": "rrr"},
    ])

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "unsafe_startup_program"
    assert "min_green=10" in result.detail
    assert bridge.written == []


def test_startup_program_rejects_a_direct_green_to_green_transition():
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=0.0,
    )
    bridge = _PrivateSinkBridge()
    action = _program_action([
        {"duration": 30.0, "state": "Grr"},
        {"duration": 30.0, "state": "rGr"},
        {"duration": 3.0, "state": "ryr"},
        {"duration": 1.0, "state": "rrr"},
    ])

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "unsafe_startup_program"
    assert "direct green-to-green" in result.detail
    assert bridge.written == []


@pytest.mark.parametrize(
    ("phases", "detail_fragment"),
    [
        (
            [
                {"duration": 30.0, "state": "Grr"},
                {"duration": 1.0, "state": "rrr"},
                {"duration": 30.0, "state": "rGr"},
                {"duration": 3.0, "state": "ryr"},
                {"duration": 1.0, "state": "rrr"},
            ],
            "missing yellow clearance",
        ),
        (
            [
                {"duration": 30.0, "state": "Grr"},
                {"duration": 2.9, "state": "yrr"},
                {"duration": 1.0, "state": "rrr"},
                {"duration": 30.0, "state": "rGr"},
                {"duration": 3.0, "state": "ryr"},
                {"duration": 1.0, "state": "rrr"},
            ],
            "yellow clearance=2.9 requires 3",
        ),
        (
            [
                {"duration": 30.0, "state": "Grr"},
                {"duration": 3.0, "state": "yrr"},
                {"duration": 30.0, "state": "rGr"},
                {"duration": 3.0, "state": "ryr"},
                {"duration": 1.0, "state": "rrr"},
            ],
            "missing all-red clearance",
        ),
        (
            [
                {"duration": 30.0, "state": "Grr"},
                {"duration": 3.0, "state": "yrr"},
                {"duration": 0.9, "state": "rrr"},
                {"duration": 30.0, "state": "rGr"},
                {"duration": 3.0, "state": "ryr"},
                {"duration": 1.0, "state": "rrr"},
            ],
            "all-red clearance=0.9 requires 1",
        ),
    ],
    ids=("missing-yellow", "short-yellow", "missing-all-red", "short-all-red"),
)
def test_startup_program_requires_configured_clearance(
    phases,
    detail_fragment,
):
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=0.0,
    )
    bridge = _PrivateSinkBridge()
    action = _program_action(phases)

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "unsafe_startup_program"
    assert detail_fragment in result.detail
    assert bridge.written == []


def test_startup_program_rejects_yellow_on_an_unrelated_signal():
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=0.0,
    )
    bridge = _PrivateSinkBridge()
    action = _program_action([
        {"duration": 30.0, "state": "Gr"},
        {"duration": 3.0, "state": "ry"},
        {"duration": 1.0, "state": "rr"},
        {"duration": 30.0, "state": "rG"},
        {"duration": 3.0, "state": "yr"},
        {"duration": 1.0, "state": "rr"},
    ])

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "unsafe_startup_program"
    assert "signal_index=0" in result.detail
    assert "missing yellow clearance" in result.detail
    assert bridge.written == []


def test_startup_program_accepts_a_movement_aligned_multi_green_cycle():
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=0.0,
    )
    bridge = _PrivateSinkBridge()
    action = _program_action([
        {"duration": 30.0, "state": "Gr"},
        {"duration": 3.0, "state": "yr"},
        {"duration": 1.0, "state": "rr"},
        {"duration": 30.0, "state": "rG"},
        {"duration": 3.0, "state": "ry"},
        {"duration": 1.0, "state": "rr"},
    ])

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is True
    assert bridge.written == [action]


def test_direct_legal_green_edge_is_rejected_without_a_clearance_path():
    phases = (
        PhaseMovementState(0, "Gr", (), 30.0),
        PhaseMovementState(1, "rG", (), 30.0),
    )
    state = JointState(
        step=10,
        timestamp=10.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=10.0,
        phase_movements=phases,
        legal_phase_transitions=((0, 1),),
    )
    bridge = _PrivateSinkBridge()
    action = ControlAction("tls", "set_phase", 1, "unsafe adjacent green")

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "clearance_path_unavailable"
    assert bridge.written == []


def test_green_change_uses_an_available_clearance_path_before_a_direct_edge():
    phases = (
        PhaseMovementState(0, "Gr", (), 30.0),
        PhaseMovementState(1, "rG", (), 30.0),
        PhaseMovementState(2, "yr", (), 3.0),
    )
    state = JointState(
        step=10,
        timestamp=10.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=10.0,
        phase_movements=phases,
        legal_phase_transitions=((0, 1), (0, 2), (2, 1)),
    )
    bridge = _PrivateSinkBridge()
    action = ControlAction("tls", "set_phase", 1, "target green")

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is True
    assert [(written.action_type, written.value) for written in bridge.written] == [
        ("set_phase", 2),
        ("set_phase_duration", 3.0),
    ]


def test_stale_action_is_rejected_with_a_deterministic_safe_fallback():
    state = _state(current_phase=0, elapsed=12.5)
    bridge = _bridge(current_phase=0)
    action = ControlAction(
        "tls",
        "set_phase",
        3,
        "delayed decision",
        issued_at=10.0,
        expires_at=10.0,
    )

    result = _executor().apply([action], state, bridge)[0]

    assert result.accepted is False
    assert result.reason_code == "stale_action"
    assert "fallback=preserve_current_phase" in result.detail
    assert bridge._applied_actions == []


def test_executor_reads_dynamic_minimum_green_for_each_action_batch():
    minimum = [5.0]
    executor = importlib.import_module("engine.safety_executor").SafetyExecutor(
        lambda: minimum[0]
    )
    state = _state(current_phase=0, elapsed=6.0)
    action = ControlAction("tls", "set_phase", 3, "higher pressure")
    first_bridge = _bridge(current_phase=0)

    first = executor.apply([action], state, first_bridge)[0]
    minimum[0] = 7.0
    second_bridge = _bridge(current_phase=0)
    second = executor.apply([action], state, second_bridge)[0]

    assert first.accepted is True
    assert second.accepted is False
    assert second.reason_code == "minimum_green_violation"
    assert second_bridge._applied_actions == []


def test_fallback_preserves_the_known_current_phase_deterministically():
    actions = _executor().fallback(_state(current_phase=2, elapsed=0.5))

    assert [(action.action_type, action.value) for action in actions] == [
        ("set_phase", 2)
    ]
    assert actions[0].reason == "safety_fallback_preserve_current_phase"


def test_fallback_leaves_fixed_timing_untouched_without_phase_topology():
    state = JointState(
        step=1,
        timestamp=1.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=1.0,
    )

    assert _executor().fallback(state) == []


def test_apply_is_the_public_boundary_for_the_private_bridge_sink():
    state = JointState(
        step=1,
        timestamp=1.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=1.0,
    )
    bridge = _PrivateSinkBridge()
    action = ControlAction("tls", "set_phase_duration", 5.0)

    result = _executor().apply([action], state, bridge)

    assert result == (ActionResult(action, True, "applied"),)
    assert bridge.written[0].value == 5.0


@pytest.mark.parametrize(
    "minimum",
    [0.0, -1.0, float("nan"), float("inf"), float("-inf")],
)
def test_executor_rejects_an_invalid_minimum_green_configuration(minimum):
    with pytest.raises(ValueError, match="min_green_seconds"):
        importlib.import_module("engine.safety_executor").SafetyExecutor(minimum)


def test_plan_derived_startup_program_is_validated_structurally():
    """Official multi-stage plans install; strict policy targets algorithm
    programs, not the frozen official baseline."""
    plan_program = {
        "source": "plan_derived",
        "program_id": "excel:早高峰",
        "phases": [
            {"duration": 50, "state": "GGGGrGrrrGGGGrGrrr"},
            {"duration": 3, "state": "GYYYrGrrrGYYYrGrrr"},
            {"duration": 2, "state": "rrrrrrrrrrrrrrrrrr"},
            {"duration": 23, "state": "GYYYrGrrrGYYYrGrrr"},
            {"duration": 3, "state": "GrrrYGrrrGrrrYGrrr"},
            {"duration": 2, "state": "rrrrrrrrrrrrrrrrrr"},
            {"duration": 52, "state": "GrrrrGrrrGrrrrGrrr"},
            {"duration": 3, "state": "GrrrrGYYrGrrrrGYYr"},
            {"duration": 2, "state": "rrrrrrrrrrrrrrrrrr"},
            {"duration": 25, "state": "GrrrGGrrrGrrrGGrrr"},
            {"duration": 3, "state": "GrrrrGrrYGrrrrGrrY"},
            {"duration": 2, "state": "rrrrrrrrrrrrrrrrrr"},
        ],
    }
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=0.0,
        phase_movements=_phases(),
        legal_phase_transitions=((0, 1), (1, 2), (2, 3)),
    )
    action = ControlAction("tls", "set_program", plan_program, "install plan")

    results = _executor().apply([action], state, _bridge())

    assert results[0].accepted is True, results[0].detail


def test_unmarked_startup_program_stays_strict():
    multistage = {
        "program_id": "manual",
        "phases": [
            {"duration": 50, "state": "GGGGrGrrrGGGGrGrrr"},
            {"duration": 3, "state": "GYYYrGrrrGYYYrGrrr"},
            {"duration": 2, "state": "rrrrrrrrrrrrrrrrrr"},
            {"duration": 23, "state": "GYYYrGrrrGYYYrGrrr"},
            {"duration": 3, "state": "GrrrYGrrrGrrrYGrrr"},
            {"duration": 2, "state": "rrrrrrrrrrrrrrrrrr"},
        ]
    }
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=0.0,
        phase_movements=_phases(),
        legal_phase_transitions=((0, 1), (1, 2), (2, 3)),
    )
    action = ControlAction("tls", "set_program", multistage, "install plan")

    results = _executor().apply([action], state, _bridge())

    assert results[0].accepted is False
    assert results[0].reason_code == "unsafe_startup_program"
