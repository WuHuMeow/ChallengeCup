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
python examples/run_demo.py [路口编号] [算法名] --sumo
```

算法名可选：`fixed_time`、`actuated`、`ca_maxpressure`

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

## 常见问题

**Q: 报错 "traci 未安装"？**
A: 执行 `pip install traci sumolib`，或确认 `SUMO_HOME/tools` 在 Python 路径中。

**Q: 仿真步数怎么换算成秒？**
A: 步长 = 0.1s（路口 11-13、15-20）或 1.0s（路口 1-10）。36000 步 = 3600 秒（1 小时）或 36000 秒。具体看 `engine/configs/demo_N.sumocfg` 中的 `step-length`。

**Q: 输出 CSV 在哪？**
A: 默认在 `output/csv/` 目录下，文件名格式 `{路口}_{算法}.csv`。
