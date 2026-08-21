import sys
import os

# Add the parent directory (tutoro) to Python's module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.agents.sales_agent import run_agent

async def run_automated_tests():
    print("🚀 STARTING AUTOMATED TUTORO AI TESTS...\n" + "="*50)
    
    # Use a unique test phone number
    test_phone = "whatsapp:+60199999999"
    chat_history = []

    # A sequence of simulated user messages representing a full registration journey
    test_steps = [
        "Hi, I want to register. How much are your monthly fees?",
        "My name is Wesh, and I want to register my sister Swesh. She is in Form 4.",
        "My email is wesh@example.com and we live in Melaka. We want to take Mathematics.",
        "CONFIRM",
        "I want to book Class ID 1" # (Make sure you have a class with ID 1 in your DB!)
    ]

    for i, message in enumerate(test_steps, 1):
        print(f"\n[Step {i}] 👤 User: {message}")
        
        try:
            # Run the agent with current conversation history
            reply = await run_agent(
                user_phone=test_phone,
                user_message=message,
                history=chat_history
            )
            
            print(f"[Step {i}] 🤖 TUTORO: {reply}")
            print("-" * 50)

            # Append to history so context is preserved for the next step
            chat_history.append({"role": "user", "content": message})
            chat_history.append({"role": "assistant", "content": reply})
            
            # Brief pause between simulated steps
            await asyncio.sleep(1)

        except Exception as e:
            print(f"❌ Error at Step {i}: {e}")
            break

    print("\n✅ Automated test sequence finished! Check your database dashboard to see the new lead and booking.")

if __name__ == "__main__":
    asyncio.run(run_automated_tests())