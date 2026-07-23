# docker/

## 模块职责

容器化部署配置，确保评委和队友能够在不同环境中一键复现系统。

## 当前完成情况

- [x] `Dockerfile`：已创建（IA，2026-07-23）。基础镜像 `ubuntu:22.04` + `ppa:sumo/stable`（SUMO 1.27.x）。
  > 注意：未采用原规划的 `python:3.10-slim`——Ubuntu 默认源的 SUMO 为 1.12.0，无法读取本项目 net 格式 1.20 的路网；选型依据见 `docs/notes/docker_sumo_research.md`。
- [x] `docker-compose.yml`：已创建（仓库根目录，单容器编排，输出挂载宿主机）。
- [x] `.dockerignore`：已创建（仓库根目录，排除 `output/`、`__pycache__/`、`.git` 等）。
- [x] `docs/deployment.md`：部署运行说明文档（含 Docker 章节、常见问题、三平台差异）。

## 待完成情况

- [ ] Docker 实机构建验证：`docker build -t ca-mp:latest -f docker/Dockerfile .`（本机无 Docker，待有环境的机器执行）。
- [ ] 镜像大小与构建时间回填到 `docs/deployment.md`（目标 < 2GB）。
- [ ] 验证 `docker-compose up --build` 可一键运行指定路口仿真。
- [ ] （W6）`docker save` 导出镜像 tar，应对答辩现场无网络场景。

## 需求分析

| 需求 | 说明 |
|------|------|
| 环境一致性 | 避免 SUMO/Python 依赖在评委机器上配置失败 |
| 一键复现 | `docker run` / `docker-compose up` 即可运行仿真 |
| 可移植 | 支持 Windows（Docker Desktop）、Linux、macOS |
| headless 运行 | 容器内使用 `sumo` 命令行版，无需 GUI |

## 关键文件

| 文件 | 说明 |
|------|------|
| `docker/Dockerfile` | 镜像构建（已创建） |
| `docker-compose.yml` | 服务编排（仓库根目录，已创建） |
| `.dockerignore` | 构建上下文排除清单（仓库根目录，已创建） |
| `docs/deployment.md` | 部署运行说明文档（已创建） |

## 使用方式

```bash
# 构建（在项目根目录执行）
docker build -t ca-mp:latest -f docker/Dockerfile .

# 运行指定路口（ENTRYPOINT 为 examples/run_fixed_time.py，参数即路口 ID）
docker run --rm -v ${PWD}/output:/app/output ca-mp:latest 16

# 或用 compose（默认路口 16）
docker-compose up --build
```

## 负责人

- IB（仿真基础设施 B）：Docker 打包与部署文档
- IA（仿真基础设施 A）：Dockerfile/compose/部署文档初版已完成，配合容器内验证
