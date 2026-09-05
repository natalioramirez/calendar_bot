"""Unit tests for database CRUD and models."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.database.models import Base
from bot.database import crud


@pytest.fixture
async def test_session():
    """Create in-memory SQLite engine and session for testing."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_user_creation_and_default_calendar(test_session: AsyncSession):
    """Test user registration creates user and a default personal calendar."""
    user = await crud.get_or_create_user(
        test_session,
        telegram_id=123456789,
        username="john_doe",
        full_name="John Doe",
    )
    assert user.id is not None
    assert user.telegram_id == 123456789

    # User should automatically have their default calendar
    calendars = await crud.get_user_calendars(test_session, user.id)
    assert len(calendars) == 1
    assert calendars[0].name == "Personal Calendar"
    assert calendars[0].invite_code is not None


@pytest.mark.asyncio
async def test_team_calendar_and_invites(test_session: AsyncSession):
    """Test creating a shared team calendar and inviting another user."""
    alice = await crud.get_or_create_user(test_session, telegram_id=111, username="alice", full_name="Alice")
    bob = await crud.get_or_create_user(test_session, telegram_id=222, username="bob", full_name="Bob")

    # Alice creates Dev Team calendar
    team_cal = await crud.create_calendar(
        test_session,
        owner_id=alice.id,
        name="Dev Team",
        description="Engineering sprint dates",
    )
    assert team_cal.id is not None

    # Bob joins using invite code
    found_cal = await crud.get_calendar_by_invite_code(test_session, team_cal.invite_code)
    assert found_cal is not None
    assert found_cal.id == team_cal.id

    member = await crud.add_calendar_member(test_session, found_cal.id, bob.id, role="member")
    assert member.user_id == bob.id

    # Check members
    members = await crud.get_calendar_members(test_session, team_cal.id)
    assert len(members) == 2


@pytest.mark.asyncio
async def test_event_and_reminders_creation(test_session: AsyncSession):
    """Test creating an event with notes and checking scheduled reminders."""
    user = await crud.get_or_create_user(test_session, telegram_id=333, username="carol", full_name="Carol")
    cal = await crud.create_calendar(test_session, owner_id=user.id, name="Project Alpha")

    start_time = datetime.now() + timedelta(hours=2)
    event = await crud.create_event(
        test_session,
        calendar_id=cal.id,
        created_by_id=user.id,
        title="Sprint Review & Demo",
        notes="Google Meet link: https://meet.google.com/xyz-abc\nAgenda: Review sprint tasks",
        start_time=start_time,
        reminder_offsets_minutes=[0, 60],  # at time and 1h before
    )
    assert event.id is not None
    assert event.title == "Sprint Review & Demo"
    assert "https://meet.google.com" in event.notes

    # Verify pending reminders for 1 hour before
    check_time = start_time - timedelta(minutes=59)
    pending = await crud.get_pending_reminders(test_session, current_time=check_time)
    assert len(pending) == 1
    assert pending[0].event_id == event.id
    assert pending[0].remind_before_minutes == 60

    # Mark as sent
    await crud.mark_reminder_sent(test_session, pending[0].id)
    pending_after = await crud.get_pending_reminders(test_session, current_time=check_time)
    assert len(pending_after) == 0


@pytest.mark.asyncio
async def test_update_notes_and_delete_event(test_session: AsyncSession):
    """Test editing notes and deleting event."""
    user = await crud.get_or_create_user(test_session, telegram_id=444, username="dave", full_name="Dave")
    cal = await crud.create_calendar(test_session, owner_id=user.id, name="Operations")

    event = await crud.create_event(
        test_session,
        calendar_id=cal.id,
        created_by_id=user.id,
        title="Server Maintenance",
        notes="Initial note",
        start_time=datetime.now() + timedelta(days=1),
    )

    updated_event = await crud.update_event_notes(test_session, event.id, "Updated note: downtime 15m")
    assert updated_event.notes == "Updated note: downtime 15m"

    # Delete event
    deleted = await crud.delete_event(test_session, event.id)
    assert deleted is True

    not_found = await crud.get_event_by_id(test_session, event.id)
    assert not_found is None


@pytest.mark.asyncio
async def test_recurring_events_advance(test_session: AsyncSession):
    """Test recurring events advancement across yearly, monthly, and weekly cycles."""
    user = await crud.get_or_create_user(test_session, telegram_id=555, username="elena", full_name="Elena")
    cal = await crud.create_calendar(test_session, owner_id=user.id, name="Celebrations")

    # 1. Yearly birthday
    bday_time = datetime(2026, 9, 15, 9, 0)
    event_yearly = await crud.create_event(
        test_session,
        calendar_id=cal.id,
        created_by_id=user.id,
        title="Elena's Birthday",
        notes="Party at 8pm",
        start_time=bday_time,
        recurrence="yearly",
        reminder_offsets_minutes=[0, 1440],
    )
    assert event_yearly.recurrence == "yearly"

    # Advance to next year
    advanced = await crud.advance_recurring_event(test_session, event_yearly.id)
    assert advanced.start_time == datetime(2027, 9, 15, 9, 0)
    for r in advanced.reminders:
        assert r.is_sent is False
        if r.remind_before_minutes == 1440:
            assert r.remind_at == datetime(2027, 9, 14, 9, 0)

    # 2. Monthly recurrence
    event_monthly = await crud.create_event(
        test_session,
        calendar_id=cal.id,
        created_by_id=user.id,
        title="Monthly Billing",
        start_time=datetime(2026, 1, 31, 10, 0),
        recurrence="monthly",
    )
    advanced_month = await crud.advance_recurring_event(test_session, event_monthly.id)
    assert advanced_month.start_time.month == 2
    assert advanced_month.start_time.day == 28
