import os,sys
from pathlib import Path
from deployment.common import configure_application,database_url
configure_application()
os.environ['P0_ADMIN_DATABASE_URL']=database_url('postgres',Path('/run/secrets/postgres_password').read_text().strip())
os.environ['P1_MIGRATION_DATABASE_URL']=database_url('app_migrator',Path('/run/secrets/migration_password').read_text().strip())
sys.path[:0]=['/tests/p2','/tests/p3','/tests/p4']
import pytest,conftest as baseline_fixtures
focused='--focused' in sys.argv
targets=['/tests/p4/test_cutover.py::test_p4_realm_client_reproducibility',
 '/tests/p4/test_cutover.py::test_live_p4_global_rate_limit',
 '/tests/p2/test_tls.py::test_https_gateway_health_and_http_401_are_distinct_from_tls_failure'] if focused else [
 '/tests/p4/test_cutover.py','/tests/p2/test_tls.py','/tests/p1/test_privileges.py']
sys.exit(pytest.main(['-c','/tests/p0/pytest.ini',*targets,
 '--tb=short','-ra','-o','junit_family=legacy','--junitxml=/results/p4-'+('focused-' if focused else '')+'junit.xml'],plugins=[baseline_fixtures]))
