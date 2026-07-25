# 如何跑批量实验（360 组）

## 目的

运行完整实验矩阵（20 路口 x 3 算法 x 2 流量等级 x 3 种子 = 360 次仿真），生成对比数据。

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
  --flow-multiplier 1.5 \
  --seed 42 \
  --steps 36000 \
  --output-dir output/exp1
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
A: 已完成的 CSV 不受影响。重新运行时跳过已有输出文件即可（手动检查 `output/csv/` 目录）。

**Q: 输出文件命名规则？**
A: `{路口}_x{倍率}_{算法}_s{种子}.csv`，如 `16_x1.5_ca_maxpressure_s42.csv`。

**Q: 内存不够？**
A: 用 `python scripts/stress_memory.py 16 36000` 测试峰值。Python 侧峰值应 < 1GB。
