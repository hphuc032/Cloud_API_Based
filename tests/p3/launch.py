import os
from pathlib import Path
import sys
from deployment.common import configure_application, database_url
configure_application()
os.environ['P0_ADMIN_DATABASE_URL'] = database_url('postgres', Path('/run/secrets/postgres_password').read_text().strip())
import pytest
import conftest as baseline_fixtures
sys.exit(pytest.main(['-c', '/tests/p0/pytest.ini', '/tests/p3/test_identity.py',
                      '--tb=short', '-ra', '--junitxml=/results/p3-junit.xml'], plugins=[baseline_fixtures]))
