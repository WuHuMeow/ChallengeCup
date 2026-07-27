# Internal Documentation PDF Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align every README and Markdown document with the project PDF, current repository behavior, and the verified IA/IB state while preserving useful historical records.

**Architecture:** Treat the root README and flat `docs/` files as the current internal documentation surface, with module READMEs and focused subdirectory indexes supporting them. Keep dated plans and weekly tasks as historical evidence, consolidate duplicate copies into the Gitee-compatible canonical paths, and validate all remaining Markdown with repository-wide encoding, link, path, status, and regression checks.

**Tech Stack:** Markdown, PowerShell 7/Windows PowerShell, Git, Python 3.11, pytest, flake8, SUMO project configuration.

## Global Constraints

- The PDF requires both Function 1 and Function 2; Function 3 requires one selected track, and this project selects Track B.
- The repository is an internal engineering repository, not the future evaluator-facing repository.
- Historical plans and weekly task checkbox states remain historical and must not be rewritten as current completion claims.
- IA/IB evidence remains 13 `pass`, 0 `fail`, and a 360-run matrix in `pass/audited` mode.
- Docker live verification and second-machine reproduction remain `not_run` until real evidence exists.
- Generated simulation outputs and archives remain deleted; do not regenerate the approximately 79 GB evidence set.
- Preserve `data/`, `engine/configs/`, `config/`, `docs/pdf/`, source code, and source configuration.
- Keep Gitee's flat top-level project structure and use `docs/tasks/` as the only weekly-task tree.
- Use a normal merge and normal push only; never force-push.
- After integration, the local repository must contain only the `main` branch.

---

### Task 1: Establish the Current Documentation Source of Truth

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/总路线.md`
- Modify: `docs/tasks/README.md`
- Modify: `docs/tasks/roadmap.md`
- Create: `docs/superpowers/README.md`

**Interfaces:**
- Consumes: PDF requirements in `docs/pdf/XH-202613_面向雄安新区“城市大脑”的车路云.pdf`, final evidence in `docs/ia-ib-final-verification.md`, and cleanup evidence in `docs/ia-ib-simulation-artifact-cleanup.md`.
- Produces: one current project narrative and navigation hierarchy used by every later documentation task.

- [ ] **Step 1: Record the current status phrases that must be replaced or clarified**

Run:

```powershell
rg -n --glob '*.md' '功能三赛道|功能一.*任选|功能二.*任选|Docker.*(已完成|通过)|第二机器.*(已完成|通过)|output/verification|output/archives|docs/team/tasks' README.md docs
```

Expected: matches identify current wording, historical wording, and links that need classification; do not edit dated plans solely because they match.

- [ ] **Step 2: Rewrite the root status summary and PDF alignment section**

Add a concise internal-repository statement near the project overview with these exact facts:

```markdown
本仓库是团队内部研发仓库。项目 PDF 要求功能一、功能二作为共同基础完成，功能三选择一个方向深入；本项目选择赛道 B（算法调优型），以 CA-MP 的场景适配、参数调优和性能评估为主线。

当前仓库保留可运行代码、20 路口配置、接口与部署说明、实验流程和验收报告。大体积仿真结果及压缩包已删除，需要时按复现指南重新生成。Docker live 与第二机器复现尚无真实证据，状态保持 `not_run`。PPT、Word 报告和演示视频将在后续评委版仓库中整理。
```

Keep Function 2 module development truthful: the PDF permits any one practical module, while this repository implements communication simulation, data/visualization, and an algorithm adapter.

- [ ] **Step 3: Make `docs/README.md` the active documentation map**

Classify links under these exact headings:

```markdown
## 当前入口
## PDF 与验收依据
## 操作与参考资料
## 历史设计和周任务
```

State that current commands come from the root README and active guides, while `docs/superpowers/` and `docs/tasks/` preserve historical decisions and schedules.

- [ ] **Step 4: Align the roadmap and task indexes**

Update `docs/总路线.md`, `docs/tasks/README.md`, and `docs/tasks/roadmap.md` so they distinguish planned weekly tasks from the current verified IA/IB state. Do not change historical dates or bulk-toggle checkboxes. Link the current state to `../ia-ib-final-verification.md` and the cleanup record to `../ia-ib-simulation-artifact-cleanup.md` from the task directory.

- [ ] **Step 5: Add a history index for dated specifications and plans**

Create `docs/superpowers/README.md` with this structure:

```markdown
# 历史设计与实施记录

