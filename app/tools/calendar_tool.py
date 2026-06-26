"""
Google Calendar integration — Phase 6
Handles checking availability and creating trial class booking events.
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
import logging

# Load the JSON string from the environment variable
google_creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")

if google_creds_json:
    # Convert the string back into a dictionary
    creds_dict = json.loads(google_creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict)
else:
    # Fallback for local testing if the variable isn't set
    creds = service_account.Credentials.from_service_account_file('app/credentials/google_service_account.json')

from app.config import settings

# Load the JSON string from the environment variable
google_creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")

if google_creds_json:
    # Convert the string back into a dictionary
    creds_dict = json.loads(google_creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict)
else:
    # Fallback for local testing if the variable isn't set
    creds = service_account.Credentials.from_service_account_file('app/credentials/google_service_account.json')
    
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Business hours for trial classes
BUSINESS_HOURS = {
    0: (14, 18),  # Monday    2pm-6pm
    1: (14, 18),  # Tuesday
    2: (14, 18),  # Wednesday
    3: (14, 18),  # Thursday
    4: (14, 18),  # Friday
    5: (9, 13),   # Saturday  9am-1pm
    6: None,      # Sunday — closed
}

SLOT_DURATION_MINUTES = 60
TIMEZONE = "Asia/Kuala_Lumpur"

_service = None  # singleton


def get_calendar_service():
    """Build and cache the Google Calendar API service client."""
    global _service
    if _service is not None:
        return _service

    credentials = service_account.Credentials.from_service_account_file(
        settings.google_service_account_file,
        scopes=SCOPES,
    )
    _service = build("calendar", "v3", credentials=credentials)
    return _service


def get_busy_slots(start: datetime, end: datetime) -> list[dict]:
    """Query Google Calendar's freebusy API for existing events in a range."""
    service = get_calendar_service()
    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "timeZone": TIMEZONE,
        "items": [{"id": settings.google_calendar_id}],
    }
    result = service.freebusy().query(body=body).execute()
    busy = result["calendars"][settings.google_calendar_id]["busy"]
    return busy


def get_available_slots(days_ahead: int = 7, max_slots: int = 4) -> list[dict]:
    """
    Generate available 1-hour trial slots within business hours,
    excluding any time already booked on the calendar.
    Returns a list of dicts: {"label": str, "start": datetime, "end": datetime}
    """
    now = datetime.now(timezone.utc)
    range_end = now + timedelta(days=days_ahead)

    try:
        busy_slots = get_busy_slots(now, range_end)
    except Exception as e:
        logger.error(f"Calendar fetch error: {e}")
        busy_slots = []

    def is_busy(slot_start, slot_end):
        for b in busy_slots:
            b_start = datetime.fromisoformat(b["start"].replace("Z", "+00:00"))
            b_end = datetime.fromisoformat(b["end"].replace("Z", "+00:00"))
            if slot_start < b_end and slot_end > b_start:
                return True
        return False

    available = []
    day_cursor = now

    while len(available) < max_slots and day_cursor < range_end:
        weekday = day_cursor.weekday()
        hours = BUSINESS_HOURS.get(weekday)

        if hours:
            open_hour, close_hour = hours
            slot_start = day_cursor.replace(hour=open_hour, minute=0, second=0, microsecond=0)
            day_close = day_cursor.replace(hour=close_hour, minute=0, second=0, microsecond=0)

            while slot_start + timedelta(minutes=SLOT_DURATION_MINUTES) <= day_close:
                slot_end = slot_start + timedelta(minutes=SLOT_DURATION_MINUTES)
                if slot_start > now and not is_busy(slot_start, slot_end):
                    available.append({
                        "label": slot_start.strftime("%A, %I:%M %p").lstrip("0") + " – " + slot_end.strftime("%I:%M %p").lstrip("0"),
                        "start": slot_start,
                        "end": slot_end,
                    })
                    if len(available) >= max_slots:
                        break
                slot_start += timedelta(minutes=SLOT_DURATION_MINUTES)

        day_cursor = (day_cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    return available


def format_slots_message(slots: list[dict]) -> str:
    """Format slots into a WhatsApp-friendly numbered list."""
    if not slots:
        return "Sorry, no trial slots available in the next 7 days. Please check back soon!"
    lines = ["Available trial slots:\n"]
    for i, slot in enumerate(slots, 1):
        lines.append(f"{i}. {slot['label']}")
    lines.append("\nReply with the number to book your slot.")
    return "\n".join(lines)


def create_calendar_event(
    student_name: str,
    parent_name: str,
    phone: str,
    subjects: str,
    start: datetime,
    end: datetime,
) -> str:
    """
    Create a calendar event for the trial class.
    Returns the Google Calendar event ID.
    """
    service = get_calendar_service()
    event = {
        "summary": f"Trial Class — {student_name} ({parent_name})",
        "description": (
            f"Parent: {parent_name}\n"
            f"Student: {student_name}\n"
            f"Phone: {phone}\n"
            f"Subjects: {subjects}\n"
            f"Booked via EduBot WhatsApp"
        ),
        "start": {"dateTime": start.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": TIMEZONE},
    }
    created = service.events().insert(
        calendarId=settings.google_calendar_id,
        body=event,
    ).execute()
    return created["id"]


def cancel_calendar_event(event_id: str) -> bool:
    """Cancel/delete a calendar event by ID."""
    try:
        service = get_calendar_service()
        service.events().delete(
            calendarId=settings.google_calendar_id,
            eventId=event_id,
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to cancel event {event_id}: {e}")
        return False
