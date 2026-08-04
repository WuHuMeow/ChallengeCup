# 挑战杯项目提交收敛实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 2026-09-01 前，由一名项目主导人与 AI 协作，把当前仓库收敛为代码、部署、实验、报告、PPT、视频和复现证据完整一致的可提交项目包。

**Architecture:** 采用“提交物驱动、证据链优先”的五阶段冻结流程：质量基线 → Docker/第二机器 → 正式实验 → 正式材料 → 最终提交。后级成果只读取已冻结的上级证据；任何代码、配置或统计口径变更都会使受影响的后级成果重新进入未冻结状态。

**Tech Stack:** Python 3.10+、pytest、SUMO 1.27.1、TraCI、FastAPI、Docker Desktop、pandas、SciPy、matplotlib、python-docx、python-pptx、ReportLab、FFmpeg 或桌面剪辑软件、PowerShell、Git。

## Global Constraints

- 最终截止时间固定为 2026-09-01，08-31 前完成提交包冻结。
- 执行模式固定为一人主导、AI 执行；主导人只承担授权、第二机器、身份信息、内容审批、真人录制和平台上传。
- 完整质量门禁必须达到 198 passed、0 failed；不得通过改变 pytest 临时目录掩盖跨盘符缺陷。
- 正式矩阵固定为 20 路口 × 3 算法 × 2 流量 × 3 种子，共 360 组，每组 36000 步。
- 算法固定为 `fixed_time`、`actuated`、`ca_maxpressure`；流量固定为 `1.0`、`1.5`；种子固定为 `42`、`123`、`456`。
- 缺失精确指标必须保持 JSON `null`，不得转换成数值 0。
- Docker live 和第二机器复现只有在真实执行并保存证据后才能标记为 `pass`。
- 报告、PPT 和视频的每个量化结论必须追溯到冻结矩阵、统计表或图表清单。
- 2026-08-26 后不修改算法核心；2026-08-29 后只修复阻塞提交的问题。
- PyQt 看板不进入必交路径；08-25 前硬性材料全部冻结后才允许重新评估。
- 原始 `data/intersection_data/` 保持只读；所有新运行写入 `output/` 下的独立目录。
- 每个任务使用独立提交，提交前运行该任务规定的验证命令。

## 文件结构锁定

- Modify: `scripts/generate_configs.py` — 修复 Windows 跨盘符配置路径生成。
- Modify: `README.md` — 统一实际稳定分支、最终运行入口和提交状态。
- Modify: `docs/tasks/current-status.md` — 统一分支名称，并在阶段冻结后同步角色状态。
- Create: `docs/tasks/submission-progress.md` — 唯一的逐日状态与阶段门禁台账。
- Modify: `.gitignore` — 仅保留证据区说明文件，不追踪大体积运行产物。
- Create: `output/evidence/README.md` — 说明证据目录结构、保留范围和清理规则。
- Create: `scripts/analyze_matrix.py` — 从冻结 `matrix.csv` 生成描述统计、配对检验和来源清单。
- Create: `tests/test_analyze_matrix.py` — 固定统计方向、配对键、缺失值和输出契约。
- Modify: `report/实验评估报告.md` — 由内部提纲升级为数据可追溯的正式报告源文件。
- Create: `report/答辩讲稿.md` — 与 PPT 页码一致的中文讲稿。
- Create: `report/演示视频脚本.md` — 5–8 分钟分镜、旁白和备用镜头。
- Create: `report/实际场景演示方案.md` — 演示输入、步骤、观察项、异常和备用方案。
- Create: `report/交付事实清单.md` — 锁定报告、PPT 和视频允许使用的事实、数字与来源。
- Modify: `output/deliverables/README.md` — 最终材料名称、来源与审核状态。
- Generated: `output/deliverables/实验评估报告.docx`、`实验评估报告.pdf`、`挑战杯项目汇报.pptx`、`演示视频.mp4`、`提交材料清单.md`。

---

### Task 1: 修复 Windows 跨盘符缺陷并冻结绿色基线

**计划日期：** 2026-07-30—2026-08-01

**Files:**
- Modify: `scripts/generate_configs.py:48-49`
- Modify: `README.md:33,112,299-300`
- Modify: `docs/tasks/current-status.md:4,8`
- Test: `tests/test_generate_configs.py`

**Interfaces:**
- Consumes: `source: pathlib.Path`、`output_dir: pathlib.Path`。
- Produces: `relative_input_path(source: Path, output_dir: Path) -> str`；同盘返回相对 POSIX 路径，跨 Windows 盘符返回绝对 POSIX 路径。

- [ ] **Step 1: 在默认 Windows 临时目录复现已有失败**

Run:

```powershell
python -m pytest tests/test_generate_configs.py -q -p no:cacheprovider
```

Expected: 2 failed、1 passed，失败信息包含 `ValueError: path is on mount 'D:', start on mount 'C:'`。

- [ ] **Step 2: 实现最小跨盘符降级逻辑**

将函数替换为：

```python
def relative_input_path(source: Path, output_dir: Path) -> str:
    source = Path(source).resolve()
    output_dir = Path(output_dir).resolve()
    try:
        return Path(os.path.relpath(source, output_dir)).as_posix()
    except ValueError:
        return source.as_posix()
```

- [ ] **Step 3: 验证同盘相对路径和默认跨盘测试均通过**

Run:

```powershell
python -m pytest tests/test_generate_configs.py -q -p no:cacheprovider
python -m pytest tests -q -p no:cacheprovider
```

Expected: 第一条 3 passed；第二条 198 passed、0 failed。

- [ ] **Step 4: 统一稳定分支表述**

