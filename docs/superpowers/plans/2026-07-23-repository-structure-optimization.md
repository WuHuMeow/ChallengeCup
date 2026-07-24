# Repository Structure Optimization Implementation Plan

> **历史迁移记录：** 本计划中的旧路径用于定义来源到目标的迁移映射，不是当前可执行命令。现行路径以仓库 README 索引为准。
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the repository's scripts, tests, documentation, and historical outputs by responsibility while preserving public Python imports, runtime output paths, and all existing user changes.

**Architecture:** Keep the import-bearing source packages at the repository root. Introduce category directories only under `scripts/`, `tests/`, and `docs/`; update path-sensitive scripts to derive the repository root from their new depth and update every repository-local command/link to the new canonical location. Keep current runtime output directories stable and move only historical artifacts into explicit archive namespaces.

**Tech Stack:** Python 3, pytest, PowerShell file moves, Markdown, Bash, Git, SUMO/TraCI.

## Global Constraints

- Preserve public imports such as `from engine...` and `from scenes...`; do not move `algorithms/`, `api/`, `cloud/`, `config/`, `core/`, `engine/`, `experiments/`, `ml/`, `scenes/`, or `visualization/`.
- Do not move `data/intersection_data/`, `engine/configs/`, `docs/superpowers/`, or `.superpowers/sdd/`.
- Preserve runtime-compatible `output/csv/`, `output/logs/`, and `output/variants/` paths.
- Do not delete historical artifacts; move them only after resolving and checking every destination.
- Python files remain `snake_case`; Markdown files use English `kebab-case`; the competition PDF retains its original filename.
- Existing tracked and untracked user changes are valid input and must not be reverted, overwritten, or committed by this work.
- All repository commands and local Markdown links must reference canonical new paths after migration.
- `python -m pytest tests/ -q` must still collect and pass 66 tests; `bash scripts/quality/lint_check.sh` must report `clean`.

## File Map

- Modify path-sensitive scripts in `scripts/data/`, `scripts/simulation/`, and `scripts/validation/` after moving them; leave `scripts/quality/lint_check.sh` executable and update its self-references.
- Move tests into `tests/unit/` and `tests/integration/`; add `tests/README.md` describing the collection contract.
- Move operational, architecture, report, team, guide, note, and reference Markdown files under `docs/`; add/update `docs/README.md` as the index.
- Create `scripts/README.md`, `output/README.md`, and `output/deliverables/README.md`; update root and module READMEs to describe stable responsibilities rather than stale progress checkboxes.
- Update `.gitignore` only as needed to allow the two output README files while continuing to ignore generated runtime artifacts.

### Task 1: Establish migration inventory and safety baseline

**Files:**
- Create: `docs/superpowers/plans/2026-07-23-repository-structure-optimization.md`
- Read-only inputs: `docs/superpowers/specs/2026-07-23-repository-structure-optimization-design.md`, `git status --short`

**Interfaces:**
- Produces a complete old-path/new-path mapping, file-count baseline, and hash manifest used by later tasks.

- [ ] **Step 1: Record the worktree baseline**

Run from the repository root:

```powershell
git status --short
Get-ChildItem scripts -File | Sort-Object Name
Get-ChildItem tests -File | Sort-Object Name
Get-ChildItem docs -File | Sort-Object Name
Get-ChildItem docs\tasks -Recurse -File | Sort-Object FullName
Get-ChildItem output -Recurse -File | Sort-Object FullName
```

Expected: the pre-existing modified/untracked files remain visible; no move is performed by this task.

- [ ] **Step 2: Capture hashes for files that will move**

Use `Get-FileHash -Algorithm SHA256` for every file under `scripts`, `tests`, `docs` (excluding `docs/superpowers`), and historical `output` directories. Save the command output outside the repository or in a temporary review buffer; do not add generated manifests to Git.

- [ ] **Step 3: Check all destination paths are absent**

Before moving, assert that each destination in Tasks 2-5 either does not exist or is the exact intended existing directory. Abort the move if a destination file already exists.

### Task 2: Reclassify scripts without changing their command behavior

