# Docker

## 模块职责

`docker/` 定义包含 Python、SUMO 和项目运行代码的 headless 镜像；仓库根目录的 Compose 文件负责挂载输出并运行示例。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `docker/Dockerfile` | 基于 Ubuntu 22.04 和 `ppa:sumo/stable` 构建运行镜像 |
| `../docker-compose.yml` | 构建 `simulation` 服务并挂载输出目录 |
| `../.dockerignore` | 排除 Git、缓存和本地输出等构建上下文 |
| `docs/operations/deployment.md` | 本地与容器部署说明 |

## 命令接口

```bash
docker build -t ca-mp:latest -f docker/Dockerfile .
docker run --rm -v ${PWD}/output:/app/output ca-mp:latest 16
docker compose up --build
docker compose run --rm simulation 1
```

容器内环境和路口数据自检：

```bash
docker run --rm --entrypoint sumo ca-mp:latest --version
docker run --rm --entrypoint python3 ca-mp:latest scripts/validation/validate_all.py
```

## 输入与输出

- 构建输入：`requirements.txt`、运行时 Python 模块、示例、验证脚本和 `data/intersection_data/`。
- 默认入口：`python3 examples/run_fixed_time.py`；位置参数是路口 ID。
- 宿主机输出：Compose 将 `output/` 和 `experiments/results/` 挂载到容器对应目录。

## 依赖

- 构建需要访问 Ubuntu、SUMO PPA 和 Python 包源。
- 运行需要 Docker Engine 或 Docker Desktop。
- 镜像内使用命令行 `sumo`，不包含 GUI 交互流程。

## 已知限制

- 仓库没有记录当前镜像在所有平台上的构建时长和镜像大小实测值。
- 默认入口只运行固定配时示例；其他算法需覆盖 entrypoint 或使用项目 Python 命令。
- 容器自检会启动多个 SUMO 配置，不能作为高频健康检查。
- 离线答辩环境仍需预先导出镜像或准备可用的软件包缓存。
