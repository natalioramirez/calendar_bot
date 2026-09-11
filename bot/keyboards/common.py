"""Keyboards shared across the event-creation, event-editing, and /events flows."""

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

# Extra reminder ahead of the day-of notification, expressed in days-before.
REMINDER_LABELS = {
    "none": "Sin recordatorio extra",
    "1": "1 día antes",
    "2": "2 días antes",
    "3": "3 días antes",
    "7": "1 semana antes",
}

EVENTS_RANGE_LABELS = {
    "week": "la próxima semana",
    "month": "el próximo mes",
    "3months": "los próximos 3 meses",
    "all": "todas tus fechas",
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


def get_reminder_keyboard(prefix: str = "remind") -> InlineKeyboardMarkup:
    """Ask whether to add an extra reminder ahead of the day-of notification."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔕 Sin recordatorio extra", callback_data=f"{prefix}:none")],
        [
            InlineKeyboardButton("1 día antes", callback_data=f"{prefix}:1"),
            InlineKeyboardButton("2 días antes", callback_data=f"{prefix}:2"),
        ],
        [
            InlineKeyboardButton("3 días antes", callback_data=f"{prefix}:3"),
            InlineKeyboardButton("1 semana antes", callback_data=f"{prefix}:7"),
        ],
    ])


def get_edit_field_keyboard() -> InlineKeyboardMarkup:
    """Choose which field of an event to edit."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Fecha", callback_data="editfield:datetime")],
        [InlineKeyboardButton("📝 Título", callback_data="editfield:title")],
        [InlineKeyboardButton("💬 Comentario", callback_data="editfield:notes")],
        [InlineKeyboardButton("🔁 Recursión", callback_data="editfield:recurrence")],
        [InlineKeyboardButton("✅ Listo", callback_data="editfield:done")],
    ])


def get_events_range_keyboard(prefix: str = "eventsrange") -> InlineKeyboardMarkup:
    """Choose which date range to list events for."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓 Próxima semana", callback_data=f"{prefix}:week")],
        [InlineKeyboardButton("📆 Próximo mes", callback_data=f"{prefix}:month")],
        [InlineKeyboardButton("🗓 Próximos 3 meses", callback_data=f"{prefix}:3months")],
        [InlineKeyboardButton("📋 Todos los eventos", callback_data=f"{prefix}:all")],
    ])
