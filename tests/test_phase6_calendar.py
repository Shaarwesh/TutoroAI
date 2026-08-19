import os
import sys
from pathlib import Path

# Force unbuffered output so print statements flush immediately
sys.stdout.reconfigure(line_buffering=True)

print("\n" + "=" * 55)
print("🚀 TUTOR0 AI — Phase 6 Google Calendar Test")
print("=" * 55)

# Setup root path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
print(f"📁 Project root added: {PROJECT_ROOT}")

# Load .env
from dotenv import load_dotenv
env_path = PROJECT_ROOT / ".env"
load_dotenv(env_path)
print(f"🔑 Loaded .env from: {env_path}")

# Import calendar functions
print("📦 Importing calendar tool...")
try:
    from app.tools.calendar_tool import (
        get_available_slots,
        format_slots_message,
        create_calendar_event,
        cancel_calendar_event,
    )
    print("✅ Imports successful!")
except Exception as e:
    print(f"❌ Failed to import calendar tools: {e}")
    sys.exit(1)

# Step 1: Fetch slots
print("\n1️⃣  Fetching available slots from Google Calendar...")
try:
    slots = get_available_slots(days_ahead=7, max_slots=4)
    print(f"   Found {len(slots)} slot(s)\n")
    print(format_slots_message(slots))
except Exception as e:
    print(f"   ❌ Error checking slots: {e}")
    slots = []

if not slots:
    print("\n⚠️  No slots returned. Check your calendar ID and service account permissions.")
    sys.exit(0)

# Step 2: Book test slot
print("\n2️⃣  Creating test booking on Slot #1...")
chosen = slots[0]
event_id = None
try:
    event_id = create_calendar_event(
        student_name="Aina Farah",
        parent_name="Farah",
        phone="whatsapp:+60123456789",
        subjects="Mathematics, English",
        start=chosen["start"],
        end=chosen["end"],
    )
    print(f"   ✅ Event created! Google Event ID: {event_id}")
    print("   📅 Check your Google Calendar to see the booking.")
except Exception as e:
    print(f"   ❌ Error creating calendar event: {e}")

# Step 3: Cleanup / Cancel slot
if event_id:
    input("\n👉 Press Enter after verifying Google Calendar to delete the test event...")
    print("\n3️⃣  Cancelling test booking...")
    success = cancel_calendar_event(event_id)
    if success:
        print("   ✅ Event cancelled and cleaned up successfully.")
    else:
        print("   ❌ Failed to cancel event.")

print("\n" + "=" * 55)
print("🏁 Test execution finished.")
print("=" * 55 + "\n")