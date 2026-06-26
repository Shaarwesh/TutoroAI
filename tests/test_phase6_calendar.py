"""
Phase 6 test — Google Calendar integration. NO Groq calls here.
Usage: python tests/test_phase6_calendar.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import timedelta
from app.tools.calendar_tool import (
    get_available_slots,
    format_slots_message,
    create_calendar_event,
    cancel_calendar_event,
)


def test_calendar():
    print("\n🧪 Phase 6 — Google Calendar Test\n" + "="*40)

    print("\n1️⃣  Fetching available slots...")
    slots = get_available_slots(days_ahead=7, max_slots=4)
    print(f"   Found {len(slots)} slot(s)")
    print("\n" + format_slots_message(slots))

    if not slots:
        print("\n⚠️  No slots found — check calendar permissions/sharing settings.")
        return

    print("\n2️⃣  Creating a test booking on slot #1...")
    chosen = slots[0]
    event_id = create_calendar_event(
        student_name="Test Student",
        parent_name="Test Parent",
        phone="whatsapp:+60100000000",
        subjects="English, Mathematics",
        start=chosen["start"],
        end=chosen["end"],
    )
    print(f"   ✅ Event created! ID: {event_id}")
    print(f"   📅 Check your Google Calendar — you should see 'Trial Class — Test Student (Test Parent)'")

    input("\n   Press Enter once you've verified the event appears in Google Calendar...")

    print("\n3️⃣  Cancelling the test booking...")
    success = cancel_calendar_event(event_id)
    print(f"   {'✅ Cancelled successfully' if success else '❌ Cancel failed'}")

    print("\n" + "="*40)
    print("✅ Phase 6 test complete!\n")


if __name__ == "__main__":
    test_calendar()
