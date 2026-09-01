"""Public-documentation boundary checker (Task 20).

Scans the judge-facing documentation set for internal role codes, stale
matrix/algorithm wording, personal machine paths, unsupported success claims,
and broken local links.  Exit 0 = clean, 1 = violations, 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PUBLIC_DOCS = (
    "README.md",
    "docs/README.md",
    "docs/deployment.md",
    "docs/release/README.md",
    "docs/release/experiment-protocol.md",
    "docs/release/evidence-contract.md",
    "docs/release/algorithm-extension.md",
    "output/README.md",
)

# Rules applied to every public document.
CORE_RULES = {
    "role_codes": (
        r"(?<![/\w])(TL|IA|IB|AA|AB|EX|DA|DB)(?!/\w)(?![\w-])",
        "internal role code",
    ),
    "internal_task_docs": (r"docs/tasks", "internal task-document link"),
    "verify_route": (r"verify_route", "internal route-verification reference"),
    "verify_ia_ib": (r"verify_ia_ib", "internal acceptance script reference"),
    "old_algorithm_name": (r"ca_maxpressure", "stale algorithm spelling"),
    "old_algorithm_option": (r"--algorithm\s+actuated", "stale algorithm option"),
    "flow_multiplier_claim": (r"1\.5x|--flow-multiplier\s+1\.5\b", "stale 1.5x claim"),
    "unsupported_live_pass": (
        r"(Docker live verification|gui_smoke|save_load|formal matrix):\s*pass",
        "unsupported pass claim",
    ),
    "personal_windows_path": (
        r"C:\\Users\\|D:\\Temp\\|D:\\WorkPlace\\|D:\\Desktop\\",
        "personal machine path",
    ),
}

# Stale seconds/steps matrix wording is banned in judge-facing entry documents;
# docs/deployment.md may keep structural-validation commands that legitimately
# accept a step count.
RESTRICTED_EXTRA_RULES = {
    "quick_flag": (r"--quick\b", "stale --quick flag"),
    "steps_flag": (r"--steps\b", "stale --steps flag"),
    "steps_count": (r"\b36000\b", "stale 36000-step matrix wording"),
    "frozen_360": (r"\b360-run\b|\b360 组\b|\b360次\b", "stale 360-run matrix claim"),
}
RESTRICTED_FILES = frozenset(
    {
        "README.md",
        "docs/README.md",
        "docs/release/README.md",
        "docs/release/experiment-protocol.md",
        "docs/release/evidence-contract.md",
        "docs/release/algorithm-extension.md",
        "output/README.md",
    }
)

LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _relative_local_link(target: str) -> Path | None:
    if re.match(r"^(https?://|mailto:|#|/)", target):
        return None
    clean = target.split("#", 1)[0]
    if not clean:
        return None
    return Path(clean)


def scan_document(root: Path, relative: str) -> list[dict[str, object]]:
    path = root / relative
    text = path.read_text(encoding="utf-8")
    violations: list[dict[str, object]] = []
    rules = dict(CORE_RULES)
    if relative in RESTRICTED_FILES:
        rules.update(RESTRICTED_EXTRA_RULES)
    for name, (pattern, message) in rules.items():
        for match in re.finditer(pattern, text):
            line_no = text.count("\n", 0, match.start()) + 1
            violations.append(
                {
                    "file": relative,
                    "line": line_no,
                    "rule": name,
                    "message": message,
                    "excerpt": text.splitlines()[line_no - 1].strip()[:160],
                }
            )
    for match in LINK_PATTERN.finditer(text):
        relative_link = _relative_local_link(match.group(1))
        if relative_link is None:
            continue
        resolved = (path.parent / relative_link).resolve()
        if not resolved.exists():
            line_no = text.count("\n", 0, match.start()) + 1
            violations.append(
                {
                    "file": relative,
                    "line": line_no,
                    "rule": "broken_local_link",
                    "message": "local link target does not exist",
                    "excerpt": match.group(1)[:160],
                }
            )
    return violations


def scan_repository(root: Path) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for relative in PUBLIC_DOCS:
        doc = root / relative
        if not doc.exists():
            violations.append(
                {
                    "file": relative,
                    "line": 0,
                    "rule": "missing_public_doc",
                    "message": "public document is missing",
                    "excerpt": "",
                }
            )
            continue
        violations.extend(scan_document(root, relative))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    violations = scan_repository(root)
    if args.format == "json":
        print(json.dumps({"violations": violations}, ensure_ascii=False, indent=2))
    else:
        for violation in violations:
            print(
                f"{violation['file']}:{violation['line']}: "
                f"[{violation['rule']}] {violation['message']}: "
                f"{violation['excerpt']}"
            )
        print(f"{len(violations)} violation(s) across {len(PUBLIC_DOCS)} public docs")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
