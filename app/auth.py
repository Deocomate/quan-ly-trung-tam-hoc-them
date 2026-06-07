from __future__ import annotations

from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.timezone import now_vietnam

SECRET_KEY = "doi-khoa-bi-mat-trong-moi-truong-that"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12
COOKIE_NAME = "ql_lop_hoc_token"

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user: User) -> str:
    expires_at = now_vietnam() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user.id), "username": user.username, "exp": expires_at}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_user_from_request(request, db)
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn cần đăng nhập để tiếp tục.")


def get_user_from_request(request: Request, db: Session) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except Exception:
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user
