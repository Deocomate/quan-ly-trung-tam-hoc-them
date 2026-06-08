from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import TeacherSalaryRecord, User, Teacher
from app.schemas import PayrollLockRequest
from app.services.payroll_service import build_payroll_preview, lock_payroll_period
from app.services.pdf_service import payroll_to_pdf
from app.services.settings_service import get_settings_map


def slugify_vietnamese(name: str) -> str:
    s = name.replace('đ', 'd').replace('Đ', 'D')
    s = unicodedata.normalize('NFKD', s)
    s = "".join([c for c in s if not unicodedata.combining(c)])
    s = s.replace(' ', '_')
    s = re.sub(r'[^a-zA-Z0-9_\-\.]', '', s)
    return s


class TemporaryPayrollItem:
    def __init__(self, class_name, sessions_count, class_revenue, salary_type, applied_rate, calculated_amount,
                 sessions_present=0, sessions_late=0, sessions_absent=0,
                 fixed_present_salary=0, fixed_late_salary=0, fixed_absent_salary=0):
        self.class_name = class_name
        self.sessions_count = sessions_count
        self.class_revenue = class_revenue
        self.salary_type = salary_type
        self.applied_rate = applied_rate
        self.calculated_amount = calculated_amount
        self.sessions_present = sessions_present
        self.sessions_late = sessions_late
        self.sessions_absent = sessions_absent
        self.fixed_present_salary = fixed_present_salary
        self.fixed_late_salary = fixed_late_salary
        self.fixed_absent_salary = fixed_absent_salary


class TemporaryPayrollRecord:
    def __init__(self, teacher, month, year, items, total_amount):
        self.teacher = teacher
        self.month = month
        self.year = year
        self.items = items
        self.total_amount = total_amount

router = APIRouter(prefix="/api/payroll", tags=["payroll"], dependencies=[Depends(get_current_user)])


@router.get("/preview")
def preview_payroll(month: int, year: int, db: Session = Depends(get_db)):
    try:
        preview = build_payroll_preview(db, month, year)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
        
    is_locked = any(item["is_locked"] for item in preview)
    return {
        "is_locked": is_locked,
        "records": preview
    }


