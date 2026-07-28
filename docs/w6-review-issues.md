# W6 Review 问题清单

> 当前分工关联状态（2026-07-28）：本文件仍是 W6 当日的历史审查快照，不是当前完成清单。当前角色完成度和剩余交付物以 [`docs/tasks/current-status.md`](tasks/current-status.md) 为准；Docker live、第二机器复现、Word/PPT/视频和比赛提交仍不得从静态检查推断为完成。

**日期**：2026-07-23

**用途**：本表是 W6 当日评审快照，不代表当前缺陷清单。当前 IA/IB 状态以
[`docs/ia-ib-final-verification.md`](ia-ib-final-verification.md) 为准：CA-MP、精确指标和
按 `run_id` 隔离的变体输出均已闭环；Docker 静态契约已检查，但 Docker live 与第二机器
复现仍为 `not_run`。下表保留当时原始表述用于追溯。

| # | 文件 | 问题 | 优先级 | 状态 |
|---|------|------|--------|------|
| 1 | algorithms/ca_max_pressure.py | MVI 桩 set_phase 值为方向字符串（非法相位索引），被 bridge 容错跳过，CA-MP 当前未真正改变相位，指标不具算法对比意义；正式实现归 AB；IB 已在 bridge 容错跳过 | 高 | 待 AB 实现 |
| 2 | docker/Dockerfile | 镜像内 runner 一致性未实机验证（IA 交付，待回填镜像大小/构建时间实测值） | 中 | 静态契约通过；Docker live 未运行，待外部环境验证 |
| 3 | experiments/metrics.py | throughput / travel_time 为占位（需 tripinfo 二次校准，EX 协同） | 中 | 待 EX |
| 4 | scenes/variant.py + experiments/runner.py | 变体 `-a` 叠加语义注意项：additional_files 与默认 sumocfg 流量叠加时的覆盖语义、以及多场景批量下输出命名不含变体维度可能互相覆盖 | 中 | 待 EX 确认 |
| 5 | engine/traci_bridge.py | `_collect_vehicles` 的 500 辆截断+进口道优先路径在真实高流量下未触达（实测 vehicles 峰值 22），仅单测覆盖 | 低 | 单测已覆盖，接受现状 |
