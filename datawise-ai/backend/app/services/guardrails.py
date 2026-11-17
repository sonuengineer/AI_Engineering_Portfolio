"""Input guardrails: reject unsafe intents BEFORE any planner (local or LLM) sees the question.

These are deliberately conservative pattern checks. They are a first layer only -- the real safety
guarantees come from the typed plan, our own SQL compiler, the validator and the read-only role.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailRule:
    category: str
    pattern: re.Pattern[str]
    reason: str


def _rx(p: str) -> re.Pattern[str]:
    return re.compile(p, re.IGNORECASE)


_ANALYTICS_TABLES = r"(orders|order_items|customers|products|suppliers|web_sessions|supplier_deliveries)"

RULES: list[GuardrailRule] = [
    GuardrailRule(
        "prompt_injection",
        _rx(r"\b(ignore|disregard|forget|override)\b.{0,30}\b(instructions?|rules?|prompts?|guardrails?|"
            r"polic(y|ies)|constraints?)\b|\bsystem prompt\b|\byou are now\b|\bjailbreak\b|"
            r"\bdeveloper mode\b|\bdan mode\b|\bact as\b|\bpretend (to be|you)\b|\breveal\b.{0,20}\b(prompt|"
            r"instructions?)\b|\bnew instructions?\b|\bbypass\b"),
        "The question contains instructions aimed at the assistant (possible prompt injection). "
        "Ask a business question instead.",
    ),
    GuardrailRule(
        "raw_sql",
        _rx(r";|--|/\*|\*/|\bunion\s+(all\s+)?select\b|\bselect\s+\*|\bselect\b.{0,80}\bfrom\s+"
            + _ANALYTICS_TABLES + r"\b|\b(pg_sleep|dblink|pg_read_file|lo_import|lo_export|copy\s+\w+\s+(to|from))\b"
            r"|'\s*or\s*'?\d|\b1\s*=\s*1\b|\bexec(ute)?\s*\("),
        "Raw SQL, SQL fragments or comment markers are not accepted. Ask in plain language; "
        "DATAWISE generates and validates the SQL itself.",
    ),
    GuardrailRule(
        "write_intent",
        _rx(r"\b(delete|drop|truncate|insert|update|alter|grant|revoke|erase|wipe|destroy|overwrite|"
            r"rename|modify|remove|purge)\b|\bcreate\s+(table|index|user|role|database|view|function)\b|"
            r"\bset\s+\w+\s*="),
        "DATAWISE is read-only: it cannot create, change or delete data, users or permissions.",
    ),
    GuardrailRule(
        "sensitive_data",
        _rx(r"\b(passwords?|passwd|password[_ ]?hash(es)?|credentials?|secrets?|api[_ ]?keys?|access[_ ]?"
            r"tokens?|jwt|tokens?|ssn|social security|credit card|card numbers?|pg_\w+|information_schema|"
            r"system (tables?|catalog)|datawise_app|app database|audit (log|events)|login (details|"
            r"history)|connection string)\b|\b(list|show|dump|export|get|give|read|select|all|every)\b"
            r".{0,25}\b(users?|user accounts?|accounts? (emails?|passwords?)|admins?)\b|"
            r"\b(customer|customers'|user|users') (emails?|e-mail addresses|phone numbers?|home addresses)\b|"
            r"\busers? (table|accounts?|emails?|list)\b"),
        "That request targets credentials, user accounts or system catalogs, which are outside the "
        "allowlisted analytics data.",
    ),
]


def check_question(question: str) -> tuple[str, str] | None:
    """Return (category, reason) if the question must be rejected, else None."""
    for rule in RULES:
        if rule.pattern.search(question):
            return rule.category, rule.reason
    return None
