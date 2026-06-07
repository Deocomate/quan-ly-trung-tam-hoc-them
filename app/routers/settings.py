from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import BASE_DIR, get_db
from app.schemas import SettingUpdate
from app.services.settings_service import get_settings_map, upsert_setting

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_settings(db: Session = Depends(get_db)):
    return get_settings_map(db)


@router.put("")
def update_settings(payload: list[SettingUpdate], db: Session = Depends(get_db)):
    for item in payload:
        upsert_setting(db, item.key, item.value)
    return {"message": "Đã lưu cài đặt phiếu thu."}


@router.post("/qr")
async def upload_qr(file: UploadFile = File(...)):
    if file.content_type != "image/png":
        raise HTTPException(status_code=400, detail="Vui lòng tải ảnh QR định dạng PNG.")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ảnh QR không được vượt quá 5MB.")
    target = Path(BASE_DIR / "static" / "assets" / "qr.png")
    target.write_bytes(data)
    return {"message": "Đã cập nhật mã QR thanh toán."}


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    if file.content_type not in ("image/png", "image/jpeg"):
        raise HTTPException(status_code=400, detail="Vui lòng tải ảnh Logo định dạng PNG hoặc JPEG.")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ảnh Logo không được vượt quá 5MB.")
    target = Path(BASE_DIR / "static" / "assets" / "logo.png")
    
    from io import BytesIO
    from PIL import Image as PILImage
    try:
        img = PILImage.open(BytesIO(data))
        img.save(target, format="PNG")
    except Exception:
        target.write_bytes(data)
        
    return {"message": "Đã cập nhật logo trung tâm thành công."}
