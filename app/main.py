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
        traces_sample_rate=1.0,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("🚀 TUTOR0 AI starting up...", flush=True)
    
    # --- STARTUP LOGIC ---
    try:
        await init_db()
        print("✅ Database ready", flush=True)
    except Exception as e:
        print(f"⚠️  Database not available at startup: {e}", flush=True)

    # ❌ We removed the blocking knowledge base load from here ❌
    # It will now load gracefully on the first user message instead.

    yield  # Uvicorn instantly opens the port here!

    # --- SHUTDOWN LOGIC ---
    print("🛑 TUTOR0 AI shutting down. Cleaning up connections...", flush=True)
    
    try:
        from app.db.postgres import engine
        if engine:
            await engine.dispose()
            print("✅ PostgreSQL connection pool closed", flush=True)
    except Exception as e:
        print(f"⚠️  Failed to close PostgreSQL pool: {e}", flush=True)

    try:
        from app.db.redis_client import _redis_async, _redis_sync
        if _redis_async:
            await _redis_async.close()
        if _redis_sync:
            _redis_sync.close()
        print("✅ Redis connections closed", flush=True)
    except Exception as e:
        print(f"⚠️  Failed to close Redis: {e}", flush=True)


# 2. Initialize FastAPI ONCE
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

# 4. Define Endpoints
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
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
    if x_admin_key != settings.secret_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    from app.tools.reminders import send_upcoming_reminders
    result = await send_upcoming_reminders()
    return {"status": "ok", **result}


@app.get("/admin/stats")
async def admin_stats(x_admin_key: str = Header(None)):
    if x_admin_key != settings.secret_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    from app.tools.analytics import get_analytics_summary
    summary = await get_analytics_summary()
    return summary