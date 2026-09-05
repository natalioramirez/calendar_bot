"""Event creation, notes editing, listing, and deletion handlers."""

import logging
from datetime import datetime
from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import settings
from bot.database.crud import (
    create_event,
    delete_event,
    get_calendar_by_id,
    get_calendar_events,
    get_event_by_id,
    get_or_create_user,
    get_user_by_telegram_id,
    get_user_calendars,
    get_user_upcoming_events,
    update_event_notes,
)
from bot.database.session import get_db
from bot.keyboards.calendar_picker import (
    get_calendars_list_keyboard,
    get_event_detail_keyboard,
    get_quick_date_shortcuts_keyboard,
    get_quick_time_shortcuts_keyboard,
    get_recurrence_selection_keyboard,
    get_reminder_options_keyboard,
    get_upcoming_events_keyboard,
)
from bot.keyboards.common import get_cancel_keyboard, get_skip_or_cancel_keyboard
from bot.services.google_calendar import google_calendar_service
from bot.utils.datetime_utils import format_datetime, parse_datetime_input

logger = logging.getLogger(__name__)

# Conversation States for Event Creation
EV_CHOOSE_CALENDAR, EV_ENTER_TITLE, EV_SELECT_DATE, EV_SELECT_TIME, EV_ENTER_NOTES, EV_SELECT_REMINDERS, EV_SELECT_RECURRENCE = range(7)

# Conversation States for Editing Notes
EDIT_NOTES_INPUT = range(1)


# ==========================================
# LIST & VIEW EVENTS
# ==========================================

