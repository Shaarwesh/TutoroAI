from fastapi import APIRouter, Request, Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator

from app.config import settings
from app.agents.sales_agent import run_agent
from app.db.redis_client import get_conversation_history, save_message, clear_conversation_history, _redis_async, is_bot_paused
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Define the trigger words that will reset the conversation
RESET_TRIGGERS = {"start over", "restart", "reset", "mula semula", "batal"}

def validate_twilio_request(request: Request, form_data: dict) -> bool:
    """Validate that the request is genuinely from Twilio."""
    if settings.app_env == "development":
        return True  # Skip validation in dev
        
    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    
    # CRITICAL FIX FOR RAILWAY/PRODUCTION DEPLOYMENTS:
    # Load balancers terminate SSL and pass HTTP to FastAPI.
    # Twilio signs the payload using the original HTTPS URL.
    url = str(request.url)
    if "localhost" not in url and url.startswith("http://"):
        url = url.replace("http://", "https://", 1)
        
    return validator.validate(url, form_data, signature)

@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Main entry point for all incoming WhatsApp messages via Twilio.
    Twilio sends a POST with form-encoded data.
    """
    form_data = dict(await request.form())

    # 1. Validate it's really Twilio
    if not validate_twilio_request(request, form_data):
        logger.warning(f"🚨 Invalid Twilio signature detected from IP: {request.client.host} — request rejected")
        return Response(content="Forbidden", status_code=403)

    # 2. Extract message details
    sender    = form_data.get("From", "")   # e.g. whatsapp:+60123456789
    message   = form_data.get("Body", "").strip()
    media_url = form_data.get("MediaUrl0")  # image/voice if sent

    # --- 3. RATE LIMITING (Max 15 requests per 60 seconds per user) ---
    if _redis_async and sender:
        rl_key = f"rate_limit:{sender}"
        req_count = await _redis_async.incr(rl_key)
        
        # If it's the first request in the window, set the expiration timer
        if req_count == 1:
            await _redis_async.expire(rl_key, 60)
            
        # If they breached the limit, throttle them instantly
        if req_count > 15:
            logger.warning(f"🛑 Rate limit exceeded for {sender} ({req_count} requests/min)")
            return _twiml_reply(
                "Sila tunggu sebentar sebelum menghantar mesej lagi. ⏳\n"
                "Please wait a moment before sending more messages."
            )
    # -----------------------------------------------------------------

    # --- HUMAN HANDOFF INTERCEPTOR ---
    if await is_bot_paused(sender):
        logger.info(f"⏸️ Bot is paused for {sender}. Waiting for human response.")
        # Return an empty response so Twilio knows we received it, but the AI stays quiet.
        return Response(status_code=200) 

    logger.info(f"📩 Message from {sender}: {message}")

    if not message and not media_url:
        return _twiml_reply("Maaf, saya tidak dapat membaca mesej anda. / Sorry, I couldn't read your message.")

    # --- 4. HARD RESET INTERCEPTOR ---
    if message.lower() in RESET_TRIGGERS:
        await clear_conversation_history(sender)
        # Change the message under the hood so the agent knows to greet them freshly
        message = "Hi, I would like to start over with a new registration."
        logger.info(f"🔄 Hard reset triggered for {sender}")

    # 5. Load conversation history from Redis
    history = await get_conversation_history(sender)

    # 6. Run the LangChain agent
    try:
        reply = await run_agent(
            user_phone=sender,
            user_message=message,
            history=history,
        )
    except Exception as e:
        logger.error(f"Agent error for {sender}: {e}")
        reply = (
            "Maaf, berlaku ralat. Sila cuba lagi sebentar. 🙏\n"
            "Sorry, something went wrong. Please try again shortly."
        )

    # 7. Persist this turn to Redis
    await save_message(sender, role="user", content=message)
    await save_message(sender, role="assistant", content=reply)

    return _twiml_reply(reply)

def _twiml_reply(message: str) -> Response:
    """Wrap a text reply in TwiML format that Twilio expects."""
    resp = MessagingResponse()
    resp.message(message)
    return Response(content=str(resp), media_type="application/xml")