# XH-202613 车路云协同仿真平台仓库工程设计规范 V1.0

> 日期：2026-07-20
> 状态：定稿
> 适用范围：GitHub 仓库 `xiong-an-traffic` 的完整工程结构与协作规范

---

## 1. 设计目标

将当前以数据存放为主的项目目录，重建为一个规范、长期可维护、适合 8 人协作的工程仓库。

**约束：**
- 不修改原始数据集（`intersection_data/` 保持原样）
- 不进行算法设计、代码实现或实验方案讨论
- 团队为 8 人大二学生，Git 经验仅限 add/commit/push
- 仓库为 Public，对外展示效果需专业
- 项目硬性截止：2026年9月1日；提交缓冲：9月15日
- 文档语言：中英混合（目录/文件名英文，正文中文，commit 英文前缀+中文描述）

---

## 2. 数据管理策略

- `intersection_data/` 全部纳入 Git，clone 即可用
- 原始数据只读，不直接修改
- 需要修改/清洗/转换数据时，在 `results/` 或 `src/` 中生成新文件
- 发现原始数据错误时，单独记录修改说明，经团队确认后统一修正
- `intersection_data/` 中已有的输出文件（stats.xml、traj.xml 等）作为原始数据集的一部分保留入库
- **后续运行产生的新输出**不提交 Git，通过 `.gitignore` 按路径排除（`results/`、`workspace/`），而非按文件名全局排除
- `.gitignore` 中保留 README 例外：`results/*` + `!results/README.md`，`workspace/*` + `!workspace/README.md`

---

## 3. 仓库目录结构

```
xiong-an-traffic/
│
├── intersection_data/          # 主办方原始数据集，20个路口
│   ├── metadata/               # [可写] 路口元数据（CSV/YAML，团队维护的派生数据）
│   │   ├── intersections.csv
│   │   └── intersections.yaml
│   ├── 1/ ~ 20/                # [只读] 各路口原始文件，不修改
│   └── README.md               # 数据集说明、文件结构、使用规则
│
├── src/                        # 源代码
│   ├── main.py                 # 项目统一入口
│   ├── algorithms/             # 信号控制算法
│   ├── simulation/             # SUMO 仿真驱动（批量运行、TraCI封装）
│   ├── analysis/               # 数据分析与可视化
│   ├── interfaces/             # 算法接口、TraCI接口封装、控制器接口
│   ├── common/                 # 公共工具、配置读取、日志
│   └── README.md
│
├── scripts/                    # 一次性/运维脚本（环境配置、数据校验等）
│   └── README.md
│
├── configs/                    # 配置文件（仿真参数、实验参数、路径配置）
│   └── README.md
│
├── docs/                       # 知识中心
│   ├── guides/                 # 指南类
│   │   ├── first-day.md            # 新人第一天指南（15分钟）
│   │   ├── git-for-beginners.md    # Git入门（10分钟）
│   │   ├── sumo-for-beginners.md   # SUMO入门
│   │   ├── traci-for-beginners.md  # TraCI入门
│   │   ├── environment-setup.md    # 环境配置
│   │   ├── how-to-run-simulation.md
│   │   ├── how-to-add-docs.md
│   │   └── development-guide.md    # 开发指南
│   ├── tasks/                  # 任务管理
│   │   ├── current-tasks.md        # 当前阶段任务池
│   │   ├── learning-roadmap.md     # 学习路线
│   │   └── completed-tasks.md      # 已完成任务记录
│   ├── research/               # 算法调研（B组主导）
│   ├── intersections/          # 20个路口档案（A组主导）
│   ├── experiments/            # 实验体系（C组主导）
│   ├── meetings/               # 周会记录（D组主导）
│   ├── decisions/              # ADR（架构/技术决策记录）
│   ├── standards/              # 规范文档（D组主导）
│   ├── faq/                    # 常见问题、踩坑记录
│   ├── glossary/               # 术语表
│   └── README.md               # 知识中心首页（知识地图+阅读顺序+各组入口）
│
├── results/                    # [gitignore] 实验输出
│   └── README.md               # 输出文件组织方式和命名规则
│
├── submission/                 # 最终提交物（报告、PPT、视频、部署文档）
│   ├── report/
│   ├── presentation/
│   ├── video/
│   └── README.md
│
├── references/                 # 外部参考资料
│   ├── papers/
│   ├── standards/
│   ├── policy/
│   ├── manuals/
│   └── README.md
│
├── templates/                  # 文档模板
│   ├── intersection-card.md
│   ├── meeting-notes.md
│   ├── weekly-report.md
│   ├── adr.md
│   ├── research-notes.md
│   ├── experiment-log.md
│   ├── faq-entry.md
│   ├── task-template.md
│   ├── issue-template.md
│   ├── roadmap-template.md
│   └── README.md
│
├── assets/                     # 静态资源（图片、图标、视频素材）
│   └── README.md
│
├── workspace/                  # [gitignore] 团队临时工作区
│   ├── a-team/
│   ├── b-team/
│   ├── c-team/
│   └── d-team/
│
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/              # CI（低优先级，后期启用）
│
├── .gitignore
├── .gitattributes
├── .python-version
├── requirements.txt
├── environment.yml
├── LICENSE
├── README.md                   # 项目导航入口
├── PROJECT_STRUCTURE.md        # 仓库工程说明书（面向团队成员）
└── CONTRIBUTING.md             # 贡献指南
```

