# Task 8 review fix round 1: request/foes link-index mapping

Date: 2026-08-20

## Scope

`junction/request@index` indexes the junction's `intLanes`, not TraCI's
controlled `connection@linkIndex`. The correction maps each request lane to
the controlled link which reaches it, following a single unambiguous internal
connection chain. `ConflictDefinition` therefore retains TraCI-controlled link
indices. Networks without `intLanes` retain the previous request-index fallback
and their stop-line-to-exit geometry fallback.

No official input was edited: `data/intersection_data/` and `赛题资料.7z` are
outside the changed files. This mapping correction is part of the existing
uncommitted Task 8 review-fix range and will be committed with that range.

## TDD evidence

Initial command attempted with the system Python:

```powershell
python -m pytest tests/test_traci_outputs.py -q -k 'map_junction_internal_lanes_to_controlled_link_indices'
```

Output: `Python314\\python.exe: No module named pytest`. The project test
interpreter is `.venv\\Scripts\\python.exe` (Python 3.12.13), so the behavior
test was rerun there.

RED command:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_traci_outputs.py -q -k 'map_junction_internal_lanes_to_controlled_link_indices' --basetemp=.t8-red-link-index
```

RED output: `1 failed, 30 deselected in 1.07s`. The new fixture has request
indices `0, 1`, junction internal lanes reached by controlled link indices `7,
9`, and internal chains before each junction lane. Before the fix, the actual
definitions were `[]`; the fixed assertion is `[(7, 9)]`.

GREEN command:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_traci_outputs.py -q -k 'map_junction_internal_lanes_to_controlled_link_indices' --basetemp=.t8-green-link-index -p no:cacheprovider
```

GREEN output: `1 passed, 30 deselected in 0.62s`.

The first expanded focused run exposed three existing fallback fixtures that do
not declare `intLanes`. The minimum compatibility branch was added only for
that absence, then rerun:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_traci_outputs.py tests/test_safety_metrics.py tests/test_movement_state.py -q --basetemp=.t8-focused-link-index-final -p no:cacheprovider
```

Output: `55 passed in 1.96s`.

## Official scene preflight

The final read-only inline preflight used `SceneRegistry().list_scenes(formal_only=True)`.
For every scene it independently converted `request/foes` through
`junction@intLanes` and internal connection chains into controlled link-index
pairs, instantiated `RunArtifacts` beneath `.t8-preflight-link-index-verified2`,
asserted every SUMO command output token was redirected under that run
directory, and asserted actual `bridge.conflict_definitions` was nonempty and
covered every mappable pair. SUMO was not started; official source directories
were read only.

```text
scene  mappable  actual
1      68        68
2      5         5
3      38        38
4      28        28
5      6         6
6      30        30
7      6         6
8      44        44
9      53        53
10     6         6
11     68        68
12     88        88
13     12        12
14     6         6
15     76        76
16     52        52
17     10        10
18     88        88
19     45        45
20     68        68
TOTAL  797       797
```

Final preflight output: `SCENES 20`, `TOTALS 797 797`; all assertions passed.

## Full verification

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -q --basetemp=.t8-full-link-index -p no:cacheprovider
```

Output: `409 passed in 86.78s (0:01:26)`.

## Self-review

- Request mapping uses `intLanes[request_index]` when available; it never
  assumes request index equals controlled `linkIndex` in a real internal-link
  network.
- Controlled routes collect the direct `via` lane and unambiguous successors;
  the visited lane list prevents a malformed cyclic internal chain from
  looping indefinitely.
- Concatenated internal-lane geometry provides conflict offsets from the first
  controlled lane, while the pre-existing no-`via` lane-endpoint fallback is
  unchanged.
- The regression fixture asserts the public `ConflictDefinition` indices
  directly and hard-codes `(7, 9)`, so a request-index implementation cannot
  satisfy it.

## Changed files

- `engine/traci_bridge.py`
- `tests/test_traci_outputs.py`
- `.superpowers/sdd/2026-08-18-judge-facing-final-release/task-8-report.md`

## Controller final verification

The controller independently reran the final working tree after the mapping
fix:

- Plan-focused tests: `59 passed in 1.73s`.
- Expanded focused tests: `120 passed in 2.98s`.
- Full suite: `409 passed in 86.28s`.
- Real TraCI preflight: all 20 official scenes started; all movement
  capacities were positive; every incoming-lane turn-ratio sum was 1; all
  scenes had conflicts; 797 independently mapped request/foe pairs matched
  797 conflict definitions exactly.
- Real RunService smoke: intersection 1, `fixed_time`, 100 steps, seed 42,
  run `a9aaca9ee48b` completed at 100.0 simulation seconds. `collisions.xml`
  and all required outputs were non-empty; safety-event steps matched the
  real step; `red_light=0` and `illegal_transition=0`.
- System Python 3.14.7 compileall and `git diff --check` exited 0.
- Protected archive SHA-256 remained
  `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`;
  official scene data remained 163 tracked files with no protected-path diff.

Task 8 remains in progress until the complete review-fix commit receives a
clean scoped independent re-review.
