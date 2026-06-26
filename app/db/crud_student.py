from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.student import Student
from app.models.lead import Lead


async def add_student(db: AsyncSession, lead_id: int, name: str, form_year: str = None, subjects: str = None) -> Student:
    """Add a student (child) under a parent lead. Supports multiple students per lead."""
    student = Student(lead_id=lead_id, name=name, form_year=form_year, subjects=subjects)
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


async def get_students_by_phone(db: AsyncSession, phone: str) -> list[Student]:
    """Get all students (siblings) registered under a parent's phone number."""
    result = await db.execute(select(Lead).where(Lead.phone == phone))
    lead = result.scalar_one_or_none()
    if not lead:
        return []
    result = await db.execute(select(Student).where(Student.lead_id == lead.id))
    return result.scalars().all()
