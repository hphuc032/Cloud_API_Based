import os
from pathlib import Path
import sys

from deployment.common import configure_application, database_url

configure_application()
os.environ['P0_ADMIN_DATABASE_URL'] = database_url('postgres', Path('/run/secrets/postgres_password').read_text().strip())
import pytest
import conftest as baseline_fixtures
sys.exit(pytest.main(['-c', '/tests/p0/pytest.ini', '/tests/p2/test_tls.py',
                      '/tests/p2/test_https_business.py', '--tb=short', '-ra',
                      '-o', 'junit_family=legacy',
                      '--junitxml=/results/p2-junit.xml'], plugins=[baseline_fixtures]))
