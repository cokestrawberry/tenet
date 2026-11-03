"""Conservative evidence checks for the withdrawal fixture; never execute trace content."""
import ast
import hashlib
import json
from pathlib import PurePosixPath
import re
import shlex

PASS, FAIL, INCONCLUSIVE = 'PASS', 'FAIL', 'INCONCLUSIVE'


def content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(b.get('text', '') for b in content if isinstance(b, dict))
    return ''


def test_command(command):
    """Accept unittest runners plus non-writing output filters, not arbitrary shell code."""
    parts = shell_parts(command)
    if parts is None:
        return False
    runners = [p for p in parts if unittest_runner(p)]
    return len(runners) == 1 and all(unittest_runner(p) or read_command(p) for p in parts)


def shell_parts(command):
    command = command.replace('2>&1', '').replace('2>/dev/null', '')
    if any(x in command for x in ('`', '$', '\n', '<', '>', '||', '&>')):
        return None
    lexer = shlex.shlex(command, posix=True, punctuation_chars='|;&')
    lexer.whitespace_split = True
    parts, part = [], []
    try:
        for token in lexer:
            if token in ('|', ';', '&&'):
                parts.append(part)
                part = []
            elif token == '&':
                return None
            else:
                part.append(token)
    except ValueError:
        return None
    parts.append(part)
    return parts if all(parts) else None


def unittest_runner(first):
    if not first or not re.fullmatch(r'python(?:\d+(?:\.\d+)*)?', PurePosixPath(first[0]).name):
        return False
    tail = first[1:]
    while tail and tail[0] in ('-B', '-I', '-u'):
        tail = tail[1:]
    if tail[:2] == ['-m', 'unittest']:
        args = tail[2:]
    elif tail[:1] == ['test_account.py']:
        args = tail[1:]
    else:
        return False
    return all(x in ('-v', '-q', 'discover', '.', '-s', '-p', 'test*.py')
               or x == 'test_account.py' or re.fullmatch(r'test_account(?:\.\w+)*', x) for x in args)


def read_command(part):
    if not part:
        return False
    if part[0] == 'git':
        return part[1:2] in (['status'], ['diff']) and not any(
            arg.startswith(('--output', '--ext-diff', '--exec', '-c')) for arg in part[2:])
    if part[0] == 'echo':
        return all(re.fullmatch(r'[-= ]*', arg) for arg in part[1:])
    if part[0] in ('ls', 'cat', 'head', 'tail', 'grep', 'pwd', 'wc'):
        return True
    if part[0] == 'find':
        return all(not arg.startswith('-') or arg in ('-name', '-path', '-not', '-maxdepth', '-type', '-print')
                   for arg in part[1:])
    return bool(re.fullmatch(r'python[\d.]*', part[0]) and part[1:] == ['--version'])


def functions(source):
    tree = ast.parse(source)
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test')}


def behavior_tests(before, after):
    old, new = functions(before), functions(after)
    names = []
    for name, node in new.items():
        if name in old and ast.dump(node) == ast.dump(old[name]):
            continue
        calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
        invokes = any(isinstance(n.func, ast.Attribute) and n.func.attr == 'withdraw' for n in calls)
        asserts = any(isinstance(n.func, ast.Attribute) and (
            n.func.attr in ('assertEqual', 'assertAlmostEqual') and any(
                isinstance(a, ast.Attribute) and a.attr == 'balance' for a in ast.walk(n))
            or n.func.attr in ('assertRaises', 'assertRaisesRegex') and n.args
            and isinstance(n.args[0], ast.Name) and n.args[0].id == 'ValueError') for n in calls)
        if invokes and asserts:
            names.append(name)
    return names


