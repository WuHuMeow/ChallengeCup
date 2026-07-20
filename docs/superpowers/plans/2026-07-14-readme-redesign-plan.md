# README Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `README.md` into a comprehensive dual-audience entry point (judges + developers), create supporting project scaffolding, and fix inconsistent project-structure descriptions in existing Markdown docs.

**Architecture:** Keep the existing `docs/` structure and SVG assets; add source-directory skeletons (`engine/`, `scenes/`, `algorithms/`, `ml/`, `api/`, `experiments/`, `visualization/`, `config/`, `docker/`, `output/`) with per-module `README.md` files; rewrite top-level `README.md` with badges, TOC, environment setup, quick start, and navigation to existing docs.

**Tech Stack:** Markdown, Git, SUMO 1.18, Python 3.10+, FastAPI, XGBoost, Matplotlib.

## Global Constraints

- Keep all artifacts in Chinese, except technical terms (SUMO, TraCI, XGBoost, FastAPI, etc.).
- Do not modify `.gitignore` or existing SVG images.
- All internal links in `README.md` must resolve to actual files/directories after the plan runs.
- Do not add implementation code beyond module-level `README.md` explanations.
- `requirements.txt` must include only dependencies already named in the design spec.

---

## Task 1: Create Source Directory Skeleton

**Files:**
- Create: `engine/README.md`
- Create: `scenes/README.md`
- Create: `algorithms/README.md`
- Create: `ml/README.md`
- Create: `api/README.md`
- Create: `experiments/README.md`
- Create: `visualization/README.md`
- Create: `config/README.md`
- Create: `docker/README.md`
- Create: `output/README.md`

**Interfaces:**
- Consumes: existing design doc module descriptions in `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md` §三、§十.
- Produces: a directory tree that matches the structure shown in `README.md` and the design doc.

- [ ] **Step 1: Create `engine/README.md`**

```markdown
# engine/ — 仿真引擎

封装 SUMO 生命周期与 TraCI 数据读写。

## 规划文件

- `runner.py` — SUMO 启动 / 停止 / 重置，支持命令行批量运行。
- `traci_bridge.py` — TraCI 批量读写：车辆位置、速度、信号灯状态、排队长度。
- `collector.py` — 每个仿真步采集状态数据，输出 CSV 供 ML 训练。

## 职责边界

`engine/` 只负责"把 SUMO 跑起来并把数据读出来"，不做算法决策。
```

- [ ] **Step 2: Create `scenes/README.md`**

```markdown
# scenes/ — 场景管理（功能一）

20 个雄安路口 SUMO 工程与流量变体管理。

## 规划文件

- `registry.py` — 20 路口元数据索引（车道数、默认流量、配时方案）。
- `variant.py` — 场景变体生成：每个路口生成 0.5x / 1.0x / 3.0x 三个流量等级。
- `validator.py` — 场景校验，跑一轮无算法仿真检查车辆是否全部完成行程。
- `data/` — 20 个路口 SUMO 工程文件（`.net.xml`、`.rou.xml`、`.sumocfg` 等）。

## 数据约定

`scenes/data/` 为只读原始数据，生成的变体写入临时输出目录，不污染源码。
```

- [ ] **Step 3: Create `algorithms/README.md`**

```markdown
# algorithms/ — 算法库（功能二 + 功能三）

三种递进式交通控制策略。

## 规划文件

- `base.py` — 标准算法接口（ABC）。
- `fixed_time.py` — 固定配时基线（对照组）。
- `rule_adaptive.py` — 规则自适应算法（中间对比）。
- `ca_max_pressure.py` — ML 增强算法（主打）：加载 `ml/model.pkl` 进行预测驱动配时。

## 接口约定

```python
class BaseControlAlgorithm(ABC):
    def init(self, scene: Scene) -> None: ...
    def step(self, state: JointState) -> list[ControlAction]: ...
    def reset(self) -> None: ...
