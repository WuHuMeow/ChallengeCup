# 仓库工程化建设 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前项目目录初始化为一个完整的、符合设计规范 V1.0 的 GitHub 工程仓库。

**Architecture:** 在现有 `intersection_data/` 和 `docs/` 基础上，新建工程目录结构、配置文件、README 体系、文档模板和新人指南，然后初始化 Git 仓库并创建协作分支。

**Tech Stack:** Git, GitHub, Markdown, YAML, CSV, Python (requirements only)

## Global Constraints

- 不修改 `intersection_data/1~20/` 中的任何原始文件
- 不编写算法代码、不运行仿真、不做实验
- 文档语言：目录/文件名英文，正文中文，commit 英文前缀+中文描述
- 仓库为 Public，README 需专业可读
- 所有新建目录必须包含 README.md
- `results/` 和 `workspace/` 整体 gitignore，但保留其中的 README.md

---

## File Structure

### 新建文件清单

| 路径 | 职责 |
|------|------|
| `.gitignore` | 排除规则 |
| `.gitattributes` | 换行符与二进制标记 |
| `.python-version` | Python 版本锁定 |
| `requirements.txt` | pip 依赖 |
| `environment.yml` | conda 依赖 |
| `LICENSE` | MIT 许可证 |
| `README.md` | 项目导航入口 |
| `PROJECT_STRUCTURE.md` | 仓库工程说明书 |
| `CONTRIBUTING.md` | 贡献指南 |
| `intersection_data/README.md` | 数据集说明 |
| `intersection_data/metadata/intersections.csv` | 路口元数据表 |
| `intersection_data/metadata/intersections.yaml` | 路口元数据（结构化） |
| `src/README.md` | 源代码目录说明 |
| `scripts/README.md` | 脚本目录说明 |
| `configs/README.md` | 配置目录说明 |
| `docs/README.md` | 知识中心首页 |
| `docs/guides/first-day.md` | 新人第一天指南 |
| `docs/guides/git-for-beginners.md` | Git 入门指南 |
| `docs/guides/environment-setup.md` | 环境配置指南 |
| `docs/tasks/current-tasks.md` | 当前任务池 |
| `docs/tasks/learning-roadmap.md` | 学习路线 |
| `docs/tasks/completed-tasks.md` | 已完成任务 |
| `docs/research/README.md` | 调研目录说明 |
| `docs/intersections/README.md` | 路口档案目录说明 |
| `docs/experiments/README.md` | 实验目录说明 |
| `docs/meetings/README.md` | 会议记录目录说明 |
| `docs/decisions/README.md` | ADR 目录说明 |
| `docs/standards/README.md` | 规范目录说明 |
| `docs/faq/README.md` | FAQ 目录说明 |
| `docs/glossary/README.md` | 术语表目录说明 |
| `results/README.md` | 实验输出说明 |
| `submission/README.md` | 提交物说明 |
| `references/README.md` | 参考资料说明 |
| `templates/README.md` | 模板目录说明 |
| `templates/intersection-card.md` | 路口资料卡模板 |
| `templates/meeting-notes.md` | 会议记录模板 |
| `templates/weekly-report.md` | 周报模板 |
| `templates/adr.md` | ADR 模板 |
| `templates/research-notes.md` | 调研笔记模板 |
| `templates/experiment-log.md` | 实验记录模板 |
| `templates/faq-entry.md` | FAQ 条目模板 |
| `templates/task-template.md` | 任务模板 |
| `templates/issue-template.md` | Issue 模板 |
| `templates/roadmap-template.md` | 阶段计划模板 |
| `assets/README.md` | 静态资源说明 |
| `workspace/README.md` | 临时工作区说明 |
| `.github/ISSUE_TEMPLATE/task.md` | GitHub Issue 模板 |
| `.github/ISSUE_TEMPLATE/bug.md` | GitHub Bug 模板 |

---

### Task 1: 初始化 Git 仓库 + 创建目录骨架

**Files:**
- Create: 所有空目录（通过 .gitkeep 占位）
- Create: `.gitignore`
- Create: `.gitattributes`

- [ ] **Step 1: 初始化 Git 仓库**

```bash
cd C:/Users/peng/Desktop/project
git init
git branch -M main
```

- [ ] **Step 2: 创建 .gitignore**

```gitignore
# === 实验输出（按路径排除） ===
results/*
!results/README.md

# === 团队临时工作区 ===
workspace/*
!workspace/README.md

# === Python ===
__pycache__/
*.py[cod]
*$py.class
*.so
.venv/
venv/
env/
*.egg-info/
dist/
build/

# === SUMO 后续运行输出（仅排除 results/ 中的，不排除 intersection_data/ 中已有的） ===
# intersection_data/ 中的 stats.xml/traj.xml 是原始数据的一部分，保留入库

# === IDE ===
.idea/
.vscode/
*.swp
*.swo

# === OS ===
.DS_Store
Thumbs.db

# === 日志 ===
*.log

# === 大文件（防止意外提交） ===
*.mp4
*.avi
*.mov
```

- [ ] **Step 3: 创建 .gitattributes**

```gitattributes
# 统一换行符
* text=auto eol=lf

# 二进制文件
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.xlsx binary
*.xls binary
*.pdf binary
*.mp4 binary
*.zip binary

# XML 文件强制 LF
*.xml text eol=lf
*.sumocfg text eol=lf
```

- [ ] **Step 4: 创建目录骨架**

```bash
cd C:/Users/peng/Desktop/project

# src 及子目录
mkdir -p src/algorithms src/simulation src/analysis src/interfaces src/common

# scripts / configs
mkdir -p scripts configs

# docs 子目录
mkdir -p docs/guides docs/tasks docs/research docs/intersections
mkdir -p docs/experiments docs/meetings docs/decisions docs/standards
mkdir -p docs/faq docs/glossary

# results / submission / references / templates / assets
mkdir -p results
mkdir -p submission/report submission/presentation submission/video
mkdir -p references/papers references/standards references/policy references/manuals
mkdir -p templates
mkdir -p assets

# workspace
mkdir -p workspace/a-team workspace/b-team workspace/c-team workspace/d-team

# intersection_data/metadata
mkdir -p intersection_data/metadata

# .github
mkdir -p .github/ISSUE_TEMPLATE .github/workflows
```

- [ ] **Step 5: 在空目录中放置 .gitkeep**

```bash
cd C:/Users/peng/Desktop/project

# 需要 .gitkeep 的空目录（没有 README 或其他文件的）
for dir in \
  src/algorithms src/simulation src/analysis src/interfaces src/common \
  workspace/a-team workspace/b-team workspace/c-team workspace/d-team \
  submission/report submission/presentation submission/video \
  references/papers references/standards references/policy references/manuals \
  .github/workflows; do
  touch "$dir/.gitkeep"
done
```

- [ ] **Step 6: 验证目录结构**

```bash
find . -type d -not -path './.git*' -not -path './intersection_data/[0-9]*' | sort
```

Expected: 所有设计文档中列出的目录均存在。

