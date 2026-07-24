# 仿真基础设施 B（IB） W2 任务书

> 周期：7/27（周日）- 8/2（周六） | 核心目标：完善云-边-端消息流，为 experiments/runner.py 添加实验参数并确保输出完整

## 本周背景

W1 已经把单路口跑通，本周进入"系统级"工作：实验入口 `experiments/runner.py` 要支持 EX 需要的随机种子、流量倍率、输出目录三组参数；`CloudPolicy` 要从骨架升级为基于全局压力的动态参数下发；同时要在 edge 侧加入 V2X 消息过滤与延迟模拟（PDF 加分项："模拟 V2X 消息的发送、接收、简单延迟"）。本周还开始 `docs/operations/deployment.md` 初稿。

## 每日任务

### Day 1（7/27 周日）

- [ ] 在 `experiments/runner.py` 中新增三个命令行参数：`--seed`、`--flow-multiplier`、`--output-dir`
- [ ] 实现 `--seed`：在 `traci.start()` 命令列表中追加 `["--seed", str(seed)]`
- [ ] 实现 `--flow-multiplier`：采用方案 A——运行前调用 EX 的 `scale_flow.py` 生成临时 `flow.xml`，再传给 SUMO（更简单可靠）
- [ ] 实现 `--output-dir`：把 `tripinfo.xml / stats.xml / traj.xml` 全部写入指定目录
- [ ] 用 `argparse` 的 `--help` 自检参数说明清晰

```python
# experiments/runner.py（节选）
import argparse, subprocess, tempfile
from engine.runner import SimulationRunner

def parse_args():
    p = argparse.ArgumentParser(description="批量仿真实验入口")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--flow-multiplier", type=float, default=1.0)
    p.add_argument("--output-dir", type=str, default=None)
    p.add_argument("--intersection", type=int, default=1)
    p.add_argument("--steps", type=int, default=3600)
    return p.parse_args()

def prepare_flow(scene, multiplier: float) -> str:
    """方案 A：用 scale_flow.py 生成缩放后的临时 flow.xml。"""
    if multiplier == 1.0:
        return scene.meta.sumo_flow
    tmp = tempfile.NamedTemporaryFile(suffix=".flow.xml", delete=False)
    subprocess.run(["python", "scripts/scale_flow.py",
                    scene.meta.sumo_flow, "--factor", str(multiplier),
                    "--output", tmp.name], check=True)
    return tmp.name
```

**验证：** `python experiments/runner.py --help` 列出三个新参数；`python experiments/runner.py --intersection 1 --steps 100 --seed 7 --output-dir output/exp1` 退出码 0，`output/exp1/` 下生成 tripinfo/stats/traj 三个文件。

### Day 2（7/28 周一）

- [ ] 在 `cloud/cloud_policy.py` 中实现 `_compute_params(states)`：根据各路口平均排队压力分档返回 `min_green / max_green / base_green`
- [ ] 把 `predict()` 改为接收 `List[JointState]`（多路口全局视图），每 `update_interval` 步下发一次
- [ ] 与 AB 确认：CA-MP 在 `__init__` 或 `step()` 中接收并应用云端参数
- [ ] 写一个最小单测：构造高/中/低三档压力，断言返回参数正确

```python
# cloud/cloud_policy.py（节选）
import numpy as np
from core.types import JointState

class CloudPolicy:
    def _compute_params(self, states: list[JointState]) -> dict:
        avg_pressure = np.mean([np.mean([q.queue_length for q in s.queues])
                                for s in states])
        if avg_pressure > 0.7:      # 高压力
            return {"min_green": 15, "max_green": 80, "base_green": 40}
        elif avg_pressure > 0.4:    # 中压力
            return {"min_green": 10, "max_green": 60, "base_green": 30}
        else:                       # 低压力
            return {"min_green": 8,  "max_green": 45, "base_green": 25}

    def predict(self, states: list[JointState]):
        self._step_count += 1
        if self._step_count % self.update_interval != 0:
            return None
        return self._compute_params(states)
```

**验证：** `python -m pytest tests/unit/test_cloud.py -q` 全部通过；CA-MP 跑 3600 步时日志中能看到至少 1 次参数更新。

### Day 3（7/29 周二）

- [ ] 在 edge 侧实现 V2X 消息过滤：`on_state_receive()` 只保留属于本路口进口道的 `JointState` 字段
- [ ] 加入 1 步延迟队列（`_delay_buffer`），模拟通信延迟（加分项）
- [ ] 把过滤+延迟模块挂到 `SimulationRunner._tick()` 的状态传递路径上
- [ ] 写注释说明这是 PDF "通信模拟模块" 的实现位置

```python
# engine/edge_channel.py（新增）
from collections import deque
from core.types import JointState

class EdgeChannel:
    """模拟 V2X 消息的发送、接收与简单延迟（PDF 加分项）。"""

    def __init__(self, delay_steps: int = 1):
        self._delay_buffer: deque = deque(maxlen=delay_steps + 1)

    def on_state_receive(self, states: list[JointState],
                         inbound_lanes: set[str]) -> list[JointState]:
        relevant = [s.filter_lanes(inbound_lanes) for s in states]
        self._delay_buffer.append(relevant)
        # 取出 delay_steps 之前那一帧，模拟通信延迟
        return self._delay_buffer[0] if len(self._delay_buffer) > 1 else []
```

**验证：** 单元测试：连续推送 3 帧状态，第 1 帧返回为空、第 2 帧返回第 1 帧内容（延迟 1 步生效）。

### Day 4（7/30 周三）

