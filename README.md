# 雄安新区"城市大脑"车路云一体化协同管控算法平台

[![挑战杯 2026](https://img.shields.io/badge/%E6%8C%91%E6%88%98%E6%9D%AF-2026-blue)](https://www.tiaozhanbei.net)
[![编号 XH-202613](https://img.shields.io/badge/%E7%BC%96%E5%8F%B7-XH--202613-orange)](docs/pdf/)
[![赛道 B](https://img.shields.io/badge/%E8%B5%9B%E9%81%93-B%EF%BC%88%E7%AE%97%E6%B3%95%E8%B0%83%E4%BC%98%E5%9E%8B%EF%BC%89-green)](docs/pdf/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)](https://www.python.org)
[![SUMO](https://img.shields.io/badge/SUMO-1.27.1-brightgreen)](https://www.eclipse.org/sumo/)
[![License MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

本项目为挑战杯 2026 参赛作品（编号 XH-202613，赛道 B：算法调优型）。针对雄安
"窄路密网"交通特征（路口间距短、进口道容量低、排队回溢快），提出 **CA-MP
（Capacity-Aware MaxPressure）** 信号控制算法：容量归一化压力、下游溢出门控、
云端动态绿灯三项改进。基于 SUMO 微观仿真，在 20 个真实路口上与固定配时、经典
MaxPressure 对比验证，形成可复现的车路云协同算法优化平台与评委入口。

## 评委快速开始

环境要求：Python 3.12（3.10+ 可运行）、SUMO 1.27.1（安装与校验见
[`docs/sumo_env_setup.md`](docs/sumo_env_setup.md)）。

### 1. 一键启动（原生）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\scripts\start_judge.ps1
```

启动器使用仓库 `.venv`、预检 SUMO/FastAPI/Web 资产、`/api/health` 通过后打开
Web 控制台，诊断写入 `output/evidence/judge-launch/launcher.json`。完整选项与
故障处理见 [`docs/deployment.md`](docs/deployment.md)。

### 2. 演示与矩阵命令（秒数口径）

```powershell
# 100 秒演示（路口 1）
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py --profile smoke --output-root output/runs/matrix-smoke

# 600 秒 quick 演示（路口 1 / 11 / 16）
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py --profile quick --output-root output/runs/matrix-quick

# 540-run 形式矩阵（Task 22 执行并冻结前保持 not_run）
.\.venv\Scripts\python.exe scripts/run_pdf_matrix.py --profile formal `
  --duration-seconds 3600 --warmup-seconds 600 --resume --output-root output/runs/formal
```

实验协议与统计判定：[`docs/release/experiment-protocol.md`](docs/release/experiment-protocol.md)。
产物字段与单位：[`docs/release/evidence-contract.md`](docs/release/evidence-contract.md)。

### 3. Docker 部署（辅助路径）

```powershell
docker compose up --build                 # headless，127.0.0.1:8000
docker compose --profile gui up --build   # container-gui，127.0.0.1:8001
```

镜像契约、证据导出与 live 验证门控见 [`docker/README.md`](docker/README.md)。

## 支持的算法

| Canonical ID | 说明 |
| --- | --- |
| `fixed_time` | 固定配时基线 |
| `classic_max_pressure` | 经典 MaxPressure 基线 |
| `capacity_aware_max_pressure` | CA-MP：容量归一化压力 + 下游溢出门控 + 云端动态绿灯 |

扩展新算法的接口与契约见
[`docs/release/algorithm-extension.md`](docs/release/algorithm-extension.md)。

## 当前证据状态

所有检查严格使用三态：`pass`（当前代码真实执行且门禁通过）、`fail`、
`not_run`（未执行）。

| 证据轴 | 状态 |
| --- | --- |
| 全量 Python 测试（`pytest tests`） | pass（1889 passed, 1 skipped） |
| Web typecheck / build / Playwright judge-flow | pass / pass / pass（15 用例） |
| 静态 Docker 契约（Dockerfile/Compose/lock） | pass |
| 原生 smoke/quick 真实 SUMO 运行 | pass（本机可复现，见上命令） |
| 540-run 形式矩阵（Task 22） | not_run |
| Docker live build/health/smoke/save-load/GUI frames/cleanup | not_run |
| 第二环境复现（Task 23） | not_run |

Docker live 状态的机器实时结果以
`output/evidence/docker/docker-status.json`（detector 输出）为准。

## 数据与场景

| 路径 | 说明 |
| --- | --- |
| `data/intersection_data/` | 20 个雄安路口原始数据（SUMO 工程、流量与配时 Excel、高精地图），只读 |
| `data/intersection_data/metadata/` | 路口元数据汇总（intersections.csv + intersections.yaml） |

导入、校验与场景变体说明见
[`docs/guides/02-import-intersection.md`](docs/guides/02-import-intersection.md)
与 [`docs/interface.md`](docs/interface.md)。

## 项目结构（摘要）

```text
core/            共享数据契约与配置
engine/          SUMO + TraCI 运行器、安全执行、指标采集
scenes/          20 路口注册表、流量变体、配时加载
algorithms/      fixed_time / classic_max_pressure / capacity_aware_max_pressure
cloud/           云端策略（动态绿灯信封）
api/             FastAPI REST + WebSocket + 内置 Web 控制台
experiments/     矩阵、密封证据、配对统计
scripts/         run_pdf_matrix / analyze_matrix / release 工具 / 启动器
web/             React 控制台源码（构建产物经镜像内构建，不入库）
docker/          三阶段镜像 + GUI 派生 + 依赖锁
tests/           全量测试套件
docs/release/    评委向发布文档（协议/证据合同/算法扩展）
```

## 提交材料

正式报告、答辩 PPT、演示方案与视频脚本由冻结的形式矩阵证据生成
（`output/deliverables/`，随 Task 24 交付）；每个数字回链到具体 run 目录。
分支策略与协作规范见 [`docs/guides/git-workflow.md`](docs/guides/git-workflow.md)。

## 许可与致谢

MIT License，见 [LICENSE](LICENSE)。感谢 Eclipse SUMO 社区与出题方提供的
真实路口数据。
