"""实验框架接口测试。"""
import inspect
from experiments.runner import run_batch, ALGORITHM_MAP


def test_algorithm_map_has_three_entries():
    assert set(ALGORITHM_MAP.keys()) == {"fixed_time", "actuated", "ca_maxpressure"}


def test_run_batch_signature_accepts_seeds():
    """run_batch 应接受 seeds 参数。"""
    sig = inspect.signature(run_batch)
    assert "seeds" in sig.parameters