```
```

- [ ] **Step 4: Create `ml/README.md`**

```markdown
# ml/ — ML 模型模块（赛道 B 核心）

XGBoost 流量预测与模型评估。

## 规划文件

- `train.py` — XGBoost 回归训练脚本。
- `features.py` — 特征工程：滑动窗口、one-hot、归一化。
- `evaluate.py` — 模型评估：RMSE、MAE、R²、残差分析。
- `model.pkl` — 训练产出，推理时由 `algorithms/ca_max_pressure.py` 加载。

## 数据流

```
SUMO 仿真 CSV
  → 特征工程
    → XGBoost 训练
      → model.pkl + 评估报告
        → 算法运行时推理
```
```

- [ ] **Step 5: Create `api/README.md`**

```markdown
# api/ — REST API（功能一要求）

轻量实验控制接口，基于 FastAPI。

## 规划文件

- `server.py` — FastAPI 应用入口。
- `routes/` — 各端点路由实现。

## 核心端点

- `GET    /api/scenes`
- `POST   /api/scenes/{id}/load`
- `POST   /api/simulation/start`
- `POST   /api/simulation/stop`
- `GET    /api/algorithms`
- `POST   /api/algorithm/switch`
- `POST   /api/experiments/run`
- `GET    /api/experiments/compare`
- `GET    /api/metrics/current`
```

- [ ] **Step 6: Create `experiments/README.md`**

```markdown
# experiments/ — 实验分析框架

多场景 × 多算法交叉跑批与统计分析。

## 规划文件

- `runner.py` — 20 路口 × 3 流量 × 3 算法 = 180 次仿真实验跑批。
- `metrics.py` — 指标采集：平均排队长度、平均延误、总通行量、停车次数。
- `analyzer.py` — 统计检验（配对 t 检验 / Mann-Whitney U）与报告生成。
```

- [ ] **Step 7: Create `visualization/README.md`**

```markdown
# visualization/ — 可视化

算法效果与预测结果可视化。

## 规划文件

- `plots.py` — Matplotlib / Seaborn 图表：排队长度曲线、信号相位时序图、对比曲线、热力图。
- `report.py` — 实验报告图表自动化生成。
```

- [ ] **Step 8: Create `config/README.md`**

```markdown
# config/ — 全局配置

项目级配置与默认参数。

## 规划文件

- `default.yaml` — 仿真步长、训练参数、API 端口等默认配置。
```

- [ ] **Step 9: Create `docker/README.md`**

```markdown
# docker/ — Docker 镜像

可复现的运行环境。

## 规划文件

- `Dockerfile` — 基于 Python 3.10+，预装 SUMO 1.18 与 Python 依赖。
- `docker-compose.yml` — 一键启动仿真 + API 服务。
```

- [ ] **Step 10: Create `output/README.md`**

```markdown
# output/ — 提交材料输出

竞赛提交物与运行产物（不进入版本控制核心，但保留说明文件）。

## 预期内容

- 实验报告图表
- Demo 视频
- PPT 素材
- 模型评估报告

## 注意

大体积输出文件应通过 `.gitignore` 忽略，仅保留说明文档。
```

- [ ] **Step 11: Verify directories exist**

Run:

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
find engine scenes algorithms ml api experiments visualization config docker output -maxdepth 1 -name 'README.md' | sort
```

Expected output: 10 paths, one for each directory above.

- [ ] **Step 12: Commit**

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
git add engine/ scenes/ algorithms/ ml/ api/ experiments/ visualization/ config/ docker/ output/
git commit -m "docs: add source directory skeleton with per-module READMEs"
```

---

## Task 2: Create requirements.txt

**Files:**
- Create: `requirements.txt`

**Interfaces:**
- Consumes: tech stack table in `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md` §2.3.
- Produces: a dependency list used by the environment-install section in `README.md`.

- [ ] **Step 1: Write `requirements.txt`**

