"""Database CRUD helper functions."""

from datetime import datetime, timedelta
from typing import List, Optional, Sequence
from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import Calendar, CalendarMember, Event, Reminder, User


# ==========================================
# USER CRUD
# ==========================================

async def get_or_create_user(
    db: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    full_name: str = "",
) -> User:
    """Retrieve an existing user or create a new user record."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
        )
        db.add(user)
        await db.flush()
        # No personal calendar is created: calendars come from the web admin panel
        # and users only subscribe to them with /sub.
    else:
        # Update username/full_name if changed
        updated = False
        if username and user.username != username:
            user.username = username
            updated = True
        if full_name and user.full_name != full_name:
            user.full_name = full_name
            updated = True
        if updated:
            await db.flush()

    return user


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> Optional[User]:
    """Get user by Telegram ID."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by primary key ID."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ==========================================
# CALENDAR CRUD
# ==========================================

async def create_calendar(
    db: AsyncSession,
    owner_id: int,
    name: str,
    description: Optional[str] = None,
    google_calendar_id: Optional[str] = None,
) -> Calendar:
    """Create a new calendar and assign the owner as a member."""
    calendar = Calendar(
        name=name,
        description=description,
        owner_id=owner_id,
        google_calendar_id=google_calendar_id,
    )
    db.add(calendar)
    await db.flush()

    membership = CalendarMember(
        calendar_id=calendar.id,
        user_id=owner_id,
        role="owner",
        receive_notifications=True,
    )
    db.add(membership)
    await db.flush()
    return calendar


