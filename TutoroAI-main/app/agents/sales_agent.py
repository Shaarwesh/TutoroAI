"""
TUTORO AI Sales Agent — Phase 6
Optimized: Fully integrated with PostgreSQL Database Timetable. GCal deprecated.
"""
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

from app.config import settings
from app.tools.knowledge_base import query_knowledge_base as _query_kb
from app.tools.schedule_tool import get_database_schedule

import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── SYSTEM PROMPT OVERHAUL FOR METRIC EXCELLENCE & LOW LATENCY ────────────────
SYSTEM_PROMPT = """TUTORO AI — Official Sales & Registration Agent for Wesh Tuition Centre, Melaka.

CUSTOMER WHATSAPP ID: {phone}
Use this exact value as the `phone` parameter in EVERY tool call. NEVER ask the customer for their phone number; you already have it.

ROLE & PERSONALITY:
You are TUTORO AI, the official customer service and sales agent for Wesh Tuition Centre.
You are professional, friendly, and highly persuasive. Your goal is to provide accurate information and secure trial class bookings.

CORE BEHAVIOR RULES (CRITICAL FOR PRODUCTION EVALUATION):
1. ZERO HALLUCINATION (100% Faithfulness): You must answer questions using ONLY the facts listed in this prompt or retrieved from 'query_knowledge_base' (call it for anything not listed here: policies, hours, location, payments). If a subject, class schedule, or specific discount is NOT explicitly stated in the context, you MUST explicitly state that it is not offered or unavailable. Never invent prices, dates, or terms.
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
- Discounts: We do not offer a 50% discount. Sibling discount is maximum 10%. No other discounts exist.
- Registration fee: RM30 one-time for new students (includes a starter kit). Monthly fees are due by the 5th of each month.
- Payment methods: cash, or online bank transfer (TNG, DuitNow).
- Hours: Monday-Friday 2:00 PM-6:00 PM, Saturday 9:00 AM-1:00 PM, closed Sunday. Each class is 1 hour per subject, max 10 students per class.
- Free parking outside the centre. The first trial class is FREE with no commitment. Location is Melaka only.
- If something is NOT stated here or in the knowledge base (public holidays, exact street address, teacher details, other branches), say you do not have that information and offer to have our staff follow up. NEVER invent policies, prices or branches.
- You CANNOT cancel bookings or manage waitlists. For those requests, call request_human_handoff and tell the customer our staff will assist. Never claim a cancellation or waitlist spot was made.

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
9. Upon 'CONFIRM', transition to checking available slots using `check_available_classes` and booking via `book_trial` using the provided Class ID.

LANGUAGE RULE:
You MUST reply in the exact same language the user uses.
- If they speak English, reply in English.
- If they speak Malay (Bahasa Melayu), reply in Malay.
- If they use "Manglish" (a mix of English and Malay), you must reply naturally in Manglish.

FORMATTING RULE:
Never send long paragraphs. You must use WhatsApp's native formatting to make your messages highly readable and structured:
- Use bullet points (-) for lists, packages, and features.
- Use *bold* for emphasis on key terms (e.g., *RM50*, *Trial Class*).
- Use spacing (newlines) to separate different thoughts.

OUTPUT CONSTRAINT:
Every time you execute a tool call, you MUST append a friendly, clear, non-empty text response back to the user explaining what was done or what step is next. Never leave an output message blank.

HUMAN HANDOFF PROTOCOL:
If a parent expresses deep concerns, anxiety, anger, or says things like "My son is failing" or "I am worried," DO NOT try to handle the emotional concern. Immediately call 'request_human_handoff'. Explain politely that you are transferring them to a senior teacher/admin who will assist them shortly.

RESCHEDULING:
If a user wants to reschedule, first use 'check_my_booking' to get their booking ID, then use 'check_available_classes' to show new slots. Once they pick a new Class ID, call 'reschedule_booking'.
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

async def _save_booking_async(phone, subjects, slot_note):
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
                    subjects=subjects, notes=slot_note, status="confirmed"
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
    """Check if this customer has registered before."""
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
    phone: str, parent_name: Optional[str] = None, child_name: Optional[str] = None,
    child_age: Optional[int] = None, subjects: Optional[str] = None, email: Optional[str] = None,
    address: Optional[str] = None, language: Optional[str] = "en", stage: Optional[str] = "new",
) -> str:
    """Save/update lead data to PostgreSQL."""
    try:
        _db_run(_save_lead_async(phone, parent_name, child_name, child_age, subjects, email, address, language, stage))
        return f"Saved. Stage: {stage}."
    except Exception as e:
        logger.error(f"save_lead error: {e}")
        return f"Save failed: {e}"

@tool
def check_available_classes(subject_requested: Optional[str] = None) -> str:
    """Fetch REAL available tuition classes from the PostgreSQL database timetable."""
    try:
        return _db_run(get_database_schedule(subject_requested))
    except Exception as e:
        logger.error(f"check_available_classes error: {e}")
        return "Sorry, I couldn't check the schedule right now."

@tool
def book_trial(phone: str, parent_name: str, student_name: str, class_id: int, subjects: Optional[str] = "Not specified") -> str:
    """Book a trial class using the Class ID from the check_available_classes list."""
    try:
        _db_run(_save_booking_async(phone, subjects or "Not specified", f"Trial Class ID: {class_id}"))

        return (
            f"🎉 *TRIAL CLASS CONFIRMED!*\n\n"
            f"Thank you, {parent_name}! Here are your booking details:\n\n"
            f"👤 *Student:* {student_name}\n"
            f"📚 *Subject(s):* {subjects or 'Not specified'}\n"
            f"📅 *Class ID:* {class_id}\n\n"
            f"📍 *Location:* Wesh Tuition Centre, Melaka\n"
            f"📌 *Reminder:* Please arrive 10 minutes early. Don't forget to bring a notebook and stationery!\n\n"
            f"We will send you a reminder closer to the date. Let us know if you have any questions. See you soon! 😊"
        )
    except Exception as e:
        logger.error(f"book_trial error: {e}")
        return f"Booking failed: {e}"

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
    """Look up the customer's existing booking(s) by phone number."""
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
def request_human_handoff(phone: str, reason: str) -> str:
    """Triggers when a parent has a complex, emotional, or highly specific concern."""
    try:
        from app.db.redis_client import pause_bot
        _db_run(pause_bot(phone))
        logger.warning(f"🚨 HUMAN HANDOFF REQUESTED for {phone}. Reason: {reason}")
        return "Please inform the user that their concern is very important, and you are transferring them to a human coordinator who will reply to this chat shortly."
    except Exception as e:
        logger.error(f"Handoff error: {e}")
        return "Handoff failed, but tell the user someone will contact them."

@tool
def reschedule_booking(phone: str, booking_id: int, new_class_id: int, parent_name: str, student_name: str) -> str:
    """Reschedules an existing booking to a new class ID in one step."""
    try:
        bookings = _db_run(_get_bookings_async(phone))
        target_booking = next((b for b in bookings if b.id == booking_id), None)
        if not target_booking:
            return "Could not find the original booking to reschedule."

        _db_run(_cancel_booking_async(booking_id))

        return book_trial.invoke({
            "phone": phone, 
            "parent_name": parent_name, 
            "student_name": student_name, 
            "class_id": new_class_id, 
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
        temperature=0.0,
        max_tokens=1500,
    )
    tools = [
        query_knowledge_base, get_lead_info, save_lead, check_available_classes, book_trial,
        check_my_booking, request_human_handoff, reschedule_booking
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
        if not output:
            logger.warning("Agent returned empty output")
            return "Maaf, saya tidak dapat menjawab sekarang. Sila hantar semula mesej anda. 🙏\nSorry, I couldn't answer that. Could you please send your message again?"
        return output
    except Exception as e:
        logger.error(f"Agent error: {e}")
        return "Maaf, berlaku ralat. Sila cuba lagi. 🙏\nSorry, something went wrong. Please try again."