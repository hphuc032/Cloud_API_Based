"""Staff/admin URL and DNS validation only; never performs a remote fetch."""
import ipaddress
import re
import socket
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, field_validator
from app.middleware.logging import mark
from app.auth.dependencies import require_staff_or_admin
from app.models.user import User

router = APIRouter(prefix='/security', tags=['Security'])
ALLOWED_DOMAINS = {'example.com','api.partner.com','cdn.company.com'}
TRANSITION_NETWORKS = (ipaddress.ip_network('64:ff9b::/96'),ipaddress.ip_network('64:ff9b:1::/48'))


def _checked_url(url):
    if not isinstance(url,str) or any(ord(c)<=32 or ord(c)==127 for c in url) or '\\' in url:
        raise HTTPException(400,'Invalid URL')
    try:
        parsed = urlsplit(url)
        port = parsed.port  # force strict invalid/overflow port validation
    except ValueError:
        raise HTTPException(400,'Invalid URL') from None
    if parsed.scheme not in {'http','https'}:
        raise HTTPException(400,'Only http and https URLs are allowed')
    if parsed.username is not None or parsed.password is not None:
        raise HTTPException(403,'Embedded credentials are forbidden')
    if not parsed.hostname or '%' in parsed.hostname:
        raise HTTPException(400,'Invalid hostname')
    return parsed


class URLRequest(BaseModel):
    url: HttpUrl
    @field_validator('url',mode='before')
    @classmethod
    def validate_original_representation(cls,value):
        # Validate BEFORE HttpUrl canonicalizes alternate numeric IP forms.
        if isinstance(value,str):
            try:_checked_url(value)
            except HTTPException as exc:raise ValueError(exc.detail) from None
        return value


def _is_allowed_domain(hostname):
    name=hostname.lower().removesuffix('.')
    return any(name==d or name.endswith('.'+d) for d in ALLOWED_DOMAINS)


def _normalize_ip(value):
    ip=ipaddress.ip_address(value)
    if isinstance(ip,ipaddress.IPv6Address):
        if ip.scope_id is not None:raise ValueError('Scoped address not permitted')
        if ip.ipv4_mapped is not None:ip=ip.ipv4_mapped
    return ip


def _is_blocked_ip(ip):
    ip=_normalize_ip(ip)
    if isinstance(ip,ipaddress.IPv6Address) and (ip.sixtofour is not None or ip.teredo is not None or
            any(ip in network for network in TRANSITION_NETWORKS)):
        return True
    return (not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified or
            ip.is_loopback or ip.is_link_local or ip.is_private)


def _resolve_host(hostname):
    try:answers=socket.getaddrinfo(hostname,None)
    except socket.gaierror:raise HTTPException(400,'Unable to resolve hostname') from None
    addresses=set()
    for item in answers:
        try:addresses.add(_normalize_ip(item[4][0]))
        except (ValueError,IndexError,TypeError):
            # Invalid answers cannot be discarded to approve the remaining subset.
            raise HTTPException(400,'Invalid DNS address') from None
    return sorted(addresses,key=lambda ip:(ip.version,int(ip)))


def _validate_public_url(url):
    parsed=_checked_url(url)
    hostname=parsed.hostname.lower().removesuffix('.')
    # Literal IPs and alternate numeric notations never qualify as approved DNS names.
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?',hostname) or any(
            not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in hostname.split('.')):
        raise HTTPException(403,'Domain is not allowed')
    if not _is_allowed_domain(hostname):raise HTTPException(403,'Domain is not allowed')
    ips=_resolve_host(hostname)
    if not ips:raise HTTPException(400,'Hostname has no valid IP address')
    if any(_is_blocked_ip(ip) for ip in ips):raise HTTPException(403,'SSRF blocked')
    return [str(ip) for ip in ips]


@router.post('/fetch-url')
def fetch_url(payload: URLRequest, _: User = Depends(require_staff_or_admin)):
    url=str(payload.url)
    try:
        ips = _validate_public_url(url)
    except HTTPException as exc:
        if exc.status_code == 403:
            mark('ssrf_denied')
        raise
    return {'message':'URL accepted','url':url,'resolved_ips':ips}
