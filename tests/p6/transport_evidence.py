"""Validate sanitized transport reasons in actual Loki after original P2 probes."""
import sys,time,json
from pathlib import Path
from deployment.common import configure_application
configure_application()
sys.path[:0]=['/tests/p2','/tests/p3','/tests/p4','/tests/p5']
from test_observability import query
expected={'does not match','unable to verify the first certificate','certificate has expired','unsuitable certificate purpose'}
for _ in range(30):
 rows=query('{service="kong"} | json | event_type="mtls_verification_failed"')
 if expected<={r.get('security_reason') for r in rows}:break
 time.sleep(1)
else:raise AssertionError('Actual TLS reasons missing from Loki')
assert all(set(r)<={'service','level','event_type','event_outcome','security_reason','request_id','status_code'} for r in rows)
assert all(r['request_id']=='unattributed' for r in rows)
Path('/results/p6-transport-ingestion.json').write_text(json.dumps({'expected_reasons':sorted(expected),'observed_reasons':sorted({r['security_reason'] for r in rows}),'raw_error_persisted':False,'samples':rows[:8]},indent=2))
print('PASS: all four real TLS verification failures collected by Alloy and queried from Loki; raw error text excluded')
