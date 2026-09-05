"""The only keyboard the bot needs: picking a calendar to subscribe to or leave."""

from typing import Sequence
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database.models import Calendar


def get_calendar_choice_keyboard(calendars: Sequence[Calendar], action: str) -> InlineKeyboardMarkup:
    """One button per calendar. `action` is the callback prefix: 'sub' or 'unsub'."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📁 {cal.name}", callback_data=f"{action}:{cal.id}")]
        for cal in calendars
    ])