**Files:**
- Move: `scripts/extract_metadata.py`, `scripts/generate_edge_mapping.py` -> `scripts/data/`
- Move: `scripts/generate_configs.py`, `scripts/split_jobs.py` -> `scripts/simulation/`
- Move: `scripts/validate_all.py`, `scripts/batch_validate.py`, `scripts/check_outputs.py`, `scripts/check_seed_repro.py`, `scripts/stress_memory.py` -> `scripts/validation/`
- Move: `scripts/lint_check.sh` -> `scripts/quality/`
- Create/modify: `scripts/README.md`

**Interfaces:**
- Commands become `python scripts/data/<name>.py`, `python scripts/simulation/<name>.py`, `python scripts/validation/<name>.py`, and `bash scripts/quality/lint_check.sh`.
- Every moved Python script defines `ROOT = Path(__file__).resolve().parents[2]` (or an equivalent repository-root calculation) and uses it for repository-relative files.

- [ ] **Step 1: Create category directories and move files**

Create `scripts/data`, `scripts/simulation`, `scripts/validation`, and `scripts/quality`. Move only the files listed above, preserving bytes and executable mode where applicable. Do not leave compatibility wrapper files at `scripts/*.py`.

- [ ] **Step 2: Update root derivation and generated-document destinations**

For each moved Python file, replace one-level root derivation with:

```python
ROOT = Path(__file__).resolve().parents[2]
```

Update embedded command examples and generated output paths, especially `batch_validate.py`'s report path, `generate_edge_mapping.py`'s `docs/reference/edge-mapping.md` target, and `generate_configs.py`'s `engine/configs/` target. Keep `output/csv/`, `output/logs/`, and `output/variants/` unchanged.

- [ ] **Step 3: Update lint script path assumptions**

Make `scripts/quality/lint_check.sh` resolve the repository root from its own directory, scan tracked and untracked source files as before, and continue to print exactly `clean` on success.

- [ ] **Step 4: Add the scripts index**

Write `scripts/README.md` with the four responsibilities, a file index, exact commands, inputs/outputs, dependencies, and known limitations. Include the new paths in every command example.

- [ ] **Step 5: Run the script-level regression**

Run:

```powershell
python scripts/validation/check_seed_repro.py
python scripts/validation/stress_memory.py 1 100
bash scripts/quality/lint_check.sh
```

Expected: seed check reports reproducible seed 42 and differing seed 7; stress check exits 0; lint prints `clean`.

### Task 3: Split tests into unit and integration suites

**Files:**
- Move to `tests/unit/`: `test_algorithms.py`, `test_cloud.py`, `test_edge_channel.py`, `test_ml.py`, `test_mock_bridge.py`, `test_types_fields.py`, `test_vehicles.py`
- Move to `tests/integration/`: `test_api.py`, `test_edge_mapping.py`, `test_events.py`, `test_experiments.py`, `test_resilience.py`, `test_scenes.py`, `test_seed.py`, `test_step_log.py`
- Create: `tests/README.md`
- Modify: any moved test that contains a hard-coded old script path

**Interfaces:**
- `pytest tests/` remains the single supported collection entry point and must retain 66 collected tests.

- [ ] **Step 1: Move tests and preserve package discovery**

Create `tests/unit` and `tests/integration`, move exactly the listed files, and do not add `__init__.py` unless pytest discovery requires it.

- [ ] **Step 2: Update test diagnostics and script references**

Change messages such as `python scripts/generate_edge_mapping.py` to `python scripts/data/generate_edge_mapping.py`; do not alter test assertions or fixtures unrelated to paths.

- [ ] **Step 3: Add test-suite documentation**

Document unit/integration ownership, the `pytest tests/` command, expected collection count, external SUMO prerequisites for integration tests, and known slow tests.

- [ ] **Step 4: Run the collection and full test suite**

Run:

```powershell
python -m pytest tests/ --collect-only -q
python -m pytest tests/ -q
```

Expected: collection still reports 66 tests and the suite reports `66 passed`.

### Task 4: Rebuild the docs taxonomy and canonical names

