"""Optional regression against local evidence; no model calls or evidence writes.

Set TENET_PREVIOUS_EVAL and TENET_POSTFIX_EVAL to the two preserved output roots.
Development checks require a working macOS sandbox-exec, just like post_eval.py.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import post_eval


class PreservedRunTests(unittest.TestCase):
    def check_round(self, root, previous):
        if previous:
            aggregates = [root / 'logs/run1/results/aggregate-result.json']
            roots = [root / 'evidence/run1']
        else:
            aggregates = [root / f'src/tenet-eval-results/{group}/aggregate-result.json' for group in ('review', 'develop')]
            roots = [root / f'evidence/{group}' for group in ('review', 'develop')]
        count = 0
        for aggregate in aggregates:
            for case in json.loads(aggregate.read_text())['cases']:
                for arm, runs in case['arms'].items():
                    for number, run in enumerate(runs, 1):
                        count += 1
                        with self.subTest(round='previous' if previous else 'postfix', case=case['name'], arm=arm, run=number):
                            trace, workspace = post_eval.resolve_run(run, case['name'], arm, number, roots)
                            before = (hashlib.sha256(trace.read_bytes()).digest(), post_eval.plain_files(workspace))
                            result = post_eval.process_run(run, case['name'], arm, number, roots)
                            expected = 'PASS'
                            if previous:
                                if case['name'] == 'develop-withdrawal' and arm == 'without':
                                    expected = 'FAIL'
                                if arm == 'with' and ((case['name'] == 'review-domain-invariant' and number == 3)
                                                      or (case['name'] == 'review-no-dogma' and number in (1, 2))):
                                    expected = 'FAIL'
                            else:
                                if arm == 'without' and (case['name'] == 'review-domain-invariant'
                                                         or (case['name'] == 'develop-withdrawal' and number < 3)):
                                    expected = 'FAIL'
                                if arm == 'without' and number == 3 and case['name'] != 'review-domain-invariant':
                                    expected = 'INCONCLUSIVE'
                            self.assertEqual(result['outcome'], expected, result)
                            after = (hashlib.sha256(trace.read_bytes()).digest(), post_eval.plain_files(workspace))
                            self.assertEqual(before, after)
        self.assertEqual(count, 18)

    @unittest.skipUnless(os.environ.get('TENET_PREVIOUS_EVAL'), 'TENET_PREVIOUS_EVAL is not set')
    def test_previous_round(self):
        self.check_round(Path(os.environ['TENET_PREVIOUS_EVAL']), previous=True)

    @unittest.skipUnless(os.environ.get('TENET_POSTFIX_EVAL'), 'TENET_POSTFIX_EVAL is not set')
    def test_postfix_round(self):
        self.check_round(Path(os.environ['TENET_POSTFIX_EVAL']), previous=False)

    @unittest.skipUnless(os.environ.get('TENET_PREVIOUS_EVAL'), 'TENET_PREVIOUS_EVAL is not set')
    def test_previous_failed_grader_probes_without_model_calls(self):
        root = Path(os.environ['TENET_PREVIOUS_EVAL']) / 'evidence/probe-run'
        for name, expected in [('probe-dev-vacuous', 'FAIL'), ('probe-dev-correct-alt-style', 'PASS')]:
            with self.subTest(probe=name):
                workspace = root / name / 'sealed/home/cwd'
                before = post_eval.plain_files(workspace)
                self.assertEqual(post_eval.independent('develop-withdrawal', workspace)['outcome'], expected)
                self.assertEqual(before, post_eval.plain_files(workspace))


if __name__ == '__main__':
    unittest.main()