### 目录权限规则

| 目录 | 权限 | 负责人 |
|------|------|--------|
| `intersection_data/` | 只读 | A组（发现问题经团队确认后统一修正） |
| `src/` | 可写 | B组为主，A/C组配合 |
| `docs/intersections/` | 可写 | A组 |
| `docs/research/` | 可写 | B组 |
| `docs/experiments/` | 可写 | C组 |
| `docs/standards/` + `docs/meetings/` | 可写 | D组 |
| `docs/guides/` + `docs/tasks/` | 可写 | D组为主，全员可贡献 |
| `submission/` | 可写 | D组为主，冲刺阶段全员 |
| `workspace/` | 自由使用 | 各组（gitignore） |
| `results/` | 自由使用 | 全员（gitignore） |

---

## 4. README 体系

### 层级与职责

| 文件 | 面向谁 | 核心内容 |
|------|--------|---------|
| `README.md`（根） | 任何人 | 项目简介、状态、快速导航、目录表、团队、比赛信息 |
| `PROJECT_STRUCTURE.md` | 团队成员 | 每个目录职责、权限、负责人、新增文件规范 |
| `CONTRIBUTING.md` | 团队成员 | Git工作流、commit规范、分支命名、PR流程、Issue规范 |
| 各目录 `README.md` | 进入该目录的人 | 这里放什么？怎么用？谁负责？ |

### 根 README 结构

1. 项目标题 + 一句话描述
2. **项目状态（Project Status）**：当前阶段、路线、最近更新、版本号
3. 项目简介（2-3句）
4. **快速导航（Quick Links）**：新成员入口、项目结构、贡献指南、知识中心、团队分工、任务板
5. 快速开始（clone → 环境 → 运行，3步）
6. 目录导航表
7. 团队信息
8. 比赛信息
9. License

### docs/README.md（知识中心首页）

- 知识地图
- 新人推荐阅读顺序
- 各小组对应文档入口
- 最近新增文档（保持5-10条）
- 常用文档推荐

### 统一规范

- 任何新增一级目录必须同时创建 README.md
- 任何新增二级目录如果承担长期维护职责，也应创建 README.md
- 根 README 不超过一屏半，详细内容通过链接跳转
- README 是活文档，目录结构变化时必须同步更新

---

## 5. Git 分支策略与协作规范

### 三阶段渐进

| 阶段 | 时间 | 模式 | 团队需要会的操作 |
|------|------|------|----------------|
| Phase 1 | 当前~第2周 | 4个组分支 + main（Owner合并） | switch, pull, add, commit, push |
| Phase 2 | 第3周起 | 引入 develop + 功能分支 | checkout -b, merge |
| Phase 3 | 第5周起 | PR + 1人 Review | GitHub 网页操作 PR |

### Phase 1 规则

- `main` 为保护分支，普通成员不直接 push
- 组分支：`docs/a-team`、`docs/b-team`、`docs/c-team`、`docs/d-team`
- 组员在组分支上 commit + push
- 各组 Owner 每2-3天 merge 到 main（merge 前先 pull origin main）
- 按目录分工避免冲突

### Phase 2 规则

