# 雄安新区“城市大脑”车路云一体化协同管控算法平台

[![挑战杯 2026](https://img.shields.io/badge/%E6%8C%91%E6%88%98%E6%9D%AF-2026-blue)](https://www.tiaozhanbei.net)
[![编号 XH-202613](https://img.shields.io/badge/%E7%BC%96%E5%8F%B7-XH--202613-orange)](docs/reference/competition/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org)
[![SUMO](https://img.shields.io/badge/SUMO-1.27.1-brightgreen)](https://www.eclipse.org/sumo/)
[![License MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

本项目面向挑战杯 2026 赛题 XH-202613，使用 20 个雄安新区路口的 SUMO 工程，提供固定配时、规则感应控制和 CA-MP 三类策略的统一仿真、实验与展示接口。代码按核心契约、场景、引擎、算法、云端策略、实验和交付工具分层组织。

CA-MP 当前实现是可运行的接口闭环：边缘控制器读取 `JointState`，调用 `CloudPolicy` 的 EWMA 预测，并输出信号控制动作。容量归一化压力、溢出门控和预测融合仍是已知实现限制，不能把现有结果解读为完整算法效果。

## 快速开始

### 环境要求

- Python 3.10 或更高版本。
- 真实仿真使用 SUMO 1.27.1，并确保 `sumo` 位于 `PATH`。
- Mock 演示不需要本机安装 SUMO。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

先运行不依赖 SUMO 的完整调用链演示：

```powershell
python examples/run_demo.py 1 ca_maxpressure
```

安装 SUMO 后，可验证路口数据并运行真实仿真：

```powershell
python scripts/validation/validate_all.py
python examples/run_fixed_time.py 1
python examples/run_ca_max_pressure.py 1 3600
```

单次可复现实验入口：

```powershell
python experiments/runner.py --intersection 1 --algorithm ca_maxpressure `
  --flow-multiplier 1.5 --seed 42 --steps 3600 --output-dir output/exp1
```

启动 REST API：

```powershell
uvicorn api.server:app --reload
```

Swagger UI 位于 `http://127.0.0.1:8000/docs`。API 中 `/health`、`/scenes`、`/run` 和 `/status` 提供轻量状态接口；多数 `/api/*` 路由仍返回占位数据，详见 [api/README.md](api/README.md)。

## 验证命令

从仓库根目录执行：

```powershell
python -m pytest tests/
python scripts/validation/validate_all.py
python scripts/validation/check_outputs.py
```

静态检查使用 Git Bash：

```bash
bash scripts/quality/lint_check.sh
```

测试套件当前收集 66 个测试；SUMO 数据验证和真实仿真需要本机 SUMO 环境。脚本输入、输出与限制见 [scripts/README.md](scripts/README.md)，测试分层见 [tests/README.md](tests/README.md)。

## 仓库结构

```text
challenge-cup/
├── core/                 # 共享数据契约与配置加载
├── scenes/               # 路口发现、流量变体与 Excel 配时读取
├── engine/               # SUMO/Mock 桥接、运行循环、采集与事件日志
├── algorithms/           # 固定配时、规则感应和 CA-MP 控制器
├── cloud/                # EWMA 预测与压力分档参数下发
├── ml/                   # 特征、训练占位实现与预测评估
├── api/                  # FastAPI 服务接口
├── experiments/          # 单次 CLI、批量矩阵与指标计算
├── visualization/        # 实验 CSV 图表输出
├── examples/             # Mock 和真实 SUMO 最小示例
├── config/               # 默认运行时配置
├── data/                 # 20 个只读路口工程及生成的元数据
├── scripts/
│   ├── data/             # 元数据与边映射生成
│   ├── simulation/       # SUMO 配置生成与任务拆分
│   ├── validation/       # 环境、输出、种子与压力验证
│   └── quality/          # 静态检查
├── tests/
│   ├── unit/             # 单模块行为测试
│   └── integration/      # 跨模块接口测试
├── docs/                 # 架构、运维、报告、参考资料与团队文档
├── output/               # 运行时生成物和提交物分区
└── docker/               # 容器镜像定义
```

各目录的职责、接口、输入输出、依赖和限制记录在对应 README 中。

## 模块索引

| 模块 | 职责 | 文档 |
| --- | --- | --- |
| Core | 数据类与 YAML 配置访问 | [core/README.md](core/README.md) |
| Scenes | 场景发现、配时解析、流量变体 | [scenes/README.md](scenes/README.md) |
| Engine | SUMO 生命周期、状态采集和日志 | [engine/README.md](engine/README.md) |
| Algorithms | 统一控制器接口和三类策略 | [algorithms/README.md](algorithms/README.md) |
| Cloud | EWMA 预测与参数下发 | [cloud/README.md](cloud/README.md) |
| ML | 特征、训练接口和误差评估 | [ml/README.md](ml/README.md) |
| API | FastAPI 场景与运行接口 | [api/README.md](api/README.md) |
| Experiments | 单次/批量实验和指标 | [experiments/README.md](experiments/README.md) |
| Visualization | CSV 曲线与热力图输出 | [visualization/README.md](visualization/README.md) |
| Examples | 可直接运行的入口 | [examples/README.md](examples/README.md) |
| Docker | 容器构建与运行 | [docker/README.md](docker/README.md) |
| Config | 默认配置字段 | [config/README.md](config/README.md) |

## 文档索引

[docs/README.md](docs/README.md) 是文档的规范入口。常用资料如下：

| 资料 | 路径 |
| --- | --- |
| 数据契约与模块接口 | [docs/architecture/interface.md](docs/architecture/interface.md) |
| 部署运行说明 | [docs/operations/deployment.md](docs/operations/deployment.md) |
| SUMO 环境安装 | [docs/operations/sumo-environment-setup.md](docs/operations/sumo-environment-setup.md) |
| 边方向映射 | [docs/reference/edge-mapping.md](docs/reference/edge-mapping.md) |
| SUMO 迁移记录 | [docs/reports/sumo-migration-log.md](docs/reports/sumo-migration-log.md) |
| 批量验证报告 | [docs/reports/batch-validation-report.md](docs/reports/batch-validation-report.md) |
| 赛题原始资料 | [docs/reference/competition/](docs/reference/competition/) |
| 项目路线图 | [docs/team/project-roadmap.md](docs/team/project-roadmap.md) |
| 协作指南 | [docs/guides/README.md](docs/guides/README.md) |

团队周任务保存在以下目录；任务书记录计划与验收口径，不代表当前实现状态：

| 周次 | 任务目录 |
| --- | --- |
| W1 | [docs/team/tasks/w1/](docs/team/tasks/w1/) |
| W2 | [docs/team/tasks/w2/](docs/team/tasks/w2/) |
| W3 | [docs/team/tasks/w3/](docs/team/tasks/w3/) |
| W4 | [docs/team/tasks/w4/](docs/team/tasks/w4/) |
| W5 | [docs/team/tasks/w5/](docs/team/tasks/w5/) |
| W6 | [docs/team/tasks/w6/](docs/team/tasks/w6/) |

## 系统架构

![系统架构](docs/architecture/images/architecture.svg)

运行时主链路为：场景注册表提供 `Scene`，`SimulationRunner` 通过 `TraCIBridge` 或 `MockBridge` 生成 `JointState`，算法输出 `ControlAction`，采集器将指标写入 CSV。更完整的字段和调用约束见 [接口文档](docs/architecture/interface.md)。

## 数据与输出

- `data/intersection_data/{1..20}/` 保存原始 SUMO 工程、流量/配时 Excel 和地图图片。原始数据按只读输入处理。
- `data/intersection_data/metadata/` 保存脚本生成的路口元数据和边方向映射。
- `engine/configs/` 保存由 `scripts/simulation/generate_configs.py` 生成的 20 个增强 SUMO 配置。
- `output/csv/`、`output/logs/`、`output/variants/` 和 `output/validate*/` 保存运行产物；目录契约见 [output/README.md](output/README.md)。

可用 `CC_DATA_ROOT` 临时覆盖数据根目录：

```powershell
$env:CC_DATA_ROOT = "D:\data\intersection_data"
```

## 已知限制

- CA-MP 当前控制动作仍以最长队列为主，尚未完成容量归一化压力、溢出门控和预测融合。
- `/api/*` 协同端点多数是接口占位，不会启动真实仿真或返回真实控制结果。
- `ml.train()` 返回默认参数，`ml.predict()` 使用流量均值；它们不是已训练模型。
- 部分实验指标是基于实时状态的近似值；精确行程时间和燃油消耗需结合 SUMO `tripinfo`。
- Docker 镜像定义包含 SUMO 和验证脚本，但仓库不记录可跨机器复用的构建性能结论。

## 许可

项目采用 [MIT License](LICENSE)。
