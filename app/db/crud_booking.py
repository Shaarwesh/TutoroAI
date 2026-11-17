from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.booking import Booking
from app.models.lead import Lead
from datetime import datetime


async def create_booking(
    db: AsyncSession,
    phone: str,
    appointment_start: datetime,
    appointment_end: datetime,
    subjects: str = None,
    google_event_id: str = None,
    notes: str = None,
) -> Booking | None:
    """Create a booking — lead must exist first."""
    # Get lead_id from phone
    result = await db.execute(select(Lead).where(Lead.phone == phone))
    lead = result.scalar_one_or_none()
    if not lead:
        return None

    booking = Booking(
        lead_id=lead.id,
        phone=phone,
        appointment_start=appointment_start,
        appointment_end=appointment_end,
        subjects=subjects,
        google_event_id=google_event_id,
        notes=notes,
        status="confirmed",
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


async def get_bookings_by_phone(db: AsyncSession, phone: str) -> list[Booking]:
    """Get all bookings for a phone number."""
    result = await db.execute(
        select(Booking)
        .where(Booking.phone == phone)
        .order_by(Booking.appointment_start)
    )
    return result.scalars().all()


async def cancel_booking(db: AsyncSession, booking_id: int) -> Booking | None:
    """Cancel a booking by ID."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        return None
    booking.status = "cancelled"
    await db.commit()
    await db.refresh(booking)
    return booking
