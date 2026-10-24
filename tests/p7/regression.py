"""P4 runner, with explicit operator-requested real-DNS scheduling deferral."""
import os
import runpy
import sys
import hashlib
import json
from pathlib import Path

if os.environ.get('P7_DEFER_PUBLIC_DNS') == '1':
    import pytest
    original = pytest.main

    def main(args, **kwargs):
        if '--focused' not in sys.argv:
            args = list(args) + ['-k',
                'not test_https_ssrf_uses_real_dns_and_preserves_roles or (not staff and not admin)']
            class SelectionReport:
                def pytest_deselected(self, items):
                    names = [item.name for item in items]
                    expected = ['test_https_ssrf_uses_real_dns_and_preserves_roles[staff-200]',
                                'test_https_ssrf_uses_real_dns_and_preserves_roles[admin-200]']
                    if sorted(names) != sorted(expected):
                        raise RuntimeError('Unexpected public-DNS selection scope')
                    Path('/results/p7-selection.json').write_text(json.dumps({
                        'status': 'NOT EXECUTED', 'names': names,
                        'reason': 'User deferred real DNS until later',
                        'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2))
            kwargs['plugins'] = list(kwargs.get('plugins', [])) + [SelectionReport()]
        return original(args, **kwargs)

    pytest.main = main

runpy.run_path('/tests/p4/launch.py', run_name='__main__')
