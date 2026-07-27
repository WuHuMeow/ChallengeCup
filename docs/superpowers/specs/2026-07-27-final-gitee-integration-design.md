# Final Gitee Integration Design

## Goal

Finish IA/IB locally, remove generated simulation artifacts after the final
successful audit, merge the Gitee history, and publish the result to GitHub
without rewriting either repository's history.

## Verified Starting Point

- Local branch: `main` at `a4a68df`, ahead of `origin/main`.
- Gitee source: `fyx0927/challenge-cup`, branch `master`, at `522fcbd`.
- Common ancestor: `17d3873`.
- Final IA/IB verifier: 13 checks passed, zero failed, matrix mode `audited`.
- External evidence remains truthful: Docker and second-machine checks are
  `not_run`.

## Cleanup Boundary

Delete generated content under `output/`, including the 360-run matrix,
verification outputs, test caches, figures, stress runs, and
`output/archives/ia-ib-simulation-evidence-2026-07-27.tar.zst`.

Preserve the tracked repository placeholders:

- `output/README.md`
- `output/deliverables/README.md`

Do not delete source inputs or runnable configuration under `data/`,
`engine/configs/`, `config/`, or `docs/pdf/`. Remove the obsolete duplicate
`docs/reports/ia-ib-final-verification.md`; retain the canonical generated
report at `docs/ia-ib-final-verification.md`.

Record the cleanup in `docs/ia-ib-simulation-artifact-cleanup.md`, including
the final verifier counts, the archive size and SHA-256, exact deleted roots,
and regeneration guidance.

## Merge Strategy

Use a normal Git merge from Gitee `master` into local `main`. This preserves
both histories and makes Gitee's flat top-level layout the shared base:
`core/`, `engine/`, `algorithms/`, `api/`, `cloud/`, `experiments/`, `ml/`,
`scenes/`, `scripts/`, `tests/`, and `visualization/`.

Keep the newer local IA/IB implementation and tests at those paths. Preserve
Gitee-only structure such as `slides/`. The merge preview has one add/add
conflict in `report/实验评估报告.md`; both working-tree contents are equal, so
the conflict can be resolved without changing report content.

## Verification And Publication

After the merge, run all 198 repository tests, compile all Python modules,
run import checks, run flake8, and run `git diff --check`. Do not regenerate
the deleted 360-run matrix. Verify that the Gitee merge changes no Python
implementation relative to the pre-merge tree.

Before publishing, fetch GitHub and require `origin/main` to remain an
ancestor of local `main`. Push with a normal `git push origin main`; do not
force-push. Verify the remote `main` hash equals local `HEAD`.
