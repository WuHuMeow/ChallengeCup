# Quick Demo 证据

quick 档（600 秒，路口 1 / 11 / 16，3 算法 × 2 流量 × 3 种子 = 54 run）于
2026-08-28 在本机以原生 SUMO 1.27.1 全部执行完成（54/54 completed）。

- 运行根：`output/runs/matrix-quick/`
- 命令：`python scripts/run_pdf_matrix.py --profile quick --resume --output-root output/runs/matrix-quick`
- 用途：评委现场演示与 preflight；不作为形式统计结论来源。
- 首轮暴露并修复的缺陷：变体信号程序缺全红清空（`b0f500b`）、启动校验与
  官方多阶段配时计划的分层裁定（`e099278`）。
