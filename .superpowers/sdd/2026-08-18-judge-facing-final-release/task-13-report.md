# Task 13 Implementation Report

Date: 2026-08-22

Branch: `codex/judge-final-release`

Baseline: `ea8b1a919a5584c066b92e707ccee959ee7b7085`

## Current Code Evidence Head

The current Task 13 code evidence head is
`d1edd109916a3372cab5dfcbd367df7f7b10dbb3`. The additive code/test commits are:

- `c9da80b4f670809ccd4310b07d160c267ad09e80` —
  `feat: define run-scoped evidence and metric semantics`
- `5ee5a667dd98631200dee4ecb8a104243e8d53fd` —
  `fix: record SUMO server version`
- `9b74a61c70ea9bbbfa6525a17f42aa765879524d` —
  `fix: close task 13 final review findings`
- `b1a1ec72efe74f2629b1096aa3bba3f9dca441bb` —
  `fix: bind task 13 consumers to sealed evidence`
- `d1edd109916a3372cab5dfcbd367df7f7b10dbb3` —
  `fix: publish validated figure sets atomically`

The first post-implementation real-SUMO attempt exposed the version-tuple bug
described below. Its run and PID are historical RED evidence only. The
pre-review `5ee5a66` and the first review-closing `9b74a61` verification are
also historical/superseded after the two later code/test fixes. All latest
verification and the authoritative real-SUMO evidence in this report bind to
`d1edd109916a3372cab5dfcbd367df7f7b10dbb3`.

## Outcome

Task 13 defines a versioned, run-scoped evidence contract without replacing
Task 12's lifecycle artifacts. Every production-managed run begins provisional
evidence before SUMO startup, records runtime provenance after the exact child
and server are known, materializes raw outputs and the canonical metric summary
before a successful terminal transition, then seals the final terminal files
with SHA-256 hashes. Failed and interrupted runs preserve truthful partial
evidence and a failure reason but cannot be mistaken for publishable completed
evidence.

`EvidenceReader` is the single fail-closed boundary for canonical resume and
visualization consumers. It validates identity, provenance, status, metadata,
timebase, schemas, hashes, paths, XML, CSV, canonical metric semantics, and
completion requirements. Optional figures and variant artifacts remain
additive and do not weaken the required evidence set.

The implementation reuses `core.types.MetricSummary`; the brief's
`RunSummary` name was treated as a type-name error rather than introducing a
second incompatible summary model. Minimal plan-outside changes in
`engine/runner.py`, `engine/run_service.py`, and their direct regression tests
were required to connect the contract to actual production runs.

## Evidence Contract and Ownership

The additive contract preserves `manifest.json`, `status.json`, and
`run_metadata.json`, and adds versioned `provenance.json`, canonical raw SUMO
outputs, `metrics.csv`, `simulation_log.csv`, `events.csv`, `summary.json`, and
`hashes.json`.

The writer lifecycle is deliberately split:

1. `begin()` writes provisional manifest/provenance and establishes the run
   identity before startup.
2. `update_runtime()` records the exact runtime identity, including the actual
   SUMO server version and timebase.
3. `finalize()` atomically materializes snapshots and the canonical summary
   before a would-be completed terminal state is committed.
4. Task 12 writes final `status.json` and `run_metadata.json`.
5. `seal()` hashes every required final artifact except `hashes.json` itself.

This ordering prevents a completed status from advertising missing outputs and
prevents a hash manifest from becoming stale when terminal lifecycle files are
written. A secondary evidence, metadata, status, seal, or cleanup failure does
not mask the primary run failure or `BaseException`. If persistence of a
terminal status fails, the in-memory state still moves monotonically to a
terminal state without claiming publishable evidence.

Lifecycle completion and evidence publishability remain separate contracts.
A custom injected runner that is not marked `evidence_managed` may complete its
lifecycle for compatibility, but `EvidenceReader` and `is_complete()` always
reject it as canonical completed evidence.

## Metric Semantics

`MetricSummary.from_raw_outputs()` now freezes the following rules:

- warmup is measured in simulation seconds, not row counts;
- time-series and events aggregate only samples at or after the warmup time;
- a completed trip counts only when `depart >= warmup_seconds` and arrival is
  non-negative;
