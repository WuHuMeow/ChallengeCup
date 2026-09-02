# 部署与复现

本文是 IA/IB 的规范部署入口。原始 `data/intersection_data/` 只读，所有运行和验收产物写入
`output/` 下的独立目录。仓库当前不保留完整矩阵、验收输出或压缩包；下列命令会在本机
重新创建一次性运行目录。

## 一键启动

Windows 根目录入口会选择仓库内的 `.venv` Python，执行原生 SUMO/FastAPI/Web 控制台预检，
在 `/api/health` 返回 `{"status":"ok"}` 后才打开浏览器。请求端口被占用时，启动器只在
连续十个端口内选择并把冲突写入诊断文件，不会静默改用不可追踪的端口。

```powershell
.\start_frontend.ps1
.\start_frontend.ps1 --gui-mode headless --no-browser
.\start_frontend.ps1 --gui-mode native --port 8765
```

也可以双击或从命令提示符运行根目录的 `start_frontend.bat`。两个根目录入口均调用
`scripts/start_judge.ps1`，因此不会产生第二套启动逻辑。启动状态写入
`output/evidence/judge-launch/launcher.json`，其中包含所选端口、Python/FastAPI/Uvicorn/
TraCI/SUMO 版本、静态资产、健康检查、浏览器动作和退出原因。Windows 本地默认使用
`native`（`sumo-gui.exe`），确保“开始快速演示”可以连接 GUI 和发布画面；非 Windows
默认使用 `headless`。`--gui-mode auto` 仍可显式用于兼容旧流程，但不建议作为评审入口；
`headless` 强制使用 `sumo`；`native` 在缺少 Windows `sumo-gui` 时明确失败，不会伪造
GUI 成功。启动器会打印最终选择的控制台 URL；若 native 窗口在运行后不可聚焦，
`/api/runs/{run_id}/native-gui` 会返回明确的失败状态。

稳定 CLI 选项包括：`--host`、`--port`、`--port-attempts`（最多连续十个端口）、
`--gui-mode auto|native|headless|container-gui`、`--open-browser/--no-browser`、`--health-timeout`
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

上面的命令只启动 API 进程，使用默认 `sumo`，不负责 native SUMO-GUI、WebSocket
事件链和前端控制台；它适合 API/headless 调试，不适合作为“开始快速演示”的启动方式。
需要打开评审前端时请使用根目录的 `start_frontend.ps1` 或 `start_frontend.bat`。

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

## 2. 单次运行（秒数口径）

单次与批量运行统一经 `RunService`（单 worker），推荐直接使用矩阵脚本的
smoke/quick 档（秒数窗口）：

```powershell
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py `
  --profile smoke --output-root output/runs/matrix-smoke
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py `
  --profile quick --output-root output/runs/matrix-quick
```

每次运行生成独立 `run_id`：

```text
<output-root>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/
```

常用产物包括 `metrics.csv`、`simulation_log.csv`、`events.csv`、`tripinfo.xml`、
`stats.xml`、`traj.xml`、`summary.json`、`run_metadata.json`、`manifest.json`、
`provenance.json`、`status.json` 和 `variants/`。

## 3. REST API（API-only 调试）

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.server:app `
  --host 127.0.0.1 --port 8000
```

规范路由统一为 `/api/*`。静态接口交付：

- `docs/api/openapi.json`
- `docs/api/postman_collection.json`

API 和 CLI 都调用单 worker 的 `RunService`，不会绕过统一运行目录和终态记录。

## 4. PDF 实验矩阵（秒数口径）

smoke（100 秒，路口 1）与 quick（600 秒，路口 1/11/16）用于演示与预检：

```powershell
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py `
  --profile quick --output-root output/runs/matrix-quick
```

formal 矩阵为 20 路口 × 3 算法 × 2 流量变体 × 3 种子，共 360 次正常 +
180 次扰动运行，每次 `--duration-seconds 3600 --warmup-seconds 600`（秒数
窗口，秒级步长）：

```powershell
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py `
  --profile formal --duration-seconds 3600 --warmup-seconds 600 `
  --resume --output-root output/runs/formal
```

`--resume` 读取 sealed evidence，只跳过终态 `completed` 且七类必需产物均
非空的运行；失败运行保留失败证据并生成新 run id 重试。分析入口：

```powershell
.\.venv\Scripts\python.exe scripts/analyze_matrix.py `
  --input output/runs/formal --output output/evidence/formal
```

## 5. 发布证据与状态口径

形式矩阵执行并冻结前，其状态一律为 `not_run`；任何检查状态严格为
`pass`、`fail`、`not_run`，不得把计划写成结果。证据合同
（`manifest.json` / `provenance.json` / `status.json` / events / metrics /
summary 字段与单位）见
[`docs/release/evidence-contract.md`](release/evidence-contract.md)；
实验协议与统计判定规则见
[`docs/release/experiment-protocol.md`](release/experiment-protocol.md)。

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
