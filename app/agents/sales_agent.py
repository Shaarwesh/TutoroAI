"""
EduBot Sales Agent — Phase 5 v5
Fixed: each tool creates its own DB connection (no shared engine across threads).
"""
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

from app.config import settings
from app.tools.knowledge_base import query_knowledge_base as _query_kb

import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """EduBot — WhatsApp registration bot, Wesh Tuition Centre, Melaka.

STYLE: Short replies, 1 point per message. No filler. Never invent info.

SUBJECTS (only these): English, Bahasa Melayu, Mathematics, History, Geography, RBT.
If asked about others (Science etc), say we don't offer it.

RULES:
- query_knowledge_base before any fee/schedule answer.
- One question per message.
- `phone` param in save_lead/book_trial = the {phone} context value ALWAYS, never a number customer typed in chat.
- get_lead_info: once only, first turn.
- save_lead: call after EVERY new detail given (name/child/form/contact/email/address/subjects).
- check_availability: use its exact text, never invent slots.
- book_trial: use slot_number from check_availability's list only.

RETURNING CUSTOMER: if get_lead_info says RETURNING_CUSTOMER, greet by name, ask update-or-book, skip known fields.

FLOW (1 step/msg, save_lead each step):
1. get_lead_info → greet, ask need
2. answer via KB if needed
3. ask parent name
4. save name → ask student name
5. save → ask form/year
6. save → ask phone
7. save → ask email
8. save → ask address
9. save → send subject menu:
Please select your subjects (reply with the numbers):
1. English — RM50/month
2. Bahasa Melayu — RM50/month
3. Mathematics — RM50/month
4. History — RM50/month
5. Geography — RM50/month
6. RBT — RM50/month
📦 Packages: 1+2+3=RM100/mo | 4+5+6=RM100/mo | All 6=RM170/mo
10. save subjects → KB lookup fee → show summary, ask CONFIRM/CANCEL:
*Registration Summary*
Parent: [name] | Student: [name], [form]
Phone: [num] | Email: [email] | Address: [addr]
Subjects: [subj] | Fee: RM[amt]
Reply CONFIRM or CANCEL.
11. CONFIRM→save(stage=confirmed)+check_availability | CANCEL→save(stage=cancelled)+friendly close
12. on slot number reply → book_trial(slot_number, student_name, parent_name)

CANCEL/RESCHEDULE EXISTING BOOKING:
If customer says "cancel my booking", "reschedule", or asks about their existing trial:
- Call check_my_booking(phone) to find their booking ID
- If found, confirm with customer which booking before cancelling
- Call cancel_my_booking(booking_id, phone, parent_name, student_name) to cancel
- For reschedule: cancel the old one, then run check_availability + book_trial for a new slot

MULTIPLE CHILDREN (SIBLINGS):
If customer wants to register MORE than one child:
- First child goes through the normal flow (save_lead with child_name/child_age)
- For each ADDITIONAL child, ask for their name, form/year, and subjects, then call add_sibling
- If asked "who's registered", call list_my_children

WAITLIST:
If check_availability returns no slots, offer the waitlist. If customer agrees,
call join_waitlist with their details.

LANGUAGE: mirror customer (EN/BM/Manglish).
"""


# ── DB helper: fresh connection per call ──────────────────────────────────────
def _db_run(coro):
    """Run an async DB coroutine safely from a sync thread context."""
    try:
        with __import__('concurrent.futures', fromlist=['ThreadPoolExecutor']).ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except Exception as e:
        logger.error(f"DB error: {e}")
        raise


async def _get_lead(phone: str):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.models.lead import Lead

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            result = await db.execute(select(Lead).where(Lead.phone == phone))
            return result.scalar_one_or_none()
    finally:
        await engine.dispose()


async def _save_lead_async(phone, name, child_name, child_age, subjects, email, address, language, stage):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.models.lead import Lead
    from datetime import datetime, timezone

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            result = await db.execute(select(Lead).where(Lead.phone == phone))
            lead = result.scalar_one_or_none()
            if lead:
                if name: lead.name = name
                if child_name: lead.child_name = child_name
                if child_age: lead.child_age = child_age
                if subjects: lead.subjects = subjects
                if email: lead.email = email
                if address: lead.address = address
                if language: lead.language = language
                if stage: lead.stage = stage
                lead.updated_at = datetime.now(timezone.utc)
            else:
                lead = Lead(
                    phone=phone, name=name, child_name=child_name,
                    child_age=child_age, subjects=subjects, email=email,
                    address=address, language=language, stage=stage or "new"
                )
                db.add(lead)
            await db.commit()
    finally:
        await engine.dispose()


