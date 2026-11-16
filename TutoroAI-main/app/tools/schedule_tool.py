from sqlalchemy import select
from app.db.postgres import AsyncSessionLocal
from app.models.schedule import ClassSchedule

async def get_database_schedule(subject_requested: str = None) -> str:
    """
    Tool for the AI to fetch available tuition classes directly from the PostgreSQL database.
    """
    async with AsyncSessionLocal() as db:
        query = select(ClassSchedule)
        
        # If the parent asks for a specific subject (like "Math"), filter the search
        if subject_requested:
            query = query.where(ClassSchedule.subject.ilike(f"%{subject_requested}%"))
            
        result = await db.execute(query)
        schedules = result.scalars().all()

    if not schedules:
        return "I couldn't find any classes matching that description in our current timetable."

    # Format the data cleanly so the AI can read it and formulate a natural response
    available_slots = []
    for c in schedules:
        if c.current_enrolled < c.max_capacity:
            available_slots.append(
                f"- {c.form_year} {c.subject} on {c.day_of_week}s from {c.start_time} to {c.end_time} (Class ID: {c.id})"
            )
    
    if not available_slots:
        return "Those classes are currently completely full. No seats are available."
        
    return "Here are the available classes from our database:\n" + "\n".join(available_slots)