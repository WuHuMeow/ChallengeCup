# Gitee 平铺结构合并实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 Gitee `origin/master` 的顶层平铺结构为最终结构，迁移本地 `ca_mp/` 中的增强代码、测试和文档，完成验证后暂停等待用户确认，再覆盖推送 GitHub `github/main`。

**Architecture:** 保留 Gitee 的 `core/`、`engine/`、`algorithms/`、`cloud/`、`ml/`、`api/`、`experiments/`、`scenes/`、`visualization/` 顶层模块。以本地模块实现为代码基线，吸收 Gitee 独有内容；所有运行时导入改为平铺模块导入，文档入口统一到 Gitee 的 README、`docs/tasks/` 和 `docs/总路线.md`。

**Tech Stack:** Python 3.10+、setuptools、pytest、SUMO/TraCI 1.27.1、PowerShell、Git。

## Global Constraints

- 合并源：Gitee `origin/master`；最终远程目标：GitHub `github/main`。
- 代码最终不得依赖 `ca_mp/` 作为运行时主入口。
- 同路径代码以本地增强版本为基线，但不得丢失 Gitee 独有文件和测试。
- 所有 README 和 Markdown 中的当前路径、命令、导入示例必须与平铺结构一致。
- 生成结果目录 `output/` 与报告目录 `report/` 保持不同职责。
- `.remote-gitee-inspect/` 只用于迁移分析，完成后删除且不得进入提交。
- 用户确认前不得执行 GitHub 推送；确认后使用 `git push --force-with-lease github HEAD:main`。

---

## 文件变更总览

### 代码目录迁移

- `ca_mp/core/` → `core/`
- `ca_mp/engine/` → `engine/`
- `ca_mp/algorithms/` → `algorithms/`
- `ca_mp/cloud/` → `cloud/`
- `ca_mp/ml/` → `ml/`
- `ca_mp/api/` → `api/`
- `ca_mp/experiments/` → `experiments/`
- `ca_mp/scenes/` → `scenes/`
- `ca_mp/visualization/` → `visualization/`

### 重点入口

- `pyproject.toml`
- `config/default.yaml`
- `examples/*.py`
- `scripts/`
- `tests/`
- `README.md`
- `docs/总路线.md`
- `docs/tasks/`
- `docs/guides/`
- `docs/superpowers/`

### 必须保留的本地增强

- `engine/edge_channel.py`、`engine/events.py` 和增强版 `engine/configs/`
- `data/intersection_data/metadata/edge_mapping.json`
- `tests/unit/`、`tests/integration/` 中的新增测试
- `pyproject.toml`、`output/`、`output/deliverables/`
- Gitee 的 `report/`

---

### Task 1: 建立远程差异清单

**Files:**
- Read: `.remote-gitee-inspect/`
- Read: `README.md`、`pyproject.toml`、`docs/`
- Modify: none

**Interfaces:**
- Consumes: Gitee 临时克隆和当前本地 HEAD。
- Produces: 迁移期间使用的文件差异清单，不写入仓库。

- [ ] **Step 1: 确认工作区状态**

Run:

```powershell
git status --short --branch
git log -3 --oneline --decorate
```

Expected: 当前分支为 `main`；最近提交包含本次设计文档；除临时克隆外没有未预期改动。

- [ ] **Step 2: 比较两边文件树**

Run:

```powershell
$local = @(git ls-tree -r --name-only HEAD)
$remote = @(git -C .remote-gitee-inspect ls-tree -r --name-only HEAD)
"LOCAL=$($local.Count) REMOTE=$($remote.Count)"
Compare-Object $local $remote
```

Expected: 明确远程独有、本地独有和同路径文件；同路径代码不直接整目录覆盖。

- [ ] **Step 3: 确认远程目标**

Run:

```powershell
git -C .remote-gitee-inspect log -1 --oneline --decorate
git ls-remote --heads github main
git remote -v
```

Expected: 源为 Gitee `master`，GitHub 目标为 `main`。

- [ ] **Step 4: Commit**

本任务只产生分析结果，不单独提交。

---

### Task 2: 将本地代码迁移到平铺目录

**Files:**
- Move: `ca_mp/{algorithms,api,cloud,core,engine,experiments,ml,scenes,visualization}/` 到对应顶层目录
- Delete: `ca_mp/__init__.py`

