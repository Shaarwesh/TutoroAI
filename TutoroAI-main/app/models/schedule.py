from sqlalchemy import Column, Integer, String, Time
from app.db.postgres import Base

class ClassSchedule(Base):
    __tablename__ = "class_schedules"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    form_year = Column(String, nullable=False)
    day_of_week = Column(String, nullable=False)
    start_time = Column(String, nullable=False) # Storing as string like "10:00 AM" for simplicity right now
    end_time = Column(String, nullable=False)
    max_capacity = Column(Integer, default=15)
    current_enrolled = Column(Integer, default=0)