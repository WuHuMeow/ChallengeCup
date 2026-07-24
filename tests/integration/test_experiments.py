"""实验框架接口测试。"""
import inspect
from experiments.runner import run_batch, ALGORITHM_MAP


def test_algorithm_map_has_three_entries():
    assert set(ALGORITHM_MAP.keys()) == {"fixed_time", "actuated", "ca_maxpressure"}


def test_run_batch_signature_accepts_seeds():
    """run_batch 应接受 seeds 参数。"""
    sig = inspect.signature(run_batch)
    assert "seeds" in sig.parameters


def test_parse_args_defaults():
    from experiments.runner import parse_args
    args = parse_args([])
    assert args.seed == 42
    assert args.flow_multiplier == 1.0
    assert args.output_dir is None
    assert args.intersection == "1"
    assert args.steps == 3600
    assert args.algorithm == "fixed_time"


def test_parse_args_custom():
    from experiments.runner import parse_args
    args = parse_args([
        "--seed", "7", "--flow-multiplier", "1.5",
        "--output-dir", "output/x", "--intersection", "16",
        "--steps", "100", "--algorithm", "ca_maxpressure",
    ])
    assert (args.seed, args.flow_multiplier, args.intersection) == (7, 1.5, "16")
    assert args.algorithm == "ca_maxpressure"
