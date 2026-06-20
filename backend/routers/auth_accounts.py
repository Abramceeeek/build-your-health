"""Email/password account auth — register, login, refresh (issues JWT access+refresh).

This is the non-Telegram identity path. Accounts are Users with `telegram_id` NULL and
an `email` + `password_hash`. Tokens are validated by `get_current_user`'s Bearer branch,
which yields `{"account_id": <User.id>}` to the rest of the API.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, verify_password,
)
from backend.dependencies.auth_deps import get_db
from backend.models.database import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LEN = 8


class RegisterIn(BaseModel):
    email: str
    password: str
    first_name: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "first_name": user.first_name},
    }


@router.post("/register")
async def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = _normalize_email(data.email)
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid email")
    if len(data.password) < MIN_PASSWORD_LEN:
        raise HTTPException(status_code=422, detail=f"Password must be at least {MIN_PASSWORD_LEN} characters")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    first_name = (data.first_name or "").strip() or email.split("@")[0]
    user = User(email=email, password_hash=hash_password(data.password), first_name=first_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _tokens(user)


@router.post("/login")
async def login(data: LoginIn, db: Session = Depends(get_db)):
    email = _normalize_email(data.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _tokens(user)


@router.post("/refresh")
async def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    account_id = decode_token(data.refresh_token, "refresh")
    user = db.get(User, account_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account not found")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}
