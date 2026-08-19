"""
Quick smoke test — just 4 messages to verify tool calls fire correctly.
Cheaper than the full flow test. Run this first.
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.sales_agent import run_agent

PHONE = "whatsapp:+60177777777"

async def chat(message: str, history: list) -> str:
    print(f"\n👤 User: {message}")
    reply = await run_agent(PHONE, message, history)
    print(f"🤖 tutoro: {reply}")
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    return reply

async def main():
    print("\n🧪 SMOKE TEST — 4 messages only\n" + "="*40)
    h = []
    await chat("Hi", h)
    await chat("I want to register my child", h)
    await chat("My name is Wei Ling", h)
    await chat("My son's name is Marcus", h)
    print("\n" + "="*40)
    print("✅ Smoke test done — check if save_lead was actually invoked above")

if __name__ == "__main__":
    asyncio.run(main())
