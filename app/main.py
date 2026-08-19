import os
import sentry_sdk
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import HTMLResponse

from app.routers import webhook
from app.db.postgres import init_db
from app.config import settings

# 1. Initialize Sentry BEFORE FastAPI is created
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring.
        traces_sample_rate=1.0,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("🚀 TUTOR0 AI starting up...")
    
    # --- STARTUP LOGIC ---
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

    yield  # App runs and handles requests here

    # --- SHUTDOWN LOGIC (CRITICAL FOR RAILWAY) ---
    print("🛑 TUTOR0 AI shutting down. Cleaning up connections...")
    
    # 1. Close PostgreSQL connections safely
    try:
        from app.db.postgres import engine
        if engine:
            await engine.dispose()
            print("✅ PostgreSQL connection pool closed")
    except Exception as e:
        print(f"⚠️  Failed to close PostgreSQL pool: {e}")

    # 2. Close Redis connections safely
    try:
        from app.db.redis_client import _redis_async, _redis_sync
        if _redis_async:
            await _redis_async.close()
        if _redis_sync:
            _redis_sync.close()
        print("✅ Redis connections closed")
    except Exception as e:
        print(f"⚠️  Failed to close Redis: {e}")


# 2. Initialize FastAPI ONCE (with lifespan and metadata)
app = FastAPI(
    title="TUTOR0 AI — Bilingual WhatsApp Sales Agent",
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

# 3. Mount Routers
app.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])

# 4. Define Endpoints (Must be AFTER app = FastAPI())

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the live admin dashboard."""
    html_path = "dashboard.html"
    if not os.path.exists(html_path):
        return "Dashboard file not found."
    
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/")
async def health():
    return {"status": "ok", "agent": "TUTOR0 AI", "version": "1.0.0"}


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
    
    return summary