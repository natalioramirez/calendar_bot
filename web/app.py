"""Flask Web Administration Panel for Telegram Team Calendar Bot."""

import logging
from datetime import datetime
from typing import Optional
from flask import Flask, flash, redirect, render_template, request, url_for

from bot.config import settings
from bot.database import crud
from bot.database.session import get_db, init_db
from bot.services.islamic_calendar import sync_islamic_calendar

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates")
app.secret_key = "tg-calendar-admin-secret-key-change-if-needed"


@app.context_processor
def inject_global_vars():
    return {
        "now_year": datetime.now().year,
    }


# ==========================================
# 1. DASHBOARD
# ==========================================

@app.route("/")
async def dashboard():
    """Main dashboard showing stats, upcoming events, and active calendars."""
    async with get_db() as db:
        stats = await crud.get_admin_dashboard_stats(db)
        calendars = await crud.get_all_calendars(db)
        upcoming_events = await crud.get_all_events_with_details(db)
        # Filter upcoming 5 events
        now = datetime.now()
        upcoming = [e for e in upcoming_events if e.start_time >= now][:8]

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        stats=stats,
        calendars=calendars,
        upcoming_events=upcoming,
    )


# ==========================================
# 2. CALENDARS MANAGEMENT
# ==========================================

@app.route("/calendars")
async def list_calendars():
    """List all calendars with creation modal and delete actions."""
    async with get_db() as db:
        calendars = await crud.get_all_calendars(db)
        users = await crud.get_all_users(db)

    return render_template(
        "calendars.html",
        active_page="calendars",
        calendars=calendars,
        users=users,
    )


@app.route("/calendars/create", methods=["POST"])
async def create_calendar_route():
    """Create a new calendar from web admin panel."""
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None
    owner_id_raw = request.form.get("owner_id")

    if not name:
        flash("El nombre del calendario es obligatorio.", "error")
        return redirect(url_for("list_calendars"))

    async with get_db() as db:
        owner_id = int(owner_id_raw) if owner_id_raw and owner_id_raw.isdigit() else 1
        # If user doesn't exist, pick the first user or create a system user
        user = await crud.get_user_by_id(db, owner_id)
        if not user:
            all_users = await crud.get_all_users(db)
            owner_id = all_users[0].id if all_users else 1

        cal = await crud.create_calendar(
            db=db,
            owner_id=owner_id,
            name=name,
            description=description,
        )
        flash(f"Calendario '{cal.name}' creado con éxito (Código: {cal.invite_code}).", "success")

    return redirect(url_for("list_calendars"))


@app.route("/calendars/<int:calendar_id>/delete", methods=["POST"])
async def delete_calendar_route(calendar_id: int):
    """Delete a calendar and its associated events/members."""
    async with get_db() as db:
        cal = await crud.get_calendar_by_id(db, calendar_id)
        if not cal:
            flash("El calendario no existe.", "error")
            return redirect(url_for("list_calendars"))

        cal_name = cal.name
        await crud.delete_calendar(db, calendar_id)
        flash(f"Calendario '{cal_name}' eliminado con éxito.", "success")

    return redirect(url_for("list_calendars"))


# ==========================================
# 3. USERS & MEMBERSHIPS MANAGEMENT
# ==========================================

@app.route("/members")
async def list_members():
    """List members and allow assigning or moving users across calendars."""
    calendar_id_raw = request.args.get("calendar_id")
    selected_calendar_id = int(calendar_id_raw) if calendar_id_raw and calendar_id_raw.isdigit() else None

    async with get_db() as db:
        calendars = await crud.get_all_calendars(db)
        users = await crud.get_all_users(db)

        # Build list of memberships
        memberships = []
        for cal in calendars:
            if selected_calendar_id and cal.id != selected_calendar_id:
                continue
            for member in cal.members:
                memberships.append({
                    "user": member.user,
                    "calendar": cal,
                    "role": member.role,
                    "receive_notifications": member.receive_notifications,
                })

    return render_template(
        "members.html",
        active_page="members",
        calendars=calendars,
        users=users,
        memberships=memberships,
        selected_calendar_id=selected_calendar_id,
    )


@app.route("/members/assign", methods=["POST"])
async def assign_user_route():
    """Assign or move a user to a calendar."""
    user_id_raw = request.form.get("user_id")
    calendar_id_raw = request.form.get("calendar_id")
    role = request.form.get("role", "member")

    if not user_id_raw or not calendar_id_raw:
        flash("Debes seleccionar un usuario y un calendario.", "error")
        return redirect(url_for("list_members"))

    user_id = int(user_id_raw)
    calendar_id = int(calendar_id_raw)

    async with get_db() as db:
        user = await crud.get_user_by_id(db, user_id)
        cal = await crud.get_calendar_by_id(db, calendar_id)
        if not user or not cal:
            flash("Usuario o calendario no encontrado.", "error")
            return redirect(url_for("list_members"))

        await crud.assign_user_to_calendar(db, user_id=user_id, calendar_id=calendar_id, role=role)
        flash(f"Usuario {user.full_name or user.username} asignado al calendario '{cal.name}' con rol '{role}'.", "success")

    return redirect(url_for("list_members", calendar_id=calendar_id))


