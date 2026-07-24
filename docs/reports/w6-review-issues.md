# W6 Review 问题清单

**日期**：2026-07-23

**用途**：评审遗留问题登记模板 + 当前已知项。新增问题按同一表格追加，
状态流转：待确认 → 待实现/待验证 → 已闭环。

| # | 文件 | 问题 | 优先级 | 状态 |
|---|------|------|--------|------|
| 1 | algorithms/ca_max_pressure.py | MVI 桩 set_phase 值为方向字符串（非法相位索引），被 bridge 容错跳过，CA-MP 当前未真正改变相位，指标不具算法对比意义；正式实现归 AB；IB 已在 bridge 容错跳过 | 高 | 待 AB 实现 |
| 2 | docker/Dockerfile | 镜像内 runner 一致性未实机验证（IA 交付，待回填镜像大小/构建时间实测值） | 中 | 待验证 |
| 3 | experiments/metrics.py | throughput / travel_time 为占位（需 tripinfo 二次校准，EX 协同） | 中 | 待 EX |
| 4 | scenes/variant.py + experiments/runner.py | 变体 `-a` 叠加语义注意项：additional_files 与默认 sumocfg 流量叠加时的覆盖语义、以及多场景批量下输出命名不含变体维度可能互相覆盖 | 中 | 待 EX 确认 |
| 5 | engine/traci_bridge.py | `_collect_vehicles` 的 500 辆截断+进口道优先路径在真实高流量下未触达（实测 vehicles 峰值 22），仅单测覆盖 | 低 | 单测已覆盖，接受现状 |
