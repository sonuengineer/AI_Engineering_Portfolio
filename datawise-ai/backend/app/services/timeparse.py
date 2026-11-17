"""Deterministic parsing of time phrases into a [start, end) date range.

Relative phrases are anchored to `as_of` (ANALYTICS_AS_OF_DATE, default 2026-10-31 = end of the
synthetic data), treated as "today". Conventions:
- "last month"/"last quarter"/"last year": the previous full calendar period
- "this month"/"this quarter"/"this year"/"ytd": period start .. as_of (inclusive)
- "last N months": N calendar months ending with the as_of month (inclusive)
- "last N days|weeks": N days (or 7*N) ending on as_of
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.schemas.plan import TimeRange

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH_RX = "|".join(sorted(MONTHS, key=len, reverse=True))
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "a": 1,
}
_NUM_RX = r"\d+|" + "|".join(k for k in NUMBER_WORDS if k != "a")
_ORDINAL_Q = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4}


@dataclass
class TimeParse:
    time_range: TimeRange | None = None
    all_time: bool = False
    years_mentioned: list[int] = field(default_factory=list)
    spans: list[tuple[int, int]] = field(default_factory=list)


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _quarter_start(d: date) -> date:
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def _num(token: str) -> int:
    return int(token) if token.isdigit() else NUMBER_WORDS[token]


def parse_time(text: str, as_of: date) -> TimeParse:
    """`text` must already be lower-cased."""
    out = TimeParse()
    tomorrow = as_of + timedelta(days=1)

    def found(m: re.Match[str], start: date, end: date, label: str) -> TimeParse:
        out.time_range = TimeRange(start=start, end=end, label=label)
        out.spans.append(m.span())
        return out

    # "since march 2026" / "since 2025"
    m = re.search(rf"\bsince\s+(?:({_MONTH_RX})\s+)?(20\d\d)\b", text)
    if m:
        year = int(m.group(2))
        start = date(year, MONTHS[m.group(1)], 1) if m.group(1) else date(year, 1, 1)
        return found(m, start, tomorrow, f"since {start.isoformat()}")

    # quarter: "q3 2025", "q3 of 2025", "third quarter of 2025"
    m = re.search(r"\bq([1-4])\s*(?:of\s+|,\s*)?(20\d\d)\b", text) or re.search(
        r"\b(first|1st|second|2nd|third|3rd|fourth|4th)\s+quarter\s+(?:of\s+)?(20\d\d)\b", text
    )
    if m:
        q = int(m.group(1)) if m.group(1).isdigit() else _ORDINAL_Q[m.group(1)]
        year = int(m.group(2))
        start = date(year, 3 * (q - 1) + 1, 1)
        return found(m, start, _add_months(start, 3), f"Q{q} {year}")

    # month + year: "march 2026", "mar of 2026"
    m = re.search(rf"\b({_MONTH_RX})\s+(?:of\s+)?(20\d\d)\b", text)
    if m:
        start = date(int(m.group(2)), MONTHS[m.group(1)], 1)
        return found(m, start, _add_months(start, 1), start.strftime("%B %Y"))

    # relative: last/past/previous N units
    m = re.search(rf"\b(?:last|past|previous|trailing)\s+({_NUM_RX})\s+(days?|weeks?|months?|quarters?|years?)\b",
                  text)
    if m:
        n = _num(m.group(1))
        unit = m.group(2).rstrip("s")
        if n < 1 or n > 120:
            n = max(1, min(n, 120))
        if unit == "day":
            start = tomorrow - timedelta(days=n)
        elif unit == "week":
            start = tomorrow - timedelta(days=7 * n)
        elif unit == "month":
            start = _add_months(_month_start(as_of), -(n - 1))
        elif unit == "quarter":
            start = _add_months(_quarter_start(as_of), -3 * (n - 1))
        else:
            start = date(as_of.year - (n - 1), 1, 1)
        return found(m, start, tomorrow, f"last {n} {unit}s")

    rel: list[tuple[str, date, date, str]] = [
        (r"\b(?:last|previous|prior)\s+month\b", _add_months(_month_start(as_of), -1), _month_start(as_of),
         "last month"),
        (r"\bthis\s+month\b|\bmonth\s+to\s+date\b|\bmtd\b", _month_start(as_of), tomorrow, "this month"),
        (r"\b(?:last|previous|prior)\s+quarter\b", _add_months(_quarter_start(as_of), -3), _quarter_start(as_of),
         "last quarter"),
        (r"\bthis\s+quarter\b|\bquarter\s+to\s+date\b|\bqtd\b", _quarter_start(as_of), tomorrow, "this quarter"),
        (r"\b(?:last|previous|prior)\s+year\b", date(as_of.year - 1, 1, 1), date(as_of.year, 1, 1), "last year"),
        (r"\bthis\s+year\b|\byear\s+to\s+date\b|\bytd\b", date(as_of.year, 1, 1), tomorrow, "year to date"),
        (r"\b(?:last|past|previous)\s+week\b", tomorrow - timedelta(days=7), tomorrow, "last 7 days"),
        (r"\byesterday\b", as_of - timedelta(days=1), as_of, "yesterday"),
        (r"\btoday\b", as_of, tomorrow, "today"),
    ]
    for pattern, start, end, label in rel:
        m = re.search(pattern, text)
        if m:
            return found(m, start, end, label)

    # explicit years: one year -> that year; several -> span covering all of them
    year_matches = list(re.finditer(r"\b(?:in|during|for|of|from|between|and|vs\.?|versus|to)?\s*(20\d\d)\b", text))
    if year_matches:
        years = sorted({int(x.group(1)) for x in year_matches})
        out.years_mentioned = years
        out.time_range = TimeRange(
            start=date(years[0], 1, 1), end=date(years[-1] + 1, 1, 1),
            label=str(years[0]) if len(years) == 1 else f"{years[0]}-{years[-1]}",
        )
        out.spans.extend(x.span() for x in year_matches)
        return out

    m = re.search(r"\b(all[\s-]time|overall|ever|lifetime|since (the )?(beginning|start|launch)|to date|"
                  r"in total|all (the )?data|whole period|entire period)\b", text)
    if m:
        out.all_time = True
        out.spans.append(m.span())
    return out
