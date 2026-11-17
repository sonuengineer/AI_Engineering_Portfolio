"""SSRF-safe URL fetching for web-source ingestion.

Controls: http/https only, host allowlist, DNS resolution with private/loopback/link-local/
reserved address blocking, manual redirect handling (each hop re-validated), size cap, timeout,
and content-type allowlist.

Known limitation: the DNS check and the connection resolve separately (TOCTOU / DNS rebinding).
Production mitigation: route egress through an allowlisting proxy.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urljoin, urlparse

import httpx

from app.core.errors import AppError


class UnsafeUrl(AppError):
    status_code = 400
    code = "unsafe_url"


Resolver = Callable[[str], list[str]]


def _default_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return list({str(i[4][0]) for i in infos})


def validate_url(url: str, allowlist: set[str], resolver: Resolver = _default_resolver) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrl("Only http and https URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeUrl("Credentials in URLs are not allowed")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeUrl("URL has no host")
    if not any(host == a or host.endswith("." + a) for a in allowlist):
        raise UnsafeUrl(f"Host '{host}' is not in the ingestion allowlist")
    try:
        ipaddress.ip_address(host)
        raise UnsafeUrl("Literal IP addresses are not allowed")
    except ValueError:
        pass
    try:
        addrs = resolver(host)
    except OSError as exc:
        raise UnsafeUrl(f"Could not resolve host '{host}'") from exc
    if not addrs:
        raise UnsafeUrl("Host resolved to no addresses")
    for a in addrs:
        ip = ipaddress.ip_address(a)
        if not ip.is_global or ip.is_multicast:
            raise UnsafeUrl(f"Host resolves to a non-public address ({a})")
    return url


ALLOWED_CONTENT = ("text/html", "text/plain", "text/markdown", "application/pdf")


def fetch_url(
    url: str,
    allowlist: set[str],
    *,
    max_bytes: int,
    timeout_s: float = 10.0,
    resolver: Resolver = _default_resolver,
    transport: httpx.BaseTransport | None = None,
) -> tuple[bytes, str, str]:
    """Returns (body, content_type, final_url)."""
    current = url
    with httpx.Client(follow_redirects=False, timeout=timeout_s, transport=transport) as client:
        for _hop in range(4):
            validate_url(current, allowlist, resolver)
            with client.stream("GET", current, headers={"User-Agent": "nexus-ingest/0.1"}) as resp:
                if resp.is_redirect:
                    loc = resp.headers.get("location")
                    if not loc:
                        raise UnsafeUrl("Redirect without location")
                    current = urljoin(current, loc)
                    continue
                if resp.status_code != 200:
                    raise UnsafeUrl(f"Fetch failed with HTTP {resp.status_code}")
                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype not in ALLOWED_CONTENT:
                    raise UnsafeUrl(f"Content type '{ctype}' is not allowed")
                body = bytearray()
                for part in resp.iter_bytes():
                    body.extend(part)
                    if len(body) > max_bytes:
                        raise UnsafeUrl("Remote document exceeds the size limit")
                return bytes(body), ctype, current
    raise UnsafeUrl("Too many redirects")
