from __future__ import annotations

from sqlalchemy import delete, select, update
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.bootstrap import seed_defaults
from main import app
from app.models import (
    Teacher,
    Class,
    Attendance,
    Enrollment,
    Student,
    TuitionPeriod,
    TuitionRecord,
    TuitionRecordItem,
    TeacherSalaryRecord,
    TeacherSalaryRecordItem,
    TeacherClassAssignment,
    TeacherAttendance,
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
        # Delete salary records
        salary_record_ids = set(
            db.scalars(
                select(TeacherSalaryRecord.id).where(
                    TeacherSalaryRecord.year == 2099
                )
            ).all()
        )
        if salary_record_ids:
            db.execute(delete(TeacherSalaryRecordItem).where(TeacherSalaryRecordItem.record_id.in_(salary_record_ids)))
            db.execute(delete(TeacherSalaryRecord).where(TeacherSalaryRecord.id.in_(salary_record_ids)))

        # Delete tuition records
        tuition_record_ids = set(
            db.scalars(
                select(TuitionRecord.id).where(
                    TuitionRecord.year == 2099
                )
            ).all()
        )
        if tuition_record_ids:
            db.execute(delete(TuitionRecordItem).where(TuitionRecordItem.record_id.in_(tuition_record_ids)))
            db.execute(delete(TuitionRecord).where(TuitionRecord.id.in_(tuition_record_ids)))

        # Delete tuition period
        db.execute(delete(TuitionPeriod).where(TuitionPeriod.year == 2099))

        # Delete enrollment & attendance
        test_student_ids = set(
            db.scalars(select(Student.id).where(Student.student_code.like("TEST_ST_%"))).all()
        )
        if test_student_ids:
            db.execute(delete(Attendance).where(Attendance.student_id.in_(test_student_ids)))
            db.execute(delete(Enrollment).where(Enrollment.student_id.in_(test_student_ids)))
            db.execute(delete(Student).where(Student.id.in_(test_student_ids)))

        test_class_ids = set(
            db.scalars(select(Class.id).where(Class.name.like("TEST_CL_%"))).all()
        )
        if test_class_ids:
            db.execute(delete(TeacherClassAssignment).where(TeacherClassAssignment.class_id.in_(test_class_ids)))
            db.execute(delete(TeacherAttendance).where(TeacherAttendance.class_id.in_(test_class_ids)))
            db.execute(delete(Attendance).where(Attendance.class_id.in_(test_class_ids)))
            db.execute(delete(Enrollment).where(Enrollment.class_id.in_(test_class_ids)))
            db.execute(delete(Class).where(Class.id.in_(test_class_ids)))

        # Delete teachers
        test_teacher_ids = set(
            db.scalars(select(Teacher.id).where(Teacher.full_name.like("TEST_TCH_%"))).all()
        )
        if test_teacher_ids:
            db.execute(delete(TeacherClassAssignment).where(TeacherClassAssignment.teacher_id.in_(test_teacher_ids)))
            db.execute(delete(TeacherAttendance).where(TeacherAttendance.teacher_id.in_(test_teacher_ids)))
            db.execute(delete(Teacher).where(Teacher.id.in_(test_teacher_ids)))
        db.commit()


def login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    assert response.status_code == 200


def test_payroll_full_flow() -> None:
    with TestClient(app) as client:
        login(client)

        # 1. Create Teachers
        t1_resp = client.post(
            "/api/teachers",
            json={
                "full_name": "TEST_TCH_1",
                "phone": "0900000001",
                "email": "t1@test.com",
                "default_salary_coefficient": 1.0,
                "is_active": True,
            },
        )
        assert t1_resp.status_code == 200
        t1 = t1_resp.json()

        t2_resp = client.post(
            "/api/teachers",
            json={
                "full_name": "TEST_TCH_2",
                "phone": "0900000002",
                "email": "t2@test.com",
                "default_salary_coefficient": 1.2,
                "is_active": True,
            },
        )
        assert t2_resp.status_code == 200
        t2 = t2_resp.json()

        # 2. Create Classes with new assignments structure
        c_a_resp = client.post(
            "/api/classes",
            json={
                "name": "TEST_CL_A",
                "subject": "TOAN",
                "default_fee": 100000,
                "notes": "",
                "is_active": True,
                "assignments": [
                    {
                        "teacher_id": t1["id"],
                        "role": "main",
                        "salary_type": "coefficient",
                        "salary_coefficient": 1.0,
                    }
                ],
            },
        )
        assert c_a_resp.status_code == 200
        c_a = c_a_resp.json()

        c_b_resp = client.post(
            "/api/classes",
            json={
                "name": "TEST_CL_B",
                "subject": "LY",
                "default_fee": 100000,
                "notes": "",
                "is_active": True,
                "assignments": [
                    {
                        "teacher_id": t1["id"],
                        "role": "main",
                        "salary_type": "coefficient",
                        "salary_coefficient": 1.5,
                    }
                ],
            },
        )
        assert c_b_resp.status_code == 200
        c_b = c_b_resp.json()

        c_c_resp = client.post(
            "/api/classes",
            json={
                "name": "TEST_CL_C",
                "subject": "HOA",
                "default_fee": 100000,
                "notes": "",
                "is_active": True,
                "assignments": [
                    {
                        "teacher_id": t2["id"],
                        "role": "main",
                        "salary_type": "fixed",
                        "fixed_salary_per_session": 300000,
                    }
                ],
            },
        )
        assert c_c_resp.status_code == 200
        c_c = c_c_resp.json()

        # 3. Create Student
        s_resp = client.post(
            "/api/students",
            json={
                "student_code": "TEST_ST_01",
                "full_name": "TEST_STUDENT_01",
                "parent_phone": "0900000100",
                "notes": "",
                "is_active": True,
            },
        )
        assert s_resp.status_code == 200
        s = s_resp.json()

        # 4. Enroll Student in Classes
        enroll_resp = client.post(
            "/api/enrollments",
            json={
                "student_id": s["id"],
                "class_ids": [c_a["id"], c_b["id"], c_c["id"]],
                "custom_fee": None,
                "is_exempt": False,
                "start_date": "2099-12-01",
                "is_active": True,
                "notes": "",
            },
        )
        assert enroll_resp.status_code == 200

        # 5. Add Attendance (Students)
        client.post("/api/attendance/bulk", json={"class_id": c_a["id"], "date": "2099-12-01", "items": [{"student_id": s["id"], "status": "P"}]})
        client.post("/api/attendance/bulk", json={"class_id": c_a["id"], "date": "2099-12-02", "items": [{"student_id": s["id"], "status": "P"}]})
        client.post("/api/attendance/bulk", json={"class_id": c_b["id"], "date": "2099-12-01", "items": [{"student_id": s["id"], "status": "P"}]})
        client.post("/api/attendance/bulk", json={"class_id": c_c["id"], "date": "2099-12-01", "items": [{"student_id": s["id"], "status": "P"}]})
        client.post("/api/attendance/bulk", json={"class_id": c_c["id"], "date": "2099-12-02", "items": [{"student_id": s["id"], "status": "P"}]})
        client.post("/api/attendance/bulk", json={"class_id": c_c["id"], "date": "2099-12-03", "items": [{"student_id": s["id"], "status": "P"}]})

        # 5b. Add Attendance (Teachers) - New System
        client.put("/api/teacher-attendance/single", json={"class_id": c_a["id"], "teacher_id": t1["id"], "date": "2099-12-01", "status": "P"})
        client.put("/api/teacher-attendance/single", json={"class_id": c_a["id"], "teacher_id": t1["id"], "date": "2099-12-02", "status": "P"})
        client.put("/api/teacher-attendance/single", json={"class_id": c_b["id"], "teacher_id": t1["id"], "date": "2099-12-01", "status": "P"})
        client.put("/api/teacher-attendance/single", json={"class_id": c_c["id"], "teacher_id": t2["id"], "date": "2099-12-01", "status": "P"})
        client.put("/api/teacher-attendance/single", json={"class_id": c_c["id"], "teacher_id": t2["id"], "date": "2099-12-02", "status": "P"})
        client.put("/api/teacher-attendance/single", json={"class_id": c_c["id"], "teacher_id": t2["id"], "date": "2099-12-03", "status": "P"})

        # 6. Lock Tuition Period to calculate and save Class Revenue
        lock_tuition_resp = client.post("/api/tuition/lock", json={"month": 12, "year": 2099, "class_id": None})
        assert lock_tuition_resp.status_code == 200

        # 7. Preview Payroll and Verify Calculations
        preview_resp = client.get("/api/payroll/preview?month=12&year=2099")
        assert preview_resp.status_code == 200
        preview_data = preview_resp.json()
        assert preview_data["is_locked"] is False

        records = preview_data["records"]
        t1_rec = next(r for r in records if r["teacher_id"] == t1["id"])
        t2_rec = next(r for r in records if r["teacher_id"] == t2["id"])

        assert t1_rec["total_salary"] == 350000  # 200000 + 150000
        assert t2_rec["total_salary"] == 900000  # 900000

        c_a_item = next(c for c in t1_rec["classes"] if c["class_id"] == c_a["id"])
        c_b_item = next(c for c in t1_rec["classes"] if c["class_id"] == c_b["id"])
        c_c_item = next(c for c in t2_rec["classes"] if c["class_id"] == c_c["id"])

        assert c_a_item["sessions"] == 2
        assert c_a_item["revenue"] == 200000
        assert c_a_item["applied_rate"] == 1.0
        assert c_a_item["amount"] == 200000

        assert c_b_item["sessions"] == 1
        assert c_b_item["revenue"] == 100000
        assert c_b_item["applied_rate"] == 1.5
        assert c_b_item["amount"] == 150000

        assert c_c_item["sessions"] == 3
        assert c_c_item["applied_rate"] == 300000
        assert c_c_item["amount"] == 900000

        # 7b. Test Temporary PDF Export (Single and All)
        temp_single_pdf = client.get(f"/api/payroll/export-pdf?month=12&year=2099&teacher_id={t1['id']}")
        assert temp_single_pdf.status_code == 200
        assert temp_single_pdf.headers["Content-Type"] == "application/pdf"
        assert len(temp_single_pdf.content) > 0
        assert "phieu-luong-tam-TEST_TCH_1" in temp_single_pdf.headers.get("Content-Disposition", "")

        temp_all_pdf = client.get("/api/payroll/export-pdf?month=12&year=2099")
        assert temp_all_pdf.status_code == 200
        assert temp_all_pdf.headers["Content-Type"] == "application/pdf"
        assert len(temp_all_pdf.content) > 0
        assert "phieu-luong-tam-all" in temp_all_pdf.headers.get("Content-Disposition", "")

        # 8. Lock Payroll Period
        lock_pay_resp = client.post("/api/payroll/lock", json={"month": 12, "year": 2099})
        assert lock_pay_resp.status_code == 200

        # 9. Verify History Preservation
        # Update teacher default salary coeff and class rates
        update_tch_resp = client.put(
            f"/api/teachers/{t1['id']}",
            json={
                "full_name": "TEST_TCH_1",
                "phone": "0900000001",
                "email": "t1@test.com",
                "default_salary_coefficient": 2.0,  # Changed from 1.0 to 2.0
                "is_active": True,
            },
        )
        assert update_tch_resp.status_code == 200

        update_cls_resp = client.put(
            f"/api/classes/{c_b['id']}",
            json={
                "name": "TEST_CL_B",
                "subject": "LY",
                "default_fee": 100000,
                "notes": "",
                "is_active": True,
                "assignments": [
                    {
                        "teacher_id": t1["id"],
                        "role": "main",
                        "salary_type": "coefficient",
                        "salary_coefficient": 2.5,  # Changed from 1.5 to 2.5
                    }
                ],
            },
        )
        assert update_cls_resp.status_code == 200

        update_cls_c_resp = client.put(
            f"/api/classes/{c_c['id']}",
            json={
                "name": "TEST_CL_C",
                "subject": "HOA",
                "default_fee": 100000,
                "notes": "",
                "is_active": True,
                "assignments": [
                    {
                        "teacher_id": t2["id"],
                        "role": "main",
                        "salary_type": "fixed",
                        "fixed_salary_per_session": 500000,  # Changed from 300k to 500k
                    }
                ],
            },
        )
        assert update_cls_c_resp.status_code == 200

        # Fetch payroll records list for Dec 2099 and verify values remain unchanged
        records_resp = client.get("/api/payroll/records?month=12&year=2099")
        assert records_resp.status_code == 200
        records_list = records_resp.json()
        
        # Filter for our test teachers
        test_records = [r for r in records_list if r["teacher_name"] in ("TEST_TCH_1", "TEST_TCH_2")]
        assert len(test_records) == 2

        t1_hist = next(r for r in test_records if r["teacher_id"] == t1["id"])
        t2_hist = next(r for r in test_records if r["teacher_id"] == t2["id"])

        # Amounts must match historical calculations, NOT new rates!
        assert t1_hist["total_amount"] == 350000
        assert t2_hist["total_amount"] == 900000

        t1_items = t1_hist["items"]
        c_a_hist = next(i for i in t1_items if i["class_name"] == "TEST_CL_A")
        c_b_hist = next(i for i in t1_items if i["class_name"] == "TEST_CL_B")

        assert c_a_hist["applied_rate"] == 1.0
        assert c_a_hist["calculated_amount"] == 200000

        assert c_b_hist["applied_rate"] == 1.5
        assert c_b_hist["calculated_amount"] == 150000

        t2_items = t2_hist["items"]
        c_c_hist = next(i for i in t2_items if i["class_name"] == "TEST_CL_C")
        assert c_c_hist["applied_rate"] == 300000
        assert c_c_hist["calculated_amount"] == 900000

        # 10. Test PDF download endpoint works
        pdf_resp = client.get(f"/api/payroll/records/{t1_hist['id']}/pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["Content-Type"] == "application/pdf"
        assert len(pdf_resp.content) > 0

        # 11. Test Locked PDF Export (Single and All via unified route)
        locked_single_pdf = client.get(f"/api/payroll/export-pdf?month=12&year=2099&teacher_id={t1['id']}")
        assert locked_single_pdf.status_code == 200
        assert locked_single_pdf.headers["Content-Type"] == "application/pdf"
        assert len(locked_single_pdf.content) > 0
        assert "phieu-luong-TEST_TCH_1" in locked_single_pdf.headers.get("Content-Disposition", "")

        locked_all_pdf = client.get("/api/payroll/export-pdf?month=12&year=2099")
        assert locked_all_pdf.status_code == 200
        assert locked_all_pdf.headers["Content-Type"] == "application/pdf"
        assert len(locked_all_pdf.content) > 0
        assert "phieu-luong-all" in locked_all_pdf.headers.get("Content-Disposition", "")


def test_advanced_payroll_and_deactivation() -> None:
    with TestClient(app) as client:
        login(client)

        # 1. Create Teacher
        t_resp = client.post(
            "/api/teachers",
            json={
                "full_name": "TEST_TCH_ADV_1",
                "phone": "0900000003",
                "email": "tadv@test.com",
                "default_salary_coefficient": 1.0,
                "is_active": True,
            },
        )
        assert t_resp.status_code == 200
        t = t_resp.json()

        # 2. Create Class with advanced rates configuration
        c_resp = client.post(
            "/api/classes",
            json={
                "name": "TEST_CL_ADV",
                "subject": "TIENG_ANH",
                "school_year": "2099 - 2100",
                "default_fee": 150000,
                "notes": "",
                "is_active": True,
                "assignments": [
                    {
                        "teacher_id": t["id"],
                        "role": "main",
                        "salary_type": "fixed",
                        "fixed_salary_per_session": 400000,
                        "fixed_present_salary": 400000,
                        "fixed_late_salary": 250000,
                        "fixed_absent_salary": 5000,
                        "is_active": True,
                    }
                ],
            },
        )
        assert c_resp.status_code == 200
        c = c_resp.json()

        # 3. Create Student
        s_resp = client.post(
            "/api/students",
            json={
                "student_code": "TEST_ST_ADV",
                "full_name": "TEST_STUDENT_ADV",
                "parent_phone": "0900000200",
                "notes": "",
                "is_active": True,
            },
        )
        assert s_resp.status_code == 200
        s = s_resp.json()

        # 4. Enroll Student
        enroll_resp = client.post(
            "/api/enrollments",
            json={
                "student_id": s["id"],
                "class_ids": [c["id"]],
                "custom_fee": None,
                "is_exempt": False,
                "start_date": "2099-12-01",
                "is_active": True,
                "notes": "",
            },
        )
        assert enroll_resp.status_code == 200

        # 5. Add student attendance (so there is a class session)
        client.post("/api/attendance/bulk", json={"class_id": c["id"], "date": "2099-12-01", "items": [{"student_id": s["id"], "status": "P"}]})
        client.post("/api/attendance/bulk", json={"class_id": c["id"], "date": "2099-12-02", "items": [{"student_id": s["id"], "status": "P"}]})
        client.post("/api/attendance/bulk", json={"class_id": c["id"], "date": "2099-12-03", "items": [{"student_id": s["id"], "status": "P"}]})
        client.post("/api/attendance/bulk", json={"class_id": c["id"], "date": "2099-12-04", "items": [{"student_id": s["id"], "status": "P"}]})

        # 6. Add teacher attendance: 2 Present (P), 1 Late (M), 1 Absent (V)
        client.put("/api/teacher-attendance/single", json={"class_id": c["id"], "teacher_id": t["id"], "date": "2099-12-01", "status": "P"})
        client.put("/api/teacher-attendance/single", json={"class_id": c["id"], "teacher_id": t["id"], "date": "2099-12-02", "status": "P"})
        client.put("/api/teacher-attendance/single", json={"class_id": c["id"], "teacher_id": t["id"], "date": "2099-12-03", "status": "M"})
        client.put("/api/teacher-attendance/single", json={"class_id": c["id"], "teacher_id": t["id"], "date": "2099-12-04", "status": "V"})

        # 7. Lock Tuition Period to calculate and save Class Revenue
        lock_tuition_resp = client.post("/api/tuition/lock", json={"month": 12, "year": 2099, "class_id": None})
        assert lock_tuition_resp.status_code == 200

        # 8. Preview Payroll and Verify Calculations
        preview_resp = client.get("/api/payroll/preview?month=12&year=2099")
        assert preview_resp.status_code == 200
        preview_data = preview_resp.json()
        
        records = preview_data["records"]
        t_rec = next(r for r in records if r["teacher_id"] == t["id"])
        
        # Total salary: (2 * 400000) + (1 * 250000) + (1 * 5000) = 1,055,000
        assert t_rec["total_salary"] == 1055000
        c_item = next(cl for cl in t_rec["classes"] if cl["class_id"] == c["id"])
        assert c_item["sessions"] == 3  # P + M = 3 sessions
        assert c_item["sessions_present"] == 2
        assert c_item["sessions_late"] == 1
        assert c_item["sessions_absent"] == 1
        assert c_item["fixed_present_salary"] == 400000
        assert c_item["fixed_late_salary"] == 250000
        assert c_item["fixed_absent_salary"] == 5000

        # 9. Test soft deactivation of assignment
        # Deactivate assignment (is_active = False)
        update_cls_resp = client.put(
            f"/api/classes/{c['id']}",
            json={
                "name": "TEST_CL_ADV",
                "subject": "TIENG_ANH",
                "school_year": "2099 - 2100",
                "default_fee": 150000,
                "notes": "",
                "is_active": True,
                "assignments": [
                    {
                        "teacher_id": t["id"],
                        "role": "main",
                        "salary_type": "fixed",
                        "fixed_salary_per_session": 400000,
                        "fixed_present_salary": 400000,
                        "fixed_late_salary": 250000,
                        "fixed_absent_salary": 5000,
                        "is_active": False,  # Ngừng dạy
                    }
                ],
            },
        )
        assert update_cls_resp.status_code == 200

        # Preview payroll for Dec 2099: should STILL calculate because they have attendance records!
        preview_resp_dec = client.get("/api/payroll/preview?month=12&year=2099")
        assert preview_resp_dec.status_code == 200
        t_rec_dec = next(r for r in preview_resp_dec.json()["records"] if r["teacher_id"] == t["id"])
        assert len(t_rec_dec["classes"]) == 1
        assert t_rec_dec["total_salary"] == 1055000

        # Preview payroll for Jan 2100: should NOT calculate since assignment is Inactive and there is no attendance in Jan 2100!
        preview_resp_jan = client.get("/api/payroll/preview?month=1&year=2100")
        assert preview_resp_jan.status_code == 200
        t_rec_jan = next((r for r in preview_resp_jan.json()["records"] if r["teacher_id"] == t["id"]), None)
        if t_rec_jan:
            assert len(t_rec_jan["classes"]) == 0

        # 10. Test hard delete protection: attempting to remove the assignment completely from payload
        delete_assignment_resp = client.put(
            f"/api/classes/{c['id']}",
            json={
                "name": "TEST_CL_ADV",
                "subject": "TIENG_ANH",
                "school_year": "2099 - 2100",
                "default_fee": 150000,
                "notes": "",
                "is_active": True,
                "assignments": [],  # Tried to remove assignment completely
            },
        )
        # Should return 400 Bad Request
        assert delete_assignment_resp.status_code == 400
        assert "Không thể xóa giáo viên" in delete_assignment_resp.json()["detail"]

