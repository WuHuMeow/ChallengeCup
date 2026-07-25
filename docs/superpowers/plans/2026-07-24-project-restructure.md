# Project Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate 9 top-level code modules into a `ca_mp/` package, clean up import hacks, simplify Docker, add `pyproject.toml`, and write 11 operational guides for the team.

**Architecture:** Move all Python source modules under a single `ca_mp/` namespace package via `git mv`, then batch-replace all import paths. Add `pyproject.toml` for editable install so imports work without cwd hacks. Docker simplifies from 9 COPY lines to 1. Documentation gets 11 new step-by-step guides in Chinese.

**Tech Stack:** Python 3.10+, git, pytest, Docker, pyproject.toml (setuptools)

## Global Constraints

- `data/` directory is untouched (competition raw materials)
- `docs/team/tasks/` historical documents keep old path references
- Each task produces an independent commit that can be rolled back alone
- All 66 tests must pass after Task 2
- Language: docs in Chinese, code/commands/paths in English

---

### Task 1: Move 9 modules into `ca_mp/` package

**Files:**
- Create: `ca_mp/__init__.py`
- Move: `algorithms/` → `ca_mp/algorithms/`
- Move: `api/` → `ca_mp/api/`
- Move: `cloud/` → `ca_mp/cloud/`
- Move: `core/` → `ca_mp/core/`
- Move: `engine/` → `ca_mp/engine/`
- Move: `experiments/` → `ca_mp/experiments/`
- Move: `ml/` → `ca_mp/ml/`
- Move: `scenes/` → `ca_mp/scenes/`
- Move: `visualization/` → `ca_mp/visualization/`

**Interfaces:**
- Produces: `ca_mp/` directory with all 9 sub-packages, each retaining their existing `__init__.py` and source files

- [ ] **Step 1: Create `ca_mp/` directory and `__init__.py`**

```bash
mkdir ca_mp
```

Create `ca_mp/__init__.py`:
```python
"""CA-MP: Capacity-Aware MaxPressure 信号控制平台。"""
```

- [ ] **Step 2: Move all 9 modules with `git mv`**

```bash
git mv algorithms ca_mp/algorithms
git mv api ca_mp/api
git mv cloud ca_mp/cloud
git mv core ca_mp/core
git mv engine ca_mp/engine
git mv experiments ca_mp/experiments
git mv ml ca_mp/ml
git mv scenes ca_mp/scenes
git mv visualization ca_mp/visualization
```

- [ ] **Step 3: Verify directory structure**

```bash
ls ca_mp/
```

Expected output (9 subdirectories + `__init__.py`):
```
__init__.py  algorithms  api  cloud  core  engine  experiments  ml  scenes  visualization
```

- [ ] **Step 4: Commit**

```bash
git add ca_mp/__init__.py
git commit -m "refactor: move 9 source modules into ca_mp/ package"
```

---

### Task 2: Replace all import paths and remove `sys.path` hacks

**Files:**
- Modify: 37 `.py` files across `ca_mp/`, `examples/`, `scripts/`, `tests/` (93 import replacements)
- Modify: `examples/run_demo.py` (remove sys.path hack)
- Modify: `examples/run_fixed_time.py` (remove sys.path hack)
- Modify: `examples/run_ca_max_pressure.py` (remove sys.path hack)
- Modify: `ca_mp/experiments/runner.py` (remove sys.path hack)
- Modify: `scripts/validation/stress_memory.py` (remove sys.path hack)
- Modify: `scripts/validation/check_seed_repro.py` (remove sys.path hack)

**Interfaces:**
- Consumes: `ca_mp/` package structure from Task 1
- Produces: All imports use `from ca_mp.<module>...` pattern; no `sys.path.insert` hacks remain

- [ ] **Step 1: Batch-replace imports in all `.py` files**

Run these replacements across the entire repo (excluding `data/`):

```bash
# Replace all 9 module prefixes in Python imports
find . -name "*.py" -not -path "./data/*" -not -path "./.venv/*" -exec sed -i \
  -e 's/from algorithms\./from ca_mp.algorithms./g' \
  -e 's/from api\./from ca_mp.api./g' \
  -e 's/from cloud\./from ca_mp.cloud./g' \
  -e 's/from core\./from ca_mp.core./g' \
  -e 's/from engine\./from ca_mp.engine./g' \
  -e 's/from experiments\./from ca_mp.experiments./g' \
  -e 's/from ml\./from ca_mp.ml./g' \
  -e 's/from scenes\./from ca_mp.scenes./g' \
  -e 's/from visualization\./from ca_mp.visualization./g' \
  {} +
```

On Windows (Git Bash), use:
```bash
git grep -l "from \(algorithms\|api\|cloud\|core\|engine\|experiments\|ml\|scenes\|visualization\)\." -- "*.py" ":!data/" | xargs sed -i \
  -e 's/from algorithms\./from ca_mp.algorithms./g' \
  -e 's/from api\./from ca_mp.api./g' \
  -e 's/from cloud\./from ca_mp.cloud./g' \
  -e 's/from core\./from ca_mp.core./g' \
  -e 's/from engine\./from ca_mp.engine./g' \
  -e 's/from experiments\./from ca_mp.experiments./g' \
  -e 's/from ml\./from ca_mp.ml./g' \
  -e 's/from scenes\./from ca_mp.scenes./g' \
  -e 's/from visualization\./from ca_mp.visualization./g'
```

- [ ] **Step 2: Remove `sys.path.insert` hack from `examples/run_demo.py`**

Remove line 19:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

Also remove the now-unused `Path` import if no other usage remains in the file. Keep `from pathlib import Path` only if used elsewhere.

- [ ] **Step 3: Remove `sys.path.insert` hack from `examples/run_fixed_time.py`**

Remove lines 15-16:
```python
# 兼容直接运行示例脚本
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

Remove unused `Path` import if applicable.

- [ ] **Step 4: Remove `sys.path.insert` hack from `examples/run_ca_max_pressure.py`**

Remove lines 12-13:
```python
# 兼容直接运行示例脚本
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

Remove unused `Path` import if applicable.

- [ ] **Step 5: Remove `sys.path.insert` hack from `ca_mp/experiments/runner.py`**

Remove line 16:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

