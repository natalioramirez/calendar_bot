"""Keyboards shared across the event-creation and event-editing conversations."""

from typing import Sequence
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database.models import Calendar

RECURRENCE_LABELS = {
    "none": "No se repite",
    "daily": "Diario",
    "weekly": "Semanal",
    "monthly": "Mensual",
    "yearly": "Anual",
}


def get_calendar_choice_keyboard(calendars: Sequence[Calendar], action: str) -> InlineKeyboardMarkup:
    """One button per calendar. `action` is the callback prefix: 'sub' or 'unsub'."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📁 {cal.name}", callback_data=f"{action}:{cal.id}")]
        for cal in calendars
    ])


def get_recurrence_keyboard(prefix: str = "rec") -> InlineKeyboardMarkup:
    """Ask how often (if at all) an event repeats. `prefix` namespaces the callback_data."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 No se repite", callback_data=f"{prefix}:none")],
        [
            InlineKeyboardButton("☀️ Diario", callback_data=f"{prefix}:daily"),
            InlineKeyboardButton("📅 Semanal", callback_data=f"{prefix}:weekly"),
        ],
        [
            InlineKeyboardButton("🗓 Mensual", callback_data=f"{prefix}:monthly"),
            InlineKeyboardButton("🎉 Anual", callback_data=f"{prefix}:yearly"),
        ],
    ])


def get_edit_field_keyboard() -> InlineKeyboardMarkup:
    """Choose which field of an event to edit."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Fecha y hora", callback_data="editfield:datetime")],
        [InlineKeyboardButton("📝 Título", callback_data="editfield:title")],
        [InlineKeyboardButton("💬 Comentario", callback_data="editfield:notes")],
        [InlineKeyboardButton("🔁 Recursión", callback_data="editfield:recurrence")],
        [InlineKeyboardButton("✅ Listo", callback_data="editfield:done")],
    ])