- [ ] **Step 7: Commit**

```bash
git add .gitignore .gitattributes
git add src/ scripts/ configs/ results/ submission/ references/ templates/ assets/ workspace/ .github/
git add intersection_data/metadata/
git commit -m "chore: 初始化仓库目录骨架与 Git 配置"
```

---

### Task 2: 环境文件 + LICENSE

**Files:**
- Create: `requirements.txt`
- Create: `environment.yml`
- Create: `.python-version`
- Create: `LICENSE`

- [ ] **Step 1: 创建 requirements.txt**

```text
# SUMO 交通仿真接口
traci
sumolib

# 数据处理
pandas
numpy
openpyxl

# 可视化
matplotlib

# 配置管理
pyyaml
```

- [ ] **Step 2: 创建 environment.yml**

```yaml
name: xiong-an-traffic
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - pip
  - numpy
  - pandas
  - matplotlib
  - openpyxl
  - pyyaml
  - pip:
    - traci
    - sumolib
```

- [ ] **Step 3: 创建 .python-version**

```text
3.11
```

- [ ] **Step 4: 创建 LICENSE (MIT)**

```text
MIT License

Copyright (c) 2026 XH-202613 Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt environment.yml .python-version LICENSE
git commit -m "chore: 添加环境配置文件与 MIT 许可证"
```

---

### Task 3: 根 README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建根 README.md**

```markdown
# 雄安新区车路云协同管控算法与仿真平台

> XH-202613 · 路线 B：经典交通管控算法的场景适配与优化

## 项目状态

| 项目 | 状态 |
|------|------|
| 当前阶段 | 学习与知识库建设 |
| 技术路线 | 路线 B（算法调优型） |
| 版本 | v0.1 |
| 最近更新 | 2026-07-20 |

## 项目简介

面向雄安新区"城市大脑"车路云一体化场景，将经典交通信号控制算法应用于"窄路密网"路网，通过 SUMO 仿真平台进行参数调优与性能评估，并与传统固定配时方案进行对比验证。

## 快速导航

| 入口 | 说明 |
|------|------|
| [新人第一天指南](docs/guides/first-day.md) | 15 分钟完成环境搭建 |
| [仓库结构说明](PROJECT_STRUCTURE.md) | 每个目录的职责与权限 |
| [贡献指南](CONTRIBUTING.md) | Git 工作流与提交规范 |
| [知识中心](docs/README.md) | 所有文档、笔记、规范的入口 |
| [团队分工](docs/团队分工方案.md) | 4 组 × 2 人职责划分 |
| [当前任务](docs/tasks/current-tasks.md) | 本周各组的任务 |

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/<org>/xiong-an-traffic.git
cd xiong-an-traffic

# 2. 配置 Python 环境（二选一）
pip install -r requirements.txt        # pip 用户
conda env create -f environment.yml    # conda 用户

# 3. 验证 SUMO 安装
sumo --version
```

## 目录导航

| 目录 | 用途 | 负责人 |
|------|------|--------|
| `intersection_data/` | 主办方原始数据集（只读） | A 组 |
| `src/` | 源代码（算法、仿真、分析） | B 组为主 |
| `docs/` | 知识中心（文档、笔记、规范） | 全员 |
| `scripts/` | 运维/一次性脚本 | A 组 |
| `configs/` | 配置文件 | B 组 |
| `results/` | 实验输出（gitignore） | C 组 |
| `submission/` | 最终提交物 | D 组 |
| `references/` | 外部参考资料 | 全员 |
| `templates/` | 文档模板 | D 组 |
| `assets/` | 静态资源 | 全员 |
| `workspace/` | 临时工作区（gitignore） | 各组 |

## 团队

| 小组 | 定位 | Owner |
|------|------|-------|
| A 数据与仿真组 | 基础设施层 | TBD |
| B 算法研究组 | 核心智力层 | TBD |
| C 实验评估组 | 验证度量层 | TBD |
| D 项目管理与文档组 | 组织协调层 | TBD |

## 比赛信息

- 赛题编号：XH-202613
- 截止日期：2026-09-01（提交缓冲：09-15）
- 提交方式：发送至 497923691@qq.com

## License

[MIT](LICENSE)
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: 创建根 README 项目导航"
```

---

### Task 4: PROJECT_STRUCTURE.md + CONTRIBUTING.md

**Files:**
- Create: `PROJECT_STRUCTURE.md`
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: 创建 PROJECT_STRUCTURE.md**

```markdown
# 仓库工程说明书

> 本文面向团队成员，说明仓库每个目录的职责、权限和使用规则。

## 目录职责与权限

| 目录 | 职责 | 权限 | 负责人 |
|------|------|------|--------|
| `intersection_data/1~20/` | 主办方原始数据 | 只读 | A 组 |
| `intersection_data/metadata/` | 路口元数据（派生） | 可写 | A 组 |
| `src/algorithms/` | 信号控制算法实现 | 可写 | B 组 |
| `src/simulation/` | SUMO 仿真驱动 | 可写 | A/B 组 |
| `src/analysis/` | 数据分析与可视化 | 可写 | C 组 |
| `src/interfaces/` | 算法/TraCI 接口封装 | 可写 | B 组 |
| `src/common/` | 公共工具 | 可写 | 全员 |
| `scripts/` | 一次性/运维脚本 | 可写 | A 组 |
| `configs/` | 仿真/实验参数配置 | 可写 | B/C 组 |
| `docs/guides/` | 新人指南、操作指南 | 可写 | D 组为主 |
| `docs/tasks/` | 任务管理 | 可写 | D 组 |
| `docs/research/` | 算法调研笔记 | 可写 | B 组 |
| `docs/intersections/` | 20 路口档案 | 可写 | A 组 |
| `docs/experiments/` | 实验设计与指标 | 可写 | C 组 |
| `docs/meetings/` | 周会记录 | 可写 | D 组 |
| `docs/decisions/` | ADR 决策记录 | 可写 | 全员 |
| `docs/standards/` | 规范文档 | 可写 | D 组 |
| `docs/faq/` | 常见问题 | 可写 | 全员 |
| `docs/glossary/` | 术语表 | 可写 | 全员 |
| `results/` | 实验输出（gitignore） | 自由 | 全员 |
| `submission/` | 最终提交物 | 可写 | D 组为主 |
| `references/` | 外部参考资料 | 可写 | 全员 |
| `templates/` | 文档模板 | 可写 | D 组 |
| `assets/` | 静态资源 | 可写 | 全员 |
| `workspace/` | 临时工作区（gitignore） | 自由 | 各组 |

## 新增文件规范

