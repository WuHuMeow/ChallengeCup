def test_flat_layout_exposes_core_and_algorithm_modules():
    from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
    from core.types import JointState, VehicleState

    assert CAMaxPressureAlgorithm is not None
    assert JointState is not None
    assert VehicleState is not None
