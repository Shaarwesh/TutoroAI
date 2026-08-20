# TUTORO AI 🤖

### WhatsApp Sales & Booking Agent for Tuition Centres

**TUTORO AI** is an autonomous AI agent that operates on WhatsApp to handle the full customer journey for a tuition centre — from the first enquiry to a confirmed trial class booking — without any human involvement.

Rather than a simple FAQ chatbot, TUTORO AI combines **lead qualification, bilingual conversation, RAG-grounded question answering, Google Calendar booking, and a real-time admin dashboard** to replace the manual WhatsApp management that small tuition businesses currently do by hand.

The agent is deployed on **WhatsApp via Twilio**, powered by **Groq (Llama 3.3 70B)** with a **LangChain agent framework**, and runs on **FastAPI** with **PostgreSQL, Redis, and Google Calendar** integrations.

---

## 🎥 Demo

> TUTORO AI completing a full registration and trial class booking autonomously via WhatsApp — from "Hi" to a confirmed Google Calendar event, entirely without human intervention.

**Proven end-to-end:** The agent collected a parent's name, child's details, form/year, contact info, email, home address, and subject preferences — calculated the correct monthly fee — then booked a real trial class directly into Google Calendar.

---

## 🎯 Project Background

Small tuition centres in Malaysia receive constant WhatsApp enquiries about subjects, fees, class schedules, and trial bookings. Staff manually reply to every message, ask the same qualifying questions repeatedly, and manually schedule appointments — a time-consuming process prone to missed leads and delayed responses.

TUTORO AI solves this by deploying an AI agent that handles the entire inbound sales flow autonomously, 24/7, in both English and Bahasa Malaysia — responding in the same language the customer uses.

The project demonstrates the practical application of agentic AI in a real business context, combining multiple production-grade integrations into a single, deployable system.

---

## 🎯 Project Objectives

1. **To design and build** an autonomous AI sales agent capable of qualifying leads, answering grounded questions, and booking appointments via WhatsApp.
2. **To demonstrate** bilingual conversational AI (English + Bahasa Malaysia) in a real Malaysian business context.
3. **To integrate** multiple production APIs (Twilio, Groq, Google Calendar, PostgreSQL, Redis) into a cohesive, deployable agentic system.
4. **To evaluate** the system's reliability and correctness through end-to-end testing with real calendar bookings and database persistence.

---

## ✨ Key Features

### 🗣️ Bilingual Conversation (English + Bahasa Malaysia)

TUTORO AI detects the language of each incoming message and responds entirely in the same language — English replies for English messages, full Bahasa Malaysia for Malay messages, with natural Manglish handling for mixed inputs.

---

### 🧠 RAG-Grounded Knowledge Base

Rather than relying on the LLM's general knowledge, TUTORO AI queries a **FAISS vector index** built from the tuition centre's own FAQ documents. This means:

* Fees and packages are always accurate (pulled from actual documents, not hallucinated)
* Subjects offered are never fabricated — if asked about Science (not offered), the bot correctly says so
* Schedule, teacher info, policies, and testimonials are all retrieved from real source documents

---

### 📋 Full Registration Flow

TUTORO AI guides customers through a structured registration process, collecting:

* Parent/guardian name
* Student name
* Form/year level
* Contact phone number
* Email address
* Home address
* Subject selection (with package pricing options shown as a numbered menu)

Each piece of information is saved to the database incrementally — even if the conversation is abandoned mid-flow, the data is preserved.

---

### 📅 Real Google Calendar Booking

When a customer confirms their registration, TUTORO AI:

1. Queries the connected Google Calendar for genuinely available trial slots
2. Presents real slots to the customer (never fabricated times)
3. Creates an actual calendar event with parent name, student name, subjects, and contact info
4. Sends an admin notification to the business owner's WhatsApp

---

### 🔄 Cancel & Reschedule

Customers can text "cancel my booking" or "I want to reschedule" at any time. TUTORO AI:

1. Looks up their existing booking by phone number
2. Cancels the Google Calendar event
3. Updates the database record
4. Notifies the admin
5. Offers new available slots for rescheduling

---

### 👨‍👩‍👧‍👦 Multi-Student Registration (Siblings)

