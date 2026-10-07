import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl

from app.auth.dependencies import require_staff_or_admin
from app.models.user import User

router = APIRouter(
    prefix="/security",
    tags=["Security"],
)

ALLOWED_DOMAINS = {
    "example.com",
    "api.partner.com",
    "cdn.company.com",
}

PRIVATE_HOSTNAMES = {
    "localhost",
}

BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class URLRequest(BaseModel):
    url: HttpUrl


def _is_allowed_domain(hostname: str) -> bool:
    hostname = hostname.lower().strip(".")

    return any(
        hostname == domain or hostname.endswith("." + domain)
        for domain in ALLOWED_DOMAINS
    )


def _resolve_host(hostname: str):
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to resolve hostname",
        )

    addresses = []

    for item in addr_info:
        ip = item[4][0]
        try:
            addresses.append(ipaddress.ip_address(ip))
        except ValueError:
            continue

    return list(set(addresses))


def _is_blocked_ip(ip) -> bool:
    return any(ip in network for network in BLOCKED_NETWORKS)


def _validate_public_url(url: str) -> list[str]:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only http and https URLs are allowed",
        )

    if not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL",
        )

    hostname = parsed.hostname.lower().strip(".")

    if not _is_allowed_domain(hostname):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Domain is not allowed",
        )

    if hostname in PRIVATE_HOSTNAMES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SSRF blocked",
        )

    resolved_ips = _resolve_host(hostname)

    if not resolved_ips:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hostname has no valid IP address",
        )

    if any(_is_blocked_ip(ip) for ip in resolved_ips):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SSRF blocked",
        )

    return [str(ip) for ip in resolved_ips]


@router.post("/fetch-url")
def fetch_url(
    payload: URLRequest,
    _: User = Depends(require_staff_or_admin),
):
    """
    SSRF protection demo.
    Security controls:
    - Staff/Admin only.
    - Only http/https URLs are allowed.
    - Domain must be in allowlist.
    - DNS is resolved before accepting the URL.
    - Private, loopback, link-local, and metadata IP ranges are blocked.
    """
    url = str(payload.url)
    resolved_ips = _validate_public_url(url)

    return {
        "message": "URL accepted",
        "url": url,
        "resolved_ips": resolved_ips,
    }