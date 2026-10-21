import os,sys
from pathlib import Path
from deployment.common import configure_application,database_url
configure_application()
os.environ['P0_ADMIN_DATABASE_URL']=database_url('postgres',Path('/run/secrets/postgres_password').read_text().strip())
os.environ['P1_MIGRATION_DATABASE_URL']=database_url('app_migrator',Path('/run/secrets/migration_password').read_text().strip())
sys.path[:0]=['/tests/p2','/tests/p3','/tests/p4']
import pytest,conftest as baseline_fixtures
sys.exit(pytest.main(['-c','/tests/p0/pytest.ini','/tests/p5/test_hardening.py','/tests/p5/test_gateway.py','/tests/p5/test_configuration.py',
 '--tb=short','-ra','-o','junit_family=legacy','--junitxml=/results/p5-hardening-junit.xml'],plugins=[baseline_fixtures]))
