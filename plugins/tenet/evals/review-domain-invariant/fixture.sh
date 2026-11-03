#!/usr/bin/env bash
set -euo pipefail

cat > order.py <<'EOF'
class Order:
    def __init__(self, status):
        self.status = status

    def cancel(self):
        self.status = "CANCELLED"
EOF
