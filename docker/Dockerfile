# CA-MP 仿真平台镜像。SUMO 版本选型见 docs/notes/docker-sumo-research.md。
# Ubuntu 22.04 默认源的 SUMO 1.12.0 无法读取项目使用的 net 格式 1.20，
# 因此使用 ppa:sumo/stable。
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

# 先复制依赖清单，再复制运行时源码和验证脚本，以利用构建缓存。
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY algorithms/ ./algorithms/
COPY api/ ./api/
COPY cloud/ ./cloud/
COPY core/ ./core/
COPY engine/ ./engine/
COPY experiments/ ./experiments/
COPY ml/ ./ml/
COPY scenes/ ./scenes/
COPY visualization/ ./visualization/
COPY config/ ./config/
COPY examples/ ./examples/
COPY scripts/ ./scripts/
COPY data/intersection_data/ ./data/intersection_data/
RUN python3 -m compileall -q .

# 统一走 RunService 支持的实验入口，参数可由 docker run 覆盖。
ENTRYPOINT ["python3", "-m", "experiments.runner"]
CMD ["--intersection", "1", "--algorithm", "fixed_time", "--steps", "100", "--output-dir", "/app/output/runs"]
