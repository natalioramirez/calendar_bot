"""Configuration module using pydantic-settings."""

from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot application settings."""

    # Telegram Bot Token from @BotFather
    BOT_TOKEN: str = ""

    # Database settings
    # Default to a local SQLite database file in the project root
    DATABASE_URL: str = "sqlite+aiosqlite:///tg_calendar.db"

    # Reminder polling interval in seconds
    REMINDER_CHECK_INTERVAL_SECONDS: int = 30

    # Admin user IDs (Telegram) who can run admin commands
    ADMIN_USER_IDS: Union[List[int], str] = []

    # Allowed Islamic calendar events/keywords to sync into calendar 'P'
    ISLAMIC_ALLOWED_EVENTS: Union[List[str], str] = [
        "Miraj",
        "Isra",
        "Baraat",
        "Bara'ah",
        "Shab-e-Barat",
        "Ramadan",
        "Qadr",
        "Fitr",
        "Quds",
        "Hajj",
        "Arafa",
        "Adha",
        "Ghadir",
        "New Year",
        "Año Nuevo",
        "Ashura",
        "Arbaeen",
        "Arba'in",
        "Mawlid",
        "Mubahala",
    ]

    @field_validator("ADMIN_USER_IDS", mode="after")
    @classmethod
    def parse_admin_ids(cls, v: Union[List[int], str]) -> List[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        return v

    @field_validator("ISLAMIC_ALLOWED_EVENTS", mode="after")
    @classmethod
    def parse_islamic_events(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


    # Web Admin Flask Panel Settings
    WEB_ADMIN_HOST: str = "127.0.0.1"
    WEB_ADMIN_PORT: int = 8088

    # Google Calendar Settings (optional)
    GOOGLE_SERVICE_ACCOUNT_FILE: str = ""
    GOOGLE_CALENDAR_ID: str = ""

    # Path settings
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
