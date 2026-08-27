# 部署与复现

本文是 IA/IB 的规范部署入口。原始 `data/intersection_data/` 只读，所有运行和验收产物写入
`output/` 下的独立目录。仓库当前不保留完整矩阵、验收输出或压缩包；下列命令会在本机
重新创建一次性运行目录。

## 评委一键启动

Windows 评委入口会选择仓库内的 `.venv` Python，执行原生 SUMO/FastAPI/Web 控制台预检，
在 `/api/health` 返回 `{"status":"ok"}` 后才打开浏览器。请求端口被占用时，启动器只在
连续十个端口内选择并把冲突写入诊断文件，不会静默改用不可追踪的端口。

```powershell
.\scripts\start_judge.ps1
.\scripts\start_judge.ps1 --gui-mode headless --no-browser
.\scripts\start_judge.ps1 --gui-mode native --port 8765
```

也可以双击或从命令提示符运行 `scripts\start_judge.bat`。启动状态写入
`output/evidence/judge-launch/launcher.json`，其中包含所选端口、Python/FastAPI/Uvicorn/
TraCI/SUMO 版本、静态资产、健康检查、浏览器动作和退出原因。`--gui-mode auto` 在本机
Windows 优先选择 `sumo-gui`；`headless` 强制使用 `sumo`；`native` 在缺少 Windows
`sumo-gui` 时明确失败，不会伪造 GUI 成功。启动器会打印最终选择的控制台 URL；若
native 窗口在运行后不可聚焦，`/api/runs/{run_id}/native-gui` 会返回明确的失败状态。

稳定 CLI 选项包括：`--host`、`--port`、`--port-attempts`（最多连续十个端口）、
`--gui-mode auto|native|headless`、`--open-browser/--no-browser`、`--health-timeout`
以及 `--diagnostics`。

常见故障处理：

- 缺少 `.venv`：先按下方环境章节创建虚拟环境并安装依赖。
- SUMO 版本不是 1.27.1：安装/修正 `SUMO_HOME` 后重新启动，诊断文件会保留检测版本。
- `api/static/dist/index.html` 缺失：先在 `web/` 执行 `npm ci; npm run build`。
- 连续十个端口均冲突：释放其中一个端口，或用 `--port` 指定新的扫描起点。
- native GUI 不可用：使用 `--gui-mode headless --no-browser` 验证服务，或在有桌面的
  Windows 环境重试 native 模式。

手动启动入口仍保留，适合开发调试：

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```

## 1. 本地环境

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
sumo --version
.\.venv\Scripts\python.exe scripts/validate_all.py `
  --steps 100 --output-root output/runs/validate-original
```

### Linux / macOS

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
sumo --version
python scripts/validate_all.py \
  --steps 100 --output-root output/runs/validate-original
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
  --quick --output-root output/runs/matrix-quick
```

完整 PDF 矩阵为 20 路口、3 算法、2 流量、3 种子，共 360 次，每次 36000 步：

```powershell
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py `
  --steps 36000 --output-root output/runs/matrix-full
```

首次需要同时校准 CA-MP 时可加 `--tune`。恢复运行会读取 `matrix_state.json`，只跳过终态
`completed` 且七类必需产物均非空的运行。若单独完成校准，应把 `selected_params.json` 放在
矩阵输出根目录，避免使用未校准参数恢复旧矩阵。

## 5. IA/IB 验收

```powershell
.\.venv\Scripts\python.exe scripts/verify_ia_ib.py `
  --quick --output-root output/runs/ia-ib-quick
.\.venv\Scripts\python.exe scripts/verify_ia_ib.py `
  --output-root output/runs/ia-ib-full
```

`--quick` 会跳过增强配置的 3600 步检查，并把该项写为 `not_run`。完整验收包括：

- 20 路口原始配置 100 步；
- 20 路口增强配置 100 步和 3600 步；
- 场景变体、运行时、API、CA-MP、精确指标和图表契约；
- 360 次、每次 36000 步 PDF 矩阵；
- 1.5 倍流量压力运行；
- Docker 静态检查，以及环境可用时的 live build/run。

验收输出 `verification.json` 和 `docs/ia-ib-final-verification.md`，检查状态严格为
`pass`、`fail`、`not_run`。

## 6. Docker

原生启动器是评委首选；Docker 是无宿主依赖的辅助路径。镜像目标固定
`linux/amd64`、Python 3.12、SUMO 1.27.1。详细契约见 `docker/README.md` 与
`docs/superpowers/specs/2026-08-24-docker-judge-deployment-design.md`。

默认 headless 服务（内部严格 8000 端口，host 端口默认 8000）：

```powershell
docker compose up --build
docker compose down
```

可选 GUI profile（host 8001 → 容器 8000，`container-gui` 模式经 Xvfb 运行
`sumo-gui`）：

```powershell
docker compose --profile gui up --build
```

直接构建必须显式指定平台：

```powershell
docker build --platform linux/amd64 -t ca-mp:latest -f docker/Dockerfile .
# Dockerfile.gui 需要 judge_base 命名上下文（常规路径为 compose --profile gui）：
docker build --platform linux/amd64 `
  --build-context judge_base=docker-image://ca-mp:latest `
  -t ca-mp-gui:latest -f docker/Dockerfile.gui .
```

证据导出与受控关闭：

```powershell
docker compose cp judge:/app/output/evidence ./output/evidence-from-container
docker compose down
```

detector（任何主机、零变更）：

```powershell
.\.venv\Scripts\python.exe scripts/release/docker_status.py --repo-root . `
  --output output/evidence/docker/docker-status.json
```

Docker CLI 不可用时输出 `not_run` / `docker_cli_unavailable`；CLI 与 daemon
可用但未执行 live 时输出 `not_run` / `live_verification_not_run`。live 验证
`python scripts/release/docker_verify.py --repo-root . --execute-live` 只能在
明确授权且具备 Docker 的主机执行；它按 invocation ID 管理资源并拒绝任何宽泛
清理（`docker system prune`、`docker volume prune`、`docker compose down -v`
均为禁止命令）。

当前没有 Docker live build/run/save/load/GUI frames 的真实证据，Docker live
状态为 `not_run`；换机后的控制器实际结果以 detector 的 JSON 输出为准。第二
机器复现同样保持 `not_run`，由 Task 23 在真实独立环境补齐。

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
  --root output/runs/ia-ib-full
.\.venv\Scripts\python.exe scripts/check_seed_repro.py `
  --steps 300 --output-root output/runs/seed-repro
```

## 9. 已知源数据 warning

主办方原始路口 J2 信号方案可能输出 unsafe/unused-state warning，部分路口还会提示缺少黄灯。
原始数据保持只读；验收报告同时保留运行完成状态和 warning，不隐藏、也不把 warning
误报为运行失败。

## 10. 交付边界

当前记录中，仓库实现、自动测试和本地 SUMO 证据已经验收；Docker live 与第二机器复现
仍为 `not_run`。历史 `output/verification/` 路径只是脚本可创建的运行时根目录，不是当前
仓库中保留的产物。PPT、Word 实验报告和演示视频仍是独立提交材料。
