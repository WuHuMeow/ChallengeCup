# Release Baseline Evidence

This directory defines the reproducible native-environment baseline for the
judge-facing release. Generate the machine-readable snapshot from the
repository root with:

```powershell
python scripts/release/preflight.py --repo-root . --output output/evidence/release-baseline/environment.json
```

The generated `environment.json` records repository-relative source identity,
tool and package versions, the official source archive SHA-256, and explicit
`pass`, `fail`, or `not_run` preflight results. It intentionally excludes user
names, Python executable locations, and personal absolute paths.

The official `赛题资料.7z` archive and `data/intersection_data/` tree are
read-only inputs. A successful preflight does not authorize either source to
be overwritten, repackaged, or removed.

Docker is an independent reproduction route. Its status remains `not_run`
until a live image build and container health check have actually completed;
detecting a Docker executable alone is not a pass.
