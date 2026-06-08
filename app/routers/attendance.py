from __future__ import annotations

from datetime import date
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Attendance, Enrollment
from app.schemas import AttendanceBulkSave
from app.services.tuition_service import is_period_locked, sync_attendance_to_tuition
from app.timezone import month_bounds

router = APIRouter(prefix="/api/attendance", tags=["attendance"], dependencies=[Depends(get_current_user)])


@router.get("")
def get_attendance(class_id: int, date: str, db: Session = Depends(get_db)):
    from app.timezone import parse_local_date

    target_date = parse_local_date(date)
    enrollments = db.scalars(
        select(Enrollment)
        .options(selectinload(Enrollment.student))
        .where(Enrollment.class_id == class_id, Enrollment.is_active.is_(True))
        .order_by(Enrollment.id)
    ).all()
    existing = {
        row.student_id: row
        for row in db.scalars(
            select(Attendance).where(Attendance.class_id == class_id, Attendance.date == target_date)
        ).all()
    }
    locked = is_period_locked(db, target_date.month, target_date.year)
    return {
        "date": target_date.isoformat(),
        "is_locked": locked,
        "students": [
            {
                "student_id": e.student_id,
                "student_code": e.student.student_code,
                "full_name": e.student.full_name,
                "status": existing.get(e.student_id).status if e.student_id in existing else "P",
            }
            for e in enrollments
        ],
    }


@router.post("/bulk")
def save_attendance(payload: AttendanceBulkSave, db: Session = Depends(get_db)):
    affected_student_ids = set()
    for item in payload.items:
        row = db.scalar(
            select(Attendance).where(
                Attendance.student_id == item.student_id,
                Attendance.class_id == payload.class_id,
                Attendance.date == payload.date,
            )
        )
        if row:
            row.status = item.status
        else:
            db.add(
                Attendance(
                    student_id=item.student_id,
                    class_id=payload.class_id,
                    date=payload.date,
                    status=item.status,
                )
            )
        affected_student_ids.add(item.student_id)
    db.commit()

    # Auto-sync: Cập nhật TuitionRecord đã chốt (nếu có)
    for sid in affected_student_ids:
        sync_attendance_to_tuition(db, sid, payload.class_id, payload.date)
    db.commit()

    return {"message": "Đã lưu điểm danh."}


class AttendanceSingleSave(BaseModel):
    class_id: int
    student_id: int
    date: date
    status: str | None = None


@router.get("/month")
def get_attendance_month(class_id: int, month: int, year: int, db: Session = Depends(get_db)):
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Tháng phải từ 1 đến 12.")
    if not (2000 <= year <= 2100):
        raise HTTPException(status_code=400, detail="Năm không hợp lệ.")

    start_date, end_date = month_bounds(year, month)

    # 1. Lấy học sinh trong lớp
    enrollments = db.scalars(
        select(Enrollment)
        .options(selectinload(Enrollment.student))
        .where(Enrollment.class_id == class_id, Enrollment.is_active.is_(True))
        .order_by(Enrollment.id)
    ).all()

    # 2. Lấy toàn bộ điểm danh của lớp trong tháng
    attendances = db.scalars(
        select(Attendance).where(
            Attendance.class_id == class_id,
            Attendance.date >= start_date,
            Attendance.date < end_date
        )
    ).all()

    # Map điểm danh theo cấu trúc: { student_id: { "YYYY-MM-DD": "P" } }
    att_map = {}
    for att in attendances:
        student_att = att_map.setdefault(att.student_id, {})
        student_att[att.date.isoformat()] = att.status

    locked = is_period_locked(db, month, year)

    return {
        "is_locked": locked,
        "students": [
            {
                "student_id": e.student_id,
                "student_code": e.student.student_code,
                "full_name": e.student.full_name,
                "attendance": att_map.get(e.student_id, {})
            }
            for e in enrollments
        ]
    }


@router.put("/single")
def save_single_attendance(payload: AttendanceSingleSave, db: Session = Depends(get_db)):
    row = db.scalar(
        select(Attendance).where(
            Attendance.student_id == payload.student_id,
            Attendance.class_id == payload.class_id,
            Attendance.date == payload.date,
        )
    )

    if payload.status in ["P", "V", "M"]:
        if row:
            row.status = payload.status
        else:
            db.add(Attendance(
                student_id=payload.student_id,
                class_id=payload.class_id,
                date=payload.date,
                status=payload.status
            ))
    else:
        # Nếu gửi status = None hoặc rỗng thì xóa điểm danh ngày đó
        if row:
            db.delete(row)

    db.commit()

    # Auto-sync: Cập nhật TuitionRecord đã chốt (nếu có)
    sync_attendance_to_tuition(db, payload.student_id, payload.class_id, payload.date)
    db.commit()

    return {"message": "Saved"}

