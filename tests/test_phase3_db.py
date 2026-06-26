"""
Phase 3 test — run this to verify PostgreSQL CRUD works.
Usage: python tests/test_phase3_db.py
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
from app.db.postgres import AsyncSessionLocal, init_db
from app.db.crud_lead import upsert_lead, get_lead_by_phone, update_lead_stage
from app.db.crud_booking import create_booking, get_bookings_by_phone


async def test_db():
    print("\n🧪 Phase 3 — PostgreSQL CRUD Test\n" + "="*40)

    await init_db()

    async with AsyncSessionLocal() as db:

        # ── Test 1: Create / upsert a lead ──────────────────
        print("\n1️⃣  Creating lead...")
        lead = await upsert_lead(
            db,
            phone="whatsapp:+60123456789",
            name="Siti Aminah",
            language="ms",
            child_name="Adam",
            child_age=10,
            subjects="Math, Science",
            stage="qualified",
        )
        print(f"   ✅ Lead created: {lead.name} | stage: {lead.stage} | id: {lead.id}")

        # ── Test 2: Fetch lead by phone ──────────────────────
        print("\n2️⃣  Fetching lead by phone...")
        fetched = await get_lead_by_phone(db, "whatsapp:+60123456789")
        print(f"   ✅ Found: {fetched.name} | child: {fetched.child_name} | subjects: {fetched.subjects}")

        # ── Test 3: Update lead stage ────────────────────────
        print("\n3️⃣  Updating stage to 'booked'...")
        updated = await update_lead_stage(db, "whatsapp:+60123456789", "booked")
        print(f"   ✅ Stage updated: {updated.stage}")

        # ── Test 4: Create a booking ─────────────────────────
        print("\n4️⃣  Creating booking...")
        start = datetime.now(timezone.utc) + timedelta(days=2)
        end   = start + timedelta(hours=1)
        booking = await create_booking(
            db,
            phone="whatsapp:+60123456789",
            appointment_start=start,
            appointment_end=end,
            subjects="Math, Science",
            google_event_id="fake_event_id_123",
            notes="Trial class for Adam",
        )
        print(f"   ✅ Booking created: id={booking.id} | start={booking.appointment_start.strftime('%Y-%m-%d %H:%M')} UTC | status={booking.status}")

        # ── Test 5: Fetch bookings ───────────────────────────
        print("\n5️⃣  Fetching bookings for phone...")
        bookings = await get_bookings_by_phone(db, "whatsapp:+60123456789")
        print(f"   ✅ Found {len(bookings)} booking(s)")

    print("\n" + "="*40)
    print("✅ All Phase 3 tests passed! PostgreSQL CRUD is working.\n")


if __name__ == "__main__":
    asyncio.run(test_db())
