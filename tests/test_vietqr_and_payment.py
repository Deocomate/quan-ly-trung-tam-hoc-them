from __future__ import annotations

import pytest
from sqlalchemy import delete, select
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.bootstrap import seed_defaults
from app.main import app
from app.models import Student, Class, Enrollment, Attendance, TuitionPeriod, TuitionRecord, TuitionRecordItem
from app.services.vietqr_service import (
    remove_vietnamese_accents,
    normalize_transfer_content,
    normalize_account_name,
    generate_vietqr_url
)

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
        student = db.scalar(select(Student).where(Student.student_code == "QRTEST2099"))
        if student:
            records = db.scalars(select(TuitionRecord).where(TuitionRecord.student_id == student.id)).all()
            for record in records:
                db.execute(delete(TuitionRecordItem).where(TuitionRecordItem.record_id == record.id))
                db.delete(record)
            db.execute(delete(Attendance).where(Attendance.student_id == student.id))
            db.execute(delete(Enrollment).where(Enrollment.student_id == student.id))
            db.delete(student)
            
        test_class = db.scalar(select(Class).where(Class.name == "Lớp QR Test"))
        if test_class:
            db.execute(delete(Attendance).where(Attendance.class_id == test_class.id))
            db.execute(delete(Enrollment).where(Enrollment.class_id == test_class.id))
            db.delete(test_class)
            
        db.execute(delete(TuitionPeriod).where(TuitionPeriod.month == 11, TuitionPeriod.year == 2099))
        db.commit()


def login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    assert response.status_code == 200


def test_vietqr_service_sanitization():
    # Test removing accents
    assert remove_vietnamese_accents("Nguyễn Vũ Minh Long") == "Nguyen Vu Minh Long"
    assert remove_vietnamese_accents("học phí tháng 6/2026") == "hoc phi thang 6/2026"
    assert remove_vietnamese_accents("đố vui") == "do vui"
    assert remove_vietnamese_accents("ĐỘI CẤN") == "DOI CAN"

    # Test transfer content normalization
    assert normalize_transfer_content("HP HS001 0626!") == "HP HS001 0626"
    assert normalize_transfer_content("Thanh toán học phí @2026") == "THANH TOAN HOC PHI 2026"
    
    # Test account name normalization
    assert normalize_account_name("Nguyễn Vũ Minh Long") == "NGUYEN VU MINH LONG"
    
    # Test URL generation
    url = generate_vietqr_url("970422", "0565651189", "NGUYEN VU MINH LONG", 1500000, "HP HS001 0626")
    assert "https://img.vietqr.io/image/970422-0565651189-compact2.png" in url
    assert "amount=1500000" in url
    assert "addInfo=HP+HS001+0626" in url
    assert "accountName=NGUYEN+VU+MINH+LONG" in url


def test_vietqr_and_payment_flow():
    with TestClient(app) as client:
        login(client)
        
        # 1. Setup a class and student
        klass = client.post(
            "/api/classes",
            json={"name": "Lớp QR Test", "subject": "VẬT LÝ", "default_fee": 150000, "notes": "", "is_active": True},
        ).json()
        
        student = client.post(
            "/api/students",
            json={
                "student_code": "QRTEST2099",
                "full_name": "Nguyen QR Student",
                "parent_phone": "0912345678",
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
                "start_date": "2099-11-01",
                "is_active": True,
                "notes": "",
            },
        )
        assert enrollment.status_code == 200

        # 2. Add attendance
        att = client.post(
            "/api/attendance/bulk",
            json={
                "class_id": klass["id"],
                "date": "2099-11-05",
                "items": [{"student_id": student["id"], "status": "P"}],
            },
        )
        assert att.status_code == 200

        # 3. Lock tuition
        lock = client.post("/api/tuition/lock", json={"month": 11, "year": 2099, "class_id": None})
        assert lock.status_code == 200

        # 4. Check locked record in database contains new fields
        records_resp = client.get("/api/tuition/records?month=11&year=2099")
        assert records_resp.status_code == 200
        records = records_resp.json()
        assert len(records) == 1
        record = records[0]
        
        assert record["transfer_code"] == "HP QRTEST2099 1199"
        assert record["paid_amount"] == 0
        assert record["payment_status"] == "unpaid"
        assert record["total_amount"] == 150000

        record_id = record["id"]

        # 5. Test updating payment status (partial)
        pay_partial = client.put(
            f"/api/tuition/records/{record_id}/payment",
            json={"paid_amount": 50000}
        )
        assert pay_partial.status_code == 200
        data = pay_partial.json()
        assert data["paid_amount"] == 50000
        assert data["payment_status"] == "partial"
        assert data["debt"] == 100000

        # Verify through GET
        record_check = client.get("/api/tuition/records?month=11&year=2099").json()[0]
        assert record_check["paid_amount"] == 50000
        assert record_check["payment_status"] == "partial"

        # 6. Test updating payment status (full)
        pay_full = client.put(
            f"/api/tuition/records/{record_id}/payment",
            json={"paid_amount": 150000}
        )
        assert pay_full.status_code == 200
        data = pay_full.json()
        assert data["payment_status"] == "paid"
        assert data["debt"] == 0

        # Verify through GET
        record_check = client.get("/api/tuition/records?month=11&year=2099").json()[0]
        assert record_check["paid_amount"] == 150000
        assert record_check["payment_status"] == "paid"

        # 7. Test invalid negative amount
        pay_invalid = client.put(
            f"/api/tuition/records/{record_id}/payment",
            json={"paid_amount": -100}
        )
        assert pay_invalid.status_code == 400

        # 8. Test pdf download with various payments
        # Test download paid in full (uses paid stamp)
        pdf_full = client.get(f"/api/tuition/records/{record_id}/pdf")
        assert pdf_full.status_code == 200
        assert len(pdf_full.content) > 0

        # Reset payment to partial and download
        client.put(
            f"/api/tuition/records/{record_id}/payment",
            json={"paid_amount": 50000}
        )
        pdf_partial = client.get(f"/api/tuition/records/{record_id}/pdf")
        assert pdf_partial.status_code == 200
        assert len(pdf_partial.content) > 0
