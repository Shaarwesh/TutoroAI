"""
Run from the repo root:  python apply_fixes.py
Patches app/agents/sales_agent.py and app/tools/knowledge_base.py in place (backups: *.bak).
Safe to re-run: it skips patches that are already applied.
"""
from pathlib import Path
import shutil, sys

AGENT = Path("app/agents/sales_agent.py")
KB = Path("app/tools/knowledge_base.py")
for p in (AGENT, KB):
    if not p.exists():
        sys.exit(f"Can't find {p}. Run this from C:\\Tutoro\\TutoroAI-main")

def patch(path, old, new, label):
    s = path.read_text(encoding="utf-8")
    if new in s:
        print(f"[skip] {label} (already applied)"); return
    if s.count(old) != 1:
        sys.exit(f"[FAIL] {label}: expected 1 match, found {s.count(old)}. Paste me that part of {path}.")
    path.write_text(s.replace(old, new), encoding="utf-8"); print(f"[ok]   {label}")

for p in (AGENT, KB):
    bak = p.with_suffix(p.suffix + ".bak")
    if not bak.exists(): shutil.copy(p, bak)

# 1. The agent must know the customer's WhatsApp ID (the 'phone' input was never used by the prompt)
patch(AGENT,
 'SYSTEM_PROMPT = """TUTORO AI — Official Sales & Registration Agent for Wesh Tuition Centre, Melaka.\n',
 'SYSTEM_PROMPT = """TUTORO AI — Official Sales & Registration Agent for Wesh Tuition Centre, Melaka.\n\n'
 'CUSTOMER WHATSAPP ID: {phone}\n'
 'Use this exact value as the `phone` parameter in EVERY tool call. NEVER ask the customer for their phone number; you already have it.\n',
 "inject WhatsApp ID into prompt")

# 2. Rule 1 contradicted the hardcoded facts: allow the prompt facts AND the KB
patch(AGENT,
 "using ONLY the facts retrieved from 'query_knowledge_base'.",
 "using ONLY the facts listed in this prompt or retrieved from 'query_knowledge_base' (call it for anything not listed here: policies, hours, location, payments).",
 "rule 1 allows prompt facts")

# 3. Missing facts + explicit don't-know rule + cannot-do rule
patch(AGENT,
 "- Discounts: We do not offer a 50% discount. Sibling discount is maximum 10%.\n",
 "- Discounts: We do not offer a 50% discount. Sibling discount is maximum 10%. No other discounts exist.\n"
 "- Registration fee: RM30 one-time for new students (includes a starter kit). Monthly fees are due by the 5th of each month.\n"
 "- Payment methods: cash, or online bank transfer (TNG, DuitNow).\n"
 "- Hours: Monday-Friday 2:00 PM-6:00 PM, Saturday 9:00 AM-1:00 PM, closed Sunday. Each class is 1 hour per subject, max 10 students per class.\n"
 "- Free parking outside the centre. The first trial class is FREE with no commitment. Location is Melaka only.\n"
 "- If something is NOT stated here or in the knowledge base (public holidays, exact street address, teacher details, other branches), say you do not have that information and offer to have our staff follow up. NEVER invent policies, prices or branches.\n"
 "- You CANNOT cancel bookings or manage waitlists. For those requests, call request_human_handoff and tell the customer our staff will assist. Never claim a cancellation or waitlist spot was made.\n",
 "add missing facts and don't-know rule")

# 4. Reasoning model was running out of tokens -> empty / cut-off replies
patch(AGENT, "max_tokens=450,", "max_tokens=1500,", "raise max_tokens")

# 5. Empty-output fallback must not read like a booking confirmation
patch(AGENT,
 "return \"Terima kasih! Maklumat anda telah diproses. Sila nyatakan subjek pilihan atau taip 'CONFIRM' untuk meneruskan. 😊\"",
 "logger.warning(\"Agent returned empty output\")\n"
 "            return \"Maaf, saya tidak dapat menjawab sekarang. Sila hantar semula mesej anda. 🙏\\nSorry, I couldn't answer that. Could you please send your message again?\"",
 "safe empty-output fallback")

# 6. Retrieval: k=2 missed the payment-methods chunk
patch(KB, "def query_knowledge_base(question: str, k: int = 2) -> str:",
          "def query_knowledge_base(question: str, k: int = 4) -> str:", "retrieve k=4")

print("\nDone. Originals saved as *.bak. Now re-run the eval.")
