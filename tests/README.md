# Test Suites

Run the complete suite from the repository root:

```powershell
python -m pytest tests/
```

The exact count is reported by pytest and increases when a new contract test is added.

The suite includes isolated tests for algorithms, cloud policy, data types, bridge
helpers, artifact contracts, validation scripts, and Docker static consistency, plus
integration tests that cross application boundaries.

Integration tests that exercise a real simulation environment require SUMO 1.18
or newer, with `SUMO_HOME` configured and the SUMO binaries available on `PATH`.
The repository's fixture-based integration tests can run without starting SUMO.

The suite also checks the active documentation, canonical `/api/*` contract,
`docs/api/openapi.json`, `docs/api/postman_collection.json`, resumable PDF matrix,
offline packaging, Docker static consistency, exact metric null semantics, and the
run-scoped artifact layout:

```text
<root>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/
```

Known slower coverage is concentrated in `integration/test_scenes.py`, which
loads the full scene registry and parses scenario XML fixtures. Run it directly
when iterating on scene changes:

```powershell
python -m pytest tests/test_scenes.py
```

Run IA/IB live acceptance separately; these checks start real SUMO processes and may
run Docker when available:

```powershell
python scripts/verify_ia_ib.py --quick --output-root output/runs/ia-ib-quick
python scripts/verify_ia_ib.py --output-root output/runs/ia-ib-full
```

Live acceptance uses `pass`, `fail`, and `not_run`. A missing Docker executable or
second-machine run is `not_run`, not a test pass.

These commands create disposable output roots. The retained acceptance record reports 13 checks
`pass`, 0 `fail`, and an audited 360-run matrix; its generated artifacts were removed. Docker live
and second-machine reproduction remain `not_run` in that record.