@router.post("/lock")
def lock_payroll(payload: PayrollLockRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        records = lock_payroll_period(db, payload.month, payload.year, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Đã chốt bảng lương thành công.", "count": len(records)}


@router.get("/records")
def list_records(month: int | None = None, year: int | None = None, db: Session = Depends(get_db)):
    stmt = select(TeacherSalaryRecord).options(
        selectinload(TeacherSalaryRecord.teacher),
        selectinload(TeacherSalaryRecord.items)
    )
    if month is not None:
        stmt = stmt.where(TeacherSalaryRecord.month == month)
    if year is not None:
        stmt = stmt.where(TeacherSalaryRecord.year == year)
        
    rows = db.scalars(stmt.order_by(TeacherSalaryRecord.year.desc(), TeacherSalaryRecord.month.desc())).all()
    from sqlalchemy import func
    results = []
    for row in rows:
        prior_unpaid_stmt = (
            select(func.coalesce(func.sum(TeacherSalaryRecord.total_amount - TeacherSalaryRecord.paid_amount), 0))
            .where(
                TeacherSalaryRecord.teacher_id == row.teacher_id,
                (TeacherSalaryRecord.year < row.year) | ((TeacherSalaryRecord.year == row.year) & (TeacherSalaryRecord.month < row.month))
            )
        )
        prior_unpaid = db.scalar(prior_unpaid_stmt) or 0
        results.append({
            "id": row.id,
            "teacher_id": row.teacher_id,
            "teacher_name": row.teacher.full_name,
            "month": row.month,
            "year": row.year,
            "total_amount": row.total_amount,
            "paid_amount": row.paid_amount,
            "payment_status": row.payment_status,
            "prior_unpaid": prior_unpaid,
            "grand_total": row.total_amount + prior_unpaid,
            "is_locked": row.is_locked,
            "locked_at": row.locked_at.isoformat() if row.locked_at else None,
            "items": [
                {
                    "class_name": item.class_name,
                    "sessions_count": item.sessions_count,
                    "sessions_present": item.sessions_present,
                    "sessions_late": item.sessions_late,
                    "sessions_absent": item.sessions_absent,
                    "class_revenue": item.class_revenue,
                    "salary_type": item.salary_type,
                    "applied_rate": item.applied_rate,
                    "fixed_present_salary": item.fixed_present_salary,
                    "fixed_late_salary": item.fixed_late_salary,
                    "fixed_absent_salary": item.fixed_absent_salary,
                    "calculated_amount": item.calculated_amount,
                }
                for item in row.items
            ]
        })
    return results


@router.get("/records/{record_id}/pdf")
def record_pdf(record_id: int, db: Session = Depends(get_db)):
    record = db.get(
        TeacherSalaryRecord, 
        record_id, 
        options=[
            selectinload(TeacherSalaryRecord.teacher), 
            selectinload(TeacherSalaryRecord.items)
        ]
    )
    if not record:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu xác nhận lương.")
        
    pdf = payroll_to_pdf(record, get_settings_map(db))
    teacher_name_slug = slugify_vietnamese(record.teacher.full_name)
    filename = f"phieu-luong-{teacher_name_slug}-{record.month:02d}-{record.year}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export-pdf")
def export_payroll_pdf(
    month: int,
    year: int,
    teacher_id: int | None = None,
    db: Session = Depends(get_db)
):
    stmt = select(TeacherSalaryRecord).where(
        TeacherSalaryRecord.month == month,
        TeacherSalaryRecord.year == year,
        TeacherSalaryRecord.is_locked.is_(True)
    ).options(
        selectinload(TeacherSalaryRecord.teacher),
        selectinload(TeacherSalaryRecord.items)
    )
    if teacher_id is not None:
        stmt = stmt.where(TeacherSalaryRecord.teacher_id == teacher_id)
        
    locked_records = db.scalars(stmt).all()
    
    if locked_records:
        records = locked_records
        is_temp = False
    else:
        if teacher_id is not None:
            teachers = db.scalars(select(Teacher).where(Teacher.id == teacher_id, Teacher.is_active.is_(True))).all()
        else:
            teachers = db.scalars(select(Teacher).where(Teacher.is_active.is_(True))).all()
            
        if not teachers:
            raise HTTPException(status_code=404, detail="Không tìm thấy giáo viên.")
            
        records = []
        preview_list = build_payroll_preview(db, month, year)
        
        teacher_ids = {t.id for t in teachers}
        preview_items = [p for p in preview_list if p["teacher_id"] in teacher_ids]
        
        for p in preview_items:
            teacher = db.get(Teacher, p["teacher_id"])
            if not teacher:
                continue
                
            items = []
            for c in p["classes"]:
                items.append(TemporaryPayrollItem(
                    class_name=c["class_name"],
                    sessions_count=c["sessions"],
                    class_revenue=c["revenue"],
                    salary_type=c["salary_type"],
                    applied_rate=c["applied_rate"],
                    calculated_amount=c["amount"],
                    sessions_present=c.get("sessions_present", 0),
                    sessions_late=c.get("sessions_late", 0),
                    sessions_absent=c.get("sessions_absent", 0),
                    fixed_present_salary=c.get("fixed_present_salary", 0),
                    fixed_late_salary=c.get("fixed_late_salary", 0),
                    fixed_absent_salary=c.get("fixed_absent_salary", 0)
                ))
                
            records.append(TemporaryPayrollRecord(
                teacher=teacher,
                month=month,
                year=year,
                items=items,
                total_amount=p["total_salary"]
            ))
        is_temp = True
        
    if not records:
        raise HTTPException(status_code=404, detail="Không có dữ liệu lương để xuất PDF.")
        
    pdf = payroll_to_pdf(records, get_settings_map(db))
    
    prefix = "phieu-luong-tam" if is_temp else "phieu-luong"
    if teacher_id is not None:
        teacher_name_slug = slugify_vietnamese(records[0].teacher.full_name)
        filename = f"{prefix}-{teacher_name_slug}-{month:02d}-{year}.pdf"
    else:
        filename = f"{prefix}-all-{month:02d}-{year}.pdf"
        
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class PayrollPaymentUpdate(BaseModel):
    paid_amount: int


@router.put("/records/{record_id}/payment")
def update_payroll_payment(record_id: int, payload: PayrollPaymentUpdate, db: Session = Depends(get_db)):
    record = db.get(TeacherSalaryRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu lương.")
    
    if payload.paid_amount < 0:
        raise HTTPException(status_code=400, detail="Số tiền chi trả không được âm.")
        
    from app.services.payroll_service import allocate_teacher_payment
    allocate_teacher_payment(db, record.teacher_id, payload.paid_amount, record.month, record.year)
    
    db.refresh(record)
    return {
        "message": "Đã cập nhật chi trả lương.",
        "paid_amount": record.paid_amount,
        "payment_status": record.payment_status,
        "remaining": max(0, record.total_amount - record.paid_amount)
    }


@router.get("/export-excel")
def export_payroll_excel(
    month: int,
    year: int,
    status: str | None = None,
    db: Session = Depends(get_db)
):
    from app.services.excel_service import generate_payroll_excel
    
    excel_data = generate_payroll_excel(db, month, year, status)
    filename = f"luong-giao-vien-{month:02d}-{year}.xlsx"
    
    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

