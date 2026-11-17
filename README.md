# 🤖 TUTORO AI
### Agentic WhatsApp Sales & Booking Assistant for Tuition Centres

**From customer enquiries to trial-class reservations — powered by conversational AI, RAG, and real-world integrations.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-Agent_Framework-blue)](https://langchain.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-Conversation_State-DC382D?logo=redis&logoColor=white)](https://redis.io)
![Status](https://img.shields.io/badge/Status-Active_Development-yellow)

**[GitHub Repository](https://github.com/Shaarwesh/TutoroAI)**

---

## 📖 Overview

**TUTORO AI** is an AI-powered WhatsApp assistant developed to automate customer enquiries, student registration, and trial-class booking for tuition centres.

Designed around the communication habits of Malaysian small businesses, TUTORO AI enables parents to interact with a tuition centre through natural WhatsApp conversations in **English or Bahasa Malaysia**.

Unlike a conventional rule-based chatbot, TUTORO AI uses a **LangChain tool-calling agent**, a **Retrieval-Augmented Generation (RAG) knowledge base**, and integrations with PostgreSQL and Google Calendar to perform actions beyond simply answering questions.

The system can retrieve tuition information, collect parent and student details, identify returning customers, check available classes, register siblings, manage waitlist requests, and create or cancel trial bookings.

A companion web-based administrative interface provides class management, student enquiry records, and basic analytics. This interface is currently being expanded.

**Project Type:** Personal AI Software Development Project  
**Application:** WhatsApp Automation and Tuition Centre Management  
**Primary Language:** Python 3.11  
**Deployment Configuration:** Railway  
**Development Status:** Core AI agent implemented; admin dashboard under development

---

## 🎯 Problem Statement

Small tuition centres often depend on staff to handle repetitive WhatsApp enquiries about class schedules, fees, subjects, and student registration.

This creates several operational challenges:

- Repeatedly answering identical customer questions.
- Manually collecting parent and student information.
- Tracking enquiries across different WhatsApp conversations.
- Checking class availability and coordinating trial appointments.
- Maintaining accurate booking and student records.
- Responding to customers outside normal business hours.

TUTORO AI explores how autonomous, tool-enabled AI agents can reduce this repetitive workload while preserving a conversational customer experience.

## 🎯 Project Objectives

1. Design an AI-powered WhatsApp assistant capable of conducting natural-language conversations and executing business actions through tools.
2. Implement RAG to answer tuition-related questions using a structured knowledge base.
3. Build a registration and trial-booking workflow supported by PostgreSQL and Google Calendar.
4. Support English and Bahasa Malaysia conversations for Malaysian users.
5. Develop an administrative interface for class scheduling, student records, and operational reporting.
6. Evaluate agent behaviour, retrieval quality, and integration reliability through development testing.

---

## ✨ Core Features

### 🗣️ 1. Conversational WhatsApp AI

TUTORO AI receives incoming WhatsApp messages through Twilio and processes them using a LangChain agent.

The agent can interpret natural-language enquiries, determine which tools are relevant, and generate responses based on the information returned.

The system includes:

- English and Bahasa Malaysia conversational support.
- Context-aware multi-turn conversations.
- Conversation history stored in Redis.
- Recognition of existing customer records.
- Conversation reset commands.
- Basic rate limiting and webhook validation.

The current agent is powered by **Groq's `openai/gpt-oss-120b` model**.

### 🧠 2. Retrieval-Augmented Generation (RAG)

TUTORO AI uses RAG to retrieve relevant tuition-centre information from local FAQ documents.

The knowledge base includes English and Bahasa Malaysia documents containing tuition-related information.

**RAG pipeline:**

1. Load tuition-centre FAQ documents.
2. Split documents into smaller text chunks.
3. Generate vector embeddings using FastEmbed.
4. Store embeddings in a FAISS vector index.
5. Retrieve relevant passages for incoming questions.
6. Provide retrieved context to the language-model agent.

**Current embedding model:** `BAAI/bge-small-en-v1.5`

**Vector database:** FAISS

This architecture helps ground the AI's answers in configured information rather than relying exclusively on general model knowledge.

### 👨‍👩‍👧 3. Lead and Student Registration

The agent can collect and save customer information during conversations.

Supported registration details include parent or guardian information, student names, educational levels, selected subjects, and contact information.

Lead records are stored in PostgreSQL, allowing the system to retrieve information when a customer returns.

### 📅 4. Trial-Class Booking

The booking workflow integrates the centre's class timetable with Google Calendar.

The application:

1. Retrieves available classes from PostgreSQL.
2. Checks a selected class's maximum capacity.
3. Verifies the parent's registration record.
4. Calculates the next occurrence of the selected class.
5. Checks Google Calendar availability.
6. Creates the Google Calendar event.
7. Saves the confirmed booking to PostgreSQL.
8. Updates the class's stored enrolled count.

The booking service uses the **Asia/Kuala_Lumpur** timezone and includes error handling for unsuccessful booking attempts.

### ❌ 5. Booking Cancellation

Customers can request cancellation of an existing booking.

The implemented cancellation service:

- Finds the customer's confirmed booking.
- Attempts to remove the associated Google Calendar event.
- Updates the booking status to `cancelled` when cancellation succeeds.

**Current limitation:** The cancellation workflow does not yet decrement the class's enrolled count. This remains an important synchronization improvement.

### 👨‍👩‍👧‍👦 6. Sibling Registration

The agent supports registration of additional students under an existing parent's record.

Each sibling can have separate details such as name, educational level, and selected subjects.

### ⏳ 7. Waitlist Management

When a suitable class is unavailable, the agent can collect a waitlist request.

The waitlist stores customer and student details, subject preferences, and preferred days where provided.

Automated notification when a seat becomes available is a future enhancement.

### 🙋 8. Human Handoff

The application includes an agent tool for requesting human assistance and Redis-based functionality for pausing bot responses.

The overall staff takeover and notification workflow requires further refinement.

### 📊 9. Administrative Dashboard

TUTORO AI includes an authenticated browser-based administrative interface.

Its current pages cover:

| Module | Current Functionality |
|---|---|
| Dashboard | Lead totals, class totals, booking counts, class schedule listing |
| Class Management | Add, edit, and delete class schedules |
| Students | Searchable list of parent and student enquiry records |
| Timetable | Dedicated page with basic class-count information |
| Analytics | Lead, booking, conversion, and popular-subject reporting |
| Authentication | Admin login, logout, sessions, and password recovery functionality |

**Development status:** The dashboard is functional in parts but is not yet a complete tuition management system.

Detailed clickable student profiles, a comprehensive weekly timetable, and fully synchronized class-capacity reporting remain in progress.

### 🔔 10. Reminder Generation

The project includes a module that identifies upcoming confirmed bookings and generates reminder records approximately 24 hours before their appointments.

The current implementation saves reminder information locally in JSON files.

**WhatsApp reminder delivery is not yet implemented in this module.**

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    A["Parent / Guardian"] --> B["WhatsApp / Twilio"]
    B --> C["FastAPI Webhook"]
    C <--> D[("Redis Conversation History")]
    C --> E["LangChain AI Agent"]
    E --> F["Groq LLM"]
    E --> G["RAG Retrieval"]
    G --> H[("FAISS Knowledge Base")]
    E --> I["Registration & Booking Tools"]
    I <--> J[("PostgreSQL")]
    I <--> K["Google Calendar API"]
    E --> L["AI Response"]
    L --> B
    M["Admin Dashboard"] <--> J
```

### Agent Tools

The agent uses tools defined in `app/agents/sales_agent.py`.

| Tool | Function |
|---|---|
| `query_knowledge_base` | Retrieve relevant FAQ information |
| `get_lead_info` | Retrieve existing customer records |
| `save_lead` | Create or update customer registration |
| `check_available_classes` | Retrieve available classes from PostgreSQL |
| `book_trial` | Create a trial-class booking |
| `check_my_booking` | Look up existing confirmed bookings |
| `cancel_my_booking` | Cancel an existing booking |
| `add_sibling` | Register another student |
| `join_waitlist` | Save a waitlist request |
| `request_human_handoff` | Request staff intervention |
| `reschedule_booking` | Acknowledge rescheduling requests and direct customers to staff |

The rescheduling tool currently preserves the existing booking and requires administrator assistance to complete the change.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.11 | Core programming language |
| FastAPI | API server and webhook processing |
| Uvicorn | ASGI application server |
| LangChain | AI agent and tool orchestration |
| Groq | Language-model inference |
| `openai/gpt-oss-120b` | Currently configured LLM |
| FAISS | Vector-based document retrieval |
| FastEmbed | Text embedding generation |
| Twilio WhatsApp API | WhatsApp communication |
| Google Calendar API | Calendar availability and event management |
| PostgreSQL | Persistent business records |
| SQLAlchemy / asyncpg | Asynchronous database operations |
| Redis | Conversation and session management |
| Jinja2 | Server-rendered admin pages |
| Tailwind CSS | Admin interface styling |
| Pydantic Settings | Environment configuration |
| Railway | Deployment configuration |
| Sentry SDK | Optional error monitoring |

---

## 🗄️ Database Design

TUTORO AI uses PostgreSQL for persistent application data.

The main database models are:

**Leads**

Stores parent or guardian information, contact details, student enquiry information, subjects, and registration stages.

**Students**

Stores additional student records associated with parent leads.

**Bookings**

Stores confirmed or cancelled trial bookings, including appointment dates, selected subjects, and Google Calendar event identifiers.

**Class Schedules**

Stores subject, educational level, day of week, start and end time, maximum capacity, and current enrolled count.

**Waitlist**

Stores customer requests for classes that are currently unavailable.

**Admin Users**

Stores authentication information for the administrative interface.

Redis is used separately for conversation state, administrator sessions, and other temporary application data.

---

## 📂 Project Structure

```text
TutoroAI/
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── agents/
│   │   └── sales_agent.py
│   │
│   ├── routers/
│   │   ├── webhook.py
│   │   └── demo.py
│   │
│   ├── db/
│   │   ├── postgres.py
│   │   ├── redis_client.py
│   │   ├── crud_lead.py
│   │   ├── crud_booking.py
│   │   └── crud_student.py
│   │
│   ├── models/
│   │   ├── lead.py
│   │   ├── student.py
│   │   ├── booking.py
│   │   ├── schedule.py
│   │   ├── waitlist.py
│   │   └── admin.py
│   │
│   ├── tools/
│   │   ├── knowledge_base.py
│   │   ├── schedule_tool.py
│   │   ├── booking_service.py
│   │   ├── calendar_tool.py
│   │   ├── analytics.py
│   │   ├── notifications.py
│   │   ├── reminders.py
│   │   ├── handoff.py
│   │   ├── security.py
│   │   └── email_auth.py
│   │
│   └── templates/
│       ├── login.html
│       ├── dashboard.html
│       ├── students.html
│       ├── timetable.html
│       ├── analytics.html
│       ├── forgot_password.html
│       └── reset_password.html
│
├── knowledge_base/
│   ├── docs/
│   │   ├── faq_english.md
│   │   └── faq_malay.md
│   └── index/
│
├── tests/
│   ├── test_phase3_db.py
│   ├── test_phase5_smoke.py
│   ├── test_phase5_agent.py
│   ├── test_phase6_calendar.py
│   ├── test_booking_only.py
│   ├── test_chat.py
│   ├── evaluate_rag.py
│   └── eval/
│
├── requirements.txt
├── railway.json
├── seed_demo.py
└── README.md
```

Additional development, backup, and patch scripts are also present in the repository.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11
- PostgreSQL
- Redis
- Groq API key
- Twilio account with WhatsApp configuration
- Google Cloud project with Calendar API enabled
- Google service-account credentials

### Step 1 — Clone the Repository

```bash
git clone https://github.com/Shaarwesh/TutoroAI.git
cd TutoroAI
```

### Step 2 — Create a Virtual Environment

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure Environment Variables

Create a `.env` file in the project root.

```dotenv
# Database
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE
REDIS_URL=redis://localhost:6379

# AI
GROQ_API_KEY=your_groq_api_key

# Twilio
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+YOUR_TWILIO_NUMBER

# Google Calendar
GOOGLE_CALENDAR_ID=your_calendar_id
GOOGLE_SERVICE_ACCOUNT_FILE=app/credentials/google_service_account.json

# Admin
ADMIN_INITIAL_PASSWORD=replace_with_a_strong_password_at_least_12_chars
ADMIN_WHATSAPP_NUMBER=whatsapp:+60XXXXXXXXX
ADMIN_RECOVERY_EMAIL=

# Application
APP_ENV=development
SECRET_KEY=replace_with_a_long_random_secret
DEMO_MODE=0
PORT=8000

# Optional
SENTRY_DSN=
```

Important:

- `DATABASE_URL` is required.
- The first admin account requires an initial password of at least 12 characters.
- Google Calendar integration requires access to the configured calendar.
- The application also supports `GOOGLE_CREDENTIALS_JSON` for service-account credentials supplied through an environment variable.
- Never commit actual credentials, private keys, or customer information.

### Step 5 — Build the Knowledge Base

```bash
python -m app.tools.knowledge_base
```

This processes the FAQ documents and creates the FAISS vector index.

### Step 6 — Run the Application

```bash
uvicorn app.main:app --reload --port 8000
```

Access the application locally:

| Page | URL |
|---|---|
| API Documentation | `http://localhost:8000/docs` |
| Admin Login | `http://localhost:8000/login` |
| Dashboard | `http://localhost:8000/dashboard` |
| Student Directory | `http://localhost:8000/students` |
| Timetable | `http://localhost:8000/timetable` |
| Analytics | `http://localhost:8000/analytics` |

The initial administrator username is `admin`, with the password configured during first-time setup.

### Step 7 — Connect WhatsApp

For local Twilio webhook testing, expose the FastAPI server using a tool such as ngrok:

```bash
ngrok http 8000
```

Set the Twilio inbound webhook to:

```text
POST https://YOUR-PUBLIC-URL/webhook/whatsapp
```

For non-development environments, the webhook validates Twilio request signatures.

### Optional — Browser Chat Demo

TUTORO AI also contains a browser-based demonstration page.

Enable it in `.env`:

```dotenv
DEMO_MODE=1
```

Restart the application, then visit:

```text
http://localhost:8000/demo
```

This demo uses the same AI agent execution pipeline without requiring a Twilio inbound message.

It can still access configured databases and calendar services, so use test data and a test calendar when demonstrating bookings.

---

## 🧪 Testing and Evaluation

The repository contains development tests and evaluation scripts for key components.

| File | Test Area |
|---|---|
| `tests/test_phase3_db.py` | Database operations |
| `tests/test_phase5_smoke.py` | Agent smoke testing |
| `tests/test_phase5_agent.py` | Agent conversational flow |
| `tests/test_phase6_calendar.py` | Google Calendar integration |
| `tests/test_booking_only.py` | Trial booking workflow |
| `tests/test_chat.py` | Chat functionality |
| `tests/evaluate_rag.py` | RAG retrieval evaluation |
| `tests/eval/run_eval.py` | Evaluation workflow |

Example:

```bash
python tests/test_phase5_smoke.py
```

The repository also contains stored evaluation reports and result files.

These scripts support development and evaluation; successful execution may depend on environment configuration, external credentials, and test data. Live integration tests were not independently executed as part of this documentation review.

---

## 🚧 Development Status

The main focus of TUTORO AI is its autonomous conversational agent, supported by a developing administrative management system.

### Implemented

- [x] Twilio WhatsApp webhook integration
- [x] LangChain AI tool-calling agent
- [x] English and Bahasa Malaysia conversational support
- [x] FAISS-based knowledge retrieval
- [x] Parent and student registration
- [x] Existing-customer lookup
- [x] PostgreSQL class availability checking
- [x] Google Calendar trial-class booking
- [x] Booking lookup and cancellation
- [x] Sibling registration
- [x] Waitlist registration
- [x] Basic human-handoff support
- [x] Admin authentication
- [x] Class schedule creation, editing, and deletion
- [x] Basic student directory
- [x] Basic analytics reporting
- [x] Browser-based chat demo

### Under Development

- [ ] Detailed clickable student profiles
- [ ] Full weekly timetable interface
- [ ] Accurate capacity updates following booking cancellation
- [ ] Fully automated booking rescheduling
- [ ] WhatsApp delivery of scheduled reminders
- [ ] Improved administrative workflows
- [ ] Reliable synchronization between bookings, calendars, and schedules
- [ ] Additional automated integration and regression tests

---

## ⚠️ Known Limitations

**1. Admin dashboard maturity**

The current dashboard offers basic administrative functionality, but it is not yet a complete tuition-centre CRM.

**2. Class capacity reconciliation**

Confirmed bookings increment the stored class occupancy. The existing cancellation workflow does not yet decrement that count.

**3. Rescheduling workflow**

The rescheduling tool currently directs customers to an administrator rather than automatically moving calendar events and booking records.

**4. Reminder delivery**

The reminder module generates local JSON records; outbound WhatsApp reminder delivery remains unimplemented.

**5. Single-centre configuration**

The application is currently structured around a single tuition-centre deployment rather than supporting isolated accounts for multiple businesses.

**6. External service dependencies**

Real bookings and WhatsApp interactions require correctly configured Groq, Twilio, Google Calendar, PostgreSQL, and Redis services.

**7. AI response reliability**

LLM tool selection, multilingual output, and RAG answer accuracy require continued testing across realistic customer conversations.

---

## 🔮 Future Improvements

Planned improvements include:

- **Student Management:** Detailed student profiles, parent-student relationships, and registration histories.
- **Capacity Management:** Reliable updates on confirmed bookings, cancellations, and class changes.
- **Timetable Management:** Interactive weekly class schedules and clearer occupancy information.
- **Booking Management:** Fully automated and safely synchronized rescheduling.
- **WhatsApp Automation:** Scheduled reminder delivery and improved staff notifications.
- **Human Handoff:** More complete customer-to-staff escalation.
- **Multi-Tenancy:** Independent tuition-centre accounts and configurations.
- **Payment Integration:** Online registration and tuition-fee collection.
- **Parent Portal:** Self-service access to student and booking information.
- **Analytics:** Improved enquiry tracking, booking conversion, and operational reporting.

---

## 💡 Technical Skills Demonstrated

Developing TUTORO AI involved integrating multiple software-engineering concepts:

**Artificial Intelligence**
- Large Language Models
- Agentic AI
- Tool Calling
- Retrieval-Augmented Generation
- Semantic Search
- Prompt Engineering

**Backend Engineering**
- Python
- FastAPI
- REST APIs
- Webhooks
- Asynchronous Programming
- External API Integration

**Data Engineering**
- PostgreSQL
- SQLAlchemy
- Redis
- FAISS
- Database Relationships

**Cloud and Integration**
- Twilio WhatsApp API
- Google Calendar API
- Groq API
- Railway Deployment
- Environment Configuration

**Application Development**
- Business Workflow Automation
- Error Handling
- Authentication
- Backend–Frontend Integration
- Integration Testing
- Iterative Product Development

---

## 👩‍💻 Developer

### Shaarweshwary Saravanan

**Bachelor of Computer Science (Software Development)**

TUTORO AI is a personal project developed to explore the practical application of AI agents and software automation in small-business environments.

My development work spans system architecture, AI agent integration, RAG implementation, backend development, database workflows, third-party API integrations, testing, deployment configuration, and administration-interface development.

The project reflects my interest in building AI-enabled applications that connect conversational interfaces with practical business operations.

**GitHub:** [github.com/Shaarwesh](https://github.com/Shaarwesh)

---

## 📄 License

This repository is shared for educational and portfolio demonstration purposes.

No separate open-source license is currently included. Reuse, modification, distribution, or commercial deployment should not be assumed to be permitted without the author's authorization.

---

**Built by Shaarweshwary Saravanan**

*Exploring the intersection of Agentic AI, RAG, backend engineering, and practical business automation.*