本目录保存项目设计和实施过程的时间切片，不是当前运行说明。文件中的任务状态、路径、测试数量和命令反映文档编写时的情况。

## 当前入口

- 项目与快速开始：[`README.md`](../../README.md)
- 当前文档地图：[`docs/README.md`](../README.md)
- IA/IB 最终验收：[`docs/ia-ib-final-verification.md`](../ia-ib-final-verification.md)

## 历史目录

- [`specs/`](specs/)：已确认的设计说明。
- [`plans/`](plans/)：对应设计的实施计划与执行记录。
```

- [ ] **Step 6: Verify the source-of-truth wording**

Run:

```powershell
rg -n '功能一、功能二作为共同基础|赛道 B|内部研发仓库|not_run|大体积仿真' README.md docs/README.md docs/总路线.md docs/tasks/README.md docs/tasks/roadmap.md docs/superpowers/README.md
git diff --check
```

Expected: all six concepts are discoverable from the current entry points and `git diff --check` exits 0.

- [ ] **Step 7: Commit the source-of-truth update**

```powershell
git add -- README.md docs/README.md docs/总路线.md docs/tasks/README.md docs/tasks/roadmap.md docs/superpowers/README.md
git commit -m "docs: align internal project direction with PDF"
```

---

### Task 2: Align Every Module README with Current Behavior

**Files:**
- Modify: `algorithms/README.md`
- Modify: `api/README.md`
- Modify: `cloud/README.md`
- Modify: `config/README.md`
- Modify: `core/README.md`
- Modify: `data/README.md`
- Modify: `docker/README.md`
- Modify: `engine/README.md`
- Modify: `examples/README.md`
- Modify: `experiments/README.md`
- Modify: `ml/README.md`
- Modify: `scenes/README.md`
- Modify: `scripts/README.md`
- Modify: `tests/README.md`
- Modify: `visualization/README.md`
- Modify: `output/README.md`
- Modify: `output/deliverables/README.md`

**Interfaces:**
- Consumes: navigation and status wording from Task 1 plus actual files in each module.
- Produces: accurate module-level reference and how-to documentation with no stale output claims.

- [ ] **Step 1: Inventory module README claims against real files**

Run:

```powershell
$readmes = @(
  'algorithms/README.md','api/README.md','cloud/README.md','config/README.md',
  'core/README.md','data/README.md','docker/README.md','engine/README.md',
  'examples/README.md','experiments/README.md','ml/README.md','scenes/README.md',
  'scripts/README.md','tests/README.md','visualization/README.md',
  'output/README.md','output/deliverables/README.md'
)
foreach ($file in $readmes) {
  "=== $file ==="
  rg -n 'output/verification|output/archives|archive/checks|66 passed|115 passed|Docker.*通过|docs/team/tasks|src/' $file
}
```

Expected: stale counts, deleted output paths, and old layout references are listed for correction; no source file is changed.

- [ ] **Step 2: Normalize each module README's factual contract**

For every listed README, retain its module-specific explanation and ensure it states:

```markdown
- Purpose: what the directory owns.
- Inputs/outputs: concrete paths or public interfaces that exist now.
- Minimal usage: a command or import that is present in the repository.
- Dependencies: adjacent modules and external tools.
- Limits: `not_run` external evidence or generated-output behavior where applicable.
```

Do not paste the root project overview into every module. `docker/README.md` must separate static Dockerfile checks from live build/run evidence. `output/README.md` must list only `README.md` and `deliverables/README.md` as retained files and describe generated directories as runtime-created, not currently present.

- [ ] **Step 3: Verify every documented local path exists or is explicitly generated**

Run:

```powershell
rg -n 'output/verification|output/archives|archive/checks|docs/team/tasks|src/' algorithms api cloud config core data docker engine examples experiments ml scenes scripts tests visualization output -g 'README.md'
```

Expected: no current-state claim points at the removed artifact directories, duplicate task tree, or pre-flattening `src/` layout. Generated output examples are explicitly introduced as paths created by commands.

- [ ] **Step 4: Commit the module README update**

```powershell
git add -- algorithms/README.md api/README.md cloud/README.md config/README.md core/README.md data/README.md docker/README.md engine/README.md examples/README.md experiments/README.md ml/README.md scenes/README.md scripts/README.md tests/README.md visualization/README.md output/README.md output/deliverables/README.md
git commit -m "docs: synchronize module readmes with current repository"
```

---

### Task 3: Align Active Guides, Interfaces, Deployment, and Reports

**Files:**
- Modify: `docs/architecture/README.md`
- Modify: `docs/architecture/interface.md`
- Modify: `docs/guides/README.md`
- Modify: `docs/guides/01-algorithm-config.md`
- Modify: `docs/guides/02-import-intersection.md`
- Modify: `docs/guides/03-run-simulation.md`
- Modify: `docs/guides/04-batch-experiments.md`
- Modify: `docs/guides/05-cloud-coordinator.md`
- Modify: `docs/guides/06-generate-configs.md`
- Modify: `docs/guides/07-view-results.md`
- Modify: `docs/guides/08-visualization.md`
- Modify: `docs/guides/09-docker-deploy.md`
- Modify: `docs/guides/10-testing.md`
- Modify: `docs/guides/11-new-algorithm.md`
- Modify: `docs/guides/citation-guide.md`
- Modify: `docs/guides/git-workflow.md`
- Modify: `docs/guides/markdown-guide.md`
- Modify: `docs/operations/README.md`
- Modify: `docs/operations/deployment.md`
- Modify: `docs/notes/README.md`
- Modify: `docs/reference/README.md`
- Modify: `docs/reports/README.md`
- Modify: `docs/deployment.md`
- Modify: `docs/interface.md`
- Modify: `docs/w6-review-issues.md`
- Modify: `report/实验评估报告.md`

**Interfaces:**
- Consumes: current commands, paths, and status wording established in Tasks 1-2.
- Produces: task-oriented how-to, architecture reference, operational limits, and truthful historical report context.

- [ ] **Step 1: Separate active instructions from historical examples**

For each file, retain commands that resolve to existing scripts and flags. Prefix preserved obsolete examples in `git-workflow.md`, `markdown-guide.md`, or historical issue reports with an explicit historical label rather than presenting them as current commands.

- [ ] **Step 2: Align experiment and output documentation with cleanup**

In batch, result-viewing, visualization, deployment, and evaluation-report documents, state that full matrix outputs are generated locally and excluded from the current repository. Point reproduction commands to `scripts/run_pdf_matrix.py` and verification commands to `scripts/verify_ia_ib.py`; do not claim that `output/verification/` currently exists.

- [ ] **Step 3: Align Docker and external-evidence wording**

Use this exact distinction wherever Docker status appears:

```markdown
Dockerfile、Compose 配置和静态契约已检查；当前没有 Docker live build/run/save/load 的真实证据，因此 Docker live 状态为 `not_run`。第二机器复现同样保持 `not_run`。
```

- [ ] **Step 4: Mark W6 issue review as historical**

Add an opening note to `docs/w6-review-issues.md` that the table is a W6 review snapshot. Link current status to `docs/ia-ib-final-verification.md`; do not leave resolved CA-MP or exact-metrics findings presented as current defects.

- [ ] **Step 5: Verify current commands and paths**

Run:

```powershell
rg -n --glob '*.md' 'scripts/[A-Za-z0-9_.-]+\.py|docs/[A-Za-z0-9_./-]+\.md' docs/guides docs/architecture docs/operations docs/deployment.md docs/interface.md report/实验评估报告.md
python scripts/verify_ia_ib.py --help
python scripts/run_pdf_matrix.py --help
```

Expected: referenced scripts/docs exist, both help commands exit 0, and no guide claims deleted output is committed.

- [ ] **Step 6: Commit active guide and report updates**

```powershell
git add -- docs/architecture docs/guides docs/operations docs/notes/README.md docs/reference/README.md docs/reports/README.md docs/deployment.md docs/interface.md docs/w6-review-issues.md report/实验评估报告.md
git commit -m "docs: refresh active guides and verification boundaries"
```

---

### Task 4: Consolidate Duplicate Documentation into Canonical Gitee Paths

**Files:**
- Delete: `docs/team/tasks/README.md`
- Delete: `docs/team/tasks/` (the index plus 48 task files)
- Delete: `docs/reference/edge-mapping.md`
- Delete: `docs/reports/sumo-migration-log.md`
- Delete: `docs/reports/batch-validation-report.md`
- Delete: `docs/operations/sumo-environment-setup.md`
- Delete: `docs/reports/w3-log-audit.md`
- Delete: `docs/reports/w5-verification.md`
- Delete: `docs/reports/w6-review-issues.md`
- Delete: `docs/notes/docker-sumo-research.md`
- Delete: `docs/reference/competition/XH-202613_面向雄安新区“城市大脑”的车路云.pdf`
- Modify: `docs/w6-review-issues.md`
- Modify: `docs/edge_mapping.md`
- Modify: `docs/migration_log.md`
- Modify: `docs/batch_validate_report.md`
- Modify: `docs/sumo_env_setup.md`
- Modify: `docs/w3-log-audit.md`
- Modify: `docs/w5-verification.md`
- Modify: `docs/notes/docker_sumo_research.md`
- Modify: `docs/reference/README.md`
- Modify: `docs/reports/README.md`
- Modify: `docs/operations/README.md`
- Modify: `docs/notes/README.md`

**Interfaces:**
- Consumes: the canonical links chosen in Tasks 1-3.
- Produces: one copy of each historical/reference document and one weekly-task tree.

- [ ] **Step 1: Reconfirm the 48 task-pair comparison before deletion**

Run:

```powershell
$nameMap = [ordered]@{
  TL='tl-technical-lead'; IA='ia-infrastructure-a'; IB='ib-infrastructure-b'
  AA='aa-algorithm-a'; AB='ab-algorithm-b'; EX='ex-experiment'
  DA='da-delivery-a'; DB='db-delivery-b'
}
$suffixMap = @{ TL='tech_lead'; IA='infra_a'; IB='infra_b'; AA='algo_a'; AB='algo_b'; EX='experiment'; DA='delivery_a'; DB='delivery_b' }
$different = @()
foreach ($week in 1..6) {
  foreach ($role in $nameMap.Keys) {
    $canonical = "docs/tasks/w$week/$($role)_$($suffixMap[$role]).md"
    $legacy = "docs/team/tasks/w$week/$($nameMap[$role]).md"
    if ((Get-FileHash $canonical).Hash -ne (Get-FileHash $legacy).Hash) {
      $different += "$week/$role"
    }
  }
}
"DIFFERENT=$($different.Count):$($different -join ',')"
```

Expected: 47 pairs are byte-identical. The only differing pair is W1 IA: canonical `docs/tasks/w1/IA_infra_a.md` references `docs/migration_log.md`, which exists; legacy `docs/team/tasks/w1/ia-infrastructure-a.md` references nonexistent `docs/sumo-migration-log.md`. No legacy-only content needs merging.

- [ ] **Step 2: Reconfirm duplicate reference/report hashes and differences**

Run:

```powershell
$pairs = @(
  @('docs/edge_mapping.md','docs/reference/edge-mapping.md'),
  @('docs/migration_log.md','docs/reports/sumo-migration-log.md'),
  @('docs/sumo_env_setup.md','docs/operations/sumo-environment-setup.md'),
  @('docs/w3-log-audit.md','docs/reports/w3-log-audit.md'),
  @('docs/w5-verification.md','docs/reports/w5-verification.md'),
  @('docs/notes/docker_sumo_research.md','docs/notes/docker-sumo-research.md')
)
foreach ($pair in $pairs) {
  if ((Get-FileHash $pair[0]).Hash -ne (Get-FileHash $pair[1]).Hash) {
    throw "Unexpected duplicate drift: $($pair -join ' <> ')"
  }
}
```

Expected: exit 0. `batch-validation-report.md` differs only by trailing spaces; `reports/w6-review-issues.md` has one newer Docker status that Task 3 has already incorporated into the canonical historical file.

- [ ] **Step 3: Delete the redundant task tree and duplicate files**

Run:

```powershell
git rm -r -- docs/team/tasks
git rm -- docs/reference/edge-mapping.md docs/reports/sumo-migration-log.md docs/reports/batch-validation-report.md docs/operations/sumo-environment-setup.md docs/reports/w3-log-audit.md docs/reports/w5-verification.md docs/reports/w6-review-issues.md docs/notes/docker-sumo-research.md
```

Keep `docs/tasks/`, flat canonical docs, `docs/operations/deployment.md`, and `docs/architecture/interface.md`; the latter two are focused summaries rather than byte duplicates.

- [ ] **Step 4: Delete the duplicate PDF copy**

Before deletion, verify both PDF hashes equal `FB5005724413E128CFBF3AD61D2E1782F93FD08BB54394E16561660C2E25C930`. Keep `docs/pdf/XH-202613_面向雄安新区“城市大脑”的车路云.pdf`, then run:

```powershell
git rm -- 'docs/reference/competition/XH-202613_面向雄安新区“城市大脑”的车路云.pdf'
```

- [ ] **Step 5: Update directory indexes to canonical paths**

Point references and reports indexes to the retained flat files:

```markdown
- `../edge_mapping.md`
- `../migration_log.md`
- `../batch_validate_report.md`
- `../sumo_env_setup.md`
- `../w3-log-audit.md`
- `../w5-verification.md`
- `../w6-review-issues.md`
- `../notes/docker_sumo_research.md`
- `../pdf/XH-202613_面向雄安新区“城市大脑”的车路云.pdf`
```

- [ ] **Step 6: Verify no active link targets a deleted duplicate**

Run:

```powershell
rg -n --glob '*.md' 'docs/team/tasks|team/tasks|reference/edge-mapping|reports/sumo-migration-log|reports/batch-validation-report|operations/sumo-environment-setup|reports/w3-log-audit|reports/w5-verification|reports/w6-review-issues|notes/docker-sumo-research|reference/competition' README.md docs algorithms api cloud config core data docker engine examples experiments ml output report scenes scripts tests visualization
```

Expected: no matches outside dated historical plans/specifications. Any historical match must be explicitly contextual and must not be changed merely to erase history.

- [ ] **Step 7: Commit duplicate consolidation**

```powershell
git add -- docs
git commit -m "docs: consolidate duplicate internal documentation"
```

---

### Task 5: Audit All Remaining Markdown for Encoding, Links, and PDF Direction

**Files:**
- Modify only files identified by the deterministic checks below.
- Create: `docs/reports/markdown-audit.md`

**Interfaces:**
- Consumes: all repository Markdown after Tasks 1-4.
- Produces: an auditable inventory showing that every remaining Markdown file was checked.

- [ ] **Step 1: Generate the Markdown inventory**

Create `docs/reports/markdown-audit.md` with the audit date, total file count, canonical entry points, deleted duplicate groups, and result counts for UTF-8, link, stale-path, and PDF-direction checks. Include a compact table by category rather than one 130-line table when a category has one shared status.

- [ ] **Step 2: Check strict UTF-8 decoding for every Markdown file**

Run:

```powershell
$utf8 = [System.Text.UTF8Encoding]::new($false, $true)
$errors = @()
foreach ($file in @(rg --files -g '*.md' -g '*.MD')) {
  try { $null = $utf8.GetString([IO.File]::ReadAllBytes((Resolve-Path $file))) }
  catch { $errors += $file }
}
if ($errors.Count) { $errors; exit 1 }
"UTF8_OK=$(@(rg --files -g '*.md' -g '*.MD').Count)"
```

Expected: all Markdown files decode strictly as UTF-8.

- [ ] **Step 3: Check local Markdown links**

Run this read-only checker. It ignores `http:`, `https:`, `mailto:`, fragment-only links, and fenced-code examples. It resolves repository-root and document-relative links, URL-decodes them, strips anchors, and requires the target to exist.

```powershell
$repo = (Resolve-Path '.').Path
$broken = [System.Collections.Generic.List[string]]::new()
foreach ($file in @(rg --files -g '*.md' -g '*.MD')) {
  $full = (Resolve-Path -LiteralPath $file).Path
  $base = Split-Path -Parent $full
  $inFence = $false
  $lineNumber = 0
  foreach ($line in Get-Content -Encoding UTF8 -LiteralPath $full) {
    $lineNumber++
    if ($line -match '^\s*(```|~~~)') { $inFence = -not $inFence; continue }
    if ($inFence) { continue }
    foreach ($match in [regex]::Matches($line, '!??\[[^\]]*\]\((?<target>[^)]+)\)')) {
      $target = $match.Groups['target'].Value.Trim()
      if ($target.StartsWith('<') -and $target.EndsWith('>')) {
        $target = $target.Substring(1, $target.Length - 2)
      } else {
        $target = ($target -split '\s+["'']')[0]
      }
      if ($target -match '^(#|https?:|mailto:|data:)' -or [string]::IsNullOrWhiteSpace($target)) { continue }
      $target = [Uri]::UnescapeDataString(($target -split '#')[0])
      if ($target.StartsWith('/')) {
        $candidate = Join-Path $repo $target.TrimStart('/')
      } else {
        $candidate = Join-Path $base $target
      }
      if (-not (Test-Path -LiteralPath $candidate)) {
        $broken.Add("${file}:${lineNumber} -> $target")
      }
    }
  }
}
if ($broken.Count) { $broken; exit 1 }
'MARKDOWN_LINKS_OK'
```

Expected: zero broken active local links. Fix the source Markdown for every failure and rerun until zero.

- [ ] **Step 4: Check PDF direction and evidence truthfulness**

Run:

```powershell
rg -n --glob '*.md' '功能一.*(可选|任选|二选一)|功能二.*(可选|任选|二选一)|赛道 A.*赛道 B.*赛道 C.*(全部|同时)|Docker live.*pass|第二机器.*pass' README.md docs algorithms api cloud config core data docker engine examples experiments ml output report scenes scripts tests visualization
```

Expected: current docs have zero false claims. Matches quoting the PDF's Function 2 “choose any module” rule or historical documents are classified in the audit report rather than rewritten blindly.

- [ ] **Step 5: Check repository-wide stale paths and deleted artifacts**

Run:

```powershell
rg -n --glob '*.md' 'docs/team/tasks|reference/competition|output/verification|output/archives|archive/checks' .
```

Expected: current docs do not claim deleted paths exist. Historical plans and cleanup reports may mention them as historical or deleted evidence.

- [ ] **Step 6: Update the audit report with exact results**

Record exact totals and exceptions. Do not write “all pass” unless the preceding commands exited 0. List dated historical files that intentionally retain old paths or status wording.

- [ ] **Step 7: Commit final Markdown audit fixes**

```powershell
$auditFixes = @(git diff --name-only -- '*.md' '*.MD')
git add -- docs/reports/markdown-audit.md
if ($auditFixes.Count) { git add -- $auditFixes }
git commit -m "docs: record repository-wide markdown audit"
```

---

### Task 6: Run Full Regression Verification and Review the Documentation Diff

**Files:**
- Test: all changed Markdown files.
- Test: `tests/`
- Test: Python packages imported by the project.

**Interfaces:**
- Consumes: the complete documentation update.
- Produces: evidence required before merging and pushing.

- [ ] **Step 1: Run Markdown and Git hygiene checks**

Run the strict UTF-8, local-link, stale-path, and PDF-direction checks from Task 5, then:

```powershell
git diff --check main...HEAD
git status --short --branch
```

Expected: all checks exit 0 and the worktree is clean after commits.

- [ ] **Step 2: Run the complete Python regression suite in a writable temporary root**

Run:

```powershell
$checkRoot = Join-Path (Resolve-Path '.').Path 'output/.docs-final-check'
$env:PYTHONPYCACHEPREFIX = Join-Path $checkRoot 'pycache'
$env:MPLCONFIGDIR = Join-Path $checkRoot 'mplconfig'
python -m pytest tests/ -q --basetemp (Join-Path $checkRoot 'pytest')
```

Expected: `198 passed`, exit 0.

- [ ] **Step 3: Run compile, import, lint, and repository checks**

Run:

```powershell
python -m compileall -q algorithms api cloud config core engine experiments ml scenes scripts visualization
python -c "import algorithms, api, cloud, config, core, engine, experiments, ml, scenes, visualization; print('imports ok')"
python -m flake8 algorithms api cloud config core engine experiments ml scenes scripts tests visualization
git diff --check main...HEAD
```

Expected: all commands exit 0; import command prints `imports ok`.

- [ ] **Step 4: Remove only the generated final-check directory**

Resolve `output/.docs-final-check`, confirm it is inside the repository and equals the intended path, then remove it. Verify `output/` again contains only `README.md` and `deliverables/README.md`.

- [ ] **Step 5: Review the final documentation diff**

Run:

```powershell
git diff --stat main...HEAD
git diff --name-status main...HEAD
git log --oneline main..HEAD
```

Expected: only Markdown/PDF duplicate cleanup and the design/plan documents changed; no Python, configuration, source data, or runtime dependency file changed.

---

### Task 7: Merge to Main, Remove the Temporary Branch, and Push GitHub

**Files:**
- No new file content; Git integration only.

**Interfaces:**
- Consumes: verified commits from Tasks 1-6.
- Produces: GitHub `main` containing the complete documentation refresh, with local `main` as the only branch.

- [ ] **Step 1: Refresh and validate the remote main branch**

Run:

```powershell
git fetch origin main
git merge-base --is-ancestor origin/main codex/docs-pdf-alignment
```

Expected: ancestor check exits 0. If it fails, stop and integrate the new remote commits normally before continuing.

- [ ] **Step 2: Merge the temporary branch into main**

Run:

```powershell
git switch main
git merge --no-ff codex/docs-pdf-alignment -m "merge: align internal documentation with project PDF"
```

Expected: normal merge succeeds without conflict.

- [ ] **Step 3: Delete the local temporary branch**

Run:

```powershell
git branch -d codex/docs-pdf-alignment
git branch --format='%(refname:short)'
```

Expected: output contains only `main`.

- [ ] **Step 4: Push main without force**

Run:

```powershell
git push origin main
```

Expected: GitHub accepts the normal update.

- [ ] **Step 5: Verify remote and local identity**

Run:

```powershell
$local = git rev-parse HEAD
$remote = (git ls-remote origin refs/heads/main).Split()[0]
if ($local -ne $remote) { throw "GitHub main mismatch: local=$local remote=$remote" }
git status --short --branch
git branch --format='%(refname:short)'
```

Expected: local and remote hashes match, worktree is clean, and only `main` remains locally.
