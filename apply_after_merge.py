"""
Run from the repo root of the MERGED repo:  python apply_after_merge.py
(timetable.html, student_detail.html, analytics.html must sit next to this script.)
Backups: *.bak_am next to each edited file.  Safe to re-run.

Fixes the things that are still broken after the calendar merge:
  1. Cancelling a booking never released the class seat           -> now releases it (once)
  2. reschedule_booking was a stub                                 -> real: books the NEW class first, then releases the old one
  3. Booking failed outright when Google Calendar isn't configured -> calendar is optional (demo-friendly)
  4. Timetable page was a placeholder                              -> weekly grid with live seat bars
  5. Student rows weren't clickable                                -> /students/<id> profile with bookings + cancel button
  6. Dashboard/analytics numbers                                   -> confirmed bookings only; conversion = unique converted leads
"""
from pathlib import Path
import re, shutil, sys

HERE = Path(__file__).parent
BS, AGENT, MAIN, AN = (Path(p) for p in ("app/tools/booking_service.py", "app/agents/sales_agent.py", "app/main.py", "app/tools/analytics.py"))
TPL = Path("app/templates")
for p in (BS, AGENT, MAIN, AN):
    if not p.exists(): sys.exit(f"Run from the repo root (missing {p}).")
    b = p.with_suffix(p.suffix + ".bak_am")
    if not b.exists(): shutil.copy(p, b)

def sub(path, old, new, label, marker):
    s = path.read_text(encoding="utf-8")
    if marker in s: print(f"[skip] {label}"); return
    if s.count(old) != 1: sys.exit(f"[FAIL] {label}: found {s.count(old)} matches in {path}. Paste me that part of the file.")
    path.write_text(s.replace(old, new), encoding="utf-8"); print(f"[ok]   {label}")

# ------------------------------------------------------------------ 1. booking_service.py
sub(BS, "import asyncio\nimport logging\n", "import asyncio\nimport logging\nimport re\n", "booking_service: import re", "import re\n")

sub(BS,
'''                booking.status = "cancelled"

        return {
            "booking_id": booking_id,
            "status": "cancelled",
        }''',
'''                # Release the seat (once): the class id is stored in the booking notes.
                match = re.search(r"Class ID:\\s*(\\d+)", booking.notes or "")
                if match:
                    schedule = (
                        await db.execute(
                            select(ClassSchedule)
                            .where(ClassSchedule.id == int(match.group(1)))
                            .with_for_update()
                        )
                    ).scalar_one_or_none()
                    if schedule and (schedule.current_enrolled or 0) > 0:
                        schedule.current_enrolled -= 1

                booking.status = "cancelled"

        return {
            "booking_id": booking_id,
            "status": "cancelled",
        }''', "cancel releases the seat", "Release the seat (once)")

# calendar is optional: skip availability check + event creation when GOOGLE_CALENDAR_ID is empty
s = BS.read_text(encoding="utf-8")
if "if settings.google_calendar_id:" in s: print("[skip] calendar optional")
else:
    a = s.index("                available = await asyncio.to_thread(")
    b = s.index("                booking = Booking(")
    block = s[a:b].rstrip("\n")
    indented = "\n".join(("    " + l if l.strip() else l) for l in block.split("\n"))
    new = "                if settings.google_calendar_id:  # calendar is optional (e.g. local demo)\n" + indented + "\n\n"
    BS.write_text(s[:a] + new + s[b:], encoding="utf-8"); print("[ok]   calendar is optional")

RESCHED = '''

async def reschedule_trial_booking(
    phone: str,
    booking_id: int,
    new_class_id: int,
    parent_name: str,
    student_name: str,
):
    """Book the NEW class first; only then release the old seat."""
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            old = (
                await db.execute(
                    select(Booking).where(Booking.id == booking_id, Booking.phone == phone)
                )
            ).scalar_one_or_none()
        if not old or old.status != "confirmed":
            raise ValueError("No active booking with that ID was found for this customer.")
        subjects = old.subjects or "Not specified"
    finally:
        await engine.dispose()

    new = await create_trial_booking(
        phone=phone,
        parent_name=parent_name,
        student_name=student_name,
        class_id=new_class_id,
        subjects=subjects,
    )
    try:
        await cancel_trial_booking(phone=phone, booking_id=booking_id)
        new["old_booking_cancelled"] = True
    except Exception:
        logger.exception("Old booking %s could not be released after reschedule", booking_id)
        new["old_booking_cancelled"] = False
    return new
'''
s = BS.read_text(encoding="utf-8")
if "async def reschedule_trial_booking" in s: print("[skip] reschedule service")
else: BS.write_text(s.rstrip("\n") + "\n" + RESCHED, encoding="utf-8"); print("[ok]   reschedule_trial_booking service")