```text
# 仿真
traci>=1.18.0
sumolib>=1.18.0

# 数据处理与 ML
pandas>=2.0.0
numpy>=1.24.0
xgboost>=2.0.0
scikit-learn>=1.3.0
scipy>=1.11.0

# 可视化
matplotlib>=3.7.0
seaborn>=0.12.0

# Web API
fastapi>=0.100.0
uvicorn[standard]>=0.23.0

# 配置
pyyaml>=6.0
```

- [ ] **Step 2: Verify file is parseable**

Run:

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
python -c "import pkg_resources; pkg_resources.parse_requirements(open('requirements.txt', encoding='utf-8').read())" && echo "OK"
```

Expected: `OK` (no exception).

- [ ] **Step 3: Commit**

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
git add requirements.txt
git commit -m "chore: add requirements.txt with SUMO, ML, API and viz dependencies"
```

---

## Task 3: Rewrite README.md

**Files:**
- Modify: `README.md` (complete rewrite)

**Interfaces:**
- Consumes: design doc `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md`, team doc `docs/tasks/README.md`, and SVG images in `docs/superpowers/specs/images/`.
- Produces: a comprehensive `README.md` with badges, TOC, environment setup, quick start, project structure, docs navigation, milestones, team, scoring alignment, and submission checklist.

- [ ] **Step 1: Write the new `README.md`**

Content (save as `README.md`):

```markdown
# 🏙️ 雄安新区"城市大脑"车路云一体化 — 智能交通管控算法优化

[![挑战杯 2026](https://img.shields.io/badge/挑战杯-2026-blue)](https://www.tiaozhanbei.net)
[![编号 XH-202613](https://img.shields.io/badge/编号-XH--202613-orange)](./docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md)
[![赛道 B](https://img.shields.io/badge/赛道-B（算法优化型+ML增强）-green)](./docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org)
[![SUMO](https://img.shields.io/badge/SUMO-1.18+-brightgreen)](https://www.eclipse.org/sumo/)

> **一句话描述**：基于 SUMO 微观仿真，在雄安新区 20 个真实路口上对比验证"固定配时 → 规则自适应 → XGBoost ML 增强"三种交通管控策略，形成可复现的车路云协同算法优化平台。

---

## 📑 目录

- [项目概览](#项目概览)
  - [竞赛信息](#竞赛信息)
  - [项目背景](#项目背景)
  - [三大功能模块](#三大功能模块)
- [🚀 核心创新点](#-核心创新点)
- [🏗️ 系统架构](#️-系统架构)
- [🧠 核心策略](#-核心策略)
- [🧪 实验设计](#-实验设计)
- [🛠️ 环境安装](#️-环境安装)
  - [系统要求](#系统要求)
  - [安装 SUMO](#安装-sumo)
  - [安装 Python 依赖](#安装-python-依赖)
  - [验证安装](#验证安装)
- [⚡ 快速开始](#-快速开始)
- [📁 项目结构](#-项目结构)
- [📚 文档与接口导航](#-文档与接口导航)
- [📅 开发阶段与里程碑](#-开发阶段与里程碑)
- [👥 团队分工](#-团队分工)
- [🎯 评分对标](#-评分对标)
- [📦 提交材料清单](#-提交材料清单)
- [📄 许可与致谢](#-许可与致谢)

---

## 项目概览

### 竞赛信息

| 项目 | 内容 |
|------|------|
| **竞赛** | 挑战杯 2026 |
| **编号** | XH-202613 |
| **赛道** | 功能三 → 赛道 B（算法优化型 + ML 增强） |
| **提交截止** | 2026 年 9 月 15 日 |
| **团队规模** | 8 人（含 2 位负责人） |

### 项目背景

雄安新区作为"未来之城"，其"城市大脑"需要一套智能化交通协同管控系统。本项目围绕"车-路-云"一体化架构，针对雄安新区"窄路密网"特征，在 **20 个真实路口** 上完成交通管控算法的深度优化与对比验证。

### 三大功能模块

| 功能 | 核心内容 | 在本系统中的定位 |
|------|----------|-----------------|
| **功能一** | 仿真场景构建与数据接口定义 | 为算法提供"标准化测试靶场" + 数据接口 |
| **功能二** | 算法逻辑实现与可视化验证 | 算法的"基础实现与验证" |
| **功能三（赛道B）** | 基于 ML（XGBoost）增强的交通管控算法深度优化 | **主战场**：AI 与传统控制融合 + 科学对比实验 |

---

## 🚀 核心创新点

1. **AI 与传统控制融合**  
   不是纯 ML 端到端黑盒，而是 **XGBoost 预测 + 规则决策**，在提升效果的同时保留可解释性。

2. **预测驱动的主动控制**  
   不等排队堆积再反应，而是根据未来 5 分钟流量预测提前预调配时。

3. **标准化对比实验**  
   **20 路口 × 3 流量等级 × 3 算法 = 180 次仿真**，配合统计显著性检验，量化 ML 的增量价值。

---

## 🏗️ 系统架构

![系统架构](./docs/superpowers/specs/images/architecture.png)

**数据流**：SUMO 仿真 → TraCI 数据采集 → CSV 数据集 → XGBoost 训练 → `ml/model.pkl` → 算法推理 → 指标输出 → 可视化报告。

---

## 🧠 核心策略

```
固定配时基线 → 规则自适应 → ML 增强算法（XGBoost）
   (对照组)       (中间对比)       (主打)