将上述两个文档中的稳定基线从 `main` 改为仓库真实存在的 `master`；将“每周日从 main 拉新分支”改为“每周日从 master 拉新分支”。不改历史设计文档。

- [ ] **Step 5: 运行完整质量门禁**

Run:

```powershell
python -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization
python -m flake8 algorithms api cloud core engine experiments scenes scripts visualization --max-line-length=100
git diff --check
git status --short
```

Expected: 前三条退出码均为 0；状态仅包含本任务三个文件。

- [ ] **Step 6: Commit**

```powershell
git add scripts/generate_configs.py README.md docs/tasks/current-status.md
git commit -m "fix: support config generation across Windows drives"
```

---

### Task 2: 建立提交进度台账和证据目录契约

**计划日期：** 2026-08-01—2026-08-02

**Files:**
- Create: `docs/tasks/submission-progress.md`
- Modify: `.gitignore`
- Create: `output/evidence/README.md`
- Modify: `output/README.md`

**Interfaces:**
- Produces: 每日唯一状态入口 `docs/tasks/submission-progress.md`。
- Produces: `output/evidence/{baseline,docker,second-machine,matrix-final,statistics,figures,final-acceptance}/` 运行目录契约。

- [ ] **Step 1: 创建进度台账**

文件必须包含以下初始内容：

```markdown
# 提交收敛进度

> 最终截止：2026-09-01
> 执行模式：一人主导、AI 执行
> 当前阶段：质量基线冻结

## 阶段门禁

| 阶段 | 截止 | 状态 | 证据入口 |
|---|---|---|---|
| 质量基线 | 2026-08-02 | 进行中 | `output/evidence/baseline/` |
| Docker 与第二机器 | 2026-08-07 | 未开始 | `output/evidence/docker/`、`second-machine/` |
| 正式实验 | 2026-08-16 | 未开始 | `output/evidence/matrix-final/` |
| 正式材料 | 2026-08-25 | 未开始 | `output/deliverables/` |
| 提交包 | 2026-08-31 | 未开始 | `output/submission/` |

## 今日状态

| 日期 | 唯一主目标 | 结果 | 验证命令 | 下一步 |
|---|---|---|---|---|
| 2026-07-30 | 确认收敛设计与实施计划 | 通过 | 设计与计划文档审阅 | 修复跨盘符测试 |

## 主导人介入事项

| 最晚日期 | 操作 | 预计用时 | 完成证据 |
|---|---|---:|---|
| 2026-08-03 | 安装并启动 Docker Desktop | 30–60 分钟 | `docker version` 输出 |
| 2026-08-06 | 提供第二台电脑 | 60–90 分钟 | `second-machine.json` |
| 2026-08-17 | 确认学校、团队、成员、指导教师和署名顺序 | 20 分钟 | 主导人书面确认 |
| 2026-08-24 | 录制真人讲解 | 60–120 分钟 | 原始音视频文件 |
| 2026-09-01 | 上传并确认比赛平台状态 | 30 分钟 | 平台成功截图 |
```

- [ ] **Step 2: 为证据说明文件增加窄范围 Git 例外**

在 `.gitignore` 的 `output/*` 规则后加入：

```gitignore
!output/evidence/
output/evidence/*
!output/evidence/README.md
```

- [ ] **Step 3: 写明证据目录契约**

`output/evidence/README.md` 必须明确：运行产物默认忽略；每个冻结目录保留命令、版本、退出码、时间、Git commit 和 SHA-256；只有经过审阅的小型 Markdown/JSON 清单才允许窄范围跟踪；不得把历史已删除产物描述为当前存在。

- [ ] **Step 4: 更新输出所有权说明并检查规则**

Run:

```powershell
git check-ignore -v output/evidence/example.bin
git check-ignore -v output/evidence/README.md
git diff --check
```

Expected: `example.bin` 被忽略；README 不被忽略；diff 无空白错误。

- [ ] **Step 5: Commit**

```powershell
git add .gitignore docs/tasks/submission-progress.md output/README.md output/evidence/README.md
git commit -m "docs: establish submission progress and evidence contract"
```

---

### Task 3: 完成本地 SUMO 快速验收

**计划日期：** 2026-08-02

**Files:**
- Generated: `output/evidence/baseline/`
- Modify: `docs/tasks/submission-progress.md`
- Generated/Modify: `docs/ia-ib-final-verification.md`

**Interfaces:**
- Consumes: Task 1 的绿色 commit。
- Produces: 本地仓库、自动化和 SUMO 三条证据轴；Docker 仍如实为 `not_run`。

- [ ] **Step 1: 记录环境版本**

Run:

```powershell
New-Item -ItemType Directory -Force output/evidence/baseline | Out-Null
@(
  python --version
  sumo --version
  git rev-parse HEAD
) | Set-Content -Encoding UTF8 output/evidence/baseline/environment.txt
```

将完整输出保存到 `output/evidence/baseline/environment.txt`。

- [ ] **Step 2: 运行快速 IA/IB 验收**

Run:

```powershell
python scripts/verify_ia_ib.py --quick --output-root output/evidence/baseline/ia-ib-quick
```

Expected: 退出码 0；不存在 `fail`；`enhanced_3600` 和 Docker 可以是 `not_run`。

- [ ] **Step 3: 检查验收 JSON**

Run:

```powershell
python -c "import json,pathlib; p=pathlib.Path('output/evidence/baseline/ia-ib-quick/verification.json'); d=json.loads(p.read_text(encoding='utf-8')); print({x['name']:x['status'] for x in d})"
```

