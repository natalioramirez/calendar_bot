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

    # Whether to run the initial Islamic calendar sync on startup.
    # Disable it to avoid hitting the AlAdhan API every time the bot boots;
    # the monthly scheduled sync and the web panel button are unaffected.
    CALLS_ON_BOOT: bool = True

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

    @field_validator("ISLAMIC_ALLOWED_EVENTS", mode="after")
    @classmethod
    def parse_islamic_events(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


    # Web Admin Flask Panel Settings (the only administration interface)
    WEB_ADMIN_HOST: str = "127.0.0.1"
    WEB_ADMIN_PORT: int = 5314

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
