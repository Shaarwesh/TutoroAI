
import os
import secrets
import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import (
    FastAPI, HTTPException, Depends,
    Request, Form,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse, RedirectResponse,
)
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select, func

from app.config import settings
from app.db.postgres import init_db, AsyncSessionLocal
from app.db.redis_client import _redis_async
from app.models.schedule import ClassSchedule
from app.models.lead import Lead
from app.models.booking import Booking
from app.models.admin import AdminUser
from app.routers import webhook, demo
from app.tools.security import (
    verify_password, get_password_hash,
)
from app.tools.email_auth import send_reset_link_email


logger = logging.getLogger(__name__)


async def get_current_admin_html(request: Request):
    session_id = request.cookies.get("session_id")

    if session_id and _redis_async:
        username = await _redis_async.get(
            f"session:{session_id}"
        )
        if username:
            return username

    raise HTTPException(
        status_code=303,
        headers={"Location": "/login"},
    )


async def get_current_admin_api(request: Request):
    session_id = request.cookies.get("session_id")

    if session_id and _redis_async:
        username = await _redis_async.get(
            f"session:{session_id}"
        )
        if username:
            return username

    raise HTTPException(
        status_code=401,
        detail="Unauthorized",
    )


if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=1.0,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("TUTORO AI starting up")

    # Do not silently start with an unavailable DB.
    await init_db()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AdminUser).where(
                AdminUser.username == "admin"
            )
        )
        user = result.scalar_one_or_none()

        if user is None:
            password = settings.admin_initial_password

            if len(password) < 12:
                raise RuntimeError(
                    "Set ADMIN_INITIAL_PASSWORD in "
                    ".env to at least 12 characters "
                    "before creating the first admin."
                )

            db.add(
                AdminUser(
                    username="admin",
                    hashed_password=get_password_hash(
                        password
                    ),
                )
            )
            await db.commit()
            logger.info("Initial admin created")
        else:
            logger.info(
                "Existing admin retained; "
                "password was not reset"
            )

    yield

    logger.info("TUTORO AI shutting down")


app = FastAPI(
    title="TUTORO AI",
    version="1.1.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(
    directory="app/templates"
)

# The local demo uses same-origin requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(
    webhook.router,
    prefix="/webhook",
    tags=["Webhook"],
)

if settings.demo_mode:
    app.include_router(demo.router)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request},
    )


@app.post("/login", response_class=HTMLResponse)
async def process_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AdminUser).where(
                AdminUser.username == username
            )
        )
        user = result.scalar_one_or_none()

    if (
        not user
        or not verify_password(
            password, user.hashed_password
        )
    ):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid username or password",
            },
        )

    if not _redis_async:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Redis is unavailable.",
            },
        )

    session_id = secrets.token_urlsafe(32)

    await _redis_async.setex(
        f"session:{session_id}",
        86400,
        user.username,
    )

    response = RedirectResponse(
        url="/dashboard",
        status_code=303,
    )

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        max_age=86400,
        path="/",
    )

    return response


@app.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")

    if session_id and _redis_async:
        await _redis_async.delete(
            f"session:{session_id}"
        )

    response = RedirectResponse(
        url="/login",
        status_code=303,
    )
    response.delete_cookie(
        "session_id",
        path="/",
    )
    return response


@app.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def serve_dashboard(
    request: Request,
    admin: str = Depends(get_current_admin_html),
):
    async with AsyncSessionLocal() as db:
        schedules = (
            await db.execute(
                select(ClassSchedule).order_by(
                    ClassSchedule.id.desc()
                )
            )
        ).scalars().all()

        lead_count = await db.scalar(
            select(func.count(Lead.id))
        ) or 0

        booking_count = await db.scalar(
            select(func.count(Booking.id)).where(Booking.status == "confirmed")
        ) or 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_leads": lead_count,
            "total_classes": len(schedules),
            "total_bookings": booking_count,
            "schedules": schedules,
        },
    )


@app.get(
    "/timetable",
    response_class=HTMLResponse,
)
async def serve_timetable(
    request: Request,
    admin: str = Depends(get_current_admin_html),
):
    async with AsyncSessionLocal() as db:
        schedules = (
            await db.execute(
                select(ClassSchedule).order_by(
                    ClassSchedule.id.desc()
                )
            )
        ).scalars().all()

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def _mins(t):
        try:
            hm, ap = t.strip().split()
            h, mi = map(int, hm.split(":"))
            return (h % 12 + (12 if ap.upper() == "PM" else 0)) * 60 + mi
        except Exception:
            return 0

    by_day = {
        d: sorted(
            [c for c in schedules if (c.day_of_week or "").strip().lower() == d.lower()],
            key=lambda c: _mins(c.start_time),
        )
        for d in day_order
    }
    seats = sum(c.max_capacity or 0 for c in schedules)
    filled = sum(c.current_enrolled or 0 for c in schedules)

    return templates.TemplateResponse(
        "timetable.html",
        {
            "request": request,
            "schedules": schedules,
            "by_day": by_day,
            "seats": seats,
            "filled": filled,
        },
    )


@app.get(
    "/students",
    response_class=HTMLResponse,
)
async def serve_students(
    request: Request,
    admin: str = Depends(get_current_admin_html),
):
    async with AsyncSessionLocal() as db:
        leads = (
            await db.execute(
                select(Lead).order_by(
                    Lead.id.desc()
                )
            )
        ).scalars().all()

    return templates.TemplateResponse(
        "students.html",
        {
            "request": request,
            "leads": leads,
        },
    )