async def list_upcoming_events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of upcoming events across user's calendars."""
    user = update.effective_user
    if not user:
        return

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        events = await get_user_upcoming_events(db, db_user.id, limit=10)

    if not events:
        text = (
            "📅 *No Upcoming Events Found*\n\n"
            "You have no scheduled dates or reminders coming up.\n"
            "Click below to create your first event! 👇"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add New Event", callback_data="start_add_event")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ])
    else:
        text = "📅 *Upcoming Dates & Events*:\n\nClick any event to view details and notes:"
        keyboard = get_upcoming_events_keyboard(events)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def view_calendar_events_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show events specifically for one calendar."""
    query = update.callback_query
    await query.answer()

    cal_id = int(query.data.split(":")[1])

    async with get_db() as db:
        cal = await get_calendar_by_id(db, cal_id)
        if not cal:
            await query.edit_text("⚠️ Calendar not found.")
            return

        events = await get_calendar_events(db, cal_id)

    if not events:
        text = f"📋 *Events in '{cal.name}'*\n\nNo events found in this calendar yet."
    else:
        text = f"📋 *Events in '{cal.name}'* ({len(events)} total):\n\nClick an event to view full notes:"

    keyboard = get_upcoming_events_keyboard(events)
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def view_event_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show comprehensive details, notes, and actions for a single event."""
    query = update.callback_query
    await query.answer()

    event_id = int(query.data.split(":")[1])
    user = update.effective_user

    async with get_db() as db:
        db_user = await get_user_by_telegram_id(db, user.id)
        event = await get_event_by_id(db, event_id)
        if not event or not db_user:
            await query.edit_text("⚠️ Event not found or deleted.")
            return

        creator_name = event.creator.full_name or f"@{event.creator.username}" if event.creator else "Unknown"
        time_str = format_datetime(event.start_time)

        # Build reminder list
        reminders_text = []
        for r in event.reminders:
            if r.remind_before_minutes == 0:
                reminders_text.append("• At event time")
            elif r.remind_before_minutes < 60:
                reminders_text.append(f"• {r.remind_before_minutes} mins before")
            elif r.remind_before_minutes < 1440:
                reminders_text.append(f"• {r.remind_before_minutes // 60} hour(s) before")
            else:
                reminders_text.append(f"• {r.remind_before_minutes // 1440} day(s) before")

        rem_summary = "\n".join(reminders_text) if reminders_text else "None"

        # Recurrence label
        rec_label = "Una sola vez (No se repite)"
        if event.recurrence == "yearly":
            rec_label = "Todos los años (Anual 🎂)"
        elif event.recurrence == "monthly":
            rec_label = "Todos los meses (Mensual 📆)"
        elif event.recurrence == "weekly":
            rec_label = "Todas las semanas (Semanal 🗓)"
        elif event.recurrence == "daily":
            rec_label = "Todos los días (Diario ⏰)"

    notes_display = f"\n📝 *Notes & Details:*\n{event.notes}\n" if event.notes else "\n📝 *Notes:* _None attached_\n"

    text = (
        f"📌 *Event:* **{event.title}**\n"
        f"📁 *Calendar:* {event.calendar.name}\n"
        f"🕒 *Date & Time:* {time_str}\n"
        f"🔁 *Recurrence:* {rec_label}\n"
        f"👤 *Created By:* {creator_name}\n"
        f"{notes_display}\n"
        f"🔔 *Scheduled Reminders:*\n{rem_summary}\n"
    )

    keyboard = get_event_detail_keyboard(
        event_id=event.id,
        can_edit=True,
        has_notes=bool(event.notes),
    )
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def delete_event_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete an event and its Google Calendar sync if present."""
    query = update.callback_query
    await query.answer()

    event_id = int(query.data.split(":")[1])

    async with get_db() as db:
        event = await get_event_by_id(db, event_id)
        if not event:
            await query.edit_text("⚠️ Event not found.")
            return

        title = event.title
        if event.google_event_id and event.calendar and event.calendar.google_calendar_id:
            google_calendar_service.delete_event(
                calendar_id=event.calendar.google_calendar_id,
                google_event_id=event.google_event_id,
            )

        await delete_event(db, event_id)

    await query.message.edit_text(
        f"🗑 *Event '{title}' has been successfully deleted.*",
        parse_mode="Markdown",
    )


# ==========================================
# CREATE EVENT CONVERSATION WIZARD
# ==========================================

async def start_add_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start wizard to create a new event."""
    user = update.effective_user
    context.user_data.clear()

    cal_id_preselect = None
    if update.callback_query and update.callback_query.data.startswith("ev_add_to:"):
        cal_id_preselect = int(update.callback_query.data.split(":")[1])
        await update.callback_query.answer()

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        calendars = await get_user_calendars(db, db_user.id)

    if not calendars:
        msg = "⚠️ You are not enrolled in any calendars yet. Please create one in *🗂 My Calendars*."
        if update.callback_query:
            await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return ConversationHandler.END

    if cal_id_preselect:
        context.user_data["event_calendar_id"] = cal_id_preselect
        text = "📌 *New Event: Step 1 of 4*\n\nPlease enter the *Title* of your event (e.g. `Project Review`, `Team Lunch`, `Release v1.0`):"
        if update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=get_cancel_keyboard("cancel_wizard"), parse_mode="Markdown")
        return EV_ENTER_TITLE

    if len(calendars) == 1:
        context.user_data["event_calendar_id"] = calendars[0].id
        text = f"📌 *New Event for '{calendars[0].name}'*\n\nPlease enter the *Title* of your event:"
        if update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=get_cancel_keyboard("cancel_wizard"), parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=get_cancel_keyboard("cancel_wizard"), parse_mode="Markdown")
        return EV_ENTER_TITLE

    # Multiple calendars - let user select one
    text = "📁 *Choose Calendar*\n\nWhich calendar do you want to add this event to?"
    keyboard = get_calendars_list_keyboard(calendars, action_prefix="pick_cal", show_create_btn=False, show_join_btn=False)

    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

    return EV_CHOOSE_CALENDAR


async def calendar_chosen_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback when user selects a calendar."""
    query = update.callback_query
    await query.answer()

    cal_id = int(query.data.split(":")[1])
    context.user_data["event_calendar_id"] = cal_id

    async with get_db() as db:
        cal = await get_calendar_by_id(db, cal_id)
        cal_name = cal.name if cal else "Calendar"

    await query.message.edit_text(
        f"📁 Selected: *{cal_name}*\n\n📌 *Step 1:* Enter the *Title* of your event (e.g. `Sprint Planning`, `Doctor Appointment`):",
        reply_markup=get_cancel_keyboard("cancel_wizard"),
        parse_mode="Markdown",
    )
    return EV_ENTER_TITLE


async def event_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store title and prompt for Date."""
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Please enter a valid title:")
        return EV_ENTER_TITLE

    context.user_data["event_title"] = title

    text = (
        f"📌 *Event:* **{title}**\n\n"
        "🗓 *Step 2: Choose Date*\n"
        "Click a quick date shortcut below, or type a date like `2026-08-30` or `tomorrow`:"
    )

    await update.message.reply_text(
        text,
        reply_markup=get_quick_date_shortcuts_keyboard(),
        parse_mode="Markdown",
    )
    return EV_SELECT_DATE


