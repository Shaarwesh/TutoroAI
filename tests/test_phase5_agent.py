"""
Phase 5 test — SHORT version, single conversation, minimal tokens.
Combines multiple details per message to cut down on LLM calls.
Usage: python tests/test_phase5_agent.py
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.sales_agent import run_agent

PHONE = "whatsapp:+60188123456"

async def chat(message: str, history: list) -> str:
    print(f"\n👤 User: {message}")
    reply = await run_agent(PHONE, message, history)
    print(f"🤖 tutoro: {reply}")
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    return reply


async def main():
    print("\n" + "="*50)
    print("SHORT TEST — single conversation, minimal messages")
    print("="*50)
    h = []
    await chat("Hi, I want to register my child. My name is Farah, my daughter Aina is in Form 2, my number is 0123456789, email farah@gmail.com, address No 12 Jalan Mawar Melaka", h)
    await chat("English and Mathematics please", h)
    await chat("CONFIRM", h)
    await chat("1", h)  # Pick whichever slot is #1 in the real Calendar list shown
    print("\n" + "="*50)
    print("✅ Test done!")


if __name__ == "__main__":
    asyncio.run(main())
