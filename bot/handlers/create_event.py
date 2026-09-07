"""Step-by-step event creation: pick calendar -> date & time -> title -> recurrence -> comment."""

import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from bot.keyboards.common import RECURRENCE_LABELS, get_calendar_choice_keyboard, get_recurrence_keyboard
from bot.utils.datetime_utils import format_datetime, parse_datetime_input

logger = logging.getLogger(__name__)

CHOOSE_CALENDAR, ENTER_DATETIME, ENTER_TITLE, CHOOSE_RECURRENCE, ENTER_NOTES = range(5)

# Every event created from the bot alerts at start time and one hour before.
DEFAULT_REMINDER_OFFSETS = [0, 60]

MAX_TITLE_LENGTH = 200
MAX_NOTES_LENGTH = 500

DATETIME_PROMPT = (
    "📅 ¿Qué fecha y hora?\n\n"
    "Escribila así: `2026-10-15 14:30`\n"
    "También vale `15/10/2026 14:30`.\n\n"
    "Podés cortar en cualquier momento con /cancel."
)

SKIP_NOTES_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("⏭ Sin comentario", callback_data="notes:skip")]
])


async def new_event_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: ask which of the user's calendars the event goes into (skipped if there's only one)."""
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

    if len(calendars) == 1:
        cal = calendars[0]
        context.user_data["new_event_calendar_id"] = cal.id
        await update.message.reply_text(
            f"🗓 *Nuevo evento* en *{escape_markdown(cal.name, version=1)}*\n\n{DATETIME_PROMPT}",
            parse_mode="Markdown",
        )
        return ENTER_DATETIME

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

    await query.message.edit_text(DATETIME_PROMPT, parse_mode="Markdown")
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
    """Store the title and ask how often the event repeats."""
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("⚠️ El título no puede estar vacío. Escribí uno.")
        return ENTER_TITLE
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH]

    context.user_data["new_event_title"] = title

    await update.message.reply_text(
        "🔁 ¿Se repite este evento?",
        reply_markup=get_recurrence_keyboard(),
    )
    return CHOOSE_RECURRENCE


async def recurrence_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the recurrence and ask for an optional comment."""
    query = update.callback_query
    await query.answer()

    recurrence = query.data.split(":")[1]
    context.user_data["new_event_recurrence"] = recurrence

    await query.message.edit_text(
        "💬 ¿Querés agregar un comentario al evento?\n\nEscribilo, o tocá el botón para omitirlo.",
        reply_markup=SKIP_NOTES_KEYBOARD,
    )
    return ENTER_NOTES


async def notes_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User chose not to add a comment."""
    query = update.callback_query
    await query.answer()
    return await _finalize_event(update, context, notes=None)


async def notes_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed a comment for the event."""
    notes = update.message.text.strip()
    if len(notes) > MAX_NOTES_LENGTH:
        notes = notes[:MAX_NOTES_LENGTH]
    return await _finalize_event(update, context, notes=notes or None)


async def _finalize_event(update: Update, context: ContextTypes.DEFAULT_TYPE, notes: str | None) -> int:
    """Create the event with everything collected so far and close the conversation."""
    calendar_id = context.user_data.pop("new_event_calendar_id", None)
    start_time = context.user_data.pop("new_event_start_time", None)
    title = context.user_data.pop("new_event_title", None)
    recurrence = context.user_data.pop("new_event_recurrence", "none")

    chat = update.effective_chat
    if calendar_id is None or start_time is None or title is None:
        await chat.send_message("⚠️ Se perdió el hilo del evento. Empezá de nuevo con /nuevo.")
        return ConversationHandler.END

    user = update.effective_user
    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        cal = await get_calendar_by_id(db, calendar_id)
        if not cal:
            await chat.send_message("⚠️ Ese calendario ya no existe.")
            return ConversationHandler.END

        cal_name = cal.name
        await create_event(
            db=db,
            calendar_id=calendar_id,
            created_by_id=db_user.id,
            title=title,
            start_time=start_time,
            notes=notes,
            recurrence=recurrence,
            reminder_offsets_minutes=DEFAULT_REMINDER_OFFSETS,
        )

    lines = [
        f"✅ Evento creado en *{escape_markdown(cal_name, version=1)}*",
        "",
        f"📅 {escape_markdown(title, version=1)}",
        f"🕒 {escape_markdown(format_datetime(start_time), version=1)}",
        f"🔁 {RECURRENCE_LABELS.get(recurrence, 'No se repite')}",
    ]
    if notes:
        lines.append(f"💬 {escape_markdown(notes, version=1)}")
    lines.append("")
    lines.append("Se avisa al momento del evento y 1 hora antes, a todos los suscriptos del calendario.")

    await chat.send_message("\n".join(lines), parse_mode="Markdown")
    return ConversationHandler.END


async def cancel_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Abort the creation flow."""
    context.user_data.pop("new_event_calendar_id", None)
    context.user_data.pop("new_event_start_time", None)
    context.user_data.pop("new_event_title", None)
    context.user_data.pop("new_event_recurrence", None)
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
            CHOOSE_RECURRENCE: [
                CallbackQueryHandler(recurrence_chosen, pattern=r"^rec:(none|daily|weekly|monthly|yearly)$")
            ],
            ENTER_NOTES: [
                CallbackQueryHandler(notes_skip, pattern=r"^notes:skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, notes_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_creation)],
    )
