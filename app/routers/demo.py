"""
Demo chat page for Tutoro AI (no Twilio, no WhatsApp message caps).
Enabled only when env DEMO_MODE=1.  Open  http://localhost:8000/demo
It runs the SAME pipeline as the WhatsApp webhook: Redis history -> sales agent -> tools -> reply.
"""
import hashlib, logging, os
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.agents.sales_agent import run_agent
from app.db.redis_client import get_conversation_history, save_message, clear_conversation_history, is_bot_paused

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demo", tags=["Demo"])
RESET = {"start over", "restart", "reset", "mula semula", "batal"}


class ChatIn(BaseModel):
    session: str
    message: str


def _phone(session: str) -> str:
    """Stable fake WhatsApp ID per browser session, same shape Twilio sends."""
    n = int(hashlib.sha1(session.encode()).hexdigest(), 16) % 10**9
    return f"whatsapp:+60{n:09d}"


@router.post("/chat")
async def chat(body: ChatIn):
    if os.getenv("DEMO_MODE") != "1":
        raise HTTPException(404)
    message, phone = body.message.strip(), _phone(body.session)
    if not message:
        raise HTTPException(400, "empty message")
    if await is_bot_paused(phone):
        return {"reply": "⏸️ A staff member has taken over this chat and will reply shortly.", "paused": True}
    if message.lower() in RESET:
        await clear_conversation_history(phone)
        message = "Hi, I would like to start over with a new registration."
    history = await get_conversation_history(phone)
    try:
        reply = await run_agent(user_phone=phone, user_message=message, history=history)
    except Exception as e:
        logger.error(f"Demo agent error: {e}")
        reply = "Maaf, berlaku ralat. Sila cuba lagi. 🙏 / Sorry, something went wrong."
    await save_message(phone, role="user", content=message)
    await save_message(phone, role="assistant", content=reply)
    return {"reply": reply}


@router.get("", response_class=HTMLResponse)
async def page():
    if os.getenv("DEMO_MODE") != "1":
        raise HTTPException(404)
    return PAGE


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Tutoro AI demo</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#d9d2c5;font-family:system-ui,Segoe UI,Roboto,sans-serif;display:flex;justify-content:center}
.app{width:100%;max-width:440px;height:100vh;display:flex;flex-direction:column;background:#efeae2}
header{background:#075e54;color:#fff;padding:12px 16px;display:flex;align-items:center;gap:12px}
.av{width:38px;height:38px;border-radius:50%;background:#25d366;display:grid;place-items:center;font-weight:700}
header b{display:block}header small{opacity:.8}
#log{flex:1;overflow-y:auto;padding:14px 12px;display:flex;flex-direction:column;gap:6px}
.m{max-width:82%;padding:8px 11px;border-radius:9px;font-size:14.5px;line-height:1.4;white-space:pre-wrap;word-wrap:break-word;box-shadow:0 1px 1px rgba(0,0,0,.12)}
.u{align-self:flex-end;background:#d9fdd3}.b{align-self:flex-start;background:#fff}
.t{color:#777;font-style:italic}
.chips{display:flex;gap:6px;flex-wrap:wrap;padding:6px 12px}
.chips button{border:1px solid #075e54;color:#075e54;background:#fff;border-radius:16px;padding:5px 10px;font-size:12.5px;cursor:pointer}
form{display:flex;gap:8px;padding:10px;background:#f0f0f0}
input{flex:1;border:0;border-radius:20px;padding:11px 14px;font-size:14.5px;outline:none}
form button{border:0;background:#075e54;color:#fff;border-radius:50%;width:42px;height:42px;font-size:18px;cursor:pointer}
</style></head><body><div class="app">
<header><div class="av">W</div><div><b>Wesh Tuition Centre</b><small>Tutoro AI · live demo</small></div></header>
<div id="log"></div>
<div class="chips" id="chips"></div>
<form id="f"><input id="i" placeholder="Type a message" autocomplete="off"><button>➤</button></form></div>
<script>
const sid=sessionStorage.sid||(sessionStorage.sid=Math.random().toString(36).slice(2)+Date.now());
const log=document.getElementById('log'),inp=document.getElementById('i');
const esc=s=>s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const fmt=s=>esc(s).replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>').replace(/\\*(.+?)\\*/g,'<b>$1</b>');
function add(t,cls,html){const d=document.createElement('div');d.className='m '+cls;html?d.innerHTML=fmt(t):d.textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight;return d}
async function send(text){
  if(!text.trim())return;add(text,'u');inp.value='';
  const w=add('typing…','b t');
  try{const r=await fetch('/demo/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session:sid,message:text})});
    const j=await r.json();w.remove();add(j.reply||'(no reply)','b',true)}
  catch(e){w.remove();add('Connection error','b')}
}
document.getElementById('f').onsubmit=e=>{e.preventDefault();send(inp.value)};
['How much are the fees?','Ada kelas Sains tak?','Do you teach Physics?','I want to book a trial class','start over'].forEach(t=>{
  const b=document.createElement('button');b.textContent=t;b.onclick=()=>send(t);document.getElementById('chips').appendChild(b)});
add('Hi! 👋 Welcome to Wesh Tuition Centre. Ask me about fees, subjects, or book a free trial. / Boleh tanya dalam Bahasa Melayu juga!','b');
</script></body></html>"""
