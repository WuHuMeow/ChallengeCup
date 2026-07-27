# IA/IB Simulation Artifact Cleanup

## Final Verification Before Cleanup

The final local IA/IB verification completed successfully on 2026-07-27
before generated artifacts were removed:

- 13 checks passed.
- 0 checks failed.
- The 360-run matrix check passed in `audited` mode.
- Docker live verification remained `not_run`.
- Second-machine reproduction remained `not_run`.

The detailed pre-cleanup result is recorded in
`docs/ia-ib-final-verification.md` and commit `fa67904`.

## Deleted Artifacts

The following generated paths were deleted after verification:

- `output/verification/`
- `output/archives/`

No generated simulation result was found outside `output/`. Source inputs and
runnable SUMO configurations under `data/`, `engine/configs/`, `config/`, and
`docs/pdf/` were preserved. The tracked placeholders `output/README.md` and
`output/deliverables/README.md` were also preserved.

The deleted archive had been validated before deletion:

- Name: `ia-ib-simulation-evidence-2026-07-27.tar.zst`
- Size: `3,528,353,078` bytes
- SHA-256: `DB6AE0A4E31DAB8AD1356AC02E24534BA58547FAD921397113FEAECCE610E0B6`
- Archive entries: `8,693`
- Zstandard integrity check: passed

## Regeneration

Regenerating the complete matrix can require roughly 70 GB of storage:

```powershell
python scripts/run_pdf_matrix.py `
  --output-root output/verification/regenerated-matrix
```

After regeneration, run the acceptance verifier against its matrix CSV:

```powershell
python scripts/verify_ia_ib.py `
  --output-root output/verification/regenerated-final `
  --matrix-csv output/verification/regenerated-matrix/matrix.csv
```
