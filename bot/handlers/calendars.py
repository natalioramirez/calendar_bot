"""Calendar management handlers."""

import logging
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database.crud import (
    add_calendar_member,
    get_calendar_by_id,
    get_calendar_by_invite_code,
    get_calendar_members,
    get_member,
    get_or_create_user,
    get_user_by_telegram_id,
    get_user_calendars,
    leave_calendar,
    toggle_member_notifications,
)
from bot.database.session import get_db
from bot.keyboards.calendar_picker import (
    get_calendar_details_keyboard,
    get_calendars_list_keyboard,
)
from bot.keyboards.common import get_cancel_keyboard

logger = logging.getLogger(__name__)

# Conversation states for joining a calendar
CAL_JOIN_CODE = range(1)


# ==========================================
# LIST CALENDARS
# ==========================================

async def list_calendars_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all calendars the user is enrolled in."""
    user = update.effective_user
    if not user:
        return

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        calendars = await get_user_calendars(db, db_user.id)

    text = (
        "🗂 *Mis Calendarios*\n\n"
        "Selecciona un calendario para ver sus fechas o configurar notificaciones:\n"
    )

    keyboard = get_calendars_list_keyboard(calendars)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


# ==========================================
# VIEW CALENDAR DETAILS
# ==========================================

async def view_calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show details and management options for a calendar."""
    query = update.callback_query
    await query.answer()

    cal_id = int(query.data.split(":")[1])
    user = update.effective_user

    async with get_db() as db:
        db_user = await get_user_by_telegram_id(db, user.id)
        if not db_user:
            await query.edit_text("⚠️ Usuario no encontrado. Por favor escribe /start.")
            return

        cal = await get_calendar_by_id(db, cal_id)
        if not cal:
            await query.edit_text("⚠️ Calendario no encontrado.")
            return

        member = await get_member(db, cal.id, db_user.id)
        if not member:
            await query.edit_text("⚠️ No perteneces a este calendario.")
            return

        members = await get_calendar_members(db, cal.id)
        is_owner = cal.owner_id == db_user.id

    desc = f"_{cal.description}_\n\n" if cal.description else ""
    text = (
        f"📁 *Calendario:* **{cal.name}**\n"
        f"{desc}"
        f"🔑 *Código de Invitación:* `{cal.invite_code}`\n"
        f"👥 *Total de Miembros:* {len(members)}\n"
        f"🔔 *Notificaciones:* {'Activadas ✅' if member.receive_notifications else 'Silenciadas 🔕'}\n"
    )

    keyboard = get_calendar_details_keyboard(
        calendar=cal,
        is_owner=is_owner,
        notifications_enabled=member.receive_notifications,
    )

    await query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


# ==========================================
# TOGGLE NOTIFICATIONS
# ==========================================

async def toggle_notifications_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle notification preference for a specific calendar."""
    query = update.callback_query
    await query.answer()

    cal_id = int(query.data.split(":")[1])
    user = update.effective_user

    async with get_db() as db:
        db_user = await get_user_by_telegram_id(db, user.id)
        if not db_user:
            return

        new_state = await toggle_member_notifications(db, cal_id, db_user.id)
        cal = await get_calendar_by_id(db, cal_id)
        if not cal:
            return
        members = await get_calendar_members(db, cal.id)
        is_owner = cal.owner_id == db_user.id

    status_text = "activadas ✅" if new_state else "silenciadas 🔕"
    await query.answer(f"Notificaciones {status_text} para {cal.name}!")

    desc = f"_{cal.description}_\n\n" if cal.description else ""
    text = (
        f"📁 *Calendario:* **{cal.name}**\n"
        f"{desc}"
        f"🔑 *Código de Invitación:* `{cal.invite_code}`\n"
        f"👥 *Total de Miembros:* {len(members)}\n"
        f"🔔 *Notificaciones:* {'Activadas ✅' if new_state else 'Silenciadas 🔕'}\n"
    )

    keyboard = get_calendar_details_keyboard(
        calendar=cal,
        is_owner=is_owner,
        notifications_enabled=new_state,
    )

    await query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


# ==========================================
# SHARE INVITE CODE
# ==========================================

async def share_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send shareable invite link & code."""
    query = update.callback_query
    await query.answer()

    cal_id = int(query.data.split(":")[1])
    async with get_db() as db:
        cal = await get_calendar_by_id(db, cal_id)
        if not cal:
            return

    bot_info = await context.bot.get_me()
    join_link = f"https://t.me/{bot_info.username}?start=join_{cal.invite_code}"

    text = (
        f"🔗 *Invitar compañeros a '{cal.name}':*\n\n"
        f"1️⃣ Enlace de 1-clic:\n{join_link}\n\n"
        f"2️⃣ O compartiendo el código de invitación:\n`{cal.invite_code}`"
    )

    await query.message.reply_text(text, parse_mode="Markdown")


# ==========================================
# LEAVE CALENDAR
# ==========================================

async def leave_calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow a user to leave a calendar."""
    query = update.callback_query
    await query.answer()

    cal_id = int(query.data.split(":")[1])
    user = update.effective_user

    async with get_db() as db:
        db_user = await get_user_by_telegram_id(db, user.id)
        cal = await get_calendar_by_id(db, cal_id)
        if not cal or not db_user:
            await query.edit_text("⚠️ Calendario o usuario no encontrado.")
            return

        cal_name = cal.name
        await leave_calendar(db, cal_id, db_user.id)

    await query.message.edit_text(
        f"🚪 *Has salido del calendario '{cal_name}'.*\n\n"
        "Ya no recibirás alertas ni verás las fechas de este calendario.",
        parse_mode="Markdown",
    )


# ==========================================
# JOIN CALENDAR CONVERSATION
# ==========================================

async def start_join_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to enter invite code."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.reply_text(
            "🔗 *Unirse a un Calendario*\n\nPor favor escribe el *Código de Invitación* de 8 caracteres (ej. `A1B2C3D4`):",
            reply_markup=get_cancel_keyboard("cancel_cal_flow"),
            parse_mode="Markdown",
        )
    return CAL_JOIN_CODE


async def join_code_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate invite code and add member."""
    code = update.message.text.strip().upper()
    user = update.effective_user

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        cal = await get_calendar_by_invite_code(db, code)

        if not cal:
            await update.message.reply_text(
                "❌ *Código de invitación inválido.* Revisa el código e intenta nuevamente, o escribe /cancel:",
                parse_mode="Markdown",
            )
            return CAL_JOIN_CODE

        await add_calendar_member(db, cal.id, db_user.id, role="member")

    await update.message.reply_text(
        f"🎉 *¡Te has unido con éxito al calendario:* **{cal.name}**!\n\n"
        "Ahora recibirás alertas y podrás ver los eventos de este calendario.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel_cal_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel calendar joining flow."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.edit_text("❌ Acción cancelada.")
    elif update.message:
        await update.message.reply_text("❌ Acción cancelada.")
    return ConversationHandler.END


def get_calendar_conversation_handlers():
    """Create conversation handler for joining calendars."""
    join_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_join_calendar, pattern="^cal_join$"),
            CommandHandler("join", start_join_calendar),
        ],
        states={
            CAL_JOIN_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, join_code_received),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_cal_flow, pattern="^cancel_cal_flow$"),
            CommandHandler("cancel", cancel_cal_flow),
        ],
    )

    return (join_handler,)
