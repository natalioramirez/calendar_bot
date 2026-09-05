"""Google Calendar API integration service."""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from bot.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarService:
    """Service to interact with Google Calendar API v3."""

    def __init__(self, service_account_file: Optional[str] = None):
        self.service_account_file = (
            service_account_file or settings.GOOGLE_SERVICE_ACCOUNT_FILE
        )
        self._service = None

    def is_configured(self) -> bool:
        """Check if Google service account credentials file exists."""
        return bool(self.service_account_file and os.path.exists(self.service_account_file))

    def _get_service(self):
        """Build and cache Google Calendar API client."""
        if not self.is_configured():
            return None

        if self._service is None:
            try:
                creds = service_account.Credentials.from_service_account_file(
                    self.service_account_file, scopes=SCOPES
                )
                self._service = build("calendar", "v3", credentials=creds)
            except Exception as ex:
                logger.error(f"Error initializing Google Calendar client: {ex}")
                return None
        return self._service

    def create_event(
        self,
        calendar_id: str,
        title: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        notes: Optional[str] = None,
        is_all_day: bool = False,
    ) -> Optional[str]:
        """Create an event on Google Calendar and return its Google Event ID."""
        service = self._get_service()
        if not service:
            logger.info("Google Calendar is not configured. Skipping Google sync.")
            return None

        if end_time is None:
            end_time = start_time + timedelta(hours=1)

        try:
            if is_all_day:
                start_body = {"date": start_time.strftime("%Y-%m-%d")}
                end_body = {"date": end_time.strftime("%Y-%m-%d")}
            else:
                start_body = {"dateTime": start_time.isoformat() + "Z", "timeZone": "UTC"}
                end_body = {"dateTime": end_time.isoformat() + "Z", "timeZone": "UTC"}

            event_body = {
                "summary": title,
                "description": notes or "",
                "start": start_body,
                "end": end_body,
            }

            created = (
                service.events()
                .insert(calendarId=calendar_id, body=event_body)
                .execute()
            )
            event_id = created.get("id")
            logger.info(f"Created Google Calendar event: {event_id}")
            return event_id
        except HttpError as err:
            logger.error(f"Google Calendar API HTTP error: {err}")
            return None
        except Exception as ex:
            logger.error(f"Unexpected error creating Google Calendar event: {ex}")
            return None

    def update_event(
        self,
        calendar_id: str,
        google_event_id: str,
        title: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Update an existing event in Google Calendar."""
        service = self._get_service()
        if not service or not google_event_id:
            return False

        try:
            event = service.events().get(calendarId=calendar_id, eventId=google_event_id).execute()
            event["summary"] = title
            if notes is not None:
                event["description"] = notes
            service.events().update(calendarId=calendar_id, eventId=google_event_id, body=event).execute()
            return True
        except Exception as ex:
            logger.error(f"Error updating Google Calendar event {google_event_id}: {ex}")
            return False

    def delete_event(self, calendar_id: str, google_event_id: str) -> bool:
        """Delete an event from Google Calendar."""
        service = self._get_service()
        if not service or not google_event_id:
            return False

        try:
            service.events().delete(calendarId=calendar_id, eventId=google_event_id).execute()
            logger.info(f"Deleted Google Calendar event: {google_event_id}")
            return True
        except Exception as ex:
            logger.error(f"Error deleting Google Calendar event {google_event_id}: {ex}")
            return False


# Global instance
google_calendar_service = GoogleCalendarService()

