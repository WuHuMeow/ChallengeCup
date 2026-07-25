# Docker 中运行 SUMO 的调研笔记（IA W2 Day 7）

> 调研日期：2026-07-23 | 结论先行：**基础镜像 `ubuntu:22.04` + 官方 PPA `ppa:sumo/stable`**

## 方案对比

| 方案 | SUMO 版本 | 评价 |
|------|-----------|------|
| `ubuntu:22.04` + `apt install sumo sumo-tools` | **1.12.0**（Ubuntu 官方源） | （不通过） 否决：版本过旧，无法读取 net 格式 1.20 的路网（本项目路口 1-10、14-20 均为 1.20） |
| `ubuntu:22.04` + `ppa:sumo/stable` | 跟随官方稳定版（当前 1.27.x） | （已完成） **采纳**：[SUMO 官方下载页](https://sumo.dlr.de/docs/Downloads.html)推荐的 Ubuntu 安装方式，版本与本项目统一目标 1.27.1 一致 |
| `pip install eclipse-sumo` | 跟随 PyPI 发布（当前 1.27.x） | 备选：[eclipse-sumo on PyPI](https://pypi.org/project/eclipse-sumo/) 的 wheel 自带 SUMO 二进制，免 apt；但镜像内调试工具（netconvert 等）不如 apt 齐全 |
| 社区 Docker 镜像（Docker Hub 搜索 "sumo"） | 参差不齐 | （不通过） 否决：无官方维护镜像，版本与安全性不可控 |

## 采纳方案的 apt 包清单

```bash
apt-get update
apt-get install -y software-properties-common
add-apt-repository -y ppa:sumo/stable
apt-get update
apt-get install -y sumo sumo-tools python3 python3-pip
```

- `sumo`：仿真核心（含 `sumo`、`netconvert`、`duarouter` 等）
- `sumo-tools`：Python 工具集（`traci`、`sumolib` 的源码形态）
- 环境变量：`SUMO_HOME=/usr/share/sumo`

## 关键验证点（W3/W4 执行）

- 容器内 `sumo --version` 输出 1.27.x（与主机一致）
- 容器内能读取 net 格式 1.20 与 1.9 两种路网
- 镜像大小目标 < 2GB（ubuntu:22.04 基础 ~78MB + sumo ~500MB + Python 依赖 ~1GB，可行）

## 参考

- [SUMO 官方下载页（PPA 说明）](https://sumo.dlr.de/docs/Downloads.html)
- [eclipse-sumo PyPI](https://pypi.org/project/eclipse-sumo/)