Expected: `automated_regression`、`original_100`、`enhanced_100`、`matrix`、`stress_runs` 为 `pass`，无 `fail`。

- [ ] **Step 4: 更新台账并提交小型验收报告**

在进度台账记录 commit、命令和结果；保留生成的 `docs/ia-ib-final-verification.md`，不提交被忽略的大型运行目录。

```powershell
git add docs/tasks/submission-progress.md docs/ia-ib-final-verification.md
git commit -m "docs: record local SUMO baseline acceptance"
```

---

### Task 4: 完成 Docker live 验证

**计划日期：** 2026-08-03—2026-08-04

**Files:**
- Existing: `docker/Dockerfile`
- Existing: `docker-compose.yml`
- Existing: `scripts/verify_ia_ib.py:676-756`
- Generated: `output/evidence/docker/`
- Modify: `docs/tasks/submission-progress.md`
- Modify: `docs/ia-ib-final-verification.md`

**Interfaces:**
- Consumes: 主导人安装并启动的 Docker Desktop。
- Produces: build、run、save、load、二次 run 五步 live 证据和 `ca-mp-ia-ib.tar`。

- [ ] **Step 1: 主导人安装并启动 Docker Desktop**

Run:

```powershell
docker version
docker info
```

Expected: Client 与 Server 均可访问，Server OS 为 Linux。

- [ ] **Step 2: 运行静态容器契约**

```powershell
python -m pytest tests/test_docker_static.py -q -p no:cacheprovider
```

Expected: 3 passed。

- [ ] **Step 3: 运行脚本内置 live 流程**

```powershell
python scripts/verify_ia_ib.py --quick --output-root output/evidence/docker/ia-ib-quick
```

Expected: `docker` 为 `pass`；镜像构建、带卷运行、保存、加载和无卷运行退出码均为 0。

- [ ] **Step 4: 独立检查镜像和容器产物**

```powershell
docker image inspect ca-mp:ia-ib --format "{{.Id}} {{.Size}}"
Get-FileHash output/evidence/docker/ia-ib-quick/ca-mp-ia-ib.tar -Algorithm SHA256
Get-ChildItem output/runs -Recurse -Filter summary.json | Select-Object -First 1 FullName,Length
```

Expected: 镜像 ID 非空、tar 的 SHA-256 非空、至少一个容器生成的 `summary.json` 非空。

- [ ] **Step 5: 更新状态并提交报告**

```powershell
git add docs/tasks/submission-progress.md docs/ia-ib-final-verification.md
git commit -m "docs: record Docker live verification"
```

---

### Task 5: 生成离线包并完成第二机器复现

**计划日期：** 2026-08-05—2026-08-07

**Files:**
- Existing: `scripts/package_offline.py`
- Generated: `output/evidence/second-machine/first-package/`
- Generated: `output/evidence/second-machine/second-machine.json`
- Generated: `output/evidence/second-machine/final-package/`
- Modify: `docs/tasks/submission-progress.md`

**Interfaces:**
- Consumes: `ca-mp:ia-ib` Docker 镜像与 Docker live 通过证据。
- Produces: source zip、requirements、image tar、manifest 以及带真实退出码的第二机器证据。

- [ ] **Step 1: 在第一台电脑生成离线包**

```powershell
python scripts/package_offline.py --output-dir output/evidence/second-machine/first-package --image ca-mp:ia-ib
```

Expected: `challenge-cup-source.zip`、`requirements.txt`、`ca-mp-ia-ib.tar`、`offline_manifest.json` 均存在；Docker 状态为 `pass`，第二机器状态为 `not_run`。

- [ ] **Step 2: 在第二台电脑验证文件校验值**

复制整个 `first-package` 后运行：

```powershell
Get-FileHash challenge-cup-source.zip -Algorithm SHA256
Get-FileHash ca-mp-ia-ib.tar -Algorithm SHA256
docker load -i ca-mp-ia-ib.tar
docker run --rm ca-mp:ia-ib --intersection 1 --algorithm fixed_time --steps 100 --output-dir /app/output/runs
```

Expected: 两个哈希与 `offline_manifest.json` 一致；load 和 run 退出码均为 0。

- [ ] **Step 3: 在第二台电脑验证源码路线**

```powershell
Expand-Archive challenge-cup-source.zip -DestinationPath source -Force
Set-Location source
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm ca_maxpressure --steps 100 --output-dir output/runs
```

Expected: 198 passed、0 failed；仿真命令退出码 0，产生非空 `summary.json`。

- [ ] **Step 4: 生成真实第二机器 JSON**

在第二台电脑 PowerShell 中执行；每条命令的退出码由 `$LASTEXITCODE` 立即捕获，不手工填写：

```powershell
$commands = @()
docker load -i ca-mp-ia-ib.tar
$commands += [ordered]@{ command = 'docker load -i ca-mp-ia-ib.tar'; exit_code = $LASTEXITCODE }
docker run --rm ca-mp:ia-ib --intersection 1 --algorithm fixed_time --steps 100 --output-dir /app/output/runs
$commands += [ordered]@{ command = 'docker run --rm ca-mp:ia-ib --intersection 1 --algorithm fixed_time --steps 100 --output-dir /app/output/runs'; exit_code = $LASTEXITCODE }
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
$commands += [ordered]@{ command = 'python -m pytest tests -q -p no:cacheprovider'; exit_code = $LASTEXITCODE }
.\.venv\Scripts\python.exe -m experiments.runner --intersection 1 --algorithm ca_maxpressure --steps 100 --output-dir output/runs
$commands += [ordered]@{ command = 'python -m experiments.runner --intersection 1 --algorithm ca_maxpressure --steps 100 --output-dir output/runs'; exit_code = $LASTEXITCODE }
$evidence = [ordered]@{
  machine = $env:COMPUTERNAME
  timestamp = (Get-Date).ToString('o')
  commands = $commands
}
$evidence | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 second-machine.json
```