```

| 算法 | 定位 | ML 介入 | 协同层级 |
|------|------|---------|----------|
| **固定配时基线** | 对照组，读取 Excel 配时方案 | 无 | 无协同 |
| **规则自适应** | 中间对比态，根据实时排队长度动态调整绿灯时长 | 无 | 单路口独立优化 |
| **ML 增强算法** | 主打：XGBoost 预测 + 规则融合，提前预判流量变化 | XGBoost 预测 4 方向未来流量 | 单路口 AI 增强 |

---

## 🧪 实验设计

| 维度 | 方案 |
|------|------|
| **场景** | 20 个路口 × 3 个流量等级（0.5x / 1.0x / 3.0x）= 60 个变体 |
| **算法** | 固定配时 / 规则自适应 / ML 增强 = 3 种 |
| **指标** | 平均排队长度、平均车辆延误、总通行量、停车次数 |
| **总实验次数** | 60 × 3 = **180 次仿真** |
| **统计方法** | 配对 t 检验（固定 vs 自适应 / 自适应 vs ML 增强） |

---

## 🛠️ 环境安装

### 系统要求

- **操作系统**：Windows 10/11（推荐）、Linux、macOS
- **Python**：3.10 或更高版本
- **SUMO**：1.18 或更高版本
- **Git**：用于克隆仓库

### 安装 SUMO

1. 访问 [Eclipse SUMO 官方下载页](https://www.eclipse.org/sumo/)。
2. 下载并安装 SUMO 1.18+。
3. 设置环境变量 `SUMO_HOME`：
   - **Windows**：`SUMO_HOME = C:\Program Files (x86)\Eclipse\Sumo`（根据实际安装路径调整）
   - **Linux/macOS**：`export SUMO_HOME=/usr/share/sumo`
4. 将 `%SUMO_HOME%\bin`（Windows）或 `$SUMO_HOME/bin`（Linux/macOS）加入 `PATH`。
5. 验证：

```bash
sumo --version
```

应显示 SUMO 版本号。

### 安装 Python 依赖

```bash
# 1. 克隆仓库
git clone https://gitee.com/fyx0927/challenge-cup.git
cd challenge-cup

# 2. 创建虚拟环境（推荐）
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
```

### 验证安装

```bash
# 验证 SUMO Python 绑定
python -c "import traci; print('traci', traci.__version__)"

