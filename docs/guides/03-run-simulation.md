# 如何运行单路口仿真

## 目的

对指定路口运行一次完整仿真，验证算法效果或调试问题。

## 前置条件

- 已安装 SUMO 并设置 `SUMO_HOME` 环境变量（参见 `docs/sumo_env_setup.md`）
- 已安装项目依赖：`pip install -e .`
- 或：不安装 SUMO，使用 Mock 模式验证调用链

## 操作步骤

### 方式一：Mock 模式（无需 SUMO）

```bash
python examples/run_demo.py [路口编号] [算法名]
```

示例：
```bash
python examples/run_demo.py 16 ca_maxpressure
```

输出 6 步链路验证结果，10 步仿真指标。

### 方式二：真实 SUMO 仿真

```bash
python examples/run_fixed_time.py [路口编号]        # 固定配时基线
python examples/run_ca_max_pressure.py [路口编号] [步数]  # CA-MP 算法
```

示例：
```bash
python examples/run_fixed_time.py 1
python examples/run_ca_max_pressure.py 16 36000
```

### 方式三：通用入口（支持所有算法）

```bash
python -m experiments.runner --intersection [路口编号] --algorithm [算法名] \
  --steps 36000 --output-dir output/runs
```

算法名可选：`fixed_time`、`actuated`、`ca_maxpressure`。这是推荐入口，会创建带
`run_id` 的独立目录并写入终态、精确汇总和 SUMO 原始输出。

## 示例

运行路口 16（24m 短边，CA-MP 效果最显著）：
```bash
python examples/run_ca_max_pressure.py 16 36000
```

输出：
```
运行路口 16: demo_16 (CA-MP)
仿真完成，共记录 60 条指标快照
CSV 输出: output/csv/16_ca_maxpressure.csv
```

上例使用的是直接示例脚本，因此只生成简化 CSV；该目录由命令运行时创建，不随仓库保留。
需要可审计产物时使用方式三。

## 常见问题

**Q: 报错 "traci 未安装"？**
A: 执行 `pip install traci sumolib`，或确认 `SUMO_HOME/tools` 在 Python 路径中。

**Q: 仿真步数怎么换算成秒？**
A: 步长 = 0.1s（路口 11-13、15-20）或 1.0s（路口 1-10）。36000 步 = 3600 秒（1 小时）或 36000 秒。具体看 `engine/configs/demo_N.sumocfg` 中的 `step-length`。

**Q: 输出文件在哪？**
A: 通用入口写入 `output/runs/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/`；直接示例脚本
仍写入运行时生成的 `output/csv/{路口}_{算法}.csv`。