将生成的 `second-machine.json` 原样复制回第一台电脑的 `output/evidence/second-machine/second-machine.json`，不得重新手工录入。

- [ ] **Step 5: 回传证据并重新生成最终离线包**

```powershell
python scripts/package_offline.py --output-dir output/evidence/second-machine/final-package --image ca-mp:ia-ib --second-machine-evidence output/evidence/second-machine/second-machine.json
```

Expected: `offline_manifest.json` 中 `docker.status` 和 `second_machine.status` 均为 `pass`。

- [ ] **Step 6: 更新台账并提交证据摘要**

台账记录第二台机器名称、时间、四条命令结果和 manifest 路径，不提交镜像 tar 或完整运行目录。

```powershell
git add docs/tasks/submission-progress.md
git commit -m "docs: record independent reproduction evidence"
```

---

### Task 6: 运行预实验并冻结正式参数

**计划日期：** 2026-08-08—2026-08-09

**Files:**
- Existing: `scripts/run_pdf_matrix.py`
- Existing: `experiments/tuning.py`
- Generated: `output/evidence/matrix-preflight/`
- Modify: `docs/tasks/submission-progress.md`

**Interfaces:**
- Produces: 54 行快速矩阵、`selected_params.json`、`tuning_results.csv`、`holdout_summary.json`。

- [ ] **Step 1: 运行矩阵与调参契约测试**

```powershell
python -m pytest tests/test_tuning.py tests/test_experiments.py tests/test_run_service.py -q -p no:cacheprovider
```

Expected: 全部通过。

- [ ] **Step 2: 运行带调参的快速矩阵**

```powershell
python scripts/run_pdf_matrix.py --quick --tune --output-root output/evidence/matrix-preflight
```

Expected: 输出 `{"runs": 54, "statuses": {"completed": 54}}`；若有失败，保持目录并先诊断，不进入正式矩阵。

- [ ] **Step 3: 审计预实验完整性**

```powershell
python -c "import csv,json,pathlib; r=pathlib.Path('output/evidence/matrix-preflight'); rows=list(csv.DictReader((r/'matrix.csv').open(encoding='utf-8'))); print(len(rows), sorted({x['status'] for x in rows}), json.loads((r/'selected_params.json').read_text(encoding='utf-8'))['parameters'])"
```

Expected: `54 ['completed']`，并输出三个冻结参数。

- [ ] **Step 4: 检查留出集与产物恢复**

```powershell
python scripts/run_pdf_matrix.py --quick --output-root output/evidence/matrix-preflight
```

Expected: 复用已有 54 组，不创建新的 run ID；`matrix_state.json` 仍为 54 个键。

- [ ] **Step 5: 更新台账并提交**

```powershell
git add docs/tasks/submission-progress.md
git commit -m "docs: freeze experiment preflight parameters"
```

---

### Task 7: 运行并审计正式 360 组矩阵

**计划日期：** 2026-08-10—2026-08-16

**Files:**
- Generated: `output/evidence/matrix-final/`
- Modify: `docs/tasks/submission-progress.md`

**Interfaces:**
- Consumes: Task 6 验证过的调参和恢复链路。
- Produces: 完整正式调参证据、360 行 `matrix.csv`、360 键 `matrix_state.json` 和 run-scoped 原始产物。

- [ ] **Step 1: 启动全长度调参与矩阵**

```powershell
python scripts/run_pdf_matrix.py --tune --steps 36000 --output-root output/evidence/matrix-final
```

Expected: 首次运行完成全长度校准/留出评估和 360 组矩阵；运行中断时保留全部已完成产物。

- [ ] **Step 2: 中断后只执行恢复命令**

只在首次命令中断或存在失败组时运行：

```powershell
python scripts/run_pdf_matrix.py --steps 36000 --output-root output/evidence/matrix-final
```

Expected: 不重新运行完整调参，不覆盖成功组，仅补齐未完成请求。

- [ ] **Step 3: 审计 360 个组合**

```powershell
python -c "import csv,json,pathlib; r=pathlib.Path('output/evidence/matrix-final'); rows=list(csv.DictReader((r/'matrix.csv').open(encoding='utf-8'))); keys={(x['intersection_id'],x['algorithm'],x['flow_multiplier'],x['seed']) for x in rows}; print(len(rows),len(keys),sorted({x['status'] for x in rows}),len(json.loads((r/'matrix_state.json').read_text(encoding='utf-8'))))"
```

Expected: `360 360 ['completed'] 360`。

- [ ] **Step 4: 使用验收器审计既有矩阵**

```powershell
python scripts/verify_ia_ib.py --matrix-csv output/evidence/matrix-final/matrix.csv --output-root output/evidence/final-acceptance
```

Expected: `matrix` 为 `pass`，预期请求与 CSV 完全相等；本地 SUMO、自动回归、压力运行和 Docker 均为 `pass`。

- [ ] **Step 5: 冻结矩阵来源信息**

记录 Git commit、Python/SUMO 版本、选中参数、开始/结束时间、360 行状态、警告数量、矩阵 CSV SHA-256 和根目录总字节数到进度台账。

- [ ] **Step 6: Commit**

```powershell
git add docs/tasks/submission-progress.md docs/ia-ib-final-verification.md
git commit -m "docs: freeze the formal 360-run experiment matrix"
```

---

### Task 8: 实现可追溯统计分析

