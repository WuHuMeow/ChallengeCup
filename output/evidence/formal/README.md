# 形式矩阵证据（540-run）

- 矩阵：20 路口 × 3 算法 × 2 流量 × 3 种子 = 360 正常 + 180 扰动
  （construction / event_demand / vehicle_failure 各 60）。
- 执行：原生 SUMO 1.27.1，秒数口径 `duration=3600s, warmup=600s`，
  `--resume` 断点续跑，2026-08-27/28 完成 540/540。
- 规范矩阵根：`output/runs/formal/`（matrix_manifest.json + matrix.csv，
  由 37 个执行根合并，按 run_key 去重，每个 key 采用首个完成尝试）。
- 分析产物：`analysis_manifest.json`、`descriptive_stats.json`、
  `paired_tests.json`、`disturbance_resilience.json`、`selection.json`，
  全部由 `scripts/analyze_matrix.py` 生成，SHA-256 记录于分析清单。
- 执行期修复（test-first，均在本仓库历史）：
  - `b0f500b` 变体信号程序从验证配时计划派生（修复全红清空缺失）；
  - `e099278` 启动校验分层（官方多阶段计划走结构校验）；
  - `458e02d` construction 扰动 rerouter 覆盖全网边（修复 no-valid-route
    崩溃，该缺陷曾使 36 个 construction run 无法完成）；
  - `47e3df7` 扰动运行启用 `--ignore-route-errors`（无法重路由车辆按施工
    语义移除）。
- 统计口径与安全门禁见 `docs/release/experiment-protocol.md`。
