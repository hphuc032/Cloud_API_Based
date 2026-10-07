"""Generate NEW deployment secrets only. Never overwrite an existing secret."""
import argparse
import os
from pathlib import Path
import secrets

NAMES = ("postgres_password", "migration_password", "runtime_password", "jwt_secret",
         "webhook_secret", "keycloak_admin_password", "grafana_admin_password")


def generate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if any((directory / name).exists() for name in NAMES):
        raise RuntimeError("Secret files already exist; preserve them or rotate deliberately")
    for name in NAMES:
        with os.fdopen(os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            stream.write(secrets.token_hex(32) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-deployment", action="store_true", required=True)
    parser.add_argument("--directory", default=str(Path(__file__).resolve().parent / ".secrets"))
    args = parser.parse_args()
    generate(args.directory)
    print("Created secret files; restrict directory access with host filesystem permissions.")
