from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.db.postgres import Base


class Waitlist(Base):
    """
    Customers who want to be notified when a trial slot opens up,
    because none were available when they tried to book.
    """
    __tablename__ = "waitlist"

    id              = Column(Integer, primary_key=True, index=True)
    phone           = Column(String(30), index=True, nullable=False)
    parent_name     = Column(String(100))
    student_name    = Column(String(100))
    subjects        = Column(String(200))
    preferred_day   = Column(String(50))   # optional preference, e.g. "Saturday"
    notified        = Column(Boolean, default=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Waitlist {self.phone} | {self.parent_name} | notified={self.notified}>"
