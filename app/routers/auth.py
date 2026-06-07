from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME, authenticate_user, create_access_token, get_current_user
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        response.status_code = 401
        return {"message": "Tên đăng nhập hoặc mật khẩu không đúng."}
    token = create_access_token(user)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=60 * 60 * 12)
    return {"message": "Đăng nhập thành công.", "user": UserOut.model_validate(user)}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"message": "Đã đăng xuất."}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user

