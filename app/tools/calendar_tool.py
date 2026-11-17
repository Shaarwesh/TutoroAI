
"""Google Calendar integration for TUTORO AI."""

import json
import logging
import os
from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import settings


logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kuala_Lumpur"
MYT = ZoneInfo(TIMEZONE)

SCOPES = [
    "https://www.googleapis.com/auth/calendar"
]

BUSINESS_HOURS = {
    0: (14, 18),
    1: (14, 18),
    2: (14, 18),
    3: (14, 18),
    4: (14, 18),
    5: (9, 13),
    6: None,
}

SLOT_DURATION_MINUTES = 60


@lru_cache(maxsize=1)
def get_calendar_service():
    if not settings.google_calendar_id:
        raise RuntimeError(
            "GOOGLE_CALENDAR_ID is not configured."
        )

    credentials_json = os.getenv(
        "GOOGLE_CREDENTIALS_JSON", ""
    )

    if credentials_json:
        credentials = (
            service_account.Credentials
            .from_service_account_info(
                json.loads(credentials_json),
                scopes=SCOPES,
            )
        )
    else:
        credentials = (
            service_account.Credentials
            .from_service_account_file(
                settings.google_service_account_file,
                scopes=SCOPES,
            )
        )

    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def get_busy_slots(start: datetime, end: datetime):
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError(
            "Calendar dates must include a timezone."
        )

    service = get_calendar_service()

    result = service.freebusy().query(
        body={
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": TIMEZONE,
            "items": [
                {"id": settings.google_calendar_id}
            ],
        }
    ).execute()

    calendar_data = result.get(
        "calendars", {}
    ).get(settings.google_calendar_id)

    if not calendar_data:
        raise RuntimeError(
            "Google Calendar returned no calendar data."
        )

    if calendar_data.get("errors"):
        raise RuntimeError(
            f"Calendar availability error: "
            f"{calendar_data['errors']}"
        )

    return calendar_data.get("busy", [])


def is_calendar_slot_available(
    start: datetime,
    end: datetime,
) -> bool:
    if end <= start:
        raise ValueError(
            "Booking end must be after start."
        )

    return len(get_busy_slots(start, end)) == 0


def get_available_slots(
    days_ahead: int = 7,
    max_slots: int = 4,
):
    now = datetime.now(MYT)
    range_end = now + timedelta(days=days_ahead)

    # Fail closed if Google Calendar is unavailable.
    busy_slots = get_busy_slots(now, range_end)

    def is_busy(slot_start, slot_end):
        for busy in busy_slots:
            busy_start = datetime.fromisoformat(
                busy["start"].replace("Z", "+00:00")
            )
            busy_end = datetime.fromisoformat(
                busy["end"].replace("Z", "+00:00")
            )

            if (
                slot_start < busy_end
                and slot_end > busy_start
            ):
                return True

        return False

    available = []
    day_cursor = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    while (
        len(available) < max_slots
        and day_cursor < range_end
    ):
        hours = BUSINESS_HOURS.get(
            day_cursor.weekday()
        )

        if hours:
            opening, closing = hours

            slot_start = day_cursor.replace(
                hour=opening,
            )
            day_close = day_cursor.replace(
                hour=closing,
            )

            while (
                slot_start
                + timedelta(
                    minutes=SLOT_DURATION_MINUTES
                )
                <= day_close
            ):
                slot_end = slot_start + timedelta(
                    minutes=SLOT_DURATION_MINUTES
                )

                if (
                    slot_start > now
                    and not is_busy(
                        slot_start, slot_end
                    )
                ):
                    available.append({
                        "label": (
                            slot_start.strftime(
                                "%A, %d %B %Y, %I:%M %p"
                            )
                        ),
                        "start": slot_start,
                        "end": slot_end,
                    })

                    if len(available) >= max_slots:
                        break

                slot_start = slot_end

        day_cursor += timedelta(days=1)

    return available


def format_slots_message(slots):
    if not slots:
        return (
            "Sorry, no available trial slots "
            "were found."
        )

    lines = ["Available trial slots:"]

    for index, slot in enumerate(slots, 1):
        lines.append(
            f"{index}. {slot['label']}"
        )

    return "\n".join(lines)


def create_calendar_event(
    student_name: str,
    parent_name: str,
    phone: str,
    subjects: str,
    start: datetime,
    end: datetime,
) -> str:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError(
            "Booking times must be timezone-aware."
        )

    if end <= start:
        raise ValueError(
            "Booking end must be after start."
        )

    service = get_calendar_service()

    event = {
        "summary": (
            f"Trial Class - {student_name}"
        ),
        "description": (
            f"Parent: {parent_name}\n"
            f"Student: {student_name}\n"
            f"Phone: {phone}\n"
            f"Subjects: {subjects}\n"
            "Booked via TUTORO AI"
        ),
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": TIMEZONE,
        },
    }

    created = service.events().insert(
        calendarId=settings.google_calendar_id,
        body=event,
    ).execute()

    return created["id"]


def cancel_calendar_event(
    event_id: str,
) -> bool:
    if not event_id:
        return False

    try:
        service = get_calendar_service()

        service.events().delete(
            calendarId=settings.google_calendar_id,
            eventId=event_id,
        ).execute()

        return True

    except Exception:
        logger.exception(
            "Could not delete Calendar event %s",
            event_id,
        )
        return False