- unfinished vehicles are counted separately and never enter throughput or
  completed-vehicle averages;
- fuel remains in millilitres and CO2 is independently converted from
  milligrams to grams;
- collision, red-light, illegal-transition, harsh-braking, teleport, and
  potential-conflict counts are explicit in every canonical summary;
- the serialized summary and raw-derived summary must agree exactly under the
  schema's numeric and finiteness rules.

## Fail-Closed Reader Boundary

The final reader rejects, as `EvidenceIssue` values rather than uncaught parser
errors:

- missing, empty, malformed, or wrongly typed required JSON/CSV/XML artifacts;
- booleans where the schema requires integers or numbers, non-finite values,
  inconsistent status, timebase, run identity, commit, scene, or runtime fields;
- unsafe hash paths, invalid algorithms/digests, missing canonical mappings,
  content mismatches, and required artifacts omitted from `hashes.json`;
- direct symlinks/junctions and ancestor reparse points that can escape the run
  directory;
- invalid tripinfo, emissions, queue, or safety XML and CSV row/schema errors,
  including per-row event run-id/time inconsistencies;
- terminal outputs carrying `evidence_error`, or completed evidence whose raw
  outputs, summary, metadata, final status, or seal are incomplete.

`scripts/run_pdf_matrix.py` and `visualization/report.py` now consume only this
validated boundary. Legacy directories without Task 13 provenance and hashes
remain readable as files but cannot be resumed or presented as canonical
completed runs.

The post-review consumer closure binds every consumer to the exact validated
on-disk summary snapshot and request execution dimensions. API, tuning, live
matrix, IA/IB verification, and visualization therefore cannot publish a
caller-provided in-memory summary after the run directory has been validated.
Figure generation stages a complete validated set before atomic publication;
if validation, source stability, or the final swap fails, it publishes no
partial new set and preserves the previous publication.

The run-local SHA-256 seal detects accidental corruption and verifies internal
self-consistency. It is not a signature and does not claim authenticity against
an actor who can coordinately rewrite raw outputs, canonical summaries, and the
hash manifest. The Task 13 brief supplies no signing key, external digest, or
immutable store; release-level external anchoring is therefore an explicit
Task 22/24 packaging handoff rather than a hidden claim of this reader.

## TDD Evidence

### Baseline and RED

The fresh baseline at `ea8b1a9` was:

```text
655 passed in 107.88s
```

The first contract collection failed because `experiments.evidence` did not
exist. After adding only interface skeletons, the required behavior suite
remained RED as intended:

```text
7 failed in 0.54s
```

Subsequent focused RED phases exposed the missing boundaries before each
production repair:

```text
schema/parser expansion: 9 failed, 8 deselected
seal ordering: 1 failed, 16 deselected
canonical consumer validation: 2 failed
atomic CSV snapshot preservation: 2 failed
production lifecycle ownership: 6 failed in 4.49s
strict reader breaker: 8 failed, 21 passed, 1 skipped
lifecycle breaker: 10 failed
status persistence breaker: 2 failed
SUMO server-version tuple: 1 failed
final-review strict evidence/reparse/events group: 11 failed
final-review RunService SystemExit terminalization: 1 failed
final-review matrix/tuning consumers: 2 failed
final-review single-run visualization consumer: 1 failed
controller API submit validation: 1 failed
controller live-result request identity: 1 failed
round-2 sealed-consumer and invalid-tuning publication boundaries: RED
round-3 figure-source stability and publication rollback boundaries: RED
```

The strict-reader rounds specifically forced coverage of unsafe/reparse paths,
all-row CSV validation, XML parsing, hash coverage, exact JSON types and
finiteness, metadata consistency, junction/ancestor traversal, and persisted
`evidence_error`. The lifecycle rounds forced coverage of early scene failure,
direct runner behavior, finalize/seal failures, `KeyboardInterrupt`, cancelled
futures, and persistent terminal-status write failure.

### GREEN

The corresponding focused milestones included:

