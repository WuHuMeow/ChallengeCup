# Experiments

## 模块职责

`experiments/` 提供单次实验 CLI、批量实验矩阵和基于 `JointState` 的指标计算。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `runner.py` | 算法映射、单次 CLI、流量变体和批量组合运行 |
| `metrics.py` | 每步排队、延误、吞吐量、停车和燃油近似指标 |

## 命令与接口

```powershell
python experiments/runner.py --intersection 1 --algorithm ca_maxpressure `
  --flow-multiplier 1.5 --seed 42 --steps 3600 --output-dir output/exp1
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
- 单次 CLI 输出：`csv/` 指标、`logs/` 逐步与事件日志、非 1.0 倍时的 `variants/` 流量文件。
- `run_batch()` 输出：每次实验的摘要字典列表；每个运行的指标 CSV 写入输出根目录。

## 依赖

- 依赖 `SceneRegistry`、`VariantGenerator`、三种算法和 `SimulationRunner`。
- 真实运行需要 SUMO/TraCI 和有效路口数据。
- 默认输出根目录来自 `config/default.yaml`。

## 已知限制

- `run_batch()` 默认矩阵是 20 路口 × 3 算法 × 2 流量等级 × 3 种子，共 360 次，且串行执行。
- 批量运行没有断点续跑、失败重试或汇总 CSV；返回值仅存在于调用进程。
- `avg_travel_time` 当前为 0，停车与燃油是近似值，不能替代 `tripinfo` 指标。
- 尚未提供配对检验、效应量或显著性分析模块。
