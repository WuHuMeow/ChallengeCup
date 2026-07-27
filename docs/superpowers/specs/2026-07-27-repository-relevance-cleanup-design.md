# Repository Relevance Cleanup Design

**Date:** 2026-07-27

## Goal

Remove files that are unrelated to the current project or are byte-identical
duplicates, while preserving every asset needed for development, PDF alignment,
IA/IB verification, internal collaboration, and future reproduction.

## Preservation Boundary

The cleanup must preserve:

- `.git/` and `.venv/`;
- the competition PDF under `docs/pdf/`;
- both `data/intersection_data.zip` and the extracted 20-intersection dataset;
- source code, configuration, tests, deployment files, and dependency manifests;
- active documentation, IA/IB evidence, dated design records, and weekly tasks;
- the two tracked `output/` README files.

Generated simulation data must not be recreated.

## Tracked Repository Cleanup

Delete the redundant placeholders `report/.keep` and `slides/.keep`. The report
directory already contains a real report, while the empty slides placeholder has
no current artifact or runtime role.

Use `docs/architecture/images/` as the single canonical architecture-image
directory. Update all active and historical Markdown references that currently
point to `docs/superpowers/specs/images/`, then delete the byte-identical duplicate
files from that directory. Historical prose remains unchanged apart from link
targets needed to keep local links valid.

## Local-Only Cleanup

Delete these ignored or empty local artifacts after resolving and validating each
target beneath the repository root:

- `.worktrees/ia-ib-completion/`, which is an unregistered stale copy and has no
  independent Git metadata;
- `.pytest_cache/`;
- `.superpowers/` local review and browser scratch files;
- empty `tmp/` and `unused/` directories.

The local `.venv/` remains because it is the verified test environment.

## Safety Rules

- Inspect the final candidate list before deletion.
- Use Git deletion for tracked files so every removal is recoverable from history.
- Do not use force-push, history rewriting, or broad unresolved deletion targets.
- Do not delete registered worktrees or files with uncommitted project changes.
- Stop if a candidate differs from the inventory recorded in this design.

## Verification

After cleanup:

1. Confirm no Markdown reference points to the removed image directory.
2. Strictly decode every Markdown file as UTF-8 and validate every active local
   Markdown link.
3. Confirm `output/` still contains only its two README files.
4. Run all 198 tests, compile the Python packages, import the public packages,
   run flake8 with the repository's 100-character limit, and run `git diff --check`.
5. Review the deletion diff to confirm no protected project asset was removed.
6. Commit on `main`, push normally to GitHub, and compare local and remote hashes.

## Success Criteria

The repository retains all project and reproduction assets, contains one canonical
copy of each architecture image, has no empty tracked placeholders, passes the full
verification suite, and matches GitHub `main` after a normal push.
