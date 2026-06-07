from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image as PILImage, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import BASE_DIR, get_db
from app.schemas import SettingUpdate
from app.services.settings_service import get_settings_map, upsert_setting

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(get_current_user)])

MAX_IMAGE_SIZE = 5 * 1024 * 1024
ASSETS_DIR = BASE_DIR / "static" / "assets"


def _target_asset_path(filename: str) -> Path:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    return ASSETS_DIR / filename


async def _read_uploaded_image(file: UploadFile, label: str) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"Vui lòng tải ảnh {label}.")
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"Ảnh {label} không được vượt quá 5MB.")
    return data


def _save_as_png(data: bytes, target: Path, label: str) -> None:
    try:
        with PILImage.open(BytesIO(data)) as image:
            image.seek(0)
            image.verify()
        with PILImage.open(BytesIO(data)) as image:
            image.seek(0)
            has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
            converted = image.convert("RGBA" if has_alpha else "RGB")
            output = BytesIO()
            converted.save(output, format="PNG", optimize=True)
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f"File {label} không phải ảnh hợp lệ. Vui lòng dùng PNG, JPEG, WebP, GIF, BMP hoặc TIFF.",
        )
    try:
        target.write_bytes(output.getvalue())
    except OSError:
        raise HTTPException(status_code=500, detail=f"Không thể lưu ảnh {label}. Vui lòng kiểm tra quyền ghi thư mục assets.")


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
    data = await _read_uploaded_image(file, "QR")
    target = _target_asset_path("qr.png")
    _save_as_png(data, target, "QR")
    return {"message": "Đã cập nhật mã QR thanh toán."}


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    data = await _read_uploaded_image(file, "Logo")
    target = _target_asset_path("logo.png")
    _save_as_png(data, target, "Logo")
    return {"message": "Đã cập nhật logo trung tâm thành công."}
