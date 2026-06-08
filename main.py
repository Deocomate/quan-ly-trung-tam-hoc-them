from __future__ import annotations

import threading
import time
import webbrowser
import socket
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_user_from_request
from app.bootstrap import ensure_default_assets, seed_defaults
from app.database import BASE_DIR, SessionLocal, get_db, init_db
from app.models import User
from app.routers import admin_users, attendance, auth, classes, dashboard, settings, students, tuition, data_management, teachers, payroll, teacher_attendance
from app.timezone import today_vietnam

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_default_assets()
    init_db()
    with SessionLocal() as db:
        seed_defaults(db)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Quản lý lớp học", version="1.0.0", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    app.include_router(auth.router)
    app.include_router(admin_users.router)
    app.include_router(classes.router)
    app.include_router(students.router)
    app.include_router(students.enrollment_router)
    app.include_router(attendance.router)
    app.include_router(tuition.router)
    app.include_router(settings.router)
    app.include_router(data_management.router)
    app.include_router(teachers.router)
    app.include_router(payroll.router)
    app.include_router(teacher_attendance.router)
    app.include_router(dashboard.router)

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard")

    @app.get("/login")
    def login_page(request: Request):
        return templates.TemplateResponse("login.html", {"request": request})

    def page_context(request: Request, active: str, title: str, user: User, db: Session) -> dict:
        from app.routers.settings import asset_url
        from app.services.settings_service import get_settings_map
        settings = get_settings_map(db)
        return {
            "request": request,
            "active": active,
            "title": title,
            "user": user,
            "today": today_vietnam(),
            "logo_url": asset_url("logo.png"),
            "qr_url": asset_url("qr.png"),
            "center_logo_text": settings.get("center_logo_text", "HH\nEducation"),
        }

    def page_user(request: Request, db: Session) -> User | RedirectResponse:
        user = get_user_from_request(request, db)
        if not user:
            return RedirectResponse(url="/login")
        return user

    @app.get("/dashboard")
    def dashboard_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("dashboard.html", page_context(request, "dashboard", "Tổng quan", user, db))

    @app.get("/students")
    def students_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("students.html", page_context(request, "students", "Học sinh", user, db))

    @app.get("/classes")
    def classes_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("classes.html", page_context(request, "classes", "Lớp/Môn học", user, db))

    @app.get("/attendance")
    def attendance_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("attendance.html", page_context(request, "attendance", "Điểm danh", user, db))

    @app.get("/tuition")
    def tuition_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("tuition.html", page_context(request, "tuition", "Học phí", user, db))

    @app.get("/settings")
    def settings_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("settings.html", page_context(request, "settings", "Cài đặt phiếu thu", user, db))

    @app.get("/data-management")
    def data_management_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("data_management.html", page_context(request, "data_management", "Quản lý dữ liệu", user, db))

    @app.get("/center-info")
    def center_info_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("center_info.html", page_context(request, "center_info", "Thông tin trung tâm", user, db))

    @app.get("/admin-users")
    def admin_users_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("admin_users.html", page_context(request, "admin_users", "Tài khoản", user, db))

    @app.get("/teachers")
    def teachers_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("teachers.html", page_context(request, "teachers", "Giáo viên", user, db))

    @app.get("/payroll")
    def payroll_page(request: Request, db: Session = Depends(get_db)):
        user = page_user(request, db)
        if isinstance(user, RedirectResponse):
            return user
        return templates.TemplateResponse("payroll.html", page_context(request, "payroll", "Lương giáo viên", user, db))

    return app


app = create_app()


def find_free_port(start: int = 8000) -> int:
    port = start
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1


def open_browser(port: int) -> None:
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    selected_port = find_free_port()
    threading.Thread(target=open_browser, args=(selected_port,), daemon=True).start()
    uvicorn.run("main:app", host="127.0.0.1", port=selected_port, reload=True)