**计划日期：** 2026-08-15—2026-08-17

**Files:**
- Create: `scripts/analyze_matrix.py`
- Create: `tests/test_analyze_matrix.py`
- Modify: `scripts/README.md`

**Interfaces:**
- Consumes: `analyze_matrix(matrix_csv: Path, output_dir: Path) -> dict[str, Path]`。
- Produces: `descriptive_stats.csv`、`paired_tests.csv`、`analysis_manifest.json`。
- 配对键固定为 `intersection_id`、`flow_multiplier`、`seed`；比较固定为 CA-MP 对 FixedTime、CA-MP 对 Actuated。

- [ ] **Step 1: 写入失败测试**

测试必须构造两个路口、两个流量、三个种子、三种算法的数据，并断言：

```python
from pathlib import Path

import pandas as pd
import pytest

from scripts.analyze_matrix import analyze_matrix


def write_complete_matrix_fixture(tmp_path: Path) -> Path:
    rows = []
    factors = {
        "fixed_time": (100.0, 50.0, 10.0, 100.0, 8.0, 1000.0),
        "actuated": (90.0, 45.0, 9.0, 105.0, 7.0, 900.0),
        "ca_maxpressure": (80.0, 40.0, 8.0, 110.0, 6.0, 800.0),
    }
    metrics = (
        "avg_travel_time", "avg_delay", "avg_queue_length",
        "throughput", "total_stops", "fuel_consumption",
    )
    for intersection in ("1", "2"):
        for flow in (1.0, 1.5):
            for seed in (42, 123, 456):
                for algorithm, values in factors.items():
                    row = {
                        "intersection_id": intersection,
                        "algorithm": algorithm,
                        "flow_multiplier": flow,
                        "seed": seed,
                        "status": "completed",
                    }
                    row.update(dict(zip(metrics, values)))
                    rows.append(row)
    path = tmp_path / "matrix.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def write_matrix_with_duplicate_case(tmp_path: Path) -> Path:
    path = write_complete_matrix_fixture(tmp_path)
    frame = pd.read_csv(path)
    pd.concat([frame, frame.iloc[[0]]], ignore_index=True).to_csv(path, index=False)
    return path


def test_analysis_pairs_identical_cases_and_preserves_direction(tmp_path):
    matrix = write_complete_matrix_fixture(tmp_path)
    outputs = analyze_matrix(matrix, tmp_path / "stats")
    paired = pd.read_csv(outputs["paired_tests"])
    assert set(paired["baseline"]) == {"fixed_time", "actuated"}
    assert set(paired["metric"]) == {
        "avg_travel_time", "avg_delay", "avg_queue_length",
        "throughput", "total_stops", "fuel_consumption",
    }
    assert set(paired["n_pairs"]) == {12}
    travel = paired.query(
        "baseline == 'fixed_time' and metric == 'avg_travel_time'"
    ).iloc[0]
    assert travel["improvement_percent"] > 0
    throughput = paired.query(
        "baseline == 'fixed_time' and metric == 'throughput'"
    ).iloc[0]
    assert throughput["improvement_percent"] > 0


def test_analysis_rejects_incomplete_or_duplicate_matrix(tmp_path):
    matrix = write_matrix_with_duplicate_case(tmp_path)
    with pytest.raises(ValueError, match="duplicate case"):
        analyze_matrix(matrix, tmp_path / "stats")
```

- [ ] **Step 2: 运行测试确认模块缺失**

```powershell
python -m pytest tests/test_analyze_matrix.py -q -p no:cacheprovider
```

Expected: FAIL，因为 `scripts.analyze_matrix` 尚不存在。

- [ ] **Step 3: 实现固定统计口径**

实现必须使用：

```python
PAIR_KEYS = ["intersection_id", "flow_multiplier", "seed"]
METRICS = (
    "avg_travel_time",
    "avg_delay",
    "avg_queue_length",
    "throughput",
    "total_stops",
    "fuel_consumption",
)
BASELINES = ("fixed_time", "actuated")
LOWER_IS_BETTER = {
    "avg_travel_time",
    "avg_delay",
    "avg_queue_length",
    "total_stops",
    "fuel_consumption",
}


def improvement_percent(candidate: pd.Series, baseline: pd.Series, metric: str) -> float:
    if metric in LOWER_IS_BETTER:
        return float(((baseline - candidate) / baseline).mean() * 100.0)
    return float(((candidate - baseline) / baseline).mean() * 100.0)
```

对每个指标和基线执行 `scipy.stats.ttest_rel(candidate, baseline, nan_policy="omit")`，输出 `n_pairs`、两组均值、均值差、改善百分比、t 值和双侧 p 值。固定共有 2 个基线 × 6 个指标 = 12 个检验，因此同时输出 `p_value_bonferroni = min(p_value * 12, 1.0)` 和 `significant_after_bonferroni = p_value_bonferroni < 0.05`；报告的“显著”只依据校正后结果。任何重复配对键、非 completed 行、缺失算法或空配对都抛出 `ValueError`。manifest 记录矩阵路径、SHA-256、命令、指标、配对键、校正规则和三个输出文件 SHA-256。

- [ ] **Step 4: 运行测试和正式分析**

```powershell
python -m pytest tests/test_analyze_matrix.py -q -p no:cacheprovider
python scripts/analyze_matrix.py --matrix output/evidence/matrix-final/matrix.csv --output output/evidence/statistics
```

Expected: 测试通过；三个统计文件存在且非空；每个比较和指标都有一行结果。

- [ ] **Step 5: 运行完整回归并提交**

