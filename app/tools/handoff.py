from langchain_core.tools import tool
from app.db.redis_client import _redis_async

@tool
async def request_human_handoff(phone_number: str, reason: str) -> str:
    """
    Trigger this tool IMMEDIATELY if a parent expresses anger, anxiety, 
    frustration, or concerns about their child's falling grades.
    """
    # Pause the bot for this specific user in Redis for 24 hours (86400 seconds)
    if _redis_async:
        await _redis_async.setex(f"bot_paused:{phone_number}", 86400, "true")
    
    # In the future, you can add a Telegram/Email API call here to ping your phone
    print(f"🚨 HUMAN HANDOFF TRIGGERED for {phone_number}. Reason: {reason}")
    
    return "The bot has been paused. Tell the user exactly this: 'I completely understand your concerns. Let me pause my automated responses and connect you directly with our centre manager, who will text you shortly to help sort this out.'"