- 新增 `develop` 分支作为开发主线
- 进入 Phase 2 后，`docs/*` 组分支归档（不再使用），所有新工作从 `develop` 创建功能分支
- 功能分支命名：`feature/<描述>`、`simulation/<描述>`、`fix/<描述>`
- 从 develop 创建，完成后 merge 回 develop
- main 只在里程碑节点从 develop 合并

### Phase 3 规则

- 功能分支通过 PR 合并到 develop
- Review 只看三点：能不能运行、有没有影响别人、命名目录是否规范
- Squash merge 保持历史整洁

### Commit 规范

格式：`<type>(<scope>): <中文描述>`

Phase 1 只需记4个 type：

| type | 场景 | 示例 |
|------|------|------|
| `docs` | 文档 | `docs(A): 完成路口1数据档案` |
| `feat` | 新功能/算法 | `feat(B): 新增Webster算法框架` |
| `fix` | 修复 | `fix(A): 修复SUMO配置文件` |
| `chore` | 配置/仓库维护 | `chore: 更新.gitignore` |

后期按需增加 `refactor`、`experiment`、`test`、`style`。

scope 取值：`A` / `B` / `C` / `D` / `all`，或模块名。

规则：一次 commit 只做一件事；不写无信息量描述。

### Issue Labels（精简版）

```
group/A  group/B  group/C  group/D
task  bug  question
high  normal  low
```

### Milestones

| # | 内容 | 目标 |
|---|------|------|
| M1 | 知识库完成 | 第2周末 |
| M2 | 算法方案确定 | 第3周末 |
| M3 | 20路口全部跑通 | 第5周末 |
| M4 | 实验全部完成 | 第7周末 |
| M5 | 报告/PPT/视频全部完成 | 9月1日 |
| M6 | 最终检查与提交 | 9月15日 |

### Project Board

GitHub Projects 看板视图：`Backlog → 本周任务 → 进行中 → 待Review → 完成`

### 分支保护

| 分支 | 规则 |
|------|------|
| `main` | 禁止直接 push；Phase 1 由 Owner merge；Phase 3 后只接受来自 develop 的 PR |
| `develop` | Phase 2 起禁止直接 push；只接受功能分支的 merge/PR |

---

## 6. 知识库体系

### 定位

`docs/` 是整个项目的知识中心。所有学习成果、调研资料、会议记录、规范文档都沉淀在这里。

### 知识沉淀原则

| 原则 | 说明 |
|------|------|
| 先知识库，后正式文档 | 素材先沉淀到 docs/，最终报告/PPT 从中提取整合 |
| 一个主题一个文件 | 按主题拆分，不塞大文件 |
| 文件头部标注元信息 | 作者、创建日期、最后更新、所属小组、状态 |
| 不删除，只标记过时 | 标注 `[已过时]` 并链接新结论，保留思考轨迹 |
| 可引用 | 后续写报告时直接引用 docs/ 内容 |

### 文档元信息模板

```markdown
---
title: 文档标题
author: X组-姓名
created: YYYY-MM-DD
updated: YYYY-MM-DD
group: A/B/C/D
status: draft | review | final
---
```

### ADR 格式