@app.route("/members/remove", methods=["POST"])
async def remove_member_route():
    """Remove a user from a calendar."""
    user_id_raw = request.form.get("user_id")
    calendar_id_raw = request.form.get("calendar_id")

    if not user_id_raw or not calendar_id_raw:
        flash("Datos de membresía incompletos.", "error")
        return redirect(url_for("list_members"))

    user_id = int(user_id_raw)
    calendar_id = int(calendar_id_raw)

    async with get_db() as db:
        await crud.remove_member(db, calendar_id=calendar_id, user_id=user_id)
        flash("Usuario removido del calendario.", "success")

    return redirect(url_for("list_members", calendar_id=calendar_id))


# ==========================================
# 4. EVENTS MANAGEMENT
# ==========================================

@app.route("/events")
async def list_events():
    """List events with calendar filter and creation modal."""
    calendar_id_raw = request.args.get("calendar_id")
    selected_calendar_id = int(calendar_id_raw) if calendar_id_raw and calendar_id_raw.isdigit() else None

    async with get_db() as db:
        calendars = await crud.get_all_calendars(db)
        users = await crud.get_all_users(db)
        events = await crud.get_all_events_with_details(db, calendar_id=selected_calendar_id)

    return render_template(
        "events.html",
        active_page="events",
        calendars=calendars,
        users=users,
        events=events,
        selected_calendar_id=selected_calendar_id,
    )


@app.route("/events/create", methods=["POST"])
async def create_event_route():
    """Create a new event in a calendar."""
    calendar_id_raw = request.form.get("calendar_id")
    user_id_raw = request.form.get("user_id")
    title = request.form.get("title", "").strip()
    date_str = request.form.get("date", "").strip()
    time_str = request.form.get("time", "09:00").strip()
    notes = request.form.get("notes", "").strip() or None
    recurrence = request.form.get("recurrence", "none")
    reminders_raw = request.form.getlist("reminders")

    if not title or not date_str or not calendar_id_raw:
        flash("Título, fecha y calendario son obligatorios.", "error")
        return redirect(url_for("list_events"))

    try:
        start_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("Formato de fecha u hora inválido.", "error")
        return redirect(url_for("list_events"))

    reminder_offsets = [int(r) for r in reminders_raw if r.isdigit()]
    calendar_id = int(calendar_id_raw)

    async with get_db() as db:
        cal = await crud.get_calendar_by_id(db, calendar_id)
        if not cal:
            flash("El calendario seleccionado no existe.", "error")
            return redirect(url_for("list_events"))

        owner_id = int(user_id_raw) if user_id_raw and user_id_raw.isdigit() else cal.owner_id

        await crud.create_event(
            db=db,
            calendar_id=calendar_id,
            created_by_id=owner_id,
            title=title,
            start_time=start_time,
            notes=notes,
            recurrence=recurrence,
            reminder_offsets_minutes=reminder_offsets,
        )
        flash(f"Evento '{title}' creado con éxito en '{cal.name}'.", "success")

    return redirect(url_for("list_events", calendar_id=calendar_id))


@app.route("/events/<int:event_id>/delete", methods=["POST"])
async def delete_event_route(event_id: int):
    """Delete an event from web admin panel."""
    async with get_db() as db:
        ev = await crud.get_event_by_id(db, event_id)
        if not ev:
            flash("El evento no existe.", "error")
            return redirect(url_for("list_events"))

        title = ev.title
        cal_id = ev.calendar_id
        await crud.delete_event(db, event_id)
        flash(f"Evento '{title}' eliminado con éxito.", "success")

    return redirect(url_for("list_events", calendar_id=cal_id))


# ==========================================
# 5. SYNC ISLAMIC CALENDAR
# ==========================================

@app.route("/sync-islamic", methods=["POST"])
async def sync_islamic():
    """Trigger manual sync for Islamic calendar P from web admin panel."""
    now = datetime.now()
    try:
        count = await sync_islamic_calendar("P", now.year, now.month, months_ahead=12)
        flash(f"Sincronización islámica completada. Se importaron {count} nuevas festividades para el calendario 'P'.", "success")
    except Exception as e:
        logger.exception("Error syncing Islamic calendar via web: %s", e)
        flash(f"Error al sincronizar festividades islámicas: {e}", "error")

    return redirect(url_for("dashboard"))


# ==========================================
# RUNNER
# ==========================================

async def setup():
    """Initialize DB tables if not already initialized."""
    await init_db()


if __name__ == "__main__":
    import asyncio
    asyncio.run(setup())
    host = settings.WEB_ADMIN_HOST
    port = settings.WEB_ADMIN_PORT
    print("\n" + "=" * 60)
    print(f"🚀 Panel de Administración Web de Calendarios iniciado:")
    print(f"👉 http://{host}:{port}")
    print("=" * 60 + "\n")
    app.run(host=host, port=port, debug=False)
