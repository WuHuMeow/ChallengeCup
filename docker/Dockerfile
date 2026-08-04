# CA-MP 仿真平台镜像。SUMO 版本选型见 docs/notes/docker-sumo-research.md。
FROM ubuntu:22.04

ENV SUMO_HOME=/usr/share/sumo
ENV DEBIAN_FRONTEND=noninteractive

# Single RUN with retry wrapper — network can be unreliable
RUN set -e; \
    for attempt in 1 2 3 4 5; do \
      echo "=== Build attempt $attempt ==="; \
      if apt-get update \
          && apt-get install -y --no-install-recommends --fix-missing \
             gnupg curl ca-certificates gpg-agent \
          && curl -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0xC32412BB1ADB414B" \
             | gpg --batch --no-tty --dearmor \
             > /etc/apt/trusted.gpg.d/sumo-ubuntu-stable.gpg \
          && echo "deb https://ppa.launchpadcontent.net/sumo/stable/ubuntu/ jammy main" \
             > /etc/apt/sources.list.d/sumo-ubuntu-stable.list \
          && apt-get update \
          && apt-get install -y --no-install-recommends --fix-missing \
             sumo sumo-tools python3 python3-pip \
          && rm -rf /var/lib/apt/lists/*; \
      then \
        echo "=== Build succeeded on attempt $attempt ==="; \
        exit 0; \
      fi; \
      echo "=== Attempt $attempt failed, cleaning up and retrying... ==="; \
      apt-get install -f -y 2>/dev/null || true; \
      rm -rf /var/lib/apt/lists/*; \
      sleep 10; \
    done; \
    echo "=== All 5 attempts failed ==="; \
    exit 1

WORKDIR /app

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

ENTRYPOINT ["python3", "-m", "experiments.runner"]
CMD ["--intersection", "1", "--algorithm", "fixed_time", "--steps", "100", "--output-dir", "/app/output/runs"]
