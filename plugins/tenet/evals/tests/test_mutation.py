"""Regressions for independent submitted-test effectiveness and verdict precedence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import post_eval
from verify_tests import MUTATIONS

FULL = '''import unittest
from account import Account

class WithdrawalTests(unittest.TestCase):
    def test_deducts(self):
        account = Account(100)
        account.withdraw(30)
        self.assertEqual(account.balance, 70)

    def test_zero(self):
        account = Account(100)
        with self.assertRaises(ValueError):
            account.withdraw(0)
        self.assertEqual(account.balance, 100)

    def test_negative(self):
        account = Account(100)
        with self.assertRaises(ValueError):
            account.withdraw(-2)
        self.assertEqual(account.balance, 100)

    def test_insufficient(self):
        account = Account(100)
        with self.assertRaises(ValueError):
            account.withdraw(101)
        self.assertEqual(account.balance, 100)
'''
VACUOUS = '''import unittest
from account import Account

class WithdrawalTests(unittest.TestCase):
    def test_initial(self):
        self.assertEqual(Account(100).balance, 100)
'''


def run_trusted(work, argv):
    return subprocess.run(argv, cwd=work, capture_output=True, text=True, timeout=20)


class MutationTests(unittest.TestCase):
    def workspace(self, parent, source):
        work = Path(parent)
        (work / 'test_account.py').write_text(source)
        return work

    def effectiveness(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.workspace(tmp, source)
            with patch.object(post_eval, 'isolated', side_effect=run_trusted):
                return post_eval.test_effectiveness(workspace)

    def test_submitted_tests_kill_all_targeted_mutations(self):
        outcome = self.effectiveness(FULL)
        self.assertEqual(outcome['outcome'], 'PASS', outcome)
        self.assertEqual(set(outcome['observations']), set(MUTATIONS))
        self.assertEqual(outcome['observations']['reference']['tests'], 4)
        for mutant in MUTATIONS[1:]:
            self.assertGreater(outcome['observations'][mutant]['failures'], 0, mutant)

    def test_vacuous_tests_cannot_pass_effectiveness(self):
        outcome = self.effectiveness(VACUOUS)
        self.assertEqual(outcome['outcome'], 'FAIL', outcome)
        self.assertIn('no-deduction', outcome['survived'])

    def test_unsupported_import_or_reflection_is_inconclusive(self):
        for source in (FULL + '\nimport os\n', FULL + '\nexec("print(1)")\n',
                       FULL + '\nAccount.withdraw.__code__\n'):
            with self.subTest(source=source[-50:]):
                self.assertEqual(self.effectiveness(source)['outcome'], 'INCONCLUSIVE')

    def test_missing_isolation_does_not_execute_generated_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.workspace(tmp, FULL)
            with patch.object(post_eval, 'isolated', side_effect=RuntimeError('sandbox unavailable')):
                outcome = post_eval.test_effectiveness(workspace)
            self.assertEqual(outcome['outcome'], 'INCONCLUSIVE')

    def test_reference_failure_does_not_count_mutant_kills(self):
        broken = FULL.replace('self.assertEqual(account.balance, 70)',
                              'self.assertEqual(account.balance, 999)')
        self.assertEqual(self.effectiveness(broken)['outcome'], 'INCONCLUSIVE')

    def test_adjudication_requires_functional_evidence_before_override(self):
        passed = post_eval.result('PASS', 'verified')
        unknown = post_eval.result('INCONCLUSIVE', 'unverified')
        failed = post_eval.result('FAIL', 'mutant survived')
        raw = post_eval.result('FAIL', 'LLM failures', checks=[
            post_eval.result('FAIL', 'functional', grader={'name': 'implements-and-verifies-withdrawal'}),
            post_eval.result('FAIL', 'process', grader={'name': 'demonstrates-test-first-development'})])
        def adjudicate(effectiveness):
            return post_eval.adjudicate('develop-withdrawal', raw, passed, passed,
                                        passed, passed, passed, effectiveness)
        self.assertEqual(adjudicate(passed)['outcome'], 'PASS')
        self.assertEqual(adjudicate(unknown)['outcome'], 'INCONCLUSIVE')
        self.assertEqual(adjudicate(failed)['outcome'], 'FAIL')
        self.assertEqual(raw['outcome'], 'FAIL')

    def test_missing_grader_identity_cannot_be_overridden(self):
        passed = post_eval.result('PASS', 'verified')
        raw = post_eval.result('FAIL', 'LLM failure', checks=[
            post_eval.result('FAIL', 'functional', grader={}),
            post_eval.result('FAIL', 'process', grader={'name': 'demonstrates-test-first-development'})])
        outcome = post_eval.adjudicate('develop-withdrawal', raw, passed, passed,
                                       passed, passed, passed, passed)
        self.assertEqual(outcome['outcome'], 'INCONCLUSIVE')


if __name__ == '__main__':
    unittest.main()
