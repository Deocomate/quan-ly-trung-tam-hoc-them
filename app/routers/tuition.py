from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import TuitionRecord, User
from app.schemas import TuitionLockRequest
from app.services.pdf_service import receipt_to_pdf
from app.services.settings_service import get_settings_map
from app.services.tuition_service import build_tuition_preview, check_tuition_staleness, get_period, list_records, lock_tuition_period

router = APIRouter(prefix="/api/tuition", tags=["tuition"], dependencies=[Depends(get_current_user)])


def _preview_to_dict(item):
    return {
        "student_id": item.student_id,
        "student_code": item.student_code,
        "student_name": item.student_name,
        "total_sessions": item.total_sessions,
        "total_amount": item.total_amount,
        "prior_debt": item.prior_debt,
        "grand_total": item.grand_total,
        "items": [row.__dict__ for row in item.items],
    }


@router.get("/preview")
def preview_tuition(month: int, year: int, class_id: int | None = None, db: Session = Depends(get_db)):
    period = get_period(db, month, year)
    return {
        "is_locked": bool(period and period.is_locked),
        "locked_at": period.locked_at.isoformat() if period and period.locked_at else None,
        "records": [_preview_to_dict(item) for item in build_tuition_preview(db, month, year, class_id)],
    }


@router.get("/check-stale")
def check_stale(month: int, year: int, class_id: int | None = None, db: Session = Depends(get_db)):
    """So sánh dữ liệu học phí đã chốt với dữ liệu điểm danh hiện tại."""
    return check_tuition_staleness(db, month, year, class_id)


@router.post("/lock")
def lock_tuition(payload: TuitionLockRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        records = lock_tuition_period(db, payload.month, payload.year, user, payload.class_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Đã chốt học phí.", "count": len(records)}


@router.get("/records")
def records(month: int | None = None, year: int | None = None, class_id: int | None = None, db: Session = Depends(get_db)):
    rows = list_records(db, month, year, class_id)
    from sqlalchemy import func
    results = []
    for row in rows:
        prior_debt_stmt = (
            select(func.coalesce(func.sum(TuitionRecord.total_amount - TuitionRecord.paid_amount), 0))
            .where(
                TuitionRecord.student_id == row.student_id,
                (TuitionRecord.year < row.year) | ((TuitionRecord.year == row.year) & (TuitionRecord.month < row.month))
            )
        )
        prior_debt = db.scalar(prior_debt_stmt) or 0
        results.append({
            "id": row.id,
            "student_id": row.student_id,
            "student_code": row.student.student_code,
            "student_name": row.student.full_name,
            "month": row.month,
            "year": row.year,
            "total_sessions": row.total_sessions,
            "total_amount": row.total_amount,
            "transfer_code": row.transfer_code,
            "paid_amount": row.paid_amount,
            "payment_status": row.payment_status,
            "prior_debt": prior_debt,
            "grand_total": row.total_amount + prior_debt,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "items": [
                {
                    "id": item.id,
                    "class_name": item.class_name,
                    "subject": item.subject,
                    "sessions": item.sessions,
                    "unit_fee": item.unit_fee,
                    "amount": item.amount,
                    "notes": item.notes,
                }
                for item in row.items
            ],
        })
    return results


@router.get("/records/{record_id}/pdf")
def record_pdf(record_id: int, db: Session = Depends(get_db)):
    record = db.get(TuitionRecord, record_id, options=[selectinload(TuitionRecord.student), selectinload(TuitionRecord.items)])
    if not record:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu thu.")
    pdf = receipt_to_pdf(record, get_settings_map(db))
    filename = f"phieu-thu-{record.student.student_code}-{record.month:02d}-{record.year}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export-pdf")
def export_pdf(
    month: int,
    year: int,
    class_id: int | None = None,
    student_id: int | None = None,
    db: Session = Depends(get_db),
):
    from app.services.tuition_service import is_period_locked
    
    # 1. Nếu kỳ học phí đã chốt, lấy từ Database
    if is_period_locked(db, month, year):
        rows = list_records(db, month, year, class_id)
        if student_id:
            rows = [r for r in rows if r.student_id == student_id]
    else:
        # 2. Nếu chưa chốt, tự dựng TuitionRecord tạm thời trong bộ nhớ
        from app.models import Student, TuitionRecordItem
        previews = build_tuition_preview(db, month, year, class_id)
        if student_id:
            previews = [p for p in previews if p.student_id == student_id]
            
        rows = []
        for p in previews:
            # Lấy thông tin học sinh
            student_obj = db.get(Student, p.student_id)
            if not student_obj:
                continue
            
            temp_record = TuitionRecord(
                student_id=p.student_id,
                student=student_obj,
                month=month,
                year=year,
                total_sessions=p.total_sessions,
                total_amount=p.total_amount,
                items=[
                    TuitionRecordItem(
                        class_name=item.class_name,
                        subject=item.subject,
                        sessions=item.sessions,
                        unit_fee=item.unit_fee,
                        amount=item.amount,
                        notes=item.notes,
                    )
                    for item in p.items
                ]
            )
            rows.append(temp_record)

    if not rows:
        raise HTTPException(status_code=404, detail="Chưa có phiếu thu để xuất.")
        
    settings = get_settings_map(db)
    pdf = receipt_to_pdf(rows, settings)
    
    if student_id and len(rows) == 1:
        filename = f"phieu-thu-{rows[0].student.student_code}-{month:02d}-{year}.pdf"
    else:
        filename = f"phieu-thu-{month:02d}-{year}.pdf"
        
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class TuitionItemNotesUpdate(BaseModel):
    notes: str | None = None


@router.put("/items/{item_id}/notes")
def update_tuition_item_notes(item_id: int, payload: TuitionItemNotesUpdate, db: Session = Depends(get_db)):
    from app.models import TuitionRecordItem
    item = db.get(TuitionRecordItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy chi tiết học phí.")
    item.notes = payload.notes
    db.commit()
    return {"message": "Đã cập nhật ghi chú.", "notes": item.notes}


class TuitionPaymentUpdate(BaseModel):
    paid_amount: int


@router.put("/records/{record_id}/payment")
def update_tuition_payment(record_id: int, payload: TuitionPaymentUpdate, db: Session = Depends(get_db)):
    record = db.get(TuitionRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu thu.")
    
    if payload.paid_amount < 0:
        raise HTTPException(status_code=400, detail="Số tiền thanh toán không được âm.")
        
    from app.services.tuition_service import allocate_student_payment
    allocate_student_payment(db, record.student_id, payload.paid_amount, record.month, record.year)
    
    db.refresh(record)
    return {
        "message": "Đã cập nhật thanh toán.",
        "paid_amount": record.paid_amount,
        "payment_status": record.payment_status,
        "debt": max(0, record.total_amount - record.paid_amount)
    }


@router.get("/export-excel")
def export_tuition_excel(
    month: int,
    year: int,
    class_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db)
):
    from app.services.excel_service import generate_tuition_excel
    
    excel_data = generate_tuition_excel(db, month, year, class_id, status)
    filename = f"hoc-phi-{month:02d}-{year}.xlsx"
    
    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