```text
core evidence contract: 7 passed in 0.53s
evidence/metrics/artifacts/safety expansion: 56 passed in 0.96s
schema/parser group: 9 passed
seal group: 1 passed
strict reader re-review group: 41 passed
lifecycle breaker group: 10 passed
status persistence group: 2 passed
latest SUMO-version focused group: 75 passed in 29.90s
final-review API group: 14 passed
final-review evidence contract: 55 passed
final-review RunService: 34 passed
final-review runner channel: 36 passed
final-review lifecycle: 28 passed
final-review tuning/matrix: 20 passed
final-review visualization: 4 passed
final-review events/artifacts/metrics: 39 passed
round-2 sealed-consumer regression suite: GREEN (recorded by the exact-head
review and the full `b1a1ec7` gate below)
round-3 validated figure publication/rollback regressions: GREEN (recorded by
the exact-head review and the full `d1edd10` gate below)
```

The earlier controller affected suite on the submitted `9b74a61` behavior
returned (historical only):

```text
230 passed in 72.77s
```

## Latest Code-Head Verification

The controller reran the complete repository suite on exact code head
`d1edd109916a3372cab5dfcbd367df7f7b10dbb3` with a fresh repo-local base-temp
directory:

```text
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .task13-pytest-round3-full-d1edd10
771 passed in 158.25s
```

An earlier `9b74a61` latest-tree attempt deliberately used `D:\Temp` and returned
`4 failed, 738 passed`. All four failures were the same pre-existing
`FixedTimePlanResolver` repository-containment assertion: pytest's temporary
timing fixtures were outside the repository. No Task 13 assertion failed. The
fresh repo-local rerun above is the authoritative behavioral result.

Static and compatibility gates were:

```text
.\.venv\Scripts\python.exe --version
Python 3.12.13

.\.venv\Scripts\python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts tests visualization
exit 0

py -3.14 --version
Python 3.14.7

py -3.14 -m compileall -q algorithms api cloud core engine experiments ml scenes scripts tests visualization
exit 0

targeted flake8
exit 0

git diff --check ea8b1a9..HEAD
clean
```

All implementation commits used explicit code/test file lists. The final two
closure commits are `b1a1ec7` (13 code/test files) and `d1edd10` (5 code/test
files); their indexes were empty afterward. The controller ledger, report,
scratch directories, archive, and official data were not staged with code.

## Real SUMO Evidence

### Historical RED caught by the production gate

The first real-SUMO run after `c9da80b` completed all other evidence and process
checks, but stored `22` as the SUMO version. The installed TraCI API returns
`(22, "SUMO 1.27.1")`; the implementation had selected the protocol integer
instead of the server-version string. Run `3223b1418723` / PID `15488` is
therefore historical RED evidence only. A focused unit test reproduced the bug
before the additive `5ee5a66` fix.

### Historical pre-review run

The controller then ran a real fixed-time scene for exactly 100 simulation
seconds through the production `RunService` path:

```text
run_id: 968823f6861e
run_dir: D:\Temp\t13-real-sumo-100-final2\i1\fixed_time\x1\s42\968823f6861e
code commit: 5ee5a667dd98631200dee4ecb8a104243e8d53fd
result/status/metadata: completed
EvidenceReader issues: []
required non-empty artifacts: 13
SUMO version in manifest/metadata: 1.27.1
requested/derived steps: 100
requested/final simulation seconds: 100.0 / 100.0
step length: 1.0
warmup seconds: 0.0
simulation_log rows: 100
hash coverage: every required artifact except hashes.json itself
owned SUMO PID: 22312
exact PID alive after cleanup: false
SUMO PIDs before: []
SUMO PIDs after: []
```

Manifest and metadata identify the same exact child. The PID no longer existed
after cleanup, and no SUMO process residue was introduced. No process-name kill
was used.

This `968823f6861e` / PID `22312` run is valid historical evidence for
`5ee5a66`, but is superseded by the post-review latest-HEAD run below.

### Historical `9b74a61` authoritative run