async def _save_booking_async(phone, subjects, slot_note, google_event_id=None):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.models.lead import Lead
    from app.models.booking import Booking
    from datetime import datetime, timezone

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            result = await db.execute(select(Lead).where(Lead.phone == phone))
            lead = result.scalar_one_or_none()
            if lead:
                lead.stage = "booked"
                now = datetime.now(timezone.utc)
                booking = Booking(
                    lead_id=lead.id, phone=phone,
                    appointment_start=now, appointment_end=now,
                    subjects=subjects, notes=slot_note, status="confirmed",
                    google_event_id=google_event_id,
                )
                db.add(booking)
                await db.commit()
    finally:
        await engine.dispose()


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def query_knowledge_base(question: str) -> str:
    """Search Wesh Tuition Centre's knowledge base for fees, subjects, schedule, and policies."""
    return _query_kb(question)


@tool
def get_lead_info(phone: str) -> str:
    """
    Check if this customer has registered before.
    Call this at the start of registration to detect returning customers.
    Use the customer's WhatsApp phone number (e.g. whatsapp:+60123456789).
    """
    try:
        lead = _db_run(_get_lead(phone))
        if not lead:
            return "NEW_CUSTOMER"
        return (
            f"RETURNING_CUSTOMER | name={lead.name} | child={lead.child_name} | "
            f"form={lead.child_age} | subjects={lead.subjects} | "
            f"email={lead.email} | stage={lead.stage}"
        )
    except Exception as e:
        logger.error(f"get_lead_info error: {e}")
        return "NEW_CUSTOMER"


@tool
def save_lead(
    phone: str,
    parent_name: Optional[str] = None,
    child_name: Optional[str] = None,
    child_age: Optional[int] = None,
    subjects: Optional[str] = None,
    email: Optional[str] = None,
    address: Optional[str] = None,
    language: Optional[str] = "en",
    stage: Optional[str] = "new",
) -> str:
    """
    Save/update lead. Call after CONFIRM or CANCEL (save regardless).
    phone: use exact {phone} context value, never a number typed in chat.
    child_age: form/year as int. stage: 'confirmed'/'cancelled'/'qualified'/'new'.
    """
    try:
        _db_run(_save_lead_async(phone, parent_name, child_name, child_age, subjects, email, address, language, stage))
        return f"Saved. Stage: {stage}."
    except Exception as e:
        logger.error(f"save_lead error: {e}")
        return f"Save failed: {e}"


@tool
def check_availability(preferred_day: Optional[str] = None) -> str:
    """Show REAL available trial class slots from Google Calendar. Call after customer confirms registration."""
    try:
        from app.tools.calendar_tool import get_available_slots, format_slots_message
        slots = get_available_slots(days_ahead=7, max_slots=4)
        if not slots:
            return (
                "No trial slots available in the next 7 days. "
                "Would you like to join our waitlist? We'll notify you as soon as a slot opens up. "
                "If yes, call join_waitlist with their details."
            )
        # Cache slots globally so book_trial can resolve the number the customer picks
        _slot_cache["last"] = slots
        return format_slots_message(slots)
    except Exception as e:
        logger.error(f"check_availability error: {e}")
        return "Sorry, I couldn't check the calendar right now. Please try again shortly."


