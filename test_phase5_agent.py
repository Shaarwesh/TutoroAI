"""
Phase 5 test — full registration flow including confirm/cancel + returning customer.
Usage: python tests/test_phase5_agent.py
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.sales_agent import run_agent

PHONE = "whatsapp:+60199001122"

async def chat(message: str, history: list) -> str:
    print(f"\n👤 User: {message}")
    reply = await run_agent(PHONE, message, history)
    print(f"🤖 tutoro: {reply}")
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    return reply


async def test_new_customer():
    print("\n" + "="*50)
    print("TEST 1 — New customer full registration flow")
    print("="*50)
    h = []
    await chat("Hi", h)
    await chat("I want to register my child for tuition", h)
    await chat("My name is Farah", h)
    await chat("My daughter's name is Aina", h)
    await chat("She's in Form 2", h)
    await chat("My number is 0123456789", h)
    await chat("farah@gmail.com", h)
    await chat("No 12, Jalan Mawar, Melaka", h)
    await chat("1 3", h)  # English + Mathematics
    await chat("CONFIRM", h)
    await chat("3", h)    # Pick slot 3 — Saturday 10am


async def test_returning_customer():
    print("\n" + "="*50)
    print("TEST 2 — Returning customer (same number)")
    print("="*50)
    h = []
    await chat("Hi semula", h)


async def main():
    await test_new_customer()
    await test_returning_customer()
    print("\n" + "="*50)
    print("✅ All tests done!")


if __name__ == "__main__":
    asyncio.run(main())
