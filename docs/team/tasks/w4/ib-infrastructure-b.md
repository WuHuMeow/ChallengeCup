# 仿真基础设施 B（IB） W4 任务书

> 周期：8/10（周日）- 8/16（周六） | 核心目标：保障 1.5 倍流量压力测试稳定运行，完善 CloudPolicy 在高压力下的行为

## 本周背景

本周进入 1.5 倍流量压力测试阶段。高流量下 `JointState` 中的车辆列表会暴增，需要防止内存溢出；`CloudPolicy` 在普遍高压力下应给出更激进的参数；同时 AB 接入 EWMA 预测，可能需要 `traci_bridge` 提供历史到达数据。Docker 镜像内的 runner 行为也必须与本地一致。

## 每日任务

### Day 1（8/10 周日）

- [ ] 监控 1.5 倍流量测试中 `experiments/runner.py` 的稳定性，重点观察内存占用
- [ ] 在 `engine/traci_bridge.py` 中对车端字段做采样：高流量下每 3 辆取 1 辆（可配置 `vehicle_sample_rate`）
- [ ] 给 `JointState.vehicles` 设置硬上限（如 500 辆），超出则只保留进口道上的车辆
- [ ] 用 `tracemalloc` 跑一次 1.5 倍流量 3600 步，确认峰值内存可接受

```python
# engine/traci_bridge.py（节选）
class TraCIBridge:
    def __init__(self, scene, sumo_binary="sumo", gui=False,
                 vehicle_sample_rate: int = 1):
        ...
        self.vehicle_sample_rate = vehicle_sample_rate  # 1=全采, 3=每3辆取1

    def _collect_vehicles(self) -> list:
        ids = traci.vehicle.getIDList()
        if self.vehicle_sample_rate > 1:
            ids = ids[:: self.vehicle_sample_rate]
        return [self._vehicle_snapshot(vid) for vid in ids[:500]]
```

**验证：** `python experiments/runner.py --intersection 1 --steps 3600 --flow-multiplier 1.5 --output-dir output/stress` 完整跑完，进程峰值内存 < 1GB（`tracemalloc` 输出）。

### Day 2（8/11 周一）

- [ ] 在 `cloud/cloud_policy.py` 中新增"极高压力"档位：`avg_pressure > 0.8` 时返回更激进参数
- [ ] 验证 1.5 倍流量下云端参数确实下发并影响 CA-MP 行为（日志中能看到参数切换）
- [ ] 在 `CloudPolicy` 中加日志：每次下发参数时打印 `step / avg_pressure / params`
- [ ] 与 AB 确认 CA-MP 收到新参数后行为符合预期

```python
# cloud/cloud_policy.py（节选）
def _compute_params(self, states: list[JointState]) -> dict:
    avg_pressure = self._avg_pressure(states)
    if avg_pressure > 0.8:      # 极高压力（1.5 倍流量）
        params = {"min_green": 20, "max_green": 90, "base_green": 50}
    elif avg_pressure > 0.7:    # 高压力
        params = {"min_green": 15, "max_green": 80, "base_green": 40}
    elif avg_pressure > 0.4:    # 中压力
        params = {"min_green": 10, "max_green": 60, "base_green": 30}
    else:                       # 低压力
        params = {"min_green": 8,  "max_green": 45, "base_green": 25}
    print(f"[CloudPolicy] step={self._step_count} pressure={avg_pressure:.2f} -> {params}")
    return params
```

**验证：** 跑 1.5 倍流量 1800 步，stdout 至少出现 1 次 `pressure=0.8x -> {'min_green': 20, ...}` 日志。

### Day 3（8/12 周二）

- [ ] 协助 AB 接入 EWMA 预测：与 AB 确认历史数据由谁维护（bridge 提供 vs 算法内部维护）
- [ ] 若由 bridge 提供：在 `JointState` 中新增 `arrival_history: list[dict[str, int]]` 字段，记录过去 N 步各进口道到达车辆数
- [ ] 在 `TraCIBridge` 内维护一个 `deque(maxlen=N)` 滚动窗口
- [ ] 写最小单测：连续 tick N+5 步，断言 `arrival_history` 长度始终 ≤ N

