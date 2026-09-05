"""Background scheduler service for processing and dispatching event reminders."""

import logging
from telegram.ext import CallbackContext

from bot.database.crud import get_pending_reminders, mark_reminder_sent
from bot.database.session import get_db
from bot.utils.datetime_utils import format_datetime

logger = logging.getLogger(__name__)


def format_reminder_message(event_title: str, cal_name: str, start_time_str: str, notes: str, offset_mins: int) -> str:
    """Construct a clean, rich reminder notification message."""
    if offset_mins == 0:
        header = "🚨 *EVENT STARTING NOW!*"
        timing = "Starting now!"
    elif offset_mins < 60:
        header = f"⏰ *REMINDER: Event in {offset_mins} minutes*"
        timing = f"In {offset_mins} minutes"
    elif offset_mins < 1440:
        hours = offset_mins // 60
        header = f"⏰ *REMINDER: Event in {hours} hour(s)*"
        timing = f"In {hours} hour(s)"
    else:
        days = offset_mins // 1440
        header = f"📅 *REMINDER: Event in {days} day(s)*"
        timing = f"In {days} day(s)"

    msg = (
        f"{header}\n\n"
        f"📌 *Event:* {event_title}\n"
        f"📁 *Calendar:* {cal_name}\n"
        f"🕒 *Scheduled Time:* {start_time_str} ({timing})\n"
    )

    if notes and notes.strip():
        msg += f"\n📝 *Notes:*\n{notes.strip()}\n"

    msg += "\n_Have a productive day!_ ✨"
    return msg


async def check_and_send_reminders(bot) -> int:
    """Core logic to check due reminders and dispatch messages to members.

    Returns the number of reminders processed.
    """
    processed_count = 0
    async with get_db() as db:
        pending_reminders = await get_pending_reminders(db)

        for reminder in pending_reminders:
            event = reminder.event
            if not event:
                await mark_reminder_sent(db, reminder.id)
                continue

            calendar = event.calendar
            if not calendar:
                await mark_reminder_sent(db, reminder.id)
                continue

            time_str = format_datetime(event.start_time)

            # Send to all members who have notifications enabled
            for member in calendar.members:
                if not member.receive_notifications or not member.user:
                    continue

                user = member.user
                text = format_reminder_message(
                    event_title=event.title,
                    cal_name=calendar.name,
                    start_time_str=time_str,
                    notes=event.notes or "",
                    offset_mins=reminder.remind_before_minutes,
                )

                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=text,
                        parse_mode="Markdown",
                    )
                    logger.info(
                        f"Sent reminder for event '{event.title}' to user {user.telegram_id} ({user.full_name})"
                    )
                except Exception as ex:
                    logger.warning(
                        f"Failed to send reminder to user {user.telegram_id}: {ex}"
                    )

            # Mark reminder as processed in database
            await mark_reminder_sent(db, reminder.id)
            processed_count += 1

            # If the event is recurring and all its reminders are sent (or event time reached),
            # advance to next cycle (e.g. next year, next month, next week, next day)
            if event.recurrence and event.recurrence != "none":
                # Check if all reminders for this event are sent
                all_sent = all(r.is_sent for r in event.reminders if r.id != reminder.id)
                if all_sent or reminder.remind_before_minutes == 0:
                    from bot.database.crud import advance_recurring_event
                    await advance_recurring_event(db, event.id)
                    logger.info(
                        f"Advanced recurring event '{event.title}' ({event.recurrence}) to next cycle: {event.start_time}"
                    )

    return processed_count


async def reminder_job_callback(context: CallbackContext) -> None:
    """Telegram JobQueue recurring callback wrapper."""
    try:
        count = await check_and_send_reminders(context.bot)
        if count > 0:
            logger.info(f"Processed {count} reminder(s).")
    except Exception as ex:
        logger.error(f"Error executing reminder job: {ex}", exc_info=True)
