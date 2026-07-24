# 仿真基础设施 B（IB） W3 任务书

> 周期：8/3（周日）- 8/9（周六） | 核心目标：保障 experiments/runner.py 在全量实验中稳定运行，完善日志输出并协助实验组

## 每日任务

### Day 1（8/3 周日）

- [ ] 监控 `experiments/runner.py` 在全量实验（20 路口 × 多算法）中的稳定性，记录任何崩溃日志
- [ ] 在 `engine/traci_bridge.py` 中包裹 `traci.simulationStep()`：捕获 `traci.exceptions.FatalTraCIError`，断开时优雅退出而非崩溃
- [ ] 添加可选自动重连：连续运行超过阈值时关闭并重启 SUMO 进程
- [ ] 在 `SimulationRunner.run()` 外层加 `try/finally`，确保 `bridge.close()` 一定被调用

```python
# engine/traci_bridge.py（节选）
import traci
from traci.exceptions import FatalTraCIError

class TraCIBridge:
    def tick(self) -> bool:
        """推进一步；返回 False 表示仿真已结束/断开。"""
        try:
            traci.simulationStep()
            return True
        except FatalTraCIError as e:
            print(f"[TraCIBridge] connection lost: {e}; closing gracefully")
            self.close()
            return False

    def close(self) -> None:
        try:
            traci.close()
        except Exception:
            pass  # 已断开则忽略
```

**验证：** 手动 `taskkill /F /IM sumo.exe`（或 `pkill sumo`）后，runner 不抛未捕获异常，退出码 0 且日志含 "closing gracefully"。

### Day 2（8/4 周一）

- [ ] 确认所有 20 路口的 `simulation_log.csv` 列名与格式一致（方向列按路口实际进口数自适应）
- [ ] 在 `engine/runner.py` 中新增溢出门控事件日志：每次触发追加一行到 `{output_dir}/events.csv`
- [ ] 事件字段：`step, time, event, detail`，detail 用 `key=value` 串拼接（lane / occupancy / forced_phase）
- [ ] 与 DA 确认事件日志格式满足报告引用需求

```python
# engine/runner.py（节选）
def _log_overflow_event(self, step: int, time: float,
                        lane_id: str, occupancy: float, forced_phase: int):
    self._events_w.writerow([
        step, time, "overflow_gate",
        f"lane={lane_id}, occupancy={occupancy:.2f}, forced_phase={forced_phase}",
    ])
    self._events_f.flush()  # 事件稀疏，立即落盘
```

**验证：** 跑一个高压力短仿真后，`output/.../events.csv` 至少含 1 行 `overflow_gate` 记录，detail 字段三个 key 完整。

### Day 3（8/5 周二）

- [ ] 协助 EX 处理 `experiments/runner.py` 运行中的问题（参数、路径、超时）
- [ ] 性能优化：在 `get_state()` 中跳过非必要的逐车采集（`vehicle.getPosition` 等），仅 GUI 模式才采车端字段
- [ ] 减少 TraCI 调用：把 `lane.getLastStepHaltingNumber` 等批量改用 `traci.lane.getIDList()` + 一次性订阅
- [ ] 测量优化前后单步耗时（目标：0.1s 步长路口运行时间可接受）

```python
# engine/traci_bridge.py（节选：按需采集）
def get_state(self, step: int, full_vehicle_data: bool = False) -> JointState:
    queues = self._collect_queues()              # 始终采集
    flows = self._read_flows()                   # 始终采集
    vehicles = (self._collect_vehicles()         # 仅 GUI/调试模式
                if full_vehicle_data else [])
    return JointState(step=step, time=self.current_time,
                      queues=queues, flows=flows, vehicles=vehicles,
                      phase=traci.trafficlight.getPhase(self._tls_id))
```

**验证：** `python -m timeit -n 5 -r 3 "from engine.traci_bridge import TraCIBridge; ..."` 优化后单步耗时下降 ≥30%；0.1s 步长路口（如 11）跑 3600 仿真秒 wall-time 可接受。