# 验证核心依赖
python -c "import pandas, numpy, xgboost, fastapi; print('all dependencies OK')"
```

---

## ⚡ 快速开始

> 当前项目处于开发初期，源码模块正在按计划搭建。以下命令为规划中的最小可运行示例，实际命令将随代码实现更新。

```bash
# 1. 加载环境
cd ChallengeCup
.venv\Scripts\activate

# 2. 运行单个路口的固定配时基线仿真（示例）
python engine/runner.py --scene scenes/data/intersection_01 --algorithm fixed_time

# 3. 启动 FastAPI 服务（可选）
uvicorn api.server:app --reload
```

服务启动后，访问 http://127.0.0.1:8000/docs 查看自动生成的 API 文档。

---

## 📁 项目结构

```text
ChallengeCup/
├── engine/                 # 仿真引擎（SUMO + TraCI）
│   ├── runner.py           # SUMO 生命周期管理
│   ├── traci_bridge.py     # TraCI 批量读写
│   └── collector.py        # 数据采集 → CSV
├── scenes/                 # 场景管理（功能一）
│   ├── registry.py         # 20 路口元数据索引
│   ├── variant.py          # 场景变体生成（3 个流量等级）
│   ├── validator.py        # 场景校验
│   └── data/               # 20 个路口 SUMO 工程（只读）
├── algorithms/             # 算法库（功能二 + 功能三）
│   ├── base.py             # 标准算法接口（ABC）
│   ├── fixed_time.py       # 固定配时基线
│   ├── rule_adaptive.py    # 规则自适应算法
│   └── ca_max_pressure.py      # ML 增强算法（主打）
├── ml/                     # ML 模型模块（赛道 B 核心）
│   ├── train.py            # XGBoost 训练脚本
│   ├── features.py         # 特征工程
│   ├── evaluate.py         # 模型评估
│   └── model.pkl           # 训练产出（推理用）
├── api/                    # REST API（功能一要求）
│   ├── server.py           # FastAPI 应用
│   └── routes/
├── experiments/            # 实验分析框架
│   ├── runner.py           # 多场景多算法交叉跑批
│   ├── metrics.py          # 指标采集
│   └── analyzer.py         # 统计检验 + 报告
├── visualization/          # 可视化
│   ├── plots.py            # Matplotlib 图表
│   └── report.py           # 报告生成
├── config/
│   └── default.yaml        # 全局配置
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── output/                 # 提交材料与运行产物
├── docs/                   # 文档
│   ├── api-spec.md         # 接口文档（功能一产出，待创建）
│   ├── experiment-report.md # 实验报告（待创建）
│   ├── superpowers/specs/  # 设计文档
│   │   ├── 2026-07-14-xiongan-vehicle-road-cloud-design.md
│   │   ├── 2026-07-14-readme-redesign-design.md
│   │   └── images/         # 架构图、依赖图等 SVG
│   └── team/               # 团队分工
│       ├── README.md
│       └── 成员1-仿真引擎/任务书.md
│       └── ...
├── requirements.txt        # Python 依赖
├── .gitignore
└── README.md
```

> 当前源码目录（`engine/`、`algorithms/`、`ml/` 等）已建立骨架，每个目录下包含 `README.md` 说明模块职责，具体实现按里程碑推进。

---

## 📚 文档与接口导航

| 文档 | 说明 | 路径 |
|------|------|------|
| 📐 完整设计文档 | 架构设计、模块详情、分工、里程碑 | [`docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md`](./docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md) |
| 📋 本 README 重设计文档 | README  redesign 方案 | [`docs/superpowers/specs/2026-07-14-readme-redesign-design.md`](./docs/superpowers/specs/2026-07-14-readme-redesign-design.md) |
| 👥 团队分工 | 8 成员4 组详细任务 | [`docs/tasks/README.md`](./docs/tasks/README.md) |
| 🔌 API 接口文档 | 功能一产出：接口定义与 Postman Collection | `docs/api-spec.md`（待创建） |
| 📊 实验报告 | 180 次仿真分析与统计检验 | `docs/experiment-report.md`（待创建） |

---

## 📅 开发阶段与里程碑

| 阶段 | 时间 | 关键产出 | 里程碑 |
|------|------|----------|--------|
| **P1 基础搭建** | 7.16–7.30 | 1 个路口固定配时跑通 + 第一批 CSV 数据 | **M1（7.23）** |
| **P2 核心开发** | 7.31–8.20 | XGBoost model.pkl v1 + 规则自适应 + ML 增强集成 | **M2（8.5）**、**M3（8.15–8.20）** |
| **P3 集成联调** | 8.21–9.2 | 180 次全量跑批 + 对比报告 | **M4（8.28）** |
| **P4 打磨交付** | 9.3–9.9 | PPT + Demo 视频 + 报告终稿 | **M5（9.9）** |
| **P5 缓冲冲刺** | 9.10–9.14 | 答辩模拟 + 最后一轮集成测试 | 9.15 提交 |

详见 [完整设计文档 §九](./docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md#九开发阶段与里程碑9-周)。

---

## 👥 团队分工

| 组 | 成员 | 主责 |
|----|------|------|
| 仿真场景组 | 成员1、成员2 | SUMO 引擎封装、20 路口场景管理、CSV 数据采集 |
| 算法 ML 组 | 成员3、成员4 | 算法接口与三种策略实现、XGBoost 训练与评估 |
| 实验分析组 | 成员5、成员8 | 180 次跑批、指标采集、统计检验、Docker 工程化 |
| 可视化与交付 | 🔷 成员6（后端负责）、🔶 成员7（前端负责） | FastAPI、可视化图表、PPT、Demo 视频 |

详细分工与个人任务书见 [`docs/tasks/README.md`](./docs/tasks/README.md)。

---

## 🎯 评分对标

| 评分维度 | 满分 | 本项目对应 |
|----------|------|-----------|
| **创新性** | 25 | XGBoost 预测 + 规则融合的 AI 与传统控制结合；预测驱动主动控制 vs 传统被动响应 |
| **系统实现与功能完成度** | 30 | 三种算法完整实现（基线 → 自适应 → ML增强）；20 路口 60 场景仿真验证；标准化 API 接口 |
| **实验验证与分析** | 20 | 180 次仿真跑批；多维度指标（排队/延误/通行量/停车次数）；统计显著性检验；vs 传统信号控制对比 |
| **工程化与标准价值** | 10 | 标准算法接口（ABC）；接口文档（Postman）；场景变体生成标准化；Docker 可复现 |
| **团队答辩与表达** | 15 | 前后端负责人双层管理；PPT 专人 + 视频专人；模拟答辩演练 |

---

## 📦 提交材料清单

根据挑战杯赛道 B 要求，最终需提交：

| 材料 | 格式 | 状态 | 路径 |
|------|------|------|------|
| 系统说明 / 算法介绍 | PPT | 待制作 | `output/` |
| 仿真系统与算法源码 | 源代码 | 开发中 | `engine/`、`algorithms/`、`ml/` 等 |
| 实验验证与分析文档 | Word / Markdown | 待创建 | `docs/experiment-report.md` |
| 系统演示视频 | 视频（5–8 分钟） | 待录制 | `output/` |
| 接口文档 | Markdown / Postman Collection | 待创建 | `docs/api-spec.md` |

---

## 📄 许可与致谢

本项目为挑战杯 2026 参赛作品，技术方案参考竞赛官方 PDF 要求与雄安新区"城市大脑"车路云一体化场景需求。

如有问题，欢迎通过团队分工文档中的联系方式交流。
```

