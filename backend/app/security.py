import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db
from .models import User

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def _bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _is_detector(request: Request) -> bool:
    key = request.headers.get("x-api-key")
    return bool(key) and hmac.compare_digest(key, settings.detector_api_key)


async def _user_from_request(request: Request, db: AsyncSession) -> User | None:
    token = _bearer(request)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    return await db.get(User, int(payload["sub"]))


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    user = await _user_from_request(request, db)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


def require_roles(*roles: str):
    async def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return dep


staff = require_roles("admin", "operator")
admin_only = require_roles("admin")


async def require_detector(request: Request) -> str:
    if not _is_detector(request):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid detector API key")
    return "detector"


async def any_principal(request: Request, db: AsyncSession = Depends(get_db)) -> User | str:
    """Accepts either the detector API key or a logged-in user."""
    if _is_detector(request):
        return "detector"
    user = await _user_from_request(request, db)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user
