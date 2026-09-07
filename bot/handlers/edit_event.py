"""Step-by-step event editing: pick an event, then edit its date, title, comment, or recurrence."""

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

from bot.database.crud import get_event_by_id, get_or_create_user, get_user_upcoming_events, update_event
from bot.database.session import get_db
from bot.keyboards.common import RECURRENCE_LABELS, get_edit_field_keyboard, get_recurrence_keyboard
from bot.utils.datetime_utils import format_datetime, parse_datetime_input

logger = logging.getLogger(__name__)

CHOOSE_EVENT, CHOOSE_FIELD, ENTER_DATETIME, ENTER_TITLE, ENTER_NOTES = range(5)

MAX_TITLE_LENGTH = 200
MAX_NOTES_LENGTH = 500

# How many of the user's upcoming events to offer for editing.
EDITABLE_EVENTS_LIMIT = 25


def _event_summary(ev) -> str:
    lines = [
        f"📅 *{escape_markdown(ev.title, version=1)}*",
        f"🕒 {escape_markdown(format_datetime(ev.start_time), version=1)}",
        f"🔁 {RECURRENCE_LABELS.get(ev.recurrence, 'No se repite')}",
    ]
    if ev.notes:
        lines.append(f"💬 {escape_markdown(ev.notes, version=1)}")
    return "\n".join(lines)


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: list the user's upcoming events so they can pick one to edit."""
    user = update.effective_user
    if not user:
        return ConversationHandler.END

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        events = list(await get_user_upcoming_events(db, db_user.id, limit=EDITABLE_EVENTS_LIMIT))

    if not events:
        await update.message.reply_text(
            "📭 No tenés eventos próximos para editar.\n\nUsá /nuevo para crear uno."
        )
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{ev.title} — {format_datetime(ev.start_time)}", callback_data=f"editev:{ev.id}")]
        for ev in events
    ])

    await update.message.reply_text(
        "✏️ *Editar evento*\n\n¿Cuál querés editar?",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return CHOOSE_EVENT


async def event_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the chosen event and show the field-choice menu."""
    query = update.callback_query
    await query.answer()

    event_id = int(query.data.split(":")[1])
    context.user_data["edit_event_id"] = event_id

    return await _show_field_menu(update, context, event_id, edit_message=True)


async def field_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask for the new value of the chosen field, or finish editing."""
    query = update.callback_query
    await query.answer()

    field = query.data.split(":")[1]

    if field == "done":
        await query.message.edit_text("✅ Listo, terminé de editar ese evento.")
        context.user_data.pop("edit_event_id", None)
        return ConversationHandler.END

    if field == "datetime":
        await query.message.edit_text(
            "📅 ¿Nueva fecha y hora?\n\n"
            "Escribila así: `2026-10-15 14:30`\n"
            "También vale `15/10/2026 14:30`.\n\n"
            "Podés cortar en cualquier momento con /cancel.",
            parse_mode="Markdown",
        )
        return ENTER_DATETIME

    if field == "title":
        await query.message.edit_text("📝 ¿Nuevo título?")
        return ENTER_TITLE

    if field == "notes":
        await query.message.edit_text(
            "💬 Escribí el nuevo comentario.\n\nMandá `-` para borrar el comentario actual.",
            parse_mode="Markdown",
        )
        return ENTER_NOTES

    if field == "recurrence":
        await query.message.edit_text(
            "🔁 ¿Cada cuánto se repite?",
            reply_markup=get_recurrence_keyboard(prefix="editrec"),
        )
        return CHOOSE_FIELD

    return CHOOSE_FIELD


async def recurrence_edited(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Apply the new recurrence and go back to the field menu."""
    query = update.callback_query
    await query.answer()

    recurrence = query.data.split(":")[1]
    event_id = context.user_data.get("edit_event_id")

    async with get_db() as db:
        await update_event(db, event_id, recurrence=recurrence)

    return await _show_field_menu(update, context, event_id, edit_message=True)


async def datetime_edited(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and apply the new date/time, then go back to the field menu."""
    start_time = parse_datetime_input(update.message.text)

    if start_time is None:
        await update.message.reply_text(
            "⚠️ No entendí esa fecha.\n\n"
            "Probá con `2026-10-15 14:30` o `15/10/2026 14:30`.",
            parse_mode="Markdown",
        )
        return ENTER_DATETIME

    if start_time <= datetime.now():
        await update.message.reply_text(
            "⚠️ Esa fecha ya pasó. Escribí una futura para que las alertas tengan sentido."
        )
        return ENTER_DATETIME

    event_id = context.user_data.get("edit_event_id")
    async with get_db() as db:
        await update_event(db, event_id, start_time=start_time)

    return await _show_field_menu(update, context, event_id, edit_message=False)


async def title_edited(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and apply the new title, then go back to the field menu."""
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("⚠️ El título no puede estar vacío. Escribí uno.")
        return ENTER_TITLE
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH]

    event_id = context.user_data.get("edit_event_id")
    async with get_db() as db:
        await update_event(db, event_id, title=title)

    return await _show_field_menu(update, context, event_id, edit_message=False)


async def notes_edited(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and apply the new comment (or clear it), then go back to the field menu."""
    notes = update.message.text.strip()
    if notes == "-":
        notes = ""
    elif len(notes) > MAX_NOTES_LENGTH:
        notes = notes[:MAX_NOTES_LENGTH]

    event_id = context.user_data.get("edit_event_id")
    async with get_db() as db:
        await update_event(db, event_id, notes=notes)

    return await _show_field_menu(update, context, event_id, edit_message=False)


async def _show_field_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, event_id: int, edit_message: bool) -> int:
    """Render the event's current state and the field-choice keyboard."""
    async with get_db() as db:
        event = await get_event_by_id(db, event_id)

    if not event:
        await update.effective_chat.send_message("⚠️ Ese evento ya no existe.")
        context.user_data.pop("edit_event_id", None)
        return ConversationHandler.END

    text = f"{_event_summary(event)}\n\n¿Qué querés editar?"
    keyboard = get_edit_field_keyboard()

    if edit_message and update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.effective_chat.send_message(text, reply_markup=keyboard, parse_mode="Markdown")

    return CHOOSE_FIELD


async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Abort the editing flow."""
    context.user_data.pop("edit_event_id", None)
    await update.message.reply_text("❌ Cancelado.")
    return ConversationHandler.END


def get_edit_event_handler() -> ConversationHandler:
    """Build the /edit conversation."""
    return ConversationHandler(
        entry_points=[CommandHandler("edit", edit_command)],
        states={
            CHOOSE_EVENT: [CallbackQueryHandler(event_chosen, pattern=r"^editev:\d+$")],
            CHOOSE_FIELD: [
                CallbackQueryHandler(field_chosen, pattern=r"^editfield:(datetime|title|notes|recurrence|done)$"),
                CallbackQueryHandler(recurrence_edited, pattern=r"^editrec:(none|daily|weekly|monthly|yearly)$"),
            ],
            ENTER_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, datetime_edited)],
            ENTER_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, title_edited)],
            ENTER_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, notes_edited)],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
    )
