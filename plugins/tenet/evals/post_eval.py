#!/usr/bin/env python3
"""Verify every preserved eval run without changing evidence or calling a model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from verify_trace import FAIL, INCONCLUSIVE, PASS, read_trace, verify

HERE = Path(__file__).resolve().parent
CASES = {'review-domain-invariant', 'review-no-dogma', 'develop-withdrawal'}


def result(outcome, reason, **details):
    return dict(outcome=outcome, reason=reason, **details)


def combine(checks):
    outcomes = [c['outcome'] for c in checks]
    return FAIL if FAIL in outcomes else INCONCLUSIVE if INCONCLUSIVE in outcomes else PASS


def resolve_case(case, mappings):
    """Map a probe only when its fixture matches the trusted source fixture."""
    if case in CASES:
        return case
    entry = mappings.get(case)
    if not isinstance(entry, dict) or entry.get('case') not in CASES:
        return None
    fixture_path = entry.get('fixturePath')
    expected_hash = entry.get('fixtureSha256')
    if not isinstance(fixture_path, str) or not isinstance(expected_hash, str):
        return None
    candidate = Path(fixture_path)
    trusted = HERE / entry['case'] / 'fixture.sh'
    try:
        data = candidate.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest == expected_hash and data == trusted.read_bytes():
            return entry['case']
    except OSError:
        pass
    return None


def adjudicate(case, automatic_result, independent_result, completion, full_trace=None,
               consistency=None, refactoring=None):
    """Retain raw grader evidence and only replace judgments with adequate proof."""
    verified = [independent_result, completion]
    if full_trace is not None:
        verified.extend([full_trace, consistency, refactoring])
    if any(item['outcome'] == FAIL for item in verified):
        return result(FAIL, 'independent verification established a failure')
    if any(item['outcome'] == INCONCLUSIVE for item in verified):
        if automatic_result['outcome'] == FAIL and case == 'develop-withdrawal':
            return result(INCONCLUSIVE, 'LLM failure is not independently established; evidence incomplete')
        return result(combine([automatic_result, *verified]), 'verification incomplete')

    if automatic_result['outcome'] != FAIL:
        return result(automatic_result['outcome'], 'automatic and independent verification combined')

    if case != 'develop-withdrawal':
        return result(FAIL, 'review criteria are not established by workspace integrity alone')

    graders = automatic_result.get('checks', [])
    if len(graders) != 2:
        return result(INCONCLUSIVE, 'grader identity cannot be established')
    names = ['implements-and-verifies-withdrawal', 'demonstrates-test-first-development']
    verdicts = []
    for index, check in enumerate(graders):
        grader = check.get('grader', {})
        if grader.get('name') != names[index]:
            return result(INCONCLUSIVE, 'unexpected grader identity')
        verdicts.append(check['outcome'])
    if verdicts[0] == PASS and verdicts[1] == FAIL:
        return result(PASS, 'full-trace and independent checks establish test-first behavior',
                      overriddenGrader=names[1])
    return result(INCONCLUSIVE, 'LLM functional failure conflicts with independent evidence')


def plain_files(root):
    """Reject symlinks and surface inaccessible entries instead of skipping them."""
    if root.is_symlink():
        raise ValueError('workspace root is a symlink')
    files = {}
    def visit(directory):
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                if entry.is_symlink():
                    raise ValueError('symlink in workspace: ' + str(path))
                if entry.is_dir(follow_symlinks=False):
                    visit(path)
                elif entry.is_file(follow_symlinks=False):
                    files[str(path.relative_to(root))] = path.read_bytes()
                else:
                    raise ValueError('non-regular workspace entry: ' + str(path))
    visit(root)
    return files


def resolve_run(run, case, arm, number, roots):
    original = Path(run['tracePath'])
    # Prefer an explicitly selected preservation copy with matching provenance.
    for root in roots:
        candidate = root / case / f'{arm}-{number}'
        source = candidate / 'source.json'
        kept = candidate / 'kept-source.txt'
        if source.is_file():
            origin = json.loads(source.read_text())['source']
        elif kept.is_file():
            origin = kept.read_text().strip()
        else:
            continue
        if Path(origin) != original.parent.parent:
            continue
        workspace = candidate / 'workspace'
        if not workspace.exists():
            workspace = candidate / 'sealed/home/cwd'
        return candidate / 'out/trace.jsonl', workspace
    return original, original.parent.parent / 'sealed/home/cwd'


def automatic(run):
    graders = run.get('graders', [])
    if run.get('error') or run.get('skippedPaidGraders'):
        return result(INCONCLUSIVE, 'agent/API error or skipped grading', error=run.get('error'))
    if not isinstance(graders, list) or not graders:
        return result(INCONCLUSIVE, 'no grader results')
    checks = []
    for grader in graders:
        if not isinstance(grader, dict):
            checks.append(result(INCONCLUSIVE, 'malformed grader result'))
            continue
        if grader.get('scored') is False:
            continue
        explanation = str(grader.get('explanation', ''))
        if grader.get('error') or 'grader threw:' in explanation:
            checks.append(result(INCONCLUSIVE, 'grader error', grader=grader))
        elif isinstance(grader.get('passed'), bool):
            checks.append(result(PASS if grader['passed'] else FAIL, 'scored grader', grader=grader))
        else:
            checks.append(result(INCONCLUSIVE, 'missing grader verdict', grader=grader))
    return result(combine(checks) if checks else INCONCLUSIVE, 'automatic grader results', checks=checks)


def sandbox_command(work, argv):
    """macOS backend. No fallback to running generated code on the host."""
    if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').is_file():
        raise RuntimeError('macOS sandbox-exec is unavailable; development execution skipped')
    profile = work / 'isolation.sb'
    # Use the same restrictions as the preserved macOS independent checks.
    # System/runtime reads remain available; user data, network and outside writes do not.
    profile.write_text('(version 1)\n(allow default)\n(deny network*)\n'
                       '(deny file-read* (subpath "/Users"))\n(deny file-write*)\n'
                       '(allow file-read* file-write* (subpath ' + json.dumps(str(work)) + '))\n'
                       '(allow file-read* file-write* (literal "/dev/null") (literal "/dev/urandom"))\n')
    return ['/usr/bin/sandbox-exec', '-f', str(profile), *argv]


def isolated(work, argv):
    env = {'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin',
           'HOME': str(work), 'TMPDIR': str(work / 'tmp'), 'PYTHONDONTWRITEBYTECODE': '1'}
    return subprocess.run(sandbox_command(work, argv), cwd=work, env=env,
                          capture_output=True, text=True, timeout=60)


def independent(case, workspace):
    try:
        files = plain_files(workspace)
        if case == 'develop-withdrawal' and not {'account.py', 'test_account.py'} <= files.keys():
            return result(FAIL, 'required development file missing')
        with tempfile.TemporaryDirectory(prefix='tenet-post-eval-', dir='/private/tmp' if sys.platform == 'darwin' else None) as tmp:
            work = Path(tmp)
            (work / 'tmp').mkdir()
            copied = work / 'workspace'
            copied.mkdir()
            for name, data in files.items():
                if case == 'develop-withdrawal' and name != 'account.py':
                    continue
                target = copied / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            # Copy only the trusted verifier and fixture needed for this case.
            shutil.copy2(HERE / 'verify_case.py', work / 'verify_case.py')
            (work / case).mkdir()
            shutil.copy2(HERE / case / 'fixture.sh', work / case / 'fixture.sh')
            argv = [sys.executable, '-I', '-B', str(work / 'verify_case.py'), case, str(copied)]
            if case.startswith('review-'):
                proc = subprocess.run(argv, cwd=work, capture_output=True, text=True, timeout=30)
            else:
                # Verify restrictions before loading any agent-generated Python.
                probe = work / 'probe.py'
                probe.write_text('''import pathlib, socket
checks = [lambda: list(pathlib.Path('/Users').iterdir()),
          lambda: pathlib.Path(''' + repr(str(work) + '-outside') + ''').write_text('x'),
          lambda: socket.socket().connect(('127.0.0.1', 9))]
for check in checks:
    try:
        check()
    except PermissionError:
        continue
    raise SystemExit('restriction not enforced')
''')
                check = isolated(work, [sys.executable, '-I', '-B', str(probe)])
                if check.returncode:
                    return result(INCONCLUSIVE, 'isolation self-check failed; generated code not executed',
                                  exit=check.returncode, stdout=check.stdout, stderr=check.stderr)
                proc = isolated(work, argv)
            output = proc.stdout + proc.stderr
            if proc.returncode == 0:
                return result(PASS, 'independent fixture/behavior verification passed', output=output)
            if 'FAIL: review changed workspace' in output or 'FAILED (' in output:
                return result(FAIL, 'independent verification failed', output=output)
            return result(INCONCLUSIVE, 'verifier could not complete', exit=proc.returncode, output=output)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        return result(INCONCLUSIVE, 'workspace inaccessible, unsupported, or verifier unavailable', error=str(error))


def process_run(run, case, arm, number, roots, mappings=None):
    if not isinstance(run, dict):
        return {'case': case, 'arm': arm, 'run': number, 'outcome': INCONCLUSIVE,
                'evidenceError': result(INCONCLUSIVE, 'malformed run record')}
    row = {'case': case, 'arm': arm, 'run': number, 'automatic': automatic(run)}
    verified_case = resolve_case(case, mappings or {})
    row['verifiedCase'] = verified_case
    if verified_case is None:
        row['independent'] = result(INCONCLUSIVE, 'unsupported case or unverified fixture provenance')
        row['outcome'] = INCONCLUSIVE
        return row
    try:
        trace, workspace = resolve_run(run, case, arm, number, roots)
        row.update(trace=str(trace), workspace=str(workspace))
        row['independent'] = independent(verified_case, workspace)
        events = read_trace(trace)
        row['traceSha256'] = hashlib.sha256(trace.read_bytes()).hexdigest()
        row['eventCount'] = len(events)
        terminals = [e for e in events if e.get('type') == 'result']
        complete = len(terminals) == 1 and terminals[0].get('subtype') == 'success' and not terminals[0].get('is_error')
        row['completion'] = result(PASS if complete else INCONCLUSIVE, 'observed terminal execution status')
        if verified_case == 'develop-withdrawal':
            # Fixture content is trusted source, read without executing it here.
            fixture = (HERE / verified_case / 'fixture.sh').read_text()
            tests = fixture.split("cat > test_account.py <<'EOF'\n", 1)[1].split('\nEOF', 1)[0] + '\n'
            code = fixture.split("cat > account.py <<'EOF'\n", 1)[1].split('\nEOF', 1)[0] + '\n'
            row['fullTrace'] = verify(events, tests, code)
            mismatches = [name for name, digest in row['fullTrace']['replayedSha256'].items()
                          if hashlib.sha256((workspace / name).read_bytes()).hexdigest() != digest]
            row['replayConsistency'] = result(INCONCLUSIVE if mismatches else PASS,
                                             'replayed files compared with preserved workspace', mismatches=mismatches)
            row['adjudication'] = adjudicate(
                verified_case, row['automatic'], row['independent'], row['completion'],
                row['fullTrace'], row['replayConsistency'],
                {'outcome': row['fullTrace']['refactoringDecision']['status']})
        else:
            row['adjudication'] = adjudicate(
                verified_case, row['automatic'], row['independent'], row['completion'])
        row['outcome'] = row['adjudication']['outcome']
    except (OSError, ValueError, KeyError, IndexError, TypeError, SyntaxError) as error:
        row['evidenceError'] = result(INCONCLUSIVE, 'missing, restricted, or malformed evidence', error=str(error))
        checks = [row[key] for key in ('independent', 'completion', 'fullTrace', 'replayConsistency')
                  if key in row]
        row['outcome'] = FAIL if any(c['outcome'] == FAIL for c in checks) else INCONCLUSIVE
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aggregate', type=Path, action='append', required=True)
    parser.add_argument('--case-map', type=Path, help='JSON mapping probe names to verified fixture provenance')
    parser.add_argument('--run-root', type=Path, action='append', default=[],
                        help='Preserved root containing <case>/<arm>-<n> with matching source.json or kept-source.txt')
    parser.add_argument('--output', type=Path, required=True, help='New output directory; existing evidence is never replaced')
    args = parser.parse_args()
    output = args.output.resolve()
    protected = [p.resolve() for p in args.run_root] + [p.resolve().parent for p in args.aggregate]
    loaded, errors = [], []
    mappings = {}
    if args.case_map:
        try:
            mappings = json.loads(args.case_map.read_text())
            if not isinstance(mappings, dict):
                raise ValueError('case mapping must be a JSON object')
        except (OSError, ValueError) as error:
            parser.error('invalid case mapping: ' + str(error))
    for aggregate in args.aggregate:
        try:
            data = json.loads(aggregate.read_text())
            if not isinstance(data, dict) or not isinstance(data.get('cases'), list):
                raise ValueError('missing cases array')
            loaded.append((aggregate, data))
            for case in data['cases']:
                if not isinstance(case, dict) or not isinstance(case.get('arms'), dict):
                    continue
                for runs in case['arms'].values():
                    if isinstance(runs, list):
                        protected += [Path(r['tracePath']).resolve().parent.parent for r in runs
                                      if isinstance(r, dict) and isinstance(r.get('tracePath'), str)]
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append({'aggregate': str(aggregate), 'error': str(error)})
    if any(output == p or output.is_relative_to(p) for p in protected):
        parser.error('output must be outside original results and evidence')
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for aggregate, data in loaded:
        for case in data['cases']:
            if not isinstance(case, dict) or not isinstance(case.get('name'), str) or not isinstance(case.get('arms'), dict):
                errors.append({'aggregate': str(aggregate), 'error': 'malformed case'})
                continue
            if not case['arms']:
                errors.append({'aggregate': str(aggregate), 'case': case['name'], 'error': 'no arms'})
            for arm, runs in case['arms'].items():
                if not isinstance(runs, list) or not runs:
                    errors.append({'aggregate': str(aggregate), 'case': case['name'], 'arm': arm, 'error': 'missing run array'})
                    continue
                for number, run in enumerate(runs, 1):
                    row = process_run(run, case['name'], arm, number, args.run_root, mappings)
                    row['aggregate'] = str(aggregate)
                    rows.append(row)
    counts = {outcome: sum(r['outcome'] == outcome for r in rows) for outcome in (PASS, FAIL, INCONCLUSIVE)}
    overall = FAIL if counts[FAIL] else INCONCLUSIVE if counts[INCONCLUSIVE] or errors or not rows else PASS
    report = dict(schemaVersion=1, outcome=overall, counts=counts, errors=errors, runs=rows)
    (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = ['# Post-evaluation verification', '', f'Overall: {overall}', '',
             '| Case | Arm | Run | Outcome |', '| --- | --- | ---: | --- |']
    lines += [f"| {r['case']} | {r['arm']} | {r['run']} | {r['outcome']} |" for r in rows]
    (output / 'verification.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'outcome': overall, 'counts': counts, 'errors': errors}))
    return 0 if overall == PASS else 1 if overall == FAIL else 2


if __name__ == '__main__':
    sys.exit(main())