```powershell
python -m pytest tests -q -p no:cacheprovider
python -m flake8 scripts/analyze_matrix.py tests/test_analyze_matrix.py --max-line-length=100
git diff --check
git add scripts/analyze_matrix.py tests/test_analyze_matrix.py scripts/README.md
git commit -m "feat: add traceable paired matrix analysis"
```

---

### Task 9: 生成并审核正式图表

**计划日期：** 2026-08-16—2026-08-18

**Files:**
- Existing: `visualization/report.py`
- Existing: `visualization/plots.py`
- Generated: `output/evidence/figures/`
- Modify: `docs/tasks/submission-progress.md`

**Interfaces:**
- Consumes: 正式运行树和 Task 8 统计表。
- Produces: 算法均值柱状图、路口热图、代表性排队时序、轨迹图和 `manifest.json`。

- [ ] **Step 1: 运行图表契约测试**

```powershell
python -m pytest tests/test_visualization.py -q -p no:cacheprovider
```

Expected: 全部通过。

- [ ] **Step 2: 生成正式图表**

```powershell
python -m visualization.report --input output/evidence/matrix-final/runs --output output/evidence/figures
```

Expected: 五个指标分别生成算法柱状图与路口热图，并生成代表性排队时序和轨迹图；`manifest.json` 中每张图都有存在的来源文件。

- [ ] **Step 3: 自动检查来源和文件大小**

```powershell
python -c "import json,pathlib; r=pathlib.Path('output/evidence/figures'); m=json.loads((r/'manifest.json').read_text(encoding='utf-8')); assert m['figures']; assert all((r/x['file']).stat().st_size>1000 for x in m['figures']); assert all(pathlib.Path(s).exists() for x in m['figures'] for s in x['sources']); print(len(m['figures']))"
```

Expected: 退出码 0，图表数量不小于 10。

- [ ] **Step 4: 逐张视觉检查**

使用本地图片查看工具检查：标题和坐标不截断；图例不遮挡；颜色对三算法保持一致；热图数值方向与统计表一致；任何空指标不被画成 0。将检查结论记录到进度台账。

- [ ] **Step 5: Commit**

```powershell
git add docs/tasks/submission-progress.md
git commit -m "docs: record frozen submission figures"
```

---

### Task 10: 冻结交付事实清单

**计划日期：** 2026-08-17—2026-08-18

**Files:**
- Create: `report/交付事实清单.md`
- Modify: `docs/tasks/submission-progress.md`

**Interfaces:**
- Consumes: 正式矩阵、配对统计、图表 manifest、Docker manifest 和第二机器 manifest。
- Produces: 报告、PPT、讲稿和视频唯一允许引用的事实表。

- [ ] **Step 1: 创建事实清单骨架**

文件固定包含以下表：

```markdown
# 交付事实清单

## 项目身份
| 字段 | 已确认文本 | 确认人 | 确认日期 |

## 环境与复现
| 结论编号 | 结论 | 状态 | 证据文件 | SHA-256 |

## 实验设计
| 字段 | 固定值 | 来源 |

## 量化结论
| 结论编号 | 比较 | 指标 | 流量 | 样本量 | 基线均值 | CA-MP 均值 | 改善百分比 | p 值 | 表述限制 | 来源行 |

## 图表
| 图号 | 文件 | 结论编号 | 来源 manifest | 审核状态 |

## 已知限制
| 限制编号 | 可使用表述 | 禁止表述 | 证据来源 |
```

- [ ] **Step 2: 主导人确认项目身份**

记录学校全称、团队名称、负责人、成员、指导教师、联系方式、署名顺序和代码公开范围。AI 不从路径、Git 用户名或历史文档猜测缺失信息。

- [ ] **Step 3: 从冻结证据自动提取事实**

从 `paired_tests.csv`、`descriptive_stats.csv`、图表 `manifest.json`、`offline_manifest.json` 和最终 `verification.json` 逐行录入。每个量化结论必须包含样本量、方向、p 值和来源行；不显著结果的表述限制写为“观察到差异，但未达到预设显著性阈值”。

- [ ] **Step 4: 执行来源存在性检查**

逐个打开清单引用的文件，确认 SHA-256 与冻结清单一致。任何来源缺失的结论从事实清单删除，不进入材料。

- [ ] **Step 5: Commit**

```powershell
git add report/交付事实清单.md docs/tasks/submission-progress.md
git commit -m "docs: freeze submission facts and evidence sources"
```

---

### Task 11: 完成正式实验报告

**计划日期：** 2026-08-19—2026-08-22

**Files:**
- Modify: `report/实验评估报告.md`
- Generated: `output/deliverables/实验评估报告.docx`
- Generated: `output/deliverables/实验评估报告.pdf`
- Generated: `output/deliverables/report-build-manifest.json`
- Modify: `docs/tasks/submission-progress.md`

**Interfaces:**
- Consumes: `matrix.csv`、`descriptive_stats.csv`、`paired_tests.csv`、图表 manifest、Docker/第二机器 manifest。
- Produces: 六章正式报告源文件及 DOCX/PDF。

**Required skill at execution:** 使用 `pdf` 生成并逐页渲染审核 PDF；使用工作区文档运行时生成 DOCX。

- [ ] **Step 1: 主导人一次性确认身份信息**

确认学校全称、团队名称、负责人、成员、指导教师、联系方式、署名顺序和是否公开代码。AI 只使用主导人确认的文本，不从 Git 用户名或文件路径猜测。

- [ ] **Step 2: 将内部提纲扩写为证据驱动报告**