A parent registering more than one child is handled natively — the first child goes through the standard flow, and TUTORO AI prompts for additional children and registers each with their own subjects and form level under the same parent record.

---

### ⏳ Waitlist Handling

When no trial slots are available in the next 7 days, TUTORO AI offers to add the customer to a waitlist rather than simply turning them away, capturing leads that would otherwise be lost.

---

### 🔔 Admin Notifications

Every new booking and every cancellation triggers an instant WhatsApp message to the configured admin number, including full customer details and the booked slot. Business owners are always informed in real time without checking any dashboard.

---

### ⏰ Automated Reminders

A built-in reminder system checks for upcoming trial classes and sends WhatsApp reminders to customers approximately 24 hours before their appointment. Triggered via a protected API endpoint suitable for scheduled jobs.

---

### 📊 Analytics Dashboard

A live analytics dashboard accessible via browser shows:

* Total leads captured
* Trial bookings confirmed
* Conversion rate (lead → booking percentage)
* Most requested subjects (ranked bar chart)
* Recent enquiries with stage badges

Styled as a "Weekly Report Card" theme appropriate for an education business context.

---

### 🔁 Returning Customer Recognition

TUTORO AI identifies returning customers by phone number at the start of every conversation. Returning customers are greeted by name and offered to update their information or book a new trial class — without being asked to re-enter details already on file.

---

## 🏗️ System Architecture

```
Customer's WhatsApp message
        │
        ▼
Twilio Webhook → FastAPI (/webhook/whatsapp)
        │
        ▼
Load conversation history from Redis (24hr TTL, per phone number)
        │
        ▼
LangChain Agent (Groq — Llama 3.3 70B) decides which tool(s) to call:
    ├── get_lead_info          → check if returning customer (PostgreSQL)
    ├── query_knowledge_base   → RAG lookup for fees/subjects/schedule (FAISS)
    ├── save_lead              → save/update registration details (PostgreSQL)
    ├── check_availability     → fetch real open slots (Google Calendar API)
    ├── book_trial              → create Calendar event + save booking (PostgreSQL)
    ├── cancel_my_booking      → cancel Calendar event + update record
    ├── add_sibling            → register additional child under same parent
    ├── join_waitlist          → add to waitlist when no slots available
    └── check_my_booking       → look up existing booking details
        │
        ▼
Agent's text reply → saved to Redis → sent back via Twilio → customer sees it on WhatsApp
        │
        ▼
Admin notification → business owner's WhatsApp (on booking/cancellation)

```

---

## 🗄️ Database Schema

```
PostgreSQL
│
├── leads
│   ├── id, phone (unique), name (parent)
│   ├── email, address, language
│   ├── child_name, child_age (primary child)
│   ├── subjects, notes
│   └── stage (new → qualified → confirmed → booked → cancelled)
│
├── bookings
│   ├── id, lead_id (FK), phone
│   ├── appointment_start, appointment_end
│   ├── subjects, google_event_id
│   └── status (confirmed / cancelled)
│
├── students
│   ├── id, lead_id (FK)
│   ├── name, form_year, subjects
│   └── created_at
│
└── waitlist
    ├── id, phone, parent_name, student_name
    ├── subjects, preferred_day
    └── notified (boolean)

Redis
└── convo:{phone_number}   → conversation history list (JSON messages, 24hr TTL)

```

---

## 🛠️ Technology Stack

| Technology | Purpose |
| --- | --- |
| **FastAPI + Uvicorn** | Async API server, Twilio webhook receiver |
| **LangChain** | Agent framework, tool orchestration |
| **Groq API (Llama 3.3 70B)** | LLM backbone for agent reasoning and tool-calling |
| **FAISS** | Local vector store for RAG knowledge base |
| **Sentence Transformers** | Multilingual embeddings (paraphrase-multilingual-MiniLM-L12-v2) |
| **Twilio WhatsApp API** | Inbound/outbound WhatsApp messaging |
| **Google Calendar API** | Real availability checking and event creation |
| **PostgreSQL + SQLAlchemy** | Async relational database for leads and bookings |
| **Redis (Upstash)** | Conversation state management |
| **Railway** | Cloud deployment platform |
| **Pydantic + pydantic-settings** | Configuration and validation |
| **Python 3.11** | Primary programming language |
| **Git + GitHub** | Version control |

