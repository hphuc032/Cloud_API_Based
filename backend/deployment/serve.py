import os

from deployment.common import configure_application

configure_application()
os.execvp("uvicorn", ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"])
