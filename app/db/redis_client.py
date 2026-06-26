import json
import redis.asyncio as aioredis
from app.config import settings

# Conversation window — keep last N messages to avoid token bloat
MAX_HISTORY = 20
TTL_SECONDS = 60 * 60 * 24  # 24 hours per conversation

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


def _key(phone: str) -> str:
    """Redis key format: convo:<phone_number>"""
    clean = phone.replace("whatsapp:", "").replace("+", "")
    return f"convo:{clean}"


async def get_conversation_history(phone: str) -> list[dict]:
    """
    Returns the last MAX_HISTORY messages for this phone number.
    Each message is {"role": "user"|"assistant", "content": "..."}
    """
    r = await get_redis()
    raw = await r.lrange(_key(phone), -MAX_HISTORY, -1)
    return [json.loads(m) for m in raw]


async def save_message(phone: str, role: str, content: str) -> None:
    """Append a message to the conversation history and reset TTL."""
    r = await get_redis()
    key = _key(phone)
    msg = json.dumps({"role": role, "content": content})
    await r.rpush(key, msg)
    await r.expire(key, TTL_SECONDS)


async def clear_conversation(phone: str) -> None:
    """Wipe conversation history (e.g. after a booking is complete)."""
    r = await get_redis()
    await r.delete(_key(phone))
