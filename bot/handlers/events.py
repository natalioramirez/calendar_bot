"""Listing of upcoming dates for the calendars a user is subscribed to, filtered by date range."""

import logging
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from bot.database.crud import get_or_create_user, get_user_upcoming_events
from bot.database.session import get_db
from bot.keyboards.common import EVENTS_RANGE_LABELS, get_events_range_keyboard
from bot.utils.datetime_utils import format_date

logger = logging.getLogger(__name__)

# How many dates a single /events message shows, regardless of range.
EVENTS_LIMIT = 100


def _range_to_dates(range_key: str) -> tuple[datetime, datetime | None]:
    """Turn a range key into a (from_date, to_date) window. to_date is None for 'all'."""
    now = datetime.now()
    if range_key == "week":
        return now, now + timedelta(weeks=1)
    if range_key == "month":
        return now, now + relativedelta(months=1)
    if range_key == "3months":
        return now, now + relativedelta(months=3)
    return now, None


async def list_upcoming_events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point: ask which date range to show."""
    user = update.effective_user
    if not user:
        return

    await update.message.reply_text(
        "📅 *Tus fechas*\n\n¿Qué rango querés ver?",
        reply_markup=get_events_range_keyboard(),
        parse_mode="Markdown",
    )


async def events_range_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and show the user's dates within the chosen range."""
    query = update.callback_query
    await query.answer()

    range_key = query.data.split(":")[1]
    user = update.effective_user

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        from_date, to_date = _range_to_dates(range_key)
        events = await get_user_upcoming_events(db, db_user.id, limit=EVENTS_LIMIT, from_date=from_date, to_date=to_date)

    range_label = EVENTS_RANGE_LABELS.get(range_key, "ese rango")

    if not events:
        await query.message.edit_text(f"📅 No tenés fechas para {range_label}.")
        return

    lines = [f"📅 *Tus fechas — {range_label}*", ""]
    for ev in events:
        title = escape_markdown(ev.title, version=1)
        when = escape_markdown(format_date(ev.start_time), version=1)
        cal_name = escape_markdown(ev.calendar.name, version=1)
        lines.append(f"• *{title}*")
        lines.append(f"  🗓 {when} — _{cal_name}_")
        if ev.notes:
            # Notes can be long or multi-line; a single trimmed line keeps the list readable.
            first_line = ev.notes.strip().splitlines()[0]
            if len(first_line) > 80:
                first_line = first_line[:77] + "..."
            lines.append(f"  📝 {escape_markdown(first_line, version=1)}")
        lines.append("")

    await query.message.edit_text("\n".join(lines).strip(), parse_mode="Markdown")
