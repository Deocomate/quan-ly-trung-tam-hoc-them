from __future__ import annotations

from sqlalchemy import delete, select
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.bootstrap import seed_defaults
from main import app
from app.models import Attendance, Class, Enrollment, Student, TuitionPeriod, TuitionRecord, TuitionRecordItem
from app.timezone import now_vietnam, parse_local_date


def setup_module() -> None:
    cleanup_test_data()
    init_db()
    with SessionLocal() as db:
        seed_defaults(db)


def teardown_module() -> None:
    cleanup_test_data()


def cleanup_test_data() -> None:
    init_db()
    with SessionLocal() as db:
        student = db.scalar(select(Student).where(Student.student_code == "TEST209912"))
        if student:
            records = db.scalars(select(TuitionRecord).where(TuitionRecord.student_id == student.id)).all()
            for record in records:
                db.execute(delete(TuitionRecordItem).where(TuitionRecordItem.record_id == record.id))
                db.delete(record)
            db.execute(delete(Attendance).where(Attendance.student_id == student.id))
            db.execute(delete(Enrollment).where(Enrollment.student_id == student.id))
            db.delete(student)
        test_class = db.scalar(select(Class).where(Class.name == "Lớp test 2099"))
        if test_class:
            db.execute(delete(Attendance).where(Attendance.class_id == test_class.id))
            db.execute(delete(Enrollment).where(Enrollment.class_id == test_class.id))
            db.delete(test_class)
        db.execute(delete(TuitionPeriod).where(TuitionPeriod.month == 12, TuitionPeriod.year == 2099))
        db.commit()


def login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    assert response.status_code == 200


def test_timezone_uses_vietnam_offset() -> None:
    assert now_vietnam().utcoffset().total_seconds() == 7 * 3600
    assert parse_local_date("2099-12-01").isoformat() == "2099-12-01"


def test_admin_seed_and_tuition_flow() -> None:
    with TestClient(app) as client:
        login(client)
        klass = client.post(
            "/api/classes",
            json={"name": "Lớp test 2099", "subject": "TOÁN", "default_fee": 130000, "notes": "", "is_active": True},
        ).json()
        student = client.post(
            "/api/students",
            json={
                "student_code": "TEST209912",
                "full_name": "Học sinh kiểm thử",
                "parent_phone": "0900000000",
                "notes": "",
                "is_active": True,
            },
        ).json()
        enrollment = client.post(
            "/api/enrollments",
            json={
                "student_id": student["id"],
                "class_ids": [klass["id"]],
                "custom_fee": None,
                "is_exempt": False,
                "start_date": "2099-12-01",
                "is_active": True,
                "notes": "",
            },
        )
        assert enrollment.status_code == 200

        attendance = client.post(
            "/api/attendance/bulk",
            json={
                "class_id": klass["id"],
                "date": "2099-12-01",
                "items": [{"student_id": student["id"], "status": "P"}],
            },
        )
        assert attendance.status_code == 200

        # Test GET /api/attendance/month
        month_att = client.get(f"/api/attendance/month?class_id={klass['id']}&month=12&year=2099")
        assert month_att.status_code == 200
        data = month_att.json()
        assert data["is_locked"] is False
        assert len(data["students"]) == 1
        assert data["students"][0]["student_id"] == student["id"]
        assert data["students"][0]["attendance"]["2099-12-01"] == "P"

        # Test PUT /api/attendance/single (update status to 'V')
        single_save = client.put(
            "/api/attendance/single",
            json={
                "class_id": klass["id"],
                "student_id": student["id"],
                "date": "2099-12-01",
                "status": "V",
            },
        )
        assert single_save.status_code == 200

        # Verify updated status
        month_att = client.get(f"/api/attendance/month?class_id={klass['id']}&month=12&year=2099").json()
        assert month_att["students"][0]["attendance"]["2099-12-01"] == "V"

        # Test PUT /api/attendance/single (delete status by passing None)
        single_delete = client.put(
            "/api/attendance/single",
            json={
                "class_id": klass["id"],
                "student_id": student["id"],
                "date": "2099-12-01",
                "status": None,
            },
        )
        assert single_delete.status_code == 200

        # Verify status is deleted
        month_att = client.get(f"/api/attendance/month?class_id={klass['id']}&month=12&year=2099").json()
        assert "2099-12-01" not in month_att["students"][0]["attendance"]

        # Restore to 'P' for subsequent tuition preview testing
        restore = client.put(
            "/api/attendance/single",
            json={
                "class_id": klass["id"],
                "student_id": student["id"],
                "date": "2099-12-01",
                "status": "P",
            },
        )
        assert restore.status_code == 200

        preview = client.get("/api/tuition/preview?month=12&year=2099").json()
        record = next(row for row in preview["records"] if row["student_id"] == student["id"])
        assert record["total_sessions"] == 1
        assert record["total_amount"] == 130000

        # Test exporting temporary PDF before locking
        temp_single_pdf = client.get(f"/api/tuition/export-pdf?month=12&year=2099&student_id={student['id']}")
        assert temp_single_pdf.status_code == 200
        assert temp_single_pdf.headers["Content-Type"] == "application/pdf"
        assert len(temp_single_pdf.content) > 0
        assert "phieu-thu-TEST209912-12-2099.pdf" in temp_single_pdf.headers.get("Content-Disposition", "")

        temp_all_pdf = client.get("/api/tuition/export-pdf?month=12&year=2099")
        assert temp_all_pdf.status_code == 200
        assert temp_all_pdf.headers["Content-Type"] == "application/pdf"
        assert len(temp_all_pdf.content) > 0
        assert "phieu-thu-12-2099.pdf" in temp_all_pdf.headers.get("Content-Disposition", "")

        lock = client.post("/api/tuition/lock", json={"month": 12, "year": 2099, "class_id": None})
        assert lock.status_code == 200

        # Verify month API shows is_locked = True
        month_att_locked = client.get(f"/api/attendance/month?class_id={klass['id']}&month=12&year=2099").json()
        assert month_att_locked["is_locked"] is True

        # Test PUT /api/attendance/single on a locked period (should succeed under soft lock)
        allowed_single = client.put(
            "/api/attendance/single",
            json={
                "class_id": klass["id"],
                "student_id": student["id"],
                "date": "2099-12-01",
                "status": "V",
            },
        )
        assert allowed_single.status_code == 200

        allowed_bulk = client.post(
            "/api/attendance/bulk",
            json={
                "class_id": klass["id"],
                "date": "2099-12-01",
                "items": [{"student_id": student["id"], "status": "V"}],
            },
        )
        assert allowed_bulk.status_code == 200

        # Test updating tuition item notes (new endpoint)
        records_resp = client.get("/api/tuition/records?month=12&year=2099")
        assert records_resp.status_code == 200
        records = records_resp.json()
        record = next(r for r in records if r["student_code"] == "TEST209912")
        item_id = record["items"][0]["id"]
        
        update_notes = client.put(
            f"/api/tuition/items/{item_id}/notes",
            json={"notes": "Đã thu tiền muộn"}
        )
        assert update_notes.status_code == 200
        assert update_notes.json()["notes"] == "Đã thu tiền muộn"
        
        records_updated = client.get("/api/tuition/records?month=12&year=2099").json()
        record_updated = next(r for r in records_updated if r["student_code"] == "TEST209912")
        assert record_updated["items"][0]["notes"] == "Đã thu tiền muộn"
