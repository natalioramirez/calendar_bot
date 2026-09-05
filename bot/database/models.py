"""SQLAlchemy ORM models for Users, Calendars, Members, Events, and Reminders."""

import secrets
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def generate_invite_code() -> str:
    """Generate a short unique 8-character invite code for calendars."""
    return secrets.token_hex(4).upper()


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class User(Base):
    """Telegram user model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    owned_calendars: Mapped[List["Calendar"]] = relationship(
        "Calendar", back_populates="owner", cascade="all, delete-orphan"
    )
    memberships: Mapped[List["CalendarMember"]] = relationship(
        "CalendarMember", back_populates="user", cascade="all, delete-orphan"
    )
    created_events: Mapped[List["Event"]] = relationship(
        "Event", back_populates="creator"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Calendar(Base):
    """A calendar workspace (e.g. Team Dev, Marketing, Personal, etc.)."""

    __tablename__ = "calendars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    invite_code: Mapped[str] = mapped_column(
        String(16), unique=True, default=generate_invite_code, index=True
    )
    google_calendar_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="owned_calendars")
    members: Mapped[List["CalendarMember"]] = relationship(
        "CalendarMember", back_populates="calendar", cascade="all, delete-orphan"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event", back_populates="calendar", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Calendar(id={self.id}, name='{self.name}', invite_code='{self.invite_code}')>"


class CalendarMember(Base):
    """Membership table associating users with calendars, roles, and notification settings."""

    __tablename__ = "calendar_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), default="member")  # 'owner', 'admin', 'member'
    receive_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    calendar: Mapped["Calendar"] = relationship("Calendar", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="memberships")

    def __repr__(self) -> str:
        return f"<CalendarMember(calendar_id={self.calendar_id}, user_id={self.user_id}, role='{self.role}')>"


class Event(Base):
    """An event/date item with notes and notifications."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False
    )
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence: Mapped[str] = mapped_column(String(20), default="none")  # 'none', 'daily', 'weekly', 'monthly', 'yearly'
    google_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    calendar: Mapped["Calendar"] = relationship("Calendar", back_populates="events")
    creator: Mapped["User"] = relationship("User", back_populates="created_events")
    reminders: Mapped[List["Reminder"]] = relationship(
        "Reminder", back_populates="event", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, title='{self.title}', start_time={self.start_time})>"


class Reminder(Base):
    """Scheduled reminder triggered prior to or at the event start time."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    remind_before_minutes: Mapped[int] = mapped_column(Integer, default=0)
    remind_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="reminders")

    def __repr__(self) -> str:
        return f"<Reminder(id={self.id}, event_id={self.event_id}, remind_at={self.remind_at}, is_sent={self.is_sent})>"