async def get_user_calendars(db: AsyncSession, user_id: int) -> Sequence[Calendar]:
    """Retrieve all calendars the user belongs to."""
    stmt = (
        select(Calendar)
        .join(CalendarMember, Calendar.id == CalendarMember.calendar_id)
        .where(CalendarMember.user_id == user_id)
        .order_by(Calendar.name)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_calendar_by_id(db: AsyncSession, calendar_id: int) -> Optional[Calendar]:
    """Get calendar by its ID."""
    stmt = select(Calendar).where(Calendar.id == calendar_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_calendar_by_invite_code(db: AsyncSession, invite_code: str) -> Optional[Calendar]:
    """Find calendar by invite code."""
    stmt = select(Calendar).where(Calendar.invite_code == invite_code.strip().upper())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
async def get_calendar_by_name(db: AsyncSession, name: str) -> Optional[Calendar]:
    """Get a calendar by its name.
    Returns the first calendar matching the given name, or None if not found.
    """
    stmt = select(Calendar).where(Calendar.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()



async def add_calendar_member(
    db: AsyncSession,
    calendar_id: int,
    user_id: int,
    role: str = "member",
) -> CalendarMember:
    """Add user to a calendar if not already a member."""
    stmt = select(CalendarMember).where(
        CalendarMember.calendar_id == calendar_id,
        CalendarMember.user_id == user_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    member = CalendarMember(
        calendar_id=calendar_id,
        user_id=user_id,
        role=role,
        receive_notifications=True,
    )
    db.add(member)
    await db.flush()
    return member


async def get_calendar_members(db: AsyncSession, calendar_id: int) -> Sequence[CalendarMember]:
    """Get all members of a calendar with their user data loaded."""
    stmt = (
        select(CalendarMember)
        .options(selectinload(CalendarMember.user))
        .where(CalendarMember.calendar_id == calendar_id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_member(db: AsyncSession, calendar_id: int, user_id: int) -> Optional[CalendarMember]:
    """Check membership for a specific user in a calendar."""
    stmt = select(CalendarMember).where(
        CalendarMember.calendar_id == calendar_id,
        CalendarMember.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def toggle_member_notifications(db: AsyncSession, calendar_id: int, user_id: int) -> bool:
    """Toggle notification preference for a user in a calendar and return new state."""
    member = await get_member(db, calendar_id, user_id)
    if member:
        member.receive_notifications = not member.receive_notifications
        await db.flush()
        return member.receive_notifications
    return False


async def get_all_users(db: AsyncSession) -> Sequence[User]:
    """Retrieve all registered users."""
    stmt = select(User).order_by(User.id.asc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_all_calendars(db: AsyncSession) -> Sequence[Calendar]:
    """Retrieve all calendars in the database with their owner and member counts."""
    stmt = (
        select(Calendar)
        .options(selectinload(Calendar.owner), selectinload(Calendar.members), selectinload(Calendar.events))
        .order_by(Calendar.id.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def leave_calendar(db: AsyncSession, calendar_id: int, user_id: int) -> bool:
    """Allow a user to leave a calendar."""
    stmt = delete(CalendarMember).where(
        CalendarMember.calendar_id == calendar_id,
        CalendarMember.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.rowcount > 0


async def remove_member(db: AsyncSession, calendar_id: int, user_id: int) -> bool:
    """Remove a user membership from a calendar."""
    return await leave_calendar(db, calendar_id, user_id)


async def assign_user_to_calendar(
    db: AsyncSession,
    user_id: int,
    calendar_id: int,
    role: str = "member",
) -> CalendarMember:
    """Assign or update a user's membership to a calendar."""
    member = await get_member(db, calendar_id, user_id)
    if member:
        member.role = role
        await db.flush()
        return member
    return await add_calendar_member(db, calendar_id, user_id, role=role)


async def delete_calendar(db: AsyncSession, calendar_id: int) -> bool:
    """Delete a calendar and all associated events/reminders/members."""
    # First delete reminders and events
    events = await get_calendar_events(db, calendar_id)
    for ev in events:
        await delete_event(db, ev.id)
    # Delete members
    await db.execute(delete(CalendarMember).where(CalendarMember.calendar_id == calendar_id))
    # Delete calendar
    stmt = delete(Calendar).where(Calendar.id == calendar_id)
    result = await db.execute(stmt)
    return result.rowcount > 0


from dateutil.relativedelta import relativedelta


def compute_next_occurrence(start_time: datetime, recurrence: str) -> datetime:
    """Calculate the next start_time based on recurrence pattern."""
    if recurrence == "daily":
        return start_time + timedelta(days=1)
    elif recurrence == "weekly":
        return start_time + timedelta(weeks=1)
    elif recurrence == "monthly":
        return start_time + relativedelta(months=1)
    elif recurrence == "yearly":
        return start_time + relativedelta(years=1)
    return start_time


# ==========================================
# EVENT CRUD
# ==========================================

async def create_event(
    db: AsyncSession,
    calendar_id: int,
    created_by_id: int,
    title: str,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    notes: Optional[str] = None,
    is_all_day: bool = False,
    recurrence: str = "none",
    google_event_id: Optional[str] = None,
    reminder_offsets_minutes: Optional[List[int]] = None,
) -> Event:
    """Create a new event and schedule its reminders."""
    event = Event(
        calendar_id=calendar_id,
        created_by_id=created_by_id,
        title=title,
        notes=notes,
        start_time=start_time,
        end_time=end_time,
        is_all_day=is_all_day,
        recurrence=recurrence,
        google_event_id=google_event_id,
    )
    db.add(event)
    await db.flush()

    if reminder_offsets_minutes is None:
        reminder_offsets_minutes = [0, 60]

    for offset in reminder_offsets_minutes:
        remind_at = start_time - timedelta(minutes=offset)
        reminder = Reminder(
            event_id=event.id,
            remind_before_minutes=offset,
            remind_at=remind_at,
            is_sent=False,
        )
        db.add(reminder)

    await db.flush()
    return event


async def get_event_by_id(db: AsyncSession, event_id: int) -> Optional[Event]:
    """Get event with calendar and creator loaded."""
    stmt = (
        select(Event)
        .options(selectinload(Event.calendar), selectinload(Event.creator), selectinload(Event.reminders))
        .where(Event.id == event_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_event_by_calendar_and_title_and_time(db: AsyncSession, calendar_id: int, title: str, start_time: datetime) -> Optional[Event]:
    """Return an existing event with matching calendar, title, and start_time, or None.
    Used to avoid duplicate events when syncing calendars.
    """
    stmt = select(Event).where(
        Event.calendar_id == calendar_id,
        Event.title == title,
        Event.start_time == start_time,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()



async def get_calendar_events(
    db: AsyncSession,
    calendar_id: int,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> Sequence[Event]:
    """Get events in a calendar within a date range."""
    conditions = [Event.calendar_id == calendar_id]
    if from_date:
        conditions.append(Event.start_time >= from_date)
    if to_date:
        conditions.append(Event.start_time <= to_date)

    stmt = select(Event).where(and_(*conditions)).order_by(Event.start_time.asc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_user_upcoming_events(
    db: AsyncSession,
    user_id: int,
    limit: int = 10,
    from_date: Optional[datetime] = None,
) -> Sequence[Event]:
    """Get upcoming events across all calendars the user is enrolled in."""
    if from_date is None:
        from_date = datetime.now()

    stmt = (
        select(Event)
        .join(Calendar, Event.calendar_id == Calendar.id)
        .join(CalendarMember, Calendar.id == CalendarMember.calendar_id)
        .options(selectinload(Event.calendar))
        .where(
            CalendarMember.user_id == user_id,
            Event.start_time >= from_date,
        )
        .order_by(Event.start_time.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def update_event_notes(db: AsyncSession, event_id: int, notes: str) -> Optional[Event]:
    """Update the notes / description of an event."""
    stmt = update(Event).where(Event.id == event_id).values(notes=notes)
    await db.execute(stmt)
    return await get_event_by_id(db, event_id)


async def delete_event(db: AsyncSession, event_id: int) -> bool:
    """Delete an event and cascade-delete its reminders."""
    stmt = delete(Event).where(Event.id == event_id)
    result = await db.execute(stmt)
    return result.rowcount > 0


async def advance_recurring_event(db: AsyncSession, event_id: int) -> Optional[Event]:
    """Advance a recurring event to its next occurrence and reset its reminders."""
    event = await get_event_by_id(db, event_id)
    if not event or event.recurrence == "none":
        return event

    next_time = compute_next_occurrence(event.start_time, event.recurrence)
    event.start_time = next_time

    # Reset all reminders for the new start_time
    for r in event.reminders:
        r.remind_at = next_time - timedelta(minutes=r.remind_before_minutes)
        r.is_sent = False

    await db.flush()
    return event


# ==========================================
# REMINDER CRUD
# ==========================================

async def get_pending_reminders(
    db: AsyncSession,
    current_time: Optional[datetime] = None,
) -> Sequence[Reminder]:
    """Fetch all un-sent reminders whose remind_at is past or equal to current_time."""
    if current_time is None:
        current_time = datetime.now()

    stmt = (
        select(Reminder)
        .options(
            selectinload(Reminder.event).selectinload(Event.calendar).selectinload(Calendar.members).selectinload(CalendarMember.user),
            selectinload(Reminder.event).selectinload(Event.reminders),
        )
        .where(
            Reminder.is_sent == False,
            Reminder.remind_at <= current_time,
        )
        .order_by(Reminder.remind_at.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def mark_reminder_sent(db: AsyncSession, reminder_id: int) -> None:
    """Mark a reminder as sent."""
    stmt = update(Reminder).where(Reminder.id == reminder_id).values(is_sent=True)
    await db.execute(stmt)


async def get_all_events_with_details(
    db: AsyncSession,
    calendar_id: Optional[int] = None,
) -> Sequence[Event]:
    """Get all events with their calendar and creator loaded."""
    stmt = select(Event).options(selectinload(Event.calendar), selectinload(Event.creator))
    if calendar_id:
        stmt = stmt.where(Event.calendar_id == calendar_id)
    stmt = stmt.order_by(Event.start_time.asc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_admin_dashboard_stats(db: AsyncSession) -> dict:
    """Get counts for dashboard overview."""
    from sqlalchemy import func
    users_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    cals_count = (await db.execute(select(func.count(Calendar.id)))).scalar_one()
    events_count = (await db.execute(select(func.count(Event.id)))).scalar_one()
    reminders_pending = (await db.execute(select(func.count(Reminder.id)).where(Reminder.is_sent == False))).scalar_one()

    return {
        "users_count": users_count,
        "calendars_count": cals_count,
        "events_count": events_count,
        "reminders_pending": reminders_pending,
    }
