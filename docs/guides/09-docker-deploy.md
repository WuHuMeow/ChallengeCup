# Docker 部署与运行

## 目的

在无本地 SUMO 环境的机器上通过 Docker 运行仿真。

## 前置条件

- 已安装 Docker 和 Docker Compose
- 仓库已克隆到本地

## 操作步骤

### 构建镜像

```bash
docker compose build
```

镜像基于 Ubuntu 22.04 + SUMO（ppa:sumo/stable），包含所有 Python 依赖。

### 运行默认仿真（路口 16，固定配时）

```bash
docker compose up
```

### 指定路口和算法

```bash
docker compose up --build \
  --output-dir /app/output/runs
```

### 直接用 docker run

```bash
docker run --rm -v "${PWD}/output:/app/output" ca-mp:latest \
  # 运行参数经 /api/runs 下发，见 docker/README.md
  --output-dir /app/output/runs
```

### 查看输出

仿真结果写入容器内 `/app/output/`，通过 volume 映射到宿主机 `./output/`：
```bash
find output/runs -name run_metadata.json
```

## 示例

完整流程：
```bash
docker compose build
docker compose run --rm simulation \
  --intersection 16 --algorithm fixed_time --steps 100 \
  --output-dir /app/output/runs
```

Dockerfile、Compose 配置和静态契约已检查；当前没有 Docker live build/run/save/load
的真实证据，因此 Docker live 状态为 `not_run`。第二机器复现同样保持 `not_run`。

## 常见问题

**Q: 构建很慢？**
A: 首次构建需下载 SUMO PPA 包（约 500MB）。后续构建有缓存，只复制代码层。

**Q: 想跑 CA-MP 而不是固定配时？**
A: 镜像入口是 `python3 -m experiments.runner`，按上面的命令传入
运行参数经 REST API（`/api/runs`）或 Compose 环境变量下发，无需修改镜像或进入容器。

**Q: Windows 下路径问题？**
A: 确保使用 Docker Desktop for Windows，volume 映射使用正斜杠。

**Q: 静态测试通过是否等于 Docker 可交付？**
A: 不等于。只有真实执行 build/run/save/load 并保留证据后，Docker live 才能从
`not_run` 改为 `pass`。
