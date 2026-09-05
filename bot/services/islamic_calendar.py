"""Service to fetch and sync Islamic calendar events from AlAdhan API.

The API endpoint used:
https://api.aladhan.com/v1/calendar?latitude={lat}&longitude={lon}&method=2&month={month}&year={year}

We use the coordinates of Buenos Aires (lat=-34.6037, lon=-58.3816).
Each day's "events" list is turned into Event records in the DB.
"""

import logging
import re
import unicodedata
from datetime import datetime
from typing import List, Dict

import httpx

from bot.config import settings
from bot.database import crud
from bot.database.session import get_db

logger = logging.getLogger(__name__)

# Buenos Aires coordinates
BA_LAT = -34.6037
BA_LON = -58.3816

API_URL = "https://api.aladhan.com/v1/calendar"


class CalendarNotFoundError(LookupError):
    """Raised when the calendar targeted by the sync does not exist yet."""


def clean_tokens(text: str) -> List[str]:
    """Normalize text into word tokens, removing accents, punctuation and quotes."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    for ch in ["-", "_", "/", "(", ")", ".", ",", ":", ";"]:
        ascii_text = ascii_text.replace(ch, " ")
    for ch in ["'", "’", "‘", "`", "ʿ", "ʾ"]:
        ascii_text = ascii_text.replace(ch, "")
    return re.findall(r"[a-z0-9]+", ascii_text.lower())


def is_allowed_islamic_event(event_title: str) -> bool:
    """Check if an event title matches any allowed keyword in settings."""
    allowed = getattr(settings, "ISLAMIC_ALLOWED_EVENTS", [])
    if not allowed:
        return True
    title_tokens = clean_tokens(event_title)
    for kw in allowed:
        kw_tokens = clean_tokens(kw)
        if not kw_tokens:
            continue
        kw_len = len(kw_tokens)
        for i in range(len(title_tokens) - kw_len + 1):
            if title_tokens[i : i + kw_len] == kw_tokens:
                return True
    return False


async def fetch_month_data(year: int, month: int) -> List[Dict]:
    """Fetch raw calendar month data from AlAdhan API."""
    params = {
        "latitude": BA_LAT,
        "longitude": BA_LON,
        "method": 2,
        "month": month,
        "year": year,
    }
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TelegramCalendarBot/1.0)"}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(API_URL, params=params, headers=headers, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"AlAdhan API error: {data.get('status')}")
    return data.get("data", [])


async def sync_islamic_calendar(calendar_name: str, start_year: int, start_month: int, months_ahead: int = 12) -> int:
    """Sync Islamic events into the calendar identified by *calendar_name* for the next `months_ahead` months.

    Calculates both API holidays and key Hijri calendar events:
      - Día de Al-Quds (último viernes de Ramadán)
      - Eid al-Ghadir (18 de Dhul-Hiyya)
      - Arbaeen (20 de Safar)
      - Mubahala (24 de Dhul-Hiyya)
      - Año Nuevo Hijri (1 de Muharram)
    """
    # Verify the target calendar exists before spending ~24 API requests on data
    # we would have to throw away. The session is closed again right away so it is
    # not held open across the network calls below.
    async with get_db() as db:
        if not await crud.get_calendar_by_name(db, calendar_name):
            raise CalendarNotFoundError(
                f"Calendar '{calendar_name}' does not exist. Create a calendar named "
                f"'{calendar_name}' in the web admin panel before syncing."
            )

    total_created = 0
    all_events: List[Dict] = []
    ramadan_fridays: Dict[str, List[Dict]] = {}

    for i in range(months_ahead):
        m = (start_month - 1 + i) % 12 + 1
        y = start_year + (start_month - 1 + i) // 12
        try:
            days = await fetch_month_data(y, m)
        except Exception as e:
            logger.error(f"Failed to fetch Islamic events for {y}-{m:02d}: {e}")
            continue

        for day_entry in days:
            g_data = day_entry.get("date", {}).get("gregorian", {})
            h_data = day_entry.get("date", {}).get("hijri", {})

            g_day = int(g_data.get("day", 1))
            g_month = int(g_data.get("month", {}).get("number", m))
            g_year = int(g_data.get("year", y))
            g_weekday = g_data.get("weekday", {}).get("en", "")

            h_day = int(h_data.get("day", 1))
            h_month = int(h_data.get("month", {}).get("number", 0))
            h_year = str(h_data.get("year", ""))
            hijri_date = h_data.get("date", "")

            # 1. Standard API holidays
            holidays = h_data.get("holidays", []) or []
            adjusted_holidays = h_data.get("adjustedHolidays", []) or []
            for ev in list(dict.fromkeys(holidays + adjusted_holidays)):
                all_events.append({
                    "year": g_year,
                    "month": g_month,
                    "day": g_day,
                    "title": str(ev).strip(),
                    "hijri": hijri_date,
                })

            # 2. Specific Hijri date-based events
            if h_month == 2 and h_day == 20:
                all_events.append({
                    "year": g_year,
                    "month": g_month,
                    "day": g_day,
                    "title": "Arbaeen (Arbaʿīn)",
                    "hijri": hijri_date,
                })
            elif h_month == 12 and h_day == 18:
                all_events.append({
                    "year": g_year,
                    "month": g_month,
                    "day": g_day,
                    "title": "Eid al-Ghadir (ʿĪd al-Ghadīr)",
                    "hijri": hijri_date,
                })
            elif h_month == 12 and h_day == 24:
                all_events.append({
                    "year": g_year,
                    "month": g_month,
                    "day": g_day,
                    "title": "Mubahala (ʿĪd al-Mubāhala)",
                    "hijri": hijri_date,
                })
            elif h_month == 1 and h_day == 1:
                all_events.append({
                    "year": g_year,
                    "month": g_month,
                    "day": g_day,
                    "title": "Año Nuevo Hijri (Ra's al-Sanah)",
                    "hijri": hijri_date,
                })

            # Track Ramadan Fridays to find the last Friday of Ramadan
            if h_month == 9 and g_weekday == "Friday":
                ramadan_fridays.setdefault(h_year, []).append({
                    "year": g_year,
                    "month": g_month,
                    "day": g_day,
                    "title": "Día de Al-Quds (Yawm al-Quds)",
                    "hijri": hijri_date,
                })

    # Add the last Friday of each Ramadan as Día de Al-Quds
    for h_year, fridays in ramadan_fridays.items():
        if fridays:
            all_events.append(fridays[-1])

    async with get_db() as db:
        cal = await crud.get_calendar_by_name(db, calendar_name)
        if not cal:
            raise CalendarNotFoundError(
                f"Calendar '{calendar_name}' was removed while the sync was running."
            )

        for ev in all_events:
            title_str = ev["title"]
            if not is_allowed_islamic_event(title_str):
                continue

            start_dt = datetime(ev["year"], ev["month"], ev["day"], 0, 0)
            existing = await crud.get_event_by_calendar_and_title_and_time(
                db,
                calendar_id=cal.id,
                title=title_str,
                start_time=start_dt,
            )
            if existing:
                continue

            await crud.create_event(
                db=db,
                calendar_id=cal.id,
                created_by_id=cal.owner_id,
                title=title_str,
                start_time=start_dt,
                notes=f"Fecha Hijri: {ev['hijri']}",
                recurrence="none",
                reminder_offsets_minutes=[],  # No automatic reminders requested
            )
            total_created += 1

        logger.info(f"Synced {total_created} Islamic events into calendar '{calendar_name}' across {months_ahead} months.")
    return total_created