async def date_picked_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick date shortcut button."""
    query = update.callback_query
    await query.answer()

    selected_date = query.data.split(":")[1]  # e.g. '2026-08-25'
    context.user_data["event_date"] = selected_date

    text = (
        f"🗓 Selected Date: *{selected_date}*\n\n"
        "⏰ *Step 3: Choose Time*\n"
        "Select a time below or type custom time (e.g. `14:30`):"
    )

    await query.message.edit_text(
        text,
        reply_markup=get_quick_time_shortcuts_keyboard(selected_date),
        parse_mode="Markdown",
    )
    return EV_SELECT_TIME


async def date_custom_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom date text input."""
    text = update.message.text.strip()

    parsed_dt = parse_datetime_input(text)
    if not parsed_dt:
        await update.message.reply_text(
            "⚠️ Could not understand that date. Try format `YYYY-MM-DD` (e.g. `2026-08-28`) or `tomorrow`:",
            reply_markup=get_cancel_keyboard("cancel_wizard"),
        )
        return EV_SELECT_DATE

    date_str = parsed_dt.strftime("%Y-%m-%d")
    context.user_data["event_date"] = date_str

    if ":" in text:
        context.user_data["event_datetime"] = parsed_dt
        return await _prompt_notes_step(update, context)

    prompt_text = (
        f"🗓 Date set to: *{date_str}*\n\n"
        "⏰ *Step 3: Choose Time*\n"
        "Select a time below or type custom time (e.g. `14:30`):"
    )
    await update.message.reply_text(
        prompt_text,
        reply_markup=get_quick_time_shortcuts_keyboard(date_str),
        parse_mode="Markdown",
    )
    return EV_SELECT_TIME


async def time_picked_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quick time button."""
    query = update.callback_query
    await query.answer()

    dt_str = query.data.split(":", 1)[1]  # e.g. '2026-08-25 14:00'
    parsed_dt = parse_datetime_input(dt_str)
    if not parsed_dt:
        await query.edit_text("⚠️ Time parsing error. Please try again.")
        return EV_SELECT_TIME

    context.user_data["event_datetime"] = parsed_dt
    return await _prompt_notes_step(query, context, is_callback=True)


async def time_custom_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom time text input (e.g. '15:45')."""
    time_str = update.message.text.strip()
    selected_date = context.user_data.get("event_date")

    full_text = f"{selected_date} {time_str}"
    parsed_dt = parse_datetime_input(full_text)

    if not parsed_dt:
        await update.message.reply_text(
            "⚠️ Invalid time format. Please enter time like `14:30` or `9:00 AM`:",
            reply_markup=get_cancel_keyboard("cancel_wizard"),
        )
        return EV_SELECT_TIME

    context.user_data["event_datetime"] = parsed_dt
    return await _prompt_notes_step(update, context, is_callback=False)


async def _prompt_notes_step(update_or_query, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False) -> int:
    """Transition to notes step."""
    event_dt = context.user_data.get("event_datetime")
    formatted_dt = format_datetime(event_dt)

    text = (
        f"🕒 Scheduled for: *{formatted_dt}*\n\n"
        "📝 *Step 4: Add Event Notes (Optional)*\n"
        "Send any notes, meeting links, agendas, or instructions for your team (or click Skip):"
    )

    keyboard = get_skip_or_cancel_keyboard(skip_data="skip_notes", cancel_data="cancel_wizard")

    if is_callback:
        await update_or_query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    elif hasattr(update_or_query, "message"):
        await update_or_query.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update_or_query.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

    return EV_ENTER_NOTES


