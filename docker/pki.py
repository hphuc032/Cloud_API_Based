"""Local DEVELOPMENT PKI only. Requires cryptography; never installs host trust."""
import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def write(path, data, private=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('xb') as stream:
        stream.write(data)
    os.chmod(path, 0o600 if private else 0o644)


def key_bytes(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def certificate_bytes(cert):
    return cert.public_bytes(serialization.Encoding.PEM)


def authority(name):
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'DEV ONLY ' + name)])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    return key, cert


def leaf(ca, name, names, client=False, expired=False, days=30, common_name=None):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    ca_key, ca_cert = ca
    start = now - timedelta(days=3) if expired else now - timedelta(minutes=5)
    end = now - timedelta(days=1) if expired else min(now + timedelta(days=days), ca_cert.not_valid_after_utc)
    if end <= start:
        raise ValueError('CA must be renewed before issuing leaves')
    sans = []
    for name_value in names:
        try:
            sans.append(x509.IPAddress(ipaddress.ip_address(name_value)))
        except ValueError:
            sans.append(x509.DNSName(name_value))
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name or name)]))
            .issuer_name(ca_cert.subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(start).not_valid_after(end)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH if client else ExtendedKeyUsageOID.SERVER_AUTH]), critical=True)
            .add_extension(x509.SubjectAlternativeName(sans), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    return key, cert


def save_leaf(directory, ca, name, names, **kwargs):
    key, cert = leaf(ca, name, names, **kwargs)
    write(Path(directory) / (name + '.key'), key_bytes(key), private=True)
    write(Path(directory) / (name + '.pem'), certificate_bytes(cert))
    return certificate_bytes(cert)


def generate(directory, ca_directory=None, test_fixtures=False):
    directory = Path(directory)
    if directory.exists():
        raise ValueError('Output must be a NEW directory; existing PKI is never overwritten')
    directory.mkdir(parents=True, mode=0o700)
    cas = {}
    for name in ('server', 'client', 'edge'):
        if ca_directory:
            source = Path(ca_directory)
            ca = (serialization.load_pem_private_key((source / (name + '.key')).read_bytes(), password=None),
                  x509.load_pem_x509_certificate((source / (name + '.pem')).read_bytes()))
        else:
            ca = authority(name)
            write(directory / 'offline' / (name + '.key'), key_bytes(ca[0]), private=True)
            write(directory / 'offline' / (name + '.pem'), certificate_bytes(ca[1]))
        cas[name] = ca
        write(directory / 'trust' / (name + '-ca.pem'), certificate_bytes(ca[1]))
    save_leaf(directory / 'backend', cas['server'], 'server', ['backend'])
    kong = save_leaf(directory / 'kong', cas['client'], 'client', ['kong.internal'], client=True)
    health = save_leaf(directory / 'backend', cas['client'], 'health', ['backend-health.internal'], client=True)
    save_leaf(directory / 'kong', cas['edge'], 'edge', ['localhost', '127.0.0.1', 'kong'])
    write(directory / 'backend/client-pins.pem', kong + health)
    write(directory / 'backend/client-issuers.pem', certificate_bytes(cas['client'][1]))
    for peer in ('backend', 'kong'):
        write(directory / peer / 'server-ca.pem', certificate_bytes(cas['server'][1]))
    # Container identity: Kong's image runs as uid 1000. Bind mounts preserve Linux owners.
    # Windows ACLs must be restricted separately; chmod/chown are not an ACL substitute.
    if os.name != 'nt' and os.geteuid() == 0:
        for path in (directory / 'kong').iterdir():
            os.chown(path, 1000, 1000)
        os.chown(directory / 'kong', 1000, 1000)
        os.chmod(directory / 'kong', 0o700)
    if test_fixtures:
        rogue = authority('untrusted test issuer')
        fixtures = directory / 'negative'
        save_leaf(fixtures, rogue, 'untrusted', ['kong.internal'], client=True)
        save_leaf(fixtures, cas['client'], 'expired', ['kong.internal'], client=True, expired=True)
        save_leaf(fixtures, cas['client'], 'unenrolled', ['kong.internal'], client=True)
        save_leaf(fixtures, cas['client'], 'wrong-client-eku', ['kong.internal'])
        # A matching CN must not rescue a certificate with a conflicting SAN.
        save_leaf(fixtures, cas['server'], 'wrong-san', ['other.internal'], common_name='backend')
        save_leaf(fixtures, rogue, 'wrong-chain', ['backend'])
        save_leaf(fixtures, cas['server'], 'expired-server', ['backend'], expired=True)
        save_leaf(fixtures, cas['server'], 'wrong-server-eku', ['backend'], client=True)
    return directory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parent / 'certs')
    parser.add_argument('--ca-directory', type=Path, help='Reuse DEV issuer keys for leaf renewal into a NEW directory')
    parser.add_argument('--development-only', action='store_true', required=True)
    args = parser.parse_args()
    generate(args.directory, args.ca_directory)
    print('Development PKI created. Private keys and offline issuers must never be committed.')
