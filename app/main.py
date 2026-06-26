from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
from contextlib import asynccontextmanager

from app.routers import webhook
from app.db.postgres import init_db
from app.config import settings


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
        print("🧠 Loading knowledge base index...")
        from app.tools.knowledge_base import get_vectorstore
        get_vectorstore()
        print("✅ Knowledge base ready")
    except Exception as e:
        print(f"⚠️  Knowledge base failed to load: {e}")

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


@app.post("/admin/send-reminders")
async def trigger_reminders(x_admin_key: str = Header(None)):
    """
    Trigger the reminder check manually or via a scheduled job (e.g. Railway Cron).
    Protected by a simple header key to prevent public abuse.
    Call with: curl -X POST https://your-app.up.railway.app/admin/send-reminders -H "X-Admin-Key: your_secret_key"
    """
    if x_admin_key != settings.secret_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    from app.tools.reminders import send_upcoming_reminders
    result = await send_upcoming_reminders()
    return {"status": "ok", **result}


@app.get("/admin/stats")
async def admin_stats(x_admin_key: str = Header(None)):
    """
    Returns business analytics: total leads, conversion rate, popular subjects, etc.
    Call with: curl https://your-app.up.railway.app/admin/stats -H "X-Admin-Key: your_secret_key"
    """
    if x_admin_key != settings.secret_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    from app.tools.analytics import get_analytics_summary
    summary = await get_analytics_summary()
    return {"status": "ok", **summary}


@app.get("/admin/dashboard")
async def admin_dashboard():
    """
    Visual analytics dashboard. Open in a browser with your admin key as a query param:
    https://your-app.up.railway.app/admin/dashboard?key=your_secret_key
    """
    static_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    return FileResponse(static_path)
