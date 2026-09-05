"""Main entry point for the Telegram Team Calendar Bot."""

import logging
import sys
from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    CallbackContext,
)

# Additional imports
from datetime import datetime

from bot.config import settings
from bot.database.session import init_db
from bot.handlers.create_event import get_create_event_handler
from bot.handlers.events import list_upcoming_events_command
from bot.handlers.start import start_command
from bot.handlers.subscriptions import (
    sub_command,
    subscribe_callback,
    unsub_command,
    unsubscribe_callback,
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


async def post_init(application: Application) -> None:
    """Post initialization hook: setup DB and schedule background jobs."""
    # Show the (short) command list in Telegram's menu.
    await application.bot.set_my_commands([
        BotCommand("sub", "Suscribirte a un calendario"),
        BotCommand("unsub", "Dejar de seguir un calendario"),
        BotCommand("events", "Ver tus próximas fechas"),
        BotCommand("nuevo", "Crear un evento en un calendario"),
    ])

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
        if settings.CALLS_ON_BOOT:
            application.job_queue.run_once(
                sync_islamic_job,
                when=5,
                name="islamic_initial_sync",
            )
        else:
            logger.info(
                "CALLS_ON_BOOT is disabled: skipping the initial Islamic calendar sync. "
                "The monthly job and the web panel button still work."
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

    # The conversation goes first so its steps capture the user's replies.
    app.add_handler(get_create_event_handler())

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("sub", sub_command))
    app.add_handler(CommandHandler("unsub", unsub_command))
    app.add_handler(CommandHandler("events", list_upcoming_events_command))

    app.add_handler(CallbackQueryHandler(subscribe_callback, pattern=r"^sub:\d+$"))
    app.add_handler(CallbackQueryHandler(unsubscribe_callback, pattern=r"^unsub:\d+$"))

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
