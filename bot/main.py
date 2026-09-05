"""Main entry point for the Telegram Team Calendar Bot."""

import logging
import sys
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
)

# Additional imports
from datetime import datetime

from bot.config import settings
from bot.database.session import init_db
from bot.handlers.calendars import (
    get_calendar_conversation_handlers,
    leave_calendar_callback,
    list_calendars_command,
    share_code_callback,
    toggle_notifications_callback,
    view_calendar_callback,
)
from bot.handlers.events import (
    delete_event_callback,
    get_event_conversation_handlers,
    list_upcoming_events_command,
    view_calendar_events_callback,
    view_event_detail_callback,
)
from bot.handlers.start import (
    help_command,
    main_menu_callback,
    start_command,
)
from bot.services.scheduler import reminder_job_callback
from bot.services.islamic_calendar import sync_islamic_calendar

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def sync_islamic_job(context: CallbackContext) -> None:
    """Background job callback for automatic Islamic calendar sync (next 12 months)."""
    now = datetime.now()
    try:
        count = await sync_islamic_calendar("P", now.year, now.month, months_ahead=12)
        logger.info("Islamic calendar sync completed for 12 months ahead (%d new events added)", count)
    except Exception as e:
        logger.error("Error during scheduled Islamic calendar sync: %s", e)


async def sync_islamic_monthly_cron(context: CallbackContext) -> None:
    """Daily check to sync Islamic calendar on the 1st of each month."""
    now = datetime.now()
    if now.day == 1:
        await sync_islamic_job(context)


async def sync_islamic_command(update: Update, context: CallbackContext) -> None:
    """Command to manually trigger Islamic calendar sync for calendar 'P'."""
    admin_ids = getattr(settings, "ADMIN_USER_IDS", [])
    if admin_ids and update.effective_user.id not in admin_ids:
        await update.message.reply_text("❌ No tienes autorización para ejecutar este comando.")
        return

    now = datetime.now()
    msg = await update.message.reply_text("⏳ Sincronizando eventos islámicos para los próximos 12 meses...")
    try:
        count = await sync_islamic_calendar("P", now.year, now.month, months_ahead=12)
        await msg.edit_text(f"✅ Calendario islámico sincronizado en 'P'.\nSe importaron {count} nuevos eventos para los próximos 12 meses.")
    except Exception as e:
        logger.exception("Error syncing Islamic calendar: %s", e)
        await msg.edit_text(f"❌ Error al sincronizar con AlAdhan API: {e}")


async def post_init(application: Application) -> None:
    """Post initialization hook: setup DB and schedule background jobs."""
    logger.info("Initializing database tables...")
    await init_db()
    logger.info("Database initialized successfully.")

    # Start background jobs
    if application.job_queue:
        logger.info(
            f"Scheduling reminder check job every {settings.REMINDER_CHECK_INTERVAL_SECONDS} seconds..."
        )
        application.job_queue.run_repeating(
            reminder_job_callback,
            interval=settings.REMINDER_CHECK_INTERVAL_SECONDS,
            first=5,
            name="reminder_dispatch_job",
        )

        # Initial sync for Islamic calendar 5 seconds after startup
        application.job_queue.run_once(
            sync_islamic_job,
            when=5,
            name="islamic_initial_sync",
        )

        # Schedule daily check at 02:00 UTC (syncs on 1st of month)
        from datetime import time as dt_time
        application.job_queue.run_daily(
            sync_islamic_monthly_cron,
            time=dt_time(hour=2, minute=0, second=0),
            name="islamic_sync_daily",
        )
    else:
        logger.warning("JobQueue is not available! Scheduled reminders will not run.")


def create_application() -> Application:
    """Build and configure the Telegram Bot Application."""
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error(
            "ERROR: BOT_TOKEN is not configured! Please set BOT_TOKEN in your .env file or environment."
        )

    # Initialize Application
    app = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # 1. Register Conversation Handlers (High Priority)
    (join_cal_handler,) = get_calendar_conversation_handlers()
    create_ev_handler, edit_notes_handler = get_event_conversation_handlers()

    app.add_handler(create_ev_handler)
    app.add_handler(edit_notes_handler)
    app.add_handler(join_cal_handler)

    # 2. Register Slash Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("events", list_upcoming_events_command))
    app.add_handler(CommandHandler("calendars", list_calendars_command))
    app.add_handler(CommandHandler("sync_islamic", sync_islamic_command))

    # 3. Register Reply Keyboard Text Handlers (Button clicks)
    app.add_handler(MessageHandler(filters.Regex("^📅 Upcoming Dates$"), list_upcoming_events_command))
    app.add_handler(MessageHandler(filters.Regex("^🗂 My Calendars$"), list_calendars_command))
    app.add_handler(MessageHandler(filters.Regex("^❓ Help & Info$"), help_command))

    # 4. Register Callback Query Handlers (Inline Buttons)
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(list_calendars_command, pattern="^list_calendars$"))
    app.add_handler(CallbackQueryHandler(list_upcoming_events_command, pattern="^list_upcoming_events$"))

    app.add_handler(CallbackQueryHandler(view_calendar_callback, pattern="^view_cal:\\d+$"))
    app.add_handler(CallbackQueryHandler(view_calendar_events_callback, pattern="^cal_events:\\d+$"))
    app.add_handler(CallbackQueryHandler(toggle_notifications_callback, pattern="^cal_toggle_notif:\\d+$"))
    app.add_handler(CallbackQueryHandler(share_code_callback, pattern="^cal_share_code:\\d+$"))
    app.add_handler(CallbackQueryHandler(view_members_callback, pattern="^cal_members:\\d+$"))
    app.add_handler(CallbackQueryHandler(delete_calendar_callback, pattern="^cal_delete_confirm:\\d+$"))

    app.add_handler(CallbackQueryHandler(view_event_detail_callback, pattern="^ev_view:\\d+$"))
    app.add_handler(CallbackQueryHandler(delete_event_callback, pattern="^ev_delete_confirm:\\d+$"))

    return app


def main() -> None:
    """Run the bot application."""
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("\n" + "=" * 60)
        print("⚠️  MISSING BOT_TOKEN!")
        print("Please copy .env.example to .env and fill in your BOT_TOKEN.")
        print("Get a bot token from @BotFather on Telegram.")
        print("=" * 60 + "\n")
        sys.exit(1)

    app = create_application()
    logger.info("Starting Telegram Bot Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