- [ ] **Step 2: Verify README renders without broken links**

Run:

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
python -c "
import re, os
with open('README.md', 'r', encoding='utf-8') as f:
    text = f.read()
links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text)
broken = []
for label, path in links:
    if path.startswith('http') or path.startswith('#'):
        continue
    if not os.path.exists(path):
        broken.append(path)
if broken:
    print('Broken links:', broken)
    exit(1)
print('All local links OK')
"
```

Expected: `All local links OK`

- [ ] **Step 3: Commit**

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
git add README.md
git commit -m "docs: rewrite README with navigation, setup, quick start, and scoring alignment"
```

---

## Task 4: Update Design Doc Directory Structure

**Files:**
- Modify: `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md` §十

**Interfaces:**
- Consumes: actual directory tree after Task 1.
- Produces: an accurate directory structure section consistent with `README.md`.

- [ ] **Step 1: Replace the directory structure section**

In `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md`, locate the section starting with `## 十、目录结构` and replace the entire tree block with:

```markdown
## 十、目录结构

当前源码目录已建立骨架，各模块 `README.md` 说明职责，具体实现按开发阶段填充。

```text
ChallengeCup/
├── engine/                 # 仿真引擎
│   ├── README.md
│   ├── runner.py           # SUMO 生命周期管理（待实现）
│   ├── traci_bridge.py     # TraCI 批量读写（待实现）
│   └── collector.py        # 数据采集 → CSV（待实现）
├── scenes/                 # 场景管理（功能一）
│   ├── README.md
│   ├── registry.py         # 20 路口元数据索引（待实现）
│   ├── variant.py          # 场景变体生成（待实现）
│   ├── validator.py        # 场景校验（待实现）
│   └── data/               # 20 个路口 SUMO 工程（待填充）
├── algorithms/             # 算法库（功能二 + 功能三）
│   ├── README.md
│   ├── base.py             # 标准算法接口（待实现）
│   ├── fixed_time.py       # 固定配时基线（待实现）
│   ├── rule_adaptive.py    # 规则自适应算法（待实现）
│   └── ca_max_pressure.py      # ML 增强算法（待实现）
├── ml/                     # ML 模型模块（赛道 B 核心）
│   ├── README.md
│   ├── train.py            # XGBoost 训练脚本（待实现）
│   ├── features.py         # 特征工程（待实现）
│   ├── evaluate.py         # 模型评估（待实现）
│   └── model.pkl           # 训练产出（待生成）
├── api/                    # REST API（功能一要求）
│   ├── README.md
│   ├── server.py           # FastAPI 应用（待实现）
│   └── routes/             # 路由（待实现）
├── experiments/            # 实验分析框架
│   ├── README.md
│   ├── runner.py           # 多场景多算法交叉跑批（待实现）
│   ├── metrics.py          # 指标采集（待实现）
│   └── analyzer.py         # 统计检验 + 报告（待实现）
├── visualization/          # 可视化
│   ├── README.md
│   ├── plots.py            # Matplotlib 图表（待实现）
│   └── report.py           # 报告生成（待实现）
├── config/
│   ├── README.md
│   └── default.yaml        # 全局配置（待创建）
├── docker/
│   ├── README.md
│   ├── Dockerfile          # 待创建
│   └── docker-compose.yml  # 待创建
├── output/                 # 提交材料与运行产物
│   └── README.md
├── docs/
│   ├── api-spec.md         # 接口文档（功能一产出，待创建）
│   ├── experiment-report.md # 实验报告（待创建）
│   ├── superpowers/
│   │   ├── plans/          # 实施计划
│   │   ├── specs/          # 设计文档与图片
│   │   │   └── images/
│   │   └── ...
│   └── team/               # 团队分工与个人任务书
│       ├── README.md
│       └── 成员1-仿真引擎/任务书.md
│       └── ...
├── requirements.txt        # Python 依赖
├── .gitignore
└── README.md
```
```

