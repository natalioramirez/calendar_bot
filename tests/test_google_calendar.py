"""Unit tests for Google Calendar service integration."""

from datetime import datetime
from unittest.mock import MagicMock
from bot.services.google_calendar import GoogleCalendarService


def test_google_calendar_unconfigured():
    """Verify service gracefully ignores Google sync when credentials are not configured."""
    service = GoogleCalendarService(service_account_file="non_existent_creds.json")
    assert service.is_configured() is False

    # Should safely return None / False without raising exceptions
    event_id = service.create_event(
        calendar_id="team_cal_123",
        title="Test Event",
        start_time=datetime(2026, 8, 25, 10, 0),
    )
    assert event_id is None

    updated = service.update_event("team_cal_123", "g_event_1", "Updated Title")
    assert updated is False

    deleted = service.delete_event("team_cal_123", "g_event_1")
    assert deleted is False


def test_google_calendar_mock_create(monkeypatch):
    """Verify event payload structure when calling Google Calendar API."""
    service = GoogleCalendarService()
    monkeypatch.setattr(service, "is_configured", lambda: True)

    mock_service_obj = MagicMock()
    mock_events = MagicMock()
    mock_insert = MagicMock()
    mock_insert.execute.return_value = {"id": "google_event_id_999"}
    mock_events.insert.return_value = mock_insert
    mock_service_obj.events.return_value = mock_events

    monkeypatch.setattr(service, "_get_service", lambda: mock_service_obj)

    start_dt = datetime(2026, 8, 25, 14, 0, 0)
    event_id = service.create_event(
        calendar_id="primary",
        title="Quarterly Review",
        start_time=start_dt,
        notes="Review roadmap & KPIs",
    )

    assert event_id == "google_event_id_999"
    mock_events.insert.assert_called_once()
    call_kwargs = mock_events.insert.call_args[1]
    assert call_kwargs["calendarId"] == "primary"
    assert call_kwargs["body"]["summary"] == "Quarterly Review"
    assert "Review roadmap" in call_kwargs["body"]["description"]

