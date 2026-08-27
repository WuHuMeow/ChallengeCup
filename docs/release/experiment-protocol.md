# 实验协议（形式矩阵）

## 矩阵构成

- 场景：20 个真实路口（`data/intersection_data/`，只读）。
- 算法（canonical ID）：`fixed_time`、`classic_max_pressure`、
  `capacity_aware_max_pressure`。
- 流量变体：`x1`（标定流量）、`x2`（加压流量）。
- 种子：`s42`、`s137`、`s2026`（校准/留出分割由调优流程固定）。
- 正常运行：20 × 3 × 2 × 3 = **360 run**。
- 扰动运行：在事件注入场景（施工占道、大型活动需求、车辆故障车道阻塞）下
  追加 **180 run**，合计 **540 run**。

## 时间窗口（秒数口径）

| 参数 | 值 |
| --- | --- |
| `--duration-seconds` | 3600 秒（秒级步长，3600 步） |
| `--warmup-seconds` | 600 秒（预热不计入统计） |
| smoke 档 | 100 秒（仅路口 1） |
| quick 档 | 600 秒（路口 1 / 11 / 16） |

命令见 [README](README.md)；`--resume` 基于 sealed evidence 跳过已完成 run，
失败 run 保留失败证据并以新 run id 重试。

## 指标

| 指标 | 单位 | 来源 |
| --- | --- | --- |
| 平均旅行时间 | s | `tripinfo.xml` |
| 平均排队长度 | m | 车道队列快照 |
| 平均速度 | m/s | 车辆采样 |
| 完成率 | % | 完成 / 全部车辆 |
| 急减速次数 | 次 | 安全事件流 |
| 红灯违规 | 次 | 安全事件流 |
| 潜在冲突 | 次 | 安全事件流 |
| 燃油消耗 | ml | SUMO 排放模型 |
| CO2 排放 | g | SUMO 排放模型 |

缺失的精确量在 JSON 中写 `null`，不伪造为 `0`。

## 安全门禁

单次运行必须满足：无碰撞、无红灯违规、无非法相位转换；终态为 `completed`
且产物完整。任一违反即 `fail` 并保留证据。

## 统计判定规则

- 算法间比较：配对（同场景、同流量、同种子）差值；报告均值差与 95% 置信
  区间（bootstrap 或 t 区间，按协议固定一种并全程使用）。
- 优势判定：CA-MP 相对 `fixed_time` 与 `classic_max_pressure` 的主要指标
  区间不跨零且方向一致。
- 稳健性：扰动 strata 与正常 strata 分开汇总，不混样。
- 所有数字由 `scripts/analyze_matrix.py` 从 sealed evidence 计算；报告不得
  手工抄写未回链的数值。

## 执行状态

形式矩阵由 Task 22 执行并冻结；执行前本协议声明的矩阵结果状态为
`not_run`。