- [ ] **Step 2: Verify section updated**

Run:

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
grep -n "engine/README.md" docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md
```

Expected: at least one line number printed.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
git add docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md
git commit -m "docs: align design doc directory tree with actual skeleton"
```

---

## Task 5: Verify Team README Links

**Files:**
- Read: `docs/tasks/README.md`

**Interfaces:**
- Consumes: actual files in `docs/tasks/人X-*/任务书.md`.
- Produces: confirmation that all internal links resolve.

- [ ] **Step 1: Check each link target exists**

Run:

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
python -c "
import re, os
with open('docs/tasks/README.md', 'r', encoding='utf-8') as f:
    text = f.read()
links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text)
broken = []
for label, path in links:
    if path.startswith('http') or path.startswith('#'):
        continue
    full = os.path.join('docs/team', path)
    if not os.path.exists(full):
        broken.append(path)
if broken:
    print('Broken links:', broken)
    exit(1)
print('All team README links OK')
"
```

Expected: `All team README links OK`

- [ ] **Step 2: Commit if any fixes were needed**

If no changes were made, skip this step. If links were fixed:

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
git add docs/tasks/README.md
git commit -m "docs: fix team README internal links"
```

---

## Task 6: Final Verification

**Files:**
- Read: `README.md`
- Read: all newly created `README.md` files