@app.get("/students/{lead_id}", response_class=HTMLResponse)
async def serve_student_detail(
    lead_id: int,
    request: Request,
    admin: str = Depends(get_current_admin_html),
):
    import re
    from zoneinfo import ZoneInfo
    from app.models.student import Student
    from app.models.waitlist import Waitlist

    myt = ZoneInfo("Asia/Kuala_Lumpur")
    async with AsyncSessionLocal() as db:
        lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Student not found")
        bookings = (
            await db.execute(select(Booking).where(Booking.lead_id == lead_id).order_by(Booking.id.desc()))
        ).scalars().all()
        siblings = (await db.execute(select(Student).where(Student.lead_id == lead_id))).scalars().all()
        waitlist = (await db.execute(select(Waitlist).where(Waitlist.phone == lead.phone))).scalars().all()
        ids = {int(x.group(1)) for b in bookings if (x := re.search(r"Class ID:\s*(\d+)", b.notes or ""))}
        classes = {}
        if ids:
            rows = (await db.execute(select(ClassSchedule).where(ClassSchedule.id.in_(ids)))).scalars().all()
            classes = {c.id: c for c in rows}

    items = []
    for b in bookings:
        x = re.search(r"Class ID:\s*(\d+)", b.notes or "")
        when = None
        if b.appointment_start:
            start = b.appointment_start if b.appointment_start.tzinfo else b.appointment_start.replace(tzinfo=ZoneInfo("UTC"))
            when = start.astimezone(myt).strftime("%d %b %Y, %I:%M %p")
        items.append({"b": b, "cls": classes.get(int(x.group(1))) if x else None, "when": when})

    return templates.TemplateResponse(
        "student_detail.html",
        {"request": request, "lead": lead, "items": items, "siblings": siblings, "waitlist": waitlist},
    )


@app.post("/admin/bookings/{booking_id}/cancel")
async def admin_cancel_booking(
    booking_id: int,
    admin: str = Depends(get_current_admin_api),
):
    from app.tools.booking_service import cancel_trial_booking

    async with AsyncSessionLocal() as db:
        booking = (await db.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    try:
        await cancel_trial_booking(booking.phone, booking_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "Booking cancelled and seat released"}



@app.get(
    "/analytics",
    response_class=HTMLResponse,
)
async def serve_analytics(
    request: Request,
    admin: str = Depends(get_current_admin_html),
):
    from app.tools.analytics import (
        get_analytics_summary,
    )

    data = await get_analytics_summary()

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "d": data,
        },
    )


@app.get(
    "/forgot-password",
    response_class=HTMLResponse,
)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        "forgot_password.html",
        {"request": request},
    )


@app.post("/admin/request-reset")
async def request_password_reset(
    request: Request,
    email: str = Form(...),
):
    if (
        settings.admin_recovery_email
        and email == settings.admin_recovery_email
    ):
        base_url = str(
            request.base_url
        ).rstrip("/")

        success = await send_reset_link_email(
            base_url
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to send reset email.",
            )

    return {"status": "success"}


@app.get(
    "/reset-password",
    response_class=HTMLResponse,
)
async def reset_password_page(
    request: Request,
    token: str,
):
    return templates.TemplateResponse(
        "reset_password.html",
        {
            "request": request,
            "token": token,
        },
    )


@app.post("/admin/reset-password")
async def process_new_password(
    token: str = Form(...),
    new_password: str = Form(...),
):
    if len(new_password) < 12:
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must contain at "
                "least 12 characters."
            ),
        )

    if not _redis_async:
        raise HTTPException(
            status_code=503,
            detail="Redis is unavailable.",
        )

    redis_key = f"reset_token:{token}"

    if not await _redis_async.get(redis_key):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired token.",
        )

    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(
                select(AdminUser).where(
                    AdminUser.username == "admin"
                )
            )
        ).scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Admin not found.",
            )

        user.hashed_password = get_password_hash(
            new_password
        )
        await db.commit()

    await _redis_async.delete(redis_key)

    return {"status": "success"}


class ClassCreate(BaseModel):
    subject: str
    form_year: str
    day_of_week: str
    start_time: str
    end_time: str
    max_capacity: int = 15


@app.post("/admin/schedule")
async def add_class_schedule(
    new_class: ClassCreate,
    admin: str = Depends(get_current_admin_api),
):
    async with AsyncSessionLocal() as db:
        db.add(
            ClassSchedule(
                **new_class.model_dump()
            )
        )
        await db.commit()

    return {
        "status": "Class added successfully!"
    }


@app.put("/admin/schedule/{class_id}")
async def update_class_schedule(
    class_id: int,
    updated_class: ClassCreate,
    admin: str = Depends(get_current_admin_api),
):
    async with AsyncSessionLocal() as db:
        target = (
            await db.execute(
                select(ClassSchedule).where(
                    ClassSchedule.id == class_id
                )
            )
        ).scalar_one_or_none()

        if not target:
            raise HTTPException(
                status_code=404,
                detail="Class not found",
            )

        for key, value in (
            updated_class.model_dump().items()
        ):
            setattr(target, key, value)

        await db.commit()

    return {
        "status": "Class updated successfully!"
    }


@app.delete("/admin/schedule/{class_id}")
async def delete_class_schedule(
    class_id: int,
    admin: str = Depends(get_current_admin_api),
):
    async with AsyncSessionLocal() as db:
        target = (
            await db.execute(
                select(ClassSchedule).where(
                    ClassSchedule.id == class_id
                )
            )
        ).scalar_one_or_none()

        if not target:
            raise HTTPException(
                status_code=404,
                detail="Class not found",
            )

        await db.delete(target)
        await db.commit()

    return {
        "status": "Class deleted successfully!"
    }
