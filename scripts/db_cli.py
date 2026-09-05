"""Command-line utility to quickly inspect, create, and manage calendars and events in the database."""

import argparse
import asyncio
from datetime import datetime
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database.session import get_db, init_db
from bot.database.models import User, Calendar, CalendarMember, Event, Reminder
from bot.database import crud
from bot.utils.datetime_utils import parse_datetime_input


async def cmd_list() -> None:
    """List all users, calendars, and events currently in the database."""
    await init_db()
    async with get_db() as db:
        # Users
        users = (await db.execute(select(User))).scalars().all()
        print("\n" + "=" * 60)
        print("👥 USERS IN DATABASE")
        print("=" * 60)
        for u in users:
            print(f"• ID: {u.id} | Telegram ID: {u.telegram_id} | Name: {u.full_name or 'N/A'} (@{u.username or 'N/A'})")

        # Calendars
        calendars = (
            await db.execute(
                select(Calendar).options(selectinload(Calendar.owner), selectinload(Calendar.members), selectinload(Calendar.events))
            )
        ).scalars().all()
        print("\n" + "=" * 60)
        print("🗂 CALENDARS IN DATABASE")
        print("=" * 60)
        for c in calendars:
            owner_name = c.owner.full_name if c.owner else f"User {c.owner_id}"
            print(f"• [ID: {c.id}] '{c.name}'")
            print(f"  Owner: {owner_name} | Invite Code: {c.invite_code} | Members: {len(c.members)} | Events: {len(c.events)}")
            if c.description:
                print(f"  Description: {c.description}")

        # Events
        events = (
            await db.execute(
                select(Event).options(selectinload(Event.calendar), selectinload(Event.creator)).order_by(Event.start_time.asc())
            )
        ).scalars().all()
        print("\n" + "=" * 60)
        print("📅 ALL EVENTS IN DATABASE")
        print("=" * 60)
        for e in events:
            cal_name = e.calendar.name if e.calendar else f"Cal {e.calendar_id}"
            time_str = e.start_time.strftime("%Y-%m-%d %H:%M")
            rec_str = f" [🔁 {e.recurrence}]" if e.recurrence != "none" else ""
            print(f"• [ID: {e.id}] '{e.title}'{rec_str} -> {cal_name} at {time_str}")
            if e.notes:
                print(f"  Notes: {e.notes}")
        print("\n" + "=" * 60 + "\n")


async def cmd_add_calendar(name: str, description: str = None, user_id: int = None) -> None:
    """Create a new calendar."""
    await init_db()
    async with get_db() as db:
        if not user_id:
            first_user = (await db.execute(select(User).limit(1))).scalar_one_or_none()
            if not first_user:
                print("❌ No user found in the database. Please start the bot first on Telegram.")
                return
            user_id = first_user.id

        calendar = await crud.create_calendar(
            db=db,
            owner_id=user_id,
            name=name,
            description=description,
        )
        print(f"✅ Successfully created calendar '{calendar.name}' (ID: {calendar.id})")
        print(f"🔑 Invite code: {calendar.invite_code}")


async def cmd_add_event(cal_id: int, title: str, date_str: str, recurrence: str = "none", notes: str = None, user_id: int = None) -> None:
    """Add a new event to a calendar."""
    await init_db()
    parsed_dt = parse_datetime_input(date_str)
    if not parsed_dt:
        print(f"❌ Invalid date format '{date_str}'. Try '2026-08-30 15:00'.")
        return

    async with get_db() as db:
        cal = await crud.get_calendar_by_id(db, cal_id)
        if not cal:
            print(f"❌ Calendar with ID {cal_id} not found.")
            return

        if not user_id:
            user_id = cal.owner_id

        event = await crud.create_event(
            db=db,
            calendar_id=cal.id,
            created_by_id=user_id,
            title=title,
            start_time=parsed_dt,
            notes=notes,
            recurrence=recurrence,
            reminder_offsets_minutes=[0, 60],
        )
        rec_str = f" [🔁 {event.recurrence}]" if event.recurrence != "none" else ""
        print(f"✅ Added event '{event.title}'{rec_str} (ID: {event.id}) to '{cal.name}' at {event.start_time.strftime('%Y-%m-%d %H:%M')}")


def main():
    parser = argparse.ArgumentParser(description="Database CLI Manager for Team Calendar Bot")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list
    subparsers.add_parser("list", help="List all users, calendars, and events")

    # add-cal
    add_cal_parser = subparsers.add_parser("add-cal", help="Create a new calendar")
    add_cal_parser.add_argument("name", help="Calendar name (e.g. 'Marketing Team')")
    add_cal_parser.add_argument("--desc", help="Optional description", default=None)
    add_cal_parser.add_argument("--user-id", type=int, help="Owner user ID (default: first user)", default=None)

    # add-event
    add_ev_parser = subparsers.add_parser("add-event", help="Create a new event")
    add_ev_parser.add_argument("cal_id", type=int, help="Calendar ID to add event to")
    add_ev_parser.add_argument("title", help="Event title (e.g. 'Cumpleaños de Ana')")
    add_ev_parser.add_argument("date", help="Date/time (e.g. '2026-08-30 15:30')")
    add_ev_parser.add_argument("--rec", choices=["none", "daily", "weekly", "monthly", "yearly"], default="none", help="Recurrence frequency")
    add_ev_parser.add_argument("--notes", help="Optional notes/links", default=None)

    args = parser.parse_args()

    if args.command == "list":
        asyncio.run(cmd_list())
    elif args.command == "add-cal":
        asyncio.run(cmd_add_calendar(args.name, args.desc, args.user_id))
    elif args.command == "add-event":
        asyncio.run(cmd_add_event(args.cal_id, args.title, args.date, args.rec, args.notes))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

