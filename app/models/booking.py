from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.db.postgres import Base


class Booking(Base):
    __tablename__ = "bookings"

    id                  = Column(Integer, primary_key=True, index=True)
    lead_id             = Column(Integer, ForeignKey("leads.id"), nullable=False)
    phone               = Column(String(30), index=True, nullable=False)
    appointment_start   = Column(DateTime(timezone=True), nullable=False)
    appointment_end     = Column(DateTime(timezone=True), nullable=False)
    subjects            = Column(String(200))
    google_event_id     = Column(String(200))   # Calendar event ID for updates/cancellations
    status              = Column(String(30), default="confirmed")  # confirmed | cancelled
    notes               = Column(Text)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Booking {self.phone} | {self.appointment_start} | {self.status}>"
