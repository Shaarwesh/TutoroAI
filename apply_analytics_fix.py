"""
Run from the repo root:  python apply_analytics_fix.py   (analytics.html must sit next to it)
Backups: analytics.py.bak, main.py.bak5.  Safe to re-run.
Fixes the numbers:
  - conversion = UNIQUE leads with a confirmed booking / all leads (was: bookings / leads, can exceed 100%)
  - adds cancelled bookings, converted leads, seat occupancy
  - /dashboard counts CONFIRMED bookings only (was: every status)
"""
from pathlib import Path
import shutil, sys

AN, MAIN, TPL = Path("app/tools/analytics.py"), Path("app/main.py"), Path("app/templates/analytics.html")
HERE = Path(__file__).parent
for p, ext in ((AN, ".bak"), (MAIN, ".bak5")):
    if not p.exists(): sys.exit(f"Run from the repo root (missing {p}).")
    b = p.with_suffix(p.suffix + ext)
    if not b.exists(): shutil.copy(p, b)

def sub(path, old, new, label, marker):
    s = path.read_text(encoding="utf-8")
    if marker in s: print(f"[skip] {label}"); return
    if s.count(old) != 1: sys.exit(f"[FAIL] {label}: found {s.count(old)} matches in {path}. Paste me that part.")
    path.write_text(s.replace(old, new), encoding="utf-8"); print(f"[ok]   {label}")

sub(AN,
'''        # Total bookings (status = confirmed)
        result = await db.execute(select(func.count(Booking.id)).where(Booking.status == "confirmed"))
        total_bookings = result.scalar() or 0

        # Conversion rate
        conversion_rate = round((total_bookings / total_leads * 100), 1) if total_leads > 0 else 0.0
''',
'''        # Bookings by status
        total_bookings = await db.scalar(select(func.count(Booking.id)).where(Booking.status == "confirmed")) or 0
        cancelled_bookings = await db.scalar(select(func.count(Booking.id)).where(Booking.status == "cancelled")) or 0

        # Conversion = UNIQUE leads with at least one confirmed booking / all leads
        converted_leads = await db.scalar(
            select(func.count(func.distinct(Booking.lead_id))).where(Booking.status == "confirmed")
        ) or 0
        conversion_rate = round((converted_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

        # Seat occupancy across the timetable
        from app.models.schedule import ClassSchedule
        seats_total = await db.scalar(select(func.coalesce(func.sum(ClassSchedule.max_capacity), 0))) or 0
        seats_filled = await db.scalar(select(func.coalesce(func.sum(ClassSchedule.current_enrolled), 0))) or 0
        occupancy = round(seats_filled / seats_total * 100, 1) if seats_total else 0.0
''', "analytics: unique conversion, cancellations, occupancy", "converted_leads = await")

sub(AN,
'''            "total_bookings": total_bookings,
            "conversion_rate_percent": conversion_rate,''',
'''            "total_bookings": total_bookings,
            "cancelled_bookings": cancelled_bookings,
            "converted_leads": converted_leads,
            "conversion_rate_percent": conversion_rate,
            "occupancy_percent": occupancy,
            "seats_total": int(seats_total),
            "seats_filled": int(seats_filled),''', "analytics: return new fields", '"cancelled_bookings": cancelled_bookings')

sub(MAIN,
'booking_count = await db.scalar(select(func.count(Booking.id))) or 0',
'booking_count = await db.scalar(select(func.count(Booking.id)).where(Booking.status == "confirmed")) or 0',
"dashboard counts confirmed bookings only", 'where(Booking.status == "confirmed")) or 0\n    return templates.TemplateResponse(\n        "dashboard.html"')

src = HERE / "analytics.html"
if not src.exists(): sys.exit("[FAIL] analytics.html must sit next to this script")
shutil.copy(src, TPL); print("[ok]   analytics.html updated")
print("\nDone. Restart uvicorn.")
