# Output Ownership

`output/` is the runtime root for generated simulation material and release
evidence. Generated files remain ignored by Git. Directory-level `README.md`
files may be tracked to define their evidence contract without committing
machine-specific results.

## Runtime Outputs

Commands create runtime-facing paths such as:

- `csv/` for metrics CSV files, including the output from
  `python examples/run_fixed_time.py 1`.
- `runs/` for run-scoped artifacts from `experiments.runner`, `RunService`, and matrix commands.
- `variants/` for generated flow variants when a runner is configured to
  emit them there.

Use the run command's output-directory option when available to direct a new
run to the appropriate runtime directory. `runs/`, `tmp/`, `pytest-*`, and
legacy experiment results are disposable state. They are not release evidence.

`evidence/` contains only evidence produced under the current release
contracts. A status is `pass` only after the corresponding command has run on
the current code and artifacts; otherwise it is `fail` or `not_run`.

## Deliverables

`deliverables/` is reserved for submission-facing material. Its current state
and retention rule are documented in `deliverables/README.md`.

## Preserved Inputs

`赛题资料.7z` and `data/intersection_data/` are official read-only inputs.
Cleanup and packaging tools may reference and audit them, but must never
overwrite, repack, or remove them. `scripts/release/output_policy.py` exposes a
read-only audit; it intentionally has no deletion operation.
