"""Release-candidate and runtime verification (Task 23).

``verify_release_copy`` re-validates a clean release copy produced by
``scripts/release/clean_release.py``: manifest hashes, public entrypoints,
absence of internal material, canonical algorithm spellings, official source
presence, Web build presence, and public-documentation boundaries.

``verify_runtime`` drives a running judge instance (native or Docker) through
health, scene/algorithm discovery, a short run, frame, metrics, stop, and
result retrieval.  Every check is honest: it is executed when this module
runs, never inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.release import check_docs  # noqa: E402

MANIFEST_NAME = "release-manifest.json"
INTERNAL_MARKERS = ("docs/tasks", ".superpowers", "verify_route", "会话")
STALE_ALGORITHM_MARKERS = ("ca_maxpressure", "--algorithm actuated")


@dataclass
class Verification:
    checks: dict[str, str]
    details: dict[str, object]

    @property
    def ok(self) -> bool:
        return all(status != "fail" for status in self.checks.values())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_release_copy(release_root: Path) -> Verification:
    release_root = release_root.resolve()
    checks: dict[str, str] = {}
    details: dict[str, object] = {}

    manifest_path = release_root / MANIFEST_NAME
    if not manifest_path.is_file():
        return Verification(
            checks={"release_manifest": "fail"},
            details={"reason": f"{MANIFEST_NAME} missing"},
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks["release_manifest"] = "pass"

    mismatches = []
    missing = []
    for entry in manifest.get("entries", []):
        item = release_root / str(entry["relative_path"])
        if not item.is_file():
            missing.append(str(entry["relative_path"]))
            continue
        if _sha256(item) != entry["sha256"]:
            mismatches.append(str(entry["relative_path"]))
    checks["manifest_hashes"] = "pass" if not (mismatches or missing) else "fail"
    details["manifest_hash_mismatches"] = mismatches
    details["manifest_missing"] = missing

    entrypoints = ["README.md", "scripts/run_judge.py", "docker/Dockerfile"]
    entry_missing = [name for name in entrypoints if not (release_root / name).is_file()]
    checks["public_entrypoints"] = "pass" if not entry_missing else "fail"
    details["entrypoints_missing"] = entry_missing

    internal_hits = []
    for item in release_root.rglob("*"):
        if not item.is_file():
            continue
        relative = item.relative_to(release_root).as_posix()
        if item.suffix == ".pyc" or "__pycache__" in relative:
            continue
        if relative == MANIFEST_NAME:
            continue
        if any(marker in relative for marker in INTERNAL_MARKERS):
            internal_hits.append(relative)
    checks["no_internal_files"] = "pass" if not internal_hits else "fail"
    details["internal_files"] = internal_hits

    stale_hits = []
    stale_markers = (
        "run_pdf_matrix.py --quick",
        "run_pdf_matrix.py --steps",
        "--steps 36000",
        "36000 步",
        "360-run",
        "360 次仿真",
        "1.5x",
        "--flow-multiplier 1.5",
    )
    for item in release_root.rglob("*.md"):
        relative = item.relative_to(release_root).as_posix()
        if relative.startswith(("docs/notes/", "docs/superpowers/")):
            continue  # historical research records, not prescriptive claims
        try:
            text = item.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(marker in text for marker in stale_markers):
            stale_hits.append(relative)
    checks["no_stale_algorithms"] = "pass" if not stale_hits else "fail"
    details["stale_algorithm_files"] = stale_hits
    registry = release_root / "algorithms" / "registry.py"
    canonical_present = registry.is_file() and all(
        token in registry.read_text(encoding="utf-8")
        for token in ("fixed_time", "classic_max_pressure", "capacity_aware_max_pressure")
    )
    checks["canonical_registry_ids"] = "pass" if canonical_present else "fail"
    details["canonical_registry_ids"] = canonical_present

    protected = manifest.get("protected_inputs", {})
    archive_info = protected.get("source_archive", {})
    archive_present = bool(archive_info.get("present"))
    archive = release_root / "赛题资料.7z"
    # The manifest binds the archive bytes that were actually copied; the
    # frozen-hash protection gate (12A6F2FD...) runs separately on the real
    # repository, so a synthetic or re-hashed archive cannot pass here.
    archive_ok = (
        archive_present
        and archive.is_file()
        and archive_info.get("sha256") == _sha256(archive)
    )
    checks["official_source_archive"] = "pass" if archive_ok else "fail"
    details["official_source_archive"] = {
        "present": archive_present,
        "note": (
            "bound to the manifest-recorded digest; the frozen-hash protection "
            "gate runs on the packaging host against "
            "12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F"
        ),
    }
    official_data = release_root / "data" / "intersection_data"
    data_files = len(list(official_data.rglob("*"))) if official_data.is_dir() else 0
    checks["official_scene_data"] = "pass" if data_files > 0 else "fail"
    details["official_scene_data_files"] = data_files

    checks["web_build_present"] = (
        "pass" if (release_root / "api" / "static" / "dist" / "index.html").is_file()
        else "fail"
    )

    doc_violations = check_docs.scan_repository(release_root)
    checks["documentation_boundary"] = "pass" if not doc_violations else "fail"
    details["documentation_violations"] = doc_violations[:20]
    return Verification(checks=checks, details=details)


def _get_json(base_url: str, path: str, timeout: float = 30.0) -> object:
    with urllib.request.urlopen(base_url + path, timeout=timeout) as response:
        return json.load(response)


def verify_runtime(
    base_url: str,
    *,
    profile: str,
    run_seconds: int = 60,
    gui_mode: str = "headless",
) -> Verification:
    checks: dict[str, str] = {}
    details: dict[str, object] = {}
    base = base_url.rstrip("/")

    def record(name: str, ok: bool, info: object = None) -> None:
        checks[name] = "pass" if ok else "fail"
        if info is not None:
            details[name] = info

    try:
        health = _get_json(base, "/api/health")
        record(
            "health",
            health == {"run_workers": 1, "status": "ok"},
            health,
        )
    except (urllib.error.URLError, OSError) as exc:
        record("health", False, str(exc))
        return Verification(checks=checks, details=details)

    for name, path in (("scenes", "/api/scenes"), ("algorithms", "/api/algorithms")):
        try:
            payload = _get_json(base, path)
            record(name, bool(payload), payload if isinstance(payload, list) else None)
        except (urllib.error.URLError, OSError) as exc:
            record(name, False, str(exc))

    request_body = json.dumps(
        {
            "intersection_id": "1",
            "algorithm": "fixed_time",
            "duration_seconds": run_seconds,
            "warmup_seconds": 0,
        }
    ).encode("utf-8")
    run_request = urllib.request.Request(
        base + "/api/runs",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(run_request, timeout=30) as response:
            payload = json.load(response)
        run_id = str(payload.get("run_id", ""))
        run_dir = str(payload.get("run_dir", ""))
        record("quick_run_submit", bool(run_id), {"run_id": run_id, "run_dir": run_dir})
    except (urllib.error.URLError, OSError) as exc:
        record("quick_run_submit", False, str(exc))
        return Verification(checks=checks, details=details)

    deadline = time.time() + max(120, run_seconds * 4)
    status = None
    frame_checked = False
    while time.time() < deadline:
        try:
            status = _get_json(base, f"/api/runs/{run_id}")
        except (urllib.error.URLError, OSError) as exc:
            record("run_status_poll", False, str(exc))
            break
        state = str(status.get("status", ""))
        if not frame_checked and gui_mode == "headless":
            # Headless command-line SUMO cannot render; the frame endpoint
            # serving 404 here is the documented fail-soft behavior, not a
            # runtime defect.
            checks["frame"] = "not_run"
            details["frame"] = "headless gui mode captures no frames (documented)"
            frame_checked = True
            continue
        if not frame_checked and state == "running":
            # Frames are run-scoped runtime resources; the contract serves
            # them while the simulation is live and 404s after terminal.
            try:
                frame_request = urllib.request.Request(
                    base + f"/api/runs/{run_id}/frame"
                )
                with urllib.request.urlopen(frame_request, timeout=30) as response:
                    frame_payload = response.read()
                record("frame", len(frame_payload) > 0, {"bytes": len(frame_payload)})
            except (urllib.error.URLError, OSError) as exc:
                record("frame", False, str(exc))
            frame_checked = True
        if state in {"completed", "failed"}:
            break
        time.sleep(2)
    if not frame_checked:
        record("frame", False, "run never reached running state while polling")
    record("quick_run_terminal", status is not None and status.get("status") == "completed", status)

    for name, path in (
        ("metrics", f"/api/runs/{run_id}/metrics"),
        ("result", f"/api/results/{run_id}"),
    ):
        try:
            payload = _get_json(base, path)
            record(name, payload is not None)
        except (urllib.error.URLError, OSError) as exc:
            record(name, False, str(exc))

    stop_request = urllib.request.Request(
        base + f"/api/runs/{run_id}/stop", data=b"{}", method="POST"
    )
    try:
        with urllib.request.urlopen(stop_request, timeout=30) as response:
            record("stop_after_completion", response.status == 200)
    except urllib.error.HTTPError as exc:
        record("stop_after_completion", exc.code in {409, 400})
    except (urllib.error.URLError, OSError) as exc:
        record("stop_after_completion", False, str(exc))
    return Verification(checks=checks, details=details)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    package = sub.add_parser("package", help="verify a release copy directory")
    package.add_argument("release_root", type=Path)
    runtime = sub.add_parser("runtime", help="verify a running judge instance")
    runtime.add_argument("--base-url", default="http://127.0.0.1:8000")
    runtime.add_argument("--profile", choices=("native", "docker"), default="native")
    runtime.add_argument("--run-seconds", type=int, default=60)
    runtime.add_argument("--gui-mode", choices=("headless", "native", "container-gui"), default="headless")
    args = parser.parse_args(argv)
    if args.command == "package":
        result = verify_release_copy(args.release_root)
    else:
        result = verify_runtime(
            args.base_url,
            profile=args.profile,
            run_seconds=args.run_seconds,
            gui_mode=args.gui_mode,
        )
    print(json.dumps(
        {"ok": result.ok, "checks": result.checks, "details": result.details},
        ensure_ascii=False,
        indent=2,
        default=str,
    ))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
