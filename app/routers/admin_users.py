from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password
from app.database import get_db
from app.models import User
from app.schemas import PasswordUpdate, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.username)).all()


@router.post("", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        is_active=payload.is_active,
        must_change_password=False,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại.") from exc
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    user.full_name = payload.full_name.strip()
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/password")
def update_password(user_id: int, payload: PasswordUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    user.password_hash = hash_password(payload.password)
    user.must_change_password = False
    db.commit()
    return {"message": "Đã cập nhật mật khẩu."}

