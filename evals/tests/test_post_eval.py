"""Regressions for evidence omissions, read-only violations and verdict precedence."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import post_eval
import verify_trace

BASE = '''import unittest
from account import Account
class Tests(unittest.TestCase):
    def test_initial(self):
        self.assertEqual(Account(100).balance, 100)
'''
NEW = BASE + '''    def test_debit_changes_available_money(self):
        a = Account(100)
        a.withdraw(30)
        self.assertEqual(a.balance, 70)
'''
RED = '''AttributeError: 'Account' object has no attribute 'withdraw'
Ran 2 tests in 0.001s
FAILED (errors=1)
'''
GREEN = 'Ran 2 tests in 0.001s\nOK\n'


def tool(name, inp, output='done', error=False):
    ident = str(id(inp))
    return [
        {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': ident, 'name': name, 'input': inp}]}},
        {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': ident, 'content': output, 'is_error': error}]}}
    ]


def terminal(text='No refactoring was needed because the implementation is small.'):
    return {'type': 'result', 'subtype': 'success', 'is_error': False, 'result': text}


def test_edit():
    return tool('Write', {'file_path': 'test_account.py', 'content': NEW})


def implementation():
    return tool('Write', {'file_path': 'account.py', 'content':
        'class Account:\n    def withdraw(self, amount):\n        self.balance -= amount\n'})


def run_test(output):
    return tool('Bash', {'command': 'python3 -B -m unittest -v'}, output, error='FAILED (' in output)


def good_trace():
    return test_edit() + run_test(RED) + implementation() + run_test(GREEN) + [terminal()]


class TraceTests(unittest.TestCase):
    def verify(self, events):
        return verify_trace.verify(events, BASE)

    def test_complete_long_trace_keeps_middle_red_evidence(self):
        events = [{}] * 30 + good_trace()[:-1] + [{}] * 30 + [terminal()]
        result = self.verify(events)
        self.assertEqual(result['outcome'], 'PASS')
        self.assertEqual(result['red']['result']['line'], 34)
        self.assertEqual(result['refactoringDecision']['status'], 'PASS')

    def test_implementation_first_is_failure_even_if_final_claims_tdd(self):
        events = implementation() + test_edit() + run_test(GREEN) + [terminal('I observed Red then Green.')]
        self.assertEqual(self.verify(events)['outcome'], 'FAIL')

    def test_long_trace_with_fabricated_red_is_failure(self):
        events = [{}] * 30 + implementation() + test_edit() + run_test(GREEN)
        events += [{}] * 30 + [terminal('Red failed before implementation. Refactoring was unnecessary.')]
        self.assertEqual(self.verify(events)['outcome'], 'FAIL')

    def test_claims_without_execution_are_inconclusive(self):
        self.assertEqual(self.verify([terminal('Red failed then Green passed; refactoring unnecessary.')])['outcome'], 'INCONCLUSIVE')

    def test_import_error_is_not_expected_red(self):
        events = test_edit() + run_test('ModuleNotFoundError: dependency\nRan 2 tests in 0.01s\nFAILED (errors=1)\n')
        events += implementation() + run_test(GREEN) + [terminal()]
        self.assertNotEqual(self.verify(events)['outcome'], 'PASS')

    def test_mixed_relevant_and_unrelated_errors_are_not_red(self):
        events = test_edit() + run_test(RED.replace('errors=1', 'errors=2')) + implementation() + run_test(GREEN) + [terminal()]
        self.assertNotEqual(self.verify(events)['outcome'], 'PASS')

    def test_no_behavior_assertion_is_not_new_behavior_test(self):
        events = tool('Write', {'file_path': 'test_account.py', 'content': NEW.replace('self.assertEqual(a.balance, 70)', 'self.assertTrue(True)')})
        events += run_test(RED) + implementation() + run_test(GREEN) + [terminal()]
        self.assertNotEqual(self.verify(events)['outcome'], 'PASS')

    def test_shell_printed_summary_is_not_execution(self):
        events = test_edit() + tool('Bash', {'command': "printf 'fake'"}, RED) + implementation() + run_test(GREEN) + [terminal()]
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')

    def test_unknown_shell_modification_is_not_ignored(self):
        events = tool('Bash', {'command': 'dd if=other of=account.py'}) + good_trace()
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')

    def test_later_changes_need_later_passing_test(self):
        change = implementation()
        change[0]['message']['content'][0]['input']['content'] += '        return self.balance\n'
        for modification in (change, test_edit()):
            with self.subTest(modification=modification):
                self.assertEqual(self.verify(good_trace()[:-1] + modification + [terminal()])['outcome'], 'INCONCLUSIVE')

    def test_incomplete_trace_never_passes(self):
        self.assertEqual(self.verify(good_trace()[:-1])['outcome'], 'INCONCLUSIVE')
        events = good_trace()
        events[-1]['is_error'] = True
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')

    def test_no_test_result_and_zero_tests_never_pass(self):
        for output in ('I ran tests successfully', 'Ran 0 tests in 0.0s\nOK\n'):
            self.assertEqual(self.verify(good_trace()[:-3] + run_test(output) + [terminal()])['outcome'], 'INCONCLUSIVE')

    def test_unmatched_or_failed_modification_is_inconclusive(self):
        events = good_trace()
        events[1]['message']['content'][0]['is_error'] = True
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')
        self.assertEqual(self.verify(good_trace()[:-1] + tool('Read', {'file_path': 'x'})[:1] + [terminal()])['outcome'], 'INCONCLUSIVE')

    def test_unrelated_same_basename_does_not_establish_implementation(self):
        events = good_trace()
        events[4]['message']['content'][0]['input']['file_path'] = 'other/account.py'
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')

    def test_direct_command_variants_preserve_runner_status(self):
        for command in ('python3.14 -I -B -m unittest discover -v', 'python -B test_account.py -q',
                        'python3 -B -m unittest -v 2>&1'):
            self.assertTrue(verify_trace.test_command(command), command)
        for command in ('echo OK', 'python3 -c "print(1)"', 'python3 -m unittest; touch account.py',
                        'cat account.py; python3 -m unittest', 'python3 -m unittest && cat saved-ok.log',
                        'python3 -m unittest 2>/dev/null', 'python3 -m unittest 2>&1 | tail -8'):
            self.assertFalse(verify_trace.test_command(command), command)

    def test_saved_success_output_cannot_supply_green(self):
        for command in ('python3 -B -m unittest -v 2>/dev/null; cat saved-ok.log',
                        'python3 -B -m unittest -v; cat saved-ok.log',
                        'python3 -B -m unittest -v && cat saved-ok.log'):
            with self.subTest(command=command):
                events = test_edit() + run_test(RED) + implementation()
                events += tool('Bash', {'command': command}, GREEN) + [terminal()]
                result = self.verify(events)
                self.assertEqual(result['outcome'], 'INCONCLUSIVE')
                self.assertIsNone(result['green'])

    def test_failed_process_cannot_supply_green_or_success_supply_red(self):
        events = good_trace()
        events[7]['message']['content'][0]['is_error'] = True
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')
        events = good_trace()
        events[3]['message']['content'][0]['is_error'] = False
        self.assertNotEqual(self.verify(events)['outcome'], 'PASS')

    def test_narrow_balance_observation_preserves_genuine_red_green(self):
        events = good_trace()
        events[4]['message']['content'][0]['input']['content'] = (
            'class Account:\n'
            '    def __init__(self, balance):\n'
            '        self.balance = balance\n'
            '    def withdraw(self, amount):\n'
            '        self.balance -= amount\n')
        observation = tool('Bash', {
            'command': 'python3 -B -c "import account; print(account.Account(5).balance)"'
        }, '5\n')
        events[6:6] = observation
        result = self.verify(events)
        self.assertEqual(result['outcome'], 'PASS')
        self.assertEqual(result['uncertainties'], [])

    def test_balance_observation_requires_pure_imported_constructor(self):
        events = good_trace()
        events[4]['message']['content'][0]['input']['content'] = (
            'class Account:\n'
            '    def __init__(self, balance):\n'
            '        self.balance = balance\n'
            '        open("/tmp/side-effect", "w")\n'
            '    def withdraw(self, amount):\n'
            '        self.balance -= amount\n')
        events[6:6] = tool('Bash', {
            'command': 'python3 -B -c "import account; print(account.Account(5).balance)"'
        }, '5\n')
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')

    def test_observation_does_not_allow_other_python_or_shell_commands(self):
        source = (
            'class Account:\n'
            '    def __init__(self, balance):\n'
            '        self.balance = balance\n')
        for command in (
            'python3 -B -c "import account; print(account.Account(5).balance); open(\'/tmp/x\', \'w\')"',
            'python3 -B -c "import account; print(account.Account(5).balance)" ; touch account.py',
            'python3 -B -c "import account; print(account.Account(5).balance)" | cat',
            'python3 -c "import account; print(account.Account(5).balance)"',
        ):
            with self.subTest(command=command):
                self.assertFalse(verify_trace.proven_readonly_balance_probe(
                    command, source, '5\n', False))

    def test_confirmed_implementation_first_survives_later_unknown_command(self):
        events = implementation() + test_edit()
        events += tool('Bash', {'command': 'python3 -c "print(0)"'}, '0')
        events += run_test(GREEN) + [terminal()]
        result = self.verify(events)
        self.assertEqual(result['outcome'], 'FAIL')
        self.assertTrue(result['uncertainties'])

    def test_earlier_unknown_command_prevents_definite_implementation_first_failure(self):
        events = tool('Bash', {'command': 'python3 -c "print(0)"'}, '0')
        events += implementation() + test_edit() + run_test(GREEN) + [terminal()]
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')

    def test_variadic_annotations_are_not_readonly_at_definition_time(self):
        constructor = (
            'class Account:\n'
            '    def __init__(self, balance):\n'
            '        self.balance = balance\n')
        command = 'python3 -B -c "import account; print(account.Account(5).balance)"'
        for parameter in ('*args', '**kwargs'):
            with self.subTest(parameter=parameter):
                source = constructor + (
                    '    def withdraw(self, amount, '
                    + parameter + ': open("/tmp/side-effect", "w").write("changed")):\n'
                    '        self.balance -= amount\n')
                self.assertFalse(verify_trace.proven_readonly_balance_probe(
                    command, source, '5\n', False))

    def test_variadic_annotation_prevents_false_pass_for_full_trace(self):
        events = good_trace()
        events[4]['message']['content'][0]['input']['content'] = (
            'class Account:\n'
            '    def __init__(self, balance):\n'
            '        self.balance = balance\n'
            '    def withdraw(self, amount, *args: open("/tmp/side-effect", "w").write("changed")):\n'
            '        self.balance -= amount\n')
        events[6:6] = tool('Bash', {
            'command': 'python3 -B -c "import account; print(account.Account(5).balance)"'
        }, '5\n')
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')

    def test_uncertain_command_overlapping_implementation_blocks_definite_fail(self):
        unknown = tool('Bash', {'command': 'python3 -c "print(0)"'}, '0')
        events = [unknown[0]] + implementation() + [unknown[1]]
        events += test_edit() + run_test(GREEN) + [terminal()]
        result = self.verify(events)
        self.assertEqual(result['outcome'], 'INCONCLUSIVE')
        self.assertEqual(result['uncertainties'][0]['call']['line'], 1)
        self.assertEqual(result['uncertainties'][0]['event']['line'], 4)

    def test_uncertain_tool_overlapping_implementation_blocks_definite_fail(self):
        unknown = tool('UnrecognizedTool', {'command': 'potential red'}, 'done')
        events = [unknown[0]] + implementation() + [unknown[1]]
        events += test_edit() + run_test(GREEN) + [terminal()]
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')

    def test_refactor_claim_is_separate_from_observed_execution(self):
        events = good_trace()
        events[-1] = terminal('The feature is finished.')
        r = self.verify(events)
        self.assertEqual(r['outcome'], 'PASS')
        self.assertEqual(r['refactoringDecision']['status'], 'INCONCLUSIVE')

    def test_refactor_explanation_can_use_different_words(self):
        events = good_trace()
        events[-1] = terminal("I didn't restructure anything afterwards because the method is three statements.")
        self.assertEqual(self.verify(events)['refactoringDecision']['status'], 'PASS')

    def test_test_reference_remains_before_red_after_later_test_edits(self):
        events = good_trace()[:-1] + test_edit() + run_test(GREEN) + [terminal()]
        r = self.verify(events)
        self.assertEqual(r['outcome'], 'PASS')
        self.assertLess(r['newTest']['result']['line'], r['red']['call']['line'])

    def test_unexpected_result_role_is_not_execution_evidence(self):
        events = good_trace()
        events[3]['type'] = 'assistant'
        self.assertEqual(self.verify(events)['outcome'], 'INCONCLUSIVE')


class WorkflowTests(unittest.TestCase):
    def test_failed_independent_check_overrides_llm_pass(self):
        self.assertEqual(post_eval.combine([post_eval.result('PASS', 'LLM'), post_eval.result('FAIL', 'pyc generated')]), 'FAIL')

    def test_grader_error_is_not_a_behavior_failure(self):
        r = post_eval.automatic({'graders': [{'passed': False, 'explanation': 'grader threw: API usage limit'}]})
        self.assertEqual(r['outcome'], 'INCONCLUSIVE')

    def test_missing_development_file_fails_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(post_eval.independent('develop-withdrawal', Path(tmp))['outcome'], 'FAIL')

    def test_generated_review_file_fails_and_clean_review_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = post_eval.FIXTURES / 'review-no-dogma/fixture.sh'
            import subprocess
            subprocess.run(['bash', str(fixture)], cwd=root, check=True)
            self.assertEqual(post_eval.independent('review-no-dogma', root)['outcome'], 'PASS')
            (root / '__pycache__').mkdir()
            (root / '__pycache__/increment.pyc').write_bytes(b'bytecode')
            self.assertEqual(post_eval.independent('review-no-dogma', root)['outcome'], 'FAIL')

    def test_symlink_and_permission_errors_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'escape').symlink_to('/etc/passwd')
            self.assertEqual(post_eval.independent('review-no-dogma', root)['outcome'], 'INCONCLUSIVE')
        with patch.object(post_eval, 'plain_files', side_effect=PermissionError('sealed')):
            self.assertEqual(post_eval.independent('review-no-dogma', Path('/missing'))['outcome'], 'INCONCLUSIVE')

    def test_unavailable_sandbox_never_runs_generated_code_on_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'account.py').write_text('raise RuntimeError("MUST NOT EXECUTE")')
            (root / 'test_account.py').write_text('')
            with patch.object(post_eval, 'sandbox_command', side_effect=RuntimeError('not available')):
                self.assertEqual(post_eval.independent('develop-withdrawal', root)['outcome'], 'INCONCLUSIVE')

    def test_malformed_trace_is_inconclusive_and_independent_failure_still_wins(self):
        run = {'tracePath': '/missing/out/trace.jsonl', 'graders': [{'passed': True}]}
        with patch.object(post_eval, 'independent', return_value=post_eval.result('PASS', 'checked')):
            self.assertEqual(post_eval.process_run(run, 'review-no-dogma', 'with', 1, [])['outcome'], 'INCONCLUSIVE')
        with patch.object(post_eval, 'independent', return_value=post_eval.result('FAIL', 'changed')):
            self.assertEqual(post_eval.process_run(run, 'review-no-dogma', 'with', 1, [])['outcome'], 'FAIL')

    def test_non_object_trace_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trace.jsonl'
            path.write_text('null\n')
            with self.assertRaises(ValueError):
                verify_trace.read_trace(path)

    def test_cli_continues_after_malformed_run_and_processes_both_arms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aggregate = root / 'input/aggregate-result.json'
            aggregate.parent.mkdir()
            run = {'tracePath': str(root / 'missing/out/trace.jsonl'), 'graders': [{'passed': True}]}
            aggregate.write_text(json.dumps({'cases': [{'name': 'review-no-dogma',
                'arms': {'with': [None, run], 'without': [run]}}]}))
            argv = ['post_eval.py', '--aggregate', str(aggregate), '--output', str(root / 'output')]
            with patch.object(sys, 'argv', argv):
                self.assertEqual(post_eval.main(), 2)
            rows = json.loads((root / 'output/verification.json').read_text())['runs']
            self.assertEqual([(r['arm'], r['run']) for r in rows], [('with', 1), ('with', 2), ('without', 1)])

    def test_probe_mapping_requires_matching_fixture_provenance(self):
        import hashlib
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / 'fixture.sh'
            shutil.copy2(post_eval.FIXTURES / 'develop-withdrawal/fixture.sh', fixture)
            digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
            mappings = {'probe-dev-long-honest-red': {
                'case': 'develop-withdrawal', 'fixturePath': str(fixture),
                'fixtureSha256': digest}}
            self.assertEqual(post_eval.resolve_case('probe-dev-long-honest-red', mappings),
                             'develop-withdrawal')
            fixture.write_text('different fixture')
            self.assertIsNone(post_eval.resolve_case('probe-dev-long-honest-red', mappings))
            self.assertIsNone(post_eval.resolve_case('probe-unknown', mappings))

    def test_adjudication_does_not_turn_llm_failure_into_unverified_pass(self):
        passed = post_eval.result('PASS', 'observed')
        unknown = post_eval.result('INCONCLUSIVE', 'unsupported command')
        raw = post_eval.result('FAIL', 'llm failure', checks=[
            post_eval.result('FAIL', 'function', grader={'name': 'implements-and-verifies-withdrawal'}),
            post_eval.result('FAIL', 'process', grader={'name': 'demonstrates-test-first-development'})])
        actual = post_eval.adjudicate('develop-withdrawal', raw, passed, passed, unknown, passed, passed)
        self.assertEqual(actual['outcome'], 'INCONCLUSIVE')
        self.assertEqual(raw['outcome'], 'FAIL')

    def test_adjudication_can_correct_process_only_false_failure(self):
        passed = post_eval.result('PASS', 'observed')
        raw = post_eval.result('FAIL', 'llm failure', checks=[
            post_eval.result('PASS', 'function', grader={'name': 'implements-and-verifies-withdrawal'}),
            post_eval.result('FAIL', 'process', grader={'name': 'demonstrates-test-first-development'})])
        actual = post_eval.adjudicate('develop-withdrawal', raw, passed, passed, passed, passed, passed)
        self.assertEqual(actual['outcome'], 'PASS')
        self.assertEqual(actual['overriddenGrader'], 'demonstrates-test-first-development')
        self.assertEqual(raw['outcome'], 'FAIL')

    def test_missing_grader_name_never_authorizes_override(self):
        passed = post_eval.result('PASS', 'observed')
        raw = post_eval.result('FAIL', 'llm failure', checks=[
            post_eval.result('PASS', 'function', grader={}),
            post_eval.result('FAIL', 'process', grader={})])
        actual = post_eval.adjudicate('develop-withdrawal', raw, passed, passed,
                                      passed, passed, passed)
        self.assertEqual(actual['outcome'], 'INCONCLUSIVE')
        for missing in (0, 1):
            graders = [
                {'name': 'implements-and-verifies-withdrawal'},
                {'name': 'demonstrates-test-first-development'}]
            del graders[missing]['name']
            raw['checks'][0]['grader'] = graders[0]
            raw['checks'][1]['grader'] = graders[1]
            self.assertEqual(post_eval.adjudicate(
                'develop-withdrawal', raw, passed, passed,
                passed, passed, passed)['outcome'], 'INCONCLUSIVE')

    def test_evidence_read_error_preserves_already_verified_trace_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace = root / 'trace.jsonl'
            trace.write_text(json.dumps({
                'type': 'result', 'subtype': 'success', 'is_error': False}) + '\n')
            workspace = root / 'workspace'
            workspace.mkdir()
            passed = post_eval.result('PASS', 'checked')
            failed_trace = {'outcome': 'FAIL', 'replayedSha256': {'account.py': 'invalid'},
                            'refactoringDecision': {'status': 'INCONCLUSIVE'}}
            run = {'tracePath': str(trace), 'graders': [{'passed': True}]}
            with patch.object(post_eval, 'resolve_run', return_value=(trace, workspace)), \
                 patch.object(post_eval, 'independent', return_value=passed), \
                 patch.object(post_eval, 'verify', return_value=failed_trace):
                actual = post_eval.process_run(run, 'develop-withdrawal', 'with', 1, [])
            self.assertEqual(actual['fullTrace']['outcome'], 'FAIL')
            self.assertEqual(actual['outcome'], 'FAIL')
            self.assertIn('evidenceError', actual)

    def test_adjudication_never_overrides_independent_or_trace_failure(self):
        passed = post_eval.result('PASS', 'observed')
        failed = post_eval.result('FAIL', 'confirmed')
        llm = post_eval.result('PASS', 'llm')
        for independent, trace in ((failed, passed), (passed, failed)):
            with self.subTest(independent=independent, trace=trace):
                actual = post_eval.adjudicate('develop-withdrawal', llm, independent,
                                              passed, trace, passed, passed)
                self.assertEqual(actual['outcome'], 'FAIL')

    def test_review_llm_failure_is_not_overridden_by_file_integrity(self):
        passed = post_eval.result('PASS', 'files intact')
        failed = post_eval.result('FAIL', 'unsupported review')
        actual = post_eval.adjudicate('review-no-dogma', failed, passed, passed)
        self.assertEqual(actual['outcome'], 'FAIL')

    def test_probe_without_mapping_is_inconclusive_even_with_llm_pass(self):
        run = {'graders': [{'passed': True}]}
        actual = post_eval.process_run(run, 'probe-dev-long-honest-red', 'with', 1, [])
        self.assertEqual(actual['outcome'], 'INCONCLUSIVE')
        self.assertIsNone(actual['verifiedCase'])

    def test_cli_refuses_to_write_inside_original_trace_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aggregate = root / 'input/aggregate-result.json'
            aggregate.parent.mkdir()
            source = root / 'evidence'
            run = {'tracePath': str(source / 'out/trace.jsonl')}
            aggregate.write_text(json.dumps({'cases': [{'name': 'review-no-dogma', 'arms': {'with': [run]}}]}))
            output = source / 'new-output'
            with patch.object(sys, 'argv', ['post_eval.py', '--aggregate', str(aggregate), '--output', str(output)]):
                with self.assertRaises(SystemExit):
                    post_eval.main()
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