---

## 📂 Project Structure

```
tutoro-ai/
├── app/
│   ├── main.py                     # FastAPI entry point, admin endpoints
│   ├── config.py                   # Settings (reads from .env)
│   ├── routers/
│   │   └── webhook.py              # Twilio WhatsApp webhook handler
│   ├── agents/
│   │   └── sales_agent.py          # LangChain agent + all tools
│   ├── tools/
│   │   ├── knowledge_base.py      # FAISS RAG setup and query
│   │   ├── calendar_tool.py        # Google Calendar integration
│   │   ├── notifications.py        # Admin WhatsApp alerts
│   │   ├── reminders.py            # 24hr reminder system
│   │   └── analytics.py            # Lead/booking metrics
│   ├── models/
│   │   ├── lead.py                 # Lead SQLAlchemy model
│   │   ├── booking.py              # Booking SQLAlchemy model
│   │   ├── student.py              # Student (sibling) model
│   │   └── waitlist.py             # Waitlist model
│   ├── db/
│   │   ├── postgres.py             # Async DB engine + table creation
│   │   ├── redis_client.py         # Conversation state
│   │   ├── crud_lead.py            # Lead CRUD operations
│   │   ├── crud_booking.py         # Booking CRUD operations
│   │   └── crud_student.py         # Student CRUD operations
│   └── static/
│       └── dashboard.html          # Visual analytics dashboard
├── knowledge_base/
│   ├── docs/
│   │   ├── faq_english.md          # Tuition centre FAQ (English)
│   │   └── faq_malay.md            # Tuition centre FAQ (Bahasa Malaysia)
│   └── index/                      # Pre-built FAISS vector index
├── tests/
│   ├── test_phase3_db.py           # PostgreSQL CRUD tests
│   ├── test_phase5_agent.py        # Full end-to-end agent test
│   ├── test_phase5_smoke.py        # Quick agent smoke test
│   ├── test_phase6_calendar.py     # Google Calendar integration test
│   └── test_booking_only.py        # Isolated booking step test
├── requirements.txt
├── railway.json                    # Railway deployment config
├── .env.example                    # Environment variable template
├── .gitignore
└── README.md

```

---

## 🚀 Getting Started

### Prerequisites

* Python 3.11
* PostgreSQL (local or hosted)
* Redis (local or Upstash)
* Twilio account (WhatsApp Sandbox for development)
* Google Cloud project with Calendar API enabled + service account
* Groq API key

Verify Python:

```bash
python --version

```

---

### Clone the Repository

```bash
git clone https://github.com/Shaarwesh/tutoro-ai.git
cd tutoro-ai

```

### Install Dependencies

```bash
pip install -r requirements.txt

```

### Configure Environment Variables

```bash
cp .env.example .env
# Fill in your actual values in .env

```

Required variables:

```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=
GROQ_API_KEY=
DATABASE_URL=
REDIS_URL=rediss://...
GOOGLE_CALENDAR_ID=
GOOGLE_SERVICE_ACCOUNT_FILE=app/credentials/google_service_account.json
ADMIN_WHATSAPP_NUMBER=whatsapp:+60xxxxxxxxx
APP_ENV=development
SECRET_KEY=your_random_secret

```

### Build the Knowledge Base Index

```bash
python -m app.tools.knowledge_base

```

### Start the Server

```bash
uvicorn app.main:app --reload --port 8000

```

### Expose via ngrok (for Twilio webhook testing)

```bash
ngrok http 8000
# Set webhook URL in Twilio console:
# https://<your-ngrok>.ngrok.io/webhook/whatsapp

```

---

## 🧪 Testing

TUTORO AI was tested across all major functional modules:

| Test | File | What it validates |
| --- | --- | --- |
| Database CRUD | `test_phase3_db.py` | Lead + booking creation, updates, queries |
| Calendar integration | `test_phase6_calendar.py` | Real slot fetching, event creation, cancellation |
| Agent smoke test | `test_phase5_smoke.py` | Tool-calling with 4 messages, token-efficient |
| Full flow test | `test_phase5_agent.py` | Complete registration → booking in one conversation |
| Booking step | `test_booking_only.py` | Isolated Calendar booking confirmation |