```text
run_id: 074551e3bdc5
run_dir: D:\Temp\t13-real-sumo-100-9b74a61-20260822-112328\i1\fixed_time\x1\s42\074551e3bdc5
code commit: 9b74a61c70ea9bbbfa6525a17f42aa765879524d
result/status/metadata: completed
EvidenceReader issues: []
required non-empty artifacts: 13 / 13
SUMO version in manifest/metadata: 1.27.1
requested/derived steps: 100 / 100
requested/final simulation seconds: 100.0 / 100.0
step length: 1.0
warmup seconds: 0.0
simulation_log rows: 100
hash coverage: every required artifact except hashes.json itself
owned SUMO PID: 17200
exact PID alive after cleanup: false
SUMO PIDs before: []
SUMO PIDs after: []
```

Every programmed check returned true, manifest `code_commit` exactly matched
the then-current `9b74a61` HEAD, the exact owned PID exited, and the
before/after SUMO inventories were both empty. No process-name termination was
used. This run is superseded as latest evidence by the exact-HEAD run below.

### Latest authoritative run

```text
run_id: 28f57c800100
run_dir: D:\Temp\t13-real-sumo-100-d1edd10-20260822-122630\i1\fixed_time\x1\s42\28f57c800100
code commit: d1edd109916a3372cab5dfcbd367df7f7b10dbb3
result/status/metadata: completed
EvidenceReader issues: []
canonical summary: loaded
required non-empty artifacts: 13 / 13
SUMO version in manifest/metadata: 1.27.1
requested/derived steps: 100 / 100
requested/final simulation seconds: 100.0 / 100.0
step length: 1.0
warmup seconds: 0.0
simulation_log rows: 100
hash coverage: every required artifact except hashes.json itself
is_complete: true
owned SUMO PID in manifest/metadata: 24348
exact PID alive after cleanup: false
SUMO PIDs before: []
SUMO PIDs after: []
```

Every programmed check returned true. The manifest `code_commit` exactly
matches the current Task 13 code evidence head, the canonical summary was loaded through the reader,
and the exact owned PID no longer existed after cleanup. No process-name
termination was used.

## Protected Inputs and Scope

```text
赛题资料.7z SHA-256:
12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F

data/intersection_data tracked files: 163
data/intersection_data files on disk: 232
ea8b1a9..d1edd109 protected diff: empty
worktree protected diff: empty
index protected diff: empty
```

The protected archive and official dataset were not modified, overwritten,
deleted, repackaged, or staged. Existing `.t9c`, `.t10`, `.t11`, `.task12-*`,
and `.task13-*` scratch/evidence directories remain outside the commits.

## Scoped Final Review

The first scoped review on `5ee5a66` returned FAIL/NEEDS FIXES. Reproducible
findings covered generic `SystemExit` terminalization and exception precedence,
Python 3.10/3.11 Windows reparse detection, uncaught temporary-directory I/O,
strict safety-event rows, manifest reason consistency, the brief-compatible
`RunManifest` constructor, explicit legacy alias units, and Reader-valid
matrix/tuning/visualization/API consumers. The controller additionally locked
API submit filtering and current-request identity for live matrix results with
RED tests before GREEN.

Commit `9b74a61` closed those first-round findings, but its exact-HEAD
re-review found three later Important consumer-integrity gaps: IA/IB could
consume an unsealed completed summary; tuning could select/publish after
invalid or non-finite calibration evidence; and API/tuning/live matrix could
consume a caller-provided in-memory summary rather than the validated disk
snapshot. RED tests established those boundaries before `b1a1ec7` bound the
consumers to sealed evidence.

Round 3 then added RED coverage for figure generation whose validated source
changes while it is read, final publication swap failure, and matrix figure
publication on a changed source. Commit `d1edd10` makes figure-set publication
atomic with rollback/preservation of the previous public set.

On exact HEAD `d1edd109916a3372cab5dfcbd367df7f7b10dbb3`, the final three
independent reviews are CLEAN: Spec reports `10 passed` (with the same-patch
affected suite at `103 passed`); Contract reports `103 passed`; and Mutation
reports `4 passed` plus clean run/aggregate atomic-publication, rollback, and
manual-mutation probes. There are no remaining Critical or Important Task 13
findings. The sole maintainability Minor is that `EvidenceReader.validate()`
is oversized; it is explicitly deferred to the final whole-branch review and
does not weaken the fail-closed contract.