@tool
def book_trial(phone: str, parent_name: str, student_name: str, slot_number: int, subjects: Optional[str] = "Not specified") -> str:
    """
    Book trial using slot_number from check_availability's list. Never invent a slot.
    phone: use exact {phone} context value.
    """
    try:
        from app.tools.calendar_tool import create_calendar_event
        slots = _slot_cache.get("last")
        if not slots or slot_number < 1 or slot_number > len(slots):
            return "That slot number isn't valid. Please call check_availability again and pick a valid number."

        chosen = slots[slot_number - 1]
        event_id = create_calendar_event(
            student_name=student_name,
            parent_name=parent_name,
            phone=phone,
            subjects=subjects or "Not specified",
            start=chosen["start"],
            end=chosen["end"],
        )
        _db_run(_save_booking_async(phone, subjects or "Not specified", f"Trial: {chosen['label']}", event_id))

        # Notify admin (never breaks the flow if this fails)
        try:
            from app.tools.notifications import notify_new_booking
            notify_new_booking(parent_name, student_name, phone, subjects or "Not specified", chosen["label"])
        except Exception as notify_err:
            logger.error(f"Admin notification failed (non-fatal): {notify_err}")

        return f"Trial booked for {parent_name} on {chosen['label']}. We'll send a reminder before the class!"
    except Exception as e:
        logger.error(f"book_trial error: {e}")
        return f"Booking failed: {e}"


# In-memory cache mapping the last shown slots to their real datetimes (per-process, simple for demo)
_slot_cache: dict = {}


async def _add_waitlist_async(phone: str, parent_name: str, student_name: str, subjects: str, preferred_day: str = None):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.models.waitlist import Waitlist

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            entry = Waitlist(
                phone=phone, parent_name=parent_name, student_name=student_name,
                subjects=subjects, preferred_day=preferred_day,
            )
            db.add(entry)
            await db.commit()
            return entry
    finally:
        await engine.dispose()


@tool
def join_waitlist(phone: str, parent_name: str, student_name: str, subjects: str, preferred_day: Optional[str] = None) -> str:
    """
    Add customer to the waitlist when check_availability found no open slots.
    They'll be notified when a slot opens up.

    Args:
        phone: WhatsApp number — use exact {phone} context value
        parent_name: Parent name
        student_name: Student name
        subjects: Subjects they want
        preferred_day: Optional preferred day, e.g. "Saturday"
    """
    try:
        _db_run(_add_waitlist_async(phone, parent_name, student_name, subjects, preferred_day))
        return "You've been added to the waitlist! We'll message you as soon as a trial slot opens up. 😊"
    except Exception as e:
        logger.error(f"join_waitlist error: {e}")
        return f"Couldn't add you to the waitlist: {e}"


async def _add_student_async(phone: str, name: str, form_year: str = None, subjects: str = None):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.models.lead import Lead
    from app.models.student import Student

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            result = await db.execute(select(Lead).where(Lead.phone == phone))
            lead = result.scalar_one_or_none()
            if not lead:
                return None
            student = Student(lead_id=lead.id, name=name, form_year=form_year, subjects=subjects)
            db.add(student)
            await db.commit()
            await db.refresh(student)
            return student
    finally:
        await engine.dispose()


async def _get_students_async(phone: str):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.models.lead import Lead
    from app.models.student import Student

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            result = await db.execute(select(Lead).where(Lead.phone == phone))
            lead = result.scalar_one_or_none()
            if not lead:
                return []
            result = await db.execute(select(Student).where(Student.lead_id == lead.id))
            return result.scalars().all()
    finally:
        await engine.dispose()


@tool
def add_sibling(phone: str, student_name: str, form_year: str, subjects: str) -> str:
    """
    Register an ADDITIONAL child (sibling) under the same parent.
    Use this when the customer says they want to register more than one child.
    The FIRST child is saved via save_lead as usual; use this tool for the 2nd, 3rd, etc.

    Args:
        phone: WhatsApp number — use exact {phone} context value
        student_name: Name of the additional student
        form_year: Their form/year (e.g. "Form 1", "Year 5")
        subjects: Comma-separated subjects for this student
    """
    try:
        result = _db_run(_add_student_async(phone, student_name, form_year, subjects))
        if result is None:
            return "Couldn't add sibling — parent record not found. Please complete initial registration first."
        return f"Added {student_name} ({form_year}) as an additional student."
    except Exception as e:
        logger.error(f"add_sibling error: {e}")
        return f"Failed to add sibling: {e}"