Also remove the `# noqa: E402` comments from the imports that follow (lines 18-26), since they were only needed because imports came after `sys.path` manipulation:
```python
from ca_mp.algorithms.base import BaseControlAlgorithm
from ca_mp.algorithms.fixed_time import FixedTimeAlgorithm
from ca_mp.algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from ca_mp.algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from ca_mp.core.config import get_config
from ca_mp.core.types import TrafficLevel
from ca_mp.engine.runner import SimulationRunner
from ca_mp.scenes.registry import SceneRegistry
from ca_mp.scenes.variant import VariantGenerator
```

Remove unused `Path` import if applicable.

- [ ] **Step 6: Remove `sys.path.insert` hack from `scripts/validation/stress_memory.py`**

Remove lines 10-11:
```python
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
```

Replace with just:
```python
ROOT = Path(__file__).resolve().parents[2]
```

(Keep `ROOT` — it's used for `output_dir` path construction.)

- [ ] **Step 7: Remove `sys.path.insert` hack from `scripts/validation/check_seed_repro.py`**

Remove lines 6-7:
```python
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
```

Replace with just:
```python
ROOT = Path(__file__).resolve().parents[2]
```

(Keep `ROOT` — it's used for output path.)

- [ ] **Step 8: Verify no old-style imports remain**

```bash
git grep -n "from \(algorithms\|api\|cloud\|core\|engine\|experiments\|ml\|scenes\|visualization\)\." -- "*.py" ":!data/"
```

Expected: no output (zero matches).

- [ ] **Step 9: Verify no `sys.path.insert` remains in project code**

```bash
git grep -n "sys.path.insert" -- "*.py" ":!data/"
```

Expected: no output. (The `sys.path.append` in `ca_mp/engine/traci_bridge.py` for SUMO_HOME is intentional and stays.)

- [ ] **Step 10: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: 66 tests pass.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "refactor: update all imports to ca_mp.* and remove sys.path hacks"
```

---

### Task 3: Update scripts, config, and `generate_configs.py` paths

**Files:**
- Modify: `scripts/simulation/generate_configs.py` (output path `engine/configs` → `ca_mp/engine/configs`)
- Modify: `scripts/validation/batch_validate.py` (config dir path)
- Modify: `scripts/quality/lint_check.sh` (lint target dirs)
- Modify: `config/default.yaml` (model_path reference)

**Interfaces:**
- Consumes: `ca_mp/` package from Tasks 1-2
- Produces: All scripts reference correct `ca_mp/` paths

- [ ] **Step 1: Update `scripts/simulation/generate_configs.py`**

Change line 19:
```python
OUT_DIR = ROOT / "engine" / "configs"
```
to:
```python
OUT_DIR = ROOT / "ca_mp" / "engine" / "configs"
```

Also update the relative path in the TEMPLATE (line 69-70). The sumocfg files now live at `ca_mp/engine/configs/`, so the relative path to data needs one more `../`:
```python
net=f"../../../data/intersection_data/{n}/sumo工程/demo_{n}.net.xml",
rou=f"../../../data/intersection_data/{n}/sumo工程/demo_{n}.rou.xml",
```

- [ ] **Step 2: Update `scripts/validation/batch_validate.py`**

Change line 23:
```python
CFG_DIR = ROOT / "engine" / "configs"
```
to:
```python
CFG_DIR = ROOT / "ca_mp" / "engine" / "configs"
```

- [ ] **Step 3: Update `scripts/quality/lint_check.sh`**

Change line 16 (the `git grep` target dirs):
```bash
if matches=$(git grep --no-index --exclude-standard -nE "$pattern" -- engine cloud experiments); then
```
to:
```bash
if matches=$(git grep --no-index --exclude-standard -nE "$pattern" -- ca_mp/engine ca_mp/cloud ca_mp/experiments); then
```

Change line 29 (flake8 target):
```bash
python -m flake8 engine/ cloud/ experiments/ --max-line-length=100
```
to:
```bash
python -m flake8 ca_mp/engine/ ca_mp/cloud/ ca_mp/experiments/ --max-line-length=100
```

- [ ] **Step 4: Update `config/default.yaml`**

Change line 12:
```yaml
  model_path: "./ml/model.pkl"
```
to:
```yaml
  model_path: "./ca_mp/ml/model.pkl"
```

- [ ] **Step 5: Verify `generate_configs.py` runs**

```bash
python scripts/simulation/generate_configs.py
```

Expected: "已生成 20 个增强版配置到 .../ca_mp/engine/configs"

- [ ] **Step 6: Run tests again**

```bash
python -m pytest tests/ -v
```

Expected: 66 tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: update script and config paths for ca_mp/ layout"
```

---

### Task 4: Update Docker files

**Files:**
- Modify: `docker/Dockerfile`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: `ca_mp/` package from Tasks 1-3
- Produces: Docker image builds and runs with new layout

- [ ] **Step 1: Rewrite `docker/Dockerfile` COPY section**

Replace lines 23-35:
```dockerfile
COPY core/ ./core/
COPY algorithms/ ./algorithms/
COPY engine/ ./engine/
COPY cloud/ ./cloud/
COPY ml/ ./ml/
COPY scenes/ ./scenes/
COPY experiments/ ./experiments/
COPY api/ ./api/
COPY visualization/ ./visualization/
COPY config/ ./config/
COPY examples/ ./examples/
COPY scripts/ ./scripts/
COPY data/intersection_data/ ./data/intersection_data/
```

With:
```dockerfile
COPY ca_mp/ ./ca_mp/
COPY config/ ./config/
COPY examples/ ./examples/
COPY scripts/ ./scripts/
COPY data/intersection_data/ ./data/intersection_data/
```

- [ ] **Step 2: Update `docker-compose.yml` volume mount**

Replace:
```yaml
    volumes:
      - ./output:/app/output
      - ./experiments/results:/app/experiments/results
```

With:
```yaml
    volumes:
      - ./output:/app/output
```

(The `experiments/results` directory no longer exists at top level; results go to `output/`.)

- [ ] **Step 3: Verify Docker build (if Docker available)**

```bash
docker compose build
```

Expected: build succeeds. (Skip if Docker not installed on this machine.)

- [ ] **Step 4: Commit**

```bash
git add docker/Dockerfile docker-compose.yml
git commit -m "refactor: simplify Docker for ca_mp/ package layout"
```

---

### Task 5: Add `pyproject.toml` and verify editable install

**Files:**
- Create: `pyproject.toml`
- Modify: `.gitignore` (add `*.egg-info/`)

**Interfaces:**
- Consumes: `ca_mp/` package from Tasks 1-4
- Produces: `pip install -e .` works; imports resolve without cwd dependency

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "ca-mp"
version = "1.0.0"
description = "Capacity-Aware MaxPressure 信号控制平台"
requires-python = ">=3.10"
dependencies = []

[tool.setuptools.packages.find]
include = ["ca_mp*"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Add `*.egg-info/` to `.gitignore`**

Append to `.gitignore`:
```
# Editable install metadata
*.egg-info/
```

- [ ] **Step 3: Install in editable mode**

```bash
pip install -e .
```

Expected: "Successfully installed ca-mp-1.0.0"

- [ ] **Step 4: Verify import from arbitrary directory**

```bash
cd /tmp && python -c "from ca_mp.core.types import JointState; print('OK')" && cd -
```

Expected: `OK`

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/ -v
```

Expected: 66 tests pass.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "feat: add pyproject.toml for editable install"
```

---

### Task 6: Update `.gitignore` for new layout

**Files:**
- Modify: `.gitignore`

**Interfaces:**
- Consumes: new `ca_mp/` layout
- Produces: gitignore patterns match new paths

- [ ] **Step 1: Update experiment results pattern**

Change:
```
experiments/results/
```
to:
```
# (removed — results now go to output/)
```

The `output/*` pattern already covers all runtime outputs.

- [ ] **Step 2: Verify git status is clean**

```bash
git status
```

Expected: no unexpected untracked files.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: update .gitignore for ca_mp/ layout"
```

---

### Task 7: Write operational guides (01-06)

**Files:**
- Create: `docs/guides/01-algorithm-config.md`
- Create: `docs/guides/02-import-intersection.md`
- Create: `docs/guides/03-run-simulation.md`
- Create: `docs/guides/04-batch-experiments.md`
- Create: `docs/guides/05-cloud-coordinator.md`
- Create: `docs/guides/06-generate-configs.md`

**Interfaces:**
- Consumes: final `ca_mp/` layout, `config/default.yaml`, `scripts/`, `examples/`
- Produces: 6 Chinese operational guides following the template: 目的 → 前置条件 → 操作步骤 → 示例 → 常见问题

- [ ] **Step 1: Create `docs/guides/01-algorithm-config.md`**

```markdown
# 如何配置算法参数

## 目的

修改信号控制算法的运行参数（绿灯时长、阈值、EWMA 系数等），无需改动代码。

## 前置条件

- 已安装项目依赖：`pip install -e .`
- 了解 YAML 基本语法

## 操作步骤

1. 打开 `config/default.yaml`
2. 定位 `algorithms` 节：

```yaml
algorithms:
  fixed_time:
    use_excel_timing: false    # true=从Excel读配时; false=用SUMO默认

  actuated:
    min_green: 10              # 最小绿灯（秒）
    max_green: 60              # 最大绿灯（秒）
    queue_threshold: 5         # 排队检测阈值（辆）

  ca_maxpressure:
    overflow_occupancy_threshold: 0.9  # 溢出门控触发阈值
    base_green: 30             # 基础绿灯时长（秒）
    min_green: 10
    max_green: 90
    ewma_alpha: 0.3            # EWMA 平滑系数（0~1，越大越敏感）
    prediction_horizon: 300    # 云端预测时域（秒）
    cloud_update_interval: 600 # 云端下发间隔（仿真步，600步=60秒）
```

3. 修改目标参数值
4. 保存文件，重新运行仿真即可生效

## 示例

将 CA-MP 的溢出门控阈值从 0.9 调低到 0.8（更积极地触发门控）：

```yaml
  ca_maxpressure:
    overflow_occupancy_threshold: 0.8
```

运行验证：
```bash
python examples/run_ca_max_pressure.py 16 3600
```

## 常见问题

**Q: 修改后没效果？**
A: 确认修改的是 `config/default.yaml`，不是 `config/` 下其他文件。也可通过环境变量 `CC_DATA_ROOT` 覆盖数据路径，但算法参数只从此文件读取。

**Q: 参数含义不确定？**
A: 参见 `docs/architecture/interface.md` 中 CloudPolicy.dispatch_params 小节的分档表。
```

- [ ] **Step 2: Create `docs/guides/02-import-intersection.md`**

```markdown
# 如何导入新路口数据

## 目的

将组委会下发的新路口 SUMO 工程导入项目，使其可被仿真引擎识别和运行。

## 前置条件

- 拥有新路口数据文件夹（含 `.net.xml`、`.rou.xml`、`.sumocfg`、配时 Excel）
- 已安装项目依赖：`pip install -e .`

## 操作步骤

1. 在 `data/intersection_data/` 下创建编号目录（如 `21/`）：

```
data/intersection_data/21/
├── sumo工程/
│   ├── demo_21.net.xml
│   ├── demo_21.rou.xml
│   ├── demo_21.flow.xml      # 可选
│   ├── demo_21.turn.xml      # 可选
│   └── demo_21.sumocfg
├── 路口数据/
│   └── demo_21流量和交叉口配时方案.xlsx
└── 高精地图/
    └── demo_21.png           # 可选
```

2. 确保文件命名遵循 `demo_N.*` 格式（N = 路口编号）

3. 运行元数据提取脚本：
```bash
python scripts/data/extract_metadata.py
```
这会更新 `data/intersection_data/metadata/intersections.yaml`。

4. 生成边方向映射：
```bash
python scripts/data/generate_edge_mapping.py
```
这会更新 `data/intersection_data/metadata/edge_mapping.json` 和 `docs/reference/edge-mapping.md`。

5. 生成增强版仿真配置：
```bash
python scripts/simulation/generate_configs.py
```
这会在 `ca_mp/engine/configs/` 下生成 `demo_21.sumocfg`。

6. 验证新路口可运行：
```bash
python scripts/validation/validate_all.py 21
```

## 示例

导入路口 21 后运行 CA-MP 仿真：
```bash
python examples/run_ca_max_pressure.py 21 3600
```

## 常见问题

**Q: 目录名必须是 `高精地图` 吗？**
A: 是的。路口 11 使用了 `高清地图`（历史原因），代码中有兼容处理（`ca_mp/scenes/registry.py`），但新路口请统一用 `高精地图`。

**Q: 没有 Excel 配时文件怎么办？**
A: 可以没有。`config/default.yaml` 中 `use_excel_timing: false` 时使用 SUMO 路网自带配时。

**Q: validate 报 FAIL？**
A: 检查 `.net.xml` 的 SUMO 版本兼容性（需 net format ≥ 1.20），参见 `docs/reports/sumo-migration-log.md`。
```

- [ ] **Step 3: Create `docs/guides/03-run-simulation.md`**

```markdown
# 如何运行单路口仿真

## 目的

对指定路口运行一次完整仿真，验证算法效果或调试问题。

## 前置条件

- 已安装 SUMO 并设置 `SUMO_HOME` 环境变量（参见 `docs/operations/sumo-environment-setup.md`）
- 已安装项目依赖：`pip install -e .`
- 或：不安装 SUMO，使用 Mock 模式验证调用链

## 操作步骤

### 方式一：Mock 模式（无需 SUMO）

```bash
python examples/run_demo.py [路口编号] [算法名]
```

示例：
```bash
python examples/run_demo.py 16 ca_maxpressure
```

输出 6 步链路验证结果，10 步仿真指标。

### 方式二：真实 SUMO 仿真

```bash
python examples/run_fixed_time.py [路口编号]        # 固定配时基线
python examples/run_ca_max_pressure.py [路口编号] [步数]  # CA-MP 算法
```

示例：
```bash
python examples/run_fixed_time.py 1
python examples/run_ca_max_pressure.py 16 36000
```

### 方式三：通用入口（支持所有算法）

```bash
python examples/run_demo.py [路口编号] [算法名] --sumo
```

算法名可选：`fixed_time`、`actuated`、`ca_maxpressure`

## 示例

运行路口 16（24m 短边，CA-MP 效果最显著）：
```bash
python examples/run_ca_max_pressure.py 16 36000
```

输出：
```
运行路口 16: demo_16 (CA-MP)
仿真完成，共记录 60 条指标快照
CSV 输出: output/csv/16_ca_maxpressure.csv
```

## 常见问题

**Q: 报错 "traci 未安装"？**
A: 执行 `pip install traci sumolib`，或确认 `SUMO_HOME/tools` 在 Python 路径中。

**Q: 仿真步数怎么换算成秒？**
A: 步长 = 0.1s（路口 11-13、15-20）或 1.0s（路口 1-10）。36000 步 = 3600 秒（1 小时）或 36000 秒。具体看 `ca_mp/engine/configs/demo_N.sumocfg` 中的 `step-length`。

**Q: 输出 CSV 在哪？**
A: 默认在 `output/csv/` 目录下，文件名格式 `{路口}_{算法}.csv`。
```

- [ ] **Step 4: Create `docs/guides/04-batch-experiments.md`**

```markdown
# 如何跑批量实验（360 组）

## 目的

运行完整实验矩阵（20 路口 × 3 算法 × 2 流量等级 × 3 种子 = 360 次仿真），生成对比数据。

## 前置条件

- 已安装 SUMO 并设置 `SUMO_HOME`
- 已安装项目依赖：`pip install -e .`
- 预估时间：约 6-10 小时（取决于机器性能）

## 操作步骤

### 单次实验（CLI）

```bash
python -m ca_mp.experiments.runner \
  --intersection 16 \
  --algorithm ca_maxpressure \
  --flow-multiplier 1.5 \
  --seed 42 \
  --steps 36000 \
  --output-dir output/exp1
```

参数说明：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--intersection` | 1 | 路口编号 1-20 |
| `--algorithm` | fixed_time | fixed_time / actuated / ca_maxpressure |
| `--flow-multiplier` | 1.0 | 流量倍率（1.5=压力测试） |
| `--seed` | 42 | 随机种子（保证可复现） |
| `--steps` | 36000 | 仿真步数 |
| `--output-dir` | config 中 paths.output_root | 输出根目录 |

### 批量实验（Python API）

```python
from ca_mp.experiments.runner import run_batch

results = run_batch(
    intersection_ids=["1", "16"],       # None=全部20个
    algorithms=["fixed_time", "ca_maxpressure"],  # None=全部3种
    seeds=[42, 123, 456],
    steps=36000,
)
print(f"完成 {len(results)} 次实验")
```

### 使用任务拆分脚本（双机并行）

```bash
python scripts/simulation/split_jobs.py           # 查看任务分配
python scripts/simulation/split_jobs.py --machine a  # A 机任务清单
python scripts/simulation/split_jobs.py --machine b  # B 机任务清单
```

## 示例

只跑路口 16 的 3 种算法对比（快速验证）：
```python
from ca_mp.experiments.runner import run_batch
results = run_batch(intersection_ids=["16"], steps=3600)
```

## 常见问题

**Q: 跑到一半中断了怎么办？**
A: 已完成的 CSV 不受影响。重新运行时跳过已有输出文件即可（手动检查 `output/csv/` 目录）。

**Q: 输出文件命名规则？**
A: `{路口}_x{倍率}_{算法}_s{种子}.csv`，如 `16_x1.5_ca_maxpressure_s42.csv`。

**Q: 内存不够？**
A: 用 `python scripts/validation/stress_memory.py 16 36000` 测试峰值。Python 侧峰值应 < 1GB。
```

- [ ] **Step 5: Create `docs/guides/05-cloud-coordinator.md`**

```markdown
# 如何配置云端协调器

## 目的

调整 CloudCoordinator（EWMA 流量预测 + 动态参数下发）的行为参数。

## 前置条件

- 了解 CA-MP 算法的云端协同机制（参见 `docs/architecture/interface.md`）
- 已安装项目依赖：`pip install -e .`

## 操作步骤

1. 打开 `config/default.yaml`，定位 `algorithms.ca_maxpressure` 节：

```yaml
  ca_maxpressure:
    ewma_alpha: 0.3            # EWMA 平滑系数
    prediction_horizon: 300    # 预测时域（秒）
    cloud_update_interval: 600 # 下发间隔（仿真步）
```

2. 调整参数：
   - `ewma_alpha`：0~1，越大对新流量越敏感（推荐 0.2~0.5）
   - `prediction_horizon`：预测未来多少秒的流量
   - `cloud_update_interval`：多少步下发一次参数（600步 = 60仿真秒）

3. 云端分档逻辑（代码位于 `ca_mp/cloud/cloud_policy.py`）：

| 全局平均压力 | min_green | max_green | base_green |
|-------------|-----------|-----------|------------|
| > 0.8（极高） | 20 | 120 | 45 |
| > 0.4（中档） | 15 | 90 | 35 |
| ≤ 0.4（常规） | 10 | 90 | 30 |

如需修改分档阈值，编辑 `ca_mp/cloud/cloud_policy.py` 中的 `PRESSURE_TIERS`。

## 示例

让云端更频繁地下发参数（每 30 秒一次）：
```yaml
    cloud_update_interval: 300  # 300步 = 30秒
```

## 常见问题

**Q: 云端协调器是独立进程吗？**
A: 不是。当前实现是单进程内模拟云-边-端协同，CloudPolicy 作为对象注入到 CA-MP 算法中。

**Q: 不用云端协调器可以吗？**
A: 可以。CA-MP 算法在 CloudPolicy 未注入时使用 `config/default.yaml` 中的静态 `base_green` 值。
```

- [ ] **Step 6: Create `docs/guides/06-generate-configs.md`**

```markdown
# 如何生成仿真配置文件

## 目的

从 20 个路口的原始 `.sumocfg` 生成增强版配置（统一输出格式、步长、容错参数）。

## 前置条件

- 已安装项目依赖：`pip install -e .`
- `data/intersection_data/{1..20}/sumo工程/demo_N.sumocfg` 存在

## 操作步骤

```bash
python scripts/simulation/generate_configs.py
```

输出：`ca_mp/engine/configs/demo_{1..20}.sumocfg`（覆盖已有文件）

## 生成规则

增强版配置相比原始配置的改动：

| 项目 | 原始 | 增强版 |
|------|------|--------|
| step-length | 不统一 | 统一 0.1s |
| tripinfo-output | 部分有 | 全部有 |
| fcd-output (traj) | 无 | 全部有 |
| summary-output (stats) | 无 | 全部有 |
| queue-output | 部分有 | 保留原有的（路口 11-13、15-20） |
| ignore-route-errors | 部分有 | 保留原有的 |
| 数据引用 | 本地相对路径 | 指向 `data/intersection_data/` 的相对路径 |

## 示例

生成后验证配置有效性：
```bash
python scripts/validation/batch_validate.py 1 16
```

## 常见问题

**Q: 修改了原始数据后需要重新生成吗？**
A: 是的。每次修改 `data/intersection_data/` 中的原始 `.sumocfg` 后都应重新运行此脚本。

**Q: 生成的配置能直接用 sumo-gui 打开吗？**
A: 可以。配置中包含 `<gui_only>` 节（自动播放、80ms 延迟），命令行 `sumo` 会忽略此节。
```

- [ ] **Step 7: Commit**

```bash
git add docs/guides/01-algorithm-config.md docs/guides/02-import-intersection.md \
  docs/guides/03-run-simulation.md docs/guides/04-batch-experiments.md \
  docs/guides/05-cloud-coordinator.md docs/guides/06-generate-configs.md
git commit -m "docs: add operational guides 01-06"
```

---

### Task 8: Write operational guides (07-11)

**Files:**
- Create: `docs/guides/07-view-results.md`
- Create: `docs/guides/08-visualization.md`
- Create: `docs/guides/09-docker-deploy.md`
- Create: `docs/guides/10-testing.md`
- Create: `docs/guides/11-new-algorithm.md`

**Interfaces:**
- Consumes: final `ca_mp/` layout, `output/` structure, `visualization/`, `docker/`, `tests/`
- Produces: 5 Chinese operational guides

- [ ] **Step 1: Create `docs/guides/07-view-results.md`**

```markdown
# 如何查看/导出结果

## 目的

找到仿真输出文件，理解 CSV 字段含义，提取关键指标用于报告。

## 前置条件

- 已运行过至少一次仿真（参见指南 03 或 04）

## 操作步骤

### 输出目录结构

```
output/
├── csv/          # 指标快照（每 snapshot_interval 步一行）
├── logs/         # 每步日志 + 事件日志
└── variants/     # 流量变体 XML（flow_multiplier != 1.0 时生成）
```

### 指标快照 CSV 字段

文件：`output/csv/{路口}_{算法}.csv` 或 `{路口}_x{倍率}_{算法}_s{种子}.csv`

| 列名 | 含义 | 单位 |
|------|------|------|
| step | 采集步编号 | 步 |
| timestamp | 仿真时间 | 秒 |
| avg_queue_length | 平均排队长度 | 米 |
| max_queue_length | 最大排队长度 | 米 |
| avg_delay | 平均延误 | 秒/辆 |
| total_throughput | 累计通过车辆数 | 辆 |
| avg_travel_time | 平均行程时间 | 秒 |
| total_stops | 累计停车次数 | 次 |
| fuel_consumption | 累计油耗 | mL |
| queue_{方向} | 各进口道排队 | 米 |
| flow_{方向} | 各进口道流量 | 辆/小时 |

### 用 pandas 快速分析

```python
import pandas as pd

df = pd.read_csv("output/csv/16_ca_maxpressure.csv")
print(df[["avg_queue_length", "avg_delay", "total_throughput"]].describe())
```

## 常见问题

**Q: CSV 文件被 .gitignore 忽略了？**
A: 是的，`*.csv` 在 `.gitignore` 中。结果文件不提交到仓库，需要时重新运行生成。

**Q: 快照间隔太大/太小？**
A: 修改 `config/default.yaml` 中 `metrics.snapshot_interval`（默认 600 步 = 60 秒一行）。
```

- [ ] **Step 2: Create `docs/guides/08-visualization.md`**

```markdown
# 如何生成可视化图表

## 目的

使用 `ca_mp.visualization` 模块从仿真结果 CSV 生成对比图表。

## 前置条件

- 已安装项目依赖：`pip install -e .`（含 matplotlib、seaborn）
- 已有仿真结果 CSV（参见指南 03/04/07）

## 操作步骤

```python
from ca_mp.visualization.plots import plot_comparison

# 对比多算法的排队长度时序
plot_comparison(
    csv_paths=[
        "output/csv/16_fixed_time.csv",
        "output/csv/16_ca_maxpressure.csv",
    ],
    metric="avg_queue_length",
    title="路口 16 排队长度对比",
    output_path="output/figures/queue_comparison.png",
)
```

### 可用图表函数

查看 `ca_mp/visualization/plots.py` 中的公开函数。典型用法：

```python
import matplotlib.pyplot as plt
from ca_mp.visualization import plots

# 具体函数签名见模块 README：ca_mp/visualization/README.md
```

## 示例

生成完整对比图后保存：
```bash
python -c "
from ca_mp.visualization.plots import plot_comparison
plot_comparison(
    csv_paths=['output/csv/16_fixed_time.csv', 'output/csv/16_ca_maxpressure.csv'],
    metric='avg_delay',
    output_path='output/figures/delay_16.png'
)
"
```

## 常见问题

**Q: 中文显示为方块？**
A: matplotlib 默认不支持中文。在脚本开头加：
```python
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False
```

**Q: 图片保存在哪？**
A: 建议保存到 `output/figures/`（已被 .gitignore 覆盖）。交付用图手动复制到 `output/deliverables/`。
```

- [ ] **Step 3: Create `docs/guides/09-docker-deploy.md`**

```markdown
# Docker 部署与运行

## 目的

在无本地 SUMO 环境的机器上通过 Docker 运行仿真。

## 前置条件

- 已安装 Docker 和 Docker Compose
- 仓库已克隆到本地

## 操作步骤

### 构建镜像

```bash
docker compose build
```

镜像基于 Ubuntu 22.04 + SUMO（ppa:sumo/stable），包含所有 Python 依赖。

### 运行默认仿真（路口 16，固定配时）

```bash
docker compose up
```

### 指定路口

```bash
docker compose run --rm simulation 1
docker compose run --rm simulation 16
```

### 直接用 docker run

```bash
docker run ca-mp:latest 16
```

### 查看输出

仿真结果写入容器内 `/app/output/`，通过 volume 映射到宿主机 `./output/`：
```bash
ls output/csv/
```

## 示例

完整流程：
```bash
docker compose build
docker compose run --rm simulation 16
cat output/csv/16_fixed_time.csv | head -5
```

## 常见问题

**Q: 构建很慢？**
A: 首次构建需下载 SUMO PPA 包（约 500MB）。后续构建有缓存，只复制代码层。

**Q: 想跑 CA-MP 而不是固定配时？**
A: 当前 ENTRYPOINT 是 `examples/run_fixed_time.py`。CA-MP 需要修改 command 或进入容器：
```bash
docker compose run --rm simulation bash
python examples/run_ca_max_pressure.py 16
```

**Q: Windows 下路径问题？**
A: 确保使用 Docker Desktop for Windows，volume 映射使用正斜杠。
```

- [ ] **Step 4: Create `docs/guides/10-testing.md`**

```markdown
# 如何跑测试 / 代码质量检查

## 目的

验证代码修改没有破坏现有功能，保持代码质量。

## 前置条件

- 已安装项目依赖：`pip install -e .`
- 已安装 pytest：`pip install pytest`

## 操作步骤

### 运行全部测试

```bash
python -m pytest tests/ -v
```

预期：66 个测试全部通过。

### 只跑单元测试

```bash
python -m pytest tests/unit/ -v
```

### 只跑集成测试

```bash
python -m pytest tests/integration/ -v
```

### 跑单个测试文件

```bash
python -m pytest tests/unit/test_algorithms.py -v
```

### 代码质量检查（lint）

```bash
bash scripts/quality/lint_check.sh
```

检查内容：
- flake8 静态分析（`ca_mp/engine/`、`ca_mp/cloud/`、`ca_mp/experiments/`）
- 调试代码残留（`breakpoint()`、`pdb.set_trace`）
- TODO/FIXME 标记

输出 `clean` 表示通过。

## 示例

修改了 CA-MP 算法后验证：
```bash
python -m pytest tests/unit/test_algorithms.py tests/unit/test_cloud.py -v
bash scripts/quality/lint_check.sh
```

## 常见问题

**Q: 测试报 ImportError？**
A: 确认已执行 `pip install -e .`，使 `ca_mp` 包可导入。

**Q: 集成测试需要 SUMO 吗？**
A: 大部分集成测试使用 MockBridge，不需要 SUMO。标注了 `@pytest.mark.sumo` 的测试需要真实 SUMO。

**Q: 新增了模块，lint 没覆盖到？**
A: `lint_check.sh` 目前只检查 `ca_mp/engine/`、`ca_mp/cloud/`、`ca_mp/experiments/`。如需扩展，编辑该脚本。
```

- [ ] **Step 5: Create `docs/guides/11-new-algorithm.md`**

```markdown
# 如何实现新算法

## 目的

添加一个新的信号控制算法（如改进版 Actuated、强化学习基线等），使其可被实验框架调度。

## 前置条件

- 了解算法标准接口（参见 `docs/architecture/interface.md`）
- 已安装项目依赖：`pip install -e .`

## 操作步骤

### 1. 创建算法文件

在 `ca_mp/algorithms/` 下新建文件，如 `my_algorithm.py`：

```python
from typing import List

from ca_mp.algorithms.base import BaseControlAlgorithm
from ca_mp.core.types import ControlAction, JointState, Scene


class MyAlgorithm(BaseControlAlgorithm):
    def init(self, scene: Scene) -> None:
        self.tls_id = f"J{scene.meta.intersection_id}"

    def step(self, state: JointState) -> List[ControlAction]:
        if state.elapsed_phase_time >= 30.0:
            next_phase = (state.current_phase + 1) % 4
            return [ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=next_phase,
                reason="定时切换",
            )]
        return []

    def reset(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "my_algorithm"
```

### 2. 注册到实验框架

编辑 `ca_mp/experiments/runner.py`，在 `ALGORITHM_MAP` 中添加：

```python
from ca_mp.algorithms.my_algorithm import MyAlgorithm

ALGORITHM_MAP: Dict[str, type[BaseControlAlgorithm]] = {
    "fixed_time": FixedTimeAlgorithm,
    "actuated": RuleAdaptiveAlgorithm,
    "ca_maxpressure": CAMaxPressureAlgorithm,
    "my_algorithm": MyAlgorithm,  # 新增
}
```

### 3. 测试

```bash
# 快速验证
python examples/run_demo.py 1 my_algorithm

# 真实仿真
python examples/run_demo.py 16 my_algorithm --sumo

# CLI 实验入口
python -m ca_mp.experiments.runner --intersection 16 --algorithm my_algorithm --steps 3600
```

### 4. 写单元测试

在 `tests/unit/` 下新建或扩展测试文件：

```python
from ca_mp.algorithms.my_algorithm import MyAlgorithm
from ca_mp.core.types import JointState, Scene

def test_my_algorithm_returns_action():
    algo = MyAlgorithm()
    # 构造 mock state，验证 step() 返回预期 ControlAction
    ...
```

运行：
```bash
python -m pytest tests/unit/ -v -k "my_algorithm"
```

## 接口约束

- `step()` 必须是纯决策，不要在里面启动 SUMO 或写文件
- 返回的 `ControlAction` 由引擎负责写入 SUMO
- 返回空列表 `[]` = 本步不干预
- `reset()` 必须清空所有内部状态

## 常见问题

**Q: 需要云端预测数据怎么办？**
A: 通过构造函数注入 CloudPolicy 对象，在 `step()` 中调用 `self.cloud_policy.predict(state)`。参见 `ca_mp/algorithms/ca_max_pressure.py` 的实现。

**Q: 需要读取路口拓扑（车道数、长度）？**
A: 在 `init(scene)` 中通过 `scene.meta.sumo_net` 获取路网文件路径，用 `sumolib` 解析。
```

- [ ] **Step 6: Commit**

```bash
git add docs/guides/07-view-results.md docs/guides/08-visualization.md \
  docs/guides/09-docker-deploy.md docs/guides/10-testing.md docs/guides/11-new-algorithm.md
git commit -m "docs: add operational guides 07-11"
```

---

### Task 9: Update existing docs and module READMEs

**Files:**
- Modify: `docs/architecture/interface.md` (update all path references)
- Modify: `docs/README.md` (update index)
- Modify: `docs/guides/README.md` (add 11 new guides to index)
- Delete: `docs/guides/markdown-guide.md`
- Create: `docs/operations/README.md`
- Create: `docs/reports/README.md`
- Create: `docs/reference/README.md`
- Create: `docs/notes/README.md`
- Modify: `ca_mp/algorithms/README.md` (update import paths)
- Modify: `ca_mp/engine/README.md` (update import paths)
- Modify: `ca_mp/cloud/README.md` (update import paths)
- Modify: `ca_mp/core/README.md` (update import paths)
- Modify: `ca_mp/scenes/README.md` (update import paths)
- Modify: `ca_mp/experiments/README.md` (update import paths)
- Modify: `ca_mp/api/README.md` (update import paths)
- Modify: `ca_mp/ml/README.md` (update import paths)
- Modify: `ca_mp/visualization/README.md` (update import paths)
- Modify: `scripts/README.md` (update paths)

**Interfaces:**
- Consumes: final `ca_mp/` layout, guides from Tasks 7-8
- Produces: all active documentation reflects new structure

- [ ] **Step 1: Update `docs/architecture/interface.md`**

Replace all bare module path references with `ca_mp/` prefixed paths:
- `algorithms/base.py` → `ca_mp/algorithms/base.py`
- `core/types.py` → `ca_mp/core/types.py`
- `engine/traci_bridge.py` → `ca_mp/engine/traci_bridge.py`
- `engine/runner.py` → `ca_mp/engine/runner.py`
- `engine/edge_channel.py` → `ca_mp/engine/edge_channel.py`
- `cloud/cloud_policy.py` → `ca_mp/cloud/cloud_policy.py`
- `scenes/registry.py` → `ca_mp/scenes/registry.py`
- `scenes/timing_loader.py` → `ca_mp/scenes/timing_loader.py`
- `scenes/variant.py` → `ca_mp/scenes/variant.py`
- `experiments/runner.py` → `ca_mp/experiments/runner.py`
- `experiments/metrics.py` → `ca_mp/experiments/metrics.py`

Also update code examples:
- `from algorithms.base import ...` → `from ca_mp.algorithms.base import ...`
- `from core.types import ...` → `from ca_mp.core.types import ...`
- `from engine.edge_channel import ...` → `from ca_mp.engine.edge_channel import ...`
- `from algorithms.ca_max_pressure import ...` → `from ca_mp.algorithms.ca_max_pressure import ...`
- `from engine.runner import ...` → `from ca_mp.engine.runner import ...`
- `from scenes.registry import ...` → `from ca_mp.scenes.registry import ...`
- `from experiments.runner import ...` → `from ca_mp.experiments.runner import ...`

Update CLI example:
```bash
python -m ca_mp.experiments.runner --intersection 1 --algorithm ca_maxpressure \
    --flow-multiplier 1.5 --seed 42 --steps 3600 --output-dir output/exp1
```

- [ ] **Step 2: Delete `docs/guides/markdown-guide.md`**

```bash
git rm docs/guides/markdown-guide.md
```

- [ ] **Step 3: Update `docs/guides/README.md`**

Rewrite to index all guides including the 11 new ones:

```markdown
# 操作指南索引

面向团队成员的 step-by-step 操作手册。每篇遵循：目的 → 前置条件 → 操作步骤 → 示例 → 常见问题。

## 指南列表

| 编号 | 文件 | 内容 |
|------|------|------|
| 01 | [01-algorithm-config.md](01-algorithm-config.md) | 如何配置算法参数 |
| 02 | [02-import-intersection.md](02-import-intersection.md) | 如何导入新路口数据 |
| 03 | [03-run-simulation.md](03-run-simulation.md) | 如何运行单路口仿真 |
| 04 | [04-batch-experiments.md](04-batch-experiments.md) | 如何跑批量实验 |
| 05 | [05-cloud-coordinator.md](05-cloud-coordinator.md) | 如何配置云端协调器 |
| 06 | [06-generate-configs.md](06-generate-configs.md) | 如何生成仿真配置文件 |
| 07 | [07-view-results.md](07-view-results.md) | 如何查看/导出结果 |
| 08 | [08-visualization.md](08-visualization.md) | 如何生成图表 |
| 09 | [09-docker-deploy.md](09-docker-deploy.md) | Docker 部署与运行 |
| 10 | [10-testing.md](10-testing.md) | 如何跑测试/质量检查 |
| 11 | [11-new-algorithm.md](11-new-algorithm.md) | 如何实现新算法 |

## 协作规范

| 文件 | 内容 |
|------|------|
| [git-workflow.md](git-workflow.md) | Git 分支与提交规范 |
| [citation-guide.md](citation-guide.md) | 引用与参考文献格式 |
```

- [ ] **Step 4: Create missing README files**

`docs/operations/README.md`:
```markdown
# 环境搭建与部署

| 文件 | 内容 |
|------|------|
| [sumo-environment-setup.md](sumo-environment-setup.md) | SUMO 安装、环境变量和版本检查 |
| [deployment.md](deployment.md) | 本地、Docker 和完整实验运行方式 |
```

`docs/reports/README.md`:
```markdown
# 验证与审计报告

由脚本自动生成的验证结果和人工审计记录。

| 文件 | 内容 |
|------|------|
| [batch-validation-report.md](batch-validation-report.md) | 20 路口增强配置批量验证 |
| [sumo-migration-log.md](sumo-migration-log.md) | SUMO 版本兼容性迁移记录 |
| [w3-log-audit.md](w3-log-audit.md) | W3 日志审计 |
| [w5-verification.md](w5-verification.md) | W5 验收验证 |
| [w6-review-issues.md](w6-review-issues.md) | W6 审查问题 |
```

`docs/reference/README.md`:
```markdown
# 参考资料

| 文件 | 内容 |
|------|------|
| [edge-mapping.md](edge-mapping.md) | 20 路口边 ID、方向和进出口属性（脚本生成） |
| [competition/](competition/) | 赛题原始 PDF |
```

`docs/notes/README.md`:
```markdown
# 调研笔记

非规范性技术调研记录，仅供背景参考。

| 文件 | 内容 |
|------|------|
| [docker-sumo-research.md](docker-sumo-research.md) | Docker 基础镜像和 SUMO 版本选型 |
```

- [ ] **Step 5: Update all module READMEs**

In each `ca_mp/<module>/README.md`, replace old import paths with new ones. For example in `ca_mp/algorithms/README.md`:
- `from algorithms.base import ...` → `from ca_mp.algorithms.base import ...`
- `from algorithms.ca_max_pressure import ...` → `from ca_mp.algorithms.ca_max_pressure import ...`

Apply the same pattern to all 9 module READMEs. Also update file path references:
- `algorithms/base.py` → `ca_mp/algorithms/base.py`
- `engine/runner.py` → `ca_mp/engine/runner.py`
- etc.

- [ ] **Step 6: Update `scripts/README.md`**

Update path references:
- `engine/configs/` → `ca_mp/engine/configs/`
- `algorithms`、`engine`、`experiments` 与 `scenes` 模块 → `ca_mp` 包下对应模块
- `python experiments/runner.py` → `python -m ca_mp.experiments.runner`

- [ ] **Step 7: Update `docs/README.md`**

Update the index to reflect:
- `guides/` description: "操作指南（11 篇）与协作规范"
- Add reference to new guides
- Update any path references

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: update all documentation for ca_mp/ layout, add missing READMEs"
```

---

### Task 10: Rewrite root `README.md`

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: final project structure, all guides, all module READMEs
- Produces: root README reflecting new structure with quick-start guide

- [ ] **Step 1: Rewrite `README.md`**

Update the following sections:
- 项目结构：reflect new `ca_mp/` layout (9 top-level dirs)
- 快速开始：use `pip install -e .` then `python examples/run_demo.py 16 ca_maxpressure`
- 代码示例：all imports use `from ca_mp.xxx import ...`
- 文档链接：point to `docs/guides/` for operational guides
- Docker 部分：reflect simplified Dockerfile
- 实验运行：`python -m ca_mp.experiments.runner --help`

Keep the overall structure and Chinese language of the existing README. Only update paths, imports, and structural descriptions.

- [ ] **Step 2: Verify all links in README are valid**

```bash
# Check that referenced files exist
grep -oP '\[.*?\]\((.*?)\)' README.md | grep -oP '\((.*?)\)' | tr -d '()' | while read f; do
  [ -f "$f" ] || echo "MISSING: $f"
done
```

- [ ] **Step 3: Final test run**

```bash
python -m pytest tests/ -v
```

Expected: 66 tests pass.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: rewrite root README for ca_mp/ package structure"
```

---

### Task 11: Final verification and cleanup

**Files:**
- Verify: entire repo

**Interfaces:**
- Consumes: all previous tasks
- Produces: clean repo state, all tests pass, no stale references

- [ ] **Step 1: Grep for any remaining old-style imports**

```bash
git grep -n "from \(algorithms\|api\|cloud\|core\|engine\|experiments\|ml\|scenes\|visualization\)\." -- "*.py" ":!data/"
```

Expected: no matches.

- [ ] **Step 2: Grep for stale path references in active docs**

```bash
git grep -n "engine/configs\|experiments/runner\|experiments/results" -- "*.md" "*.yaml" "*.yml" "*.sh" ":!docs/team/"
```

Review any matches — they should all reference `ca_mp/engine/configs` or `ca_mp/experiments/runner` now.

- [ ] **Step 3: Run full test suite one final time**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: 66 tests pass.

- [ ] **Step 4: Verify editable install from clean state**

```bash
pip install -e . && python -c "from ca_mp.algorithms.ca_max_pressure import CAMaxPressureAlgorithm; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Verify examples run (Mock mode)**

```bash
python examples/run_demo.py 1 ca_maxpressure
```

Expected: 6-step chain verification completes successfully.

- [ ] **Step 6: Check git status is clean**

```bash
git status
```

Expected: "nothing to commit, working tree clean"
