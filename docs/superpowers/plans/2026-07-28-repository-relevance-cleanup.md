# Repository Relevance Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove only unrelated, empty, or byte-identical duplicate artifacts while preserving the project's code, data, evidence, and internal documentation.

**Architecture:** Keep `docs/architecture/images/` as the single canonical image directory. Rewrite every Markdown link that targets the duplicate image directory, then remove the duplicate files and empty tracked placeholders. Clean ignored local scratch directories separately from the Git-tracked change.

**Tech Stack:** Git, PowerShell, Markdown, Python 3.12, pytest, flake8.

## Global Constraints

- Preserve `.venv/`, `docs/pdf/`, `data/intersection_data.zip`, `data/intersection_data/`, source code, tests, manifests, active docs, IA/IB evidence, dated plans, and weekly tasks.
- Do not regenerate simulation data.
- Do not force-push or rewrite history.
- Remove local directories only after resolving their exact paths under the repository root.
- Use `docs/architecture/images/` as the only retained architecture-image directory.

---

### Task 1: Reconfirm the candidate inventory

**Files:**
- Read: `docs/superpowers/specs/2026-07-27-repository-relevance-cleanup-design.md`
- Read: `docs/architecture/images/`
- Read: `docs/superpowers/specs/images/`

**Interfaces:**
- Consumes: the approved cleanup design and current repository state.
- Produces: a verified list of two tracked placeholders, nine duplicate images, and five local scratch targets.

- [ ] **Step 1: Confirm the worktree is clean and on `main`**

Run:

```powershell
git status --short --branch
git branch --show-current
```

Expected: no status entries and branch `main`.

- [ ] **Step 2: Confirm protected assets exist**

Run:

```powershell
Test-Path 'docs/pdf/XH-202613_面向雄安新区“城市大脑”的车路云.pdf'
Test-Path 'data/intersection_data.zip'
Test-Path 'data/intersection_data'
Test-Path '.venv'
```

Expected: four `True` results.

- [ ] **Step 3: Confirm every duplicate image has a canonical same-hash copy**

For each file in `docs/superpowers/specs/images/`, compare its SHA-256 hash with the same basename in `docs/architecture/images/`. Stop if any pair differs or is missing.

### Task 2: Rewrite Markdown image references

**Files:**
- Modify: `README.md`
- Modify: `docs/总路线.md`
- Modify: `docs/tasks/roadmap.md`
- Modify: `docs/superpowers/specs/2026-07-14-readme-redesign-design.md`
- Modify: `docs/superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md`
- Modify: `docs/superpowers/plans/2026-07-14-readme-redesign-plan.md`
- Modify: `docs/superpowers/specs/2026-07-27-repository-relevance-cleanup-design.md`

**Interfaces:**
- Consumes: canonical assets in `docs/architecture/images/`.
- Produces: valid relative links with no Markdown reference to `docs/superpowers/specs/images/` or its relative aliases.

- [ ] **Step 1: Apply exact path replacements**

Use these mappings, preserving each image basename:

```text
README.md: docs/superpowers/specs/images/ -> docs/architecture/images/
docs/总路线.md: superpowers/specs/images/ -> architecture/images/
docs/tasks/roadmap.md: ../superpowers/specs/images/ -> ../architecture/images/
docs/superpowers/specs/*.md: ./images/ -> ../../architecture/images/
docs/superpowers/plans/2026-07-14-readme-redesign-plan.md: ../specs/images/ -> ../../architecture/images/
```

In the cleanup design, replace the removed-directory path in prose with “the duplicate image directory” so the audit does not retain a stale path.

- [ ] **Step 2: Confirm the old image directory is no longer referenced**

Run:

```powershell
rg -n 'docs/superpowers/specs/images|superpowers/specs/images|\.\./specs/images|\./images/' README.md docs -g '*.md'
```

Expected: no output.

### Task 3: Remove tracked redundant files

**Files:**
- Delete: `report/.keep`
- Delete: `slides/.keep`
- Delete: all nine files under `docs/superpowers/specs/images/`

**Interfaces:**
- Consumes: the reference rewrite from Task 2 and canonical image copies.
- Produces: one image copy per architecture asset and no empty tracked placeholders.

- [ ] **Step 1: Review the exact deletion list**

Run:

```powershell
git -c core.quotepath=false ls-files report/.keep slides/.keep docs/superpowers/specs/images
```

