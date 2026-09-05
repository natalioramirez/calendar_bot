"""Start and Help command handlers."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.database.crud import add_calendar_member, get_calendar_by_invite_code, get_or_create_user
from bot.database.session import get_db
from bot.keyboards.common import get_main_reply_keyboard

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command, register user, and handle invite codes."""
    user = update.effective_user
    if not user:
        return

    # Check if /start was invoked with an invite argument (e.g. /start join_ABC12345)
    invite_code = None
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("join_"):
            invite_code = arg.replace("join_", "").strip().upper()

    welcome_extra = ""
    async with get_db() as db:
        db_user = await get_or_create_user(
            db=db,
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name or user.first_name,
        )

        if invite_code:
            target_cal = await get_calendar_by_invite_code(db, invite_code)
            if target_cal:
                await add_calendar_member(db, target_cal.id, db_user.id, role="member")
                welcome_extra = f"\n\n🎉 *You successfully joined the calendar:* **{target_cal.name}**!"
            else:
                welcome_extra = "\n\n⚠️ *Invalid invite code provided.*"

    welcome_text = (
        f"👋 {user.first_name}, si te llego este mensaje 🗓\n\n"
        "y no sos nico\n\n"
        "Feliciades!\n"
        "Decile al que hizo la presentacion ;)\n"
        
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_reply_keyboard(),
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command with instructions."""
    help_text = (
        "📖 *Team Calendar Bot Guide & Commands*\n\n"
        "📌 *Quick Actions:*\n"
        "• ➕ *New Event* — Schedule an event or important date with notes and alert times\n"
        "• 📅 *Upcoming Dates* — View upcoming events across all your calendars\n"
        "• 🗂 *My Calendars* — Manage team calendars, invite colleagues, or join with a code\n\n"
        "💡 *Useful Commands:*\n"
        "/start — Restart bot or view main dashboard\n"
        "/events — List your upcoming events\n"
        "/new — Create a new event\n"
        "/calendars — Manage your calendars & invite team members\n"
        "/help — Show this help message\n\n"
        "🤝 *Inviting Teammates:*\n"
        "Go to *🗂 My Calendars* ➡️ Select your calendar ➡️ Click *🔗 Share Invite Code*. Teammates can click your link or enter the code to join instantly!"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(help_text, parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback to render main menu overview."""
    query = update.callback_query
    await query.answer()

    menu_text = (
        "🏠 *Main Dashboard*\n\n"
        "Choose an option below or use the bottom keyboard to manage your team dates and reminders:"
    )

    await query.message.reply_text(
        menu_text,
        reply_markup=get_main_reply_keyboard(),
        parse_mode="Markdown",
    )