async def event_notes_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store notes and prompt for reminder options."""
    notes = update.message.text.strip()
    context.user_data["event_notes"] = notes
    return await _prompt_reminders_step(update, context, is_callback=False)


async def event_notes_skipped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skip notes and prompt for reminder options."""
    query = update.callback_query
    await query.answer()
    context.user_data["event_notes"] = ""
    return await _prompt_reminders_step(query, context, is_callback=True)


async def _prompt_reminders_step(update_or_query, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False) -> int:
    """Prompt user to select notification alerts."""
    if "selected_reminders" not in context.user_data:
        context.user_data["selected_reminders"] = [0, 60]

    selected = context.user_data["selected_reminders"]

    text = (
        "🔔 *Step 5: Notification Reminders*\n\n"
        "Choose when team members should receive Telegram alerts for this date:\n"
        "(Tap buttons to toggle alerts on/off, then click Save)"
    )

    keyboard = get_reminder_options_keyboard(selected)

    if is_callback:
        await update_or_query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update_or_query.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

    return EV_SELECT_REMINDERS


async def reminder_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Toggle a reminder offset on/off."""
    query = update.callback_query
    await query.answer()

    offset = int(query.data.split(":")[1])
    selected: List[int] = context.user_data.get("selected_reminders", [0, 60])

    if offset in selected:
        selected.remove(offset)
    else:
        selected.append(offset)

    context.user_data["selected_reminders"] = selected

    keyboard = get_reminder_options_keyboard(selected)
    await query.message.edit_reply_markup(reply_markup=keyboard)
    return EV_SELECT_REMINDERS


async def prompt_recurrence_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to choose recurrence frequency for the event."""
    query = update.callback_query
    await query.answer()

    text = (
        "🔁 *Paso 6: Recurrencia del Evento*\n\n"
        "¿Quieres que este evento se repita automáticamente?\n"
        "(Por ejemplo: *Todos los años* para cumpleaños o aniversarios)"
    )

    await query.message.edit_text(
        text,
        reply_markup=get_recurrence_selection_keyboard(),
        parse_mode="Markdown",
    )
    return EV_SELECT_RECURRENCE


