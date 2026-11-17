"""
Seed the timetable so the bot has real classes to offer in the demo.
Run from the repo root (after DATABASE_URL in .env points at a live database):
    python seed_demo.py
Only inserts if the class_schedules table is empty, so it is safe to run twice.
"""
import asyncio
from sqlalchemy import select, func
from app.db.postgres import init_db, AsyncSessionLocal
from app.models.schedule import ClassSchedule

# (form_year, subject, day, start, end)
CLASSES = [
    ("Form 1", "Mathematics",   "Tuesday",   "2:00 PM",  "3:00 PM"),
    ("Form 1", "Bahasa Melayu", "Friday",    "4:00 PM",  "5:00 PM"),
    ("Form 1", "English",       "Thursday",  "3:00 PM",  "4:00 PM"),
    ("Form 2", "Mathematics",   "Monday",    "2:00 PM",  "3:00 PM"),
    ("Form 2", "English",       "Wednesday", "3:00 PM",  "4:00 PM"),
    ("Form 2", "Mathematics",   "Saturday",  "9:00 AM",  "10:00 AM"),
    ("Form 2", "Bahasa Melayu", "Friday",    "2:00 PM",  "3:00 PM"),
    ("Form 3", "History",       "Wednesday", "4:00 PM",  "5:00 PM"),
    ("Form 3", "Geography",     "Thursday",  "4:00 PM",  "5:00 PM"),
    ("Form 3", "Mathematics",   "Saturday",  "10:00 AM", "11:00 AM"),
    ("Form 4", "RBT",           "Saturday",  "11:00 AM", "12:00 PM"),
    ("Standard 5", "Mathematics", "Monday",  "3:00 PM",  "4:00 PM"),
    ("Standard 5", "English",   "Tuesday",   "4:00 PM",  "5:00 PM"),
    ("Standard 6", "Bahasa Melayu", "Thursday", "2:00 PM", "3:00 PM"),
]


async def main():
    await init_db()
    async with AsyncSessionLocal() as db:
        n = await db.scalar(select(func.count(ClassSchedule.id))) or 0
        if n:
            print(f"Timetable already has {n} classes, nothing to do.")
            return
        for form, subj, day, s, e in CLASSES:
            db.add(ClassSchedule(form_year=form, subject=subj, day_of_week=day,
                                 start_time=s, end_time=e, max_capacity=10, current_enrolled=0))
        await db.commit()
        print(f"Seeded {len(CLASSES)} classes.")


if __name__ == "__main__":
    asyncio.run(main())
