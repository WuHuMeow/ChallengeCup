# README  redesign — 设计文档

> **项目**：雄安新区"城市大脑"车路云一体化 — 智能交通管控算法优化  
> **编号**：XH-202613  
> **日期**：2026-07-14  
> **目标**：基于竞赛 PDF 与现有设计文档，重写仓库 `README.md`，并修正相关 Markdown 中的项目结构描述。

---

## 一、背景与目标

### 1.1 背景

当前仓库 `README.md` 仅 43 行，包含标题、架构图、依赖图、快速导航、核心策略和团队简介。内容虽然方向正确，但：

- 缺少可点击的目录导航；
- 缺少详细的环境安装指南；
- 缺少快速开始（Quick Start）命令；
- 对竞赛评委关心的「赛道 B 要求 / 创新点 / 评分对标」展示不足；
- 对开发者关心的「目录结构 / 接口 / 开发流程」说明不足。

同时，仓库当前实际仅包含 `README.md`、`.gitignore` 与 `docs/` 下的设计、计划和团队分工文档，源码目录（`engine/`、`algorithms/`、`ml/` 等）尚未创建。因此：

- 需要以「规划中」或「待搭建」方式在 README 中呈现项目结构；
- 或者一次性创建源码目录骨架（推荐），使 README 和现有设计文档中的目录描述与实际一致。

仓库中已有 `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md` 等文档的目录结构描述与当前实际目录存在不一致，需要一并修正。

### 1.2 目标

1. 重写 `README.md`，使其成为「**竞赛评审 + 团队开发**」双入口。
2. 增加目录导航、环境安装、快速开始、项目结构、文档导航、里程碑、评分对标、提交材料清单等章节。
3. 参考优秀开源仓库的 README 规范（如 badges、TOC、Quick Start、Contributing 等），但不照搬，需结合本项目实际。
4. 修正 `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md` 等文件中与实际目录不一致的项目结构描述。

---

## 二、参考规范

参考以下 README 组织习惯：

- **清晰的项目身份区**：标题 + 一句话描述 + badges（竞赛编号、Python 版本、SUMO 版本）。
- **可点击目录导航（TOC）**：便于长文快速跳转。
- **Quick Start**：最小可运行示例，三步跑起来。
- **环境安装**：分 OS、分依赖，给出可复制命令。
- **项目结构**：树状目录 + 模块说明。
- **文档导航**：核心文档链接表。
- **Roadmap / Milestone**：开发阶段与关键节点。
- **Team / Contributing**：团队分工与协作约定。

本项目不做国际化（I18n），保持中文主体，技术术语保留英文。

---

## 三、当前 README 评估

| 维度 | 现状 | 问题 |
|------|------|------|
| 导航 | 仅有"快速导航"表格 | 无 TOC，章节无法快速跳转 |
| 环境安装 | 缺失 | 新成员无法快速搭建 |
| 快速开始 | 缺失 | 无法验证项目可运行 |
| 项目结构 | 缺失 | 不清楚代码组织 |
| 创新点 / 评分对标 | 仅一句话 | 评委难以抓住得分点 |
| 团队分工 | 仅一句话 | 需要链接到详细分工 |
| 视觉 | 有 SVG 架构图 | 良好，需保留并扩展 |

---

## 四、新 README 结构设计

采用「**入口页 + 详细文档分流**」方案。

### 4.1 一级目录

```markdown
1.  项目标题区（Title + Badges + 一句话描述）
2.  目录（Table of Contents，中文锚点）
3.  项目概览
    3.1 竞赛信息
    3.2 项目背景
    3.3 三大功能模块
4.  核心创新点
5.  系统架构
6.  核心策略：基线 → 自适应 → ML 增强
7.  实验设计
8.  环境安装
    8.1 系统要求
    8.2 安装 SUMO
    8.3 安装 Python 依赖
    8.4 验证安装
9.  快速开始
    9.1 克隆仓库
    9.2 运行单个路口仿真
    9.3 启动 FastAPI 服务（可选）
10. 项目结构
11. 文档与接口导航
12. 开发阶段与里程碑
13. 团队分工
14. 评分对标
15. 提交材料清单
16. 更新日志 / 许可
```