@tool
def list_my_children(phone: str) -> str:
    """
    List all children registered under this parent's phone number, including siblings.
    phone: use exact {phone} context value.
    """
    try:
        students = _db_run(_get_students_async(phone))
        if not students:
            return "No additional children found. Only the primary registration exists."
        lines = ["Registered children:"]
        for s in students:
            lines.append(f"- {s.name} ({s.form_year}) — Subjects: {s.subjects}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"list_my_children error: {e}")
        return "Couldn't retrieve children list right now."


async def _get_bookings_async(phone: str):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.db.crud_booking import get_bookings_by_phone

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            return await get_bookings_by_phone(db, phone)
    finally:
        await engine.dispose()


async def _cancel_booking_async(booking_id: int):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.db.crud_booking import cancel_booking

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            return await cancel_booking(db, booking_id)
    finally:
        await engine.dispose()


@tool
def check_my_booking(phone: str) -> str:
    """
    Look up the customer's existing booking(s) by phone number.
    Use this when customer asks to cancel or reschedule, or wants to check their booking.
    phone: use exact {phone} context value.
    """
    try:
        bookings = _db_run(_get_bookings_async(phone))
        active = [b for b in bookings if b.status == "confirmed"]
        if not active:
            return "No active bookings found for this number."
        lines = ["Your active booking(s):"]
        for b in active:
            lines.append(f"- ID {b.id}: {b.notes or b.subjects} (status: {b.status})")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"check_my_booking error: {e}")
        return "Sorry, couldn't check your bookings right now."


@tool
def cancel_my_booking(booking_id: int, phone: str, parent_name: str = "Customer", student_name: str = "") -> str:
    """
    Cancel a booking by its ID (get this from check_my_booking first).
    Cancels both the Google Calendar event and updates the database record.

    Args:
        booking_id: The booking ID from check_my_booking
        phone: Customer's WhatsApp number
        parent_name: Parent name (for notification)
        student_name: Student name (for notification)
    """
    try:
        bookings = _db_run(_get_bookings_async(phone))
        target = next((b for b in bookings if b.id == booking_id), None)
        if not target:
            return "Booking not found for that ID."

        if target.google_event_id:
            from app.tools.calendar_tool import cancel_calendar_event
            cancel_calendar_event(target.google_event_id)

        _db_run(_cancel_booking_async(booking_id))

        try:
            from app.tools.notifications import notify_cancellation
            notify_cancellation(parent_name, student_name, phone, target.notes or "")
        except Exception as notify_err:
            logger.error(f"Cancellation notification failed (non-fatal): {notify_err}")

        return "Your booking has been cancelled. Let us know if you'd like to book a new trial class!"
    except Exception as e:
        logger.error(f"cancel_my_booking error: {e}")
        return f"Cancellation failed: {e}"


# ── Agent ─────────────────────────────────────────────────────────────────────

def _build_agent() -> AgentExecutor:
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        max_tokens=350,
    )
    tools = [
        query_knowledge_base, get_lead_info, save_lead, check_availability, book_trial,
        check_my_booking, cancel_my_booking, add_sibling, list_my_children, join_waitlist,
    ]
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=6, handle_parsing_errors=True)


_agent_executor: AgentExecutor | None = None

def get_agent() -> AgentExecutor:
    global _agent_executor
    if _agent_executor is None:
        _agent_executor = _build_agent()
    return _agent_executor


# ── Entry point ───────────────────────────────────────────────────────────────

async def run_agent(user_phone: str, user_message: str, history: list[dict]) -> str:
    agent = get_agent()
    chat_history = []
    for msg in history:
        if msg["role"] == "user":
            chat_history.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            chat_history.append(AIMessage(content=msg["content"]))

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: agent.invoke({
                "input": user_message,
                "chat_history": chat_history,
                "phone": user_phone,
            })
        )
        return result.get("output", "Sorry, something went wrong. Please try again.")
    except Exception as e:
        logger.error(f"Agent error: {e}")
        if "Failed to call a function" in str(e) or "parsing" in str(e).lower():
            try:
                llm = ChatGroq(api_key=settings.groq_api_key, model="llama-3.3-70b-versatile", temperature=0.2, max_tokens=350)
                msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
                msgs += [{"role": m["role"], "content": m["content"]} for m in history]
                msgs += [{"role": "user", "content": user_message}]
                response = await asyncio.get_event_loop().run_in_executor(None, lambda: llm.invoke(msgs))
                return response.content
            except Exception as e2:
                logger.error(f"Fallback error: {e2}")
        return "Maaf, berlaku ralat. Sila cuba lagi. 🙏\nSorry, something went wrong. Please try again."
