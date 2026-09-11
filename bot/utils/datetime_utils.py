"""Simple datetime parsing and formatting utilities (no timezone conversions)."""

from datetime import datetime, time
from typing import Optional
from dateutil import parser as date_parser

# All events are all-day; their notification fires this hour on the event's date.
EVENT_NOTIFICATION_HOUR = 8


def format_datetime(dt: datetime, format_str: str = "%A, %b %d, %Y at %H:%M") -> str:
    """Format a datetime into a human-readable string."""
    return dt.strftime(format_str)


def format_date(dt: datetime, format_str: str = "%A, %b %d, %Y") -> str:
    """Format a date (no time-of-day) into a human-readable string."""
    return dt.strftime(format_str)


def parse_datetime_input(text: str) -> Optional[datetime]:
    """Parse user text input (e.g. '2026-08-25 15:30' or '25/08/2026 15:30') into a datetime object."""
    text = text.strip()
    try:
        return date_parser.parse(text, dayfirst=True)
    except Exception:
        return None


def parse_date_input(text: str) -> Optional[datetime]:
    """Parse a date-only user input (e.g. '2026-08-25' or '25/08/2026').

    Any time-of-day the user might have typed is ignored — the result always lands
    on EVENT_NOTIFICATION_HOUR, since every event is all-day.
    """
    text = text.strip()
    try:
        parsed = date_parser.parse(text, dayfirst=True)
    except Exception:
        return None
    return datetime.combine(parsed.date(), time(hour=EVENT_NOTIFICATION_HOUR))

