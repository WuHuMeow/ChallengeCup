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

### 指定路口

```bash
docker compose run --rm simulation 1
docker compose run --rm simulation 16
```

### 直接用 docker run

```bash
docker run ca-mp:latest 16
```

### 查看输出

仿真结果写入容器内 `/app/output/`，通过 volume 映射到宿主机 `./output/`：
```bash
ls output/csv/
```

## 示例

完整流程：
```bash
docker compose build
docker compose run --rm simulation 16
cat output/csv/16_fixed_time.csv | head -5
```

## 常见问题

**Q: 构建很慢？**
A: 首次构建需下载 SUMO PPA 包（约 500MB）。后续构建有缓存，只复制代码层。

**Q: 想跑 CA-MP 而不是固定配时？**
A: 当前 ENTRYPOINT 是 `examples/run_fixed_time.py`。CA-MP 需要修改 command 或进入容器：
```bash
docker compose run --rm simulation bash
python examples/run_ca_max_pressure.py 16
```

**Q: Windows 下路径问题？**
A: 确保使用 Docker Desktop for Windows，volume 映射使用正斜杠。
