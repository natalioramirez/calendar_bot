"""Simple datetime parsing and formatting utilities (no timezone conversions)."""

from datetime import datetime
from typing import Optional
from dateutil import parser as date_parser


def format_datetime(dt: datetime, format_str: str = "%A, %b %d, %Y at %H:%M") -> str:
    """Format a datetime into a human-readable string."""
    return dt.strftime(format_str)


def parse_datetime_input(text: str) -> Optional[datetime]:
    """Parse user text input (e.g. '2026-08-25 15:30' or '25/08/2026 15:30') into a datetime object."""
    text = text.strip()
    try:
        return date_parser.parse(text, dayfirst=True)
    except Exception:
        return None

