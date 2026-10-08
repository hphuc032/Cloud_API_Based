"""Validate enrolled client identities before loading the handshake trust anchors."""
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature


def validate_enrollment(directory):
    directory = Path(directory)
    roots = x509.load_pem_x509_certificates((directory / 'client-issuers.pem').read_bytes())
    pins = x509.load_pem_x509_certificates((directory / 'client-pins.pem').read_bytes())
    now = datetime.now(timezone.utc)
    for root in roots:
        if (not root.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
                or not root.not_valid_before_utc <= now < root.not_valid_after_utc):
            raise ValueError('Invalid client enrollment issuer')
    allowed = {'kong.internal', 'backend-health.internal'}
    enrolled = set()
    for cert in pins:
        if cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
            raise ValueError('Client trust pins must be leaf certificates, never CAs')
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
        if len(names) != 1 or names[0] not in allowed:
            raise ValueError('Unexpected enrolled client identity')
        for root in roots:
            try:
                cert.verify_directly_issued_by(root)
                break
            except (ValueError, TypeError, InvalidSignature):
                continue
        else:
            raise ValueError('Enrolled client was not issued by a trusted client issuer')
        enrolled.add(names[0])
    if enrolled != allowed:
        raise ValueError('Both gateway and local health identities must be enrolled')
