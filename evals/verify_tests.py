"""Trusted mutation runner for the withdrawal fixture; run only inside the eval sandbox."""
import contextlib
import io
import json
from pathlib import Path
import sys
import types
import unittest

REFERENCE = """class Account:
    def __init__(self, balance):
        self.balance = balance

    def withdraw(self, amount):
        if amount <= 0 or amount > self.balance:
            raise ValueError('Invalid amount')
        self.balance -= amount
"""

MUTATIONS = (
    'reference', 'no-deduction', 'accept-zero', 'accept-negative',
    'accept-insufficient', 'alter-zero-on-error', 'alter-negative-on-error',
    'alter-insufficient-on-error',
)


def variant_source(variant):
    if variant not in MUTATIONS:
        raise ValueError('Unknown mutation')
    if variant == 'reference':
        return REFERENCE
    if variant == 'no-deduction':
        return REFERENCE.replace('        self.balance -= amount', '        return None')
    if variant.startswith('accept-'):
        conditions = {
            'accept-zero': 'amount < 0 or amount > self.balance',
            'accept-negative': 'amount == 0 or amount > self.balance',
            'accept-insufficient': 'amount <= 0',
        }
        return REFERENCE.replace('amount <= 0 or amount > self.balance', conditions[variant])
    conditions = {
        'alter-zero-on-error': 'amount == 0',
        'alter-negative-on-error': 'amount < 0',
        'alter-insufficient-on-error': 'amount > self.balance',
    }
    return REFERENCE.replace(
        "            raise ValueError('Invalid amount')",
        f"            if {conditions[variant]}:\n"
        "                self.balance -= 1\n"
        "            raise ValueError('Invalid amount')")


def main():
    variant, test_path = sys.argv[1:]
    account = types.ModuleType('account')
    exec(compile(variant_source(variant), '<trusted-account>', 'exec'), account.__dict__)
    sys.modules['account'] = account
    submitted = types.ModuleType('tenet_submitted_tests')
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        exec(compile(Path(test_path).read_bytes(), test_path, 'exec'), submitted.__dict__)
        suite = unittest.defaultTestLoader.loadTestsFromModule(submitted)
        result = unittest.TestResult()
        suite.run(result)
    print(json.dumps({
        'tests': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': len(result.skipped),
        'expectedFailures': len(result.expectedFailures),
        'unexpectedSuccesses': len(result.unexpectedSuccesses),
    }))


if __name__ == '__main__':
    main()
