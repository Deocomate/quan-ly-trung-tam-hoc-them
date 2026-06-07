# app/routers/data_management.py
from __future__ import annotations
from datetime import datetime
from typing import List, Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from io import BytesIO

from app.auth import get_current_user
from app.database import get_db
from app.services import data_service

router = APIRouter(prefix="/api/data", tags=["data-management"], dependencies=[Depends(get_current_user)])

class ExportRequestPayload(BaseModel):
    targets: List[str] = Field(min_length=1, description="Danh sách các phân hệ dữ liệu cần xuất.")
    format: Literal["sql", "excel", "csv_zip"] = Field(description="Định dạng tệp dữ liệu trả về.")

@router.post("/export")
def export_data(payload: ExportRequestPayload, db: Session = Depends(get_db)):
    """
    API tiếp nhận yêu cầu xuất dữ liệu có cấu hình phân nhóm và định dạng đích.
    """
    valid_targets = {"students", "classes", "attendance", "tuition", "settings", "users"}
    invalid_targets = set(payload.targets) - valid_targets
    if invalid_targets:
        raise HTTPException(status_code=400, detail=f"Phân hệ không hợp lệ: {', '.join(invalid_targets)}")
        
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if payload.format == "sql":
        sql_text = data_service.export_to_sql(payload.targets)
        file_data = sql_text.encode("utf-8")
        filename = f"backup_data_{now_str}.sql"
        return Response(
            content=file_data,
            media_type="application/sql",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
        
    elif payload.format == "excel":
        excel_data = data_service.generate_formatted_excel(db, payload.targets)
        filename = f"export_data_{now_str}.xlsx"
        return StreamingResponse(
            BytesIO(excel_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
        
    elif payload.format == "csv_zip":
        zip_data = data_service.generate_csv_zip(db, payload.targets)
        filename = f"export_csv_{now_str}.zip"
        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

@router.post("/import")
async def import_data(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    API phục hồi cơ sở dữ liệu từ tập tin SQL dump.
    """
    if not file.filename.endswith(".sql"):
        raise HTTPException(status_code=400, detail="Vui lòng tải lên tệp định dạng .sql tương thích.")
        
    try:
        content_bytes = await file.read()
        sql_content = content_bytes.decode("utf-8")
        
        # Thực thi phục hồi qua transaction
        executed_statements = data_service.import_from_sql(sql_content)
        
        return {
            "success": True,
            "message": "Phục hồi dữ liệu hệ thống thành công.",
            "details": {
                "executed_inserts": executed_statements
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi cú pháp hoặc xung đột ràng buộc khi phục hồi: {str(exc)}")


class ConfirmBackupPayload(BaseModel):
    backup_date: str

@router.get("/check-auto-backup")
def check_auto_backup(db: Session = Depends(get_db)):
    from app.timezone import today_vietnam
    from app.services.settings_service import get_settings_map
    from datetime import date
    
    settings = get_settings_map(db)
    schedule_day_str = settings.get("backup_schedule_day", "")
    last_backup_date_str = settings.get("last_auto_backup_date", "")
    
    if not schedule_day_str:
        return {"due": False}
        
    try:
        backup_schedule_day = int(schedule_day_str)
    except ValueError:
        return {"due": False}
        
    if backup_schedule_day < 1 or backup_schedule_day > 28:
        return {"due": False}
        
    t_now = today_vietnam()
    
    # Tính ngày target tháng hiện tại
    target_current = date(t_now.year, t_now.month, backup_schedule_day)
    
    if t_now.day >= backup_schedule_day:
        t_target = target_current
    else:
        # Lùi về tháng trước
        if t_now.month == 1:
            t_target = date(t_now.year - 1, 12, backup_schedule_day)
        else:
            t_target = date(t_now.year, t_now.month - 1, backup_schedule_day)
            
    # So sánh với ngày sao lưu gần nhất
    if not last_backup_date_str:
        return {"due": True, "backup_date": t_target.isoformat()}
        
    try:
        t_last = date.fromisoformat(last_backup_date_str)
    except ValueError:
        return {"due": True, "backup_date": t_target.isoformat()}
        
    if t_last < t_target:
        return {"due": True, "backup_date": t_target.isoformat()}
        
    return {"due": False}

@router.post("/confirm-auto-backup")
def confirm_auto_backup(payload: ConfirmBackupPayload, db: Session = Depends(get_db)):
    from datetime import date
    from app.services.settings_service import upsert_setting
    
    try:
        date.fromisoformat(payload.backup_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Định dạng ngày không hợp lệ.")
        
    upsert_setting(db, "last_auto_backup_date", payload.backup_date)
    return {"success": True, "message": "Đã ghi nhận tải sao lưu tự động thành công."}
