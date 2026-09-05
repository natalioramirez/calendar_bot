"""Unit tests for datetime utilities."""

from datetime import datetime
from bot.utils.datetime_utils import format_datetime, parse_datetime_input


def test_parse_datetime_input():
    """Verify natural date & time parsing."""
    parsed = parse_datetime_input("2026-08-25 10:00")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 8
    assert parsed.day == 25
    assert parsed.hour == 10
    assert parsed.minute == 0

    # Invalid string should safely return None
    assert parse_datetime_input("not-a-date-12345") is None


def test_format_datetime():
    """Verify string formatting."""
    dt = datetime(2026, 8, 25, 14, 30, 0)
    formatted = format_datetime(dt, format_str="%Y-%m-%d %H:%M")
    assert formatted == "2026-08-25 14:30"

