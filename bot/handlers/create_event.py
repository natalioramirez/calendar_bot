"""Step-by-step event creation: pick calendar -> date & time -> title."""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.helpers import escape_markdown

from bot.database.crud import (
    create_event,
    get_calendar_by_id,
    get_or_create_user,
    get_user_calendars,
)
from bot.database.session import get_db
from bot.keyboards.common import get_calendar_choice_keyboard
from bot.utils.datetime_utils import format_datetime, parse_datetime_input

logger = logging.getLogger(__name__)

CHOOSE_CALENDAR, ENTER_DATETIME, ENTER_TITLE = range(3)

# Every event created from the bot alerts at start time and one hour before.
DEFAULT_REMINDER_OFFSETS = [0, 60]

MAX_TITLE_LENGTH = 200


async def new_event_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: ask which of the user's calendars the event goes into."""
    user = update.effective_user
    if not user:
        return ConversationHandler.END

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        calendars = list(await get_user_calendars(db, db_user.id))

    if not calendars:
        await update.message.reply_text(
            "📭 No seguís ningún calendario todavía.\n\nUsá /sub para suscribirte a uno primero."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🗓 *Nuevo evento*\n\n¿En qué calendario lo creo?",
        reply_markup=get_calendar_choice_keyboard(calendars, action="newev"),
        parse_mode="Markdown",
    )
    return CHOOSE_CALENDAR


async def calendar_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the chosen calendar and ask for the date and time."""
    query = update.callback_query
    await query.answer()

    context.user_data["new_event_calendar_id"] = int(query.data.split(":")[1])

    await query.message.edit_text(
        "📅 ¿Qué fecha y hora?\n\n"
        "Escribila así: `2026-10-15 14:30`\n"
        "También vale `15/10/2026 14:30`.\n\n"
        "Podés cortar en cualquier momento con /cancel.",
        parse_mode="Markdown",
    )
    return ENTER_DATETIME


async def datetime_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate the date and time, then ask for the title."""
    start_time = parse_datetime_input(update.message.text)

    if start_time is None:
        await update.message.reply_text(
            "⚠️ No entendí esa fecha.\n\n"
            "Probá con `2026-10-15 14:30` o `15/10/2026 14:30`.",
            parse_mode="Markdown",
        )
        return ENTER_DATETIME

    # A past event would fire its reminders immediately, so reject it here.
    if start_time <= datetime.now():
        await update.message.reply_text(
            "⚠️ Esa fecha ya pasó. Escribí una futura para que las alertas tengan sentido."
        )
        return ENTER_DATETIME

    context.user_data["new_event_start_time"] = start_time

    await update.message.reply_text(
        f"🕒 {format_datetime(start_time)}\n\n¿Cómo se llama el evento?"
    )
    return ENTER_TITLE


async def title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Create the event and close the conversation."""
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("⚠️ El título no puede estar vacío. Escribí uno.")
        return ENTER_TITLE
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH]

    calendar_id = context.user_data.pop("new_event_calendar_id", None)
    start_time = context.user_data.pop("new_event_start_time", None)
    if calendar_id is None or start_time is None:
        await update.message.reply_text("⚠️ Se perdió el hilo del evento. Empezá de nuevo con /nuevo.")
        return ConversationHandler.END

    user = update.effective_user
    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        cal = await get_calendar_by_id(db, calendar_id)
        if not cal:
            await update.message.reply_text("⚠️ Ese calendario ya no existe.")
            return ConversationHandler.END

        cal_name = cal.name
        await create_event(
            db=db,
            calendar_id=calendar_id,
            created_by_id=db_user.id,
            title=title,
            start_time=start_time,
            reminder_offsets_minutes=DEFAULT_REMINDER_OFFSETS,
        )

    await update.message.reply_text(
        f"✅ Evento creado en *{escape_markdown(cal_name, version=1)}*\n\n"
        f"📅 {escape_markdown(title, version=1)}\n"
        f"🕒 {escape_markdown(format_datetime(start_time), version=1)}\n\n"
        "Se avisa al momento del evento y 1 hora antes, a todos los suscriptos del calendario.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Abort the creation flow."""
    context.user_data.pop("new_event_calendar_id", None)
    context.user_data.pop("new_event_start_time", None)
    await update.message.reply_text("❌ Cancelado, no creé nada.")
    return ConversationHandler.END


def get_create_event_handler() -> ConversationHandler:
    """Build the /nuevo conversation."""
    return ConversationHandler(
        entry_points=[CommandHandler("nuevo", new_event_command)],
        states={
            CHOOSE_CALENDAR: [CallbackQueryHandler(calendar_chosen, pattern=r"^newev:\d+$")],
            ENTER_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, datetime_received)],
            ENTER_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, title_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_creation)],
    )
