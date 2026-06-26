from fastapi import APIRouter, Request, Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator

from app.config import settings
from app.agents.sales_agent import run_agent
from app.db.redis_client import get_conversation_history, save_message
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def validate_twilio_request(request: Request, form_data: dict) -> bool:
    """Validate that the request is genuinely from Twilio."""
    if settings.app_env == "development":
        return True  # Skip validation in dev
    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    return validator.validate(str(request.url), form_data, signature)


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Main entry point for all incoming WhatsApp messages via Twilio.
    Twilio sends a POST with form-encoded data.
    """
    form_data = dict(await request.form())

    # Validate it's really Twilio
    if not validate_twilio_request(request, form_data):
        logger.warning("Invalid Twilio signature — request rejected")
        return Response(content="Forbidden", status_code=403)

    # Extract message details
    sender    = form_data.get("From", "")   # e.g. whatsapp:+60123456789
    message   = form_data.get("Body", "").strip()
    media_url = form_data.get("MediaUrl0")  # image/voice if sent

    logger.info(f"📩 Message from {sender}: {message}")

    if not message and not media_url:
        return _twiml_reply("Maaf, saya tidak dapat membaca mesej anda. / Sorry, I couldn't read your message.")

    # Load conversation history from Redis
    history = await get_conversation_history(sender)

    # Run the LangChain agent
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

    # Persist this turn to Redis
    await save_message(sender, role="user", content=message)
    await save_message(sender, role="assistant", content=reply)

    return _twiml_reply(reply)


def _twiml_reply(message: str) -> Response:
    """Wrap a text reply in TwiML format that Twilio expects."""
    resp = MessagingResponse()
    resp.message(message)
    return Response(content=str(resp), media_type="application/xml")