async def recurrence_picked_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store recurrence choice and finalize event creation."""
    query = update.callback_query
    await query.answer()

    rec_type = query.data.split(":")[1]  # 'none', 'yearly', 'monthly', 'weekly', 'daily'
    context.user_data["event_recurrence"] = rec_type
    return await finalize_event_creation(update, context)


async def finalize_event_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Commit event and reminders to database and Google Calendar."""
    query = update.callback_query

    user = update.effective_user
    cal_id = context.user_data.get("event_calendar_id")
    title = context.user_data.get("event_title")
    start_time = context.user_data.get("event_datetime")
    notes = context.user_data.get("event_notes", "")
    reminder_offsets = context.user_data.get("selected_reminders", [0, 60])
    recurrence = context.user_data.get("event_recurrence", "none")

    async with get_db() as db:
        db_user = await get_or_create_user(db, user.id, user.username, user.full_name)
        cal = await get_calendar_by_id(db, cal_id)
        if not cal:
            await query.edit_text("⚠️ Calendar not found.")
            return ConversationHandler.END

        # Create event in DB with recurrence
        event = await create_event(
            db=db,
            calendar_id=cal.id,
            created_by_id=db_user.id,
            title=title,
            start_time=start_time,
            notes=notes if notes else None,
            recurrence=recurrence,
            reminder_offsets_minutes=reminder_offsets,
        )

        # Sync to Google Calendar if configured
        gcal_id = cal.google_calendar_id or settings.GOOGLE_CALENDAR_ID
        if gcal_id and google_calendar_service.is_configured():
            google_event_id = google_calendar_service.create_event(
                calendar_id=gcal_id,
                title=title,
                start_time=start_time,
                notes=notes,
            )
            if google_event_id:
                event.google_event_id = google_event_id
                await db.flush()

    time_str = format_datetime(start_time)
    notes_section = f"\n📝 *Notes:*\n{notes}\n" if notes else ""

    rec_display = "Una sola vez"
    if recurrence == "yearly":
        rec_display = "Todos los años (Anual 🎂)"
    elif recurrence == "monthly":
        rec_display = "Todos los meses (Mensual 📆)"
    elif recurrence == "weekly":
        rec_display = "Todas las semanas (Semanal 🗓)"
    elif recurrence == "daily":
        rec_display = "Todos los días (Diario ⏰)"

    success_text = (
        "🎉 *Event Created Successfully!* 🚀\n\n"
        f"📌 *Title:* **{title}**\n"
        f"📁 *Calendar:* {cal.name}\n"
        f"🕒 *Date & Time:* {time_str}\n"
        f"🔁 *Recurrence:* {rec_display}\n"
        f"{notes_section}"
        f"🔔 *Reminders Scheduled:* {len(reminder_offsets)} alert(s)\n\n"
        "Team members will automatically receive Telegram notifications!"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 View Upcoming Events", callback_data="list_upcoming_events")],
        [InlineKeyboardButton("➕ Add Another Event", callback_data="start_add_event")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
    ])

    await query.message.edit_text(success_text, reply_markup=keyboard, parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END


# ==========================================
# EDIT NOTES CONVERSATION
# ==========================================

async def start_edit_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to send new notes for an event."""
    query = update.callback_query
    await query.answer()

    event_id = int(query.data.split(":")[1])
    context.user_data["edit_event_id"] = event_id

    await query.message.reply_text(
        "📝 *Edit Event Notes*\n\nPlease send the updated notes / description for this event (or type /cancel):",
        reply_markup=get_cancel_keyboard("cancel_edit_notes"),
        parse_mode="Markdown",
    )
    return EDIT_NOTES_INPUT


async def edit_notes_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save updated notes in database."""
    new_notes = update.message.text.strip()
    event_id = context.user_data.get("edit_event_id")

    async with get_db() as db:
        updated = await update_event_notes(db, event_id, new_notes)
        if updated and updated.google_event_id and updated.calendar and updated.calendar.google_calendar_id:
            google_calendar_service.update_event(
                calendar_id=updated.calendar.google_calendar_id,
                google_event_id=updated.google_event_id,
                title=updated.title,
                notes=new_notes,
            )

    context.user_data.pop("edit_event_id", None)
    await update.message.reply_text(
        "✅ *Notes updated successfully!*",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel event creation flow."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.edit_text("❌ Event creation cancelled.")
    elif update.message:
        await update.message.reply_text("❌ Event creation cancelled.")
    context.user_data.clear()
    return ConversationHandler.END


def get_event_conversation_handlers():
    """Build conversation handlers for event creation and notes editing."""
    create_event_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_event, pattern="^(start_add_event|ev_add_to:\\d+)$"),
            CommandHandler("new", start_add_event),
            MessageHandler(filters.Regex("^➕ New Event$"), start_add_event),
        ],
        states={
            EV_CHOOSE_CALENDAR: [
                CallbackQueryHandler(calendar_chosen_callback, pattern="^pick_cal:\\d+$"),
            ],
            EV_ENTER_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, event_title_received),
            ],
            EV_SELECT_DATE: [
                CallbackQueryHandler(date_picked_callback, pattern="^dt_pick:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, date_custom_text_received),
            ],
            EV_SELECT_TIME: [
                CallbackQueryHandler(time_picked_callback, pattern="^time_pick:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_custom_text_received),
            ],
            EV_ENTER_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, event_notes_received),
                CallbackQueryHandler(event_notes_skipped, pattern="^skip_notes$"),
            ],
            EV_SELECT_REMINDERS: [
                CallbackQueryHandler(reminder_toggle_callback, pattern="^rem_toggle:\\d+$"),
                CallbackQueryHandler(prompt_recurrence_step, pattern="^rem_done$"),
            ],
            EV_SELECT_RECURRENCE: [
                CallbackQueryHandler(recurrence_picked_callback, pattern="^rec_pick:"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_wizard, pattern="^cancel_wizard$"),
            CommandHandler("cancel", cancel_wizard),
        ],
    )

    edit_notes_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_edit_notes, pattern="^ev_edit_notes:\\d+$"),
        ],
        states={
            EDIT_NOTES_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_notes_received),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_wizard, pattern="^cancel_edit_notes$"),
            CommandHandler("cancel", cancel_wizard),
        ],
    )

    return create_event_handler, edit_notes_handler
