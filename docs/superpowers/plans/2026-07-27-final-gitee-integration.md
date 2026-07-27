# Final Gitee Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove verified simulation artifacts, merge Gitee `master` into local `main` using Gitee's flat layout, and publish the verified result to GitHub.

**Architecture:** Preserve the current flat module implementation and both repositories' Git history. Generated simulation data is removed only after recording the successful final audit; Gitee is merged normally and GitHub is updated by fast-forward push.

**Tech Stack:** Git, PowerShell, Python 3.12, pytest, flake8, SUMO evidence JSON.

## Global Constraints

- Preserve `data/`, `engine/configs/`, `config/`, and `docs/pdf/` source inputs.
- Preserve `output/README.md` and `output/deliverables/README.md`.
- Delete all other generated `output/` content and the simulation archive.
- Delete obsolete `docs/reports/ia-ib-final-verification.md`.
- Preserve canonical `docs/ia-ib-final-verification.md` and write a cleanup record.
- Merge Gitee history normally; never force-push GitHub.
- Keep Docker and second-machine evidence marked `not_run`.

---

### Task 1: Commit Final Audit And Integration Documents

**Files:**
- Modify: `docs/ia-ib-final-verification.md`
- Create: `docs/superpowers/specs/2026-07-27-final-gitee-integration-design.md`
- Create: `docs/superpowers/plans/2026-07-27-final-gitee-integration.md`

**Interfaces:**
- Consumes: `output/verification/final-sharded/verification.json`.
- Produces: committed pre-deletion verification provenance and execution instructions.

- [ ] **Step 1: Confirm final audit result**

Run: parse `output/verification/final-sharded/verification.json` and require 13
`pass`, zero `fail`, matrix `pass/audited`, and Docker `not_run`.

- [ ] **Step 2: Check documentation changes**

Run: `git diff --check -- docs/ia-ib-final-verification.md docs/superpowers`

Expected: exit code 0.

- [ ] **Step 3: Commit only the canonical report and integration documents**

```text
docs: record final pre-cleanup IA and IB audit
```

Expected: the obsolete report remains unstaged for Task 2.

### Task 2: Remove Generated Simulation Artifacts

**Files:**
- Delete: generated children of `output/`
- Preserve: `output/README.md`
- Preserve: `output/deliverables/README.md`
- Delete: `docs/reports/ia-ib-final-verification.md`
- Create: `docs/ia-ib-simulation-artifact-cleanup.md`

**Interfaces:**
- Consumes: final audit counts and archive checksum.
- Produces: source-only repository plus durable cleanup record.

- [ ] **Step 1: Resolve and review exact deletion targets**

List every direct child under `output/` except `README.md` and `deliverables`.
Resolve each path and require its parent to equal the repository `output/`
directory. List non-README children under `output/deliverables/` separately.

- [ ] **Step 2: Delete only the reviewed targets**

Use PowerShell `Remove-Item -LiteralPath <exact-target> -Recurse -Force` for
each reviewed directory. Delete non-README files in `output/deliverables/`.

- [ ] **Step 3: Verify cleanup boundary**

Run: `git status --ignored --short -- output`

Expected: only the two tracked README files remain and no generated simulation
files or archive exists.

- [ ] **Step 4: Write cleanup record and remove obsolete report**

The record must include:

- 13 passed, zero failed, matrix `pass/audited`.
- Docker and second-machine `not_run`.
- Archive size `3,528,353,078` bytes.
- SHA-256 `DB6AE0A4E31DAB8AD1356AC02E24534BA58547FAD921397113FEAECCE610E0B6`.
- Deleted roots `output/verification` and `output/archives` plus other generated
  `output/` children.
- Regeneration command `python scripts/run_pdf_matrix.py --output-root <path>`.

- [ ] **Step 5: Commit cleanup**

```text
chore: remove generated simulation artifacts
```

### Task 3: Merge Gitee Master

**Files:**
- Merge: `https://gitee.com/fyx0927/challenge-cup.git`, branch `master`
- Resolve: `report/实验评估报告.md` if Git reports the previewed add/add conflict

**Interfaces:**
- Consumes: Gitee `master` at `522fcbd` and clean local `main`.
- Produces: one history-preserving merge commit on local `main`.

- [ ] **Step 1: Add or verify Gitee remote and fetch `master`**

Run: `git fetch gitee master`

Expected: `gitee/master` resolves to `522fcbd` unless the remote advanced; if
it advanced, inspect new commits before merging.

- [ ] **Step 2: Merge without committing automatically**

Run: `git merge --no-ff --no-commit gitee/master`

Expected: no code conflict; at most the previewed report add/add conflict.

- [ ] **Step 3: Resolve the report conflict without content loss**

Compare stage 2 and stage 3 blobs. If normalized contents are equal, keep the
working-tree content and stage the file. No new report behavior is invented.

- [ ] **Step 4: Verify merge tree before commit**

Run: `git diff --check` and compare Python paths with the pre-merge commit.

Expected: no whitespace errors and no Gitee regression to IA/IB code.

- [ ] **Step 5: Commit merge**

```text
merge: integrate Gitee master structure
```

### Task 4: Verify Merged Source Without Regenerating Matrix Data

**Files:**
- Read: all Python packages, tests, configuration, and Git diff.
- Modify: only defects caused by the merge.

**Interfaces:**
- Consumes: merged source-only tree.
- Produces: publishable GitHub `main`.

- [ ] **Step 1: Run all tests**

Run: bundled Python with `.venv/Lib/site-packages`, `pytest tests -q -p no:cacheprovider`.

Expected: 198 tests pass.

- [ ] **Step 2: Run compilation and imports**

Run: `python -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization`.

Run: import all listed packages.

Expected: both commands exit 0.

- [ ] **Step 3: Run lint and Git checks**

Run: `python -m flake8 algorithms api cloud core engine experiments scenes scripts visualization --max-line-length=100`.

Run: `git diff --check`.

Expected: both commands exit 0.

### Task 5: Publish GitHub Main

**Files:**
- Update remote ref: `https://github.com/WuHuMeow/ChallengeCup.git`, branch `main`

**Interfaces:**
- Consumes: verified local `main` and unchanged GitHub base.
- Produces: GitHub `main` equal to local `HEAD`.

- [ ] **Step 1: Fetch and verify remote ancestry**

Run: `git fetch origin main` and `git merge-base --is-ancestor origin/main HEAD`.

Expected: exit code 0; inspect and stop if GitHub advanced incompatibly.

- [ ] **Step 2: Check tracked object sizes**

Require no new Git object over GitHub's 100 MB per-file limit.

- [ ] **Step 3: Push normally**

Run: `git push origin main`.

Expected: fast-forward update; no force option.

- [ ] **Step 4: Verify remote hash**

Run: `git ls-remote https://github.com/WuHuMeow/ChallengeCup.git refs/heads/main`.

Expected: remote hash equals local `HEAD`.
