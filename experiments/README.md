# Experiments

## 模块职责

`experiments/` 提供单次实验 CLI、批量实验矩阵和基于 `JointState` 的指标计算。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `runner.py` | 算法映射、单次 CLI 和批量组合运行 |
| `metrics.py` | 每步排队、延误、吞吐量、停车和燃油近似指标 |
| `summary.py` | 从完整运行产物写入汇总指标 |
| `tuning.py` | CA-MP 校准/留出划分和结果文件写入 |

## 命令与接口

```powershell
python -m experiments.runner --intersection 1 --algorithm ca_maxpressure `
  --flow-multiplier 1.5 --seed 42 --steps 3600 --output-dir output/runs/exp1
```

```python
from experiments.runner import run_batch

results = run_batch(
    intersection_ids=["1", "2"],
    algorithms=["fixed_time", "actuated", "ca_maxpressure"],
    seeds=[42, 123, 456],
    steps=3600,
)
```

## 输入与输出

- 输入：路口 ID、算法名称、流量倍率/等级、随机种子、步数和输出根目录。
- 单次 CLI 在 `--output-dir`（未指定时为 `output/runs/`）下运行时创建
  `<root>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/`，其中包含指标、逐步日志、事件、SUMO XML、
  `run_metadata.json` 和完成时的 `summary.json`。
- `run_batch()` 返回 `RunResult` 列表；每个请求使用同一运行作用域布局。`output/runs/exp1` 只是命令创建的示例目录，
  不代表当前保留的输出。

## 依赖

- 依赖 `SceneRegistry`、`VariantGenerator`、三种算法和 `SimulationRunner`。
- 真实运行需要 SUMO/TraCI 和有效路口数据。
- 默认输出根目录来自 `config/default.yaml`。

## 已知限制

- `run_batch()` 默认矩阵是 20 路口 × 3 算法 × 2 流量等级 × 3 种子，共 360 次，且串行执行。
- `run_batch()` 串行执行，没有断点续跑、失败重试或汇总 CSV；返回值仅存在于调用进程。可恢复的 PDF 矩阵入口是
  `scripts/run_pdf_matrix.py`。
- `avg_travel_time` 当前为 0，停车与燃油是近似值，不能替代 `tripinfo` 指标。
- 尚未提供配对检验、效应量或显著性分析模块。
