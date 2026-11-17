"""
Minimal test — picks up where we left off: customer already confirmed,
slots already shown, just needs to pick a slot number.
Uses a FRESH phone number with pre-seeded chat history (no new registration needed).
Usage: python tests/test_booking_only.py
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.sales_agent import run_agent

PHONE = "whatsapp:+60177001100"

# Pre-seed history as if registration + confirm already happened
PRESEEDED_HISTORY = [
    {"role": "user", "content": "CONFIRM"},
    {"role": "assistant", "content": (
        "Saved! Here are the available trial slots:\n\n"
        "1. Wednesday, 02:00 PM – 3:00 PM\n"
        "2. Wednesday, 03:00 PM – 4:00 PM\n"
        "3. Wednesday, 04:00 PM – 5:00 PM\n"
        "4. Wednesday, 05:00 PM – 6:00 PM\n\n"
        "Reply with the number to book your slot."
    )},
]


async def main():
    print("\n🧪 MINIMAL BOOKING TEST — 1 message only\n" + "="*40)

    # First, seed the lead in DB so book_trial has something to update
    from app.db.postgres import AsyncSessionLocal
    from app.db.crud_lead import upsert_lead
    async with AsyncSessionLocal() as db:
        await upsert_lead(
            db, phone=PHONE,
            name="TestParent", child_name="TestChild",
            child_age=2, subjects="English, Mathematics",
            email="test@example.com", stage="confirmed",
        )
    print("✅ Lead pre-seeded in DB\n")

    print(f"👤 User: 1")
    reply = await run_agent(PHONE, "1", PRESEEDED_HISTORY)
    print(f"🤖 tutoro: {reply}")

    print("\n" + "="*40)
    print("✅ Test done — check above for real booking confirmation")
    print("   Check your Google Calendar for the new event!")


if __name__ == "__main__":
    asyncio.run(main())
