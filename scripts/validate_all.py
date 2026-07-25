"""Validate original SUMO configurations without writing into source data."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__:
    from scripts.validation_common import run_sumo_validation
else:
    from validation_common import run_sumo_validation

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "intersection_data"


def detect_app_version(net_xml: Path) -> str:
    """Extract the SUMO/netedit version from the network file header."""
    head = net_xml.read_text(encoding="utf-8", errors="replace")[:2000]
    match = re.search(r"netedit\s+Version\s+([\d.]+)", head) or re.search(
        r"netedit\s+([\d.]+)", head
    )
    return match.group(1) if match else "?"


def detect_net_version(net_xml: Path) -> str:
    """Extract the network format version."""
    match = re.search(
        r'<net[^>]*version="([^"]+)"',
        net_xml.read_text(encoding="utf-8", errors="replace"),
    )
    return match.group(1) if match else "?"


def detect_step_length(config: Path) -> str:
    """Extract the configured step length, or report SUMO's default."""
    match = re.search(
        r'<step-length\s+value="([^"]+)"', config.read_text(encoding="utf-8")
    )
    return match.group(1) if match else "1.0 (default)"


def validate(intersection_id: int, end: int, output_root: Path) -> dict:
    config = (
        DATA
        / str(intersection_id)
        / "sumo工程"
        / f"demo_{intersection_id}.sumocfg"
    )
    net_xml = config.parent / f"demo_{intersection_id}.net.xml"
    result = run_sumo_validation(
        config, end, output_root / str(intersection_id)
    )
    diagnostics = [*result.warnings, *result.errors]
    return {
        "id": intersection_id,
        "ok": result.ok,
        "elapsed": result.elapsed_seconds,
        "err": " ".join(diagnostics)[:200],
        "app_version": detect_app_version(net_xml),
        "net_version": detect_net_version(net_xml),
        "step_length": detect_step_length(config),
        "validation": result,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "ids", nargs="*", type=int, help="intersection IDs (default: 1-20)"
    )
    parser.add_argument(
        "--steps", type=int, default=100, help="simulation end time"
    )
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ids = args.ids or list(range(1, 21))
    rows = [
        validate(intersection_id, args.steps, args.output_root)
        for intersection_id in ids
    ]

    for row in rows:
        result = row["validation"]
        print(
            f"[{'PASS' if row['ok'] else 'FAIL'}] 路口 {row['id']:>2} "
            f"app={row['app_version']:<8} net={row['net_version']:<5} "
            f"step={row['step_length']:<13} {row['elapsed']:5.1f}s "
            f"returncode={result.returncode}"
        )
        for diagnostic in [*result.warnings, *result.errors]:
            print(diagnostic)

    passed = sum(row["ok"] for row in rows)
    warning_count = sum(len(row["validation"].warnings) for row in rows)
    error_count = sum(len(row["validation"].errors) for row in rows)
    print(
        f"\n{passed}/{len(rows)} PASS "
        f"warnings={warning_count} errors={error_count}"
    )
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
