# Output Ownership

`output/` holds generated simulation material. Generated files remain ignored by
Git; only this file and `deliverables/README.md` are tracked.

## Runtime Outputs

Current runs retain these runtime-facing paths:

- `csv/` contains metrics CSV files, including the output from
  `python examples/run_fixed_time.py 1`.
- `logs/` contains simulation and event logs when a runner is configured to
  emit them there.
- `variants/` contains generated flow variants when a runner is configured to
  emit them there.

Use the run command's output-directory option when available to direct a new
run to the appropriate runtime directory. These directories are disposable
generated state and must not be treated as archival evidence.

## Historical Evidence

`archive/` preserves completed validation, experiment, and check evidence:

- `archive/validation/` contains historical `validate` and `validate_quick`
  runs.
- `archive/experiments/` contains the W3 audit, stress, and batch-smoke runs.
- `archive/checks/` contains seed/CLI checks, temporary pytest output, and IB
  disconnect logs.

Archive contents are retained for inspection and are not runtime input. Do not
overwrite an existing archive item; create a distinct evidence directory for a
new retained run. The validation commands `python scripts/validation/validate_all.py`
and `python scripts/validation/batch_validate.py` currently create fresh
working output at their configured legacy paths; archive a completed run only
after it is no longer needed as working state.

## Deliverables

`deliverables/` is reserved for submission-facing material. Its current state
and retention rule are documented in `deliverables/README.md`.
