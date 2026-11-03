#!/usr/bin/env python3
"""Independently verify a preserved Claude Code evaluation workspace."""
import argparse
import pathlib
import subprocess
import sys
import tempfile

CASES = {"develop-withdrawal", "review-domain-invariant", "review-no-dogma"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=sorted(CASES))
    parser.add_argument("workspace", type=pathlib.Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    script_dir = pathlib.Path(__file__).resolve().parent
    repository_fixture = script_dir.parent / "plugins/tenet/evals" / args.case / "fixture.sh"
    copied_fixture = script_dir / args.case / "fixture.sh"
    fixture = repository_fixture if repository_fixture.is_file() else copied_fixture
    if not workspace.is_dir():
        parser.error(f"Missing workspace: {workspace}")

    with tempfile.TemporaryDirectory() as root:
        expected = pathlib.Path(root)
        subprocess.run(["bash", str(fixture)], cwd=expected, check=True)
        originals = {
            p.relative_to(expected): p.read_bytes()
            for p in expected.rglob("*") if p.is_file()
        }
        if args.case.startswith("review-"):
            actual = {
                p.relative_to(workspace): p.read_bytes()
                for p in workspace.rglob("*") if p.is_file()
            }
            if actual != originals:
                unexpected = sorted(str(p) for p in actual.keys() - originals.keys())
                changed = sorted(
                    str(p) for p in actual.keys() & originals.keys()
                    if actual[p] != originals[p]
                )
                missing = sorted(str(p) for p in originals.keys() - actual.keys())
                print(
                    f"FAIL: review changed workspace "
                    f"(extra={unexpected}, changed={changed}, missing={missing})"
                )
                return 1
            print("PASS: review workspace matches fixture")
            return 0

        check = """
class WithdrawalContract(unittest.TestCase):
    def test_initial_balance(self):
        self.assertEqual(Account(100).balance, 100)

    def test_subtract(self):
        account = Account(100)
        account.withdraw(30)
        self.assertEqual(account.balance, 70)

    def test_full_balance(self):
        account = Account(100)
        account.withdraw(100)
        self.assertEqual(account.balance, 0)

    def test_invalid_values_preserve_balance(self):
        for amount in (0, -1, 101):
            with self.subTest(amount=amount):
                account = Account(100)
                with self.assertRaises(ValueError):
                    account.withdraw(amount)
                self.assertEqual(account.balance, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
"""
        script = expected / "check.py"
        # Load the trusted framework before executing only the submitted source.
        # Never add the workspace to sys.path or load its cached bytecode/modules.
        script.write_text(
            "import pathlib\nimport types\nimport unittest\n"
            "account_path = pathlib.Path(" + repr(str(workspace / 'account.py')) + ")\n"
            "account_module = types.ModuleType('tenet_account_under_test')\n"
            "account_module.__file__ = str(account_path)\n"
            "exec(compile(account_path.read_bytes(), str(account_path), 'exec'), account_module.__dict__)\n"
            "Account = account_module.Account\n" + check
        )
        result = subprocess.run(
            [sys.executable, "-B", "-I", str(script)],
            cwd=expected,
            capture_output=True,
            text=True,
            timeout=20,
        )
        print(result.stdout + result.stderr)
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
