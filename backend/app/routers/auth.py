import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import SessionEvent, User
from ..schemas import LoginIn, SignupIn, UserIn
from ..security import admin_only, create_token, current_user, hash_password, verify_password
from ..serializers import session_dict, user_dict

router = APIRouter(prefix="/api", tags=["auth"])


async def _log(db: AsyncSession, request: Request, kind: str, user: User | None, name: str = "") -> None:
    db.add(SessionEvent(
        user_id=user.id if user else None,
        username=(user.username if user else name)[:255],
        kind=kind,
        ip=(request.client.host if request.client else "")[:64],
        user_agent=request.headers.get("user-agent", "")[:255],
    ))
    await db.commit()


def _token_response(user: User) -> dict:
    return {"access_token": create_token(user), "token_type": "bearer", "user": user_dict(user)}


@router.post("/auth/signup", status_code=201)
async def signup(body: SignupIn, request: Request, db: AsyncSession = Depends(get_db)):
    """Self-registration. New accounts are control-room operators.

    In a real deployment this would require admin approval or an invite code.
    """
    email = body.email.strip().lower()
    if (await db.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none():
        raise HTTPException(409, "An account with this e-mail already exists")
    base = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0]) or "user"
    username, n = base[:60], 1
    while (await db.execute(select(User.id).where(User.username == username))).first():
        n += 1
        username = f"{base[:56]}{n}"
    user = User(username=username, email=email, full_name=body.full_name.strip(), role="operator",
                password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await _log(db, request, "signup", user)
    return _token_response(user)


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    ident = body.username.strip()
    user = (await db.execute(
        select(User).where(or_(User.username == ident, func.lower(User.email) == ident.lower()))
    )).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        await _log(db, request, "failed", None, ident)
        raise HTTPException(401, "Invalid e-mail/username or password")
    await _log(db, request, "login", user)
    return _token_response(user)


@router.post("/auth/logout")
async def logout(request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await _log(db, request, "logout", user)
    return {"ok": True}


@router.get("/auth/me")
async def me(user: User = Depends(current_user)):
    return user_dict(user)


@router.get("/auth/sessions")
async def sessions(limit: int = 100, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Login history: admins see everyone, other users see their own."""
    stmt = select(SessionEvent).order_by(desc(SessionEvent.created_at)).limit(min(limit, 500))
    if user.role != "admin":
        stmt = stmt.where(SessionEvent.user_id == user.id)
    return [session_dict(e) for e in (await db.execute(stmt)).scalars()]


@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    return [user_dict(u) for u in users]


@router.post("/users", status_code=201)
async def create_user(body: UserIn, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    exists = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Username already exists")
    user = User(
        username=body.username,
        full_name=body.full_name,
        role=body.role,
        unit_id=body.unit_id,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    return user_dict(user)
