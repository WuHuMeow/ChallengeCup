# 部署运行说明（IA W4 Day 4 / W5 Day 3 最终版）

> 赛题 PDF 硬性要求的"详细的部署运行说明文档"。
> 环境前提详见 `docs/sumo_env_setup.md`；Docker 方案选型见 `docs/notes/docker_sumo_research.md`。

## 快速开始（3 步跑通）

```bash
docker build -t ca-mp:latest -f docker/Dockerfile .
docker run --rm -v ${PWD}/output:/app/output ca-mp:latest 1
ls output/csv/        # 仿真指标 CSV
```

## 1. 本地部署（Windows / Mac / Linux）

```bash
git clone https://github.com/WuHuMeow/ChallengeCup.git
cd ChallengeCup
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt

# 安装 SUMO 1.27.1 并设置 SUMO_HOME（步骤见 docs/sumo_env_setup.md）
python scripts/validate_all.py        # 环境自检：期望 20/20 PASS
python examples/run_fixed_time.py 1   # 跑路口 1 固定配时基线
```

平台差异：

- **Windows**：路径用 `\` 或 `/` 均可；环境变量在"系统属性 → 环境变量"设置，或用 PowerShell（见 `docs/sumo_env_setup.md` 第 2 节）。
- **Linux**：SUMO 通过 `ppa:sumo/stable` 安装（`apt install sumo sumo-tools`），`SUMO_HOME=/usr/share/sumo`。
- **macOS**：`brew install sumo`，`SUMO_HOME=$(brew --prefix)/share/sumo`。

## 2. Docker 部署

```bash
# 构建（在项目根目录执行）
docker build -t ca-mp:latest -f docker/Dockerfile .

# 运行指定路口（ENTRYPOINT 为 examples/run_fixed_time.py，参数即路口 ID）
docker run --rm -v ${PWD}/output:/app/output ca-mp:latest 16

# 或用 compose（默认路口 16，output 与 experiments/results 挂载到宿主机）
docker-compose up --build
docker-compose run --rm simulation 1    # 临时切换路口
```

容器内自检：

```bash
docker run --rm --entrypoint sumo ca-mp:latest --version     # 期望 1.27.x
docker run --rm --entrypoint python3 ca-mp:latest scripts/validate_all.py
```

## 3. 常见问题

| 问题 | 现象 | 解决 |
|------|------|------|
| `SUMO_HOME` 未设置 | `无法导入 traci…` | 见 `docs/sumo_env_setup.md` 第 2 节；Docker 镜像内已预设 |
| 镜像内 SUMO 版本过旧 | `network file format version '1.20' is not supported` | 必须用 `ppa:sumo/stable`（Dockerfile 已内置）；不要直接用 Ubuntu 默认源（1.12.0） |
| Windows 卷挂载报错 | `docker run -v ${PWD}/output:…` 路径非法 | 用绝对路径，PowerShell 为 `${PWD}`、CMD 为 `%cd%`、Git Bash 为 `$(pwd -W)` |
| 镜像拉取/构建慢 | apt/pip 超时 | 配置 apt 与 pip 国内镜像源后重建 |
| 端口冲突 | API 服务 8000 被占 | `uvicorn api.server:app --port 8001` 换端口 |
| 输出目录权限 | 容器内写 `/app/output` 失败 | 挂载目录预先 `mkdir -p output`，Linux 下注意属主 |

## 4. 输出文件说明

| 位置 | 内容 | 消费者 |
|------|------|--------|
| `output/csv/{路口}_{算法}.csv` | 每 60 步指标快照（排队、延误、吞吐量） | EX 分析、DB 图表 |
| `output/validate/{N}/` | 批量验证产物（tripinfo / traj / stats / queues） | IA 环境验收 |
| `experiments/results/…` | 实验矩阵输出（EX 管理） | EX 统计分析 |
| `tripinfo.xml` | 每车行程时间、等待、停车次数、油耗 | EX 指标计算 |
| `traj.xml`（fcd） | 每步车辆位置速度 | DB 时空轨迹图 |
| `stats.xml`（summary） | 每步全网统计 | 运行健康检查 |

## 完整实验复现（360 组）

```bash
# 1. 环境自检
python scripts/validate_all.py              # 20/20 PASS

# 2. 全量实验（EX 侧入口；矩阵 = 20 路口 × 3 算法 × 2 流量 × 3 种子）
python experiments/runner.py --help          # 查看批量参数

# 3. 输出完整性检查
python scripts/check_outputs.py              # 期望 缺失/空文件: 0
```

实测基准（2026-07-23，单机 Windows + SUMO 1.27.1）：20 路口 3600 步全量验证合计约 60s，
估算 360 次实验 ≈ 0.3h（详见 `docs/batch_validate_report.md`）。

## 镜像指标

| 指标 | 目标 | 实测 |
|------|------|------|
| 镜像大小 | < 2GB | 待 W4 在有 Docker 的机器上构建后回填 |
| 构建时间 | - | 同上 |
