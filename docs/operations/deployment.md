# 运维部署速查

详细说明见 [`docs/deployment.md`](../deployment.md)。本页保留运行人员需要的最短命令。

## 本地单次运行

```powershell
.\.venv\Scripts\python.exe -m experiments.runner `
  --intersection 1 --algorithm ca_maxpressure `
  --flow-multiplier 1.5 --seed 42 --steps 36000 `
  --output-dir output/runs
```

产物目录：

```text
<root>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/
```

## 前端评审启动（Windows）

```powershell
.\start_frontend.ps1
# 无浏览器时用于脚本化验证
.\start_frontend.ps1 --no-browser
```

根目录入口会选择仓库 `.venv`，预检 SUMO/FastAPI/静态前端后再打开控制台；Windows
默认启动 `sumo-gui.exe`。需要强制无界面运行时显式加上
`--gui-mode headless`。

## API-only 调试

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.server:app --port 8000
```

该命令只用于 REST API/headless 调试，不是前端快速演示的启动入口。

规范端点是 `/api/*`；静态契约为：

- `docs/api/openapi.json`
- `docs/api/postman_collection.json`

## PDF 矩阵

```powershell
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py `
  --quick --output-root output/runs/matrix-quick
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py `
  --steps 36000 --output-root output/runs/matrix-full
```

完整矩阵为 360 次运行。恢复机制通过 `matrix_state.json` 和每个 `run_id` 目录的完整性决定
是否跳过。

## IA/IB 验收

```powershell
.\.venv\Scripts\python.exe scripts/verify_ia_ib.py `
  --quick --output-root output/runs/ia-ib-quick
.\.venv\Scripts\python.exe scripts/verify_ia_ib.py `
  --output-root output/runs/ia-ib-full
```

这些目录由命令运行时创建，仓库当前不保留矩阵和验收产物。状态只使用 `pass`、`fail`、
`not_run`。

## Docker

```powershell
docker build -t ca-mp:ia-ib -f docker/Dockerfile .
docker run --rm -v "${PWD}/output:/app/output" ca-mp:ia-ib `
  --intersection 1 --algorithm fixed_time --steps 100 `
  --output-dir /app/output/runs
```

统一容器入口为 `python3 -m experiments.runner`。

Dockerfile、Compose 配置和静态契约已检查；当前没有 Docker live build/run/save/load
的真实证据，因此 Docker live 状态为 `not_run`。第二机器复现同样保持 `not_run`。

## 离线包

```powershell
.\.venv\Scripts\python.exe scripts/package_offline.py `
  --output-dir output/offline --image ca-mp:ia-ib
```

`offline_manifest.json` 分开记录 Docker live 和第二机器复现。未执行的轴保持 `not_run`。

## 故障判断

| 现象 | 判断与处理 |
|---|---|
| `SUMO_HOME` / `traci` 不可用 | 按 `docs/sumo_env_setup.md` 安装并配置 SUMO |
| 运行目录已存在 | 不要覆盖；让系统生成新的 `run_id` |
| `run_metadata.json` 非 `completed` | 读取 `reason` 和 `events.csv`，不要只看 CSV 是否存在 |
| 精确指标为 `null` | 表示 SUMO 未提供完整字段，不应改成 0 |
| J2 unsafe/unused-state warning | 记录为只读源数据 warning；同时检查运行终态 |
| Docker 不可用 | 记录 `not_run`，不能用静态测试替代 live 通过 |
