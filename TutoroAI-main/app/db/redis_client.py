import json
import logging
import redis.asyncio as redis
from redis import Redis
from app.config import settings

logger = logging.getLogger(__name__)

# Async client for FastAPI routes and agent history
_redis_async = None
# Sync client for tools (if needed)
_redis_sync = None

if settings.redis_url:
    _redis_async = redis.from_url(settings.redis_url, decode_responses=True)
    _redis_sync = Redis.from_url(settings.redis_url, decode_responses=True)

async def get_conversation_history(phone: str, limit: int = 10) -> list[dict]:
    """Retrieve recent conversation history for the agent."""
    if not _redis_async:
        return []
    try:
        raw_msgs = await _redis_async.lrange(f"chat_history:{phone}", -limit, -1)
        return [json.loads(m) for m in raw_msgs]
    except Exception as e:
        logger.error(f"Failed to get Redis history for {phone}: {e}")
        return []

async def save_message(phone: str, role: str, content: str):
    """Save a single message to the user's conversation history."""
    if not _redis_async:
        return
    try:
        msg = json.dumps({"role": role, "content": content})
        key = f"chat_history:{phone}"
        await _redis_async.rpush(key, msg)
        # Keep only the last 30 messages to save memory
        await _redis_async.ltrim(key, -30, -1)
        # Expire history after 24 hours of inactivity
        await _redis_async.expire(key, 86400)
    except Exception as e:
        logger.error(f"Failed to save Redis history for {phone}: {e}")

async def clear_conversation_history(phone: str):
    """Wipes the conversation history for a specific user to start fresh."""
    if _redis_async:
        try:
            await _redis_async.delete(f"chat_history:{phone}")
        except Exception as e:
            logger.error(f"Failed to clear Redis history for {phone}: {e}")

def save_user_slots(phone: str, slots: list):
    """Save available trial slots for a user."""
    if not _redis_sync:
        return
    try:
        key = f"slots:{phone}"
        _redis_sync.set(key, json.dumps(slots), ex=1800)  # Expire in 30 minutes
    except Exception as e:
        logger.error(f"Failed to save slots for {phone}: {e}")

def get_user_slots(phone: str) -> list:
    """Retrieve saved trial slots for a user."""
    if not _redis_sync:
        return []
    try:
        data = _redis_sync.get(f"slots:{phone}")
        return json.loads(data) if data else []
    except Exception as e:
        logger.error(f"Failed to get slots for {phone}: {e}")
        return []

def clear_user_slots(phone: str):
    """Clear saved trial slots after booking."""
    if _redis_sync:
        try:
            _redis_sync.delete(f"slots:{phone}")
        except Exception as e:
            logger.error(f"Failed to clear slots for {phone}: {e}")

async def pause_bot(phone: str, hours: int = 24):
    """Pauses the AI for a specific user so a human can take over."""
    if _redis_async:
        try:
            await _redis_async.set(f"paused:{phone}", "true", ex=hours * 3600)
        except Exception as e:
            logger.error(f"Failed to pause bot for {phone}: {e}")

async def is_bot_paused(phone: str) -> bool:
    """Checks if the bot is currently paused for this user."""
    if not _redis_async:
        return False
    try:
        return await _redis_async.exists(f"paused:{phone}") > 0
    except Exception as e:
        logger.error(f"Failed to check pause status for {phone}: {e}")
        return False