# Judge release image (Task 19). Contract:
# docs/superpowers/specs/2026-08-24-docker-judge-deployment-design.md Sections 3.1-3.5
# Immutable bases (2026-08-24); changing a digest is a reviewed dependency update.

FROM --platform=linux/amd64 node:20.19.5-bookworm-slim@sha256:9e70124bd00f47dd023e349cd587132ae61892acc0e47ed641416c3e18f401c3 AS web-builder

WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM --platform=linux/amd64 python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS python-builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /install
COPY docker/requirements.in docker/requirements.lock ./
RUN pip install --require-hashes --only-binary :all: -r docker/requirements.lock

FROM --platform=linux/amd64 python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS runtime

ARG TASK19_INVOCATION_ID=manual
LABEL io.challengecup.task19.invocation=$TASK19_INVOCATION_ID

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    TMPDIR=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    XDG_CACHE_HOME=/tmp/cache \
    SUMO_HOME=/opt/sumo

COPY --from=python-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin

# The eclipse-sumo wheel's executables dynamically link X11/GL (not vendored
# by manylinux and absent from slim-bookworm); without these loader libraries
# every version gate and simulation run aborts before printing a version.
# Packages resolve from the frozen Bookworm snapshot for reproducibility.
RUN printf '%s\n' \
      'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20260824T000000Z bookworm main' \
      > /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends \
        libx11-6 libxext6 libxrender1 libgl1 \
    && rm -rf /var/lib/apt/lists/* /etc/apt/sources.list

# The wheel ships its own SUMO_HOME tree; expose it at a stable path and put
# the applications on PATH before verifying the frozen versions.
RUN set -eux; \
    wheel_sumo_home="$(python -c 'import sumo, pathlib; print(pathlib.Path(sumo.__file__).parent)')"; \
    ln -s "$wheel_sumo_home" /opt/sumo; \
    for tool in sumo sumo-gui netconvert; do \
      ln -s "/opt/sumo/bin/$tool" "/usr/local/bin/$tool"; \
    done; \
    sumo --version | grep -F "1.27.1"; \
    sumo-gui --version | grep -F "1.27.1"; \
    python -c "from importlib.metadata import version; \
assert version('eclipse-sumo') == '1.27.1', version('eclipse-sumo'); \
assert version('traci') == '1.27.1', version('traci'); \
assert version('sumolib') == '1.27.1', version('sumolib')"

RUN groupadd -g 10001 judge
RUN useradd -u 10001 -g 10001 -m -s /usr/sbin/nologin judge

# Application code and official scene inputs stay root-owned (read-only for
# judge); every runtime write is confined to /app/output and /tmp.
COPY algorithms/ ./algorithms/
COPY api/ ./api/
COPY cloud/ ./cloud/
COPY core/ ./core/
COPY engine/ ./engine/
COPY experiments/ ./experiments/
COPY ml/ ./ml/
COPY scenes/ ./scenes/
COPY scripts/ ./scripts/
COPY visualization/ ./visualization/
COPY config/ ./config/
COPY data/intersection_data ./data/intersection_data
COPY pyproject.toml ./pyproject.toml
COPY --from=web-builder /build/api/static/dist ./api/static/dist

RUN mkdir -p /app/output \
    && chown judge:judge /app/output

EXPOSE 8000

USER judge

ENTRYPOINT ["python", "scripts/run_judge.py"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--port-attempts", "1", "--no-browser", "--gui-mode", "headless", "--diagnostics", "/app/output/evidence/docker/launcher.json"]
