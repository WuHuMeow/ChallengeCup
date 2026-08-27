# 证据合同

每个 run 目录包含以下文件；缺任一必需文件即视为产物不完整，`--resume` 会
重新运行该 run。

| 文件 | 内容 |
| --- | --- |
| `manifest.json` | 运行请求与推导参数（intersection、algorithm、duration/warmup 秒数、seed、step_length、derived_steps、code_commit） |
| `provenance.json` | 溯源：输入文件哈希、SUMO/Python 版本、命令行、运行身份 |
| `status.json` | 生命周期状态（queued/running/completed/failed + `started_at`/`ended_at`） |
| `simulation_log.csv` | 每步状态序列（时间、车辆数、相位、排队等） |
| `events.csv` | 事件流（安全事件、相位转换、动作） |
| `metrics.csv` | 逐步指标（见下） |
| `summary.json` | 汇总指标（聚合自 tripinfo 与队列快照） |
| `tripinfo.xml` / `stats.xml` / `traj.xml` / `collisions.xml` | SUMO 原生输出 |
| `variants/` | 该 run 实际使用的流量变体定义 |

## 字段与单位

| 字段 | 单位 | 说明 |
| --- | --- | --- |
| `duration_seconds` / `requested_seconds` / `final_simulation_time` | s | 仿真时间 |
| `warmup_seconds` | s | 预热窗口（统计剔除） |
| `travel_time` | s | 车辆旅行时间 |
| `queue_length` | m | 车道队列长度 |
| `speed` | m/s | 车辆速度 |
| `fuel_consumed` | ml | 燃油 |
| `co2_emissions` | g | CO2 排放 |
| `harsh_braking_count` / `red_light_violation_count` / `conflict_count` | 次 | 安全事件计数 |
| `completed_vehicles` / `total_vehicles` | 辆 | 完成率分母口径 |

## 完整性与恢复

- 每个文件记录 SHA-256（`hashes.json`）；`--resume` 校验终态与产物哈希。
- 失败运行不删除：`status.json` 保留失败原因与阶段，重试使用新 run id。
- 矩阵级汇总写入 `output/evidence/formal/`（`matrix-manifest.json` + 分析
  产物），全部由 `scripts/analyze_matrix.py` 生成。