**Interfaces:**
- Consumes: 本地 `ca_mp/` 代码。
- Produces: Gitee 风格的顶层 Python 模块；代码内容保持不变，导入在 Task 3 修复。

- [ ] **Step 1: 确认目标目录没有用户内容**

Run:

```powershell
Get-ChildItem -Directory -Name core,engine,algorithms,cloud,ml,api,experiments,scenes,visualization -ErrorAction SilentlyContinue
```

Expected: 目标代码目录不存在；若存在未跟踪目录，逐项比对后才继续。

- [ ] **Step 2: 使用 Git 保留迁移关系**

Run:

```powershell
git mv ca_mp/algorithms algorithms
git mv ca_mp/api api
git mv ca_mp/cloud cloud
git mv ca_mp/core core
git mv ca_mp/engine engine
git mv ca_mp/experiments experiments
git mv ca_mp/ml ml
git mv ca_mp/scenes scenes
git mv ca_mp/visualization visualization
git rm ca_mp/__init__.py
```

Expected: 9 个模块被移动，未出现内容丢失。

- [ ] **Step 3: 清除 Python 缓存**

Run:

```powershell
Get-ChildItem -Recurse -Directory -Filter __pycache__ -Path algorithms,api,cloud,core,engine,experiments,ml,scenes,visualization -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
```

- [ ] **Step 4: Commit**

```powershell
git add -A ca_mp algorithms api cloud core engine experiments ml scenes visualization
git commit -m "refactor: flatten ca-mp modules to repository layout"
```

---

### Task 3: 修复导入、包发现和配置路径

**Files:**
- Modify: `algorithms/*.py`、`api/*.py`、`cloud/*.py`、`core/*.py`、`engine/*.py`、`experiments/*.py`、`ml/*.py`、`scenes/*.py`、`visualization/*.py`
- Modify: `examples/*.py`、`scripts/*.py`、`tests/**/*.py`
- Modify: `pyproject.toml`、`config/default.yaml`

**Interfaces:**
- Consumes: Task 2 的平铺目录。
- Produces: 可从仓库根目录和 editable install 导入的顶层模块。

- [ ] **Step 1: 建立旧导入清单**

```powershell
Get-ChildItem -Recurse -File -Path algorithms,api,cloud,core,engine,experiments,ml,scenes,visualization,examples,scripts,tests | Select-String -Pattern 'from ca_mp\.|import ca_mp'
```

- [ ] **Step 2: 按模块名替换导入**

```python
# old
from ca_mp.core.types import JointState
from ca_mp.engine.runner import SimulationRunner
from ca_mp.algorithms.base import BaseControlAlgorithm

# new
from core.types import JointState
from engine.runner import SimulationRunner
from algorithms.base import BaseControlAlgorithm
```

动态导入和模块 README 中的示例使用同样规则；保留 TraCI 的 `SUMO_HOME` 处理。

- [ ] **Step 3: 更新 setuptools 配置**

将 `pyproject.toml` 的包发现配置改为：

```toml
[tool.setuptools.packages.find]
include = [
  "algorithms*",
  "api*",
  "cloud*",
  "core*",
  "engine*",
  "experiments*",
  "ml*",
  "scenes*",
  "visualization*",
]
```

- [ ] **Step 4: 更新模型路径**

在 `config/default.yaml` 中将 `./ca_mp/ml/model.pkl` 改为 `./ml/model.pkl`，并把当前配置中的其他 `ca_mp/engine`、`ca_mp/ml` 路径改为平铺路径。

- [ ] **Step 5: 运行导入冒烟测试**

```powershell
python -c "from core.types import JointState, VehicleState; from algorithms.ca_max_pressure import CAMaxPressureAlgorithm; from engine.runner import SimulationRunner; from experiments.runner import run_batch; print('flat imports OK')"
```

