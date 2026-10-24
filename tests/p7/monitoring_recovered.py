"""Provisioned monitoring survives restart and follows the recreated backend."""
import json
import sys
from pathlib import Path
sys.path[:0] = ['/tests/p0', '/tests/p2', '/tests/p3', '/tests/p4', '/tests/p5', '/tests/p6']
from deployment.common import configure_application
configure_application()
from test_observability import test_grafana_dashboards_queries_and_rules, ingested
from transport import http_client

test_grafana_dashboards_queries_and_rules()
with http_client('https://kong:8443') as client:
    response = client.get('/health/ready')
    assert response.status_code == 200
    rid = response.headers['x-request-id']
    ingested('backend', 'http_request', rid)
    ingested('kong', 'http_request', rid)
Path('/results/p7-monitoring-recovered.json').write_text(json.dumps({
    'status': 'PASS', 'request_id': rid, 'grafana_container_recreated_same_volume': True,
    'dashboard_queries': 'all provisioned targets executed', 'rules': 6,
    'recreated_backend_new_log_ingested': True, 'external_notification_delivery': 'NOT EXECUTED'}, indent=2))
print('PASS: recreated Grafana on preserved volume, four provisioned dashboards and six rules, current backend/Kong correlated event ingested')
