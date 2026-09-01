# Docker 部署（Task 19）

## 定位

评委优先使用原生启动器（见 `docs/deployment.md`）；Docker 是无宿主依赖的辅助
路径。镜像目标固定为 `linux/amd64`、Python 3.12、SUMO 1.27.1，不含 ARM64、
Windows 容器、Kubernetes 或 GPU 支持。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `docker/Dockerfile` | 三阶段（web-builder / python-builder / runtime）headless 镜像 |
| `docker/Dockerfile.gui` | 基于 `judge_base` 构建上下文的 `container-gui` 派生镜像 |
| `docker/requirements.in` / `docker/requirements.lock` | 带哈希的冻结依赖（含 `eclipse-sumo==1.27.1`） |
| `../docker-compose.yml` | `judge`（默认）与 `judge-gui`（`gui` profile）服务 |
| `../.dockerignore` | 构建上下文边界：保护输入、密钥与生成产物不入上下文 |
| `scripts/release/docker_status.py` | 非变更 detector，任何主机可运行 |
| `scripts/release/docker_verify.py` | 显式 `--execute-live` 门控的 live 验证器 |

## 快速命令

默认 headless 服务（构建 + 启动，健康检查通过后访问 `http://127.0.0.1:8000/`）：

```bash
docker compose up --build
docker compose down
```

可选 GUI profile（host 8001 → 容器 8000）：

```bash
docker compose --profile gui up --build
```

直接构建（必须显式指定 `linux/amd64` 平台）：

```bash
docker build --platform linux/amd64 -t ca-mp:latest -f docker/Dockerfile .
# Dockerfile.gui 依赖 judge_base 命名上下文；先构建 headless 镜像，再显式提供：
docker build --platform linux/amd64   --build-context judge_base=docker-image://ca-mp:latest   -t ca-mp-gui:latest -f docker/Dockerfile.gui .
```

GUI 镜像的常规构建路径是 `docker compose --profile gui up --build`（Compose 自动
以 `service:judge` 提供 `judge_base` 上下文）；上面的直接构建仅供 CI/排查使用。

证据导出使用 `docker compose cp`（不要放宽容器权限）：

```bash
docker compose cp judge:/app/output/evidence ./output/evidence-from-container
```

GUI 镜像通过 `additional_contexts: {judge_base: service:judge}` 依赖 headless
构建，不存在可漂移的镜像 tag。验证器会向 build arg 与容器/网络/卷 label 注入
唯一 `TASK19_INVOCATION_ID`。

## 依赖锁再生成

```bash
uv pip compile docker/requirements.in \
  --python-version 3.12 \
  --python-platform x86_64-manylinux_2_28 \
  --only-binary :all: \
  --generate-hashes \
  --exclude-newer 2026-08-24T00:00:00Z \
  --output-file docker/requirements.lock
```

不可变基础镜像 digest 变更属于显式评审的依赖升级；系统包固定使用
`snapshot.debian.org` 的 `20260824T000000Z` 快照（`check-valid-until=no`）。

## Detector（任何主机可运行，不产生变更）

```bash
python scripts/release/docker_status.py --repo-root . \
  --output output/evidence/docker/docker-status.json
```

Docker CLI 不可用时，detector 输出 `not_run` / `docker_cli_unavailable`；CLI
与 daemon 可用但未执行 live 时，输出 `not_run` / `live_verification_not_run`。

## Live 验证（仅限显式授权的 Docker-capable 主机）

```bash
python scripts/release/docker_verify.py --repo-root . --execute-live
```

- live 验证器按随机 12-hex invocation ID 创建/清理全部资源，逐项校验所有权
  label，任一清理失败即整体 fail，绝不进行宽泛清理。
- 禁止命令：`docker system prune`、`docker volume prune`、
  `docker compose down -v`、任何 broad filter 删除或按前缀清理。

## 当前状态（如实声明）

- 本仓库静态 Dockerfile/Compose/lock 契约由
  `python -m pytest tests/test_docker_static.py` 锁定。
- Docker live build/health/smoke/save-load/GUI frames/cleanup 均未执行，
  状态为 `not_run`；静态测试或无 Docker 主机不能替代 live 证据。
- 换机后的控制器结果以 `output/evidence/docker/docker-status.json` 的实际
  detector 输出为准（reason 见上述两类 `not_run` 取值），不在此预设结论。
- 第二环境复现同样为 `not_run`，由 Task 23 在真实独立环境补齐。

## 已知限制

- xgboost 3.4.1 在 Linux 上引入 `nvidia-nccl-cu13`（约 200MB，无功能性影响，
  仅增加镜像体积）。
- 容器以 `read_only` 根文件系统 + `/tmp` tmpfs 运行；所有写入仅限
  `/app/output` 命名卷。
- Xvfb 不提供 Windows 焦点契约；`/api/runs/{run_id}/native-gui` 在
  container-gui 模式下保持禁用。live GUI pass 需要至少两帧非空且序列/时间
  递增的 PNG 证据，不能由"Xvfb 进程存在"替代。
