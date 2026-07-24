# Main README Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the root README to the detailed `github/main` structure while preserving only verified current paths, commands, project status, limitations, and team completion states.

**Architecture:** Treat `github/main:README.md` as the narrative and layout baseline. Apply a narrowly scoped documentation migration layer: replace stale repository paths and commands, update evidence-backed status tables, and retain current limitations without rewriting the README into a module index.

**Tech Stack:** Markdown, Git, PowerShell, Python Markdown link checker, pytest, Git Bash lint script.

## Global Constraints

- Modify only `README.md`; the design and plan files are process artifacts and must not cause unrelated documentation rewrites.
- Preserve the `github/main:README.md` chapter order and long-form project narrative.
- Use SUMO 1.27.1 as the project-verified version.
- Use current canonical repository paths under `docs/architecture/`, `docs/operations/`, `docs/reference/`, `docs/reports/`, `docs/team/`, `scripts/{data,simulation,validation,quality}/`, `tests/{unit,integration}/`, and `output/`.
- Team status must distinguish 已完成、基础实现完成、部分完成、进行中 and 待完成 using repository evidence.
- IB status is 已完成; AB MVI phase handling, EX full experiment matrix, Docker real build, DA deliverables, and DB dashboard/video remain open where specified.
- Do not modify or force-push GitHub `main`; publish only to `codex/repository-structure-optimization`.

---

### Task 1: Restore and update the root README

**Files:**
- Modify: `README.md`
- Read-only baseline: `github/main:README.md`
- Read-only requirements: `docs/superpowers/specs/2026-07-24-main-readme-alignment-design.md`

**Interfaces:**
- Consumes: the long-form README structure at `github/main:README.md`, current repository paths, and the eight-role completion matrix in the design specification.
- Produces: a root README whose local links resolve against the reorganized repository and whose status statements match current implementation evidence.

- [ ] **Step 1: Restore the main README structure**

Use `git show github/main:README.md` as the source for `README.md`. Preserve these sections and their order:

```text
目录
项目概述
仓库导航
快速开始
协作指南
项目结构
数据说明
系统架构
核心算法
实验设计
团队分工
开发计划
提交材料
许可与致谢
```

Do not retain the current standalone `模块索引` rewrite. The canonical module documentation remains discoverable through a short link to `docs/README.md` inside 仓库导航.

- [ ] **Step 2: Correct badges, introduction, branch policy, and current status**

Keep the main badges and introduction, with these exact corrections:

```markdown
[![编号 XH-202613](https://img.shields.io/badge/%E7%BC%96%E5%8F%B7-XH--202613-orange)](docs/reference/competition/)
[![赛道 B](https://img.shields.io/badge/%E8%B5%9B%E9%81%93-B%EF%BC%88%E7%AE%97%E6%B3%95%E8%B0%83%E4%BC%98%E5%9E%8B%EF%BC%89-green)](docs/reference/competition/)
[![SUMO](https://img.shields.io/badge/SUMO-1.27.1-brightgreen)](https://www.eclipse.org/sumo/)
```

Replace the obsolete stable/master sentence with:

```markdown
`main` 是稳定分支，功能改动应在独立分支完成，并通过 Pull Request 审查后合入。
```

In 当前状态, retain the module summary but update infrastructure evidence to:

```markdown
**IA（仿真基础设施 A）状态（2026-07-24）**：已完成 20 个路口在 SUMO 1.27.1 下的迁移、增强配置、边映射和批量验证；Docker 定义已就绪，真实跨机器镜像构建仍待验证。

**IB（仿真基础设施 B）状态（2026-07-24）**：已完成 TraCI 桥接、seed 透传、车辆采样与 500 上限、断线韧性、EdgeChannel、逐步日志、事件日志和实验 CLI；全量回归为 66 passed，固定配时与 CA-MP 3600 步均退出 0。
```

- [ ] **Step 3: Update repository navigation and canonical documentation paths**

Use these canonical paths in 仓库导航:

```text
docs/reference/competition/
docs/team/project-roadmap.md
docs/team/tasks/w1/ ... docs/team/tasks/w6/
docs/architecture/interface.md
docs/operations/deployment.md
docs/operations/sumo-environment-setup.md
docs/reference/edge-mapping.md
docs/reports/sumo-migration-log.md
docs/reports/batch-validation-report.md
docs/reports/w3-log-audit.md
docs/reports/w5-verification.md
docs/reports/w6-review-issues.md
docs/README.md
```

Remove references to `docs/pdf/`, `docs/tasks/`, `docs/总路线.md`, `docs/deployment.md`, `docs/interface.md`, `docs/edge_mapping.md`, `docs/migration_log.md`, `docs/batch_validate_report.md`, `docs/sumo_env_setup.md`, and `docs/notes/docker_sumo_research.md`.

- [ ] **Step 4: Update quick-start and validation commands**

Keep the original environment setup and data-root override. Require SUMO 1.27.1 and include these current commands:

```powershell
python -m pytest tests/ -q
python scripts/validation/validate_all.py
python examples/run_fixed_time.py 1
python examples/run_ca_max_pressure.py 1 3600
python experiments/runner.py --intersection 1 --algorithm ca_maxpressure `
  --flow-multiplier 1.5 --seed 42 --steps 3600 --output-dir output/exp1
