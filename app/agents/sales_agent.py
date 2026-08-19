"""
TUTOR0 AI Sales Agent — Phase 5 v9
Optimized: Added rich post-booking confirmation receipt for professional closure.
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

# ── SYSTEM PROMPT OVERHAUL FOR METRIC EXCELLENCE & LOW LATENCY ────────────────
SYSTEM_PROMPT = """TUTOR0 AI — Official Sales & Registration Agent for Wesh Tuition Centre, Melaka.

ROLE & PERSONALITY:
You are an expert, highly professional sales conversational agent on WhatsApp. 
Your goal is to guide parents through querying information, saving their registration details, and booking a trial class.

CORE BEHAVIOR RULES (CRITICAL FOR PRODUCTION EVALUATION):
1. ZERO HALLUCINATION (100% Faithfulness): You must answer questions using ONLY the facts retrieved from 'query_knowledge_base'. If a subject, class schedule, or specific discount is NOT explicitly stated in the context, you MUST explicitly state that it is not offered or unavailable. Never invent prices, dates, or terms.
2. MATCH THE LANGUAGE: Always mirror the customer's language layout exactly. If the user asks a question in Malay, reply entirely in Malay. If they ask in English, reply in English. If they use Manglish, reply in clear, friendly English.
3. CONCISE & COMPLETELY GROUNDED: Keep responses brief (1-2 sentences max per turn) but structurally complete. Avoid empty conversational filler or vague fluff.

TOOL EXECUTION LIMITS (CRITICAL FOR LATENCY & COST):
- get_lead_info: Call this EXACTLY ONCE at the very beginning of the conversation. Never call it again once you know their status.
- save_lead: Call this AT MOST ONCE per user message. Batch all newly collected information (e.g., parent name, student name, subjects) into a SINGLE call. Never execute multiple save_lead calls sequentially in the same turn.
- General: Do not chain unnecessary tool calls. Extract all data, make the required tool call(s) concurrently if possible, and immediately generate the final text response.

CORE OFFERINGS & TEMPLATES:
- Only these 6 subjects are offered: English, Bahasa Melayu, Mathematics, History, Geography, RBT.
- If asked about any other subject (e.g., Science, Add Maths, Chemistry, Physics, Computer Science, IGCSE), you must state exactly: "We do not offer [Subject]. We only offer English, Bahasa Melayu, Mathematics, History, Geography, and RBT."
- Pricing: RM50/month per individual subject.
- Packages: 3 subjects = RM100/month | All 6 subjects = RM170/month.
- Discounts: We do not offer a 50% discount. Sibling discount is maximum 10%.

HANDLING PACKED INFORMATION (SINGLE-TURN EXTRACTION):
If a new customer sends a single message containing multiple registration details (e.g., Parent Name, Student Name, Form/Year, Email, Address, Subjects), extract ALL available fields instantly and call `save_lead` immediately with those parameters. 
Do not ask step-by-step questions for information the user has already provided. Skip directly to confirming their details or providing the subject menu for missing pieces.

STEP-BY-STEP DATA COLLECTION FLOW (If details are missing, collect incrementally):
1. Greet the user and check history using `get_lead_info`.
2. Address any initial FAQ questions via `query_knowledge_base`.
3. Collect Parent Name (Save).
4. Collect Student Name (Save).
5. Collect Student Form/Year (Save).
6. Collect Email & Address (Save).
7. Display the structured Subject Menu & Package Pricing clearly.
8. Once subjects are chosen, present a full *Registration Summary* showing:
   *Registration Summary*
   Parent: [name] | Student: [name], [form]
   Phone: [num] | Email: [email] | Address: [addr]
   Subjects: [subj] | Fee: RM[calculated amt]
   Ask them to reply 'CONFIRM' or 'CANCEL'.
9. Upon 'CONFIRM', transition to checking available slots using `check_availability` and booking via `book_trial`.

OUTPUT CONSTRAINT:
Every time you execute a tool call, you MUST append a friendly, clear, non-empty text response back to the user explaining what was done or what step is next. Never leave an output message blank.

HUMAN HANDOFF PROTOCOL:
If a parent expresses deep concerns, anxiety, anger, or says things like "My son is failing" or "I am worried," DO NOT try to handle the emotional concern. Immediately call 'request_human_handoff'. Explain politely that you are transferring them to a senior teacher/admin who will assist them shortly.

