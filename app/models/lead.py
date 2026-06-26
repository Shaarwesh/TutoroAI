from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.db.postgres import Base


class Lead(Base):
    __tablename__ = "leads"

    id          = Column(Integer, primary_key=True, index=True)
    phone       = Column(String(30), unique=True, index=True, nullable=False)
    name        = Column(String(100))           # parent name
    email       = Column(String(200))           # parent email
    address     = Column(Text)                  # home address
    language    = Column(String(10), default="en")
    child_name  = Column(String(100))
    child_age   = Column(Integer)
    subjects    = Column(String(200))           # comma-separated
    notes       = Column(Text)
    stage       = Column(String(50), default="new")  # new | qualified | booked | lost
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Lead {self.phone} | {self.name} | {self.stage}>"
