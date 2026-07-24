# Test Suites

Run the complete suite from the repository root:

```powershell
python -m pytest tests/
```

The suite is expected to collect 66 tests.

`unit/` contains isolated tests for algorithms, cloud policy, data types, and
bridge helpers. `integration/` contains tests that cross application boundaries,
including the API, scene registry, experiment interface, event flow, and
simulation bridge behavior.

Integration tests that exercise a real simulation environment require SUMO 1.18
or newer, with `SUMO_HOME` configured and the SUMO binaries available on `PATH`.
The repository's fixture-based integration tests can run without starting SUMO.

Known slower coverage is concentrated in `integration/test_scenes.py`, which
loads the full scene registry and parses scenario XML fixtures. Run it directly
when iterating on scene changes:

```powershell
python -m pytest tests/integration/test_scenes.py
```
