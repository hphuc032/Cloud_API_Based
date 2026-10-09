"""Bounded HTTPS JWKS loading shared by resource server and public-key renderer."""
import json
import re
import threading
import time

import httpx
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import JWTError, jwt
from jose.utils import base64url_decode


KID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def fetch_signing_keys(issuer, ca_file=None):
    """Only the configured realm's bounded, verified HTTPS endpoint is consulted."""
    with httpx.Client(verify=ca_file or True, timeout=5, follow_redirects=False,
                      trust_env=False) as client:
        with client.stream("GET", issuer + "/protocol/openid-connect/certs") as response:
            response.raise_for_status()
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > 65536:
                    raise ValueError("JWKS exceeds size limit")
    document = json.loads(raw)
    items = document.get("keys")
    if not isinstance(items, list) or not 1 <= len(items) <= 16:
        raise ValueError("Invalid JWKS collection")
    keys = {}
    for key in items:
        if not isinstance(key, dict):
            raise ValueError("Invalid public key")
        if key.get("use") != "sig" or key.get("alg") != "RS256":
            continue
        kid = key.get("kid")
        if (not isinstance(kid, str) or not KID.fullmatch(kid) or kid in keys or
                key.get("kty") != "RSA" or
                any(name in key for name in ("d", "p", "q", "dp", "dq", "qi", "oth", "k"))):
            raise ValueError("Invalid or conflicting signing key")
        n = int.from_bytes(base64url_decode(key["n"].encode()), "big")
        e = int.from_bytes(base64url_decode(key["e"].encode()), "big")
        if n.bit_length() < 2048 or e != 65537:
            raise ValueError("Unsupported RSA public key")
        rsa.RSAPublicNumbers(e, n).public_key()  # validate the public parameters
        keys[kid] = key
    if not keys:
        raise ValueError("No trusted RS256 signing keys")
    return keys


class JWKSCache:
    def __init__(self, issuer, ca_file, ttl=60, refresh_interval=5):
        self.issuer, self.ca_file = issuer, ca_file
        self.ttl, self.refresh_interval = ttl, refresh_interval
        self.keys, self.expires, self.last_attempt = {}, 0, float("-inf")
        self.lock = threading.Lock()

    def key(self, kid):
        with self.lock:
            now = time.monotonic()
            if now >= self.expires or kid not in self.keys:
                if now - self.last_attempt < self.refresh_interval:
                    # An expired cache never becomes a fail-open stale-key cache.
                    if now >= self.expires or kid not in self.keys:
                        raise JWTError("Signing key unavailable")
                else:
                    self.last_attempt = now
                    try:
                        keys = fetch_signing_keys(self.issuer, self.ca_file)
                    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
                        raise JWTError("Signing key unavailable") from exc
                    self.keys, self.expires = keys, time.monotonic() + self.ttl
            if kid not in self.keys:
                raise JWTError("Unknown signing key")
            return self.keys[kid]
