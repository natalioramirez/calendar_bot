"""Keyboards package."""
from bot.keyboards.calendar_picker import (
    get_calendar_details_keyboard,
    get_calendars_list_keyboard,
    get_event_detail_keyboard,
    get_quick_date_shortcuts_keyboard,
    get_quick_time_shortcuts_keyboard,
    get_recurrence_selection_keyboard,
    get_reminder_options_keyboard,
    get_upcoming_events_keyboard,
)
from bot.keyboards.common import (
    get_back_to_menu_keyboard,
    get_cancel_keyboard,
    get_main_reply_keyboard,
    get_skip_or_cancel_keyboard,
)

__all__ = [
    "get_main_reply_keyboard",
    "get_cancel_keyboard",
    "get_skip_or_cancel_keyboard",
    "get_back_to_menu_keyboard",
    "get_calendars_list_keyboard",
    "get_calendar_details_keyboard",
    "get_upcoming_events_keyboard",
    "get_event_detail_keyboard",
    "get_quick_date_shortcuts_keyboard",
    "get_quick_time_shortcuts_keyboard",
    "get_reminder_options_keyboard",
    "get_recurrence_selection_keyboard",
]
