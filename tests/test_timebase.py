import pytest

from core.timebase import SimulationWindow, seconds_for_steps, steps_for_seconds


def test_one_second_scene_uses_3600_steps_for_formal_window():
    assert steps_for_seconds(3600, 1.0) == 3600


def test_tenth_second_scene_uses_36000_steps_for_formal_window():
    assert steps_for_seconds(3600, 0.1) == 36000


def test_conversion_uses_a_ceiling_so_the_window_is_never_shortened():
    assert steps_for_seconds(1.01, 0.1) == 11
    assert seconds_for_steps(11, 0.1) == pytest.approx(1.1)


def test_warmup_cannot_equal_or_exceed_duration():
    with pytest.raises(ValueError):
        SimulationWindow(600, 600)
    with pytest.raises(ValueError):
        SimulationWindow(599, 600)


def test_timebase_rejects_non_positive_step_length():
    with pytest.raises(ValueError):
        steps_for_seconds(10, 0)
    with pytest.raises(ValueError):
        seconds_for_steps(10, -0.1)