Run any test:

```bash
python tests/test_phase5_agent.py

```

Testing confirmed end-to-end reliability including:

* Correct data extraction from packed natural-language messages
* Accurate fee calculation from the knowledge base
* Real Google Calendar events with correct parent/student/subject data
* Returning customer recognition across sessions
* Error recovery when Groq temporarily fails (self-correction behavior)

---

## 📊 Admin Dashboard

Access the visual analytics dashboard in any browser:

```
https://your-deployment-url.up.railway.app/admin/dashboard?key=YOUR_SECRET_KEY

```

Shows:

* Total leads, trial bookings, conversion rate, pipeline count
* Most requested subjects (ranked bar chart)
* Recent enquiries with stage badges (new / qualified / confirmed / booked)

---

## ⚠️ Current Limitations

### Groq Free Tier Rate Limits

The Groq free tier allows 100,000 tokens/day on the Llama 3.3 70B model. Each agent turn consumes approximately 2,000-4,000 tokens (system prompt + tool schemas + conversation history + RAG context). For production use, a paid Groq plan or alternative provider is recommended.

### In-Memory Slot Cache

The `_slot_cache` that maps shown calendar slot numbers to actual datetime objects is stored in-process memory. A server restart between showing slots and a customer picking one would invalidate the cache. Moving this to Redis (already used for conversation state) is the recommended fix before full production deployment.

### FAISS Index Rebuild on Cold Start

On deployments without a pre-built FAISS index (e.g. fresh Railway deployments), the embedding model must download and build the index from scratch on startup, which requires ~1GB RAM and ~30 seconds. The pre-built index files should be committed or cached to avoid this on every deploy.

---

## 🔮 Future Improvements

Potential extensions include:

* **Multi-tenant architecture** — one deployment serving multiple tuition centres / salons / businesses with isolated knowledge bases and configurations
* **Payment integration** — DuitNow/ToyyibPay/Billplz link sent post-booking for the registration fee
* **Voice note transcription** — Whisper API transcription of customer voice notes (Twilio supports media URLs)
* **Sentiment-aware escalation** — automatic handoff to human staff if the agent detects customer frustration
* **Regular class booking** — beyond trial sessions, full recurring weekly class scheduling
* **Parent portal** — a shareable link showing booking status, upcoming classes, and payment history
* **Weekly broadcast messages** — business owner sends promotional WhatsApp blasts to all leads
* **Google Sheets sync** — automatic lead export for businesses using existing spreadsheet workflows

---

## 🎓 Project Context

**Project Name:** TUTORO AI — WhatsApp Sales & Booking Agent

**Project Type:** Personal Project (AI Software Development)

**Application Type:** Agentic AI System — WhatsApp Automation

**Deployment Platform:** Railway

**Primary Language:** Python 3.11

This project demonstrates practical application of:

* Agentic AI architecture (LangChain tool-calling agents)
* Retrieval-Augmented Generation (RAG) with FAISS
* Production API integrations (Twilio, Google Calendar, Groq)
* Async Python web development (FastAPI + SQLAlchemy async)
* Multi-database state management (PostgreSQL + Redis)
* Bilingual NLP for English and Bahasa Malaysia
* Cloud deployment and environment management

---

## 👩‍💻 Development

TUTORO AI was developed to explore the practical application of large language model agents in a real Malaysian SME business context — specifically the WhatsApp-first communication culture of small businesses in Malaysia, where most customer interaction happens via WhatsApp rather than web forms or phone calls.

The project bridges the gap between enterprise-grade AI agent tools (LangChain, Groq, FAISS) and accessible small-business automation — demonstrating that production-quality AI agents are buildable and deployable at minimal cost for real business use cases.

---

## 📄 License

This project was developed for educational and portfolio purposes.

Source code and project materials should not be redistributed, commercially used, or reproduced without permission.

---

*Built by [Shaarweshwary Saravanan (Shaw)*](https://github.com/Shaarwesh)
