"""Heuristic prompt-injection scanner for untrusted document text.

Flagged chunks are still searchable (they may be legitimate evidence) but are marked, shown with a
warning in the UI, and always passed to models inside an untrusted-data envelope.
"""

import re

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("override_instructions", re.compile(r"\b(ignore|disregard|forget)\b.{0,40}\b(instructions|rules|prompt)", re.I)),
    ("role_hijack", re.compile(r"\byou are now\b|\bact as (an?|the) (admin|system|developer)", re.I)),
    ("system_prompt_probe", re.compile(r"\b(system prompt|developer message|hidden instructions)\b", re.I)),
    ("fake_delimiters", re.compile(r"</?(system|assistant|untrusted_document)>|BEGIN (SYSTEM|INSTRUCTIONS)", re.I)),
    (
        "exfiltration",
        re.compile(
            r"\b(send|email|forward|post|upload)\b.{0,60}\b(password|credential|api key|secret|all (customer|data))",
            re.I,
        ),
    ),
    ("tool_coercion", re.compile(r"\b(call|invoke|execute|run)\b.{0,30}\b(tool|function|send_email|approve)", re.I)),
]


def scan(text: str) -> list[str]:
    return [name for name, pat in PATTERNS if pat.search(text)]


def wrap_untrusted(source_label: str, text: str) -> str:
    """Envelope used whenever document text is placed in a prompt."""
    safe = text.replace("</untrusted_document>", "</ untrusted_document>")
    return f'<untrusted_document source="{source_label}">\n{safe}\n</untrusted_document>'
