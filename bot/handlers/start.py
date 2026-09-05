"""Start command: registers the user and lists the three things the bot does."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from bot.database.crud import get_or_create_user
from bot.database.session import get_db

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register the user and show the short command guide."""
    user = update.effective_user
    if not user:
        return

    async with get_db() as db:
        await get_or_create_user(
            db=db,
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name or user.first_name,
        )

    await update.message.reply_text(
        f"👋 Hola {escape_markdown(user.first_name, version=1)}!\n\n"
        "Te aviso de las fechas importantes de los calendarios que sigas.\n\n"
        "*Comandos:*\n"
        "/sub — suscribirte a un calendario\n"
        "/unsub — dejar de seguir un calendario\n"
        "/events — ver tus próximas fechas\n"
        "/nuevo — crear un evento en un calendario\n\n"
        "Las alertas te llegan solas, no tenés que hacer nada más.",
        parse_mode="Markdown",
    )
