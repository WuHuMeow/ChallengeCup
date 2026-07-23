# CA-MP 仿真平台镜像（IA W3 Day 6 初稿 / W4 Day 2 完善）
# 基础镜像与安装方式见 docs/notes/docker_sumo_research.md：
# 必须用 ppa:sumo/stable —— Ubuntu 22.04 默认源的 sumo 为 1.12.0，
# 无法读取本项目 net 格式 1.20 的路网。
FROM ubuntu:22.04

ENV SUMO_HOME=/usr/share/sumo
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends software-properties-common \
    && add-apt-repository -y ppa:sumo/stable \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       sumo sumo-tools python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 分层 COPY：先依赖清单再源码，利用构建缓存
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY algorithms/ ./algorithms/
COPY engine/ ./engine/
COPY cloud/ ./cloud/
COPY ml/ ./ml/
COPY scenes/ ./scenes/
COPY experiments/ ./experiments/
COPY api/ ./api/
COPY visualization/ ./visualization/
COPY config/ ./config/
COPY examples/ ./examples/
COPY data/intersection_data/ ./data/intersection_data/

# 默认跑路口 1 固定配时基线；可用 `docker run ca-mp:latest 16` 切换路口
ENTRYPOINT ["python3", "examples/run_fixed_time.py"]
CMD ["1"]
