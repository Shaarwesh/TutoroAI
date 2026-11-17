
"""Free local booking reminder system."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db.postgres import AsyncSessionLocal
from app.models.booking import Booking


logger = logging.getLogger(__name__)

MYT = ZoneInfo("Asia/Kuala_Lumpur")

DATA_DIR = Path("data")
REMINDER_FILE = DATA_DIR / "local_reminders.json"
STATE_FILE = DATA_DIR / "reminder_state.json"


def load_json(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        logger.exception(
            "Could not read %s", path
        )
        raise


def save_json(path, data):
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary.replace(path)


async def send_upcoming_reminders(
    hours_ahead: int = 24,
):
    """
    Create local reminders for confirmed
    bookings happening within the next
    specified number of hours.
    """
    now = datetime.now(timezone.utc)
    end = now + timedelta(
        hours=hours_ahead
    )

    summary = {
        "checked": 0,
        "created": 0,
        "skipped": 0,
    }

    state = load_json(
        STATE_FILE, {}
    )
    reminders = load_json(
        REMINDER_FILE, []
    )

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(
                Booking.status == "confirmed",
                Booking.appointment_start > now,
                Booking.appointment_start <= end,
            )
        )

        bookings = result.scalars().all()
        summary["checked"] = len(bookings)

        for booking in bookings:
            key = (
                f"{booking.id}:"
                f"{booking.appointment_start.isoformat()}"
            )

            if key in state:
                summary["skipped"] += 1
                continue

            local_start = (
                booking.appointment_start
                .replace(tzinfo=timezone.utc)
                if booking.appointment_start.tzinfo is None
                else booking.appointment_start
            ).astimezone(MYT)

            message = (
                "Trial Class Reminder\n"
                f"Booking ID: {booking.id}\n"
                f"Date: {local_start:%d %B %Y}\n"
                f"Time: {local_start:%I:%M %p}\n"
                f"Subjects: {booking.subjects}\n"
                f"Phone: {booking.phone}"
            )

            reminders.append({
                "booking_id": booking.id,
                "phone": booking.phone,
                "appointment": (
                    booking.appointment_start
                    .isoformat()
                ),
                "message": message,
                "created_at": now.isoformat(),
                "delivery": "local_only",
            })

            state[key] = now.isoformat()
            summary["created"] += 1

    # Write reminder output before recording
    # completion, so failures can be retried.
    save_json(REMINDER_FILE, reminders)
    save_json(STATE_FILE, state)

    logger.info(
        "Reminder summary: %s", summary
    )
    return summary


if __name__ == "__main__":
    result = asyncio.run(
        send_upcoming_reminders()
    )
    print(result)
