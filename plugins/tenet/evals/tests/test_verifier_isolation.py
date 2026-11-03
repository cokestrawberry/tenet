"""Execute submitted-module shadowing regressions only in the macOS sandbox."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import post_eval

ACCOUNT = '''import json
json.loads('null')
class Account:
    def __init__(self, balance):
        self.balance = balance
    def withdraw(self, amount):
        if amount <= 0 or amount > self.balance:
            raise ValueError('invalid amount')
        self.balance -= amount
'''
FAKE_UNITTEST = 'class TestCase: pass\ndef main(*args, **kwargs): pass\n'
SHADOWS = {
    'unittest.py': FAKE_UNITTEST,
    'unittest/__init__.py': FAKE_UNITTEST,
    'json.py': "raise RuntimeError('SUBMITTED JSON LOADED')\n",
    'types.py': "raise RuntimeError('SUBMITTED TYPES LOADED')\n",
    'pathlib.py': "raise RuntimeError('SUBMITTED PATHLIB LOADED')\n",
}


@unittest.skipUnless(sys.platform == 'darwin', 'macOS isolation required')
class VerifierIsolationTests(unittest.TestCase):
    def workspace(self, path, correct, shadow):
        path.mkdir()
        source = ACCOUNT if correct else ACCOUNT.replace(
            "        if amount <= 0 or amount > self.balance:\n            raise ValueError('invalid amount')\n", '')
        (path / 'account.py').write_text(source)
        (path / 'test_account.py').write_text('')
        sidecar = path / shadow
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(SHADOWS[shadow])

    def test_standalone_verifier_does_not_import_submitted_modules(self):
        for shadow in SHADOWS:
            for correct in (False, True):
                with self.subTest(shadow=shadow, correct=correct):
                    with tempfile.TemporaryDirectory(prefix='tenet-module-regression-', dir='/private/tmp') as tmp:
                        work = Path(tmp)
                        (work / 'tmp').mkdir()
                        self.workspace(work / 'workspace', correct, shadow)
                        shutil.copy2(post_eval.HERE / 'verify_case.py', work / 'verify_case.py')
                        (work / 'develop-withdrawal').mkdir()
                        shutil.copy2(post_eval.FIXTURES / 'develop-withdrawal/fixture.sh', work / 'develop-withdrawal/fixture.sh')
                        proc = post_eval.isolated(work, [sys.executable, '-I', '-B', str(work / 'verify_case.py'),
                                                       'develop-withdrawal', str(work / 'workspace')])
                        self.assertEqual(proc.returncode, 0 if correct else 1, proc.stdout + proc.stderr)
                        self.assertIn('Ran 4 tests', proc.stdout + proc.stderr)

    def test_postprocessing_ignores_sidecar_modules(self):
        for shadow in SHADOWS:
            for correct in (False, True):
                with self.subTest(shadow=shadow, correct=correct):
                    with tempfile.TemporaryDirectory() as tmp:
                        workspace = Path(tmp) / 'workspace'
                        self.workspace(workspace, correct, shadow)
                        before = post_eval.plain_files(workspace)
                        result = post_eval.independent('develop-withdrawal', workspace)
                        self.assertEqual(result['outcome'], 'PASS' if correct else 'FAIL', result)
                        self.assertEqual(before, post_eval.plain_files(workspace))


if __name__ == '__main__':
    unittest.main()