**Files:**
- Move/rename root docs into:
  - `docs/architecture/interface.md`
  - `docs/operations/deployment.md`
  - `docs/operations/sumo-environment-setup.md`
  - `docs/reports/batch-validation-report.md`
  - `docs/reports/sumo-migration-log.md`
  - `docs/reports/w3-log-audit.md`
  - `docs/reports/w5-verification.md`
  - `docs/reports/w6-review-issues.md`
  - `docs/reference/edge-mapping.md`
  - `docs/reference/competition/XH-202613_面向雄安新区“城市大脑”的车路云.pdf`
  - `docs/notes/docker-sumo-research.md`
- Merge `docs/总路线.md` and `docs/tasks/roadmap.md` into `docs/team/project-roadmap.md`; retain the more complete content and repair links.
- Move `docs/tasks/w1..w6/` to `docs/team/tasks/w1..w6/`.
- Rename each task file using the fixed role mapping: `AA_algo_a.md` -> `aa-algorithm-a.md`, `AB_algo_b.md` -> `ab-algorithm-b.md`, `DA_delivery_a.md` -> `da-delivery-a.md`, `DB_delivery_b.md` -> `db-delivery-b.md`, `EX_experiment.md` -> `ex-experiment.md`, `IA_infra_a.md` -> `ia-infrastructure-a.md`, `IB_infra_b.md` -> `ib-infrastructure-b.md`, `TL_tech_lead.md` -> `tl-technical-lead.md`.
- Preserve `docs/guides/` and `docs/superpowers/` in place.

**Interfaces:**
- Every repository-local Markdown link resolves from its new document location; no old canonical docs path remains in executable commands or navigation.

- [ ] **Step 1: Create destination taxonomy and move non-duplicate documents**

Create `architecture`, `operations`, `reports`, `team`, `reference/competition`, and retain `guides`, `notes`, `superpowers`. Move files only after destination checks from Task 1.

- [ ] **Step 2: Merge the two roadmaps**

Create `docs/team/project-roadmap.md` from the more complete roadmap, preserving unique milestone/team/risk content from both sources. Update image and task links relative to `docs/team/`; do not retain either old roadmap file.

- [ ] **Step 3: Move and rename all 48 task books**

Apply the eight-role mapping uniformly across `w1` through `w6`. Update each task book's internal links and commands to the canonical `scripts`, `docs`, and `output` paths; preserve historical status text unless a link/path is invalid.

- [ ] **Step 4: Repair links and commands by document category**

Update `README.md`, `docs/README.md`, guides, notes, reports, task books, Docker files, and module READMEs to reference the new paths. Correct relative link bases rather than using blind string replacement.

- [ ] **Step 5: Add a Markdown link checker**

Run a repository-local checker that parses Markdown links, ignores `http(s)`, anchors, and image URLs, resolves relative paths from each Markdown file's directory, and reports every missing target. Expected: zero missing local targets.

### Task 5: Archive historical output without changing runtime interfaces

**Files:**
- Move: `output/validate/`, `output/validate_quick/` -> `output/archive/validation/`
- Move: `output/w3_audit/`, `output/stress/`, `output/batch_smoke/` -> `output/archive/experiments/`
- Move: `output/seed_check/`, `output/cli_check/`, `output/cli_check2/`, temporary pytest output, and the IB disconnect check logs -> `output/archive/checks/`
- Create: `output/README.md`, `output/deliverables/README.md`
- Modify: `.gitignore`

**Interfaces:**
- Runtime code continues writing to `output/csv/`, `output/logs/`, and `output/variants/`; historical evidence is discoverable under `output/archive/`.

- [ ] **Step 1: Inventory and verify archive destinations**

Count and hash every historical file before moving. Create archive directories and abort if any destination would overwrite an existing file.

- [ ] **Step 2: Move historical directories**

Move the listed directories as complete trees. Do not delete or regenerate their contents. Leave current runtime directories untouched.

- [ ] **Step 3: Document output ownership**

Write `output/README.md` explaining runtime versus archive directories, retention rules, and commands that produce each class of artifact. Write `output/deliverables/README.md` describing the currently empty/submission-facing area without inventing deliverables.

- [ ] **Step 4: Adjust ignore rules**

Keep generated output ignored while explicitly allowing `output/README.md` and `output/deliverables/README.md`. Verify with `git check-ignore -v` that the READMEs are not ignored and generated CSV/log/XML files remain ignored.