RESCHEDULING:
If a user wants to reschedule, first use 'check_my_booking' to get their booking ID, then use 'check_availability' to show new slots. Once they pick a new slot number, call 'reschedule_booking'.
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
def check_availability(phone: str, preferred_day: Optional[str] = None) -> str:
    """Show REAL available trial class slots from Google Calendar. Call after customer confirms registration.
    phone: use exact {phone} context value.
    """
    try:
        from app.tools.calendar_tool import get_available_slots, format_slots_message
        from app.db.redis_client import save_user_slots
        slots = get_available_slots(days_ahead=7, max_slots=4)
        if not slots:
            return (
                "No trial slots available in the next 7 days. "
                "Would you like to join our waitlist? We'll notify you as soon as a slot opens up. "
                "If yes, call join_waitlist with their details."
            )
        
        # Persist slots into Redis keyed by phone number
        save_user_slots(phone, slots)
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
        from app.db.redis_client import get_user_slots, clear_user_slots
        
        # Retrieve slots securely from Redis
        slots = get_user_slots(phone)
        if not slots or slot_number < 1 or slot_number > len(slots):
            return "That slot number is no longer valid or has expired. Please call check_availability again and pick a valid number."

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

        # Clear Redis slot cache for this specific user after successful booking
        clear_user_slots(phone)

        try:
            from app.tools.notifications import notify_new_booking
            notify_new_booking(parent_name, student_name, phone, subjects or "Not specified", chosen["label"])
        except Exception as notify_err:
            logger.error(f"Admin notification failed (non-fatal): {notify_err}")

        # Structured, rich post-booking confirmation
        return (
            f"🎉 *TRIAL CLASS CONFIRMED!*\n\n"
            f"Thank you, {parent_name}! Here are your booking details:\n\n"
            f"👤 *Student:* {student_name}\n"
            f"📚 *Subject(s):* {subjects or 'Not specified'}\n"
            f"📅 *Date & Time:* {chosen['label']}\n\n"
            f"📍 *Location:* Wesh Tuition Centre, Melaka\n"
            f"📌 *Reminder:* Please arrive 10 minutes early. Don't forget to bring a notebook and stationery!\n\n"
            f"We will send you a reminder closer to the date. Let us know if you have any questions. See you soon! 😊"
        )
    except Exception as e:
        logger.error(f"book_trial error: {e}")
        return f"Booking failed: {e}"


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


@tool
def request_human_handoff(phone: str, reason: str) -> str:
    """
    Triggers when a parent has a complex, emotional, or highly specific concern.
    Pauses the AI so a human admin can take over the WhatsApp chat.
    phone: use exact {phone} context value.
    """
    try:
        from app.db.redis_client import pause_bot
        # Run the async pause_bot in our sync DB runner
        _db_run(pause_bot(phone))
        
        logger.warning(f"🚨 HUMAN HANDOFF REQUESTED for {phone}. Reason: {reason}")
        
        return "Please inform the user that their concern is very important, and you are transferring them to a human coordinator who will reply to this chat shortly."
    except Exception as e:
        logger.error(f"Handoff error: {e}")
        return "Handoff failed, but tell the user someone will contact them."


@tool
def reschedule_booking(phone: str, booking_id: int, new_slot_number: int, parent_name: str, student_name: str) -> str:
    """
    Reschedules an existing booking in one step. 
    You MUST call check_my_booking and check_availability first!
    """
    try:
        from app.tools.calendar_tool import cancel_calendar_event
        from app.db.redis_client import get_user_slots
        
        # 1. Get the new slot details from Redis
        slots = get_user_slots(phone)
        if not slots or new_slot_number < 1 or new_slot_number > len(slots):
            return "Invalid slot number. Please ask them to pick a valid number from the availability list."
        chosen_slot = slots[new_slot_number - 1]

        # 2. Get the old booking
        bookings = _db_run(_get_bookings_async(phone))
        target_booking = next((b for b in bookings if b.id == booking_id), None)
        if not target_booking:
            return "Could not find the original booking to reschedule."

        # 3. Cancel the old Google Calendar event
        if target_booking.google_event_id:
            cancel_calendar_event(target_booking.google_event_id)
        _db_run(_cancel_booking_async(booking_id))

        # 4. Book the new slot (reusing existing book_trial logic)
        return book_trial.invoke({
            "phone": phone, 
            "parent_name": parent_name, 
            "student_name": student_name, 
            "slot_number": new_slot_number, 
            "subjects": target_booking.subjects
        })
    except Exception as e:
        logger.error(f"reschedule_booking error: {e}")
        return f"Rescheduling failed: {e}"


# ── Agent ─────────────────────────────────────────────────────────────────────

def _build_agent() -> AgentExecutor:
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model="openai/gpt-oss-120b",
        temperature=0.0,  # Dropped to 0 for strict structural alignment
        max_tokens=450,
    )
    tools = [
        query_knowledge_base, get_lead_info, save_lead, check_availability, book_trial,
        check_my_booking, cancel_my_booking, add_sibling, list_my_children, join_waitlist,
        request_human_handoff, reschedule_booking
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
        output = result.get("output", "").strip()
        
        # Intercept and eliminate blank or empty agent text fields
        if not output:
            return "Terima kasih! Maklumat anda telah diproses. Sila nyatakan subjek pilihan atau taip 'CONFIRM' untuk meneruskan. 😊"
            
        return output
    except Exception as e:
        logger.error(f"Agent error: {e}")
        if "Failed to call a function" in str(e) or "parsing" in str(e).lower():
            try:
                fallback_llm = ChatGroq(
                    api_key=settings.groq_api_key, 
                    model="openai/gpt-oss-20b", 
                    temperature=0.0, 
                    max_tokens=350
                )
                msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
                msgs += [{"role": m["role"], "content": m["content"]} for m in history]
                msgs += [{"role": "user", "content": user_message}]
                response = await asyncio.get_event_loop().run_in_executor(None, lambda: fallback_llm.invoke(msgs))
                return response.content if response.content.strip() else "Maaf, sila hantar semula mesej anda."
            except Exception as e2:
                logger.error(f"Fallback error: {e2}")
        return "Maaf, berlaku ralat. Sila cuba lagi. 🙏\nSorry, something went wrong. Please try again."