```markdown
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

---

## 7. 文档规范

### 核心原则

> 规范服务于团队，而不是团队服务于规范。模板比规范更重要，示例比说明更重要，Checklist 比长篇文字更重要。

### 硬性规则（仅4条）

1. 文件放到正确目录
2. 文件命名符合规范
3. 新增目录必须带 README
4. 不修改 `intersection_data/` 原始数据

### 文件命名

| 类型 | 规则 | 示例 |
|------|------|------|
| 目录名 | 英文小写 kebab-case | `docs/guides/` |
| 代码/脚本/配置 | 英文小写 snake_case | `batch_simulation.py` |
| 对外/长期维护文档 | 英文小写 kebab-case | `intersection-01.md` |
| 团队内部文档 | 允许中文 | `A组任务书.md`、`第一次周会记录.md` |
| 图片 | 英文小写 kebab-case | `intersection-01-map.png` |
| 会议记录 | `YYYY-MM-DD-weekly.md` 或中文 | `2026-07-27-weekly.md` |
| ADR | `NNN-简短描述.md` | `001-repo-structure.md` |

禁止：文件名中使用空格、大写字母（英文部分）。

### 图片规范（仅2条）

1. 原始图片绝不修改
2. 文档引用统一放 `assets/` 或 `docs/` 对应子目录

### 推荐规范（不强制，逐步养成）

- 标题最多四级
- 代码块标注语言
- 中英文之间加空格
- 用相对路径引用仓库内文件
- 超过3列信息用表格

### 提交文档前 Checklist

```
□ 文件放在正确目录
□ 文件命名符合规范
□ README 已同步更新（如有需要）
□ 图片能够正常显示
□ 仓库内链接可以正常跳转
□ Markdown 预览正常
```

### 版本管理规则

- 不用文件名标版本（禁止 `report_v2_final.md`），用 Git 历史
- 文档状态用元信息标注（draft / review / final）
- 交付物定稿后打 tag（`v1.0-submission`）

---

## 8. 工程化建议

### 高优先级（Day 1）

| 项目 | 说明 |
|------|------|
| `.gitignore` | 排除 results/、workspace/、__pycache__/、.venv/、*.pyc、SUMO输出、.idea/、.vscode/、*.log |
| `.gitattributes` | `* text=auto eol=lf`；XML/xlsx/png 标记 binary |
| `LICENSE` | MIT 或 Apache-2.0 |
| 分支保护 | GitHub Settings 保护 main |
| 仓库三件套 | README.md + PROJECT_STRUCTURE.md + CONTRIBUTING.md |
| `requirements.txt` | traci, sumolib, pandas, numpy, matplotlib, pyyaml |
| `environment.yml` | Conda 用户环境 |
| `.python-version` | 锁定 Python 版本 |

### 中优先级（第2-3周）

| 项目 | 说明 |
|------|------|
| GitHub Labels + Issue Templates | `.github/ISSUE_TEMPLATE/` |
| GitHub Milestones | M1-M6 |
| GitHub Projects 看板 | 5列看板 |
| `configs/` 参数化 | 仿真参数用 YAML/JSON，不硬编码 |

### 低优先级（第4周后）

| 项目 | 说明 |
|------|------|
| GitHub Actions CI | Markdown lint、Python flake8、目录结构校验 |
| `scripts/validate-structure.sh` | 检查每个目录是否有 README |
| CHANGELOG.md | 里程碑变更记录 |
| 版本 Tag | `v0.1-structure`、`v0.2-knowledge-base`、`v1.0-submission` |

### 扩展性设计

| 考虑 | 做法 |
|------|------|
| 算法可替换 | `src/algorithms/` 每个算法一个文件，通过 `src/interfaces/` 统一接口 |
| 路口可扩展 | 新增路口只需在 `intersection_data/` 下加目录 + 更新 metadata |
| 实验可复现 | `configs/` 存参数，`scripts/` 存运行脚本，`results/README.md` 说明复现步骤 |
| 文档可生成 | 正式报告从 `docs/` 提取，不需要重写 |
| 比赛后可复用 | 去掉 intersection_data/ 和 submission/ 后仍是标准交通仿真项目模板 |

### 仓库健康度自检（每2周）

```
□ 每个一级目录都有 README.md
□ 没有文件放错目录
□ .gitignore 覆盖了所有不应入库的文件
□ 最近2周的 commit message 符合规范
□ 没有超过50MB的文件意外入库
□ docs/README.md 的索引是最新的
□ 没有未关闭的过期 Issue
```

---

## 9. 实施步骤

```
Step 1: 创建 GitHub 仓库（Public）
Step 2: 创建完整目录结构
Step 3: 生成所有 README 空模板
Step 4: 配置 .gitignore / .gitattributes / requirements.txt / environment.yml
Step 5: 将 intersection_data/ 纳入版本控制
Step 6: 创建 intersection_data/metadata/（intersections.csv + intersections.yaml）
Step 7: 初始化分支（main + 4个组分支）
Step 8: 配置分支保护 + Labels + Milestones
Step 9: 提交 v0.1-structure tag
Step 10: 通知8人 clone，按 docs/guides/first-day.md 开始协作
```

**环境文件使用说明：**
- `requirements.txt`：pip 用户使用（`pip install -r requirements.txt`）
- `environment.yml`：conda 用户使用（`conda env create -f environment.yml`）
- 两者维护相同的依赖列表，选择其一即可
