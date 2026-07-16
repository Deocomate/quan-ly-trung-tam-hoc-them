from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import and_, func, select

from app.database import SessionLocal
from app.models import Student
from app.services.student_code_service import (
    DEFAULT_TEMPLATE_BLOCKS,
    generate_custom_student_code,
    parse_template_blocks,
)
from app.timezone import VIETNAM_TZ, month_bounds
from main import app

DEFAULT_TEMPLATE_JSON = json.dumps(DEFAULT_TEMPLATE_BLOCKS)
CUSTOM_TEMPLATE_JSON = json.dumps([
    {"type": "TEXT", "value": "VIP"},
    {"type": "MONTH", "value": "MM"},
    {"type": "YEAR", "value": "YY"},
    {"type": "SEQ", "value": "3", "reset": "monthly"},
])
FIXED_TODAY = date(2026, 6, 10)


def login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123*#"})
    assert response.status_code == 200


def _yearly_student_count(db, t_now: date) -> int:
    start = date(t_now.year, 1, 1)
    end = date(t_now.year + 1, 1, 1)
    return db.scalar(
        select(func.count(Student.id)).where(
            and_(Student.created_at >= start, Student.created_at < end)
        )
    ) or 0


def _monthly_student_count(db, t_now: date) -> int:
    start, end = month_bounds(t_now.year, t_now.month)
    return db.scalar(
        select(func.count(Student.id)).where(
            and_(Student.created_at >= start, Student.created_at < end)
        )
    ) or 0


@patch("app.services.student_code_service.today_vietnam", return_value=FIXED_TODAY)
def test_default_template_matches_current_year_count(_mock_today) -> None:
    with SessionLocal() as db:
        expected = f"2026HS{_yearly_student_count(db, FIXED_TODAY) + 1:06d}"
        code = generate_custom_student_code(db, DEFAULT_TEMPLATE_JSON)
        assert code == expected


@patch("app.services.student_code_service.today_vietnam", return_value=FIXED_TODAY)
def test_yearly_increment_after_adding_students(_mock_today) -> None:
    with SessionLocal() as db:
        base_count = _yearly_student_count(db, FIXED_TODAY)
        suffix = uuid.uuid4().hex[:8]
        for idx in range(2):
            db.add(
                Student(
                    student_code=f"YRLY{suffix}{idx}",
                    full_name=f"Yearly Test {idx}",
                    is_active=True,
                    created_at=datetime(2026, 2, 1, tzinfo=VIETNAM_TZ),
                )
            )
        db.commit()

        code = generate_custom_student_code(db, DEFAULT_TEMPLATE_JSON)
        assert code == f"2026HS{base_count + 2 + 1:06d}"


@patch("app.services.student_code_service.today_vietnam", return_value=FIXED_TODAY)
def test_custom_template_vip_month_year_seq(_mock_today) -> None:
    with SessionLocal() as db:
        expected = f"VIP06{str(FIXED_TODAY.year)[-2:]}{_monthly_student_count(db, FIXED_TODAY) + 1:03d}"
        code = generate_custom_student_code(db, CUSTOM_TEMPLATE_JSON)
        assert code == expected


@patch("app.services.student_code_service.today_vietnam", return_value=FIXED_TODAY)
def test_invalid_json_falls_back_to_default(_mock_today) -> None:
    with SessionLocal() as db:
        expected = f"2026HS{_yearly_student_count(db, FIXED_TODAY) + 1:06d}"
        code = generate_custom_student_code(db, "not json")
        assert code == expected


def test_parse_template_blocks_sanitizes_text() -> None:
    blocks = parse_template_blocks(json.dumps([{"type": "TEXT", "value": "hs-vip!"}]))
    assert blocks == [{"type": "TEXT", "value": "HSVIP"}]


@patch("app.services.student_code_service.today_vietnam", return_value=FIXED_TODAY)
def test_create_student_api_uses_template(_mock_today) -> None:
    with TestClient(app) as client:
        login(client)
        with SessionLocal() as db:
            expected = generate_custom_student_code(db, DEFAULT_TEMPLATE_JSON)

        response = client.post(
            "/api/students",
            json={
                "full_name": "Học sinh tự sinh mã",
                "parent_phone": "0900000001",
                "notes": "",
                "is_active": True,
            },
        )
        assert response.status_code == 200
        assert response.json()["student_code"] == expected


@patch("app.services.student_code_service.today_vietnam", return_value=FIXED_TODAY)
def test_create_student_api_increments_sequence(_mock_today) -> None:
    with TestClient(app) as client:
        login(client)
        first = client.post(
            "/api/students",
            json={
                "full_name": "Học sinh A",
                "parent_phone": "0900000002",
                "notes": "",
                "is_active": True,
            },
        ).json()["student_code"]
        second = client.post(
            "/api/students",
            json={
                "full_name": "Học sinh B",
                "parent_phone": "0900000003",
                "notes": "",
                "is_active": True,
            },
        ).json()["student_code"]

        assert first.startswith("2026HS")
        assert second.startswith("2026HS")
        assert int(second[-6:]) == int(first[-6:]) + 1