- [ ] **Step 1: Verify all plan deliverables exist**

Run:

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
python -c "
import os
required = [
    'README.md',
    'requirements.txt',
    'engine/README.md', 'scenes/README.md', 'algorithms/README.md',
    'ml/README.md', 'api/README.md', 'experiments/README.md',
    'visualization/README.md', 'config/README.md', 'docker/README.md',
    'output/README.md',
    'docs/superpowers/specs/2026-07-14-readme-redesign-design.md',
]
missing = [p for p in required if not os.path.exists(p)]
if missing:
    print('Missing:', missing)
    exit(1)
print('All deliverables present')
"
```

Expected: `All deliverables present`

- [ ] **Step 2: Verify no local README links are broken**

Run:

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
python -c "
import re, os
with open('README.md', 'r', encoding='utf-8') as f:
    text = f.read()
links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text)
broken = []
for label, path in links:
    if path.startswith('http') or path.startswith('#'):
        continue
    path_no_frag = path.split('#')[0]
    if path_no_frag and not os.path.exists(path_no_frag):
        broken.append(path)
if broken:
    print('Broken links:', broken)
    exit(1)
print('All README local links OK')
"
```

Expected: `All README local links OK`

- [ ] **Step 3: Run git status to confirm clean working tree**

Run:

```bash
cd /c/Users/peng/Desktop/project/ChallengeCup
git status --short
```

Expected: empty output (all changes committed).

---

## Self-Review

### Spec Coverage

| Spec Section | Implementing Task |
|--------------|-------------------|
| README badges + TOC | Task 3 |
| 项目概览（竞赛信息 / 背景 / 三大功能） | Task 3 |
| 核心创新点 | Task 3 |
| 系统架构图引用 | Task 3 |
| 核心策略表格 | Task 3 |
| 实验设计表格 | Task 3 |
| 环境安装（SUMO + Python） | Task 2 + Task 3 |
| 快速开始 | Task 3 |
| 项目结构 | Task 1 + Task 3 + Task 4 |
| 文档导航 | Task 3 |
| 开发阶段与里程碑 | Task 3 |
| 团队分工 | Task 3 + Task 5 |
| 评分对标 | Task 3 |
| 提交材料清单 | Task 3 |
| 修正设计文档目录结构 | Task 4 |

### Placeholder Scan

- No "TBD" or "TODO" in actual deliverables.
- The phrase "待实现" / "待创建" is used intentionally in module `README.md` files and the design doc to indicate skeleton status.

### Type Consistency

- Directory paths in `README.md`, design doc, and team doc are consistent.
- File names referenced in quick-start (`engine/runner.py`, `api/server:app`) match the planned module structure.
