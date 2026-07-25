"""seed 透传测试（IB W2）：--seed 必须进入 traci.start 命令。"""
from pathlib import Path

from engine.traci_bridge import TraCIBridge


def test_build_cmd_without_seed():
    b = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"))
    cmd = b._build_cmd()
    assert "--seed" not in cmd


def test_build_cmd_with_seed():
    b = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"), seed=42)
    cmd = b._build_cmd()
    i = cmd.index("--seed")
    assert cmd[i + 1] == "42"


def test_runner_passes_seed_to_bridge():
    from unittest.mock import patch
    from algorithms.fixed_time import FixedTimeAlgorithm
    from core.types import Scene, SceneMeta
    from engine.runner import SimulationRunner

    meta = SceneMeta(
        intersection_id="1", name="t",
        sumo_net=Path("x.net.xml"), sumo_rou=Path("x.rou.xml"),
        sumo_flow=Path("x.flow.xml"), sumo_turn=Path("x.turn.xml"),
        sumo_cfg=Path("x.sumocfg"), timing_xlsx=Path("x.xlsx"),
    )
    with patch("engine.runner.TraCIBridge") as mock_cls:
        SimulationRunner(Scene(meta=meta), FixedTimeAlgorithm(), seed=42)
        assert mock_cls.call_args.kwargs.get("seed") == 42


def test_seed_script_accepts_steps_and_output_root(tmp_path):
    from scripts.check_seed_repro import parse_args

    args = parse_args(["--steps", "12", "--output-root", str(tmp_path)])
    assert args.steps == 12
    assert args.output_root == tmp_path


def test_check_outputs_recurses_and_rejects_missing_files(tmp_path, monkeypatch):
    from scripts import check_outputs

    run_dir = tmp_path / "nested" / "i1" / "fixed_time" / "x1" / "s42"
    run_dir.mkdir(parents=True)
    required = check_outputs.REQUIRED
    for name in required:
        (run_dir / name).write_text("data", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["check_outputs.py", "--root", str(tmp_path)])
    assert check_outputs.main() == 0

    (run_dir / "events.csv").unlink()
    assert check_outputs.main() == 1