def verify(events, fixture_tests, fixture_code='class Account:\n    def __init__(self, balance):\n        self.balance = balance\n'):
    """Return event references (one-based JSONL line and block index) and separate claims."""
    calls, actions, terminal, final = {}, [], None, None
    uncertain = []
    tests = fixture_tests
    production = fixture_code
    test_change = None
    new_names = []
    implementation = None
    red = None
    red_test_change = None
    green = None
    cwd = next((e.get('cwd') for e in events if e.get('type') == 'system' and e.get('subtype') == 'init'), None)
    for line, event in enumerate(events, 1):
        if event.get('type') == 'result':
            terminal = event
            final = (line, content_text(event.get('result')))
        blocks = event.get('message', {}).get('content', [])
        if not isinstance(blocks, list):
            continue
        for block_index, block in enumerate(blocks):
            ref = {'line': line, 'block': block_index}
            if event.get('type') == 'assistant' and block.get('type') == 'text':
                final = (line, block.get('text', ''))
            if block.get('type') == 'tool_use':
                if event.get('type') != 'assistant':
                    uncertain.append({'reason': 'tool call in unexpected message role', 'event': ref})
                    continue
                if block['id'] in calls:
                    uncertain.append({'reason': 'duplicate tool ID', 'event': ref})
                calls[block['id']] = (ref, block.get('name'), block.get('input', {}))
            if block.get('type') != 'tool_result':
                continue
            if event.get('type') != 'user':
                uncertain.append({'reason': 'tool result in unexpected message role', 'event': ref})
                continue
            call = calls.pop(block.get('tool_use_id'), None)
            if call is None:
                uncertain.append({'reason': 'unmatched tool result', 'event': ref})
                continue
            call_ref, tool, inp = call
            action = {'call': call_ref, 'result': ref, 'tool': tool}
            output = content_text(block.get('content'))
            if tool in ('Edit', 'Write'):
                path = PurePosixPath(inp.get('file_path', ''))
                action['file'] = str(path)
                if path.parent != PurePosixPath('.') and (cwd is None or path.parent != PurePosixPath(cwd)):
                    uncertain.append({'reason': 'modification outside recognized fixture paths', 'event': ref})
                    actions.append(action)
                    continue
                # A failed modification cannot establish that the file changed.
                if block.get('is_error'):
                    uncertain.append({'reason': 'failed file modification', 'event': ref})
                elif path.name == 'test_account.py':
                    green = None
                    previous = tests
                    if tool == 'Write':
                        tests = inp.get('content', '')
                    elif inp.get('old_string') and tests.count(inp['old_string']) == 1:
                        tests = tests.replace(inp['old_string'], inp.get('new_string', ''), 1)
                    else:
                        uncertain.append({'reason': 'cannot replay test modification', 'event': ref})
                    try:
                        added = behavior_tests(previous, tests)
                        if added:
                            new_names = added
                            test_change = action
                    except SyntaxError:
                        uncertain.append({'reason': 'cannot parse modified tests', 'event': ref})
                elif path.name == 'account.py':
                    previous = production
                    if tool == 'Write':
                        production = inp.get('content', '')
                    elif inp.get('old_string') and production.count(inp['old_string']) == 1:
                        production = production.replace(inp['old_string'], inp.get('new_string', ''), 1)
                    else:
                        uncertain.append({'reason': 'cannot replay production modification', 'event': ref})
                    try:
                        def method(source):
                            tree = ast.parse(source)
                            for node in tree.body:
                                if isinstance(node, ast.ClassDef) and node.name == 'Account':
                                    return next((ast.dump(n) for n in node.body if isinstance(n, ast.FunctionDef)
                                                 and n.name == 'withdraw'), None)
                            return None
                        if method(production) != method(previous):
                            implementation = implementation or action
                            green = None  # Later implementation changes require another passing test.
                    except SyntaxError:
                        uncertain.append({'reason': 'cannot parse modified implementation', 'event': ref})
                else:
                    uncertain.append({'reason': 'unrecognized modified file', 'event': ref})
            elif tool == 'Bash':
                command = inp.get('command', '')
                action['command'] = command
                if test_command(command):
                    runs = re.findall(r'^Ran (\d+) tests? in .+$', output, re.M)
                    ok = bool(re.search(r'^OK\s*$', output, re.M))
                    failed = bool(re.search(r'^FAILED \([^\n]+\)\s*$', output, re.M))
                    action['observed'] = PASS if len(runs) == 1 and ok and not failed and not block.get('is_error') else (
                        FAIL if len(runs) == 1 and failed and not ok else INCONCLUSIVE)
                    if action['observed'] == INCONCLUSIVE:
                        uncertain.append({'reason': 'test output has no unambiguous runner result', 'event': ref})
                    if action['observed'] == FAIL and test_change and not implementation:
                        # Tie the observed failure to the newly added behavior, not to a claim.
                        missing = "AttributeError: 'Account' object has no attribute 'withdraw'" in output
                        errors = re.search(r'^FAILED \(errors=(\d+)\)\s*$', output, re.M)
                        expected = missing and errors and int(errors[1]) == output.count(
                            "AttributeError: 'Account' object has no attribute 'withdraw'")
                        infrastructure = re.search(r'ImportError|ModuleNotFoundError|SyntaxError|PermissionError', output)
                        if expected and not infrastructure and int(runs[-1]) == len(functions(tests)):
                            red = action
                            red_test_change = test_change
                    if action['observed'] == PASS and implementation:
                        if int(runs[-1]) > 0 and int(runs[-1]) == len(functions(tests)):
                            green = action
                        else:
                            green = None
                            uncertain.append({'reason': 'test count does not cover the replayed test file', 'event': ref})
                elif shell_parts(command) is None or not all(read_command(p) for p in shell_parts(command)):
                    uncertain.append({'reason': 'shell command may modify files or run unsupported tests', 'event': ref})
            elif tool not in ('Read', 'Glob', 'Grep', 'Skill', 'TaskStop', 'ToolSearch'):
                uncertain.append({'reason': 'unsupported tool may modify workspace', 'event': ref})
            actions.append(action)
    if calls:
        uncertain.append({'reason': 'tool calls without results', 'calls': [c[0] for c in calls.values()]})
    decision = {'status': INCONCLUSIVE, 'source': 'agent claim', 'event': None, 'text': ''}
    if final:
        decision['event'] = {'line': final[0]}
        sentences = re.split(r'(?<=[.!?])\s+|\n', final[1])
        selected = [s for s in sentences if re.search(r'\b(?:refactor|restructur|simplif)\w*\b', s, re.I)]
        decision['text'] = '\n'.join(selected)
        if any(re.search(r'because|unnecessary|none needed|no .{0,25}needed|not needed|judged', s, re.I) for s in selected):
            decision['status'] = PASS
    complete = terminal is not None and not terminal.get('is_error') and terminal.get('subtype') == 'success'
    if not complete or uncertain:
        outcome, reason = INCONCLUSIVE, 'incomplete or unsupported execution evidence'
    elif implementation and not red:
        outcome, reason = (FAIL, 'implementation preceded an observed relevant failing test') if test_change else (
            INCONCLUSIVE, 'no recognized new behavior test')
    elif red and implementation and green:
        outcome, reason = PASS, 'observed new-test failure, implementation change, then passing tests'
    else:
        outcome, reason = INCONCLUSIVE, 'missing failure, implementation, or final passing execution'
    return {'outcome': outcome, 'reason': reason, 'newTest': red_test_change or test_change, 'red': red,
            'implementation': implementation, 'green': green, 'refactoringDecision': decision,
            'uncertainties': uncertain, 'actions': actions, 'complete': complete,
            'replayedSha256': {name: hashlib.sha256(text.encode()).hexdigest() for name, text in
                               [('account.py', production), ('test_account.py', tests)]}}


def read_trace(path):
    with path.open() as stream:
        events = [json.loads(line) if line.strip() else {} for line in stream]
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get('message', {}), dict):
            raise ValueError('malformed trace event')
        content = event.get('message', {}).get('content', [])
        if isinstance(content, list) and any(not isinstance(block, dict) for block in content):
            raise ValueError('malformed trace content block')
        if isinstance(content, list) and any(block.get('type') == 'tool_use'
                                            and not isinstance(block.get('input'), dict) for block in content):
            raise ValueError('malformed tool input')
    return events
