# 发布文档总览

本目录是评委向发布文档的入口。四份文档与根 [`README.md`](../../README.md)、
[`docs/deployment.md`](../deployment.md) 一起，构成可复现的运行与验证口径。

| 文档 | 内容 |
| --- | --- |
| [experiment-protocol.md](experiment-protocol.md) | 540-run 形式矩阵：参数、指标、安全门禁与统计判定规则 |
| [evidence-contract.md](evidence-contract.md) | 每次运行的证据文件（manifest/provenance/status/events/metrics/summary）字段与单位 |
| [algorithm-extension.md](algorithm-extension.md) | 在本平台上新增/替换信号控制算法的步骤与契约 |

## 命令速查

```powershell
# 一键启动（原生，健康检查通过后打开 Web 控制台）
.\start_frontend.ps1

# 100 秒演示（路口 1）
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py --profile smoke --output-root output/runs/matrix-smoke

# 600 秒 quick 演示（路口 1 / 11 / 16）
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py --profile quick --output-root output/runs/matrix-quick

# 540-run 形式矩阵（已完成；--resume 可校验并复用封存运行）
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py --profile formal `
  --duration-seconds 3600 --warmup-seconds 600 --resume --output-root output/runs/formal
```

## 证据状态口径

- `pass`：对应命令在当前代码上真实执行且门禁通过。
- `fail`：执行过但门禁未通过，保留失败证据。
- `not_run`：未执行（如 Docker live、第二环境）。

禁止把静态检查或计划表述为 `pass`；每个证据数字都能回链到具体 run 目录。
