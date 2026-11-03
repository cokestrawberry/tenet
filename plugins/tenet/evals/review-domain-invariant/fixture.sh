#!/usr/bin/env bash
set -euo pipefail

cat > REQUIREMENTS.md <<'EOF'
# Order cancellation

An order with status FILLED cannot be cancelled.
EOF

cat > order.py <<'EOF'
class Order:
    def __init__(self, status):
        self.status = status

    def cancel(self):
        self.status = "CANCELLED"
EOF
