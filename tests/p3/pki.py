"""Disposable identity TLS, separate from P2 service/client authorities."""
from pathlib import Path

def generate(directory, pki):
    directory=Path(directory)
    ca=pki.authority("identity")
    pki.save_leaf(directory / "keycloak", ca, "server", ["keycloak"])
    pki.save_leaf(directory / "edge", ca, "server", ["identity-edge", "localhost"])
    pki.write(directory / "keycloak/identity-ca.pem", pki.certificate_bytes(ca[1]))
    pki.write(directory / "edge/identity-ca.pem", pki.certificate_bytes(ca[1]))
    pki.write(directory / "trust/identity-ca.pem", pki.certificate_bytes(ca[1]))
    return directory
