import httpx
import pytest

from app.ingestion.ssrf import UnsafeUrl, fetch_url, validate_url

ALLOW = {"example.com"}


def public(_host):
    return ["93.184.215.14"]


@pytest.mark.parametrize(
    "url,msg",
    [
        ("ftp://example.com/x", "Only http"),
        ("file:///etc/passwd", "Only http"),
        ("http://user:pw@example.com/", "Credentials"),
        ("http://evil.test/", "allowlist"),
        ("http://example.com.evil.test/", "allowlist"),
    ],
)
def test_rejects_bad_urls(url, msg):
    with pytest.raises(UnsafeUrl, match=msg):
        validate_url(url, ALLOW, public)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1", "fd00::1"])
def test_rejects_private_resolution(ip):
    with pytest.raises(UnsafeUrl, match="non-public"):
        validate_url("http://example.com/", ALLOW, lambda _h: [ip])


def test_rejects_literal_ip_even_if_allowlisted():
    with pytest.raises(UnsafeUrl):
        validate_url("http://127.0.0.1/", {"127.0.0.1"}, public)


def test_allows_subdomain_of_allowlisted_public_host():
    assert validate_url("https://docs.example.com/a", ALLOW, public)


def test_redirect_to_disallowed_host_is_blocked():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://internal.corp/secret"})

    with pytest.raises(UnsafeUrl, match="allowlist"):
        fetch_url("http://example.com/", ALLOW, max_bytes=1000, resolver=public, transport=httpx.MockTransport(handler))


def test_fetch_enforces_content_type_and_size():
    t = httpx.MockTransport(lambda r: httpx.Response(200, headers={"content-type": "application/zip"}, content=b"x"))
    with pytest.raises(UnsafeUrl, match="Content type"):
        fetch_url("http://example.com/", ALLOW, max_bytes=1000, resolver=public, transport=t)
    big = httpx.MockTransport(
        lambda r: httpx.Response(200, headers={"content-type": "text/plain"}, content=b"x" * 5000)
    )
    with pytest.raises(UnsafeUrl, match="size"):
        fetch_url("http://example.com/", ALLOW, max_bytes=1000, resolver=public, transport=big)


def test_fetch_success_follows_safe_redirect():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/start":
            return httpx.Response(301, headers={"location": "/final"})
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=b"<p>hello</p>")

    body, ctype, final = fetch_url(
        "http://example.com/start", ALLOW, max_bytes=1000, resolver=public, transport=httpx.MockTransport(handler)
    )
    assert body == b"<p>hello</p>" and ctype == "text/html" and final.endswith("/final")
