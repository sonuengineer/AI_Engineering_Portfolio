from datetime import date

import pytest

from app.services.timeparse import parse_time

AS_OF = date(2026, 10, 31)


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("revenue last month", date(2026, 9, 1), date(2026, 10, 1)),
        ("revenue this month", date(2026, 10, 1), date(2026, 11, 1)),
        ("revenue last quarter", date(2026, 7, 1), date(2026, 10, 1)),
        ("revenue this year", date(2026, 1, 1), date(2026, 11, 1)),
        ("revenue ytd", date(2026, 1, 1), date(2026, 11, 1)),
        ("revenue last year", date(2025, 1, 1), date(2026, 1, 1)),
        ("revenue in 2025", date(2025, 1, 1), date(2026, 1, 1)),
        ("revenue in q3 2025", date(2025, 7, 1), date(2025, 10, 1)),
        ("revenue in the third quarter of 2025", date(2025, 7, 1), date(2025, 10, 1)),
        ("revenue in march 2026", date(2026, 3, 1), date(2026, 4, 1)),
        ("revenue last 3 months", date(2026, 8, 1), date(2026, 11, 1)),
        ("revenue past six months", date(2026, 5, 1), date(2026, 11, 1)),
        ("revenue last 30 days", date(2026, 10, 2), date(2026, 11, 1)),
        ("revenue since march 2026", date(2026, 3, 1), date(2026, 11, 1)),
        ("revenue 2025 vs 2026", date(2025, 1, 1), date(2027, 1, 1)),
    ],
)
def test_ranges(text: str, start: date, end: date) -> None:
    tr = parse_time(text, AS_OF).time_range
    assert tr is not None and (tr.start, tr.end) == (start, end)


def test_all_time_flag() -> None:
    tp = parse_time("total revenue all time", AS_OF)
    assert tp.time_range is None and tp.all_time


def test_no_time() -> None:
    tp = parse_time("revenue by region", AS_OF)
    assert tp.time_range is None and not tp.all_time
