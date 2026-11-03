#!/usr/bin/env bash
set -euo pipefail

cat > increment.py <<'EOF'
def increment(value: int) -> int:
    return value + 1
EOF
