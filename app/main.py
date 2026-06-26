from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import webhook
from app.db.postgres import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("🚀 EduBot starting up...")
    try:
        await init_db()
        print("✅ Database ready")
    except Exception as e:
        print(f"⚠️  Database not available at startup: {e}")
        print("⚠️  App will start anyway — will retry DB connections on first request")

    try:
        print("🧠 Pre-building knowledge base index...")
        from app.tools.knowledge_base import get_vectorstore
        get_vectorstore()
        print("✅ Knowledge base ready")
    except Exception as e:
        print(f"⚠️  Knowledge base failed to pre-build: {e}")

    yield
    print("🛑 EduBot shutting down...")


app = FastAPI(
    title="EduBot — Bilingual WhatsApp Sales Agent",
    description="Agentic AI for tuition centre lead qualification and booking",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])


@app.get("/")
async def health():
    return {"status": "ok", "agent": "EduBot", "version": "1.0.0"}