```

For lint, use:

```bash
bash scripts/quality/lint_check.sh
```

Retain the FastAPI command and state that most `/api/*` collaboration routes are placeholders.

- [ ] **Step 5: Replace the project tree with the reorganized taxonomy**

Preserve the detailed source-module descriptions from main and replace only moved directory blocks. The scripts, tests, docs, and output blocks must be:

```text
├── scripts/
│   ├── data/                     # 元数据与边映射生成
│   ├── simulation/               # SUMO 配置生成与任务拆分
│   ├── validation/               # 环境、输出、seed 与压力验证
│   └── quality/                  # lint 与静态检查
├── tests/
│   ├── unit/                     # 单模块行为测试
│   └── integration/              # 跨模块与真实流程测试
├── docs/
│   ├── architecture/             # 接口与架构图
│   ├── operations/               # 部署与 SUMO 环境
│   ├── reference/                # 边映射与赛题资料
│   ├── reports/                  # 验证、迁移和审查报告
│   ├── team/                     # 路线图与六周任务书
│   ├── guides/                   # 协作指南
│   └── superpowers/              # 历史设计与实施计划
├── output/                       # 运行时输出、历史归档与提交物
```

- [ ] **Step 6: Update architecture assets and preserve technical content**

Use these image paths:

```markdown
![系统架构](docs/architecture/images/architecture.png)
![仿真数据流](docs/architecture/images/simulation-loop.png)
![团队组织](docs/architecture/images/team-org.png)
![时间线](docs/architecture/images/timeline.png)
```

Retain the main README's CA-MP explanation, algorithm comparison, EWMA formula, experiment design, evaluation metrics, and data description. Add an 已知限制 paragraph after the algorithm/experiment material with these facts:

```text
CA-MP 当前 MVI 桩会产生非法 set_phase 值，TraCIBridge 会记录 warning 并跳过；真实算法效果仍由 AB 完成。
部分实验指标仍是实时状态近似值，精确行程时间和燃油消耗需要 tripinfo 校准。
ML 训练/预测和多数 /api/* 协同端点仍是占位实现。
Docker 尚未完成跨机器真实镜像构建验证。
```

- [ ] **Step 7: Update all eight team completion states and task links**

Use the following status cells in the 团队分工 table:

| Role | Status text |
| --- | --- |
| TL | 部分完成：核心契约、接口、文档 taxonomy 与集成验证已落地；最终集成和交付审查待完成 |
| IA | 已完成：20 路口迁移、增强配置、边映射和批量验证完成；Docker 实机构建待回填 |
| IB | 已完成：TraCI、seed、采样、断线、EdgeChannel、step/events 日志和 CLI 已通过 66 项回归 |
| AA | 基础实现完成：FixedTime 与 Actuated 控制器、测试和固定配时实跑已完成；全矩阵复核待完成 |
| AB | 进行中：CA-MP 管道可运行；MVI 相位值与真实算法效果待完成 |
| EX | 部分完成：runner、seed/倍率、日志与 12 次审计已完成；360 次实验和精确指标待完成 |
| DA | 待完成：技术 Markdown 已有；Word 报告、PPT 和提交排版待完成 |
| DB | 部分完成：Matplotlib 绘图接口已有；PyQt 看板与演示视频待完成 |

Update all 48 task links to `docs/team/tasks/wN/<kebab-case-name>.md` using the exact role mapping documented in `docs/team/tasks/README.md`. Set the roadmap link to `docs/team/project-roadmap.md`.

- [ ] **Step 8: Synchronize submission-material status**

Keep the original submission table and use these status statements:

```text
源代码：基础设施与目录整理已完成，算法/实验/交付继续集成
部署说明：已完成，路径为 docs/operations/deployment.md
Dockerfile + 部署文档：文件已完成，真实镜像构建待验证
PPT、Word 报告、演示视频、实际场景演示方案：待完成
```

- [ ] **Step 9: Validate the README**

Run:

```powershell
.venv\bin\python.exe .superpowers\sdd\check_markdown_links.py
```

Expected: `Missing local targets: 0`.

Run the stale-path scan:

```powershell
rg -n "docs/(pdf|tasks)/|docs/(总路线|deployment|interface|edge_mapping|migration_log|batch_validate_report|sumo_env_setup)\.md|scripts/(validate_all|batch_validate|generate_edge_mapping|lint_check)\.(py|sh)" README.md
```

Expected: no output.

Run:

```powershell
.venv\bin\python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp output/archive/checks/readme-alignment-pytest
```

Expected: `66 passed`.

Run through Git Bash:

```bash
bash scripts/quality/lint_check.sh
```

Expected: `clean`.

Run:

```powershell
git diff --check
```

Expected: exit code 0 with no whitespace errors.

- [ ] **Step 10: Review, commit, and publish**

Confirm the root README still contains all 14 main sections, all eight team roles, and no uncommitted file other than `README.md` before staging. Commit with:

```bash
git add README.md
git commit -m "docs: realign README with main"
git push github codex/repository-structure-optimization
```

Verify the remote branch SHA equals local HEAD. Do not update or force-push `github/main`.

---

## Self-Review

- Spec coverage: main-based structure, canonical paths, SUMO 1.27.1, commands, limitations, eight team statuses, submission status, validation, and branch safety all map to explicit steps.
- Placeholder scan: every action and expected result is explicit; no deferred or unspecified implementation step remains.
- Path consistency: all commands and document paths use the post-migration taxonomy; the 48 task filenames use the kebab-case mapping.
- Scope: only `README.md` is an implementation target.