Expected: 输出 `flat imports OK`。

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml config/default.yaml algorithms api cloud core engine experiments ml scenes visualization examples scripts tests
git commit -m "refactor: update imports and package paths for flat layout"
```

---

### Task 4: 整理脚本入口和仿真配置

**Files:**
- Move: `scripts/data/extract_metadata.py`、`scripts/data/generate_edge_mapping.py` 到 `scripts/`
- Move: `scripts/simulation/generate_configs.py`、`scripts/simulation/split_jobs.py` 到 `scripts/`
- Move: `scripts/validation/*.py` 到 `scripts/`
- Keep: `scripts/quality/lint_check.sh`
- Move: `ca_mp/engine/configs/` 到 `engine/configs/`

**Interfaces:**
- Consumes: Task 3 的平铺导入和配置路径。
- Produces: 与 Gitee 一致的脚本入口，同时保留本地验证能力。

- [ ] **Step 1: 移动脚本和 SUMO 配置**

使用 `git mv` 移动文件；若 Gitee 同名文件已存在，先逐行合并，再删除旧副本，不直接覆盖。

- [ ] **Step 2: 修复脚本内路径**

统一使用：

```text
ca_mp/engine/configs/ -> engine/configs/
scripts/data/ -> scripts/
scripts/simulation/ -> scripts/
scripts/validation/ -> scripts/
```

- [ ] **Step 3: 验证入口可加载**

```powershell
python scripts/validate_all.py --help
python scripts/batch_validate.py --help
python scripts/check_outputs.py --help
```

Expected: 能加载模块并输出帮助或明确参数说明，不出现 `ModuleNotFoundError`。

- [ ] **Step 4: Commit**

```powershell
git add scripts engine/configs
git commit -m "refactor: flatten simulation and validation entrypoints"
```

---

### Task 5: 合并并扁平化测试

**Files:**
- Merge: `tests/test_algorithms.py`、`test_api.py`、`test_cloud.py`、`test_experiments.py`、`test_ml.py`、`test_mock_bridge.py`、`test_scenes.py`
- Move/Create: `tests/test_edge_channel.py`、`test_edge_mapping.py`、`test_events.py`、`test_resilience.py`、`test_seed.py`、`test_step_log.py`、`test_types_fields.py`、`test_vehicles.py`
- Delete after merge: `tests/unit/`、`tests/integration/`

**Interfaces:**
- Consumes: Gitee 根目录测试与本地 unit/integration 测试。
- Produces: Gitee 风格的 `tests/test_*.py`，不重复收集测试。

- [ ] **Step 1: 合并同名测试**

按以下来源逐组比较并合并：

```text
remote tests/test_algorithms.py  + local tests/unit/test_algorithms.py       -> tests/test_algorithms.py
remote tests/test_api.py         + local tests/integration/test_api.py       -> tests/test_api.py
remote tests/test_cloud.py       + local tests/unit/test_cloud.py            -> tests/test_cloud.py
remote tests/test_experiments.py + local tests/integration/test_experiments.py -> tests/test_experiments.py
remote tests/test_ml.py          + local tests/unit/test_ml.py               -> tests/test_ml.py
remote tests/test_mock_bridge.py + local tests/unit/test_mock_bridge.py      -> tests/test_mock_bridge.py
remote tests/test_scenes.py      + local tests/integration/test_scenes.py    -> tests/test_scenes.py
```

相同测试函数只保留一个实现，不同断言、fixture 和边界用例全部保留。

- [ ] **Step 2: 移动本地独有测试**

将其他 unit/integration 测试移动到 `tests/test_*.py`，并把导入改为 `core.*`、`engine.*` 等平铺路径。

- [ ] **Step 3: 检查收集结果**

```powershell
pytest --collect-only -q
```

Expected: 没有重复 node id，也没有旧 `ca_mp` 导入错误。

- [ ] **Step 4: 运行测试**

```powershell
pytest -q
```

Expected: 可运行测试全部通过；SUMO 缺失时只记录对应环境限制。

- [ ] **Step 5: Commit**

```powershell
git add tests
git commit -m "test: merge flat-layout and local coverage"
```

---

### Task 6: 合并数据、Docker 和根目录元文件

**Files:**
- Modify: `requirements.txt`、`.gitignore`、`docker/`、`docker-compose.yml`
- Keep/Merge: `data/intersection_data/metadata/edge_mapping.json`
- Keep: `output/`、`report/`

**Interfaces:**
- Consumes: Gitee 独有元文件和本地增强数据/部署文件。
- Produces: 数据、Docker 和运行产物路径与平铺代码一致。

- [ ] **Step 1: 逐项合并根目录元文件**

对 `README.md`、`requirements.txt`、`.gitignore` 和 Docker 文件逐项比较；保留本地依赖、验证规则和 Gitee 独有说明，不整文件覆盖。

- [ ] **Step 2: 检查数据入口**

确认 `core/config.py`、`scenes/registry.py` 和脚本都指向 `data/intersection_data/`，保留 `metadata/edge_mapping.json`。

- [ ] **Step 3: 校验 Docker 代码路径**

Docker 必须复制平铺模块：

```dockerfile
COPY algorithms/ ./algorithms/
COPY api/ ./api/
COPY cloud/ ./cloud/
COPY core/ ./core/
COPY engine/ ./engine/
COPY experiments/ ./experiments/
COPY ml/ ./ml/
COPY scenes/ ./scenes/
COPY visualization/ ./visualization/
```

同时覆盖 `engine/configs/`、`data/`、`config/` 和 `scripts/`。

- [ ] **Step 4: Commit**

```powershell
git add requirements.txt .gitignore docker data/intersection_data/metadata output report
git commit -m "chore: align runtime data and deployment paths"
```

---

### Task 7: 统一全部 Markdown 和 README

**Files:**
- Modify: `README.md`、`docs/总路线.md`、`docs/tasks/`、`docs/guides/`、`docs/superpowers/`
- Merge: `docs/*.md`、`examples/README.md`、`scripts/README.md`、`tests/README.md`、`output/*/README.md`
- Delete after migration: 已合并的 `docs/team/`、`docs/operations/`、`docs/reports/` 和重复架构文档目录

**Interfaces:**
- Consumes: Gitee 文档布局、本地最新进度和最终平铺代码路径。
- Produces: 所有当前操作文档可直接执行，不引用已删除路径。

- [ ] **Step 1: 迁移任务文档**

将本地任务文档按 Gitee 命名迁移到 `docs/tasks/`：

```text
aa-algorithm-a.md -> AA_algo_a.md
ab-algorithm-b.md -> AB_algo_b.md
da-delivery-a.md -> DA_delivery_a.md
db-delivery-b.md -> DB_delivery_b.md
ex-experiment.md -> EX_experiment.md
ia-infrastructure-a.md -> IA_infra_a.md
ib-infrastructure-b.md -> IB_infra_b.md
tl-technical-lead.md -> TL_tech_lead.md
```

- [ ] **Step 2: 合并架构、部署和报告文档**

```text
docs/architecture/interface.md -> docs/interface.md
docs/operations/deployment.md -> docs/deployment.md
docs/operations/sumo-environment-setup.md -> docs/sumo_env_setup.md
docs/reports/sumo-migration-log.md -> docs/migration_log.md
docs/reports/batch-validation-report.md -> docs/batch_validate_report.md
docs/reference/edge-mapping.md -> docs/edge_mapping.md
docs/notes/docker-sumo-research.md -> docs/notes/docker_sumo_research.md
```

Gitee 同名文档与本地文档逐段合并，保留本地接口说明、部署约束和验证结果。

- [ ] **Step 3: 更新运行示例**

根 README 和相关指南使用：

```text
python examples/run_fixed_time.py 1
python examples/run_ca_max_pressure.py 1 3600
python -m experiments.runner --intersection 1 --algorithm ca_maxpressure --steps 3600
uvicorn api.server:app --reload
```

- [ ] **Step 4: 扫描并修复旧路径**

```powershell
Get-ChildItem -Recurse -File -Include *.md,README* | Select-String -Pattern 'ca_mp/|docs/team/|docs/operations/|docs/reports/|scripts/(data|simulation|validation)/'
```

Expected: 只剩本迁移设计文档的对照表和明确标注的历史说明。

- [ ] **Step 5: 校验链接**

逐个检查 README、任务书、指南和报告中的本地链接，确保目标文件存在且相对路径正确。

- [ ] **Step 6: Commit**

```powershell
git add README.md docs examples/README.md scripts/README.md tests/README.md output/README.md output/deliverables/README.md
git commit -m "docs: synchronize documentation with flat repository layout"
```

---

### Task 8: 执行静态、导入和运行验证

**Files:**
- Read: 所有 `*.py`、`pyproject.toml`、`config/`、`scripts/`
- Modify: 仅修复验证实际发现的问题

**Interfaces:**
- Consumes: Task 2–7 的最终平铺代码和文档。
- Produces: 可复现的验证结果和明确的环境限制。

- [ ] **Step 1: 编译全部源码**

```powershell
python -m compileall -q algorithms api cloud core engine experiments ml scenes visualization examples scripts tests
```

Expected: 无语法错误。

- [ ] **Step 2: 检查旧导入和路径**

```powershell
Get-ChildItem -Recurse -File -Path algorithms,api,cloud,core,engine,experiments,ml,scenes,visualization,examples,scripts,tests | Select-String -Pattern 'from ca_mp\.|import ca_mp|ca_mp/|ca_mp\\'
```

Expected: 无输出。

- [ ] **Step 3: 运行完整测试**

```powershell
pytest -q
```

Expected: 测试通过；失败时回到对应 Task 修复，不跳过失败。

- [ ] **Step 4: 运行仓库验证脚本**

```powershell
python scripts/check_outputs.py
python scripts/validate_all.py
```

Expected: 输出完整性检查通过；SUMO 缺失时记录具体限制。

- [ ] **Step 5: 运行最小仿真（具备 SUMO 时）**

```powershell
python examples/run_fixed_time.py 1
python examples/run_ca_max_pressure.py 1 100
```

Expected: 两个入口正常启动、运行和退出，输出位于预期 `output/` 路径。

- [ ] **Step 6: Commit 修复**

验证中发现的问题按模块提交，提交信息使用 `fix:` 或 `test:` 前缀，并在最终报告列出。

---

### Task 9: 清理临时目录并创建本地交付提交

**Files:**
- Delete: `.remote-gitee-inspect/`
- Read: `git status`、`git diff --stat`、`git diff --check`

**Interfaces:**
- Consumes: 全部迁移和验证结果。
- Produces: 不含临时克隆、缓存和旧结构的本地工作区，等待用户检查。

- [ ] **Step 1: 核验临时目录来源**

```powershell
git -C .remote-gitee-inspect log -1 --oneline
git -C .remote-gitee-inspect remote -v
```

Expected: 目录只指向 Gitee 仓库。

- [ ] **Step 2: 删除临时目录**

```powershell
Remove-Item -LiteralPath '.remote-gitee-inspect' -Recurse -Force
```

Expected: 临时目录不存在。

- [ ] **Step 3: 检查最终差异**

```powershell
git diff --check
git status --short --branch
git diff HEAD~1 --stat
```

Expected: 无 whitespace 错误；没有 `ca_mp/` 代码目录或临时文件。

- [ ] **Step 4: 创建本地交付提交**

```powershell
git add -A
git commit -m "merge: integrate Gitee flat layout with local updates"
```

Expected: 本地形成可供用户检查的最终提交，尚未推送 GitHub。

- [ ] **Step 5: 输出检查报告**

报告包含：目录摘要、本地增强、Gitee 独有内容、Markdown 更新范围、pytest 结果、SUMO 结果或限制、以及本地提交哈希。

---

### Task 10: 用户确认后覆盖 GitHub

**Files:**
- Read: 本地 `git status`、`git log`、远程 `github/main`
- Modify: GitHub `github/main`，仅在用户明确确认后

**Interfaces:**
- Consumes: Task 9 的本地交付提交和用户确认。
- Produces: GitHub `WuHuMeow/ChallengeCup:main` 与本地提交一致。

- [ ] **Step 1: 推送前再次核验**

```powershell
git status --short --branch
git rev-parse HEAD
git ls-remote --heads github main
```

Expected: 工作区干净；若远程哈希在用户检查期间变化，暂停并重新报告。

- [ ] **Step 2: 使用安全覆盖推送**

仅在用户明确确认后运行：

```powershell
git push --force-with-lease github HEAD:main
```

Expected: 推送成功，GitHub `main` 指向本地交付提交。

- [ ] **Step 3: 复核远程提交**

```powershell
git ls-remote --heads github main
```

Expected: 远程 `main` 哈希等于本地 `HEAD`。

- [ ] **Step 4: Commit**

本任务只改变远程引用，不创建新的本地提交。
