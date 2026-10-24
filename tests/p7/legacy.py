"""Unchanged P0/P1/P2/P3 driver, explicit optional DNS scheduling deferral.

Selection lives here, never in historical test assertions or xfail markers.
The ordinary tests/p3/run.py remains the full post-DNS-repair acceptance command.
"""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--defer-public-dns', action='store_true')
args = parser.parse_args()
deferred = []
if args.defer_public_dns:
    if os.environ.get('PYTEST_ADDOPTS'):
        parser.error('Use a clean PYTEST_ADDOPTS to keep exact case selection reviewable')
    os.environ['PYTEST_ADDOPTS'] = (
        "-k 'not test_https_ssrf_uses_real_dns_and_preserves_roles or (not staff and not admin)'")
    # Compose only forwards explicitly supplied variables. A private overlay
    # extends the caller source overlay without replacing any existing mounts.
    previous = os.environ.get('P3_SOURCE_OVERLAY')
    import tempfile
    overlay_temp = tempfile.TemporaryDirectory(prefix='cloud-api-p7-legacy-')
    overlay = Path(overlay_temp.name) / 'selection.yml'
    overlay.write_text((Path(previous).read_text() if previous else '') + '\n')
    # Preserve Compose's tagged build reset while adding a test environment key.
    import yaml
    class Reset:
        pass
    class Loader(yaml.SafeLoader):
        pass
    class Dumper(yaml.SafeDumper):
        pass
    Loader.add_constructor('!reset', lambda loader, node: Reset())
    Dumper.add_representer(Reset, lambda dumper, value: dumper.represent_scalar('!reset', 'null'))
    config = yaml.load(overlay.read_text(), Loader=Loader) or {}
    config.setdefault('services', {}).setdefault('tests', {}).setdefault('environment', {})['PYTEST_ADDOPTS'] = os.environ['PYTEST_ADDOPTS']
    overlay.write_text(yaml.dump(config, Dumper=Dumper))
    os.environ['P3_SOURCE_OVERLAY'] = str(overlay)
    original = unittest.TestLoader.loadTestsFromTestCase

    def select(self, case):
        suite = original(self, case)
        kept = []
        for test in suite:
            if test._testMethodName == 'test_public_dns_for_current_ssrf_validation':
                deferred.append({'id': test.id(), 'status': 'NOT EXECUTED', 'reason': 'User explicitly deferred real DNS for P7'})
            else:
                kept.append(test)
        return unittest.TestSuite(kept)

    unittest.TestLoader.loadTestsFromTestCase = select
sys.argv = [str(ROOT / 'tests/p3/run.py')]
try:
    runpy.run_path(str(ROOT / 'tests/p3/run.py'), run_name='__main__')
finally:
    output = ROOT / 'tests/p7/artifacts'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'legacy-deferred.json').write_text(json.dumps({'host_not_executed': deferred,
        'pytest_selection': os.environ.get('PYTEST_ADDOPTS', ''), 'strict_acceptance': 'BLOCKED' if args.defer_public_dns else 'NOT ASSESSED'}, indent=2))
