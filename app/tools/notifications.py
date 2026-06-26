"""
Admin notifications — sends WhatsApp alerts to the tuition centre owner
when key events happen (new booking, cancellation, etc.)
Uses Twilio's REST API directly (separate from the inbound webhook flow).
"""
import logging
from twilio.rest import Client
from app.config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


def notify_admin(message: str) -> bool:
    """
    Send a WhatsApp message to the admin/business owner number.
    Returns True if sent successfully, False otherwise (never raises —
    notification failures should never break the main booking flow).
    """
    admin_number = getattr(settings, "admin_whatsapp_number", None)
    if not admin_number:
        logger.warning("ADMIN_WHATSAPP_NUMBER not configured — skipping admin notification")
        return False

    try:
        client = _get_client()
        client.messages.create(
            from_=settings.twilio_whatsapp_number,
            to=admin_number,
            body=message,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")
        return False


def notify_new_booking(parent_name: str, student_name: str, phone: str, subjects: str, slot_label: str) -> None:
    """Notify admin when a new trial class is booked."""
    message = (
        f"🎉 *New Trial Booking!*\n\n"
        f"Parent: {parent_name}\n"
        f"Student: {student_name}\n"
        f"Phone: {phone}\n"
        f"Subjects: {subjects}\n"
        f"Slot: {slot_label}\n\n"
        f"Booked via EduBot WhatsApp"
    )
    notify_admin(message)


def notify_cancellation(parent_name: str, student_name: str, phone: str, slot_label: str) -> None:
    """Notify admin when a booking is cancelled."""
    message = (
        f"⚠️ *Booking Cancelled*\n\n"
        f"Parent: {parent_name}\n"
        f"Student: {student_name}\n"
        f"Phone: {phone}\n"
        f"Was scheduled: {slot_label}\n\n"
        f"Cancelled via EduBot WhatsApp"
    )
    notify_admin(message)