# ------------------------------------------------------------------ 2. sales_agent.py
sub(AGENT, "from app.tools.booking_service import (\n    create_trial_booking,\n    cancel_trial_booking,\n)",
    "from app.tools.booking_service import (\n    create_trial_booking,\n    cancel_trial_booking,\n    reschedule_trial_booking,\n)",
    "agent imports reschedule service", "reschedule_trial_booking,\n)")

NEW_RESCHED = '''def reschedule_booking(
    phone: str,
    booking_id: int,
    new_class_id: int,
    parent_name: str,
    student_name: str,
) -> str:
    """
    Move a confirmed booking to a different class. The new class is booked first;
    the old seat is only released once the new booking is secured.
    """
    try:
        result = _db_run(
            reschedule_trial_booking(
                phone=_real_phone(phone),
                booking_id=booking_id,
                new_class_id=new_class_id,
                parent_name=parent_name,
                student_name=student_name,
            )
        )
        start = datetime.fromisoformat(result["start"])
        note = "" if result.get("old_booking_cancelled") else (
            f"\\nNote: the old booking #{booking_id} could not be removed automatically; tell the customer staff will remove it."
        )
        return (
            "✅ *BOOKING RESCHEDULED!*\\n\\n"
            f"New Booking ID: {result['booking_id']}\\n"
            f"Date: {start.strftime('%d %B %Y')}\\n"
            f"Time: {start.strftime('%I:%M %p')}\\n"
            f"Class ID: {new_class_id}" + note
        )
    except Exception as exc:
        logger.exception("Reschedule failed")
        return (
            "Rescheduling was not completed: "
            f"{exc} The original booking is unchanged. Offer another class or staff help."
        )
'''
s = AGENT.read_text(encoding="utf-8")
if "reschedule_trial_booking(" in s.split("def reschedule_booking", 1)[-1][:900]: print("[skip] reschedule tool")
else:
    pat = re.compile(r'def reschedule_booking\(.*?"administrator to complete the change\."\n    \)\n', re.S)
    if len(pat.findall(s)) != 1: sys.exit("[FAIL] reschedule_booking stub not found")
    AGENT.write_text(pat.sub(lambda m: NEW_RESCHED, s, count=1), encoding="utf-8"); print("[ok]   reschedule_booking tool is real")

sub(AGENT,
'''            "Your booking has been saved and "
            "added to Google Calendar."''',
'''            "Your booking has been saved"
            + (" and added to Google Calendar." if result.get("google_event_id") else ".")''',
"confirmation text only mentions Calendar when used", 'result.get("google_event_id") else')

# ------------------------------------------------------------------ 3. main.py
sub(MAIN,
'''        booking_count = await db.scalar(
            select(func.count(Booking.id))
        ) or 0''',
'''        booking_count = await db.scalar(
            select(func.count(Booking.id)).where(Booking.status == "confirmed")
        ) or 0''', "dashboard counts confirmed bookings only", 'where(Booking.status == "confirmed")\n        ) or 0')

sub(MAIN,
'''    return templates.TemplateResponse(
        "timetable.html",
        {
            "request": request,
            "schedules": schedules,
        },
    )''',
'''    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def _mins(t):
        try:
            hm, ap = t.strip().split()
            h, mi = map(int, hm.split(":"))
            return (h % 12 + (12 if ap.upper() == "PM" else 0)) * 60 + mi
        except Exception:
            return 0

    by_day = {
        d: sorted(
            [c for c in schedules if (c.day_of_week or "").strip().lower() == d.lower()],
            key=lambda c: _mins(c.start_time),
        )
        for d in day_order
    }
    seats = sum(c.max_capacity or 0 for c in schedules)
    filled = sum(c.current_enrolled or 0 for c in schedules)

    return templates.TemplateResponse(
        "timetable.html",
        {
            "request": request,
            "schedules": schedules,
            "by_day": by_day,
            "seats": seats,
            "filled": filled,
        },
    )''', "timetable route feeds the weekly grid", '"by_day": by_day')