六章固定为需求与方案、仿真环境、算法原理、实验设计与结果、系统工程化、创新与展望。第四章所有数值从 Task 8 统计表读取；Docker 和第二机器结论从最终 manifest 读取；SUMO warning 单列说明；局限性明确原始信号相位 warning、仿真外推边界和样本规模。

- [ ] **Step 3: 执行数字一致性审计**

逐项核对报告中的百分比、均值、p 值、样本量、路口数量、算法数量、流量和种子；每张图的图注写明来源 manifest 和指标方向。找不到来源的数字直接删除，不保留估算值。

- [ ] **Step 4: 构建 DOCX/PDF**

使用工作区文档运行时把 Markdown、表格和冻结图表排入 A4 DOCX；正文宋体小四、一级标题黑体、页边距 2.5 cm。使用 `pdf` 技能从同一内容生成 PDF，不允许两个版本独立改写。输出 `实验评估报告.docx`、`实验评估报告.pdf` 和包含源文件/图片 SHA-256 的 `report-build-manifest.json`。

Expected: DOCX、PDF、manifest 均非空；PDF 至少 6 页；无缺失图片或字体错误。

Run:

```powershell
python -c "from pathlib import Path; from docx import Document; from pypdf import PdfReader; d=Document('output/deliverables/实验评估报告.docx'); p=PdfReader('output/deliverables/实验评估报告.pdf'); assert len(d.paragraphs)>20; assert len(p.pages)>=6; assert Path('output/deliverables/report-build-manifest.json').stat().st_size>0; print(len(p.pages))"
```

- [ ] **Step 5: 视觉审核 PDF**

逐页检查封面、目录、中文字体、分页、表格、图注、公式、参考资料和页码。检查结论写入进度台账；若版面问题存在，修改源文件或构建器后重新生成，不手改最终 PDF。

- [ ] **Step 6: Commit**

```powershell
git add report/实验评估报告.md docs/tasks/submission-progress.md
git commit -m "docs: complete the evidence-grounded experiment report"
```

---

### Task 12: 完成 PPT 与答辩讲稿

**计划日期：** 2026-08-22—2026-08-24

**Files:**
- Create: `report/答辩讲稿.md`
- Generated: `output/deliverables/挑战杯项目汇报.pptx`
- Generated: `output/deliverables/presentation-build-manifest.json`
- Modify: `docs/tasks/submission-progress.md`

**Interfaces:**
- Consumes: 已冻结报告和图表。
- Produces: 14 页 PPT 与逐页讲稿。

**Required skill at execution:** 使用 `nature-paper2ppt` 的证据驱动叙事、演讲备注、实际 PPTX 生成和渲染审核流程；输入改为本项目正式报告而非论文。

- [ ] **Step 1: 生成 14 页逐页内容契约**

讲稿按 `Slide 01` 至 `Slide 14` 编号，每页包含“页面目标、屏幕文字、讲解、证据来源、预计秒数”。总讲解时间控制在 6 分 30 秒至 7 分 30 秒。

- [ ] **Step 2: 构建 PPTX**

固定 14 页结构为：封面、赛题与痛点、总体方案、系统架构、数据流、CA-MP 原理、三项改进、实验设计、总体结果、重点路口、压力测试、系统演示、创新与局限、总结。使用正式报告、交付事实清单和冻结图表生成 `output/deliverables/挑战杯项目汇报.pptx`；每页备注写入对应讲稿，不生成空占位框。

Expected: 14 页；至少 4 张正式图；所有页面有备注；无空占位框。

Run:

```powershell
python -c "from pptx import Presentation; p=Presentation('output/deliverables/挑战杯项目汇报.pptx'); assert len(p.slides)==14; assert sum(len(s.shapes) for s in p.slides)>28; print(len(p.slides))"
```

- [ ] **Step 3: 视觉审核 PPT**

逐页检查文本溢出、图像拉伸、字号、颜色、对齐、页码和证据脚注。结果页的方向、百分比和显著性与报告逐项一致。

- [ ] **Step 4: 主导人完成一次计时试讲**

记录总时长、超时页面和难读术语。AI 只压缩讲稿，不删证据限定语，不把不显著结果改写为显著。

- [ ] **Step 5: Commit**

```powershell
git add report/答辩讲稿.md docs/tasks/submission-progress.md
git commit -m "docs: complete presentation narrative and evidence map"
```

---

### Task 13: 完成演示方案和 5–8 分钟视频

**计划日期：** 2026-08-24—2026-08-27

**Files:**
- Create: `report/演示视频脚本.md`
- Create: `report/实际场景演示方案.md`
- Generated: `output/deliverables/演示视频.mp4`
- Modify: `docs/tasks/submission-progress.md`

**Interfaces:**
- Consumes: 冻结代码、报告、PPT 和 Docker 镜像。
- Produces: 5–8 分钟 MP4、逐镜头脚本、现场演示主路线和备用路线。

- [ ] **Step 1: 写固定六段视频结构**

时间分配：问题背景 40 秒、方案与架构 60 秒、CA-MP 创新 80 秒、系统实机演示 120 秒、实验结果 100 秒、总结 40 秒。每段记录画面、旁白、屏幕操作、数据来源和备用画面。

- [ ] **Step 2: 写现场演示方案**

主路线固定为 Docker 启动 → 路口 16 CA-MP 100 步 → 查看 `summary.json` 与图表 → 展示三算法正式对比。备用路线固定为本地 Python 命令和预录屏；明确网络断开、Docker 未启动、SUMO 进程残留和输出目录冲突的恢复命令。

- [ ] **Step 3: AI 生成录制清单，主导人录制真人旁白和屏幕**

原始素材至少包括项目开场、Docker 运行、CA-MP 日志、输出目录、正式图表和总结。录制时不得展示个人路径、密钥、聊天记录或无关窗口。