### 4.2 内容要点

#### 标题区

- 标题：🏙️ 雄安新区"城市大脑"车路云一体化 — 智能交通管控算法优化
- 副标题：挑战杯 2026 · XH-202613 · 赛道 B（算法优化型 + ML 增强）
- Badges：竞赛编号、Python 3.x、SUMO 1.18、XGBoost、FastAPI、License（如适用）

#### 目录

使用 Markdown 锚点，例如：

```markdown
- [项目概览](#项目概览)
  - [竞赛信息](#竞赛信息)
  ...
```

#### 项目概览

- 竞赛信息：挑战杯 2026、编号、赛道、截止日期。
- 项目背景：雄安新区"未来之城"、"车-路-云"一体化、20 个真实路口。
- 三大功能模块：功能一（仿真场景与数据接口）、功能二（算法实现与可视化）、功能三（ML 增强深度优化）。

#### 核心创新点

1. AI 与传统控制融合：XGBoost 预测 + 规则决策，保留可解释性。
2. 预测驱动的主动控制：提前预判流量，预调配时。
3. 标准化对比实验：20 路口 × 3 流量 × 3 算法 = 180 次仿真，统计显著性支撑结论。

#### 系统架构

保留现有 SVG 图：`./docs/superpowers/specs/images/architecture.svg`  
并补充一句话说明：SUMO 仿真引擎 → TraCI 数据采集 → CSV → XGBoost 训练 → model.pkl → 算法推理 → 指标输出。

#### 核心策略

使用代码块或表格展示三种算法递进关系：

```
固定配时基线 → 规则自适应 → ML 增强算法（XGBoost）
   (对照组)       (中间对比)       (主打)
```

#### 实验设计

| 维度 | 方案 |
|------|------|
| 场景 | 20 路口 × 3 流量等级 = 60 变体 |
| 算法 | 固定配时 / 规则自适应 / ML 增强 = 3 种 |
| 指标 | 平均排队长度、平均延误、总通行量、停车次数 |
| 总次数 | 180 次仿真 |
| 统计方法 | 配对 t 检验 |

#### 环境安装

分 Windows / Linux / macOS（以 Windows 为主，因为队员环境多为 Windows）：

1. 安装 SUMO 1.18+，设置 `SUMO_HOME` 环境变量。
2. 安装 Python 3.10+。
3. 创建虚拟环境并安装依赖：
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. 验证：`sumo --version`、`python -c "import traci; print(traci.__version__)"`。

> 说明：当前仓库尚未创建 `requirements.txt`，本设计建议新增该文件（属于项目结构修改的一部分）。

#### 快速开始

提供最小可运行示例：

```bash
git clone https://gitee.com/fyx0927/challenge-cup.git
cd challenge-cup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python engine/runner.py --scene scenes/data/intersection_01 --algorithm fixed_time
```

> 说明：具体命令需根据实际代码文件名和参数调整；若当前代码尚未实现，可先用占位说明并标注 TODO。

#### 项目结构

以实际目录为准，示例：

```text
ChallengeCup/
├── engine/                 # 仿真引擎（SUMO + TraCI）
├── scenes/                 # 场景管理（20 路口数据）
├── algorithms/             # 算法库
├── ml/                     # XGBoost 训练与推理
├── api/                    # FastAPI 服务
├── experiments/            # 跑批与统计分析
├── visualization/          # 可视化图表
├── config/                 # 全局配置
├── docker/                 # Docker 镜像
├── docs/                   # 文档
│   ├── api-spec.md
│   ├── superpowers/specs/  # 设计文档
│   └── team/               # 团队分工
├── output/                 # 提交材料
├── requirements.txt        # Python 依赖
├── Dockerfile
├── docker-compose.yml
├── .gitignore
└── README.md
```

#### 文档与接口导航

