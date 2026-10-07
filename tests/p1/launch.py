import os
from pathlib import Path
import sys

from deployment.common import configure_application, database_url

configure_application()
for envname, role, filename in (
    ("P0_ADMIN_DATABASE_URL", "postgres", "postgres_password"),
    ("P1_MIGRATION_DATABASE_URL", "app_migrator", "migration_password"),
):
    os.environ[envname] = database_url(role, Path("/run/secrets/" + filename).read_text().strip())

import pytest
sys.exit(pytest.main(["-c", "/tests/p0/pytest.ini", "/tests/p0", "/tests/p1/test_privileges.py", "/tests/p1/test_adoption.py",
                      "--tb=short", "-ra", "--junitxml=/results/junit.xml"]))
