"""
Lead analytics — Quick Win
Computes simple business metrics: total leads, conversion rate, popular subjects.
"""
import logging
from collections import Counter
from sqlalchemy import select, func
from app.db.postgres import AsyncSessionLocal
from app.models.lead import Lead
from app.models.booking import Booking

logger = logging.getLogger(__name__)


async def get_analytics_summary() -> dict:
    """
    Returns a summary dict of key business metrics:
    - total_leads: all leads ever captured
    - leads_by_stage: breakdown by stage (new/qualified/confirmed/booked/cancelled)
    - total_bookings: confirmed bookings count
    - conversion_rate: % of leads that became a confirmed booking
    - popular_subjects: top subjects requested, ranked
    - recent_leads: last 5 leads with name + stage
    """
    async with AsyncSessionLocal() as db:
        # Total leads
        result = await db.execute(select(func.count(Lead.id)))
        total_leads = result.scalar() or 0

        # Leads by stage
        result = await db.execute(select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage))
        leads_by_stage = {stage: count for stage, count in result.all()}

        # Bookings by status
        total_bookings = await db.scalar(select(func.count(Booking.id)).where(Booking.status == "confirmed")) or 0
        cancelled_bookings = await db.scalar(select(func.count(Booking.id)).where(Booking.status == "cancelled")) or 0

        # Conversion = UNIQUE leads with at least one confirmed booking / all leads
        converted_leads = await db.scalar(
            select(func.count(func.distinct(Booking.lead_id))).where(Booking.status == "confirmed")
        ) or 0
        conversion_rate = round((converted_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

        # Seat occupancy across the timetable
        from app.models.schedule import ClassSchedule
        seats_total = await db.scalar(select(func.coalesce(func.sum(ClassSchedule.max_capacity), 0))) or 0
        seats_filled = await db.scalar(select(func.coalesce(func.sum(ClassSchedule.current_enrolled), 0))) or 0
        occupancy = round(seats_filled / seats_total * 100, 1) if seats_total else 0.0

        # Popular subjects — pull all non-null subjects strings and count occurrences
        result = await db.execute(select(Lead.subjects).where(Lead.subjects.isnot(None)))
        all_subjects_raw = result.scalars().all()
        subject_counter = Counter()
        for subj_str in all_subjects_raw:
            if subj_str:
                for s in subj_str.split(","):
                    subject_counter[s.strip()] += 1
        popular_subjects = [
            {"subject": subj, "count": count}
            for subj, count in subject_counter.most_common(10)
        ]

        # Recent leads
        result = await db.execute(
            select(Lead.name, Lead.stage, Lead.created_at)
            .order_by(Lead.created_at.desc())
            .limit(5)
        )
        recent_leads = [
            {"name": name or "Unknown", "stage": stage, "created_at": str(created_at)}
            for name, stage, created_at in result.all()
        ]

        return {
            "total_leads": total_leads,
            "leads_by_stage": leads_by_stage,
            "total_bookings": total_bookings,
            "cancelled_bookings": cancelled_bookings,
            "converted_leads": converted_leads,
            "conversion_rate_percent": conversion_rate,
            "occupancy_percent": occupancy,
            "seats_total": int(seats_total),
            "seats_filled": int(seats_filled),
            "popular_subjects": popular_subjects,
            "recent_leads": recent_leads,
        }
