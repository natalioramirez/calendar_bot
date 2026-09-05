"""Unit tests for scheduler service and reminder formatting."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.database.models import Base
from bot.database import crud
from bot.services.scheduler import check_and_send_reminders, format_reminder_message


def test_format_reminder_message():
    """Verify reminder message layout with notes and different alert timings."""
    msg_now = format_reminder_message(
        event_title="Sprint Retro",
        cal_name="Dev Team",
        start_time_str="Monday, Aug 25 at 10:00",
        notes="Discuss blockers",
        offset_mins=0,
    )
    assert "EVENT STARTING NOW" in msg_now
    assert "Sprint Retro" in msg_now
    assert "Dev Team" in msg_now
    assert "Discuss blockers" in msg_now

    msg_1h = format_reminder_message(
        event_title="Client Call",
        cal_name="Sales",
        start_time_str="Monday, Aug 25 at 14:00",
        notes="",
        offset_mins=60,
    )
    assert "Event in 1 hour(s)" in msg_1h


@pytest.mark.asyncio
async def test_check_and_send_reminders(monkeypatch):
    """Test reminder dispatcher sends Telegram messages and marks reminders as sent."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    # Monkeypatch get_db in scheduler to use our in-memory test engine
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_get_db():
        async with session_maker() as s:
            yield s
            await s.commit()

    monkeypatch.setattr("bot.services.scheduler.get_db", mock_get_db)

    # Seed data
    async with session_maker() as session:
        user = await crud.get_or_create_user(session, telegram_id=99999, username="tester", full_name="Tester")
        cal = await crud.create_calendar(session, owner_id=user.id, name="Test Cal")

        # Create event scheduled right now
        event = await crud.create_event(
            session,
            calendar_id=cal.id,
            created_by_id=user.id,
            title="Deploy to Prod",
            notes="Check database migrations",
            start_time=datetime.now(),
            reminder_offsets_minutes=[0],
        )
        await session.commit()

    # Mock Telegram Bot
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    processed = await check_and_send_reminders(mock_bot)
    assert processed == 1
    assert mock_bot.send_message.called
    call_args = mock_bot.send_message.call_args[1]
    assert call_args["chat_id"] == 99999
    assert "Deploy to Prod" in call_args["text"]
    assert "Check database migrations" in call_args["text"]

    # Running a second time should process 0 since it is marked sent
    processed_again = await check_and_send_reminders(mock_bot)
    assert processed_again == 0

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_check_and_send_recurring_reminders(monkeypatch):
    """Test scheduler automatically advances recurring event to next cycle after sending."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_get_db():
        async with session_maker() as s:
            yield s
            await s.commit()

    monkeypatch.setattr("bot.services.scheduler.get_db", mock_get_db)

    # Create yearly recurring event (e.g. Birthday)
    event_start = datetime.now()
    async with session_maker() as session:
        user = await crud.get_or_create_user(session, telegram_id=88888, username="bday_user", full_name="Birthday User")
        cal = await crud.create_calendar(session, owner_id=user.id, name="Birthdays")
        event = await crud.create_event(
            session,
            calendar_id=cal.id,
            created_by_id=user.id,
            title="Annual Anniversary",
            start_time=event_start,
            recurrence="yearly",
            reminder_offsets_minutes=[0],
        )
        event_id = event.id
        await session.commit()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    # Process reminder
    processed = await check_and_send_reminders(mock_bot)
    assert processed == 1
    assert mock_bot.send_message.called

    # Check that event was advanced by 1 year and reminder was re-armed
    async with session_maker() as session:
        updated_event = await crud.get_event_by_id(session, event_id)
        assert updated_event.start_time.year == event_start.year + 1
        assert len(updated_event.reminders) == 1
        assert updated_event.reminders[0].is_sent is False
        assert updated_event.reminders[0].remind_at.year == event_start.year + 1

    await test_engine.dispose()
