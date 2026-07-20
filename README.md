# 雄安新区"城市大脑"车路云一体化协同管控算法平台

[![挑战杯 2026](https://img.shields.io/badge/%E6%8C%91%E6%88%98%E6%9D%AF-2026-blue)](https://www.tiaozhanbei.net)
[![编号 XH-202613](https://img.shields.io/badge/%E7%BC%96%E5%8F%B7-XH--202613-orange)](./docs/pdf/)
[![赛道 B](https://img.shields.io/badge/%E8%B5%9B%E9%81%93-B%EF%BC%88%E7%AE%97%E6%B3%95%E8%B0%83%E4%BC%98%E5%9E%8B%EF%BC%89-green)](./docs/pdf/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org)
[![SUMO](https://img.shields.io/badge/SUMO-1.18+-brightgreen)](https://www.eclipse.org/sumo/)
[![License MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

本项目为挑战杯 2026 参赛作品（编号 XH-202613），围绕雄安新区"城市大脑"车路云一体化场景，针对"窄路密网"交通特征（路口间距短、进口道容量低、排队回溢快），提出 **CA-MP（Capacity-Aware MaxPressure）** 信号控制算法。基于 SUMO 微观仿真平台，在 20 个真实路口上对比验证固定配时、感应控制、CA-MP 三种策略，形成可复现的车路云协同算法优化平台。

---

<a id="目录"></a>

## 目录

- [项目概述](#项目概述)
- [仓库导航](#仓库导航)
- [快速开始](#快速开始)
- [协作指南](#协作指南)
- [项目结构](#项目结构)
- [数据说明](#数据说明)
- [系统架构](#系统架构)
- [核心算法](#核心算法)
- [实验设计](#实验设计)
- [团队分工](#团队分工)
- [开发计划](#开发计划)
- [提交材料](#提交材料)
- [许可与致谢](#许可与致谢)

---

<a id="项目概述"></a>

## 项目概述

<a id="竞赛信息"></a>

### 竞赛信息

| 项目 | 内容 |
|------|------|
| 竞赛 | 挑战杯 2026"揭榜挂帅" |
| 编号 | XH-202613 |
| 题目 | 面向雄安新区"城市大脑"的车路云一体化协同管控算法与仿真平台研究 |
| 出题方 | 雄安国创中心科技有限公司、中雄智图（雄安）科技有限公司 |
| 赛道 | 功能三 赛道 B（算法调优型） |
| 提交截止 | 2026 年 9 月 1 日（内部死线） |
| 团队规模 | 8 人 |

<a id="三大功能模块"></a>

### 三大功能模块

| 功能 | 核心内容 | 系统定位 |
|------|----------|----------|
| 功能一 | 智能交通协同管控算法的抽象设计与建模：场景建模、云-边-端数据接口设计、算法逻辑 | 设计层 |
| 功能二 | 高保真仿真验证平台：场景构建与数据导入、算法接入适配器、可视化验证、Docker 部署 | 平台层 |
| 功能三 | 经典交通管控算法的场景适配与深度优化：固定配时 → 感应控制 → CA-MP | 主战场 |

<a id="核心创新"></a>

### 核心创新（CA-MP 三项改进）

| # | 改进 | 经典 MaxPressure 的问题 | CA-MP 的解法 |
|---|------|------------------------|--------------|
| 1 | 容量归一化压力 | 绝对排队数偏向长车道，短车道（雄安 24m 短边）被忽视 | `pressure = queue / capacity`，短车道自动获得高优先级 |
| 2 | 溢出门控 | 窄路排队回溢堵死上游路口 | 进口道占用率 > 90% 时强制放行，防止死锁 |
| 3 | 云端动态绿灯 | 固定绿灯时长无法适应流量波动 | CloudCoordinator 根据全局压力周期性下发 `base_green`，边缘按压力比例动态分配 |

<a id="当前状态"></a>

### 当前状态

基础框架已完成，源码模块具备可运行骨架，队友可直接在对应文件中继续填充业务逻辑：

- 核心数据契约（`core/types.py`）已定义 JointState、ControlAction、SceneMeta 等共享类型。
- 场景注册（`scenes/registry.py`）已可自动发现 20 个路口，并兼容地图目录命名差异。
- 仿真引擎（`engine/`）已可启动 SUMO、读取状态、写入控制、输出 CSV。
- 算法库（`algorithms/`）已完成标准接口与三种策略骨架，固定配时基线支持 Excel 配时读取。
- 云端策略（`cloud/cloud_policy.py`）、REST API（`api/server.py`）、实验框架（`experiments/`）、可视化（`visualization/`）均已搭好骨架。

---

<a id="仓库导航"></a>

## 仓库导航

<a id="数据集"></a>

### 数据集

| 路径 | 说明 |
|------|------|
| `data/intersection_data/` | 20 个雄安路口原始数据，每个路口包含 SUMO 工程、流量与配时 Excel、高精地图 PNG |
| `data/intersection_data/metadata/` | 路口元数据汇总（intersections.csv + intersections.yaml） |
| `data/intersection_data.zip` | 上述路口数据的完整压缩包（66.7 MB），便于离线传输 |

数据内容详见 [数据说明](#数据说明)。

<a id="竞赛-pdf"></a>

### 竞赛 PDF

| 路径 | 说明 |
|------|------|
| `docs/pdf/XH-202613_面向雄安新区"城市大脑"的车路云.pdf` | 发榜单位提供的原始赛题 PDF，含功能要求、评分标准与提交说明 |

<a id="设计文档"></a>

### 设计文档

| 路径 | 说明 |
|------|------|
| `docs/tasks/roadmap.md` | 项目总路线图（六周里程碑、团队角色、实验设计、风险应对） |
| `docs/tasks/w1/` ~ `docs/tasks/w6/` | 各周个人任务书（8 人 × 6 周） |
| `docs/总路线.md` | 总路线图（同 roadmap，含目录结构） |
| `docs/superpowers/specs/` | 系统设计文档（架构图、接口设计） |
| [`docs/guides/`](docs/guides/) | 协作指南（Git 工作流、Markdown、引用方法） |

---

<a id="快速开始"></a>

## 快速开始

<a id="环境要求"></a>

### 环境要求

- 操作系统：Windows 10/11（推荐）、Linux、macOS
- Python：3.10 或更高版本
- SUMO：1.18 或更高版本
- Git

<a id="安装-sumo"></a>

### 安装 SUMO

1. 访问 [Eclipse SUMO 官方下载页](https://www.eclipse.org/sumo/)。
2. 下载并安装 SUMO 1.18+。
3. 设置环境变量 `SUMO_HOME`：
   - Windows：`SUMO_HOME = C:\Program Files (x86)\Eclipse\Sumo`
   - Linux/macOS：`export SUMO_HOME=/usr/share/sumo`
4. 将 `%SUMO_HOME%\bin` 或 `$SUMO_HOME/bin` 加入 `PATH`。
5. 验证安装：

```bash
sumo --version
```

<a id="安装-python-依赖"></a>

### 安装 Python 依赖

```bash
git clone https://github.com/WuHuMeow/ChallengeCup.git
cd ChallengeCup
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

<a id="验证安装"></a>

### 验证安装

```bash
python -c "import traci; print('traci', traci.__version__)"
python -c "import pandas, numpy; print('all dependencies OK')"
```

<a id="运行最小示例"></a>

### 运行最小示例

路口数据已随仓库提交，位于 `data/intersection_data/`，无需额外配置路径。

```bash
# 运行路口 1 的固定配时基线仿真（3600 步）
python examples/run_fixed_time.py 1

# 运行路口 16（24m 短边，CA-MP 效果最显著）
python examples/run_fixed_time.py 16

# 启动 FastAPI 服务（可选）
uvicorn api.server:app --reload
```

服务启动后访问 http://127.0.0.1:8000/docs 查看自动生成的 API 文档。

<a id="使用本地其他路径的数据"></a>

### 使用本地其他路径的数据（可选）

若需使用仓库外的路口数据，可通过环境变量覆盖：

```bash
# Windows
set CC_DATA_ROOT=C:\path\to\路口数据

# Linux/macOS
export CC_DATA_ROOT=/path/to/路口数据
```

---

<a id="协作指南"></a>

## 协作指南

如果你是第一次参与本仓库，建议先阅读以下指南：

| 指南 | 说明 |
|------|------|
| [Git 工作流](./docs/guides/git-workflow.md) | 如何克隆仓库、提交修改、推送代码、解决冲突 |
| [Markdown 书写方法](./docs/guides/markdown-guide.md) | README、任务书、报告常用 Markdown 语法 |
| [引用方法](./docs/guides/citation-guide.md) | 如何规范引用文献、图片、代码和内部文档 |

### 分支策略

| 分支 | 用途 | 规则 |
|------|------|------|
| `main` | 稳定版本 | 只接受 PR merge，不直接 push |
| `dev` | 开发分支 | 每周日从 main 拉新分支 |
| `feature/<name>` | 功能分支 | 每人一个（如 `feature/algo-ca-mp`、`feature/infra-traci`） |

### 同步节奏

- **每日 21:00**：群内同步"今天完成 + 卡住的问题"（每人不超过 5 行）
- **每周六 21:00**：30 分钟全体同步会
- **卡住 > 4 小时**：群内升级到 TL

---

<a id="项目结构"></a>

## 项目结构

```text
ChallengeCup/
├── core/                       # 全项目共享核心
│   ├── types.py                # JointState / ControlAction / SceneMeta 等数据契约
│   └── config.py               # YAML 配置加载（支持 CC_DATA_ROOT 环境变量覆盖）
├── engine/                     # 仿真引擎（SUMO + TraCI）
│   ├── runner.py               # 单次仿真实验运行器（启动→逐步→决策→采集→关闭）
│   ├── traci_bridge.py         # TraCI 批量读写桥接（JointState ↔ SUMO）
│   └── collector.py            # 每 60 步状态与指标 CSV 采集
├── scenes/                     # 场景管理
│   ├── registry.py             # 20 路口元数据索引（兼容高精地图/高清地图命名差异）
│   ├── variant.py              # 流量变体生成（1.0x / 1.5x）
│   └── timing_loader.py        # 从 Excel 读取信号配时方案（GBK 兼容）
├── algorithms/                 # 算法库
│   ├── base.py                 # BaseControlAlgorithm 标准接口（ABC）
│   ├── fixed_time.py           # 固定配时基线（支持 Excel 配时写入）
│   ├── rule_adaptive.py        # 感应控制 Actuated（排队阈值延长/切换）
│   └── ml_enhanced.py          # CA-MP 容量感知最大压力（核心创新）
├── cloud/                      # 云端策略层
│   └── cloud_policy.py         # CloudCoordinator 全局参数下发 + EWMA 预测
├── ml/                         # ML 模型模块
│   ├── train.py                # EWMA 参数校准
│   ├── features.py             # 特征工程（滑动窗口、排队趋势）
│   └── evaluate.py             # 模型评估（MAE、RMSE）
├── api/                        # REST API（功能一要求）
│   └── server.py               # FastAPI 应用（场景管理、仿真控制、云-边-端接口）
├── experiments/                # 实验分析框架
│   ├── runner.py               # 多场景多算法交叉跑批（360 次仿真）
│   └── metrics.py              # 指标计算（排队、延误、吞吐量、油耗）
├── visualization/              # 可视化
│   └── plots.py                # Matplotlib 图表（对比曲线、热力图）
├── config/
│   └── default.yaml            # 全局配置（路径、SUMO 参数、算法参数）
├── data/                       # 数据集
│   ├── intersection_data/      # 20 个路口原始数据（只读）
│   ├── intersection_data/metadata/  # 路口元数据（CSV + YAML）
│   └── intersection_data.zip   # 路口数据压缩包（66.7 MB）
├── examples/
│   └── run_fixed_time.py       # 最小可运行示例
├── docker/                     # 容器化部署（待实现）
├── docs/                       # 文档
│   ├── pdf/                    # 赛题 PDF
│   ├── tasks/                  # 团队任务书（roadmap + w1~w6）
│   ├── guides/                 # 协作指南
│   ├── superpowers/specs/      # 设计文档 + 架构图（SVG）
│   └── 总路线.md               # 项目总路线图
├── requirements.txt
├── LICENSE                     # MIT
├── .gitignore
└── README.md
```

---

<a id="数据说明"></a>

## 数据说明

<a id="路口数据"></a>

### 路口数据

`data/intersection_data/` 包含 20 个雄安路口的原始数据，编号为 1 至 20。每个路口目录结构如下：

```text
intersection_data/{id}/
├── sumo工程/
│   ├── algorithm.py              # TraCI 启动模板（主办方提供）
│   ├── demo_{id}.net.xml         # SUMO 路网文件（路口几何、车道、信号灯）
│   ├── demo_{id}.rou.xml         # 车辆行驶路径（OD）
│   ├── demo_{id}.flow.xml        # 交通流量定义（各方向到达率）
│   ├── demo_{id}.turn.xml        # 转向比例定义
│   └── demo_{id}.sumocfg         # SUMO 仿真配置（步长、输出）
├── 路口数据/
│   └── demo_{id}流量和交叉口配时方案.xlsx   # 分时段流量统计与信号配时方案
└── 高精地图/                      # 路口 11 为 "高清地图"，已做兼容处理
    └── demo_{id}.png              # 高精地图图片
```

<a id="数据内容"></a>

### 数据内容

| 数据类型 | 文件 | 用途 |
|----------|------|------|
| SUMO 路网 | `.net.xml` | 路口几何、车道数、信号灯相位逻辑 |
| 车辆路径 | `.rou.xml` | 车辆 OD 与行驶路径 |
| 交通流量 | `.flow.xml` | 各方向车辆到达率（183~834 辆/h/方向） |
| 转向比例 | `.turn.xml` | 车辆在路口的左转/直行/右转比例 |
| 仿真配置 | `.sumocfg` | SUMO 运行参数（步长 1s 或 0.1s） |
| 流量与配时 | `.xlsx` | 早/平/晚高峰流量统计 + 三段信号配时方案（GBK 编码） |
| 高精地图 | `.png` | 路口可视化底图 |

<a id="数据差异要点"></a>

### 数据差异要点

| 特征 | 说明 |
|------|------|
| SUMO 版本 | 至少 5 个（1.13.0 / 1.18.0 / 1.23.1 / 1.26.0 / 1.27.1） |
| 仿真步长 | 路口 1-10、14 为 1s；路口 11-13、15-20 为 0.1s |
| 额外输出 | 路口 11-13、15-20 有 queues.xml（queue-output） |
| 流量范围 | 183~834 辆/h/方向，各路口差异极大 |
| 边命名 | 不统一（E0/-E1/-E2/-E3，部分有 -E4/-E5，方向映射各异） |
| 地图目录 | 路口 11 为 `高清地图`，其余为 `高精地图`（代码已兼容） |

<a id="元数据"></a>

### 元数据

`data/intersection_data/metadata/` 提供所有路口的关键参数汇总：

- `intersections.csv`：结构化表格，供批量脚本读取
- `intersections.yaml`：带注释的 YAML 格式，含特殊路口说明

---

<a id="系统架构"></a>

## 系统架构

![系统架构](./docs/superpowers/specs/images/architecture.svg)

<a id="云-边-端协同框架"></a>

### 云-边-端协同框架

赛道 B 在单机进程内用模块边界模拟三层协同：

| 层级 | 模块 | 职责 | 数据契约 |
|------|------|------|----------|
| 云端 | `cloud/cloud_policy.py` | 全局压力评估，EWMA 流量预测，周期性下发参数 | `CloudCommand` |
| 边缘 | `algorithms/ml_enhanced.py` | CA-MP 决策：容量归一化 + 溢出门控 + 动态绿灯 | `JointState` → `ControlAction` |
| 车端/路侧 | `engine/traci_bridge.py` | 接收控制指令写入 SUMO，反馈车辆状态 | `V2XMessage` |

<a id="仿真数据流"></a>

### 仿真数据流

![仿真数据流](./docs/superpowers/specs/images/simulation-loop.svg)

每个仿真步的完整循环：

```
SUMO step → TraCI 读取 → JointState → CA-MP 决策 → ControlAction → 写入 SUMO → 下一步
                                              ↑
                                    CloudCoordinator（EWMA 修正）
```

---

<a id="核心算法"></a>

## 核心算法

<a id="ca-mp-决策逻辑"></a>

### CA-MP 决策逻辑

```python
def ca_mp_decide(state: JointState, cloud_params: CloudCommand) -> SignalAction:
    # 1. 溢出门控：任何进口道占用率 > 90% → 强制放行该方向
    for approach in state.queues:
        if approach.occupancy > 0.9:
            return SignalAction(next_phase=approach.phase, duration=cloud_params.min_green)

    # 2. 容量归一化压力：pressure = queue / capacity
    pressures = {d: q.queue_length / q.capacity for d, q in state.queues.items()}

    # 3. 选最大压力相位
    best_phase = argmax(pressures)

    # 4. 动态绿灯时长：按压力比例分配
    avg_pressure = mean(pressures.values())
    duration = cloud_params.base_green * (pressures[best_phase] / avg_pressure)
    duration = clamp(duration, cloud_params.min_green, cloud_params.max_green)

    return SignalAction(next_phase=best_phase, duration=duration)
```

<a id="算法对比"></a>

### 算法对比

| 算法 | 类型 | ML 介入 | 协同层级 | 实现文件 |
|------|------|---------|----------|----------|
| 固定配时 | 基线 | 无 | 无协同 | `algorithms/fixed_time.py` |
| 感应控制（Actuated） | 基线 | 无 | 边缘独立决策 | `algorithms/rule_adaptive.py` |
| **CA-MP** | **核心创新** | EWMA 流量预测 | 云-边协同 | `algorithms/ml_enhanced.py` |

<a id="ewma-预测"></a>

### EWMA 流量预测

```
predicted_flow(t+1) = α × observed_flow(t) + (1-α) × predicted_flow(t)
```

- α = 0.3（平滑系数，平衡响应速度与稳定性）
- 预测结果用于修正 CA-MP 的 pressure 计算，使决策具有前瞻性
- 轻量级：无需 GPU，单步计算 < 0.1ms

---

<a id="实验设计"></a>

## 实验设计

| 维度 | 方案 |
|------|------|
| 场景 | 20 个路口（主办方提供） |
| 算法 | CA-MP / FixedTime / Actuated（3 种） |
| 流量 | 原始流量 + 1.5 倍压力（2 档） |
| 重复 | 每组 3 次（随机种子 42 / 123 / 456） |
| **总计** | **20 × 3 × 2 × 3 = 360 次仿真** |
| 统计方法 | 配对 t 检验 |

### 评估指标

| 指标 | 来源 | 对应评分维度 |
|------|------|--------------|
| 平均行程时间（s） | tripinfo | 效率 |
| 平均排队长度（veh） | TraCI 实时读取 | 效率 |
| 总吞吐量（veh） | 到达目的地车辆数 | 效率 |
| 平均延误（s/veh） | 等待时间 | 效率 |
| 停车次数（次/veh） | tripinfo.stops | 安全/舒适 |
| 燃油消耗（mL） | tripinfo.fuelAbs | 能耗 |

### 重点验证路口

- **路口 16**：含 24m 短边进口道，CA-MP 容量归一化效果最显著
- **路口 11**：0.1s 步长 + 4 方向标准十字路口，验证步长兼容性
- **路口 1**：标准十字路口，边命名规范（E0/-E1/-E2/-E3），作为基准

---

<a id="团队分工"></a>

## 团队分工

![团队组织](./docs/superpowers/specs/images/team-org.svg)

| 代号 | 角色 | 人数 | 职责概述 | 主要交付 |
|------|------|------|----------|----------|
| TL | Tech Lead | 1 | 架构设计、接口定义、代码合入、集成协调 | `core/types.py` + `algorithms/base.py` + 集成 |
| IA | 仿真基础设施 A | 1 | SUMO 版本统一、20 路口迁移验证 | 20 路口可运行确认 |
| IB | 仿真基础设施 B | 1 | SumoSimulator 封装、TraCI 接口、云-边-端消息流 | `engine/` + 部署文档 |
| AA | 算法 A | 1 | FixedTimeController + ActuatedController（基线） | `fixed_time.py` + `rule_adaptive.py` |
| AB | 算法 B | 1 | CAMaxPressureController（核心创新）+ EWMA 预测 | `ml_enhanced.py` + `cloud/` + `ml/` |
| EX | 实验组 | 1 | 实验矩阵设计、批量运行、指标采集、统计分析 | `experiments/` + 360 次数据 |
| DA | 交付 A | 1 | 报告撰写、PPT 制作、文档排版 | 报告 + PPT |
| DB | 交付 B | 1 | 可视化（Matplotlib + PyQt 看板）、视频录制剪辑 | 图表 + 视频 |

### 个人任务书入口

| 代号 | 角色 | W1 | W2 | W3 | W4 | W5 | W6 |
|------|------|----|----|----|----|----|----|
| TL | Tech Lead | [W1](docs/tasks/w1/TL_tech_lead.md) | [W2](docs/tasks/w2/TL_tech_lead.md) | [W3](docs/tasks/w3/TL_tech_lead.md) | [W4](docs/tasks/w4/TL_tech_lead.md) | [W5](docs/tasks/w5/TL_tech_lead.md) | [W6](docs/tasks/w6/TL_tech_lead.md) |
| IA | 仿真基础设施 A | [W1](docs/tasks/w1/IA_infra_a.md) | [W2](docs/tasks/w2/IA_infra_a.md) | [W3](docs/tasks/w3/IA_infra_a.md) | [W4](docs/tasks/w4/IA_infra_a.md) | [W5](docs/tasks/w5/IA_infra_a.md) | [W6](docs/tasks/w6/IA_infra_a.md) |
| IB | 仿真基础设施 B | [W1](docs/tasks/w1/IB_infra_b.md) | [W2](docs/tasks/w2/IB_infra_b.md) | [W3](docs/tasks/w3/IB_infra_b.md) | [W4](docs/tasks/w4/IB_infra_b.md) | [W5](docs/tasks/w5/IB_infra_b.md) | [W6](docs/tasks/w6/IB_infra_b.md) |
| AA | 算法 A | [W1](docs/tasks/w1/AA_algo_a.md) | [W2](docs/tasks/w2/AA_algo_a.md) | [W3](docs/tasks/w3/AA_algo_a.md) | [W4](docs/tasks/w4/AA_algo_a.md) | [W5](docs/tasks/w5/AA_algo_a.md) | [W6](docs/tasks/w6/AA_algo_a.md) |
| AB | 算法 B | [W1](docs/tasks/w1/AB_algo_b.md) | [W2](docs/tasks/w2/AB_algo_b.md) | [W3](docs/tasks/w3/AB_algo_b.md) | [W4](docs/tasks/w4/AB_algo_b.md) | [W5](docs/tasks/w5/AB_algo_b.md) | [W6](docs/tasks/w6/AB_algo_b.md) |
| EX | 实验组 | [W1](docs/tasks/w1/EX_experiment.md) | [W2](docs/tasks/w2/EX_experiment.md) | [W3](docs/tasks/w3/EX_experiment.md) | [W4](docs/tasks/w4/EX_experiment.md) | [W5](docs/tasks/w5/EX_experiment.md) | [W6](docs/tasks/w6/EX_experiment.md) |
| DA | 交付 A | [W1](docs/tasks/w1/DA_delivery_a.md) | [W2](docs/tasks/w2/DA_delivery_a.md) | [W3](docs/tasks/w3/DA_delivery_a.md) | [W4](docs/tasks/w4/DA_delivery_a.md) | [W5](docs/tasks/w5/DA_delivery_a.md) | [W6](docs/tasks/w6/DA_delivery_a.md) |
| DB | 交付 B | [W1](docs/tasks/w1/DB_delivery_b.md) | [W2](docs/tasks/w2/DB_delivery_b.md) | [W3](docs/tasks/w3/DB_delivery_b.md) | [W4](docs/tasks/w4/DB_delivery_b.md) | [W5](docs/tasks/w5/DB_delivery_b.md) | [W6](docs/tasks/w6/DB_delivery_b.md) |

总路线图：[`docs/tasks/roadmap.md`](docs/tasks/roadmap.md)

---

<a id="开发计划"></a>

## 开发计划

![时间线](./docs/superpowers/specs/images/timeline.svg)

| 阶段 | 时间 | 关键产出 | 里程碑 |
|------|------|----------|--------|
| W1 框架搭建 | 7/20–7/26 | 接口冻结；路口 1 固定配时 + CA-MP 跑通 3600 步 | M1（7/23 接口冻结） |
| W2 算法联调 | 7/27–8/2 | 云-边-端消息流贯通；CA-MP 对比数据；Actuated 完成 | M2（8/2 对比表） |
| W3 全量实验 | 8/3–8/9 | 20 路口 × 3 算法 × 原始流量跑完；图表产出 | M3（8/9 180 次完成） |
| W4 压力测试 | 8/10–8/16 | 1.5 倍流量完成；EWMA 接入；Docker 打包 | M4（8/16 360 次全量） |
| W5 交付制作 | 8/17–8/23 | 报告初稿、PPT 初稿、视频脚本 + 录制 | 报告 v2 |
| W6 打磨提交 | 8/24–8/31 | 全员 review、修 bug、视频定稿、最终提交 | M5（8/31 提交） |

---

<a id="提交材料"></a>

## 提交材料

根据赛题 PDF 第八点，2026 年 9 月 1 日前需提交：

| # | 材料 | 格式 | 负责人 | 状态 |
|---|------|------|--------|------|
| 1 | PPT 汇报 | .pptx | DA | 待制作 |
| 2 | 可运行仿真系统 + 源代码 | 代码仓库 | TL 集成 | 开发中 |
| 3 | 部署运行说明文档 | Markdown | IB | 待创建 |
| 4 | 实验评估报告 | Word | DA + EX | 待创建 |
| 5 | 演示视频（5-8 分钟） | .mp4 | DB | 待录制 |
| 6 | 实际场景演示方案 | Word/Markdown | DA | 待创建 |
| 7 | Dockerfile + 部署文档 | Dockerfile + docs/ | IB | 待创建 |

压缩包命名格式：`学校全称-团队名称-车路云协同管控算法与平台-负责人姓名`

---

<a id="许可与致谢"></a>

## 许可与致谢

[MIT](LICENSE)

本项目为挑战杯 2026 参赛作品，技术方案参考竞赛官方 PDF 要求与雄安新区"城市大脑"车路云一体化场景需求。

### 参考资源

| 资源 | 说明 |
|------|------|
| [SUMO 官方文档](https://sumo.dlr.de/docs/) | 仿真平台文档 |
| [TraCI Python 接口](https://sumo.dlr.de/docs/TraCI.html) | SUMO 实时控制接口 |
| [MaxPressure (Varaiya 2013)](https://doi.org/10.1016/j.trb.2013.08.003) | 经典最大压力控制理论 |
| [LibSignal](https://github.com/LibSignal/LibSignal) | 多算法统一信号控制库 |
| [基于虚拟仿真的雄安新区道路交通系统分析](https://www.doc88.com/p-38873065731422.html) | 雄安路网特征参考 |
