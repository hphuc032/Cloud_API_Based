"""Curate explicitly allowed public evidence; never copy dumps, inspect or tokens."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
ALLOW = ('run.json', 'p4-host.json', 'p3-host.json', 'host-results.json',
         'tls-host-results.json', 'browser-results.json', 'p5-browser-results.json',
         'key-rotation-results.json', 'p6-lifecycle.json', 'p6-transport-ingestion.json',
         'p6-alert-evaluation.json', 'p6-alert-four-rules.json', 'p6-alert-upstream-errors.json',
         'image-source-evidence.json', 'p7-scenarios.json', 'p7-recovery.json',
         'p7-monitoring-recovered.json', 'p7-selection.json', 'oidc-evidence.json')


def cases(path):
    rows = []
    for case in ET.parse(path).iter('testcase'):
        row = {'file': case.get('file'), 'name': case.get('name'), 'seconds': float(case.get('time', 0)), 'status': 'PASS'}
        for tag in ('failure', 'error', 'skipped'):
            child = case.find(tag)
            if child is not None:
                row['status'] = 'EXPECTED FAILURE' if child.get('type') == 'pytest.xfail' else 'NOT EXECUTED' if tag == 'skipped' else 'FAIL'
                row['result_kind'] = tag
                # No raw exception, captured output or credential-bearing requests.
                break
        rows.append(row)
    return {'counts': {status: sum(row['status'] == status for row in rows) for status in ('PASS', 'FAIL', 'EXPECTED FAILURE', 'NOT EXECUTED')}, 'cases': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', nargs=2, metavar=('LABEL', 'DIRECTORY'), required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/testing')
    args = parser.parse_args()
    evidence, results, commands = {}, {}, {}
    for label, directory in args.run:
        source = Path(directory)
        run = json.loads((source / 'run.json').read_text())
        cutoff = datetime.fromisoformat(run['started_utc']).timestamp()
        def fresh(path):
            return path.is_file() and path.stat().st_mtime >= cutoff
        results[label] = {p.name: cases(p) for p in source.glob('*junit.xml') if fresh(p)}
        evidence[label] = {name: json.loads((source / name).read_text()) for name in ALLOW if fresh(source / name)}
        commands[label] = json.loads((source / 'commands.json').read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in [('case-results', results), ('runtime-evidence', evidence), ('commands', commands)]:
        (args.output / ('p7-' + name + '.json')).write_text(json.dumps(data, indent=2) + '\n')
    base = '45e025703f6a193aeb5738632d436d52146f12de'
    paths = subprocess.check_output(['git', 'ls-files', 'backend', 'frontend', 'gateway', 'docker', 'monitoring', 'tests/p0', 'tests/p1', 'tests/p2', 'tests/p3', 'tests/p4', 'tests/p5', 'tests/p6'], cwd=ROOT, text=True).splitlines()
    preserved = {}
    for path in paths:
        before = subprocess.check_output(['git', 'show', base + ':' + path], cwd=ROOT)
        after = (ROOT / path).read_bytes()
        preserved[path] = {'sha256': hashlib.sha256(after).hexdigest(), 'equal_approved_p6': before == after}
    (args.output / 'p7-preservation.json').write_text(json.dumps({'base': base, 'all_equal': all(p['equal_approved_p6'] for p in preserved.values()), 'files': preserved}, indent=2) + '\n')
    print(json.dumps({label: {p: r['counts'] for p, r in group.items()} for label, group in results.items()}, indent=2))


if __name__ == '__main__':
    main()
