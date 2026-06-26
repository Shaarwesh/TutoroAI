"""
Reminder system — Phase 9 (Quick Win)
Checks for trial classes happening in ~24 hours and sends WhatsApp reminders.
Designed to be triggered by a scheduled job (e.g. Railway Cron, or called
periodically). Not triggered by the conversational agent directly.
"""
import logging
from datetime import datetime, timedelta, timezone
from twilio.rest import Client

from app.config import settings
from app.db.postgres import AsyncSessionLocal
from app.models.booking import Booking
from sqlalchemy import select

logger = logging.getLogger(__name__)

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


def _send_whatsapp(to_number: str, message: str) -> bool:
    try:
        client = _get_client()
        client.messages.create(
            from_=settings.twilio_whatsapp_number,
            to=to_number,
            body=message,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send reminder to {to_number}: {e}")
        return False


async def send_upcoming_reminders(hours_ahead: int = 24) -> dict:
    """
    Find all confirmed bookings happening within the next `hours_ahead` hours
    that haven't been reminded yet, and send a WhatsApp reminder for each.

    Returns a summary dict: {"checked": N, "sent": N, "failed": N}
    """
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=hours_ahead)
    window_start = now + timedelta(hours=hours_ahead - 2)  # ~2hr window to avoid double-sends if run hourly

    summary = {"checked": 0, "sent": 0, "failed": 0}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(
                Booking.status == "confirmed",
                Booking.appointment_start >= window_start,
                Booking.appointment_start <= window_end,
            )
        )
        bookings = result.scalars().all()
        summary["checked"] = len(bookings)

        for booking in bookings:
            slot_text = booking.notes or "your scheduled time"
            message = (
                f"📅 *Reminder: Trial Class Tomorrow!*\n\n"
                f"This is a friendly reminder about your trial class:\n"
                f"{slot_text}\n"
                f"Subjects: {booking.subjects}\n\n"
                f"See you soon! Reply if you need to reschedule. 😊"
            )
            success = _send_whatsapp(booking.phone, message)
            if success:
                summary["sent"] += 1
            else:
                summary["failed"] += 1

    logger.info(f"Reminder check complete: {summary}")
    return summary


if __name__ == "__main__":
    """Run manually: python -m app.tools.reminders"""
    import asyncio
    result = asyncio.run(send_upcoming_reminders())
    print(f"Reminder run complete: {result}")