| 文档 | 说明 | 路径 |
|------|------|------|
| 完整设计文档 | 架构、模块、分工、里程碑 | `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md` |
| 团队分工 | 8 人详细任务 | `docs/tasks/README.md` |
| API 接口文档 | 功能一产出 | `docs/api-spec.md`（待创建） |
| 实验报告 | 180 次仿真分析 | `docs/experiment-report.md`（待创建） |

#### 开发阶段与里程碑

引用设计文档中的 M1–M5，用表格展示。

#### 团队分工

用表格展示 4 组 8 人，链接到 `docs/tasks/README.md` 和个人任务书。

#### 评分对标

| 评分维度 | 满分 | 本项目对应 |
|----------|------|-----------|
| 创新性 | 25 | XGBoost + 规则融合、预测驱动主动控制 |
| 系统实现与功能完成度 | 30 | 三种算法、60 场景、标准化 API |
| 实验验证与分析 | 20 | 180 次仿真、统计检验、与传统信号控制对比 |
| 工程化与标准价值 | 10 | 标准算法接口、Postman 文档、Docker |
| 团队答辩与表达 | 15 | 双层管理、PPT + 视频、模拟答辩 |

#### 提交材料清单

列出挑战杯要求提交的材料及对应路径/状态。

---

## 五、项目结构修改计划

### 5.1 新增文件

| 文件/目录 | 说明 |
|------|------|
| `requirements.txt` | Python 依赖清单，便于环境安装。建议初始包含：traci, sumolib, pandas, numpy, xgboost, scikit-learn, scipy, matplotlib, seaborn, fastapi, uvicorn, pyyaml。 |
| `engine/README.md` | 仿真引擎模块说明。 |
| `scenes/README.md` | 场景管理模块说明。 |
| `algorithms/README.md` | 算法库模块说明。 |
| `ml/README.md` | ML 模型模块说明。 |
| `api/README.md` | REST API 模块说明。 |
| `experiments/README.md` | 实验跑批模块说明。 |
| `visualization/README.md` | 可视化模块说明。 |
| `config/README.md` | 全局配置模块说明。 |
| `docker/README.md` | Docker 镜像说明。 |
| `output/README.md` | 提交材料输出目录说明。 |

> 说明：上述源码目录目前尚未创建。本次实施将一次性建立目录骨架，每个目录下放置 `README.md` 说明模块职责，暂不加具体实现代码。这样 README 和已有设计文档中的目录结构描述将与实际一致。

### 5.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `README.md` | 按本设计完全重写。 |
| `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md` | 修正「目录结构」章节，使其与实际目录一致；说明源码目录已创建为骨架，具体实现按开发阶段填充。 |
| `docs/tasks/README.md` | 检查并修正目录链接，确保个人任务书路径正确。 |

### 5.3 不修改的文件

- `.gitignore`：内容合理，保持不变。
- `docs/superpowers/plans/*.md`：继续保留，本设计不涉及修改。
- `docs/superpowers/specs/images/*.svg`：继续引用，不改动。

---

## 六、验收标准

1. `README.md` 包含目录导航、环境安装、快速开始、项目结构、文档导航、里程碑、团队分工、评分对标、提交材料清单。
2. `README.md` 所有内部链接有效（相对路径正确）。
3. `requirements.txt` 已创建且依赖合理。
4. `engine/`、`scenes/`、`algorithms/`、`ml/`、`api/`、`experiments/`、`visualization/`、`config/`、`docker/`、`output/` 目录骨架已创建，每个目录包含说明 `README.md`。
5. `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md` 中的目录结构描述与实际一致。
6. `docs/tasks/README.md` 中的链接路径与实际文件一致。
7. 无 TBD/TODO 占位符（除非明确标注为后续工作）。

---

## 七、自检清单

- [x] 目标明确：重写 README + 修正相关 Markdown 结构描述。
- [x] 结构清晰：双入口（评委 + 开发者）、TOC、环境、Quick Start 俱全。
- [x] 结合实际：保留现有 SVG 图、引用现有设计文档、新增 `requirements.txt`、创建源码目录骨架。
- [x] 可验收：列出 7 条具体验收标准。
- [x] 无歧义：所有新增/修改文件路径明确。
