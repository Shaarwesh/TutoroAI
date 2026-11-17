
"""Booking operations for TUTORO AI."""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.models.lead import Lead
from app.models.booking import Booking
from app.models.schedule import ClassSchedule
from app.tools.calendar_tool import (
    create_calendar_event,
    cancel_calendar_event,
    is_calendar_slot_available,
)


logger = logging.getLogger(__name__)
MYT = ZoneInfo("Asia/Kuala_Lumpur")

DAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def parse_class_time(value):
    if hasattr(value, "hour"):
        return value

    value = str(value).strip()

    for fmt in ("%I:%M %p", "%H:%M", "%I %p"):
        try:
            return datetime.strptime(
                value, fmt
            ).time()
        except ValueError:
            continue

    raise ValueError(
        f"Invalid timetable time: {value}"
    )


def next_class_datetime(schedule):
    day_name = str(
        schedule.day_of_week
    ).strip().lower()

    if day_name not in DAYS:
        raise ValueError(
            f"Invalid class day: {day_name}"
        )

    now = datetime.now(MYT)
    start_time = parse_class_time(
        schedule.start_time
    )
    end_time = parse_class_time(
        schedule.end_time
    )

    days_until = (
        DAYS[day_name] - now.weekday()
    ) % 7

    start_date = (
        now + timedelta(days=days_until)
    ).date()

    start = datetime.combine(
        start_date,
        start_time,
        tzinfo=MYT,
    )
    end = datetime.combine(
        start_date,
        end_time,
        tzinfo=MYT,
    )

    if end <= start:
        raise ValueError(
            "Class end time must be after start."
        )

    if start <= now:
        start += timedelta(days=7)
        end += timedelta(days=7)

    return start, end


async def create_trial_booking(
    phone: str,
    parent_name: str,
    student_name: str,
    class_id: int,
    subjects: str,
):
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )

    Session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    event_id = None

    try:
        async with Session() as db:
            async with db.begin():
                schedule = (
                    await db.execute(
                        select(ClassSchedule)
                        .where(
                            ClassSchedule.id == class_id
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()

                if not schedule:
                    raise ValueError(
                        "The selected class does not exist."
                    )

                if (
                    schedule.current_enrolled
                    >= schedule.max_capacity
                ):
                    raise ValueError(
                        "This class is already full."
                    )

                lead = (
                    await db.execute(
                        select(Lead).where(
                            Lead.phone == phone
                        )
                    )
                ).scalar_one_or_none()

                if not lead:
                    raise ValueError(
                        "Parent registration not found. "
                        "Please register before booking."
                    )

                start, end = next_class_datetime(
                    schedule
                )

                start_utc = start.astimezone(
                    timezone.utc
                )
                end_utc = end.astimezone(
                    timezone.utc
                )

                existing = (
                    await db.execute(
                        select(Booking).where(
                            Booking.phone == phone,
                            Booking.status == "confirmed",
                            Booking.appointment_start
                            == start_utc,
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    raise ValueError(
                        "This customer already has "
                        "a booking for this class time."
                    )

                if settings.google_calendar_id:  # calendar is optional (e.g. local demo)
                    available = await asyncio.to_thread(
                        is_calendar_slot_available,
                        start,
                        end,
                    )

                    if not available:
                        raise ValueError(
                            "The selected time is occupied "
                            "in Google Calendar."
                        )

                    event_id = await asyncio.to_thread(
                        create_calendar_event,
                        student_name,
                        parent_name,
                        phone,
                        subjects,
                        start,
                        end,
                    )

                booking = Booking(
                    lead_id=lead.id,
                    phone=phone,
                    appointment_start=start_utc,
                    appointment_end=end_utc,
                    subjects=subjects,
                    google_event_id=event_id,
                    status="confirmed",
                    notes=(
                        f"Class ID: {class_id}; "
                        f"Student: {student_name}"
                    ),
                )

                db.add(booking)
                lead.stage = "booked"
                schedule.current_enrolled += 1

                await db.flush()
                booking_id = booking.id

        return {
            "booking_id": booking_id,
            "class_id": class_id,
            "student_name": student_name,
            "subjects": subjects,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "google_event_id": event_id,
        }

    except Exception:
        if event_id:
            deleted = await asyncio.to_thread(
                cancel_calendar_event,
                event_id,
            )
            if not deleted:
                logger.error(
                    "Calendar event %s needs manual "
                    "cleanup after booking failure.",
                    event_id,
                )
        raise

    finally:
        await engine.dispose()


async def cancel_trial_booking(
    phone: str,
    booking_id: int,
):
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )

    Session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with Session() as db:
            async with db.begin():
                booking = (
                    await db.execute(
                        select(Booking)
                        .where(
                            Booking.id == booking_id,
                            Booking.phone == phone,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()

                if not booking:
                    raise ValueError(
                        "Booking not found for this customer."
                    )

                if booking.status != "confirmed":
                    raise ValueError(
                        "This booking is not active."
                    )

                if booking.google_event_id:
                    deleted = await asyncio.to_thread(
                        cancel_calendar_event,
                        booking.google_event_id,
                    )

                    if not deleted:
                        raise RuntimeError(
                            "Google Calendar cancellation "
                            "failed. Database booking "
                            "was not cancelled."
                        )

                # Release the seat (once): the class id is stored in the booking notes.
                match = re.search(r"Class ID:\s*(\d+)", booking.notes or "")
                if match:
                    schedule = (
                        await db.execute(
                            select(ClassSchedule)
                            .where(ClassSchedule.id == int(match.group(1)))
                            .with_for_update()
                        )
                    ).scalar_one_or_none()
                    if schedule and (schedule.current_enrolled or 0) > 0:
                        schedule.current_enrolled -= 1

                booking.status = "cancelled"

        return {
            "booking_id": booking_id,
            "status": "cancelled",
        }

    finally:
        await engine.dispose()


async def reschedule_trial_booking(
    phone: str,
    booking_id: int,
    new_class_id: int,
    parent_name: str,
    student_name: str,
):
    """Book the NEW class first; only then release the old seat."""
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            old = (
                await db.execute(
                    select(Booking).where(Booking.id == booking_id, Booking.phone == phone)
                )
            ).scalar_one_or_none()
        if not old or old.status != "confirmed":
            raise ValueError("No active booking with that ID was found for this customer.")
        subjects = old.subjects or "Not specified"
    finally:
        await engine.dispose()

    new = await create_trial_booking(
        phone=phone,
        parent_name=parent_name,
        student_name=student_name,
        class_id=new_class_id,
        subjects=subjects,
    )
    try:
        await cancel_trial_booking(phone=phone, booking_id=booking_id)
        new["old_booking_cancelled"] = True
    except Exception:
        logger.exception("Old booking %s could not be released after reschedule", booking_id)
        new["old_booking_cancelled"] = False
    return new
