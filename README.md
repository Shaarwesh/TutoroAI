# EduBot 🤖
### Bilingual WhatsApp Sales & Booking Agent for Tuition Centres

An autonomous AI agent that qualifies leads, answers questions in **English and Bahasa Malaysia**, and books trial class appointments — all within a WhatsApp conversation.

---

## Tech Stack

| Layer | Tech |
|---|---|
| WhatsApp | Twilio Sandbox → Meta Cloud API |
| API Server | FastAPI + Uvicorn |
| AI Brain | Groq (Llama 3.3 70B) + LangChain Agent |
| Knowledge Base | FAISS + Sentence Transformers |
| State | Redis (conversation memory, 24hr TTL) |
| Leads & Bookings | PostgreSQL + SQLAlchemy (async) |
| Calendar | Google Calendar API |
| Deployment | Railway |

---

## Agent Tools

- `query_knowledge_base` — answers questions about subjects, fees, teachers, schedules
- `check_availability` — queries Google Calendar for open trial slots
- `book_appointment` — creates calendar event + saves booking to PostgreSQL
- `save_lead` — captures partial lead data mid-conversation

---

## Setup

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in your keys

# 3. Run locally
uvicorn app.main:app --reload --port 8000

# 4. Expose with ngrok (for Twilio webhook)
ngrok http 8000
# Set webhook URL in Twilio console:
# https://<your-ngrok>.ngrok.io/webhook/whatsapp
```

---

## Project Structure

```
edubot/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings (pydantic)
│   ├── routers/
│   │   └── webhook.py       # Twilio WhatsApp webhook
│   ├── agents/
│   │   └── sales_agent.py   # LangChain agent
│   ├── tools/               # Agent tools (RAG, Calendar, DB)
│   ├── models/              # SQLAlchemy models
│   │   ├── lead.py
│   │   └── booking.py
│   └── db/
│       ├── postgres.py      # Async DB engine
│       └── redis_client.py  # Conversation state
├── knowledge_base/
│   └── docs/                # Tuition centre FAQ documents
├── tests/
├── requirements.txt
└── .env.example
```
