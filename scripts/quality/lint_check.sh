#!/usr/bin/env bash
# IB W5 清理检查：flake8 + 调试残留 + TODO 残留
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"

if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git command not found" >&2
    exit 2
fi

check_forbidden() {
    pattern="$1"
    message="$2"
    if matches=$(git grep --no-index --exclude-standard -nE "$pattern" -- engine cloud experiments); then
        printf '%s\n' "$matches"
        echo "$message"
        return 1
    else
        status=$?
        if [ "$status" -ne 1 ]; then
            echo "ERROR: git grep failed (exit=$status)" >&2
            return "$status"
        fi
    fi
}

python -m flake8 engine/ cloud/ experiments/ --max-line-length=100
check_forbidden "breakpoint\(\)|pdb\.set_trace" "FOUND DEBUG CODE"
check_forbidden "TODO|FIXME|XXX" "FOUND TODO"
echo "clean"
