#!/usr/bin/env python3
"""Independently verify a preserved Claude Code evaluation workspace."""
import argparse
import pathlib
import re
import subprocess
import sys
import tempfile

CASES = {"develop-withdrawal", "review-domain-invariant", "review-no-dogma"}


def fixture_files(fixture):
    """Parse only the trusted fixture's literal heredoc file creation steps."""
    header = '#!/usr/bin/env bash\nset -euo pipefail\n\n'
    script = fixture.read_text(encoding='utf-8')
    if not script.startswith(header):
        raise ValueError('unsupported fixture scaffold')
    remaining = script[len(header):]
    files = {}
    while remaining:
        match = re.match(r"cat > ([A-Za-z][A-Za-z0-9_.-]*) <<'EOF'\n", remaining)
        if match is None:
            raise ValueError('unsupported fixture command')
        name = match.group(1)
        if name in files:
            raise ValueError('duplicate fixture file')
        content, separator, suffix = remaining[match.end():].partition('\nEOF\n')
        if not separator:
            raise ValueError('unterminated fixture heredoc')
        files[name] = (content + '\n').encode('utf-8')
        remaining = suffix[1:] if suffix.startswith('\n') else suffix
    if not files:
        raise ValueError('empty fixture')
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=sorted(CASES))
    parser.add_argument("workspace", type=pathlib.Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    script_dir = pathlib.Path(__file__).resolve().parent
    repository_fixture = script_dir.parent / "plugins/tenet/evals" / args.case / "fixture.sh"
    copied_fixture = script_dir / args.case / "fixture.sh"
    fixture = copied_fixture if copied_fixture.is_file() else repository_fixture
    if not workspace.is_dir():
        parser.error(f"Missing workspace: {workspace}")

    with tempfile.TemporaryDirectory() as root:
        expected = pathlib.Path(root)
        originals = {pathlib.Path(name): data for name, data in fixture_files(fixture).items()}
        for name, data in originals.items():
            (expected / name).write_bytes(data)
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
            "Account = account_module.Account\n" + check,
            encoding='utf-8',
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