ROUTES = '''

@app.get("/students/{lead_id}", response_class=HTMLResponse)
async def serve_student_detail(
    lead_id: int,
    request: Request,
    admin: str = Depends(get_current_admin_html),
):
    import re
    from zoneinfo import ZoneInfo
    from app.models.student import Student
    from app.models.waitlist import Waitlist

    myt = ZoneInfo("Asia/Kuala_Lumpur")
    async with AsyncSessionLocal() as db:
        lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Student not found")
        bookings = (
            await db.execute(select(Booking).where(Booking.lead_id == lead_id).order_by(Booking.id.desc()))
        ).scalars().all()
        siblings = (await db.execute(select(Student).where(Student.lead_id == lead_id))).scalars().all()
        waitlist = (await db.execute(select(Waitlist).where(Waitlist.phone == lead.phone))).scalars().all()
        ids = {int(x.group(1)) for b in bookings if (x := re.search(r"Class ID:\\s*(\\d+)", b.notes or ""))}
        classes = {}
        if ids:
            rows = (await db.execute(select(ClassSchedule).where(ClassSchedule.id.in_(ids)))).scalars().all()
            classes = {c.id: c for c in rows}

    items = []
    for b in bookings:
        x = re.search(r"Class ID:\\s*(\\d+)", b.notes or "")
        when = None
        if b.appointment_start:
            start = b.appointment_start if b.appointment_start.tzinfo else b.appointment_start.replace(tzinfo=ZoneInfo("UTC"))
            when = start.astimezone(myt).strftime("%d %b %Y, %I:%M %p")
        items.append({"b": b, "cls": classes.get(int(x.group(1))) if x else None, "when": when})

    return templates.TemplateResponse(
        "student_detail.html",
        {"request": request, "lead": lead, "items": items, "siblings": siblings, "waitlist": waitlist},
    )


@app.post("/admin/bookings/{booking_id}/cancel")
async def admin_cancel_booking(
    booking_id: int,
    admin: str = Depends(get_current_admin_api),
):
    from app.tools.booking_service import cancel_trial_booking

    async with AsyncSessionLocal() as db:
        booking = (await db.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    try:
        await cancel_trial_booking(booking.phone, booking_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "Booking cancelled and seat released"}
'''
STUD = '''    return templates.TemplateResponse(
        "students.html",
        {
            "request": request,
            "leads": leads,
        },
    )'''
sub(MAIN, STUD, STUD + ROUTES, "student profile + admin cancel routes", '"/students/{lead_id}"')

# ------------------------------------------------------------------ 4. analytics.py
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
            "seats_filled": int(seats_filled),''', "analytics: new fields", '"cancelled_bookings": cancelled_bookings')

# ------------------------------------------------------------------ 5. templates
for name in ("timetable.html", "student_detail.html", "analytics.html"):
    src = HERE / name
    if not src.exists(): sys.exit(f"[FAIL] {name} must sit next to this script")
    shutil.copy(src, TPL / name); print(f"[ok]   {name} installed")

st = TPL / "students.html"; t = st.read_text(encoding="utf-8")
old = '<tr class="border-b last:border-none hover:bg-gray-50 transition student-row">'
new = "<tr onclick=\"window.location='/students/{{ lead.id }}'\" class=\"border-b last:border-none hover:bg-gray-50 transition student-row cursor-pointer\">"
if "/students/{{ lead.id }}" in t: print("[skip] clickable student rows")
elif t.count(old) == 1: st.write_text(t.replace(old, new), encoding="utf-8"); print("[ok]   student rows are clickable")
else: print("[warn] student row tag not found; paste me line 46 of app/templates/students.html")

print("\nDone. Restart uvicorn.")
