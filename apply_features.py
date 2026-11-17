"""
Run from the repo root:  python apply_features.py   (analytics.html must be next to this script)
Adds: cancel_my_booking, add_sibling, join_waitlist agent tools + prompt rules, and an /analytics admin page.
Backups: sales_agent.py.bak2 / main.py.bak2.  Safe to re-run.
"""
from pathlib import Path
import re, shutil, sys

AGENT, MAIN = Path("app/agents/sales_agent.py"), Path("app/main.py")
TPL = Path("app/templates")
HERE = Path(__file__).parent
for p in (AGENT, MAIN):
    if not p.exists(): sys.exit(f"Run from the repo root (missing {p}).")
    bak = p.with_suffix(p.suffix + ".bak2")
    if not bak.exists(): shutil.copy(p, bak)

def sub(path, old, new, label, marker=None):
    s = path.read_text(encoding="utf-8")
    if (marker or new) in s: print(f"[skip] {label}"); return
    if s.count(old) != 1: sys.exit(f"[FAIL] {label}: found {s.count(old)} matches in {path}. Paste me that area.")
    path.write_text(s.replace(old, new), encoding="utf-8"); print(f"[ok]   {label}")

TOOLS = '''
# ── Extra tools: cancel, siblings, waitlist ───────────────────────────────────

async def _add_sibling_async(phone, student_name, form_year, subjects):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.models.lead import Lead
    from app.db.crud_student import add_student

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            lead = (await db.execute(select(Lead).where(Lead.phone == phone))).scalar_one_or_none()
            if not lead:
                return None
            return await add_student(db, lead.id, student_name, form_year, subjects)
    finally:
        await engine.dispose()

async def _join_waitlist_async(phone, parent_name, student_name, subjects, preferred_day):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.models.waitlist import Waitlist

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            db.add(Waitlist(phone=phone, parent_name=parent_name, student_name=student_name,
                            subjects=subjects, preferred_day=preferred_day))
            await db.commit()
    finally:
        await engine.dispose()

@tool
def cancel_my_booking(phone: str, booking_id: int) -> str:
    """Cancel one of the customer's confirmed bookings. Use check_my_booking first to get the booking ID, and confirm with the customer before calling this."""
    try:
        bookings = _db_run(_get_bookings_async(phone))
        target = next((b for b in bookings if b.id == booking_id and b.status == "confirmed"), None)
        if not target:
            return "No active booking with that ID was found for this number."
        _db_run(_cancel_booking_async(booking_id))
        return f"Booking {booking_id} has been cancelled. Tell the customer it is cancelled and offer to book another time."
    except Exception as e:
        logger.error(f"cancel_my_booking error: {e}")
        return f"Cancellation failed: {e}"

@tool
def add_sibling(phone: str, student_name: str, form_year: Optional[str] = None, subjects: Optional[str] = None) -> str:
    """Register an additional child (sibling) under the same parent. Call once per extra child."""
    try:
        student = _db_run(_add_sibling_async(phone, student_name, form_year, subjects))
        if not student:
            return "No parent registration found for this number yet. Register the parent and first child first."
        return f"Sibling {student_name} registered. Mention that siblings get a 10% discount."
    except Exception as e:
        logger.error(f"add_sibling error: {e}")
        return f"Could not register sibling: {e}"

@tool
def join_waitlist(phone: str, parent_name: str, student_name: str, subjects: Optional[str] = None, preferred_day: Optional[str] = None) -> str:
    """Add the customer to the waitlist when no suitable class has an open seat."""
    try:
        _db_run(_join_waitlist_async(phone, parent_name, student_name, subjects, preferred_day))
        return "Added to the waitlist. Tell the customer our staff will contact them when a seat opens."
    except Exception as e:
        logger.error(f"join_waitlist error: {e}")
        return f"Could not join waitlist: {e}"

'''

# 1. tools (inserted just before the Agent section)
s = AGENT.read_text(encoding="utf-8")
m = re.search(r"\n# ── Agent ─", s)
if not m: sys.exit("[FAIL] could not find the '# ── Agent' marker in sales_agent.py")
if "def cancel_my_booking" in s: print("[skip] add tools")
else:
    AGENT.write_text(s[:m.start()] + "\n" + TOOLS + s[m.start():], encoding="utf-8"); print("[ok]   add tools")

# 2. register tools
sub(AGENT, "check_my_booking, request_human_handoff, reschedule_booking\n    ]",
    "check_my_booking, request_human_handoff, reschedule_booking,\n        cancel_my_booking, add_sibling, join_waitlist\n    ]", "register tools",
    marker="cancel_my_booking, add_sibling, join_waitlist")

# 3. prompt rule (replaces the 'cannot cancel' line)
sub(AGENT,
 "- You CANNOT cancel bookings or manage waitlists. For those requests, call request_human_handoff and tell the customer our staff will assist. Never claim a cancellation or waitlist spot was made.",
 "- Cancelling: call check_my_booking to find the booking ID, confirm with the customer, then call cancel_my_booking.\\n"
 "- Siblings: if the parent wants to register another child, call add_sibling once per child and mention the 10% sibling discount.\\n"
 "- Waitlist: if check_available_classes shows no open class for what the customer wants, offer the waitlist and call join_waitlist.\\n"
 "- Only tell the customer something was cancelled, added or waitlisted AFTER the tool returns success.",
 "prompt rules (cancel / sibling / waitlist)", marker="call cancel_my_booking.")

# 4. /analytics route
sub(MAIN,
 'return templates.TemplateResponse("students.html", {"request": request, "leads": leads})\n',
 'return templates.TemplateResponse("students.html", {"request": request, "leads": leads})\n\n'
 '@app.get("/analytics", response_class=HTMLResponse)\n'
 'async def serve_analytics(request: Request, admin: str = Depends(get_current_admin_html)):\n'
 '    from app.tools.analytics import get_analytics_summary\n'
 '    data = await get_analytics_summary()\n'
 '    return templates.TemplateResponse("analytics.html", {"request": request, "d": data})\n',
 "add /analytics route", marker='"/analytics"')

# 5. template + sidebar links
src = HERE / "analytics.html"
if not src.exists(): sys.exit("[FAIL] analytics.html must sit next to apply_features.py")
shutil.copy(src, TPL / "analytics.html"); print("[ok]   analytics.html copied")
link = '                <a href="/analytics" class="block px-4 py-2 hover:bg-slate-800 rounded-lg">📈 Analytics</a>'
for name in ("dashboard.html", "timetable.html", "students.html"):
    f = TPL / name; t = f.read_text(encoding="utf-8")
    if 'href="/analytics"' in t: print(f"[skip] sidebar {name}"); continue
    t2 = re.sub(r'(\n[^\n]*href="/students"[^\n]*</a>)', lambda mm: mm.group(1) + "\n" + link, t, count=1)
    if t2 == t: print(f"[warn] no sidebar anchor in {name}"); continue
    f.write_text(t2, encoding="utf-8"); print(f"[ok]   sidebar {name}")
print("\nDone. Restart uvicorn.")