### Task 6: Refresh root and module documentation

**Files:**
- Modify: `README.md`, `docs/README.md`, `examples/README.md`, and every source/module README under `algorithms/`, `api/`, `cloud/`, `config/`, `core/`, `docker/`, `engine/`, `experiments/`, `ml/`, `scenes/`, `visualization/`
- Modify: `docker/Dockerfile`, `docker-compose.yml`, and any configuration containing repository-local documentation or script paths

**Interfaces:**
- Each module README contains responsibility, file index, public interface/command, inputs/outputs, dependencies, and known limitations; it does not contain stale completion checklists.

- [ ] **Step 1: Rewrite indexes around the new taxonomy**

Update the root README's quick start, repository map, documentation table, task links, validation commands, and architecture image links. Update `docs/README.md` to be the canonical documentation index.

- [ ] **Step 2: Normalize module README contracts**

For each module README, retain useful technical content but replace time-sensitive `[x]/[ ]` progress sections with factual responsibility and interface sections. Keep known limitations such as SUMO requirements and mock bridge behavior.

- [ ] **Step 3: Update Docker and configuration references**

Ensure Docker commands point to `scripts/validation/validate_all.py`, documentation paths point to `docs/operations/` or `docs/notes/`, and container COPY paths remain valid after the reorganization.

- [ ] **Step 4: Search for stale canonical paths**

Run `rg` across tracked text files for old paths (`scripts/<moved-file>`, `docs/interface.md`, `docs/deployment.md`, `docs/tasks/`, `docs/pdf/`, `docs/总路线.md`, and old report names). Review every match; historical prose may remain only when it explicitly describes an old command and is relabeled as historical.

### Task 7: Execute staged verification and content-integrity checks

**Files:**
- No intended source changes; modify only files required by a failing check.

**Interfaces:**
- Produces evidence that the reorganized tree is byte-preserving where required and behavior-preserving for Python, tests, scripts, and simulation smoke runs.

- [ ] **Step 1: Verify moved-file counts and hashes**

Compare the Task 1 SHA256 manifest against new paths. Expected: every moved file has exactly one matching destination; no source file is silently lost or duplicated.

- [ ] **Step 2: Compile Python sources**

Run:

```powershell
python -m compileall algorithms api cloud core engine examples experiments ml scenes scripts visualization
```

Expected: exit code 0 with no syntax errors.

- [ ] **Step 3: Run regression and quality checks**

Run:

```powershell
python -m pytest tests/ -q
bash scripts/quality/lint_check.sh
git diff --check
```

Expected: `66 passed`, `clean`, and no whitespace errors.

- [ ] **Step 4: Run reorganized script and simulation smoke checks**

Run:

```powershell
python scripts/data/generate_edge_mapping.py
python scripts/validation/check_seed_repro.py
python experiments/runner.py --help
python examples/run_fixed_time.py 1
python examples/run_ca_max_pressure.py 1 100
```

Expected: generators write to canonical destinations, seed check succeeds, CLI help lists six parameters, and both simulations exit 0.

- [ ] **Step 5: Validate Markdown links and runtime output compatibility**

Run the link checker from Task 4 and a short runner invocation using `--output-dir output/csv` (or the existing default) to confirm `output/csv/`, `output/logs/`, and `output/variants/` remain usable. Expected: zero missing local links and no runtime path regression.

- [ ] **Step 6: Review final diff without reverting user work**

Run `git status --short`, `git diff --stat`, and inspect all deletes/renames. Confirm only the planned reorganizations, path repairs, README/Markdown updates, and generated documentation changes are present. Do not commit in this task; report the result for the user's explicit commit decision.

## Self-Review Checklist

- [x] Spec coverage: all design sections (scripts, tests, docs, output, README rules, migration safeguards, and acceptance matrix) map to Tasks 1-7.
- [x] Placeholder scan: no unresolved-marker text or implementation placeholders are used as task instructions.
- [x] Type/path consistency: all new script commands use the category paths; all moved Python scripts use `parents[2]`; tests continue to run from `tests/`.
- [x] User constraint: no task commits or discards existing worktree changes.
