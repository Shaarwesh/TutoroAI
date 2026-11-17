"""
Quick utility to cancel a specific calendar event by ID.
Usage: python tests/cancel_event.py <event_id>
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tools.calendar_tool import cancel_calendar_event

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/cancel_event.py <event_id>")
        sys.exit(1)
    event_id = sys.argv[1]
    success = cancel_calendar_event(event_id)
    print("✅ Cancelled" if success else "❌ Failed")