### Day 4（8/6 周三）

- [ ] 确认所有 20 路口实验的 `simulation_log.csv` 已正确生成
- [ ] 抽查 5 个路口（建议 1 / 5 / 11 / 16 / 20）的日志：相位切换是否合理、溢出门控事件是否记录
- [ ] 把抽查结果写入 `docs/reports/w3-log-audit.md`（DA 后续可引用）
- [ ] 发现异常立即修复并重跑该路口

```python
# scripts/audit_logs.py
import csv, glob
for path in glob.glob("output/*/simulation_log.csv"):
    rows = list(csv.DictReader(open(path)))
    phases = {r["phase"] for r in rows}
    overflow = sum(1 for r in rows if r.get("overflow_gate") == "1")
    print(f"{path}: rows={len(rows)} phases={sorted(phases)} overflow={overflow}")
```

**验证：** `python scripts/audit_logs.py` 输出 20 行，每行 `rows>0`、`phases` 至少含 2 个不同值。

### Day 5（8/7 周四）

- [ ] 完善 `docs/operations/deployment.md`：完整安装步骤（Windows / Linux 双平台）、环境变量配置（`SUMO_HOME`）
- [ ] 添加运行命令示例：单路口、批量、Docker（与 IA 协调镜像内容）
- [ ] 添加输出文件说明：`tripinfo.xml / stats.xml / traj.xml / simulation_log.csv / events.csv` 各字段含义
- [ ] 这是 PDF 硬性要求的"详细的部署运行说明文档"，必须可被陌生人复现

```markdown
<!-- docs/operations/deployment.md 章节示例 -->
## 输出文件说明
| 文件 | 内容 | 用途 |
|------|------|------|
| tripinfo.xml | 每辆车完整行程信息 | 计算延误、停车次数 |
| stats.xml | 仿真级聚合指标 | 算法对比 |
| traj.xml | 车辆轨迹 | 可视化 |
| simulation_log.csv | 每步相位/排队/压力 | DB 动画 |
| events.csv | 溢出门控等离散事件 | DA 报告引用 |
```

**验证：** 让一位未参与本项目的同学按 deployment.md 从零跑通路口 1，全程无需口头补充。

### Day 6（8/8 周五）

- [ ] 协助 TL 做 W3 集成验证：三种算法 × 路口 1/11/16 全部跑通
- [ ] 验证可复现性：clone 仓库到全新目录，按 deployment.md 跑通
- [ ] 修复集成验证暴露的问题
- [ ] 提交代码给 TL

```bash
# 可复现性验证
git clone <repo> /tmp/fresh && cd /tmp/fresh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python experiments/runner.py --intersection 1 --steps 600 --output-dir output/repro
```

**验证：** 上述命令链全部退出码 0，`output/repro/` 含完整 4 个输出文件。

### Day 7（8/9 周六）

- [ ] Buffer：修复 W3 遗留问题
- [ ] 整理本周日志审计与性能优化记录，归档到 `docs/w3_summary.md`
- [ ] 提交代码给 TL，准备 W4 高压力测试

```bash
git status                       # 确认无未提交修改
git log --oneline -10            # 确认本周提交完整
```

**验证：** `git status` 输出 `nothing to commit, working tree clean`。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| TraCI 异常处理 | 8/3 | 长时间运行不崩溃，断开时优雅退出 |
| `events.csv` 溢出门控日志 | 8/4 | 触发事件有记录，字段完整 |
| `engine/traci_bridge.py` 性能优化 | 8/5 | 0.1s 路口运行时间可接受，单步耗时下降 ≥30% |
| `docs/operations/deployment.md` 完善版 | 8/7 | Windows/Linux 双平台完整部署指南，含输出文件说明 |

## 协作对接

- 与 **EX** 配合处理批量实验中的运行问题；与 **DA** 对齐 `events.csv` 字段以满足报告引用。
- 与 **IA** 协调 Docker 镜像内容；与 **TL** 配合 W3 集成验证与可复现性测试。
