"""Redaction of PII and secrets before anything is stored in traces/spans.

Masks: email addresses, phone numbers, API keys / bearer tokens / JWTs, credit-card-like
numbers (Luhn-checked), and values of sensitive keys (password, token, authorization...).
This is a best-effort regex filter, not a DLP system (see docs/security-threat-model.md).
"""

from __future__ import annotations

import re
from typing import Any

EMAIL = "[REDACTED_EMAIL]"
PHONE = "[REDACTED_PHONE]"
SECRET = "[REDACTED_SECRET]"
CARD = "[REDACTED_CARD]"

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_BEARER_RE = re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")
_API_KEY_PATTERNS = [
    re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}\b"),  # OpenAI / Anthropic style
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),  # Google API key
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),  # GitHub tokens
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),  # Slack tokens
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
]
_KV_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|secret|password|passwd|pwd|token)\b(\s*[:=]\s*)(\"?)([^\s\"',;&]+)"
)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_PHONE_RE = re.compile(
    r"(?<![\w])(?<!\d[\s.-])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{3,4}[\s.-]\d{3,4}(?:[\s.-]\d{2,4})?"
    r"(?![\w])(?![\s.-]\d)"
)

SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "apikey",
    "x-api-key",
    "cookie",
    "set-cookie",
    "client_secret",
}


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _card_sub(m: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", m.group(0))
    if 13 <= len(digits) <= 19 and _luhn_ok(digits):
        return CARD
    return m.group(0)


def _phone_sub(m: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", m.group(0))
    # Avoid masking dates, years, money amounts, versions: need 7-15 digits.
    if 7 <= len(digits) <= 15:
        return PHONE
    return m.group(0)


def redact_text(text: str) -> str:
    if not text:
        return text
    out = _BEARER_RE.sub(lambda m: f"{m.group(1)} {SECRET}", text)
    out = _JWT_RE.sub(SECRET, out)
    for pat in _API_KEY_PATTERNS:
        out = pat.sub(SECRET, out)
    out = _KV_SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{SECRET}", out)
    out = _EMAIL_RE.sub(EMAIL, out)
    out = _CARD_RE.sub(_card_sub, out)
    out = _PHONE_RE.sub(_phone_sub, out)
    return out


def redact(value: Any, _depth: int = 0) -> Any:
    """Recursively redact strings inside dicts/lists; mask values of sensitive keys entirely."""
    if _depth > 20:
        return "[TRUNCATED]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
                result[k] = SECRET
            else:
                result[k] = redact(v, _depth + 1)
        return result
    if isinstance(value, list | tuple):
        return [redact(v, _depth + 1) for v in value]
    return value
