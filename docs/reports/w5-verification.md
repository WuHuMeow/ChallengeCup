# W5 最终验证矩阵

**日期**：2026-07-23

**范围**：G1-G14 全部代码改动就位后的最终回归。结果列如实记录各阶段验证证据；
G9/G12/G13 的详细过程见 `docs/reports/w3-log-audit.md`、相关集成测试及本报告各任务结果。

| # | 任务 | 验证命令 | 结果 |
|---|------|----------|------|
| W1 | capacity / 进口道 / CA-MP 示例 | `python -m pytest tests/ -q`；`python examples/run_ca_max_pressure.py 1 3600` | 66 passed；示例 3600 步跑完退出码 0，QueueState.capacity 由 `TraCIBridge.get_lane_capacity` 实时计算并写入 simulation_log 的 `pressure_<lane>` 列 |
| W2 | CLI 三参数 / 真 seed / 分档 / EdgeChannel / simulation_log | `python experiments/runner.py --help`；`python experiments/runner.py --intersection 1 --algorithm ca_maxpressure --flow-multiplier 1.5 --seed 42 --steps 3600 --output-dir output/exp1`；`python -m pytest tests/unit/test_cloud.py tests/unit/test_edge_channel.py -q` | CLI 六参数（--seed/--flow-multiplier/--output-dir/--intersection/--steps/--algorithm）就位，`--seed` 经 `_build_cmd` 传入 `traci.start --seed`；PRESSURE_TIERS 三档（>0.8→20/120/45；>0.4→15/90/35；常规→10/90/30）实测切换正确，每 60 步周期 logger.info"云端下发参数"；EdgeChannel 过滤+延迟单测通过；simulation_log 每步一行且含 pressure 列 |
| W3 | 断线韧性 / events / 日志审计 | G9 实跑中 `taskkill //F //IM sumo.exe`；G12 十二次批量（3 算法 × 2 倍率 × 2 seed，见 `docs/reports/w3-log-audit.md`） | G9：runner exit=0，日志含 `TraCI 连接断开: ...; closing gracefully`，无 Traceback，finally 正常收尾保存 CSV；`tests/integration/test_resilience.py` 4 例常驻回归。G12：12 次批量零失败零断线，csv/logs/variants 产物齐全，events.csv 完整记录 run_start/run_end 与控制动作 |
| W4 | 采样 / 上限 / arrival / 压力实测 | `python scripts/validation/stress_memory.py` | 峰值内存 9.8 MiB；JointState.vehicles 峰值 22 辆（采样+500 硬上限路径单测覆盖）；arrival_history 滚动 300 步窗口正确；压力分档在 1.5 倍流量长跑中按 avg_pressure 实测切换 |
| W5 | lint / docstring / 文档一致 | `bash scripts/quality/lint_check.sh` | clean（flake8 无 error）；脚本会检查 Git 可用性，并扫描跟踪与未跟踪源码；interface.md / deployment.md 已与代码逐条核对定稿（本任务） |

## 最终回归（2026-07-23）

```bash
python -m pytest tests/ -q && bash scripts/quality/lint_check.sh
# => 66 passed + clean

python examples/run_fixed_time.py 1 && python examples/run_ca_max_pressure.py 1 3600
# => 两者均 3600 步完成，退出码 0
```
