"""Subscribe / unsubscribe handlers — the only calendar actions users have."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from bot.database.crud import (
    add_calendar_member,
    get_all_calendars,
    get_calendar_by_id,
    get_or_create_user,
    get_user_calendars,
    leave_calendar,
)
from bot.database.session import get_db
from bot.keyboards.common import get_calendar_choice_keyboard

logger = logging.getLogger(__name__)


async def sub_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List the calendars the user has not subscribed to yet."""
    user = update.effective_user
    if not user:
        return

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        subscribed_ids = {cal.id for cal in await get_user_calendars(db, db_user.id)}
        available = [cal for cal in await get_all_calendars(db) if cal.id not in subscribed_ids]

    if not available:
        if subscribed_ids:
            await update.message.reply_text("✅ Ya estás suscripto a todos los calendarios disponibles.")
        else:
            await update.message.reply_text("📭 Todavía no hay calendarios disponibles para suscribirse.")
        return

    await update.message.reply_text(
        "📋 *Calendarios disponibles*\n\nElegí a cuál querés suscribirte:",
        reply_markup=get_calendar_choice_keyboard(available, action="sub"),
        parse_mode="Markdown",
    )


async def subscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Subscribe the user to the calendar they picked."""
    query = update.callback_query
    await query.answer()

    calendar_id = int(query.data.split(":")[1])
    user = update.effective_user

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        cal = await get_calendar_by_id(db, calendar_id)
        if not cal:
            await query.message.edit_text("⚠️ Ese calendario ya no existe.")
            return

        cal_name = cal.name
        await add_calendar_member(db, calendar_id, db_user.id)

    await query.message.edit_text(
        f"✅ Te suscribiste a *{escape_markdown(cal_name, version=1)}*.\n\n"
        "Vas a recibir las alertas de sus fechas. Mirá /events para ver las próximas.",
        parse_mode="Markdown",
    )


async def unsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List the calendars the user is subscribed to, to leave one."""
    user = update.effective_user
    if not user:
        return

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        subscribed = list(await get_user_calendars(db, db_user.id))

    if not subscribed:
        await update.message.reply_text("📭 No estás suscripto a ningún calendario. Usá /sub para sumarte a uno.")
        return

    await update.message.reply_text(
        "🔕 *Tus calendarios*\n\nElegí de cuál querés dejar de recibir alertas:",
        reply_markup=get_calendar_choice_keyboard(subscribed, action="unsub"),
        parse_mode="Markdown",
    )


async def unsubscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unsubscribe the user from the calendar they picked."""
    query = update.callback_query
    await query.answer()

    calendar_id = int(query.data.split(":")[1])
    user = update.effective_user

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        cal = await get_calendar_by_id(db, calendar_id)
        if not cal:
            await query.message.edit_text("⚠️ Ese calendario ya no existe.")
            return

        cal_name = cal.name
        await leave_calendar(db, calendar_id, db_user.id)

    await query.message.edit_text(
        f"🔕 Dejaste de seguir *{escape_markdown(cal_name, version=1)}*.\n\n"
        "Ya no vas a recibir sus alertas. Podés volver con /sub.",
        parse_mode="Markdown",
    )
