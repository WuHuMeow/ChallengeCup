# W3 日志审计报告

**日期**：2026-07-23

**范围**：路口 1 × 3 算法（fixed_time / actuated / ca_maxpressure）× 2 流量倍率（1.0 / 1.5）× 2 seed（42 / 7）= 12 次实跑，每次 600 步，输出目录 `output/w3_audit/`。

## 一、批量运行结果

命令：

```bash
for algo in fixed_time actuated ca_maxpressure; do for mult in 1.0 1.5; do for seed in 42 7; do
  python experiments/runner.py --intersection 1 --steps 600 --algorithm $algo \
    --flow-multiplier $mult --seed $seed --output-dir output/w3_audit || echo "FAILED: $algo $mult $seed"
done; done; done
```

无任何 `FAILED` 行，12 次全部成功收尾（exit 0）。指标快照间隔 60 步，600 步 → 每 CSV 10 个数据行；`simulation_log` 为逐步日志，600 个数据行。行数均完整、无截断。

| 算法 | 倍率 | seed | 结果 | 指标 CSV 数据行 | simulation_log 行 | events 行 |
|------|------|------|------|------|------|------|
| fixed_time | 1.0 | 42 | 成功 | 10 | 600 | 2（run_start/run_end） |
| fixed_time | 1.0 | 7 | 成功 | 10 | 600 | 2 |
| fixed_time | 1.5 | 42 | 成功 | 10 | 600 | 2 |
| fixed_time | 1.5 | 7 | 成功 | 10 | 600 | 2 |
| actuated | 1.0 | 42 | 成功 | 10 | 600 | 48 |
| actuated | 1.0 | 7 | 成功 | 10 | 600 | 48 |
| actuated | 1.5 | 42 | 成功 | 10 | 600 | 48 |
| actuated | 1.5 | 7 | 成功 | 10 | 600 | 48 |
| ca_maxpressure | 1.0 | 42 | 成功 | 10 | 600 | 602（600 条 set_phase） |
| ca_maxpressure | 1.0 | 7 | 成功 | 10 | 600 | 602 |
| ca_maxpressure | 1.5 | 42 | 成功 | 10 | 600 | 602 |
| ca_maxpressure | 1.5 | 7 | 成功 | 10 | 600 | 602 |

产物清点：`output/w3_audit/csv/` 12 个指标 CSV（命名含倍率与 seed，如 `1_x1.5_ca_maxpressure_s7.csv`），`output/w3_audit/logs/` 24 个日志 CSV（12 个 `*_simulation_log.csv` + 12 个 `*_events.csv`），与预期一致。

**抽查结论**：`1_x1.5_ca_maxpressure_s7_events.csv` 含 600 条 `set_phase` 动作事件（detail 形如 `MVI: 最大排队方向 -E1_0`）+ run_start/run_end。CA-MP 的 MVI 桩返回的相位值为车道 ID（非法相位值），被 bridge 容错校验跳过（控制台 WARNING：`set_phase 值非法，已跳过: value='E0_0' reason=MVI: ...`），但动作本身仍完整记入 events.csv——日志链路与容错路径均按设计工作。指标 CSV 与 simulation_log 表头/列数正常，逐步时间戳连续无断档。

## 二、崩溃与重连记录

| 项 | 次数 |
|----|------|
| 进程崩溃 / 非零退出 | 0 |
| 未捕获 Traceback | 0 |
| TraCI 断线（closing gracefully） | 0 |
| 自动重连触发 | 0 |

12 次运行全程无断线、无重连，控制台仅有上述 CA-MP set_phase 容错 WARNING（预期行为，非故障）。

## 三、断线韧性测试结论引用（Task 11）

本批次未触发断线路径，韧性结论来自 Task 11 的真实断线实证（详见 `.superpowers/sdd/task-11-report.md`）：仿真运行中 `taskkill //F //IM sumo.exe` 强杀 SUMO 进程，runner 以 `exit=0` 优雅退出，日志含 `TraCI 连接断开: Connection closed by SUMO.; closing gracefully`，无 Traceback，且正常走完 finally 收尾（保存 CSV）。实证覆盖了 `engine.runner._tick`（异常从 `get_state()` 抛出）与 `engine.traci_bridge.step`（内部捕获返回 None）双路径；单测 `tests/integration/test_resilience.py` 4 例常驻回归。

## 四、内存观察

本次 12 次 600 步小规模实跑未做定量内存采集（任务管理器观察无异常增长迹象）。正式内存审计（tracemalloc 采样 + 1.5 倍压力 3600 步长跑）按计划留待 W4。

## 五、遗留风险

- **CA-MP MVI 桩的 set_phase 值非法（归 AB）**：MVI 桩以车道 ID 作为相位值返回，被 bridge 容错跳过，即 CA-MP 当前并未真正改变信号相位，其指标不具备算法对比意义。动作事件已完整记录，问题归属 AB（算法行为），待真实 CA-MP 相位映射实现后消除。
- **变体 `-a` 叠加语义注意项**：`--algorithm` 与场景变体参数叠加时的语义（谁覆盖谁）需在后续多场景批量中保持一致，避免同一输出目录下不同变体互相覆盖 CSV（当前命名已含倍率/seed，不含变体维度）。
- **控制台 WARNING 编码**：Windows GBK 控制台下 WARNING 中的中文显示为乱码（日志文件本身为 UTF-8，不受影响），仅影响实时观感。
