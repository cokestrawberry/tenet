#!/usr/bin/env bash
set -euo pipefail

cat > account.py <<'EOF'
class Account:
    def __init__(self, balance):
        self.balance = balance
EOF

cat > test_account.py <<'EOF'
import unittest

from account import Account


class AccountTests(unittest.TestCase):
    def test_initial_balance(self):
        self.assertEqual(Account(100).balance, 100)


if __name__ == "__main__":
    unittest.main()
EOF
