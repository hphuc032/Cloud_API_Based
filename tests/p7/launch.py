"""Uses the same guarded disposable DB fixtures and genuine IdP token fixtures."""
import os
import sys
from pathlib import Path
from deployment.common import configure_application, database_url

configure_application()
os.environ['P0_ADMIN_DATABASE_URL'] = database_url('postgres', Path('/run/secrets/postgres_password').read_text().strip())
os.environ['P1_MIGRATION_DATABASE_URL'] = database_url('app_migrator', Path('/run/secrets/migration_password').read_text().strip())
sys.path[:0] = ['/tests/p2', '/tests/p3', '/tests/p4', '/tests/p5', '/tests/p6']
import pytest
import conftest as baseline_fixtures

sys.exit(pytest.main(['-c', '/tests/p0/pytest.ini', '/tests/p7/test_security.py',
    '--tb=short', '-ra', '-o', 'junit_family=legacy', '--junitxml=/results/p7-junit.xml'], plugins=[baseline_fixtures]))
