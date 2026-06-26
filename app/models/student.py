from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.postgres import Base


class Student(Base):
    """
    A student belongs to a parent (Lead). Supports siblings —
    one parent can have multiple Student records.
    """
    __tablename__ = "students"

    id          = Column(Integer, primary_key=True, index=True)
    lead_id     = Column(Integer, ForeignKey("leads.id"), nullable=False)
    name        = Column(String(100), nullable=False)
    form_year   = Column(String(20))   # e.g. "Form 2", "Year 5" — stored as text, not int
    subjects    = Column(String(200))  # comma-separated subjects for THIS student
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Student {self.name} | {self.form_year}>"
