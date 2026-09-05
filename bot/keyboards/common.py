"""Common Telegram keyboards and buttons."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent reply keyboard with main quick actions."""
    keyboard = [
        ["📅 Upcoming Dates", "➕ New Event"],
        ["🗂 My Calendars", "❓ Help & Info"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_cancel_keyboard(callback_data: str = "cancel") -> InlineKeyboardMarkup:
    """Inline keyboard with a single Cancel button."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=callback_data)]])


def get_skip_or_cancel_keyboard(skip_data: str = "skip", cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    """Inline keyboard with Skip and Cancel buttons (e.g. for optional notes)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ Skip (No Notes)", callback_data=skip_data),
            InlineKeyboardButton("❌ Cancel", callback_data=cancel_data),
        ]
    ])


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard to return to main menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])
