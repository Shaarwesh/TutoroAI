import os
import sentry_sdk
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel

from sqlalchemy import select, func
from app.db.postgres import init_db, AsyncSessionLocal
from app.models.schedule import ClassSchedule
from app.models.lead import Lead
from app.models.booking import Booking
from app.routers import webhook
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
    print("🚀 TUTORO AI starting up...", flush=True)
    
    try:
        await init_db()
        print("✅ Database ready", flush=True)
    except Exception as e:
        print(f"⚠️  Database not available at startup: {e}", flush=True)

    yield  

    print("🛑 TUTORO AI shutting down. Cleaning up connections...", flush=True)
    
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
    title="TUTORO AI — Bilingual WhatsApp Sales Agent",
    description="Agentic AI for tuition centre lead qualification and booking",
    version="1.0.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="app/templates")

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
async def serve_dashboard(request: Request):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ClassSchedule).order_by(ClassSchedule.id.desc()))
        schedules = result.scalars().all()

        lead_count = await db.scalar(select(func.count(Lead.id))) or 0
        booking_count = await db.scalar(select(func.count(Booking.id))) or 0
        total_classes = len(schedules)

    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request, 
            "total_leads": lead_count,
            "total_classes": total_classes,
            "total_bookings": booking_count,
            "schedules": schedules
        }
    )

@app.get("/timetable", response_class=HTMLResponse)
async def serve_timetable(request: Request):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ClassSchedule).order_by(ClassSchedule.id.desc()))
        schedules = result.scalars().all()

    return templates.TemplateResponse(
        "timetable.html", 
        {
            "request": request, 
            "schedules": schedules
        }
    )

@app.get("/students", response_class=HTMLResponse)
async def serve_students(request: Request):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Lead).order_by(Lead.id.desc()))
        leads = result.scalars().all()

    return templates.TemplateResponse(
        "students.html", 
        {
            "request": request,
            "leads": leads
        }
    )

@app.get("/")
async def health():
    return {"status": "ok", "agent": "TUTORO AI", "version": "1.0.0"}


# --- SCHEDULE API (ADD, EDIT, DELETE) ---

class ClassCreate(BaseModel):
    subject: str
    form_year: str
    day_of_week: str
    start_time: str
    end_time: str
    max_capacity: int = 15

@app.post("/admin/schedule")
async def add_class_schedule(new_class: ClassCreate):
    async with AsyncSessionLocal() as db:
        db_class = ClassSchedule(
            subject=new_class.subject,
            form_year=new_class.form_year,
            day_of_week=new_class.day_of_week,
            start_time=new_class.start_time,
            end_time=new_class.end_time,
            max_capacity=new_class.max_capacity
        )
        db.add(db_class)
        await db.commit()
        return {"status": "Class added successfully!"}

@app.put("/admin/schedule/{class_id}")
async def update_class_schedule(class_id: int, updated_class: ClassCreate):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ClassSchedule).where(ClassSchedule.id == class_id))
        db_class = result.scalar_one_or_none()
        
        if not db_class:
            raise HTTPException(status_code=404, detail="Class not found")
            
        db_class.subject = updated_class.subject
        db_class.form_year = updated_class.form_year
        db_class.day_of_week = updated_class.day_of_week
        db_class.start_time = updated_class.start_time
        db_class.end_time = updated_class.end_time
        db_class.max_capacity = updated_class.max_capacity
        
        await db.commit()
        return {"status": "Class updated successfully!"}

@app.delete("/admin/schedule/{class_id}")
async def delete_class_schedule(class_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ClassSchedule).where(ClassSchedule.id == class_id))
        target_class = result.scalar_one_or_none()
        
        if not target_class:
            raise HTTPException(status_code=404, detail="Class not found")
            
        await db.delete(target_class)
        await db.commit()
        return {"status": "Class deleted successfully!"}