Expected: exactly 11 tracked paths: two placeholders and nine duplicate images.

- [ ] **Step 2: Delete only the reviewed tracked paths**

Run:

```powershell
git rm -- report/.keep slides/.keep
git rm -- docs/superpowers/specs/images/architecture.png docs/superpowers/specs/images/architecture.svg docs/superpowers/specs/images/dependencies.svg docs/superpowers/specs/images/simulation-loop.png docs/superpowers/specs/images/simulation-loop.svg docs/superpowers/specs/images/team-org.png docs/superpowers/specs/images/team-org.svg docs/superpowers/specs/images/timeline.png docs/superpowers/specs/images/timeline.svg
```

Expected: Git stages only the reviewed 11 deletions.

### Task 4: Remove local scratch artifacts

**Files:**
- Delete locally: `.worktrees/ia-ib-completion/`
- Delete locally: `.pytest_cache/`
- Delete locally: `.superpowers/`
- Delete locally: empty `tmp/`
- Delete locally: empty `unused/`

**Interfaces:**
- Consumes: exact repository-root paths validated before deletion.
- Produces: no local stale worktree or tool scratch data; `.venv/` remains untouched.

- [ ] **Step 1: Verify the stale worktree is an unregistered copy**

Run:

```powershell
git worktree list --porcelain
Test-Path '.worktrees/ia-ib-completion/.git'
git -C '.worktrees/ia-ib-completion' status --short --branch
```

Expected: only the main worktree is registered, the nested `.git` path is absent, and the copied directory has no uncommitted status entries.

- [ ] **Step 2: Resolve and remove exact local targets**

For each target, resolve its absolute path, require that it is directly beneath the repository root, and remove only that target. Do not remove `.venv/` or any repository parent.

- [ ] **Step 3: Confirm local cleanup boundaries**

Run:

```powershell
Test-Path '.venv'
Test-Path '.worktrees/ia-ib-completion'
Test-Path '.pytest_cache'
Test-Path '.superpowers'
```

Expected: `.venv` is `True`; the three removed directories are `False`.

### Task 5: Run the complete verification suite

**Files:**
- Test: all changed Markdown and Git paths.
- Test: `tests/` and Python packages.

**Interfaces:**
- Consumes: the cleaned working tree.
- Produces: fresh evidence suitable for commit and push.

- [ ] **Step 1: Validate Markdown encoding, links, and stale references**

Run the repository's strict UTF-8 and local-link checks, then:

```powershell
rg -n 'docs/superpowers/specs/images|superpowers/specs/images|\.\./specs/images|\./images/' README.md docs -g '*.md'
git diff --check
```

Expected: UTF-8 and link checks pass, the stale-reference search is empty, and diff check exits 0.

- [ ] **Step 2: Run Python tests and static checks**

Run with the existing `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m compileall -q algorithms api cloud config core engine experiments ml scenes scripts visualization
.\.venv\Scripts\python.exe -c "import algorithms, api, cloud, config, core, engine, experiments, ml, scenes, scripts, visualization; print('imports ok')"
.\.venv\Scripts\python.exe -m flake8 algorithms api cloud config core engine experiments ml scenes scripts tests visualization --max-line-length=100
```

Expected: `198 passed`, `imports ok`, and zero compile or lint errors.

- [ ] **Step 3: Review the staged deletion diff**

Run:

```powershell
git diff --cached --stat
git diff --cached --name-status
git status --short --branch
```

Expected: only the reviewed placeholder/image deletions plus the intended Markdown reference edits are staged; protected assets are absent from the deletion list.

### Task 6: Commit and push the cleanup

**Files:**
- Commit: the staged cleanup changes.

**Interfaces:**
- Consumes: verification evidence from Task 5.
- Produces: a normal cleanup commit on `main` published to GitHub.

- [ ] **Step 1: Commit the cleanup**

Run:

```powershell
git commit -m "chore: remove unrelated repository artifacts"
```

Expected: one new cleanup commit.

- [ ] **Step 2: Push normally**

Run:

```powershell
git push origin main
```

Expected: GitHub accepts a normal update; no force option is used.

- [ ] **Step 3: Verify local and remote identity**

Compare `git rev-parse HEAD` with `git ls-remote origin refs/heads/main`, then verify a clean worktree and that the only local branch is `main`.
