"""Cross-platform regressions for preserved evaluation text and trusted fixtures."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import post_eval
import verify_case
import verify_trace


class PortabilityTests(unittest.TestCase):
    def test_non_ascii_trace_is_read_as_utf8(self):
        event = {'type': 'result', 'subtype': 'success', 'result': '출금 검증 🧪'}
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / 'trace.jsonl'
            trace.write_bytes((json.dumps(event, ensure_ascii=False) + '\n').encode('utf-8'))
            self.assertEqual(verify_trace.read_trace(trace), [event])

    def test_non_ascii_provenance_is_read_as_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / '원본 평가 🧪'
            run = {'tracePath': str(original / 'out' / 'trace.jsonl')}
            kept = root / 'preserved' / 'probe-example' / 'with-1'
            kept.mkdir(parents=True)
            (kept / 'source.json').write_bytes(
                json.dumps({'source': str(original)}, ensure_ascii=False).encode('utf-8'))
            trace, workspace = post_eval.resolve_run(
                run, 'probe-example', 'with', 1, [root / 'preserved'])
            self.assertEqual(trace, kept / 'out' / 'trace.jsonl')
            self.assertEqual(workspace, kept / 'sealed/home/cwd')

    def test_non_ascii_aggregate_mapping_and_outputs_are_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aggregate = root / 'input/aggregate-result.json'
            aggregate.parent.mkdir()
            mapping = root / 'probe-case-map.json'
            case = '매핑 없는 사례 🧪'
            aggregate.write_bytes(json.dumps({'cases': [
                {'name': case, 'arms': {'with': [
                    {'graders': [{'passed': True, 'explanation': '확인 완료'}]}]}}
            ]}, ensure_ascii=False).encode('utf-8'))
            mapping.write_bytes(json.dumps({'이름 🧪': {}}, ensure_ascii=False).encode('utf-8'))
            output = root / 'result'
            argv = ['post_eval.py', '--aggregate', str(aggregate),
                    '--case-map', str(mapping), '--output', str(output)]
            with patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                self.assertEqual(post_eval.main(), 2)
            report = json.loads((output / 'verification.json').read_bytes().decode('utf-8'))
            self.assertEqual(report['runs'][0]['case'], case)
            self.assertEqual(report['runs'][0]['automatic']['checks'][0]['grader']['explanation'],
                             '확인 완료')
            self.assertIn(case, (output / 'verification.md').read_bytes().decode('utf-8'))

    def test_native_fixtures_are_lf_and_only_create_known_files(self):
        cases = {
            'review-no-dogma': {'increment.py'},
            'review-domain-invariant': {'REQUIREMENTS.md', 'order.py'},
            'develop-withdrawal': {'account.py', 'test_account.py'},
        }
        for case, names in cases.items():
            with self.subTest(case=case):
                fixture = post_eval.FIXTURES / case / 'fixture.sh'
                self.assertNotIn(b'\r', fixture.read_bytes())
                actual = verify_case.fixture_files(fixture)
                self.assertEqual(set(actual), names)
                self.assertTrue(all(data.endswith(b'\n') for data in actual.values()))

    def test_fixture_parser_rejects_unrecognized_shell_actions(self):
        header = "#!/usr/bin/env bash\nset -euo pipefail\n\n"
        for suffix in ('touch additional\n', "cat > ../escape <<'EOF'\ntext\nEOF\n",
                       "cat > safe.py <<'EOF'\nmore\nEOF\n"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                fixture = Path(tmp) / 'fixture.sh'
                fixture.write_text(header + "cat > safe.py <<'EOF'\npass\nEOF\n"
                                   + suffix, encoding='utf-8')
                with self.assertRaises(ValueError):
                    verify_case.fixture_files(fixture)

    def test_standalone_review_verifier_needs_no_bash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / 'workspace'
            workspace.mkdir()
            fixture = post_eval.FIXTURES / 'review-no-dogma/fixture.sh'
            for name, data in verify_case.fixture_files(fixture).items():
                (workspace / name).write_bytes(data)
            command = [sys.executable, '-B', '-I', str(post_eval.HERE / 'verify_case.py'),
                       'review-no-dogma', str(workspace)]
            clean = subprocess.run(command, capture_output=True, text=True,
                                   encoding='utf-8', timeout=30)
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
            (workspace / 'unexpected.txt').write_text('changed', encoding='utf-8')
            changed = subprocess.run(command, capture_output=True, text=True,
                                     encoding='utf-8', timeout=30)
            self.assertEqual(changed.returncode, 1, changed.stdout + changed.stderr)


    def test_unicode_filename_uses_utf8_in_independent_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            fixture = post_eval.FIXTURES / 'review-no-dogma/fixture.sh'
            for name, data in verify_case.fixture_files(fixture).items():
                (workspace / name).write_bytes(data)
            (workspace / '🧪.txt').write_text('changed', encoding='utf-8')
            verdict = post_eval.independent('review-no-dogma', workspace)
            self.assertEqual(verdict['outcome'], 'FAIL', verdict)
            self.assertIn('🧪.txt', verdict['output'])
            self.assertNotIn('Traceback', verdict['output'])

    def test_standalone_review_verifier_emits_utf8_with_utf8_mode_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            fixture = post_eval.FIXTURES / 'review-no-dogma/fixture.sh'
            for name, data in verify_case.fixture_files(fixture).items():
                (workspace / name).write_bytes(data)
            (workspace / '🧪.txt').write_text('changed', encoding='utf-8')
            env = dict(os.environ, PYTHONUTF8='0')
            command = [sys.executable, '-I', '-B', str(post_eval.HERE / 'verify_case.py'),
                       'review-no-dogma', str(workspace)]
            actual = subprocess.run(command, capture_output=True, text=True,
                                    encoding='utf-8', env=env, timeout=30)
            self.assertEqual(actual.returncode, 1, actual.stdout + actual.stderr)
            self.assertIn('🧪.txt', actual.stdout)
            self.assertNotIn('UnicodeEncodeError', actual.stderr)

    def test_review_traceback_cannot_be_misclassified_as_verified_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            fixture = post_eval.FIXTURES / 'review-no-dogma/fixture.sh'
            for name, data in verify_case.fixture_files(fixture).items():
                (workspace / name).write_bytes(data)
            fake = subprocess.CompletedProcess([], 1, '', 'Traceback: FAIL: review changed workspace')
            with patch.object(post_eval.subprocess, 'run', return_value=fake):
                verdict = post_eval.independent('review-no-dogma', workspace)
            self.assertEqual(verdict['outcome'], 'INCONCLUSIVE', verdict)


    def test_development_requires_completed_unittest_failure_summary(self):
        scenarios = [
            ('', 'Traceback (most recent call last): RuntimeError: FAILED (setup unavailable)',
             'INCONCLUSIVE'),
            ('Traceback: FAILED (errors=1)', '', 'INCONCLUSIVE'),
            ('Ran 4 tests in 0.001s', 'FAILED (errors=1)', 'INCONCLUSIVE'),
            ('Ran 4 tests in 0.001s\n\nFAILED (errors=1)\n', '', 'FAIL'),
            ('Ran 4 tests in 0.001s\n\nFAILED (failures=1, errors=2)\n', '', 'FAIL'),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / 'account.py').write_text('class Account: pass', encoding='utf-8')
            (workspace / 'test_account.py').write_text('', encoding='utf-8')
            for stdout, stderr, expected in scenarios:
                with self.subTest(stdout=stdout, stderr=stderr):
                    self_check = subprocess.CompletedProcess([], 0, '', '')
                    verification = subprocess.CompletedProcess([], 1, stdout, stderr)
                    with patch.object(post_eval, 'isolated',
                                      side_effect=[self_check, verification]):
                        result = post_eval.independent('develop-withdrawal', workspace)
                    self.assertEqual(result['outcome'], expected, result)


if __name__ == '__main__':
    unittest.main()
