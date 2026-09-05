"""Listing of upcoming dates for the calendars a user is subscribed to."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from bot.database.crud import get_or_create_user, get_user_upcoming_events
from bot.database.session import get_db
from bot.utils.datetime_utils import format_datetime

logger = logging.getLogger(__name__)

# How many upcoming dates a single /events message shows.
UPCOMING_LIMIT = 15


async def list_upcoming_events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user's upcoming dates as a single plain list."""
    user = update.effective_user
    if not user:
        return

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        events = await get_user_upcoming_events(db, db_user.id, limit=UPCOMING_LIMIT)

    if not events:
        await update.message.reply_text(
            "📅 No tenés fechas próximas.\n\nUsá /sub para suscribirte a un calendario."
        )
        return

    lines = ["📅 *Tus próximas fechas*", ""]
    for ev in events:
        title = escape_markdown(ev.title, version=1)
        when = escape_markdown(format_datetime(ev.start_time), version=1)
        cal_name = escape_markdown(ev.calendar.name, version=1)
        lines.append(f"• *{title}*")
        lines.append(f"  🕒 {when} — _{cal_name}_")
        if ev.notes:
            # Notes can be long or multi-line; a single trimmed line keeps the list readable.
            first_line = ev.notes.strip().splitlines()[0]
            if len(first_line) > 80:
                first_line = first_line[:77] + "..."
            lines.append(f"  📝 {escape_markdown(first_line, version=1)}")
        lines.append("")

    await update.message.reply_text("\n".join(lines).strip(), parse_mode="Markdown")
