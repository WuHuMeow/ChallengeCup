# Output Ownership

`output/` is the runtime root for generated simulation material. Generated files remain ignored by
Git; the only retained files are `output/README.md` and `output/deliverables/README.md`.

## Runtime Outputs

Commands create runtime-facing paths such as:

- `csv/` for metrics CSV files, including the output from
  `python examples/run_fixed_time.py 1`.
- `runs/` for run-scoped artifacts from `experiments.runner`, `RunService`, and matrix commands.
- `variants/` for generated flow variants when a runner is configured to
  emit them there.

Use the run command's output-directory option when available to direct a new
run to the appropriate runtime directory. These directories are disposable
generated state and must not be treated as archival evidence.

The historical 13-pass/0-fail acceptance record and the audited 360-run matrix are documented in
`docs/ia-ib-final-verification.md` and `docs/ia-ib-simulation-artifact-cleanup.md`. Their generated
artifacts and archives were removed; do not describe any generated directory as currently present.
Docker live and second-machine reproduction remain `not_run` evidence axes.

## Deliverables

`deliverables/` is reserved for submission-facing material. Its current state
and retention rule are documented in `deliverables/README.md`.