- [ ] **Step 4: 剪辑并检查 MP4**

Expected: 时长 5:00–8:00；1080p；声音清楚；字幕与旁白一致；关键命令可读；无黑帧、静音段或错误数字。

- [ ] **Step 5: Commit**

```powershell
git add report/演示视频脚本.md report/实际场景演示方案.md docs/tasks/submission-progress.md
git commit -m "docs: complete demo plan and video script"
```

---

### Task 14: 最终验收、打包、备份和上传演练

**计划日期：** 2026-08-27—2026-08-31

**Files:**
- Modify: `README.md`
- Modify: `docs/tasks/current-status.md`
- Modify: `docs/tasks/submission-progress.md`
- Modify: `output/deliverables/README.md`
- Generated: `output/deliverables/提交材料清单.md`
- Generated: `output/submission/`

**Interfaces:**
- Consumes: 所有已冻结代码、证据和材料。
- Produces: 可上传压缩包、SHA-256、两份备份和平台上传检查单。

- [ ] **Step 1: 运行最终完整质量门禁**

```powershell
python -m pytest tests -q -p no:cacheprovider
python -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization
python -m flake8 algorithms api cloud core engine experiments scenes scripts visualization --max-line-length=100
git diff --check
```

Expected: 全部退出码 0；测试数量不少于 198，0 failed。

- [ ] **Step 2: 运行最终验收并绑定正式矩阵**

```powershell
python scripts/verify_ia_ib.py --matrix-csv output/evidence/matrix-final/matrix.csv --output-root output/evidence/final-acceptance
```

Expected: 所有检查均为 `pass`；Docker live 为 `pass`；第二机器状态由离线 manifest 单独核对为 `pass`。

- [ ] **Step 3: 在全新目录演练源码路线**

使用 `scripts/package_offline.py` 生成的新 source zip，解压到未使用目录，创建新虚拟环境，安装依赖，运行完整测试和路口 1 FixedTime 100 步。不得引用原仓库虚拟环境和输出目录。

- [ ] **Step 4: 在全新目录演练 Docker 路线**

加载最终 tar，运行路口 16 CA-MP 100 步，检查 `summary.json`、日志和退出码。记录命令和镜像 digest。

- [ ] **Step 5: 生成最终材料清单**

清单固定列出：PPT、源码与离线包、部署说明、Word/PDF 实验报告、5–8 分钟视频、实际场景演示方案、运行入口、Docker 镜像、统计与图表 manifest。每项记录文件名、字节数、SHA-256、来源 commit、审核状态和最后打开时间。

- [ ] **Step 6: 更新仓库状态文档**

README 与 `current-status.md` 只把有真实证据的项更新为完成；删除“正式材料尚未完成”的旧表述；保留已知 SUMO warning 和仿真外推局限。`output/deliverables/README.md` 列出实际生成文件及其来源，不把被忽略文件描述为 Git 已追踪。

- [ ] **Step 7: 创建最终压缩包并校验**

压缩包名称使用主导人在 Task 11 确认的学校全称、团队名称、项目名称和负责人姓名。生成后立即解压到新目录，逐个打开 DOCX、PDF、PPTX、MP4 和 Markdown，并核对 SHA-256。

- [ ] **Step 8: 制作两份独立备份**

第一份保存在当前电脑非工作目录，第二份保存在第二台电脑或移动存储；两份压缩包 SHA-256 必须一致。

- [ ] **Step 9: 最终 Git 提交与清洁检查**

```powershell
git add README.md docs/tasks/current-status.md docs/tasks/submission-progress.md output/deliverables/README.md
git commit -m "docs: freeze final challenge cup submission status"
git status --short
git log --oneline -20
```

Expected: 工作区无未说明的已跟踪改动；最近提交与本计划任务一一对应。

- [ ] **Step 10: 2026-09-01 平台上传**

主导人上传最终包，确认平台显示成功，保存成功页面截图和时间。若平台校验失败，只修复文件命名、大小或上传问题，不修改已冻结算法、实验或结论。

---

## 日历总览

| 日期 | 唯一主目标 | 阶段出口 |
|---|---|---|
| 07-30—08-01 | 跨盘符修复与 198 测试全绿 | 绿色 commit |
| 08-01—08-02 | 进度台账、本地快速验收 | baseline 证据 |
| 08-03—08-04 | Docker live | Docker `pass` |
| 08-05—08-07 | 离线包与第二机器 | second-machine `pass` |
| 08-08—08-09 | 快速调参与 54 组预实验 | 参数/恢复链路冻结 |
| 08-10—08-16 | 全长度调参与 360 组矩阵 | matrix 360/360 |
| 08-15—08-18 | 配对统计与正式图表 | 统计和图表 manifest |
| 08-17—08-18 | 冻结交付事实清单 | 所有结论可追溯 |
| 08-19—08-22 | 正式报告 | DOCX/PDF 冻结 |
| 08-22—08-24 | PPT 与讲稿 | 14 页 PPT 冻结 |
| 08-24—08-27 | 演示方案与视频 | 5–8 分钟 MP4 |
| 08-27—08-31 | 全新环境演练、打包、备份 | 最终包冻结 |
| 09-01 | 上传与确认 | 平台成功证据 |

## 每日收尾检查

每天结束前执行：

```powershell
git status --short
Get-Date -Format o
```

随后在 `docs/tasks/submission-progress.md` 记录唯一主目标、完成证据、失败原因、次日目标和截止风险。若主目标未通过验收，次日继续同一目标，不以开始下一任务代替完成。
