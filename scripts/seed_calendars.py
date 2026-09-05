"""Script to manually create and seed calendars (and optional events) directly in the database."""

import asyncio
from datetime import datetime, timedelta
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.database.session import get_db, init_db
from bot.database.models import User, Calendar, CalendarMember, Event, Reminder
from bot.database import crud


# ==============================================================================
# CONFIGURATION: Define the calendars you want to create here!
# ==============================================================================
CALENDARS_TO_CREATE: List[Dict[str, Any]] = [
    {
        "name": "Dev & Engineering",
        "description": "Sprint planning, code freezes, deployments, and tech reviews.",
        "events": [
            {
                "title": "Sprint Planning Semanal",
                "notes": "Revisar backlog y asignar tareas.\nGoogle Meet: https://meet.google.com/abc-def",
                "start_time": datetime.now() + timedelta(days=1, hours=2),
                "recurrence": "weekly",  # 'none', 'daily', 'weekly', 'monthly', 'yearly'
                "reminder_offsets": [0, 60],
            },
            {
                "title": "Deploy a Producción",
                "notes": "Ventana de mantenimiento y deploy.",
                "start_time": datetime.now() + timedelta(days=3, hours=5),
                "recurrence": "none",
                "reminder_offsets": [0, 15, 60],
            },
        ],
    },
    {
        "name": "Cumpleaños y Aniversarios",
        "description": "Fechas festivas del equipo que se repiten todos los años.",
        "events": [
            {
                "title": "🎂 Cumpleaños de Leandro",
                "notes": "¡Comprar torta y saludar en el grupo!",
                "start_time": datetime(2026, 9, 15, 9, 0),
                "recurrence": "yearly",  # Se repite automáticamente todos los años!
                "reminder_offsets": [0, 1440],  # Al momento y 1 día antes
            },
        ],
    },
    {
        "name": "Administración y Pagos",
        "description": "Cierres contables y pagos mensuales.",
        "events": [
            {
                "title": "💼 Cierre Mensual de Facturación",
                "notes": "Enviar facturas a contabilidad.",
                "start_time": datetime(2026, 8, 31, 10, 0),
                "recurrence": "monthly",  # Se repite todos los meses!
                "reminder_offsets": [0, 1440],
            },
        ],
    },
]


async def seed_data(owner_telegram_id: int = None) -> None:
    """Insert calendars and events into the database for the given owner."""
    await init_db()

    async with get_db() as db:
        if owner_telegram_id:
            user = await crud.get_user_by_telegram_id(db, owner_telegram_id)
        else:
            from sqlalchemy import select
            result = await db.execute(select(User).limit(1))
            user = result.scalar_one_or_none()

        if not user:
            print("❌ No user found in the database! Please run /start on Telegram first, or specify a telegram_id.")
            return

        print(f"👤 Creating calendars for User: {user.full_name or user.username} (ID: {user.id}, Telegram ID: {user.telegram_id})\n")

        for item in CALENDARS_TO_CREATE:
            cal_name = item["name"]
            cal_desc = item.get("description", "")
            events_to_add = item.get("events", [])

            # 1. Create Calendar
            calendar = await crud.create_calendar(
                db=db,
                owner_id=user.id,
                name=cal_name,
                description=cal_desc,
            )

            print(f"✅ Created Calendar: '{calendar.name}'")
            print(f"   🔑 Invite Code: {calendar.invite_code}")

            # 2. Add optional initial events
            for ev_data in events_to_add:
                event = await crud.create_event(
                    db=db,
                    calendar_id=calendar.id,
                    created_by_id=user.id,
                    title=ev_data["title"],
                    start_time=ev_data["start_time"],
                    notes=ev_data.get("notes"),
                    recurrence=ev_data.get("recurrence", "none"),
                    reminder_offsets_minutes=ev_data.get("reminder_offsets", [0, 60]),
                )
                rec_str = f" [🔁 {event.recurrence}]" if event.recurrence != "none" else ""
                print(f"   📅 Added Event: '{event.title}'{rec_str} scheduled for {event.start_time.strftime('%Y-%m-%d %H:%M')}")

            print()

        print("🎉 All calendars and events were created successfully!")
        print("💡 Open Telegram and go to '🗂 My Calendars' to see them live in the bot.")


if __name__ == "__main__":
    asyncio.run(seed_data())

