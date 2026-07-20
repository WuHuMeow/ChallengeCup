# docker/

## 模块职责

容器化部署配置，确保评委和队友能够在不同环境中一键复现系统。

## 当前完成情况

- [ ] `Dockerfile`：尚未创建。
- [ ] `docker-compose.yml`：尚未创建。

## 待完成情况

- [ ] `Dockerfile`：基于 `python:3.10-slim` 镜像，安装 SUMO、sumo-tools 和 Python 依赖。
- [ ] `docker-compose.yml`：定义服务、端口映射、数据卷挂载。
- [ ] 验证 `docker-compose up` 可一键启动 API 服务并运行单次仿真。

## 需求分析

| 需求 | 说明 |
|------|------|
| 环境一致性 | 避免 SUMO/Python 依赖在评委机器上配置失败 |
| 一键复现 | `docker-compose up` 启动后即可访问 API 和运行仿真 |
| 可移植 | 支持 Windows（Docker Desktop）、Linux、macOS |
| headless 运行 | 容器内使用 `sumo` 命令行版，无需 GUI |

## 关键文件

| 文件 | 说明 |
|------|------|
| `Dockerfile` | 镜像构建（待创建） |
| `docker-compose.yml` | 服务编排（待创建） |

## 使用方式（规划）

```bash
cd docker
docker-compose up
```

## 负责人

- IB（仿真基础设施 B）：Docker 打包与部署文档
- IA（仿真基础设施 A）：配合验证 SUMO 在容器内正常运行
