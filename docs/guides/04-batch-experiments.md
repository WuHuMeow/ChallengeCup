# 如何跑批量实验（360 组）

## 目的

运行形式实验矩阵（20 路口 x 3 算法 x 2 流量变体 x 3 种子 = 360 次正常 + 180 次扰动），生成密封对比证据。

## 前置条件

- 已安装 SUMO 并设置 `SUMO_HOME`
- 已安装项目依赖：`pip install -e .`
- 预估时间：约 6-10 小时（取决于机器性能）

## 操作步骤

### 单次实验（CLI）

```bash
python -m experiments.runner \
  --intersection 16 \
  --algorithm ca_maxpressure \
  --flow-multiplier 1.25 \
  --seed 42 \
  --duration-seconds 3600 --warmup-seconds 600 \
  --output-dir output/runs
```

参数说明：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--intersection` | 1 | 路口编号 1-20 |
| `--algorithm` | fixed_time | fixed_time / actuated / ca_maxpressure |
| `--flow-multiplier` | 1.0 | 流量倍率（1.5=压力测试） |
| `--seed` | 42 | 随机种子（保证可复现） |
| `--steps` | 36000 | 仿真步数 |
| `--output-dir` | config 中 paths.output_root | 输出根目录 |

### 批量实验（Python API）

```python
from experiments.runner import run_batch

results = run_batch(
    intersection_ids=["1", "16"],       # None=全部20个
    algorithms=["fixed_time", "ca_maxpressure"],  # None=全部3种
    seeds=[42, 123, 456],
    steps=36000,
)
print(f"完成 {len(results)} 次实验")
```

`run_batch()` 返回 `RunResult` 列表；每次运行使用
`<root>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/` 独立目录。

### 可恢复的 PDF 矩阵（推荐）

```bash
python scripts/run_pdf_matrix.py --profile quick --output-root output/runs/matrix-quick
python scripts/run_pdf_matrix.py --profile formal --duration-seconds 3600 --warmup-seconds 600 --resume --output-root output/runs/formal
```

脚本把索引写入 `matrix.csv` 和 `matrix_state.json`。恢复时仅跳过终态为 `completed`、
达到要求仿真时长且必需产物完整的运行。上述目录均为本地生成内容，当前仓库不保留历史
360 次矩阵产物。

### 使用任务拆分脚本（双机并行）

```bash
python scripts/split_jobs.py           # 查看任务分配
python scripts/split_jobs.py --machine a  # A 机任务清单
python scripts/split_jobs.py --machine b  # B 机任务清单
```

## 示例

只跑路口 16 的 3 种算法对比（快速验证）：
```python
from experiments.runner import run_batch
results = run_batch(intersection_ids=["16"], steps=3600)
```

## 常见问题

**Q: 跑到一半中断了怎么办？**
A: 使用相同 `--output-root` 重新执行 `scripts/run_pdf_matrix.py`。不要按文件名手动跳过，
恢复逻辑会核对 `matrix_state.json`、运行终态、仿真时长和必需产物。

**Q: 输出文件命名规则？**
A: 每次运行位于 `<root>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/`，矩阵根目录另有
`matrix.csv` 和 `matrix_state.json`。

**Q: 内存不够？**
A: 用 `python scripts/stress_memory.py --intersections 16 --steps 3600 --output-root output/runs/stress`
测试峰值。默认阈值为 1024MiB，可通过 `--max-python-mib` 调整。
