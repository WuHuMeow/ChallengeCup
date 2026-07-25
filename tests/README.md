# Test Suites

Run the complete suite from the repository root:

```powershell
python -m pytest tests/
```

The suite currently collects 114 tests (the exact count is reported by pytest and may
increase when a new contract test is added).

The suite includes isolated tests for algorithms, cloud policy, data types, bridge
helpers, artifact contracts, validation scripts, and Docker static consistency, plus
integration tests that cross application boundaries.

Integration tests that exercise a real simulation environment require SUMO 1.18
or newer, with `SUMO_HOME` configured and the SUMO binaries available on `PATH`.
The repository's fixture-based integration tests can run without starting SUMO.

Known slower coverage is concentrated in `integration/test_scenes.py`, which
loads the full scene registry and parses scenario XML fixtures. Run it directly
when iterating on scene changes:

```powershell
python -m pytest tests/test_scenes.py
```