```python
# engine/traci_bridge.py（节选）
from collections import deque

class TraCIBridge:
    def __init__(self, scene, ..., history_window: int = 30):
        ...
        self._arrival_history: deque = deque(maxlen=history_window)

    def get_state(self, step: int) -> JointState:
        arrivals = self._count_arrivals()       # {lane_id: count}
        self._arrival_history.append(arrivals)
        return JointState(..., arrival_history=list(self._arrival_history))
```

**验证：** `python -m pytest tests/unit/test_vehicles.py -q` 通过；其中 `test_mock_arrival_history_rolls` 覆盖 arrival_history 滚动窗口，CA-MP 跑 1.5 倍流量时 EWMA 项应有非零输入。

### Day 4（8/13 周三）

- [ ] 1.5 倍压力测试完成后，检查 `simulation_log.csv` 与 `events.csv`
- [ ] 核对：高压力下溢出门控触发频率是否合理（不应每步触发，也不应完全不触发）
- [ ] 核对：云端参数调整是否在 events / 日志中可追溯
- [ ] 修复发现的问题（典型：压力计算分母为 0、参数下发频率过高）

```python
# scripts/audit_stress.py
import csv
events = list(csv.DictReader(open("output/stress/events.csv")))
gates = [e for e in events if e["event"] == "overflow_gate"]
print(f"overflow_gate triggers: {len(gates)} / total steps 3600")
print(f"trigger rate: {len(gates)/3600:.2%}")
```

**验证：** `python scripts/audit_stress.py` 输出触发率在合理区间（参考 1%~15%），不为 0 也不接近 100%。

### Day 5（8/14 周四）

- [ ] 性能复核：1.5 倍流量下单路口 wall-time 是否可接受；若太慢，进一步减少 TraCI 调用
- [ ] 在 Docker 镜像内跑同一路口同一 seed，确认行为与本地一致（CSV 指标完全相同）
- [ ] 与 IA 协调 Docker 镜像中的 SUMO 版本与 `SUMO_HOME` 配置
- [ ] 把 Docker 运行命令补入 `docs/operations/deployment.md`

```bash
# Docker 内外一致性验证
docker run --rm -v $(pwd):/app project:latest \
    python experiments/runner.py --intersection 1 --steps 600 \
    --seed 42 --flow-multiplier 1.5 --output-dir output/docker
diff <(sort output/stress/stats.xml) <(sort output/docker/stats.xml) && echo "consistent"
```

**验证：** 上述 `diff` 无输出且打印 `consistent`。

### Day 6（8/15 周五）

- [ ] 协助 TL 做 W4 集成验证：1.5 倍流量 × 三种算法 × 重点路口（1/11/16）
- [ ] 最终代码 review：确保无硬编码路径、无未处理异常、无 `print` 调试残留（保留日志除外）
- [ ] 提交代码给 TL 合入
- [ ] 更新 `docs/w4_stress_report.md`，记录压力测试结论

```bash
# 静态检查
python -m flake8 engine/ cloud/ experiments/ --max-line-length=100
git grep -n "TODO\|FIXME\|print(" engine/ cloud/  # 确认无残留
```

**验证：** `flake8` 无 error；`git grep` 仅返回允许的日志输出。

### Day 7（8/16 周六）

- [ ] Buffer：修复 W4 遗留问题
- [ ] 协助 DA/DB 准备交付物：提供压力测试期间的日志与事件数据
- [ ] 整理本周提交，确保 tag/分支干净

```bash
git log --oneline -15
git status
```

**验证：** `git status` 干净；本周提交信息清晰可追溯。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 高压力下 JointState 优化 | 8/10 | 1.5 倍流量下不溢出，峰值内存 < 1GB |
| `cloud/cloud_policy.py` 高压力参数 | 8/11 | 1.5 倍流量时参数更激进（min_green=20 档生效） |
| EWMA 接入支持 | 8/12 | AB 能获取过去 N 步到达历史，单测通过 |
| 1.5 倍测试稳定运行 | 8/13 | 无崩溃，溢出门控触发频率合理 |

## 协作对接

- 与 **AB** 确认 EWMA 历史数据接入方案（bridge 提供 vs 算法内部维护）；与 **IA** 协调 Docker 镜像与 SUMO 版本一致性。
- 与 **TL** 配合 W4 集成验证；为 **DA/DB** 提供压力测试日志与事件数据。
