from __future__ import annotations

import pytest
from sqlalchemy import delete, select
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.bootstrap import seed_defaults
from app.main import app
from app.models import Attendance, Class, Enrollment, Student, TuitionPeriod, TuitionRecord, TuitionRecordItem
from app.timezone import now_vietnam


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
        # Xóa học sinh test
        student = db.scalar(select(Student).where(Student.student_code == "T_SYNC_STUD"))
        if student:
            records = db.scalars(select(TuitionRecord).where(TuitionRecord.student_id == student.id)).all()
            for record in records:
                db.execute(delete(TuitionRecordItem).where(TuitionRecordItem.record_id == record.id))
                db.delete(record)
            db.execute(delete(Attendance).where(Attendance.student_id == student.id))
            db.execute(delete(Enrollment).where(Enrollment.student_id == student.id))
            db.delete(student)
            
        # Xóa lớp test
        c1 = db.scalar(select(Class).where(Class.name == "Lớp Test Sync 1"))
        if c1:
            db.execute(delete(Attendance).where(Attendance.class_id == c1.id))
            db.execute(delete(Enrollment).where(Enrollment.class_id == c1.id))
            db.delete(c1)
        c2 = db.scalar(select(Class).where(Class.name == "Lớp Test Sync 2"))
        if c2:
            db.execute(delete(Attendance).where(Attendance.class_id == c2.id))
            db.execute(delete(Enrollment).where(Enrollment.class_id == c2.id))
            db.delete(c2)
            
        db.execute(delete(TuitionPeriod).where(TuitionPeriod.month == 11, TuitionPeriod.year == 2099))
        db.commit()


def login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    assert response.status_code == 200


def test_enrollment_update_and_sync_flow() -> None:
    with TestClient(app) as client:
        login(client)

        # 1. Tạo 2 lớp học và 1 học sinh
        c1 = client.post(
            "/api/classes",
            json={"name": "Lớp Test Sync 1", "subject": "TOÁN", "default_fee": 100000, "notes": "", "is_active": True},
        ).json()
        c2 = client.post(
            "/api/classes",
            json={"name": "Lớp Test Sync 2", "subject": "LÝ", "default_fee": 150000, "notes": "", "is_active": True},
        ).json()
        student = client.post(
            "/api/students",
            json={
                "student_code": "T_SYNC_STUD",
                "full_name": "Học sinh Sync Học Phí",
                "parent_phone": "0912345678",
                "notes": "",
                "is_active": True,
            },
        ).json()

        # 2. Gán học sinh vào cả 2 lớp học (sử dụng học phí mặc định)
        client.post(
            "/api/enrollments",
            json={
                "student_id": student["id"],
                "class_ids": [c1["id"], c2["id"]],
                "custom_fee": None,
                "is_exempt": False,
                "start_date": "2099-11-01",
                "is_active": True,
                "notes": "",
            },
        )

        # 3. Điểm danh Có mặt 1 buổi cho mỗi lớp
        client.post(
            "/api/attendance/bulk",
            json={
                "class_id": c1["id"],
                "date": "2099-11-01",
                "items": [{"student_id": student["id"], "status": "P"}],
            },
        )
        client.post(
            "/api/attendance/bulk",
            json={
                "class_id": c2["id"],
                "date": "2099-11-01",
                "items": [{"student_id": student["id"], "status": "P"}],
            },
        )

        # 4. Chốt học phí lần 1 (cho cả 2 lớp)
        client.post("/api/tuition/lock", json={"month": 11, "year": 2099, "class_id": None})

        # Xác minh học phí đã lưu
        records = client.get("/api/tuition/records?month=11&year=2099").json()
        r = next(rec for rec in records if rec["student_id"] == student["id"])
        assert r["total_amount"] == 250000 # 100k + 150k
        
        # 5. Kiểm thử đồng bộ khi cập nhật học phí mặc định của lớp học (Lớp 1 từ 100k lên 120k)
        client.put(
            f"/api/classes/{c1['id']}",
            json={"name": "Lớp Test Sync 1", "subject": "TOÁN", "default_fee": 120000, "notes": "", "is_active": True},
        )
        
        # Xác minh học phí của bản ghi chốt học phí cũ cũng tự động tăng lên
        records = client.get("/api/tuition/records?month=11&year=2099").json()
        r = next(rec for rec in records if rec["student_id"] == student["id"])
        assert r["total_amount"] == 270000 # 120k + 150k

        # 6. Kiểm thử cập nhật phân lớp học sinh (gán lại Lớp 1 với học phí riêng 80k)
        client.post(
            "/api/enrollments",
            json={
                "student_id": student["id"],
                "class_ids": [c1["id"]],
                "custom_fee": 80000,
                "is_exempt": False,
                "start_date": "2099-11-01",
                "is_active": True,
                "notes": "Cập nhật học phí riêng",
            },
        )
        
        # Xác minh học phí bản ghi đã chốt tự động giảm theo học phí riêng
        records = client.get("/api/tuition/records?month=11&year=2099").json()
        r = next(rec for rec in records if rec["student_id"] == student["id"])
        assert r["total_amount"] == 230000 # 80k + 150k

        # 7. Kiểm thử chốt học phí lọc theo lớp (Chốt lại Lớp 2)
        # Chỉ chốt lớp 2 thì thông tin Lớp 1 (80k) vẫn phải được giữ nguyên trong bản ghi chốt học phí
        client.post("/api/tuition/lock", json={"month": 11, "year": 2099, "class_id": c2["id"]})
        
        records = client.get("/api/tuition/records?month=11&year=2099").json()
        r = next(rec for rec in records if rec["student_id"] == student["id"])
        assert r["total_amount"] == 230000 # Vẫn là 230k vì cả lớp 1 và lớp 2 đều được lưu trữ đầy đủ

        # 8. Kiểm thử các API xuất báo cáo Doanh thu của Dashboard
        excel_resp = client.get("/api/dashboard/export-excel?month=11&year=2099")
        assert excel_resp.status_code == 200
        assert excel_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
        pdf_resp = client.get("/api/dashboard/export-pdf?month=11&year=2099")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"


def test_dashboard_quarter_and_year_reports() -> None:
    with TestClient(app) as client:
        login(client)

        # Verify summary stats for Quarter 4 (T10-T12)
        summary_q4 = client.get("/api/dashboard/summary?year=2099&period_type=quarter&period_value=4").json()
        assert "revenue" in summary_q4
        assert "sessions" in summary_q4
        assert "students" in summary_q4

        # Verify summary stats for Year
        summary_year = client.get("/api/dashboard/summary?year=2099&period_type=year").json()
        assert "revenue" in summary_year

        # Export Excel for Quarter 4
        excel_q4 = client.get("/api/dashboard/export-excel?year=2099&period_type=quarter&period_value=4")
        assert excel_q4.status_code == 200
        assert excel_q4.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        # Export PDF for Quarter 4
        pdf_q4 = client.get("/api/dashboard/export-pdf?year=2099&period_type=quarter&period_value=4")
        assert pdf_q4.status_code == 200
        assert pdf_q4.headers["content-type"] == "application/pdf"

        # Export Excel for Year
        excel_year = client.get("/api/dashboard/export-excel?year=2099&period_type=year")
        assert excel_year.status_code == 200
        assert excel_year.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        # Export PDF for Year
        pdf_year = client.get("/api/dashboard/export-pdf?year=2099&period_type=year")
        assert pdf_year.status_code == 200
        assert pdf_year.headers["content-type"] == "application/pdf"
