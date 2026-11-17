"""
Run from the repo root:  python apply_ux_fixes.py     (backup: sales_agent.py.bak3; safe to re-run)
1. Fixes DUPLICATE leads / re-asked questions: every tool now uses the real WhatsApp ID, never the
   model's copy (the model sometimes dropped the "whatsapp:" prefix, so data got saved under two phones).
2. Makes the registration conversation sound human: asks for the person's name, then whether they are
   a parent or a student, one question at a time, no repeated filler.
"""
from pathlib import Path
import re, shutil, sys

AGENT = Path("app/agents/sales_agent.py")
if not AGENT.exists(): sys.exit("Run from the repo root (app/agents/sales_agent.py not found).")
bak = AGENT.with_suffix(".py.bak3")
if not bak.exists(): shutil.copy(AGENT, bak)

def replace_once(old, new, label, marker):
    s = AGENT.read_text(encoding="utf-8")
    if marker in s: print(f"[skip] {label}"); return
    if s.count(old) != 1: sys.exit(f"[FAIL] {label}: found {s.count(old)} matches. Paste me that part of sales_agent.py.")
    AGENT.write_text(s.replace(old, new), encoding="utf-8"); print(f"[ok]   {label}")

# ---------------------------------------------------------------- 1. real phone everywhere
BLOCK = '''
# ── Always use the REAL WhatsApp ID (the model sometimes changes or drops the prefix) ─────────
import contextvars
_CURRENT_PHONE = contextvars.ContextVar("current_phone", default=None)

def _real_phone(arg=None):
    cur = _CURRENT_PHONE.get()
    if cur:
        return cur
    p = (arg or "").strip()
    if p and not p.startswith("whatsapp:"):
        p = "whatsapp:" + (p if p.startswith("+") else "+" + p.lstrip("+"))
    return p

def _with_real_phone(fn):
    def inner(phone, *a, **kw):
        return fn(_real_phone(phone), *a, **kw)   # resolved in the tool's thread, then returns the coroutine
    return inner

for _n in ("_get_lead", "_save_lead_async", "_save_booking_async", "_get_bookings_async",
           "_add_sibling_async", "_join_waitlist_async"):
    if _n in globals():
        globals()[_n] = _with_real_phone(globals()[_n])

def _invoke_with_phone(agent, phone, payload):
    _CURRENT_PHONE.set(phone)
    return agent.invoke(payload)

'''
s = AGENT.read_text(encoding="utf-8")
if "_CURRENT_PHONE" in s: print("[skip] real-phone block")
else:
    m = re.search(r"\n# ── Agent ─", s)
    if not m: sys.exit("[FAIL] '# ── Agent' marker not found")
    AGENT.write_text(s[:m.start()] + "\n" + BLOCK + s[m.start():], encoding="utf-8"); print("[ok]   real-phone block")

replace_once("lambda: agent.invoke({", "lambda: _invoke_with_phone(agent, user_phone, {",
             "run_agent sets the phone", "_invoke_with_phone(agent, user_phone")
replace_once("_db_run(pause_bot(phone))", "_db_run(pause_bot(_real_phone(phone)))",
             "handoff pauses the right chat", "pause_bot(_real_phone(phone))")

# ---------------------------------------------------------------- 2. human tone
replace_once(
"""3. Collect Parent Name (Save).
4. Collect Student Name (Save).
5. Collect Student Form/Year (Save).
6. Collect Email & Address (Save).""",
"""3. Ask for their name in a friendly way (e.g. "Could I get your name?") and save it.
4. Ask whether they are a parent registering a child, or a student registering for themselves (e.g. "Are you a parent registering your child, or a student registering yourself?"). If a parent, ask for the child's name next. If a student, their own name is also the student name.
5. Ask which form/year the student is in. When saving, pass child_age as the number only (Form 3 -> 3, Standard 5 -> 5).
6. Ask for an email address and a home address (the home address may be skipped).""",
"human registration questions", "Are you a parent registering your child")

replace_once(
"LANGUAGE RULE:\nYou MUST reply in the exact same language the user uses.",
"""HUMAN TONE (CRITICAL):
- Talk like a warm, friendly receptionist, not a form. Short natural sentences, ONE question at a time.
- Never write robotic requests like "please provide parent name" or "student name". Say things like "Could I get your name?" or "And what's your child's name?".
- In Malay, say it naturally too: "Boleh saya tahu nama anda?" / "Anda ibu bapa yang mendaftar untuk anak, atau pelajar yang mendaftar sendiri?"
- Never ask for something the customer already told you, or that get_lead_info or the chat history already shows. If they give several details in one message, accept all of them.
- Do not repeat what they just said back at length, and never add filler like "whenever you're ready".

LANGUAGE RULE:
You MUST reply in the exact same language the user uses.""",
"human tone section", "HUMAN TONE (CRITICAL)")

replace_once(
"Every time you execute a tool call, you MUST append a friendly, clear, non-empty text response back to the user explaining what was done or what step is next. Never leave an output message blank.",
"Your final reply to the customer must always be non-empty, friendly and clear. Send exactly ONE message per turn: never repeat yourself.",
"single non-empty reply rule", "Send exactly ONE message per turn")

print("\nDone. Restart uvicorn. Clean old duplicate test data with the SQL I gave you.")
