"""Inline keyboards for Calendars, Events, Date/Time pickers."""

from datetime import datetime, timedelta
from typing import List, Sequence
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database.models import Calendar, Event
from bot.utils.datetime_utils import format_datetime


# ==========================================
# CALENDARS KEYBOARDS
# ==========================================

def get_calendars_list_keyboard(
    calendars: Sequence[Calendar],
    action_prefix: str = "view_cal",
    show_join_btn: bool = True,
) -> InlineKeyboardMarkup:
    """Build list of user's calendars as interactive buttons."""
    buttons = []
    for cal in calendars:
        buttons.append([
            InlineKeyboardButton(
                f"📁 {cal.name}",
                callback_data=f"{action_prefix}:{cal.id}",
            )
        ])

    bottom_row = []
    if show_join_btn:
        bottom_row.append(InlineKeyboardButton("🔗 Unirse mediante Código", callback_data="cal_join"))

    if bottom_row:
        buttons.append(bottom_row)

    buttons.append([InlineKeyboardButton("🏠 Menú Principal", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def get_calendar_details_keyboard(
    calendar: Calendar,
    is_owner: bool,
    notifications_enabled: bool,
) -> InlineKeyboardMarkup:
    """Build action buttons for a specific calendar simplified for standard users."""
    notif_text = "🔔 Notificaciones: ACTIVAS" if notifications_enabled else "🔕 Notificaciones: DESACTIVADAS"
    buttons = [
        [
            InlineKeyboardButton("➕ Agregar Evento", callback_data=f"ev_add_to:{calendar.id}"),
            InlineKeyboardButton("📋 Ver Eventos", callback_data=f"cal_events:{calendar.id}"),
        ],
        [
            InlineKeyboardButton(notif_text, callback_data=f"cal_toggle_notif:{calendar.id}"),
            InlineKeyboardButton("🔗 Código de Invitación", callback_data=f"cal_share_code:{calendar.id}"),
        ],
        [
            InlineKeyboardButton("🚪 Salir de este Calendario", callback_data=f"cal_leave:{calendar.id}"),
        ],
        [
            InlineKeyboardButton("🔙 Volver a Calendarios", callback_data="list_calendars"),
            InlineKeyboardButton("🏠 Menú", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


# ==========================================
# EVENT MANAGEMENT KEYBOARDS
# ==========================================

def get_upcoming_events_keyboard(
    events: Sequence[Event],
) -> InlineKeyboardMarkup:
    """List of upcoming events with quick details."""
    buttons = []
    for ev in events:
        time_str = format_datetime(ev.start_time, format_str="%b %d, %H:%M")
        rec_badge = ""
        if ev.recurrence == "yearly":
            rec_badge = " 🔁(Anual)"
        elif ev.recurrence == "monthly":
            rec_badge = " 🔁(Mensual)"
        elif ev.recurrence == "weekly":
            rec_badge = " 🔁(Semanal)"
        elif ev.recurrence == "daily":
            rec_badge = " 🔁(Diario)"

        btn_text = f"📅 {ev.title}{rec_badge} ({time_str})"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"ev_view:{ev.id}")])

    buttons.append([
        InlineKeyboardButton("➕ Add New Event", callback_data="start_add_event"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
    ])
    return InlineKeyboardMarkup(buttons)


def get_event_detail_keyboard(
    event_id: int,
    can_edit: bool = True,
    has_notes: bool = False,
) -> InlineKeyboardMarkup:
    """Action buttons for a single event."""
    buttons = []
    if can_edit:
        notes_label = "✏️ Edit Notes" if has_notes else "➕ Add Notes"
        buttons.append([
            InlineKeyboardButton(notes_label, callback_data=f"ev_edit_notes:{event_id}"),
            InlineKeyboardButton("🗑 Delete Event", callback_data=f"ev_delete_confirm:{event_id}"),
        ])

    buttons.append([
        InlineKeyboardButton("📅 Upcoming Events", callback_data="list_upcoming_events"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
    ])
    return InlineKeyboardMarkup(buttons)


# ==========================================
# DATE & TIME PICKER SHORTCUTS
# ==========================================

def get_quick_date_shortcuts_keyboard() -> InlineKeyboardMarkup:
    """Quick date selection shortcuts for fast event creation."""
    now = datetime.now()

    today_str = now.strftime("%Y-%m-%d")
    tomorrow = now + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    in_2_days = now + timedelta(days=2)
    in_2_days_str = in_2_days.strftime("%Y-%m-%d")
    in_1_week = now + timedelta(days=7)
    in_1_week_str = in_1_week.strftime("%Y-%m-%d")

    buttons = [
        [
            InlineKeyboardButton(f"📍 Today ({now.strftime('%b %d')})", callback_data=f"dt_pick:{today_str}"),
            InlineKeyboardButton(f"⏭ Tomorrow ({tomorrow.strftime('%b %d')})", callback_data=f"dt_pick:{tomorrow_str}"),
        ],
        [
            InlineKeyboardButton(f"🗓 In 2 Days ({in_2_days.strftime('%b %d')})", callback_data=f"dt_pick:{in_2_days_str}"),
            InlineKeyboardButton(f"🗓 In 1 Week ({in_1_week.strftime('%b %d')})", callback_data=f"dt_pick:{in_1_week_str}"),
        ],
        [
            InlineKeyboardButton("✍️ Or Type Custom Date/Time", callback_data="dt_type_custom"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_wizard"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_quick_time_shortcuts_keyboard(selected_date: str) -> InlineKeyboardMarkup:
    """Quick time selection shortcuts."""
    times = ["09:00", "10:00", "11:00", "14:00", "15:00", "17:00", "18:00", "20:00"]
    rows = []
    curr_row = []
    for t in times:
        curr_row.append(InlineKeyboardButton(t, callback_data=f"time_pick:{selected_date} {t}"))
        if len(curr_row) == 4:
            rows.append(curr_row)
            curr_row = []
    if curr_row:
        rows.append(curr_row)

    rows.append([InlineKeyboardButton("✍️ Type Custom Time (e.g. 16:45)", callback_data="time_type_custom")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_wizard")])
    return InlineKeyboardMarkup(rows)


def get_reminder_options_keyboard(selected_offsets: List[int]) -> InlineKeyboardMarkup:
    """Multi-toggle reminder options keyboard."""
    options = [
        (0, "🔔 At event time"),
        (15, "⏰ 15 min before"),
        (60, "⏰ 1 hour before"),
        (1440, "📅 1 day before"),
    ]

    buttons = []
    for offset, label in options:
        is_selected = offset in selected_offsets
        icon = "✅ " if is_selected else "⬜️ "
        buttons.append([
            InlineKeyboardButton(
                f"{icon}{label}",
                callback_data=f"rem_toggle:{offset}",
            )
        ])

    buttons.append([
        InlineKeyboardButton("💾 Save & Create Event", callback_data="rem_done"),
    ])
    buttons.append([
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_wizard"),
    ])
    return InlineKeyboardMarkup(buttons)


def get_recurrence_selection_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting event recurrence."""
    buttons = [
        [
            InlineKeyboardButton("🚫 No se repite (Una sola vez)", callback_data="rec_pick:none"),
        ],
        [
            InlineKeyboardButton("🎂 Todos los años (Anual)", callback_data="rec_pick:yearly"),
        ],
        [
            InlineKeyboardButton("📆 Todos los meses (Mensual)", callback_data="rec_pick:monthly"),
        ],
        [
            InlineKeyboardButton("🗓 Todas las semanas (Semanal)", callback_data="rec_pick:weekly"),
            InlineKeyboardButton("⏰ Todos los días (Diario)", callback_data="rec_pick:daily"),
        ],
        [
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_wizard"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)
