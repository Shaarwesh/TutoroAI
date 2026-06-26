from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.lead import Lead
from datetime import datetime, timezone


async def get_lead_by_phone(db: AsyncSession, phone: str) -> Lead | None:
    """Fetch a lead by phone number."""
    result = await db.execute(select(Lead).where(Lead.phone == phone))
    return result.scalar_one_or_none()


async def create_lead(db: AsyncSession, phone: str, **kwargs) -> Lead:
    """Create a new lead."""
    lead = Lead(phone=phone, **kwargs)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


async def update_lead(db: AsyncSession, phone: str, **kwargs) -> Lead | None:
    """Update an existing lead's fields."""
    lead = await get_lead_by_phone(db, phone)
    if not lead:
        return None
    for key, value in kwargs.items():
        if hasattr(lead, key) and value is not None:
            setattr(lead, key, value)
    lead.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(lead)
    return lead


async def upsert_lead(db: AsyncSession, phone: str, **kwargs) -> Lead:
    """Create lead if not exists, otherwise update."""
    lead = await get_lead_by_phone(db, phone)
    if lead:
        return await update_lead(db, phone, **kwargs)
    return await create_lead(db, phone, **kwargs)


async def update_lead_stage(db: AsyncSession, phone: str, stage: str) -> Lead | None:
    """Shortcut to update just the lead stage."""
    return await update_lead(db, phone, stage=stage)
