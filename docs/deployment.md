# 部署与复现

本文是 IA/IB 的规范部署入口。原始 `data/intersection_data/` 只读，所有运行和验收产物写入
`output/` 下的独立目录。

## 1. 本地环境

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
sumo --version
.\.venv\Scripts\python.exe scripts/validate_all.py `
  --steps 100 --output-root output/verification/original
```

### Linux / macOS

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
sumo --version
python scripts/validate_all.py \
  --steps 100 --output-root output/verification/original
```

项目以 SUMO 1.27.1 验证；安装细节见 `docs/sumo_env_setup.md`。

## 2. 单次运行

```powershell
.\.venv\Scripts\python.exe -m experiments.runner `
  --intersection 1 `
  --algorithm ca_maxpressure `
  --flow-multiplier 1.5 `
  --seed 42 `
  --steps 36000 `
  --output-dir output/runs
```

默认步数是 `36000`。每次运行生成独立 `run_id`：

```text
<output-dir>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/
```

常用产物包括 `metrics.csv`、`simulation_log.csv`、`events.csv`、`tripinfo.xml`、
`stats.xml`、`traj.xml`、`summary.json`、`run_metadata.json` 和 `variants/`。

## 3. REST API

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.server:app `
  --host 127.0.0.1 --port 8000
```

规范路由统一为 `/api/*`。静态接口交付：

- `docs/api/openapi.json`
- `docs/api/postman_collection.json`

API 和 CLI 都调用单 worker 的 `RunService`，不会绕过统一运行目录和终态记录。

## 4. PDF 实验矩阵

快速 smoke 矩阵只跑路口 1、11、16 和 100 步：

```powershell
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py `
  --quick --output-root output/verification/matrix-quick
```

完整 PDF 矩阵为 20 路口、3 算法、2 流量、3 种子，共 360 次，每次 36000 步：

```powershell
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py `
  --steps 36000 --output-root output/verification/matrix-full
```

首次需要同时校准 CA-MP 时可加 `--tune`。恢复运行会读取 `matrix_state.json`，只跳过终态
`completed` 且七类必需产物均非空的运行。若单独完成校准，应把 `selected_params.json` 放在
矩阵输出根目录，避免使用未校准参数恢复旧矩阵。

## 5. IA/IB 验收

```powershell
.\.venv\Scripts\python.exe scripts/verify_ia_ib.py `
  --quick --output-root output/verification/quick
.\.venv\Scripts\python.exe scripts/verify_ia_ib.py `
  --output-root output/verification/final
```

`--quick` 会跳过增强配置的 3600 步检查，并把该项写为 `not_run`。完整验收包括：

- 20 路口原始配置 100 步；
- 20 路口增强配置 100 步和 3600 步；
- 场景变体、运行时、API、CA-MP、精确指标和图表契约；
- 360 次、每次 36000 步 PDF 矩阵；
- 1.5 倍流量压力运行；
- Docker 静态检查，以及环境可用时的 live build/run。

验收输出 `verification.json` 和 `docs/reports/ia-ib-final-verification.md`，检查状态严格为
`pass`、`fail`、`not_run`。

## 6. Docker

统一入口是 `python3 -m experiments.runner`：

```powershell
docker build -t ca-mp:ia-ib -f docker/Dockerfile .
docker run --rm `
  -v "${PWD}/output:/app/output" `
  ca-mp:ia-ib `
  --intersection 1 `
  --algorithm fixed_time `
  --steps 100 `
  --output-dir /app/output/runs
```

Compose：

```powershell
docker compose up --build
docker compose run --rm simulation `
  --intersection 16 --algorithm ca_maxpressure `
  --steps 36000 --output-dir /app/output/runs
```

本机没有 Docker、镜像未构建或 live 命令未执行时，Docker 证据状态为 `not_run`，静态
Dockerfile 测试通过不能替代真实容器运行。

## 7. 离线包与第二机器

```powershell
.\.venv\Scripts\python.exe scripts/package_offline.py `
  --output-dir output/offline `
  --image ca-mp:ia-ib
```

输出包含：

- `challenge-cup-source.zip`
- `requirements.txt`
- `offline_manifest.json`
- Docker 已存在且导出成功时的 `ca-mp-ia-ib.tar`

manifest 记录每个文件的 SHA-256 和字节数。第二机器证据必须由另一台机器真实运行后提供：

```powershell
.\.venv\Scripts\python.exe scripts/package_offline.py `
  --output-dir output/offline `
  --second-machine-evidence path/to/second-machine.json
```

未提供第二机器证据时状态保持 `not_run`。

## 8. 输出检查

```powershell
.\.venv\Scripts\python.exe scripts/check_outputs.py `
  --root output/verification/final
.\.venv\Scripts\python.exe scripts/check_seed_repro.py `
  --steps 300 --output-root output/verification/seed
```

## 9. 已知源数据 warning

主办方原始路口 J2 信号方案可能输出 unsafe/unused-state warning，部分路口还会提示缺少黄灯。
原始数据保持只读；验收报告同时保留运行完成状态和 warning，不隐藏、也不把 warning
误报为运行失败。

## 10. 交付边界

IA/IB 验收覆盖仓库实现、自动测试、本地 SUMO、Docker live 和第二机器复现五条证据轴。
PPT、Word 实验报告和演示视频仍是独立提交材料。
