"""Validate enhanced SUMO configurations and optionally write a report."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from defusedxml import ElementTree as ET

if __package__:
    from scripts.validation_common import run_sumo_validation
else:
    from validation_common import run_sumo_validation

ROOT = Path(__file__).resolve().parents[1]
CFG_DIR = ROOT / "engine" / "configs"
REPORT = ROOT / "docs" / "batch_validate_report.md"


def run_one(intersection_id: int, steps: int, output_root: Path) -> dict:
    config = CFG_DIR / f"demo_{intersection_id}.sumocfg"
    result = run_sumo_validation(
        config, steps, output_root / str(intersection_id)
    )
    tripinfo = result.output_dir / "tripinfo.xml"
    finished = 0
    if tripinfo.exists():
        try:
            finished = len(ET.parse(tripinfo).getroot())
        except ET.ParseError:
            finished = 0
    return {
        "id": intersection_id,
        "ok": result.ok,
        "elapsed": result.elapsed_seconds,
        "finished": finished,
        "err": " ".join([*result.warnings, *result.errors])[:150],
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
    report_group = parser.add_mutually_exclusive_group()
    report_group.add_argument(
        "--report",
        nargs="?",
        const=REPORT,
        type=Path,
        help="write a report (default path when no path is supplied)",
    )
    report_group.add_argument(
        "--no-report", action="store_true", help="do not write a report"
    )
    return parser


def _row_lines(row: dict) -> list[str]:
    result = row["validation"]
    headline = (
        f"路口 {row['id']:>2} {'PASS' if row['ok'] else 'FAIL'} "
        f"{row['elapsed']:7.1f}s finished={row['finished']:>5} "
        f"returncode={result.returncode}"
    )
    return [headline, *result.warnings, *result.errors]


def _write_report(
    report: Path, output_root: Path, lines: list[str], summary: str
) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# 批量 SUMO 验证报告（IA W2）\n\n"
        f"> 输出目录 `{output_root}`。\n\n"
        "```text\n" + "\n".join([*lines, summary]) + "\n```\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ids = args.ids or list(range(1, 21))
    rows = [
        run_one(intersection_id, args.steps, args.output_root)
        for intersection_id in ids
    ]
    total = sum(row["elapsed"] for row in rows)
    passed = sum(row["ok"] for row in rows)
    warning_count = sum(len(row["validation"].warnings) for row in rows)
    error_count = sum(len(row["validation"].errors) for row in rows)

    lines: list[str] = []
    for row in rows:
        row_lines = _row_lines(row)
        lines.extend(row_lines)
        for line in row_lines:
            print(line)

    estimated_hours = total * 18 / 3600
    summary = (
        f"{passed}/{len(rows)} PASS warnings={warning_count} "
        f"errors={error_count}; "
        f"total={total:.0f}s; estimated 360 runs={estimated_hours:.1f}h"
    )
    print(summary)

    if args.report is not None:
        _write_report(args.report, args.output_root, lines, summary)
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