1. 新增一级目录必须同时创建 `README.md`
2. 新增二级目录如果承担长期维护职责，也应创建 `README.md`
3. 文件命名规则见 [CONTRIBUTING.md](CONTRIBUTING.md#文件命名)
4. 不确定放哪里时，先放 `workspace/` 自己的组目录，周会时讨论归档位置

## 只读规则

`intersection_data/1~20/` 中的文件原则上不修改。如果确实发现数据错误：
1. 在 `docs/faq/` 中记录问题
2. 周会提出讨论
3. 团队确认后由 A 组 Owner 统一修正
4. commit message 注明 `fix(A): 修正路口N数据错误（经团队确认）`
```

- [ ] **Step 2: 创建 CONTRIBUTING.md**

```markdown
# 贡献指南

> 本文说明 Git 工作流、提交规范和协作流程。

## Git 工作流（三阶段渐进）

### Phase 1：当前 ~ 第 2 周

- `main` 为保护分支，普通成员不直接 push
- 各组使用固定分支：`docs/a-team`、`docs/b-team`、`docs/c-team`、`docs/d-team`
- 组员在组分支上 commit + push
- 各组 Owner 每 2-3 天 merge 到 main

日常操作：
```bash
git switch docs/a-team       # 切到组分支
git pull origin docs/a-team  # 拉取最新
# ... 编辑文件 ...
git add <文件>
git commit -m "docs(A): 完成路口1数据档案"
git push origin docs/a-team
```

Owner 合并：
```bash
git switch main
git pull origin main
git merge docs/a-team
git push origin main
```

### Phase 2：第 3 周起

- 引入 `develop` 分支，`docs/*` 分支归档
- 功能分支命名：`feature/<描述>`、`simulation/<描述>`、`fix/<描述>`
- 从 develop 创建，完成后 merge 回 develop
- main 只在里程碑节点从 develop 合并

### Phase 3：第 5 周起

- 功能分支通过 Pull Request 合并到 develop
- 至少 1 人 Review（看三点：能运行、不影响别人、命名规范）
- Squash merge

## Commit 规范

格式：`<type>(<scope>): <中文描述>`

| type | 场景 | 示例 |
|------|------|------|
| `docs` | 文档 | `docs(A): 完成路口1数据档案` |
| `feat` | 新功能 | `feat(B): 新增Webster算法框架` |
| `fix` | 修复 | `fix(A): 修复SUMO配置文件` |
| `chore` | 配置/维护 | `chore: 更新.gitignore` |

scope：`A` / `B` / `C` / `D` / `all`，或模块名。

规则：
- 一次 commit 只做一件事
- 不写 "update"、"修改" 等无信息量描述

## 文件命名

| 类型 | 规则 | 示例 |
|------|------|------|
| 目录名 | 英文小写 kebab-case | `docs/guides/` |
| 代码/脚本 | 英文小写 snake_case | `batch_simulation.py` |
| 对外文档 | 英文小写 kebab-case | `intersection-01.md` |
| 内部文档 | 允许中文 | `A组任务书.md` |
| 图片 | 英文小写 kebab-case | `intersection-01-map.png` |

禁止：文件名中使用空格、大写字母（英文部分）。

## Issue 规范

Labels：
- 组别：`group/A` `group/B` `group/C` `group/D`
- 类型：`task` `bug` `question`
- 优先级：`high` `normal` `low`

Issue 模板：
```markdown
## 描述
（一句话说清楚要做什么）

## 所属小组
（A/B/C/D）

## 验收标准
- [ ] 标准1
- [ ] 标准2
```

## 提交文档前 Checklist

- [ ] 文件放在正确目录
- [ ] 文件命名符合规范
- [ ] README 已同步更新（如有需要）
- [ ] 图片能够正常显示
- [ ] 仓库内链接可以正常跳转
- [ ] Markdown 预览正常
```

- [ ] **Step 3: Commit**

```bash
git add PROJECT_STRUCTURE.md CONTRIBUTING.md
git commit -m "docs: 创建仓库工程说明书与贡献指南"
```

---

### Task 5: intersection_data/README.md + metadata

**Files:**
- Create: `intersection_data/README.md`
- Create: `intersection_data/metadata/intersections.csv`
- Create: `intersection_data/metadata/intersections.yaml`

- [ ] **Step 1: 创建 intersection_data/README.md**

```markdown
# 数据集说明

> 本目录包含主办方提供的 20 个路口仿真数据，为项目基础资源。

## 使用规则

- `1/` ~ `20/`：**只读**，不修改原始文件
- `metadata/`：团队维护的派生元数据，可更新
- 如需修改/清洗数据，在 `results/` 或 `src/` 中生成新文件
- 发现数据错误时，记录到 `docs/faq/` 并经团队确认后由 A 组统一修正

## 每个路口的文件结构

```
N/
├── sumo工程/
│   ├── algorithm.py          # 算法模板（TraCI 接口）
│   ├── demo_N.net.xml        # 路网拓扑
│   ├── demo_N.flow.xml       # 流量定义
│   ├── demo_N.turn.xml       # 转向比例
│   ├── demo_N.rou.xml        # 车辆路由
│   ├── demo_N.sumocfg        # 仿真配置
│   ├── stats.xml             # 已有 summary 输出
│   └── traj.xml              # 已有 fcd 轨迹输出
├── 路口数据/
│   └── demo_N流量和交叉口配时方案.xlsx
└── 高精地图/                  # 路口11为"高清地图"
    └── demo_N.png
```

## 数据差异要点

| 特征 | 说明 |
|------|------|
| SUMO 版本 | 至少 5 个（1.13.0 / 1.18.0 / 1.23.1 / 1.26.0 / 1.27.1） |
| 仿真步长 | 路口 1-10、14 为 1s；路口 11-13、15-20 为 0.1s |
| 额外输出 | 路口 11-13、15-20 有 queues.xml（queue-output） |
| 流量范围 | 183~834 辆/h/方向，各路口差异极大 |
| 流数量 | 3/4/5 个不等 |
| 边命名 | 不统一（E0/-E1/-E2/-E3，部分有 -E4/-E5，方向映射各异） |

## 元数据

`metadata/intersections.csv` 和 `metadata/intersections.yaml` 提供所有路口的关键参数汇总，供批量脚本读取。
```

- [ ] **Step 2: 创建 intersection_data/metadata/intersections.csv**

```csv
id,name,edges_count,flow_count,timestep_s,sumo_version,has_queues,total_flow_per_h,notes
1,demo_1,4,4,1.0,1.18/1.26,no,1683,标准十字路口
2,demo_2,4,4,1.0,1.18/1.26,no,,
3,demo_3,4,4,1.0,1.18/1.26,no,,
4,demo_4,4,4,1.0,1.18/1.26,no,,
5,demo_5,4,3,1.0,1.18/1.26,no,,仅3个方向流
6,demo_6,4,4,1.0,1.18/1.26,no,,
7,demo_7,4,3,1.0,1.18/1.26,no,,仅3个方向流
8,demo_8,4,4,1.0,1.18/1.26,no,,
9,demo_9,5,5,1.0,1.18/1.26,no,,5进口道含-E4
10,demo_10,4,3,1.0,1.18/1.26,no,,仅3个方向流
11,demo_11,4,4,0.1,1.13,yes,,流ID为W/E/S/N_car;地图文件夹为"高清地图"
12,demo_12,4,4,0.1,1.13,yes,,流ID为W/E/S/N_car
13,demo_13,4,4,0.1,1.13,yes,,流ID为W/E/S/N_car
14,demo_14,4,4,1.0,1.18/1.23,no,,
15,demo_15,4,4,0.1,1.23,yes,,
16,demo_16,5,4,0.1,1.23,yes,,含-E5进口道
17,demo_17,4,4,0.1,1.23,yes,,
18,demo_18,4,4,0.1,1.23,yes,,高流量(834辆/h)
19,demo_19,4,4,0.1,1.23,yes,,
20,demo_20,4,4,0.1,1.23,yes,,低流量(最低183辆/h)
```

- [ ] **Step 3: 创建 intersection_data/metadata/intersections.yaml**

```yaml
# 20 路口元数据 - 供批量脚本读取
# 维护者：A 组
# 更新规则：发现新信息时更新对应字段

intersections:
  - id: 1
    timestep_s: 1.0
    sumo_versions: ["1.18.0", "1.26.0"]
    flow_count: 4
    has_queues: false
    map_folder: "高精地图"
    notes: "标准十字路口，边命名 E0/-E1/-E2/-E3"

  - id: 11
    timestep_s: 0.1
    sumo_versions: ["1.13.0"]
    flow_count: 4
    has_queues: true
    map_folder: "高清地图"
    notes: "流ID为 W_car/E_car/S_car/N_car，方向映射与路口1不同"

  - id: 16
    timestep_s: 0.1
    sumo_versions: ["1.23.1"]
    flow_count: 4
    has_queues: true
    map_folder: "高精地图"
    notes: "含 -E5 进口道（5进口道路口）"

  # 其余路口待 A 组验证后补充完整
  # 格式同上
```

- [ ] **Step 4: Commit**

```bash
git add intersection_data/README.md intersection_data/metadata/
git commit -m "docs(A): 创建数据集说明与路口元数据"
```

---

### Task 6: docs/README.md（知识中心首页）

**Files:**
- Create: `docs/README.md`

- [ ] **Step 1: 创建 docs/README.md**

```markdown
# 知识中心

> 本目录是项目的知识沉淀中心。所有学习成果、调研资料、会议记录、规范文档都在这里。

## 知识地图

```
docs/
├── guides/          → 怎么做（操作指南）
├── tasks/           → 做什么（任务管理）
├── research/        → 算法调研（B 组）
├── intersections/   → 路口档案（A 组）
├── experiments/     → 实验体系（C 组）
├── meetings/        → 周会记录（D 组）
├── decisions/       → 技术决策（ADR）
├── standards/       → 规范文档（D 组）
├── faq/             → 踩坑记录
└── glossary/        → 术语表
```

## 新人阅读顺序

1. [新人第一天指南](guides/first-day.md) — 15 分钟完成环境搭建
2. [Git 入门](guides/git-for-beginners.md) — 10 分钟学会日常操作
3. [仓库结构说明](../PROJECT_STRUCTURE.md) — 了解每个目录的职责
4. [贡献指南](../CONTRIBUTING.md) — 提交规范
5. 根据你所在小组，进入对应目录开始工作

## 各组入口

| 小组 | 主要工作目录 |
|------|------------|
| A 数据与仿真 | [intersections/](intersections/) + [guides/](guides/) |
| B 算法研究 | [research/](research/) |
| C 实验评估 | [experiments/](experiments/) |
| D 项目管理 | [standards/](standards/) + [meetings/](meetings/) + [decisions/](decisions/) |

## 最近新增

| 日期 | 文档 | 作者 |
|------|------|------|
| 2026-07-20 | 知识中心首页 | D 组 |

## 常用文档

- [20 路口总览表](intersections/README.md)
- [候选算法对比](research/README.md)
- [评价指标定义](experiments/README.md)
- [Git 规范](../CONTRIBUTING.md)
- [团队分工方案](团队分工方案.md)

## 知识沉淀原则

- 先知识库，后正式文档
- 一个主题一个文件
- 文件头部标注元信息（作者、日期、状态）
- 不删除，只标记过时
```

- [ ] **Step 2: Commit**

```bash
git add docs/README.md
git commit -m "docs(D): 创建知识中心首页"
```

---

### Task 7: 各子目录 README

**Files:**
- Create: `src/README.md`, `scripts/README.md`, `configs/README.md`
- Create: `docs/research/README.md`, `docs/intersections/README.md`, `docs/experiments/README.md`
- Create: `docs/meetings/README.md`, `docs/decisions/README.md`, `docs/standards/README.md`
- Create: `docs/faq/README.md`, `docs/glossary/README.md`
- Create: `results/README.md`, `submission/README.md`, `references/README.md`
- Create: `templates/README.md`, `assets/README.md`, `workspace/README.md`

- [ ] **Step 1: 创建 src/README.md**

```markdown
# 源代码

> 项目统一入口：`python src/main.py`

## 模块划分

| 目录 | 职责 | 负责人 |
|------|------|--------|
| `algorithms/` | 信号控制算法实现 | B 组 |
| `simulation/` | SUMO 仿真驱动、批量运行 | A/B 组 |
| `analysis/` | 数据分析与可视化 | C 组 |
| `interfaces/` | 算法接口、TraCI 封装 | B 组 |
| `common/` | 公共工具、配置读取、日志 | 全员 |

## 运行方式（开发阶段启用）

```bash
python src/main.py --mode simulation --intersection 1 --algorithm webster
```

## 当前状态

尚未进入开发阶段。目录结构已就绪，待算法方案确定后开始编码。
```

- [ ] **Step 2: 创建 scripts/README.md**

```markdown
# 脚本

> 一次性或运维用途的脚本。

## 使用规则

- 每个脚本在文件头部注释说明用途和参数
- 脚本应为幂等（重复运行不产生副作用）
- 长期使用的工具应迁移到 `src/`

## 当前状态

尚未创建脚本。
```

- [ ] **Step 3: 创建 configs/README.md**

```markdown
# 配置文件

> 仿真参数、实验参数、路径配置。

## 使用规则

- 参数不硬编码在代码中，统一放这里
- 格式：YAML 或 JSON
- 文件命名：`<用途>_params.yaml`（如 `simulation_params.yaml`）

## 当前状态

尚未创建配置文件。
```

- [ ] **Step 4: 创建 docs 子目录 README（research, intersections, experiments, meetings, decisions, standards, faq, glossary）**

`docs/research/README.md`:
```markdown
# 算法调研

> B 组主导。积累候选算法方案的调研笔记和对比分析。

## 文件组织

- 每个算法方向一个文件（如 `webster-notes.md`）
- `candidate-comparison.md`：候选方案对比表
- `traci-capabilities.md`：TraCI 接口能力清单
- `papers/`：论文阅读笔记

## 当前状态

等待 B 组开始调研后填充。
```

`docs/intersections/README.md`:
```markdown
# 路口档案

> A 组主导。每个路口一份资料卡。

## 文件组织

- `intersection-01.md` ~ `intersection-20.md`：各路口资料卡
- 使用 [路口资料卡模板](../../templates/intersection-card.md)

## 总览表

待 A 组完成验证后在此添加 20 路口关键参数汇总表。
```

`docs/experiments/README.md`:
```markdown
# 实验体系

> C 组主导。评价指标、实验设计、数据字段映射。

## 文件组织

- `metrics.md`：评价指标定义与公式
- `experiment-design.md`：实验矩阵草案
- `data-fields.md`：SUMO 输出字段 → 指标映射
- `visualization-plan.md`：可视化方案

## 当前状态

等待 C 组开始整理后填充。
```

`docs/meetings/README.md`:
```markdown
# 会议记录

> D 组主导。每次周会的记录。

## 命名规则

`YYYY-MM-DD-weekly.md`（如 `2026-07-27-weekly.md`）

## 模板

使用 [会议记录模板](../../templates/meeting-notes.md)
```

`docs/decisions/README.md`:
```markdown
# 技术决策记录（ADR）

> 记录项目中的重要技术决策及其背景和理由。

## 命名规则

`NNN-简短描述.md`（如 `001-repo-structure.md`）

## 模板

使用 [ADR 模板](../../templates/adr.md)

## 已有决策

| 编号 | 标题 | 状态 |
|------|------|------|
| 001 | 仓库目录结构设计 | 已采纳 |
| 002 | 数据管理策略 | 已采纳 |
| 003 | Git 工作流三阶段渐进 | 已采纳 |
```

`docs/standards/README.md`:
```markdown
# 规范文档

> D 组主导。项目的各类规范。

## 文件组织

- `git-conventions.md`：Git 规范
- `naming-conventions.md`：命名规范
- `markdown-style.md`：Markdown 写作规范
- `documentation-rules.md`：文档管理规则

## 当前状态

核心规范已在 [CONTRIBUTING.md](../../CONTRIBUTING.md) 中定义，后续按需细化。
```

`docs/faq/README.md`:
```markdown
# 常见问题与踩坑记录

> 全员可贡献。遇到问题先查这里，解决后记录在这里。

## 文件组织

- `sumo-pitfalls.md`：SUMO 相关踩坑
- `git-pitfalls.md`：Git 相关踩坑
- `data-issues.md`：数据问题记录

## 模板

使用 [FAQ 条目模板](../../templates/faq-entry.md)
```

`docs/glossary/README.md`:
```markdown
# 术语表

> 项目中涉及的专业术语解释。

## 文件

- `glossary.md`：统一术语表（SUMO、TraCI、信号控制等）
```

- [ ] **Step 5: 创建 results/README.md, submission/README.md, references/README.md**

`results/README.md`:
```markdown
# 实验输出

> 本目录存放仿真运行和实验产生的输出文件。**整体 gitignore，不纳入版本控制。**

## 组织方式（建议）

```
results/
├── baseline/          # 固定配时基线结果
├── algorithm/         # 算法控制结果
├── figures/           # 生成的图表
└── logs/              # 运行日志
```

## 命名规则

`<实验编号>_<路口>_<方案>_<重复次数>.xml`
如：`E01_intersection1_fixed_run1_tripinfo.xml`

## 复现方式

实验参数见 `configs/`，运行脚本见 `scripts/`。
```

`submission/README.md`:
```markdown
# 最终提交物

> D 组为主负责。存放比赛最终提交的所有材料。

## 目录结构

| 目录 | 内容 |
|------|------|
| `report/` | 系统设计与算法报告（Word） |
| `presentation/` | 答辩 PPT |
| `video/` | 演示视频（5-8 分钟） |

## 提交 Checklist

- [ ] 报告（Word）定稿
- [ ] PPT 定稿
- [ ] 视频定稿
- [ ] 代码可运行
- [ ] 部署文档完整
- [ ] 参赛申报表盖章 PDF

## 截止时间

2026-09-01 全部完成，09-15 前提交至 497923691@qq.com
```

`references/README.md`:
```markdown
# 外部参考资料

> 论文、标准、政策文件、官方手册等。

## 目录结构

| 目录 | 内容 |
|------|------|
| `papers/` | 学术论文 PDF 或阅读笔记 |
| `standards/` | 行业标准文件 |
| `policy/` | 政策文件（雄安新区规划等） |
| `manuals/` | SUMO/TraCI 官方文档摘要 |

## 添加规则

- 大文件（>10MB）考虑只放链接和阅读笔记
- 文件命名：`<作者>-<年份>-<关键词>.pdf`
```

- [ ] **Step 6: 创建 templates/README.md, assets/README.md, workspace/README.md**

`templates/README.md`:
```markdown
# 文档模板

> 所有文档模板的统一存放位置。新建文档时，复制对应模板填写。

## 模板清单

| 模板 | 用途 |
|------|------|
| `intersection-card.md` | 路口资料卡 |
| `meeting-notes.md` | 周会记录 |
| `weekly-report.md` | 周报 |
| `adr.md` | 技术决策记录 |
| `research-notes.md` | 调研笔记 |
| `experiment-log.md` | 实验记录 |
| `faq-entry.md` | FAQ 条目 |
| `task-template.md` | 任务分配 |
| `issue-template.md` | Issue 模板 |
| `roadmap-template.md` | 阶段计划 |

## 使用方式

```bash
cp templates/intersection-card.md docs/intersections/intersection-01.md
# 然后编辑填写内容
```
```

`assets/README.md`:
```markdown
# 静态资源

> 图片、图标、视频素材等。

## 规则

- 原始图片绝不修改
- 文件命名：英文小写 kebab-case（如 `intersection-01-map.png`）
- 文档引用使用相对路径
```

`workspace/README.md`:
```markdown
# 临时工作区

> 本目录整体 gitignore。用于存放临时脚本、草稿、调试文件、中间结果。

## 使用规则

- 每组使用自己的子目录：`a-team/`、`b-team/`、`c-team/`、`d-team/`
- 正式成果应迁移到对应目录（`src/`、`docs/`、`results/`）
- 不要在这里存放需要长期保留的文件
- clone 后需手动创建自己的组目录：`mkdir workspace/<你的组>`
```

- [ ] **Step 7: Commit**

```bash
git add src/README.md scripts/README.md configs/README.md
git add docs/research/README.md docs/intersections/README.md docs/experiments/README.md
git add docs/meetings/README.md docs/decisions/README.md docs/standards/README.md
git add docs/faq/README.md docs/glossary/README.md
git add results/README.md submission/README.md references/README.md
git add templates/README.md assets/README.md workspace/README.md
git commit -m "docs: 创建所有目录 README"
```

---

### Task 8: 文档模板

**Files:**
- Create: `templates/intersection-card.md` 及其他 9 个模板

- [ ] **Step 1: 创建 templates/intersection-card.md**

```markdown
---
title: 路口 N 资料卡
author: A组-姓名
created: YYYY-MM-DD
updated: YYYY-MM-DD
group: A
status: draft
---

# 路口 N

## 基本信息

- 形态：十字路口 / T形路口 / 其他
- 进口道：X 个
- 边命名：（记录实际边 ID）
- 车道数：每方向 X 车道
- 限速：XX m/s（约 XX km/h）
- 仿真步长：1s / 0.1s
- 仿真时长：3600 步 × 步长

## 流量

| 方向 | 流 ID | 流量（辆/h） |
|------|-------|-------------|
| | | |

## 转向比例

| 进口道 | 左转 | 直行 | 右转 |
|--------|------|------|------|
| | | | |

## 现状配时

- 周期：XXs
- 相位：

## SUMO 运行状态

- 结果：成功 / 失败
- SUMO 版本：
- 备注：

## 特殊说明

（与其他路口不同之处）
```

- [ ] **Step 2: 创建 templates/meeting-notes.md**

```markdown
---
title: 周会记录 YYYY-MM-DD
author: D组-姓名
created: YYYY-MM-DD
group: D
status: final
---

# 周会记录 YYYY-MM-DD

## 参会人员

（列出到场人员）

## 各组进展

### A 组
- 完成：
- 问题：
- 下周计划：

### B 组
- 完成：
- 问题：
- 下周计划：

### C 组
- 完成：
- 问题：
- 下周计划：

### D 组
- 完成：
- 问题：
- 下周计划：

## 讨论事项

1. 议题：
   结论：
   负责人：

## 待办事项

| 事项 | 负责人 | 截止日期 |
|------|--------|---------|
| | | |
```

- [ ] **Step 3: 创建 templates/weekly-report.md**

```markdown
---
title: 第 N 周周报
author: D组-姓名
created: YYYY-MM-DD
group: D
status: final
---

# 第 N 周周报（MM.DD - MM.DD）

## 本周总体进展

（一句话概括）

## 各组完成情况

| 组别 | 计划任务 | 完成状态 | 备注 |
|------|---------|---------|------|
| A | | 完成/进行中/延期 | |
| B | | | |
| C | | | |
| D | | | |

## 知识库更新

（本周新增了哪些资料）

## 风险与问题

## 下周重点
```

- [ ] **Step 4: 创建 templates/adr.md**

```markdown
---
title: ADR-NNN 决策标题
author: 姓名
created: YYYY-MM-DD
group: X
status: 已采纳
---

# ADR-NNN: 决策标题

## 状态

已采纳 / 已废弃 / 讨论中

## 背景

（为什么需要做这个决策）

## 决策

（最终选了什么方案）

## 理由

（为什么选这个，对比了哪些替代方案）

## 影响

（这个决策带来什么约束）
```

- [ ] **Step 5: 创建 templates/research-notes.md**

```markdown
---
title: 调研笔记标题
author: B组-姓名
created: YYYY-MM-DD
updated: YYYY-MM-DD
group: B
status: draft
---

# 调研笔记：标题

## 核心原理

（用自己的话解释，不超过 200 字）

## 关键公式/算法步骤

## 适用场景

## 优点

## 缺点/局限

## 与"窄路密网"的适配性

## 实现难度评估

## 创新性空间

## 参考文献

- [1] 作者, 标题, 年份, 来源
```

- [ ] **Step 6: 创建 templates/experiment-log.md**

```markdown
---
title: 实验记录标题
author: C组-姓名
created: YYYY-MM-DD
group: C
status: draft
---

# 实验记录：标题

## 实验目的

## 实验配置

- 路口：
- 流量水平：
- 控制方案：
- 算法参数：
- 重复次数：

## 结果

| 指标 | 基线 | 算法 | 提升 |
|------|------|------|------|
| | | | |

## 分析

## 结论
```

- [ ] **Step 7: 创建 templates/faq-entry.md**

```markdown
---
title: FAQ 标题
author: 姓名
created: YYYY-MM-DD
group: X
status: final
---

# 问题：简短描述

## 现象

（遇到了什么问题）

## 原因

（为什么会出现）

## 解决方法

（怎么解决的）

## 预防措施

（以后怎么避免）
```

- [ ] **Step 8: 创建 templates/task-template.md**

```markdown
---
title: 任务标题
author: D组-姓名
created: YYYY-MM-DD
group: X
status: 进行中
---

# 任务：标题

## 描述

（一句话说清楚要做什么）

## 负责人

## 截止日期

## 验收标准

- [ ] 标准 1
- [ ] 标准 2

## 相关资料

- [链接](路径)
```

- [ ] **Step 9: 创建 templates/issue-template.md**

```markdown
## 描述

（一句话说清楚要做什么）

## 所属小组

（A/B/C/D）

## 验收标准

- [ ] 标准 1
- [ ] 标准 2

## 相关资料

（链接到 docs/ 中的相关文档）
```

- [ ] **Step 10: 创建 templates/roadmap-template.md**

```markdown
---
title: 阶段计划标题
author: D组-姓名
created: YYYY-MM-DD
group: D
status: draft
---

# 阶段计划：标题

## 时间范围

YYYY-MM-DD ~ YYYY-MM-DD

## 目标

## 各组任务

| 组别 | 任务 | 交付物 | 截止日期 |
|------|------|--------|---------|
| A | | | |
| B | | | |
| C | | | |
| D | | | |

## 里程碑

## 风险
```

- [ ] **Step 11: Commit**

```bash
git add templates/
git commit -m "docs(D): 创建全套文档模板"
```

---

### Task 9: 新人指南

**Files:**
- Create: `docs/guides/first-day.md`
- Create: `docs/guides/git-for-beginners.md`
- Create: `docs/guides/environment-setup.md`

- [ ] **Step 1: 创建 docs/guides/first-day.md**

```markdown
---
title: 新人第一天指南
author: D组
created: 2026-07-20
group: D
status: final
---

# 新人第一天指南

> 预计用时：15 分钟。完成后即可正式开始参与项目。

## Step 1: Clone 仓库（2 分钟）

```bash
git clone https://github.com/<org>/xiong-an-traffic.git
cd xiong-an-traffic
```

## Step 2: 阅读 README（3 分钟）

打开根目录 `README.md`，快速了解：
- 项目做什么
- 目录结构
- 你在哪个组

## Step 3: 安装 SUMO（5 分钟）

1. 下载：https://sumo.dlr.de/docs/Downloading.php
2. 安装（Windows 建议用安装包）
3. 配置环境变量 `SUMO_HOME`：
   - Windows：系统环境变量 → 新建 `SUMO_HOME` = `C:\Program Files\Eclipse\Sumo`
4. 验证：
```bash
sumo --version
```

## Step 4: 配置 Python 环境（3 分钟）

```bash
# 方式一：pip
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# 方式二：conda
conda env create -f environment.yml
conda activate xiong-an-traffic
```

## Step 5: 切换到你的组分支（1 分钟）

```bash
git switch docs/a-team    # A 组
git switch docs/b-team    # B 组
git switch docs/c-team    # C 组
git switch docs/d-team    # D 组
```

## Step 6: 完成第一次 Commit（1 分钟）

在 `workspace/` 下创建你的组目录（如果还没有），写一个测试文件：

```bash
mkdir -p workspace/a-team    # 换成你的组
echo "hello from 你的名字" > workspace/a-team/hello.txt
# 注意：workspace/ 是 gitignore 的，所以这个文件不会被提交
# 真正的练习：在 docs/ 下你组的目录里创建一个文件
```

实际练习：
```bash
echo "# 我的第一篇文档" > docs/guides/my-first-doc.md
git add docs/guides/my-first-doc.md
git commit -m "docs(X): 完成新人第一次提交练习"
git push origin docs/x-team
```

提交后可以删除这个练习文件。

## Step 7: 阅读你的组任务书

- A 组：`docs/A组任务书_数据与仿真组.md`
- B 组：`docs/B组任务书_算法研究组.md`
- C 组：`docs/C组任务书_实验评估组.md`
- D 组：`docs/D组任务书_项目管理与文档组.md`

## 完成！

到这里你已经：
- ✅ 有了完整的本地环境
- ✅ 能运行 SUMO
- ✅ 知道自己在哪个分支工作
- ✅ 完成了第一次 commit
- ✅ 知道自己的任务是什么

有问题？查看 [FAQ](../faq/README.md) 或在群里问你的组 Owner。
```

- [ ] **Step 2: 创建 docs/guides/git-for-beginners.md**

```markdown
---
title: Git 入门指南
author: D组
created: 2026-07-20
group: D
status: final
---

# Git 入门指南

> 预计用时：10 分钟。覆盖日常协作所需的全部操作。

## 基本概念

| 概念 | 解释 |
|------|------|
| Repository（仓库） | 整个项目的文件夹 + 历史记录 |
| Commit（提交） | 一次保存，类似"存档点" |
| Branch（分支） | 平行的工作线，互不影响 |
| Merge（合并） | 把一条分支的工作合入另一条 |
| Remote（远程） | GitHub 上的仓库副本 |

## 每天的标准操作

```bash
# 1. 切到你的组分支
git switch docs/a-team

# 2. 拉取最新（防止和别人冲突）
git pull origin docs/a-team

# 3. 正常编辑文件...

# 4. 查看改了什么
git status

# 5. 添加要提交的文件
git add docs/intersections/intersection-01.md

# 6. 提交
git commit -m "docs(A): 完成路口1数据档案"

# 7. 推送到远程
git push origin docs/a-team
```

## 常见错误与解决

### push 被拒绝（rejected）

原因：别人先 push 了新内容。

```bash
git pull origin docs/a-team   # 先拉取
# 如果没有冲突，直接再 push
git push origin docs/a-team
```

### 不小心 commit 了错误的文件

```bash
# 撤销最近一次 commit（保留文件修改）
git reset --soft HEAD~1
# 重新选择文件提交
git add <正确的文件>
git commit -m "docs(A): 正确的描述"
```

### 不小心修改了不该改的文件

```bash
# 丢弃某个文件的修改（恢复到上次 commit 的状态）
git checkout -- intersection_data/1/sumo工程/demo_1.net.xml
```

### 冲突（conflict）

```bash
git pull origin docs/a-team
# 如果提示 CONFLICT：
# 1. 打开冲突文件，找到 <<<< ==== >>>> 标记
# 2. 手动选择保留哪部分
# 3. 保存后：
git add <冲突文件>
git commit -m "fix: 解决合并冲突"
```

## 注意事项

- 不要直接 push main（那是 Owner 的事）
- 不要修改 `intersection_data/1~20/` 中的文件
- commit 之前先 `git status` 确认没有多余文件
- 一次 commit 只做一件事
```

- [ ] **Step 3: 创建 docs/guides/environment-setup.md**

```markdown
---
title: 环境配置指南
author: D组
created: 2026-07-20
group: D
status: final
---

# 环境配置指南

## 必需软件

| 软件 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 算法开发、数据处理 |
| SUMO | 1.26+ | 交通仿真 |
| Git | 2.x | 版本控制 |

## SUMO 安装

### Windows

1. 下载：https://sumo.dlr.de/docs/Downloading.php
2. 运行安装包，默认路径 `C:\Program Files\Eclipse\Sumo`
3. 设置环境变量：
   - 变量名：`SUMO_HOME`
   - 变量值：`C:\Program Files\Eclipse\Sumo`
4. 验证：打开新终端，运行 `sumo --version`

### 注意

- 项目数据由多个 SUMO 版本生成（1.13~1.27），建议安装 1.26+ 以获得最好兼容性
- 如果某些路口报错，记录到 `docs/faq/sumo-pitfalls.md`

## Python 环境

### 方式一：venv + pip

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 方式二：conda

```bash
conda env create -f environment.yml
conda activate xiong-an-traffic
```

## 验证环境

```bash
python -c "import traci; import sumolib; import pandas; print('OK')"
sumo --version
git --version
```

## 常见问题

- SUMO_HOME 未设置：Python 中 `import traci` 会报错
- pip 安装 traci 失败：确保 Python 版本 >= 3.8
- conda 和 pip 混用：建议只用一种
```

- [ ] **Step 4: Commit**

```bash
git add docs/guides/
git commit -m "docs(D): 创建新人指南（first-day + git入门 + 环境配置）"
```

---

### Task 10: 任务管理文件 + .github 模板

**Files:**
- Create: `docs/tasks/current-tasks.md`, `docs/tasks/learning-roadmap.md`, `docs/tasks/completed-tasks.md`
- Create: `.github/ISSUE_TEMPLATE/task.md`, `.github/ISSUE_TEMPLATE/bug.md`

- [ ] **Step 1: 创建 docs/tasks/current-tasks.md**

```markdown
---
title: 当前阶段任务池
author: D组
created: 2026-07-20
group: D
status: final
---

# 当前阶段任务池

> 阶段：学习与知识库建设（第 1-2 周）

## A 组

- [ ] 验证 20 个路口 SUMO 工程能否正常运行
- [ ] 整理每个路口基础信息（资料卡）
- [ ] 制作 20 路口数据总览表
- [ ] 整理 SUMO 输出字段说明

## B 组

- [ ] 精读比赛 PDF 路线 B 要求
- [ ] 调研 Webster 配时优化
- [ ] 调研 SCOOT/SCATS 自适应控制
- [ ] 调研绿波协调
- [ ] 整理 TraCI 接口能力清单
- [ ] 制作候选方案对比表

## C 组

- [ ] 研读评分标准中实验评估得分点
- [ ] 整理评价指标定义与公式
- [ ] 设计实验矩阵草案
- [ ] 整理 SUMO 输出字段 → 指标映射

## D 组

- [ ] 提取比赛需求与评分要点清单
- [ ] 建立 Git 协作基础设施
- [ ] 制定会议机制
- [ ] 搭建报告/PPT/视频框架
- [ ] 维护知识库索引
```

- [ ] **Step 2: 创建 docs/tasks/learning-roadmap.md**

```markdown
---
title: 学习路线
author: D组
created: 2026-07-20
group: D
status: draft
---

# 学习路线

> 按优先级排列。完成 first-day.md 后开始。

## 全员必修

1. [Git 入门](../guides/git-for-beginners.md)（10 分钟）
2. [环境配置](../guides/environment-setup.md)（15 分钟）
3. 阅读本组任务书（20 分钟）

## A 组

1. SUMO 基础操作（安装、运行、文件体系）
2. XML 基础阅读
3. SUMO 输出文件格式

## B 组

1. 交通信号控制基础（周期、相位、绿信比）
2. 经典算法原理（Webster、SCOOT、绿波）
3. TraCI 接口文档

## C 组

1. 交通评价指标体系
2. SUMO 输出数据解读
3. 对比实验设计基础

## D 组

1. Git 协作规范（CONTRIBUTING.md）
2. Markdown 写作
3. 比赛 PDF 精读
```

- [ ] **Step 3: 创建 docs/tasks/completed-tasks.md**

```markdown
---
title: 已完成任务记录
author: D组
created: 2026-07-20
group: D
status: final
---

# 已完成任务记录

> 从 current-tasks.md 中完成的任务迁移到这里，保留历史记录。

## 2026-07-20

- [x] 团队分工方案定稿（D 组）
- [x] 4 份任务书编写完成（D 组）
- [x] 仓库工程设计规范 V1.0 定稿（全员讨论）
```

- [ ] **Step 4: 创建 .github/ISSUE_TEMPLATE/task.md**

```markdown
---
name: 任务
about: 新建一个工作任务
title: "[task] "
labels: task
assignees: ''
---

## 描述

（一句话说清楚要做什么）

## 所属小组

- [ ] A 组
- [ ] B 组
- [ ] C 组
- [ ] D 组

## 验收标准

- [ ] 标准 1
- [ ] 标准 2

## 相关资料

（链接到 docs/ 中的相关文档）
```

- [ ] **Step 5: 创建 .github/ISSUE_TEMPLATE/bug.md**

```markdown
---
name: 问题
about: 报告一个问题或缺陷
title: "[bug] "
labels: bug
assignees: ''
---

## 现象

（遇到了什么问题）

## 复现步骤

1. 
2. 
3. 

## 期望行为

## 实际行为

## 环境

- OS：
- SUMO 版本：
- Python 版本：
```

- [ ] **Step 6: Commit**

```bash
git add docs/tasks/ .github/ISSUE_TEMPLATE/
git commit -m "docs(D): 创建任务管理文件与 GitHub Issue 模板"
```

---

### Task 11: 纳入 intersection_data + 初始提交 + 分支初始化

**Files:**
- Modify: 将 `intersection_data/` 和已有 `docs/` 文件纳入版本控制

- [ ] **Step 1: 将 intersection_data/ 纳入版本控制**

```bash
cd C:/Users/peng/Desktop/project
git add intersection_data/
```

- [ ] **Step 2: 将已有 docs/ 文件纳入版本控制**

```bash
git add docs/团队分工方案.md
git add "docs/A组任务书_数据与仿真组.md"
git add "docs/B组任务书_算法研究组.md"
git add "docs/C组任务书_实验评估组.md"
git add "docs/D组任务书_项目管理与文档组.md"
```

- [ ] **Step 3: 将比赛 PDF 纳入版本控制**

```bash
git add "XH-202613_面向雄安新区"城市大脑"的车路云.pdf"
```

- [ ] **Step 4: 检查暂存区**

```bash
git status
```

Expected: 所有文件已暂存，无遗漏。确认没有 `.venv/`、`__pycache__/` 等被意外添加。

- [ ] **Step 5: 提交**

```bash
git commit -m "chore: 纳入原始数据集与已有文档，完成仓库初始化"
```

- [ ] **Step 6: 创建 4 个组分支**

```bash
git branch docs/a-team
git branch docs/b-team
git branch docs/c-team
git branch docs/d-team
```

- [ ] **Step 7: 验证分支**

```bash
git branch -a
```

Expected:
```
* main
  docs/a-team
  docs/b-team
  docs/c-team
  docs/d-team
```

- [ ] **Step 8: 打 tag**

```bash
git tag -a v0.1-structure -m "仓库工程结构初始化完成"
```

- [ ] **Step 9: 最终验证**

```bash
# 确认目录结构完整
ls -la
ls src/
ls docs/
ls templates/
ls intersection_data/metadata/

# 确认 git 状态干净
git status
git log --oneline
git tag
```

Expected: git status 显示 "nothing to commit, working tree clean"；git log 显示 7-8 个 commit；tag 列表包含 v0.1-structure。

---

### Task 12: 推送到 GitHub（手动步骤）

> 此任务需要团队成员在 GitHub 网页上操作，无法通过命令行自动完成。

- [ ] **Step 1: 在 GitHub 创建仓库**

1. 打开 https://github.com/new
2. 仓库名：`xiong-an-traffic`
3. 可见性：Public
4. 不勾选 "Add a README"（已有）
5. 点击 Create repository

- [ ] **Step 2: 推送本地仓库到 GitHub**

```bash
git remote add origin https://github.com/<org>/xiong-an-traffic.git
git push -u origin main
git push origin docs/a-team docs/b-team docs/c-team docs/d-team
git push origin v0.1-structure
```

- [ ] **Step 3: 配置分支保护**

GitHub → Settings → Branches → Add rule：
- Branch name pattern: `main`
- 勾选 "Require a pull request before merging"（Phase 3 启用，Phase 1 先不勾）
- 勾选 "Do not allow force pushes"
- 勾选 "Do not allow deletions"

Phase 1 简化配置：仅禁止 force push 和删除，允许 Owner 直接 merge。

- [ ] **Step 4: 创建 Labels**

GitHub → Issues → Labels → New label：

| Name | Color |
|------|-------|
| `group/A` | #0075ca |
| `group/B` | #008672 |
| `group/C` | #d93f0b |
| `group/D` | #5319e7 |
| `task` | #a2eeef |
| `bug` | #d73a4a |
| `question` | #d876e3 |
| `high` | #b60205 |
| `normal` | #fbca04 |
| `low` | #cccccc |

- [ ] **Step 5: 创建 Milestones**

GitHub → Issues → Milestones → New milestone：

| Title | Due date | Description |
|-------|----------|-------------|
| M1: 知识库完成 | 第 2 周末 | 20 路口档案、算法调研、实验设计草案、项目规范全部入库 |
| M2: 算法方案确定 | 第 3 周末 | 团队讨论确定最终算法方向 |
| M3: 20 路口全部跑通 | 第 5 周末 | 算法在 20 个路口稳定运行 |
| M4: 实验全部完成 | 第 7 周末 | 所有对比实验数据收集完成 |
| M5: 交付物完成 | 2026-09-01 | 报告、PPT、视频全部定稿 |
| M6: 最终提交 | 2026-09-15 | 最终检查与提交 |

- [ ] **Step 6: 通知团队**

在团队群中发送：

```
仓库已就绪！请大家按以下步骤开始：

1. git clone https://github.com/<org>/xiong-an-traffic.git
2. 打开 docs/guides/first-day.md，按步骤操作
3. 完成后切到自己组的分支开始工作

有问题看 docs/guides/git-for-beginners.md 或群里问。
```