- [ ] 与 EX 联调 `experiments/runner.py`：确认所有参数组合（seed × flow-multiplier × output-dir）正确工作
- [ ] 跑一次完整单次实验（路口 1，3600 步，flow×1.0），确认 tripinfo/stats/traj 三个文件齐全
- [ ] 验证 `--seed` 可复现：同 seed 跑两次，CSV 指标完全一致
- [ ] 修复联调中发现的 bug（典型：临时 flow.xml 未清理、output-dir 不存在）

```python
# 复现性验证脚本
# scripts/validation/check_seed_repro.py
import subprocess, hashlib

def run(seed):
    subprocess.run(["python", "experiments/runner.py",
                    "--intersection", "1", "--steps", "600",
                    "--seed", str(seed), "--output-dir", f"output/seed_{seed}"],
                   check=True)
    return hashlib.md5(open(f"output/seed_{seed}/stats.xml", "rb").read()).hexdigest()

assert run(42) == run(42), "same seed must be reproducible"
print("seed reproducibility OK")
```

**验证：** `python scripts/validation/check_seed_repro.py` 输出 `seed reproducibility OK`。

### Day 5（7/31 周四）

- [ ] 在 `engine/runner.py` 中新增 `simulation_log.csv` 写入：每步记录 `step, time, phase, queue_*, pressure_*`
- [ ] 字段按方向展开（E/W/N/S），便于 DB 后续做可视化动画
- [ ] 写入路径为 `{output_dir}/simulation_log.csv`，与 tripinfo 同目录
- [ ] 用 csv.writer 缓冲写入，避免每步 flush 拖慢仿真

```python
# engine/runner.py（节选）
import csv

class SimulationRunner:
    def _open_log(self, path: str):
        self._log_f = open(path, "w", newline="")
        self._log_w = csv.writer(self._log_f)
        self._log_w.writerow(["step", "time", "phase",
                              "queue_E", "queue_W", "queue_N", "queue_S",
                              "pressure_E", "pressure_W", "pressure_N", "pressure_S"])

    def _write_log(self, step: int, state, pressure: dict):
        q = state.queue_by_direction()  # {"E": ..., "W": ..., ...}
        self._log_w.writerow([step, state.time, state.phase,
                              q["E"], q["W"], q["N"], q["S"],
                              pressure["E"], pressure["W"],
                              pressure["N"], pressure["S"]])
```

**验证：** 跑 `python experiments/runner.py --intersection 1 --steps 100 --output-dir output/log_test`，`output/log_test/simulation_log.csv` 有 101 行（含表头），列名与上方一致。

### Day 6（8/1 周五）

- [ ] 协助 TL 做 W2 集成验证：三种算法（FixedTime / RuleAdaptive / CA-MP）在路口 1 与路口 16 上各跑一次
- [ ] 确认每次运行都正确输出 simulation_log.csv 与 tripinfo/stats/traj
- [ ] 修复集成验证中暴露的问题
- [ ] 提交代码给 TL 合入

```bash
# 集成验证脚本片段
for algo in fixed_time rule_adaptive ca_mp; do
  for iid in 1 16; do
    python experiments/runner.py --algorithm $algo --intersection $iid \
        --steps 1800 --output-dir output/w2_${algo}_${iid}
  done
done
ls output/w2_*_1/simulation_log.csv | wc -l   # 期望: 3
```

**验证：** 上述循环全部退出码 0；`output/` 下生成 6 个子目录，每个含完整 4 个输出文件。

### Day 7（8/2 周六）

- [ ] Buffer：修复 W2 遗留问题
- [ ] 编写 `docs/operations/deployment.md` 初稿：环境要求（Python / SUMO 版本、依赖包）、安装步骤、运行命令示例
- [ ] Docker 部署章节先放占位（W4 补充）
- [ ] 把本周新增的 `--seed / --flow-multiplier / --output-dir` 写入 deployment.md 的"运行命令示例"

```markdown
<!-- docs/operations/deployment.md 初稿骨架 -->
# 部署与运行

## 环境要求
- Python 3.10+
- SUMO 1.26.0+（设置 `SUMO_HOME`）
- 依赖：`pip install -r requirements.txt`

## 快速开始
```bash
python experiments/runner.py --intersection 1 --steps 3600 \
    --seed 42 --flow-multiplier 1.0 --output-dir output/run1
```

## Docker 部署
（W4 补充）
```

**验证：** 按 deployment.md 的步骤在新虚拟环境中执行，`python experiments/runner.py --help` 可正常运行。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| `experiments/runner.py` 新增参数 | 7/27 | `--seed / --flow-multiplier / --output-dir` 全部可用 |
| `cloud/cloud_policy.py` 动态参数 | 7/28 | 根据压力分档自动调整 min/max/base_green |
| `engine/edge_channel.py` V2X 延迟模拟 | 7/29 | 状态有 1 步延迟，单测通过 |
| `experiments/runner.py` 联调通过 | 7/30 | 单次实验输出完整、seed 可复现 |
| `simulation_log.csv` 输出 | 7/31 | 每步记录相位/排队/压力，列名规范 |
| `docs/operations/deployment.md` 初稿 | 8/2 | 含环境要求、安装、运行命令；Docker 占位 |

## 协作对接

- 与 **EX** 联调 `experiments/runner.py` 参数与 `scale_flow.py` 配合方式；与 **AB** 确认 CloudPolicy 参数下发到 CA-MP 的接入点。
- 与 **TL** 配合 W2 集成验证；为 **DB** 后续可视化提供 `simulation_log.csv` 字段说明。
