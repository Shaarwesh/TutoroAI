from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import webhook
from app.db.postgres import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("🚀 EduBot starting up...")
    await init_db()
    print("✅ Database ready")
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
