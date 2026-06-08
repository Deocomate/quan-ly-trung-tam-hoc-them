from __future__ import annotations

from sqlalchemy import func, select
from fastapi.testclient import TestClient

from app.main import app
from app.models import Attendance, Class, Enrollment, Student, TuitionPeriod, TuitionRecord
from app.seeder.sample_data import EXPECTED_REVENUE, EXPECTED_TUITION, SAMPLE_MONTH, SAMPLE_YEAR, sample_class_names, sample_student_codes
from app.seeder.seed import _reset_sample_data, seed_sample_data
from app.database import SessionLocal, init_db


def setup_module() -> None:
    init_db()
    with SessionLocal() as db:
        _reset_sample_data(db)


def teardown_module() -> None:
    init_db()
    with SessionLocal() as db:
        _reset_sample_data(db)


def test_sample_seeder_is_idempotent_and_matches_expected_totals() -> None:
    first = seed_sample_data()
    second = seed_sample_data()

    assert first.students == second.students == 5
    assert first.classes == second.classes == 4
    assert first.attendance == second.attendance == 16

    with SessionLocal() as db:
        students = db.scalar(select(func.count(Student.id)).where(Student.student_code.in_(sample_student_codes())))
        classes = db.scalar(select(func.count(Class.id)).where(Class.name.in_(sample_class_names())))
        enrollments = db.scalar(
            select(func.count(Enrollment.id)).join(Enrollment.student).where(Student.student_code.in_(sample_student_codes()))
        )
        attendance = db.scalar(
            select(func.count(Attendance.id)).join(Attendance.student).where(Student.student_code.in_(sample_student_codes()))
        )
        assert students == 5
        assert classes == 4
        assert enrollments == 5
        assert attendance == 16

        rows = db.execute(
            select(Student.student_code, TuitionRecord.total_amount)
            .join(TuitionRecord, TuitionRecord.student_id == Student.id)
            .where(TuitionRecord.month == SAMPLE_MONTH, TuitionRecord.year == SAMPLE_YEAR)
        ).all()
        totals = dict(rows)
        assert totals == EXPECTED_TUITION
        assert sum(totals.values()) == EXPECTED_REVENUE

        period = db.scalar(select(TuitionPeriod).where(TuitionPeriod.month == SAMPLE_MONTH, TuitionPeriod.year == SAMPLE_YEAR))
        assert period is not None
        assert period.is_locked is True


def test_sample_seeder_locks_attendance_month() -> None:
    seed_sample_data()
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
        assert login.status_code == 200
        with SessionLocal() as db:
            student = db.scalar(select(Student).where(Student.student_code == "2026HS001"))
            class_ = db.scalar(select(Class).where(Class.name == "Toán 6 Nâng cao"))
        allowed = client.post(
            "/api/attendance/bulk",
            json={
                "class_id": class_.id,
                "date": "2026-06-01",
                "items": [{"student_id": student.id, "status": "V"}],
            },
        )
        assert allowed.status_code == 200
